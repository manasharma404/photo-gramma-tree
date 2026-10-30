"""Explainable multi-vehicle road segment assessment engine (T3).

Rule-based passability evaluation using measured DSM road corridor geometry and
cited/PLACEHOLDER vehicle dimensions from config/vehicles.yaml.
Note: This module uses deterministic geometric threshold rules, never "AI".
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from advisor import MODES, STATUSES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VEHICLES_PATH = ROOT / "config" / "vehicles.yaml"


def _param_value(entry: Any) -> Any:
    if isinstance(entry, dict) and "value" in entry:
        return entry["value"]
    return entry


def load_vehicle_config(path: Path | None = None) -> dict[str, Any]:
    """Load config/vehicles.yaml and verify every parameter carries a source line."""
    cfg_path = path or DEFAULT_VEHICLES_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))

    rules: dict[str, Any] = {}
    for key, entry in raw.get("assessment_rules", {}).items():
        if not isinstance(entry, dict) or not str(entry.get("source", "")).strip():
            raise ValueError(f"assessment_rules.{key} missing source citation or PLACEHOLDER")
        rules[key] = entry["value"]

    vehicles: dict[str, dict[str, Any]] = {}
    for mode in MODES:
        if mode not in raw.get("vehicles", {}):
            raise ValueError(f"Missing vehicle profile for mode '{mode}' in {cfg_path}")
        v_raw = raw["vehicles"][mode]
        v_parsed: dict[str, Any] = {"label": v_raw.get("label", mode), "_sources": {}}
        for field, entry in v_raw.items():
            if field == "label":
                continue
            if not isinstance(entry, dict) or not str(entry.get("source", "")).strip():
                raise ValueError(f"vehicles.{mode}.{field} missing source citation or PLACEHOLDER")
            v_parsed[field] = entry["value"]
            v_parsed["_sources"][field] = entry["source"]
        vehicles[mode] = v_parsed

    return {"assessment_rules": rules, "vehicles": vehicles}


def _evaluate_geometry_for_mode(
    mode: str,
    profile: dict[str, Any],
    min_w: float,
    max_obs: float,
    obs_len: float | None,
    w_tol: float,
    h_tol: float,
) -> tuple[str, list[str], bool]:
    """Evaluate a single vehicle mode from corridor measurements with tolerances."""
    width_m = float(profile["width_m"])
    open_clear = float(profile["clearance_per_side_m"])
    part_clear = float(profile["partial_clearance_per_side_m"])
    open_w = width_m + 2.0 * open_clear
    part_w = width_m + 2.0 * part_clear

    open_h = float(profile["max_obstruction_open_m"])
    part_h = float(profile["max_obstruction_partial_m"])
    part_len = float(profile["max_obstructed_length_partial_m"])

    # 1. Definite geometric blockage (beyond tolerance).
    blocked_reasons: list[str] = []
    if min_w + w_tol < part_w:
        blocked_reasons.append(
            f"rule=width_blocked: min_clear_width_m={min_w:.2f}m (+tol {w_tol:.2f}m) "
            f"< min_crawl_width={part_w:.2f}m (vehicle {width_m:.2f}m + 2*{part_clear:.2f}m)"
        )
    if max_obs - h_tol > part_h:
        blocked_reasons.append(
            f"rule=obstruction_blocked: max_obstruction_m={max_obs:.2f}m (-tol {h_tol:.2f}m) "
            f"> max_crawl_obstruction={part_h:.2f}m"
        )
    if obs_len is not None and obs_len > part_len and (max_obs - h_tol > open_h):
        blocked_reasons.append(
            f"rule=obstructed_length_blocked: obstructed_length_m={obs_len:.2f}m "
            f"> max_crawl_length={part_len:.2f}m with max_obstruction_m={max_obs:.2f}m"
        )
    if blocked_reasons:
        return "blocked", blocked_reasons, False

    # 2. Within measurement tolerance of the passability (blocked/partial) threshold -> unknown.
    unknown_reasons: list[str] = []
    if abs(min_w - part_w) <= w_tol:
        unknown_reasons.append(
            f"rule=width_within_tolerance: min_clear_width_m={min_w:.2f}m within "
            f"±{w_tol:.2f}m of passability threshold {part_w:.2f}m -> unknown"
        )
    if abs(max_obs - part_h) <= h_tol:
        unknown_reasons.append(
            f"rule=obstruction_within_tolerance: max_obstruction_m={max_obs:.2f}m within "
            f"±{h_tol:.2f}m of passability threshold {part_h:.2f}m -> unknown"
        )
    if (max_obs > open_h - h_tol) and obs_len is None:
        unknown_reasons.append(
            f"rule=missing_obstructed_length: max_obstruction_m={max_obs:.2f}m exceeds "
            f"unobstructed bound {open_h - h_tol:.2f}m and obstructed_length_m is null -> unknown"
        )
    if unknown_reasons:
        return "unknown", unknown_reasons, True

    # 3. Passable, but either below full open clearance or within tolerance of open threshold -> partial.
    partial_reasons: list[str] = []
    needs_verify = False
    if min_w < open_w + w_tol:
        if abs(min_w - open_w) <= w_tol:
            needs_verify = True
            partial_reasons.append(
                f"rule=width_near_open_threshold: min_clear_width_m={min_w:.2f}m within "
                f"±{w_tol:.2f}m of open threshold {open_w:.2f}m (>{part_w:.2f}m crawl) -> partial"
            )
        else:
            partial_reasons.append(
                f"rule=width_partial: min_clear_width_m={min_w:.2f}m between crawl width "
                f"{part_w:.2f}m and open width {open_w:.2f}m -> partial"
            )
    if max_obs > open_h - h_tol:
        if abs(max_obs - open_h) <= h_tol:
            needs_verify = True
            partial_reasons.append(
                f"rule=obstruction_near_open_threshold: max_obstruction_m={max_obs:.2f}m within "
                f"±{h_tol:.2f}m of open limit {open_h:.2f}m (<{part_h:.2f}m crawl) -> partial"
            )
        else:
            len_txt = f", obstructed_length_m={obs_len:.2f}m <= {part_len:.2f}m" if obs_len is not None else ""
            partial_reasons.append(
                f"rule=obstruction_partial: max_obstruction_m={max_obs:.2f}m between open limit "
                f"{open_h:.2f}m and crawl limit {part_h:.2f}m{len_txt} -> partial"
            )
    if partial_reasons:
        return "partial", partial_reasons, needs_verify

    # 4. Unobstructed open passage beyond measurement tolerances.
    return (
        "open",
        [
            f"rule=geometry_open: min_clear_width_m={min_w:.2f}m >= {open_w:.2f}m (+tol {w_tol:.2f}m) "
            f"and max_obstruction_m={max_obs:.2f}m <= {open_h:.2f}m (-tol {h_tol:.2f}m)"
        ],
        False,
    )


def assess_segment(
    props: dict[str, Any],
    config: dict[str, Any] | None = None,
    ml_score: dict[str, Any] | None = None,
    field_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assess a single segment's passability per vehicle mode with explicit rule reasons."""
    cfg = config or load_vehicle_config()
    rules = cfg["assessment_rules"]
    vehicles = cfg["vehicles"]

    segment_id = str(props["segment_id"])
    status_by_mode: dict[str, str] = {}
    reasons_by_mode: dict[str, list[str]] = {}
    needs_verification = False

    # Case A: Report-reconstructed scenario segment (e.g. Wayanad T6).
    if props.get("source") == "scenario" and isinstance(props.get("status_by_mode"), dict):
        source = "scenario"
        needs_verification = True
        scenario_label = props.get(
            "scenario_label", "scenario reconstructed from reports, not drone-measured"
        )
        custom_reasons = props.get("scenario_reasons_by_mode") or {}
        citation = props.get("report_source")
        for mode in MODES:
            raw_st = props["status_by_mode"].get(mode, "unknown")
            st = raw_st if raw_st in STATUSES else "unknown"
            status_by_mode[mode] = st
            r_list = [f"rule=scenario_report ({scenario_label}): status={st}"]
            if citation:
                r_list.append(f"source: {citation}")
            for extra in custom_reasons.get(mode, []):
                r_list.append(str(extra))
            reasons_by_mode[mode] = r_list
    else:
        # Case B: Drone DSM geometry assessment.
        source = "geometry"
        measured = props.get("measured", True)
        cov = props.get("coverage_fraction")
        min_w = props.get("min_clear_width_m")
        max_obs = props.get("max_obstruction_m")
        obs_len = props.get("obstructed_length_m")

        min_cov = float(rules["min_coverage_fraction"])
        w_tol = (
            float(props["width_tolerance_m"])
            if props.get("width_tolerance_m") is not None
            else float(rules["default_width_tolerance_m"])
        )
        h_tol = (
            float(props["height_tolerance_m"])
            if props.get("height_tolerance_m") is not None
            else float(rules["default_height_tolerance_m"])
        )

        if measured is False:
            needs_verification = True
            for mode in MODES:
                status_by_mode[mode] = "unknown"
                reasons_by_mode[mode] = ["rule=unmeasured_segment: measured=false -> unknown"]
        elif cov is None:
            needs_verification = True
            for mode in MODES:
                status_by_mode[mode] = "unknown"
                reasons_by_mode[mode] = ["rule=missing_coverage: coverage_fraction is null -> unknown"]
        elif float(cov) < min_cov:
            needs_verification = True
            for mode in MODES:
                status_by_mode[mode] = "unknown"
                reasons_by_mode[mode] = [
                    f"rule=low_coverage: coverage_fraction={float(cov):.2f} < min_coverage_fraction={min_cov:.2f} -> unknown"
                ]
        elif min_w is None or max_obs is None:
            needs_verification = True
            missing = [
                name
                for name, val in (("min_clear_width_m", min_w), ("max_obstruction_m", max_obs))
                if val is None
            ]
            msg = f"rule=missing_geometry: {', '.join(missing)}=null -> unknown"
            for mode in MODES:
                status_by_mode[mode] = "unknown"
                reasons_by_mode[mode] = [msg]
        else:
            for mode in MODES:
                st, r_list, verify = _evaluate_geometry_for_mode(
                    mode=mode,
                    profile=vehicles[mode],
                    min_w=float(min_w),
                    max_obs=float(max_obs),
                    obs_len=float(obs_len) if obs_len is not None else None,
                    w_tol=w_tol,
                    h_tol=h_tol,
                )
                status_by_mode[mode] = st
                reasons_by_mode[mode] = r_list
                if verify:
                    needs_verification = True

    # Optional ML score fusion (Hard Rule 5: model NEVER silently flips geometric blocked to open).
    ml_block = ml_score if ml_score is not None else props.get("ml")
    if isinstance(ml_block, dict) and ml_block.get("p_blocked") is not None:
        p_blocked = float(ml_block["p_blocked"])
        model_name = ml_block.get("model") or "unspecified_model"
        ml_thresh = float(rules["ml_disagreement_p_blocked"])
        for mode in MODES:
            cur = status_by_mode[mode]
            if cur == "blocked" and p_blocked <= (1.0 - ml_thresh):
                # Never flip blocked to open; flag for verification.
                needs_verification = True
                reasons_by_mode[mode].append(
                    f"rule=ml_disagreement_keep_blocked: {model_name} p_blocked={p_blocked:.2f} "
                    f"<= {1.0 - ml_thresh:.2f}, keeping geometric blocked (needs_verification=true)"
                )
            elif cur in ("open", "partial") and p_blocked >= ml_thresh:
                needs_verification = True
                reasons_by_mode[mode].append(
                    f"rule=ml_disagreement_flag_review: {model_name} p_blocked={p_blocked:.2f} "
                    f">= {ml_thresh:.2f} while geometry={cur} (needs_verification=true)"
                )
            elif cur == "unknown":
                needs_verification = True
                reasons_by_mode[mode].append(
                    f"rule=ml_note_on_unknown: {model_name} p_blocked={p_blocked:.2f}; keeping unknown"
                )

    # Apply chronological ground responder field reports (T8).
    if field_reports:
        for rep in field_reports:
            kind = rep.get("kind", "other")
            target_modes = rep.get("modes") or list(MODES)
            target_modes = [m for m in target_modes if m in MODES]
            if not target_modes:
                target_modes = list(MODES)
            ts = rep.get("created_at") or "unspecified_time"
            note = (rep.get("note") or "").strip()
            note_suffix = f" ({note})" if note else ""

            source = "field_report"
            if kind == "dead_end":
                for m in target_modes:
                    status_by_mode[m] = "blocked"
                    reasons_by_mode[m].append(
                        f"rule=field_report: dead_end reported at {ts}{note_suffix} -> blocked"
                    )
            elif kind == "new_debris":
                needs_verification = True
                for m in target_modes:
                    status_by_mode[m] = "blocked"
                    reasons_by_mode[m].append(
                        f"rule=field_report: new_debris reported at {ts}{note_suffix} -> blocked"
                    )
            elif kind == "cleared":
                for m in target_modes:
                    status_by_mode[m] = "open"
                    reasons_by_mode[m].append(
                        f"rule=field_report: cleared reported at {ts}{note_suffix} -> open"
                    )
            else:
                needs_verification = True
                for m in target_modes:
                    reasons_by_mode[m].append(
                        f"rule=field_report: {kind} reported at {ts}{note_suffix} (status unchanged)"
                    )

    return {
        "segment_id": segment_id,
        "status_by_mode": status_by_mode,
        "reasons_by_mode": reasons_by_mode,
        "needs_verification": needs_verification,
        "source": source,
    }


