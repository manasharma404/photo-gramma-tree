"""Offline Markdown and HTML situation report generator (C2 / T17).

Generates sitrep.md and self-contained sitrep.html (zero external URLs/CDNs) from
access_report.json + priorities.json.

Honesty & terminology rules enforced:
  - Explicit "scenario" vs "measured" provenance banner and exact data timestamp.
  - "unknown" reachability or population is never treated as "open" or 0.
  - Rule/weight outputs are labelled "decision support" (never "AI" and never "dispatch").
  - Translation: Sarvam Translate (sarvamai/sarvam-translate, GPL-3.0, 4B LLM ~8 GB weights)
    requires torch + transformers + local multi-GB weights not installed in this offline
    environment, so reports are emitted in English-only with an explicit status note.

Usage:
    uv run python -m advisor.sitrep --project wayanad --out-dir data/projects/wayanad/sitrep
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from advisor import MODES
from advisor.assess import assess_collection, load_vehicle_config
from advisor.neo4j_client import project_paths
from advisor.priorities import compute_priorities
from advisor.report import compute_access_report

TRANSLATION_STATUS_NOTE = (
    "English only. Offline translation via Sarvam Translate (sarvamai/sarvam-translate, "
    "GPL-3.0, 4B-parameter LLM, ~8 GB weights) is not enabled on this laptop because "
    "PyTorch/Transformers and local 8 GB model weights are not installed in the offline runtime."
)


def _determine_data_label(
    segments_fc: dict[str, Any] | None,
    places_fc: dict[str, Any] | None,
    access_report: dict[str, Any],
) -> str:
    if access_report.get("mock") or (segments_fc and segments_fc.get("mock")):
        return "mock (contract fixture, not field data)"
    if segments_fc:
        if segments_fc.get("scenario_label"):
            return f"scenario ({segments_fc['scenario_label']})"
        feats = segments_fc.get("features") or []
        if feats and any((f.get("properties") or {}).get("source") == "scenario" for f in feats):
            return "scenario (reconstructed from cited reports, not drone-measured)"
        if feats and any((f.get("properties") or {}).get("measured") is True for f in feats):
            return "measured (drone photogrammetry)"
    if places_fc and places_fc.get("scenario_label"):
        return f"scenario ({places_fc['scenario_label']})"
    return "unmeasured assessment (awaiting photogrammetric DSM/orthophoto)"


def build_sitrep_context(
    *,
    project: str,
    access_report: dict[str, Any],
    priorities: dict[str, Any],
    segments_fc: dict[str, Any] | None = None,
    places_fc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    place_meta: dict[str, dict[str, Any]] = {}
    if places_fc:
        for feat in places_fc.get("features", []):
            props = feat.get("properties") or {}
            pid = str(props.get("place_id", ""))
            if pid:
                place_meta[pid] = props

    data_time = str(priorities.get("generated_at") or "timestamp not recorded")
    data_label = _determine_data_label(segments_fc, places_fc, access_report)

    cutoff_by_mode: dict[str, list[dict[str, Any]]] = {m: [] for m in MODES}
    unknown_by_mode: dict[str, list[dict[str, Any]]] = {m: [] for m in MODES}

    for p in access_report.get("places", []):
        pid = str(p["place_id"])
        meta = place_meta.get(pid, {})
        if meta.get("kind") == "landing_zone":
            continue
        pname = p.get("name") or meta.get("name") or pid
        pop = meta.get("population", p.get("population"))
        kind = meta.get("kind") or p.get("facility") or "settlement"
        reach = p.get("reachable") or {}
        entry = {
            "place_id": pid,
            "name": str(pname),
            "kind": str(kind),
            "population": pop,
        }
        for m in MODES:
            rval = reach.get(m)
            if rval is False:
                cutoff_by_mode[m].append(entry)
            elif rval is None:
                unknown_by_mode[m].append(entry)

    top_reopen = list(access_report.get("reopen_plan", []))[:3]
    top_priorities = list(priorities.get("items", []))[:5]
    for item in top_priorities:
        tid = str(item.get("target_id", ""))
        if tid in place_meta and place_meta[tid].get("name"):
            item = dict(item)

    return {
        "project": project,
        "data_time": data_time,
        "data_label": data_label,
        "computed_with": access_report.get("computed_with", "unknown"),
        "base_place_id": access_report.get("base_place_id"),
        "cutoff_by_mode": cutoff_by_mode,
        "unknown_by_mode": unknown_by_mode,
        "top_reopen": top_reopen,
        "top_priorities": top_priorities,
        "place_meta": place_meta,
        "weights_source": priorities.get("weights_source", "config/priority.yaml (PLACEHOLDER)"),
        "translation_note": TRANSLATION_STATUS_NOTE,
    }


def render_sitrep_markdown(ctx: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Post-Landslide Accessibility Situation Report — `{ctx['project']}`",
        "",
        f"- **Data provenance label:** `{ctx['data_label']}`",
        f"- **Data / generation time (UTC):** `{ctx['data_time']}`",
        f"- **Graph solver:** `{ctx['computed_with']}` (staging base: `{ctx['base_place_id'] or 'auto'}`)",
        "- **Scope:** Rule-based geometric & network **decision support** (not AI, not dispatch).",
        "",
        "## 1. Cut-Off and Unverified Places by Vehicle Class",
        "",
        "| Vehicle Mode | Cut-Off Count | Cut-Off Places (Population) | Unverified (`unknown`) Places |",
        "| :--- | ---: | :--- | :--- |",
    ]

    for m in MODES:
        cut_list = ctx["cutoff_by_mode"][m]
        unk_list = ctx["unknown_by_mode"][m]
        cut_str = (
            "; ".join(
                f"{e['name']} (pop: {e['population'] if e['population'] is not None else 'unknown'})"
                for e in cut_list
            )
            if cut_list
            else "None"
        )
        unk_str = (
            "; ".join(f"{e['name']} (`unknown`, never assumed open)" for e in unk_list)
            if unk_list
            else "None"
        )
        lines.append(f"| `{m}` | {len(cut_list)} | {cut_str} | {unk_str} |")

    lines.extend(["", "## 2. Top 3 Road-Reopen Actions (Graph Impact)", ""])
    if not ctx["top_reopen"]:
        lines.append("_No single-segment reopen action changes reachability under current graph state._")
    else:
        for act in ctx["top_reopen"]:
            people_str = (
                str(act["reconnects_people"])
                if act.get("reconnects_people") is not None
                else "unknown (population null)"
            )
            debris_str = (
                f"{act['debris_volume_m3']} m3"
                if act.get("debris_volume_m3") is not None
                else "not measured"
            )
            reconn_raw = act.get("reconnects_places", 0)
            if isinstance(reconn_raw, list):
                reconn_desc = f"{len(reconn_raw)} ({', '.join(str(x) for x in reconn_raw)})"
            else:
                reconn_desc = str(reconn_raw)
            reason_list = act.get("reasons") or ([act["reason"]] if act.get("reason") else [])
            reason_txt = "; ".join(str(r) for r in reason_list)
            ver_tag = " [needs field/drone verification]" if act.get("needs_verification") else ""
            lines.append(
                f"{act['rank']}. **Segment `{act['segment_id']}`** (target mode: `{act['mode']}`){ver_tag}"
            )
            lines.append(
                f"   - **Reconnects places:** {reconn_desc} | **Reconnects people:** {people_str} | **Debris volume:** {debris_str}"
            )
            lines.append(f"   - **Reasons:** {reason_txt}")

    lines.extend(
        [
            "",
            "## 3. Decision-Support Priority Summary (Hand-Set Weights — Not Dispatch)",
            "",
            f"_Weights source: `{ctx['weights_source']}`._",
            "",
        ]
    )
    for item in ctx["top_priorities"]:
        tid = str(item["target_id"])
        tname = ctx["place_meta"].get(tid, {}).get("name") or tid
        score_s = f"{item['score']:.2f}" if item.get("score") is not None else "unknown"
        lines.append(
            f"- **Rank {item['rank']} — {tname} (`{tid}`):** level `{item['level']}` "
            f"(score: `{score_s}`) — {item.get('recommended_action', '')}"
        )

    lines.extend(
        [
            "",
            "## 4. Language & Offline Translation Note",
            "",
            f"{ctx['translation_note']}",
            "",
        ]
    )
    return "\n".join(lines)


def render_sitrep_html(ctx: dict[str, Any]) -> str:
    esc = html.escape
    rows_html: list[str] = []
    for m in MODES:
        cut_list = ctx["cutoff_by_mode"][m]
        unk_list = ctx["unknown_by_mode"][m]
        cut_str = (
            ", ".join(
                f"{esc(e['name'])} <small>(pop: {esc(str(e['population'])) if e['population'] is not None else 'unknown'})</small>"
                for e in cut_list
            )
            if cut_list
            else "None"
        )
        unk_str = (
            ", ".join(f"{esc(e['name'])} <small>(unknown)</small>" for e in unk_list)
            if unk_list
            else "None"
        )
        rows_html.append(
            f"<tr><td><code>{esc(m)}</code></td><td><strong>{len(cut_list)}</strong></td>"
            f"<td>{cut_str}</td><td>{unk_str}</td></tr>"
        )

    reopen_items_html: list[str] = []
    for act in ctx["top_reopen"]:
        people_str = (
            esc(str(act["reconnects_people"]))
            if act.get("reconnects_people") is not None
            else "unknown (population null)"
        )
        debris_str = (
            f"{esc(str(act['debris_volume_m3']))} m&sup3;"
            if act.get("debris_volume_m3") is not None
            else "not measured"
        )
        reconn_raw = act.get("reconnects_places", 0)
        reconn_str = (
            esc(f"{len(reconn_raw)} ({', '.join(str(x) for x in reconn_raw)})")
            if isinstance(reconn_raw, list)
            else esc(str(reconn_raw))
        )
        reason_list = act.get("reasons") or ([act["reason"]] if act.get("reason") else [])
        reason_txt = "; ".join(str(r) for r in reason_list)
        ver = (
            " <span class='badge warn'>needs verification</span>"
            if act.get("needs_verification")
            else ""
        )
        reopen_items_html.append(
            f"<li><strong>#{act['rank']} — Segment <code>{esc(str(act['segment_id']))}</code> "
            f"(mode: <code>{esc(str(act['mode']))}</code>)</strong>{ver}<br>"
            f"Reconnects places: <strong>{reconn_str}</strong> | "
            f"Reconnects people: <strong>{people_str}</strong> | Debris volume: {debris_str}<br>"
            f"<em>Reasons:</em> {esc(reason_txt)}</li>"
        )
    reopen_block = (
        "<ol>" + "".join(reopen_items_html) + "</ol>"
        if reopen_items_html
        else "<p><em>No single-segment reopen action changes reachability under current graph state.</em></p>"
    )

    prio_html: list[str] = []
    for item in ctx["top_priorities"]:
        tid = str(item["target_id"])
        tname = str(ctx["place_meta"].get(tid, {}).get("name") or tid)
        score_s = f"{item['score']:.2f}" if item.get("score") is not None else "unknown"
        prio_html.append(
            f"<li><strong>Rank {item['rank']} — {esc(tname)} (<code>{esc(tid)}</code>)</strong>: "
            f"<span class='badge'>{esc(str(item['level']))}</span> (score: <code>{esc(score_s)}</code>) — "
            f"{esc(str(item.get('recommended_action', '')))}</li>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vortex Situation Report — {esc(ctx['project'])}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 1.5rem auto; max-width: 960px; padding: 0 1rem; color: #1a1a1a; line-height: 1.45; }}
    .banner {{ border: 2px solid #222; background: #fff8e6; padding: 0.85rem 1rem; border-radius: 6px; margin-bottom: 1.2rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0 1.25rem; }}
    th, td {{ border: 1px solid #444; padding: 0.5rem 0.65rem; text-align: left; vertical-align: top; }}
    th {{ background: #f0f0f0; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; border-radius: 3px; }}
    .badge {{ display: inline-block; padding: 0.1rem 0.45rem; border: 1px solid #333; border-radius: 4px; font-size: 0.85em; background: #eee; }}
    .badge.warn {{ background: #ffe3b3; }}
    .note {{ font-size: 0.92em; color: #333; border-left: 4px solid #555; padding-left: 0.75rem; }}
    @media print {{ body {{ max-width: none; margin: 0.5cm; }} .banner {{ background: #fff; }} }}
  </style>
</head>
<body>
  <h1>Post-Landslide Accessibility Situation Report — <code>{esc(ctx['project'])}</code></h1>
  <div class="banner">
    <strong>Data Provenance Label:</strong> <code>{esc(ctx['data_label'])}</code><br>
    <strong>Data / Generation Time (UTC):</strong> <code>{esc(ctx['data_time'])}</code> &nbsp;|&nbsp;
    <strong>Graph Solver:</strong> <code>{esc(str(ctx['computed_with']))}</code> &nbsp;|&nbsp;
    <strong>Scope:</strong> Rule-based geometric &amp; network <strong>decision support</strong> (not AI, not dispatch; <code>unknown</code> is never assumed <code>open</code>).
  </div>

  <h2>1. Cut-Off and Unverified Places by Vehicle Class</h2>
  <table>
    <thead>
      <tr>
        <th>Vehicle Mode</th>
        <th>Cut-Off Count</th>
        <th>Cut-Off Places (Population)</th>
        <th>Unverified (<code>unknown</code>) Places</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>

  <h2>2. Top 3 Road-Reopen Actions (Graph Impact)</h2>
  {reopen_block}

  <h2>3. Decision-Support Priority Summary (Hand-Set Weights — Not Dispatch)</h2>
  <p><small>Weights source: <code>{esc(str(ctx['weights_source']))}</code></small></p>
  <ul>
    {"".join(prio_html)}
  </ul>

  <h2>4. Language &amp; Offline Translation Note</h2>
  <p class="note">{esc(ctx['translation_note'])}</p>
</body>
</html>
"""


