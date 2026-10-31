"""Weighted multi-factor rescue/clearance priority engine (T11).

Decision support using hand-set PLACEHOLDER weights from config/priority.yaml.
Never called "AI" or "model", and never called "dispatch".
Missing population stays null in factors (unknown_factors), never 0.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from advisor import MODES
from advisor.assess import assess_collection, load_vehicle_config
from advisor.neo4j_client import project_paths
from advisor.report import compute_access_report

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRIORITY_PATH = ROOT / "config" / "priority.yaml"

FACILITY_SCORES = {
    "hospital": 100.0,
    "shelter": 80.0,
    "school": 75.0,
    "landing_zone": 60.0,
    "other_facility": 50.0,
    "settlement": 30.0,
}


def load_priority_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_PRIORITY_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    weights: dict[str, float] = {}
    for k, entry in raw.get("weights", {}).items():
        if isinstance(entry, dict):
            if not str(entry.get("source", "")).strip():
                raise ValueError(f"priority weight '{k}' missing source/PLACEHOLDER note")
            weights[k] = float(entry["value"])
        else:
            weights[k] = float(entry)

    pop_ref_entry = raw.get("scaling", {}).get("population_reference_max", {"value": 500})
    pop_ref = float(pop_ref_entry["value"] if isinstance(pop_ref_entry, dict) else pop_ref_entry)
    thresholds = raw.get("scaling", {}).get(
        "level_thresholds", {"critical": 75.0, "high": 50.0, "moderate": 25.0}
    )
    return {
        "weights_source": str(raw.get("weights_source", "config/priority.yaml (PLACEHOLDER)")),
        "weights": weights,
        "population_reference_max": pop_ref,
        "level_thresholds": {k: float(v) for k, v in thresholds.items()},
    }


def _score_to_level(score: float | None, thresholds: dict[str, float]) -> str:
    if score is None:
        return "unknown"
    if score >= thresholds["critical"]:
        return "critical"
    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["moderate"]:
        return "moderate"
    return "low"


def compute_priorities(
    places_geojson: dict[str, Any],
    advisor_state: dict[str, Any],
    access_report: dict[str, Any],
    priority_config: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compute schema-compliant priorities.json (decision_support=True) for all places."""
    cfg = priority_config or load_priority_config()
    weights = cfg["weights"]
    pop_ref = cfg["population_reference_max"]
    thresholds = cfg["level_thresholds"]

    is_mock = bool(
        places_geojson.get("mock")
        or advisor_state.get("mock")
        or access_report.get("mock")
    )

    seg_state_by_id = {str(s["segment_id"]): s for s in advisor_state.get("segments", [])}
    access_place_by_id = {str(p["place_id"]): p for p in access_report.get("places", [])}
    base_pid = access_report.get("base_place_id")

    # Map each isolated place to top reopen segment candidate if one exists
    reopen_hint_by_seg: dict[str, str] = {}
    for entry in access_report.get("reopen_plan", []):
        sid = entry.get("segment_id")
        if sid and sid not in reopen_hint_by_seg:
            reopen_hint_by_seg[str(sid)] = str(entry.get("mode", "ambulance"))

    scored_rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    for feat in places_geojson.get("features", []):
        props = feat.get("properties", {})
        if props.get("mock") is True:
            is_mock = True
        pid = str(props["place_id"])
        name = props.get("name") or pid
        kind = str(props.get("kind", "settlement"))
        pop = props.get("population")
        nsid = props.get("nearest_segment_id")

        acc = access_place_by_id.get(pid, {})
        reach = acc.get("reachable") or {m: None for m in MODES}
        alt_routes = acc.get("alternative_routes") or {m: 0 for m in MODES}
        nearest_seg = seg_state_by_id.get(str(nsid)) if nsid else None

        factors: dict[str, float | None] = {}
        unknown_factors: list[str] = []
        reasons: list[str] = []
        needs_ver = False

        # Factor 1: access_difficulty
        if all(reach.get(m) is None for m in MODES):
            factors["access_difficulty"] = None
            unknown_factors.append("access_difficulty")
            needs_ver = True
            reasons.append(f"{name}: reachability is unknown across all vehicle types")
        else:
            if any(reach.get(m) is None for m in MODES):
                needs_ver = True
            if reach.get("foot") is False:
                factors["access_difficulty"] = 100.0
                reasons.append(f"{name}: completely cut off (unreachable even on foot)")
            elif reach.get("jeep") is False and reach.get("ambulance") is False and reach.get("fire_truck") is False:
                if reach.get("foot") is True:
                    factors["access_difficulty"] = 80.0
                    reasons.append(f"{name}: reachable on foot only; all wheeled vehicles blocked")
                else:
                    factors["access_difficulty"] = 90.0
                    needs_ver = True
                    reasons.append(f"{name}: all wheeled vehicles blocked; foot access unverified")
            elif reach.get("ambulance") is False and reach.get("fire_truck") is False:
                factors["access_difficulty"] = 55.0
                reasons.append(f"{name}: reachable by 4x4 jeep/foot; blocked for ambulance and fire_truck")
            elif reach.get("fire_truck") is False:
                factors["access_difficulty"] = 30.0
                reasons.append(f"{name}: reachable by ambulance/jeep; blocked for heavy fire_truck")
            else:
                factors["access_difficulty"] = 0.0
                reasons.append(f"{name}: reachable by all vehicle classes including fire_truck and ambulance")

        # Factor 2: damage_severity (on nearest connecting segment)
        if nearest_seg is None:
            factors["damage_severity"] = None
            unknown_factors.append("damage_severity")
            needs_ver = True
        else:
            st_map = nearest_seg["status_by_mode"]
            if nearest_seg.get("needs_verification"):
                needs_ver = True
            if all(st_map.get(m) == "unknown" for m in MODES):
                factors["damage_severity"] = None
                unknown_factors.append("damage_severity")
                needs_ver = True
                reasons.append(f"Connecting road {nsid} has unknown damage state")
            else:
                pts = 0.0
                for m in MODES:
                    s = st_map.get(m, "unknown")
                    if s == "blocked":
                        pts += 25.0
                    elif s == "partial":
                        pts += 12.5
                    elif s == "unknown":
                        pts += 15.0
                        needs_ver = True
                factors["damage_severity"] = round(min(100.0, pts), 2)
                if pts >= 50.0:
                    reasons.append(f"Connecting segment {nsid} severely obstructed (damage factor {factors['damage_severity']:.0f}/100)")

        # Factor 3: population_exposure (Hard Rule 2: missing population = null, NEVER 0)
        if pop is None:
            factors["population_exposure"] = None
            unknown_factors.append("population_exposure")
            if kind == "settlement":
                needs_ver = True
                reasons.append("Settlement population is unknown (kept null, never assumed 0)")
        else:
            pop_int = int(pop)
            factors["population_exposure"] = round(min(100.0, (pop_int / pop_ref) * 100.0), 2)
            reasons.append(f"Known population: {pop_int} ({props.get('population_source', 'cited')})")

        # Factor 4: critical_facilities
        factors["critical_facilities"] = FACILITY_SCORES.get(kind, 40.0)
        if kind != "settlement":
            reasons.append(f"Critical facility type: {kind}")

        # Factor 5: alternative_routes
        if reach.get("ambulance") is None and reach.get("jeep") is None:
            factors["alternative_routes"] = None
            unknown_factors.append("alternative_routes")
            needs_ver = True
        else:
            n_alt = int(alt_routes.get("ambulance") or alt_routes.get("jeep") or 0)
            if n_alt == 0:
                factors["alternative_routes"] = 100.0
                reasons.append("0 passable wheeled-vehicle routes from staging base")
            elif n_alt == 1:
                factors["alternative_routes"] = 60.0
                reasons.append("Single passable corridor (no redundant route if secondary slip occurs)")
            else:
                factors["alternative_routes"] = 0.0
                reasons.append(f"{n_alt} edge-disjoint passable routes available")

        # Weighted score across known factors (only when at least access or damage is known).
        if factors["access_difficulty"] is None and factors["damage_severity"] is None:
            score: float | None = None
        else:
            num = 0.0
            den = 0.0
            for fk, w in weights.items():
                fval = factors.get(fk)
                if fval is not None and w > 0:
                    num += w * fval
                    den += w
            score = round(num / den, 2) if den > 0 else None

        level = _score_to_level(score, thresholds)

        # Actionable decision-support text (never "dispatch"; unknown is never "open").
        if pid == base_pid and score is not None and score < 25.0:
            action = "Decision support: active responder staging base; maintain approach clearance"
        elif score is None:
            action = "Decision support: insufficient survey coverage; verify road and settlement status on ground"
        elif reach.get("foot") is False:
            action = (
                f"Decision support: isolated from all ground modes; check helipad/rope access and "
                f"prioritize clearing blocked approach ({nsid or 'nearest corridor'})"
            )
        elif reach.get("ambulance") is False and reach.get("jeep") is False:
            if reach.get("foot") is True:
                action = (
                    f"Decision support: reachable on foot only; clear blockage toward {name} "
                    f"to restore 4x4/ambulance evacuation"
                )
            else:
                action = (
                    f"Decision support: all wheeled vehicles blocked and foot access unverified; "
                    f"verify foot access and clear blockage toward {name}"
                )
        elif reach.get("ambulance") is False:
            action = f"Decision support: 4x4 jeep access available; widen/clear {nsid or 'corridor'} for ambulance"
        elif (alt_routes.get("ambulance") or 0) <= 1:
            action = "Decision support: ambulance route open via single corridor; monitor for secondary debris"
        else:
            action = "Decision support: multi-vehicle access open with redundant routing"

        sort_key = (
            0 if score is not None else 1,
            -(score if score is not None else -1.0),
            -(int(pop) if pop is not None else -1),
            pid,
        )
        scored_rows.append(
            (
                sort_key,
                {
                    "target_id": pid,
                    "target_kind": "place",
                    "score": score,
                    "level": level,
                    "factors": factors,
                    "unknown_factors": unknown_factors,
                    "reasons": reasons,
                    "recommended_action": action,
                    "needs_verification": needs_ver,
                },
            )
        )

    scored_rows.sort(key=lambda item: item[0])
    items: list[dict[str, Any]] = []
    for idx, (_, body) in enumerate(scored_rows, start=1):
        items.append({"rank": idx, **body})

    ts = generated_at
    if ts is None and not is_mock:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return {
        "mock": is_mock,
        "decision_support": True,
        "weights": weights,
        "weights_source": cfg["weights_source"],
        "generated_at": ts,
        "items": items,
    }