def assess_collection(
    segments_geojson: dict[str, Any],
    config: dict[str, Any] | None = None,
    ml_scores: dict[str, Any] | None = None,
    field_reports: list[dict[str, Any]] | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Assess every feature in a segments.geojson FeatureCollection -> advisor_state payload."""
    cfg = config or load_vehicle_config()
    ml_by_seg: dict[str, dict[str, Any]] = {}
    if isinstance(ml_scores, dict):
        for item in ml_scores.get("scores", []):
            if "segment_id" in item:
                ml_by_seg[str(item["segment_id"])] = item

    reports_by_seg: dict[str, list[dict[str, Any]]] = {}
    for rep in field_reports or []:
        sid = str(rep.get("segment_id", ""))
        if sid:
            reports_by_seg.setdefault(sid, []).append(rep)

    is_mock = bool(segments_geojson.get("mock", False))
    assessed_segments: list[dict[str, Any]] = []
    for feat in segments_geojson.get("features", []):
        props = feat.get("properties", {})
        if props.get("mock") is True:
            is_mock = True
        sid = str(props["segment_id"])
        assessed_segments.append(
            assess_segment(
                props=props,
                config=cfg,
                ml_score=ml_by_seg.get(sid),
                field_reports=reports_by_seg.get(sid),
            )
        )

    ts = updated_at
    if ts is None and not is_mock:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    return {
        "mock": is_mock,
        "updated_at": ts,
        "segments": assessed_segments,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segments", type=Path, required=True, help="Path to segments.geojson")
    ap.add_argument("--vehicles", type=Path, default=DEFAULT_VEHICLES_PATH)
    ap.add_argument("--ml-scores", type=Path, default=None, help="Optional ml_scores.json")
    ap.add_argument("--out", type=Path, required=True, help="Output advisor_state JSON path")
    args = ap.parse_args()

    seg_data = json.loads(args.segments.read_text(encoding="utf-8"))
    ml_data = (
        json.loads(args.ml_scores.read_text(encoding="utf-8"))
        if args.ml_scores and args.ml_scores.exists()
        else None
    )
    cfg = load_vehicle_config(args.vehicles)
    state = assess_collection(seg_data, config=cfg, ml_scores=ml_data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"wrote {args.out} ({len(state['segments'])} segments)")


if __name__ == "__main__":
    main()
