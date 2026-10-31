"""Unit tests for vehicle profiles (T2) and road segment assessment engine (T3)."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from advisor import MODES
from advisor.assess import assess_collection, assess_segment, load_vehicle_config

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
ADVISOR_STATE_SCHEMA = json.loads((CONTRACTS / "advisor_state.schema.json").read_text(encoding="utf-8"))


def _make_props(**overrides):
    base = {
        "mock": True,
        "segment_id": "seg_TEST_01",
        "osm_way_id": None,
        "highway": "secondary",
        "length_m": 40.0,
        "corridor_width_m": 6.0,
        "corridor_width_source": "osm_tag",
        "coverage_fraction": 0.95,
        "max_obstruction_m": 0.02,
        "obstructed_length_m": 0.0,
        "min_clear_width_m": 5.0,
        "debris_volume_m3": 0.0,
        "debris_volume_tolerance_m3": 0.5,
        "ml": {"p_blocked": None, "model": None},
        "measured": True,
    }
    base.update(overrides)
    return base


def test_vehicle_config_has_sources_for_all_modes():
    cfg = load_vehicle_config()
    assert set(cfg["vehicles"].keys()) == set(MODES)
    for mode, v in cfg["vehicles"].items():
        for field, src in v["_sources"].items():
            assert src and isinstance(src, str), f"{mode}.{field} missing source"


def test_vehicle_config_rejects_missing_source(tmp_path):
    bad_yaml = (ROOT / "config" / "vehicles.yaml").read_text(encoding="utf-8").replace(
        'source: "PLACEHOLDER (~50% of 0.23 m IS 950 minimum ground clearance for unobstructed passage)"',
        'source: ""',
    )
    p = tmp_path / "bad_vehicles.yaml"
    p.write_text(bad_yaml, encoding="utf-8")
    with pytest.raises(ValueError, match="missing source"):
        load_vehicle_config(p)


def test_mock_example_segments_validate_and_default_to_unknown():
    seg_ex = json.loads((CONTRACTS / "examples" / "segments.example.geojson").read_text(encoding="utf-8"))
    state = assess_collection(seg_ex)
    jsonschema.validate(state, ADVISOR_STATE_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert state["mock"] is True
    for seg in state["segments"]:
        assert seg["needs_verification"] is True
        for mode in MODES:
            assert seg["status_by_mode"][mode] == "unknown"


def test_clean_wide_road_is_open_for_all_vehicles():
    res = assess_segment(_make_props(min_clear_width_m=5.0, max_obstruction_m=0.02, obstructed_length_m=0.0))
    assert res["source"] == "geometry"
    assert res["needs_verification"] is False
    for mode in MODES:
        assert res["status_by_mode"][mode] == "open"
        assert any("rule=geometry_open" in r for r in res["reasons_by_mode"][mode])


def test_multi_vehicle_differentiation_by_width():
    # Width 2.65 m with tight tolerance 0.10 m:
    # fire_truck crawl=2.90m -> 2.65+0.10=2.75 < 2.90 -> blocked
    # ambulance crawl=2.20m, open=2.60m (+0.10=2.70m) -> partial (near open threshold)
    # jeep open=2.42m (+0.10=2.52m) -> 2.65 >= 2.52 -> open
    # foot open=1.00m (+0.10=1.10m) -> open
    res = assess_segment(
        _make_props(min_clear_width_m=2.65, max_obstruction_m=0.02, width_tolerance_m=0.10, height_tolerance_m=0.02)
    )
    assert res["status_by_mode"] == {
        "fire_truck": "blocked",
        "ambulance": "partial",
        "jeep": "open",
        "foot": "open",
    }


def test_rubble_pile_blocks_vehicles_allows_foot_scramble():
    # 0.65 m rubble over 8 m length, wide corridor: blocks all wheeled vehicles, foot is partial scramble
    res = assess_segment(_make_props(min_clear_width_m=4.5, max_obstruction_m=0.65, obstructed_length_m=8.0))
    assert res["status_by_mode"] == {
        "fire_truck": "blocked",
        "ambulance": "blocked",
        "jeep": "blocked",
        "foot": "partial",
    }


def test_long_crawl_obstruction_becomes_blocked():
    # 0.20 m debris over 20.0 m exceeds jeep's max_obstructed_length_partial_m (15.0 m)
    res = assess_segment(
        _make_props(min_clear_width_m=4.5, max_obstruction_m=0.20, obstructed_length_m=20.0, height_tolerance_m=0.02)
    )
    assert res["status_by_mode"]["jeep"] == "blocked"
    assert any("obstructed_length_blocked" in r for r in res["reasons_by_mode"]["jeep"])
    assert res["status_by_mode"]["foot"] == "open"


def test_low_coverage_and_missing_values_produce_unknown():
    low_cov = assess_segment(_make_props(coverage_fraction=0.45))
    assert low_cov["needs_verification"] is True
    assert all(v == "unknown" for v in low_cov["status_by_mode"].values())

    missing_w = assess_segment(_make_props(min_clear_width_m=None))
    assert missing_w["needs_verification"] is True
    assert all(v == "unknown" for v in missing_w["status_by_mode"].values())

    missing_obs = assess_segment(_make_props(max_obstruction_m=None))
    assert all(v == "unknown" for v in missing_obs["status_by_mode"].values())

    # Crawl-height obstacle with null obstructed_length_m -> unknown for wheeled vehicles
    missing_len = assess_segment(_make_props(max_obstruction_m=0.19, obstructed_length_m=None, height_tolerance_m=0.02))
    assert missing_len["status_by_mode"]["jeep"] == "unknown"


def test_value_within_tolerance_of_passability_threshold_is_unknown():
    # fire_truck min crawl width = 2.90 m; 2.98 m with w_tol=0.20 m is within ±0.20 m -> unknown
    res = assess_segment(_make_props(min_clear_width_m=2.98, max_obstruction_m=0.01, width_tolerance_m=0.20))
    assert res["status_by_mode"]["fire_truck"] == "unknown"
    assert res["needs_verification"] is True
    assert any("width_within_tolerance" in r for r in res["reasons_by_mode"]["fire_truck"])


def test_ml_never_flips_geometric_blocked_to_open():
    # Hard Rule 5: geometric blocked stays blocked even if ML says p_blocked=0.02
    res = assess_segment(
        _make_props(min_clear_width_m=1.20, max_obstruction_m=1.80),
        ml_score={"p_blocked": 0.02, "model": "MOCK_crasar"},
    )
    for mode in MODES:
        assert res["status_by_mode"][mode] == "blocked"
        assert any("ml_disagreement_keep_blocked" in r for r in res["reasons_by_mode"][mode])
    assert res["needs_verification"] is True

    # Conversely, ML high p_blocked on open geometry flags needs_verification without hiding geometry
    res_open_disagree = assess_segment(
        _make_props(min_clear_width_m=5.0, max_obstruction_m=0.01),
        ml_score={"p_blocked": 0.85, "model": "MOCK_crasar"},
    )
    assert res_open_disagree["status_by_mode"]["jeep"] == "open"
    assert res_open_disagree["needs_verification"] is True


def test_field_reports_override_and_set_source():
    seg_fc = {
        "type": "FeatureCollection",
        "mock": True,
        "features": [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [0.001, 0]]}, "properties": _make_props()}],
    }
    reports = [
        {"segment_id": "seg_TEST_01", "kind": "dead_end", "modes": ["fire_truck", "ambulance"], "note": "culvert collapsed", "created_at": "2026-10-31T04:00:00Z"},
    ]
    state = assess_collection(seg_fc, field_reports=reports, updated_at="2026-10-31T04:00:00Z")
    jsonschema.validate(state, ADVISOR_STATE_SCHEMA, cls=jsonschema.Draft202012Validator)
    seg = state["segments"][0]
    assert seg["source"] == "field_report"
    assert seg["status_by_mode"]["fire_truck"] == "blocked"
    assert seg["status_by_mode"]["ambulance"] == "blocked"
    assert seg["status_by_mode"]["jeep"] == "open"