def generate_project_priorities(
    project: str,
    out_path: Path | None = None,
    base_place_id: str | None = None,
    backend: str = "auto",
    data_root: Path | None = None,
    field_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    paths = project_paths(project, data_root=data_root)
    seg_fc = json.loads(paths["segments"].read_text(encoding="utf-8"))
    places_fc = json.loads(paths["places"].read_text(encoding="utf-8"))
    ml_data = (
        json.loads(paths["ml_scores"].read_text(encoding="utf-8"))
        if paths["ml_scores"].exists()
        else None
    )
    v_cfg = load_vehicle_config()
    state = assess_collection(seg_fc, config=v_cfg, ml_scores=ml_data, field_reports=field_reports)
    acc = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project=project,
        base_place_id=base_place_id,
        backend=backend,
    )
    prio = compute_priorities(places_fc, state, acc)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(prio, indent=2), encoding="utf-8")
    return prio


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--base", default=None)
    ap.add_argument("--backend", choices=("auto", "neo4j", "networkx"), default="auto")
    args = ap.parse_args()

    prio = generate_project_priorities(
        project=args.project,
        out_path=args.out,
        base_place_id=args.base,
        backend=args.backend,
    )
    print(f"wrote {args.out} ({len(prio['items'])} priority items, decision_support={prio['decision_support']})")


if __name__ == "__main__":
    main()