def generate_sitrep(
    project: str,
    out_dir: Path,
    *,
    data_root: Path | None = None,
    access_report_path: Path | None = None,
    priorities_path: Path | None = None,
    backend: str = "auto",
) -> dict[str, Path]:
    """Generate offline sitrep.md and sitrep.html for a project."""
    paths = project_paths(project, data_root=data_root)
    seg_fc = json.loads(paths["segments"].read_text(encoding="utf-8")) if paths["segments"].is_file() else None
    places_fc = json.loads(paths["places"].read_text(encoding="utf-8")) if paths["places"].is_file() else None

    proj_dir = paths["project_dir"]
    acc_file = access_report_path or (proj_dir / "access_report.json")
    prio_file = priorities_path or (proj_dir / "priorities.json")

    if acc_file.is_file():
        access_report = json.loads(acc_file.read_text(encoding="utf-8"))
    else:
        if seg_fc is None or places_fc is None:
            raise FileNotFoundError(f"Missing segments/places or precomputed access_report for '{project}'")
        state = assess_collection(seg_fc, config=load_vehicle_config())
        access_report = compute_access_report(
            segments_geojson=seg_fc,
            places_geojson=places_fc,
            advisor_state=state,
            project=project,
            backend=backend,
        )

    if prio_file.is_file():
        priorities = json.loads(prio_file.read_text(encoding="utf-8"))
    else:
        if seg_fc is None or places_fc is None:
            raise FileNotFoundError(f"Missing segments/places or precomputed priorities for '{project}'")
        state = assess_collection(seg_fc, config=load_vehicle_config())
        priorities = compute_priorities(places_fc, state, access_report)

    ctx = build_sitrep_context(
        project=project,
        access_report=access_report,
        priorities=priorities,
        segments_fc=seg_fc,
        places_fc=places_fc,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "sitrep.md"
    html_path = out_dir / "sitrep.html"
    md_path.write_text(render_sitrep_markdown(ctx), encoding="utf-8")
    html_path.write_text(render_sitrep_html(ctx), encoding="utf-8")
    return {"markdown": md_path, "html": html_path}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="Project name (e.g. wayanad, mock)")
    ap.add_argument("--out-dir", type=Path, required=True, help="Output directory for sitrep.md and sitrep.html")
    ap.add_argument("--access-report", type=Path, default=None, help="Optional access_report.json path")
    ap.add_argument("--priorities", type=Path, default=None, help="Optional priorities.json path")
    ap.add_argument("--backend", choices=("auto", "neo4j", "networkx"), default="auto")
    args = ap.parse_args()

    written = generate_sitrep(
        project=args.project,
        out_dir=args.out_dir,
        access_report_path=args.access_report,
        priorities_path=args.priorities,
        backend=args.backend,
    )
    print(f"Wrote situation report: {written['markdown']} and {written['html']}")


if __name__ == "__main__":
    main()
