"""Tests for T11 multi-factor rescue/clearance priority engine (advisor/priorities.py)."""
import json
from pathlib import Path

import jsonschema

from advisor.assess import assess_collection
from advisor.priorities import compute_priorities, generate_project_priorities, load_priority_config
from advisor.report import compute_access_report
from tests.test_advisor_graph import _make_rich_mock_scenario

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
PRIORITIES_SCHEMA = json.loads((CONTRACTS / "priorities.schema.json").read_text(encoding="utf-8"))


def test_priority_config_marks_placeholder_weights():
    cfg = load_priority_config()
    assert "PLACEHOLDER" in cfg["weights_source"]
    assert set(cfg["weights"].keys()) == {
        "access_difficulty",
        "damage_severity",
        "population_exposure",
        "critical_facilities",
        "alternative_routes",
    }
    for val in cfg["weights"].values():
        assert 0.0 <= val <= 1.0


def test_mock_project_priorities_validates_against_contract():
    prio = generate_project_priorities("mock", backend="networkx")
    jsonschema.validate(prio, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert prio["mock"] is True
    assert prio["decision_support"] is True
    for item in prio["items"]:
        assert "dispatch" not in item["recommended_action"].lower()
        assert "ai " not in item["recommended_action"].lower()


def test_missing_population_stays_null_never_zero():
    seg_fc, places_fc = _make_rich_mock_scenario()
    state = assess_collection(seg_fc)
    acc = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="test_prio",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    prio = compute_priorities(places_fc, state, acc)
    jsonschema.validate(prio, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)

    by_id = {item["target_id"]: item for item in prio["items"]}
    # place_MOCK_WEST has population=None -> factor MUST be None (null) and listed in unknown_factors, never 0
    west = by_id["place_MOCK_WEST"]
    assert west["factors"]["population_exposure"] is None
    assert "population_exposure" in west["unknown_factors"]
    assert west["needs_verification"] is True

    # place_MOCK_NORTH has known population=400 and is completely cut off -> ranks #1
    assert prio["items"][0]["target_id"] == "place_MOCK_NORTH"
    assert prio["items"][0]["rank"] == 1
    assert prio["items"][0]["level"] == "critical"


def test_clearing_one_blocked_segment_changes_priority_ranking():
    """T11 Demo requirement: changing one road segment from blocked to open recomputes and changes ranking."""
    seg_fc, places_fc = _make_rich_mock_scenario()
    for feat in seg_fc["features"]:
        if feat["properties"]["segment_id"] == "seg_SOUTH_NARROW":
            feat["properties"]["width_tolerance_m"] = 0.10
            feat["properties"]["height_tolerance_m"] = 0.02

    # Before clearing seg_NORTH_BLOCKED: place_MOCK_NORTH is completely isolated and #1 priority.
    state_before = assess_collection(seg_fc)
    acc_before = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_before,
        project="test_prio_demo",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    prio_before = compute_priorities(places_fc, state_before, acc_before)
    jsonschema.validate(prio_before, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)

    rank_before = {item["target_id"]: item["rank"] for item in prio_before["items"]}
    score_before = {item["target_id"]: item["score"] for item in prio_before["items"]}
    assert rank_before["place_MOCK_NORTH"] == 1

    # Now clear seg_NORTH_BLOCKED via a responder field report ("cleared").
    reports = [
        {
            "segment_id": "seg_NORTH_BLOCKED",
            "kind": "cleared",
            "modes": ["fire_truck", "ambulance", "jeep", "foot"],
            "note": "Bulldozer cleared boulder pile",
            "created_at": "2026-10-31T04:00:00Z",
        }
    ]
    state_after = assess_collection(seg_fc, field_reports=reports)
    acc_after = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_after,
        project="test_prio_demo",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    prio_after = compute_priorities(places_fc, state_after, acc_after)
    jsonschema.validate(prio_after, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)

    rank_after = {item["target_id"]: item["rank"] for item in prio_after["items"]}
    score_after = {item["target_id"]: item["score"] for item in prio_after["items"]}

    # place_MOCK_NORTH is now reachable by all modes -> its urgency score drops sharply and place_MOCK_WEST rises to #1!
    assert score_after["place_MOCK_NORTH"] < score_before["place_MOCK_NORTH"]
    assert rank_after["place_MOCK_NORTH"] > rank_before["place_MOCK_NORTH"]
    assert rank_after["place_MOCK_WEST"] == 1

def test_f1_honest_reasons_unknown_vs_cut_off():
    from advisor.graph import build_topology, compute_access_report_networkx

    # 1. Real sample data test: samples/southfork_f01_4
    samples_dir = ROOT / "samples" / "southfork_f01_4"
    if (samples_dir / "segments.geojson").is_file():
        segs = json.loads((samples_dir / "segments.geojson").read_text(encoding="utf-8"))
        places = json.loads((samples_dir / "places.geojson").read_text(encoding="utf-8"))
        state = assess_collection(segs)
        top = build_topology(segs, places, state)
        acc = compute_access_report_networkx(top)
        prio = compute_priorities(places, state, acc)

        for item in prio["items"]:
            # Assert no reason contains "cut off", "passable", or "reachable by all" for places whose roads are only unknown
            for r in item["reasons"]:
                assert "cut off" not in r.lower(), f"Unexpected 'cut off' in reason for {item['target_id']}: {r}"
                assert "passable" not in r.lower(), f"Unexpected 'passable' in reason for {item['target_id']}: {r}"
                assert "reachable by all" not in r.lower(), f"Unexpected 'reachable by all' in reason for {item['target_id']}: {r}"

            if item["target_id"] == "osm_place_1":
                assert any("access unverified" in r for r in item["reasons"])
                assert any("not yet assessed" in r for r in item["reasons"])
                assert "verify" in item["recommended_action"].lower()
            elif item["target_id"] == "osm_place_0":
                assert any("staging base" in r.lower() for r in item["reasons"])

    # 2. Synthetic test with a truly blocked route must still say "cut off"
    seg_fc, places_fc = _make_rich_mock_scenario()
    state_mock = assess_collection(seg_fc)
    acc_mock = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_mock,
        project="test_truly_blocked",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    prio_mock = compute_priorities(places_fc, state_mock, acc_mock)
    north_item = next(it for it in prio_mock["items"] if it["target_id"] == "place_MOCK_NORTH")
    assert any("cut off" in r.lower() for r in north_item["reasons"])

