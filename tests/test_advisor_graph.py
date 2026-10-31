"""Tests for T4 multi-vehicle graph routing, T5 reopen plan, and Neo4j GDS == NetworkX parity."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from advisor import MODES
from advisor.assess import assess_collection
from advisor.neo4j_client import open_driver
from advisor.report import compute_access_report, generate_project_report

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
ACCESS_SCHEMA = json.loads((CONTRACTS / "access_report.schema.json").read_text(encoding="utf-8"))


def _make_rich_mock_scenario():
    """Hand-built mock road network exercising open, partial, blocked, unknown, loops, and T5 ranking."""
    def seg_feat(sid, coords, min_w, max_obs, obs_len=0.0, cov=0.95, vol=0.0):
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "mock": True,
                "segment_id": sid,
                "osm_way_id": None,
                "highway": "secondary",
                "length_m": 45.0,
                "corridor_width_m": 6.0,
                "corridor_width_source": "osm_tag",
                "coverage_fraction": cov,
                "max_obstruction_m": max_obs,
                "obstructed_length_m": obs_len,
                "min_clear_width_m": min_w,
                "debris_volume_m3": vol,
                "debris_volume_tolerance_m3": 1.0 if vol is not None else None,
                "ml": {"p_blocked": None, "model": None},
                "measured": cov is not None,
            },
        }

    # Coordinates: Base [0.0, 0.0] -> Hub [0.001, 0.0] via two parallel routes (loop via [0.0005, 0.0005])
    # Hub -> North [0.001, 0.001] (blocked for all, 400 people)
    # Hub -> South [0.001, -0.001] (width 2.55 m: blocked for fire_truck, partial for ambulance, open for jeep/foot; 150 people)
    # Hub -> West [-0.001, 0.0] (blocked for all, population=null -> reconnects_people must be null, never 0)
    # Hub -> Fog [0.002, 0.0] (low coverage=0.30 -> unknown -> reachable must be null)
    segments_fc = {
        "type": "FeatureCollection",
        "mock": True,
        "features": [
            seg_feat("seg_MAIN_1", [[0.0, 0.0], [0.001, 0.0]], min_w=5.5, max_obs=0.01),
            seg_feat("seg_ALT_1", [[0.0, 0.0], [0.0005, 0.0005]], min_w=5.0, max_obs=0.01),
            seg_feat("seg_ALT_2", [[0.0005, 0.0005], [0.001, 0.0]], min_w=5.0, max_obs=0.01),
            seg_feat("seg_NORTH_BLOCKED", [[0.001, 0.0], [0.001, 0.001]], min_w=0.4, max_obs=2.1, obs_len=18.0, vol=65.0),
            seg_feat("seg_SOUTH_NARROW", [[0.001, 0.0], [0.001, -0.001]], min_w=2.55, max_obs=0.02, obs_len=0.0, vol=18.0),
            seg_feat("seg_WEST_BLOCKED", [[0.001, 0.0], [0.001, 0.002]], min_w=0.3, max_obs=1.9, obs_len=15.0, vol=40.0),
            seg_feat("seg_FOG_UNKNOWN", [[0.001, 0.0], [0.002, 0.0]], min_w=5.0, max_obs=0.01, cov=0.30, vol=None),
        ],
    }

    def place_feat(pid, name, kind, coords, pop, nsid):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coords},
            "properties": {
                "mock": True,
                "place_id": pid,
                "name": name,
                "kind": kind,
                "source": "osm",
                "population": pop,
                "population_source": "MOCK_CENSUS" if pop is not None else "PLACEHOLDER",
                "nearest_segment_id": nsid,
            },
        }

    places_fc = {
        "type": "FeatureCollection",
        "mock": True,
        "features": [
            place_feat("place_MOCK_BASE", "MOCK Staging Hospital", "hospital", [0.0, 0.0], None, "seg_MAIN_1"),
            place_feat("place_MOCK_HUB", "MOCK Hub Junction", "settlement", [0.001, 0.0], 80, "seg_MAIN_1"),
            place_feat("place_MOCK_NORTH", "MOCK North Hamlet", "settlement", [0.001, 0.001], 400, "seg_NORTH_BLOCKED"),
            place_feat("place_MOCK_SOUTH", "MOCK South Hamlet", "settlement", [0.001, -0.001], 150, "seg_SOUTH_NARROW"),
            place_feat("place_MOCK_WEST", "MOCK West Hamlet", "settlement", [0.001, 0.002], None, "seg_WEST_BLOCKED"),
            place_feat("place_MOCK_FOG", "MOCK Uncovered Shelter", "shelter", [0.002, 0.0], None, "seg_FOG_UNKNOWN"),
        ],
    }
    return segments_fc, places_fc


def test_contract_mock_project_validates():
    rep = generate_project_report("mock", backend="networkx")
    jsonschema.validate(rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert rep["mock"] is True
    assert rep["computed_with"] == "networkx-fallback"
    by_id = {p["place_id"]: p for p in rep["places"]}
    # lz_MOCK_1 is separated by unmeasured (unknown) segments -> reachability must be None, never True
    for m in MODES:
        assert by_id["lz_MOCK_1"]["reachable"][m] is None


def test_reachability_alternative_routes_and_reopen_plan_networkx():
    seg_fc, places_fc = _make_rich_mock_scenario()
    state = assess_collection(seg_fc)
    # Tighten width tolerance on seg_SOUTH_NARROW so 2.55 m is cleanly blocked for fire_truck (crawl 2.90m)
    # and partial for ambulance (crawl 2.20m) and open for jeep (open 2.42m).
    for feat in seg_fc["features"]:
        if feat["properties"]["segment_id"] == "seg_SOUTH_NARROW":
            feat["properties"]["width_tolerance_m"] = 0.10
            feat["properties"]["height_tolerance_m"] = 0.02
    state = assess_collection(seg_fc)

    rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="test_rich",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    jsonschema.validate(rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)

    by_id = {p["place_id"]: p for p in rep["places"]}
    assert by_id["place_MOCK_HUB"]["reachable"]["fire_truck"] is True
    assert by_id["place_MOCK_HUB"]["alternative_routes"]["fire_truck"] == 2

    # North is blocked for everyone
    assert all(by_id["place_MOCK_NORTH"]["reachable"][m] is False for m in MODES)

    # South is blocked for fire_truck, reachable for ambulance (partial), jeep (open), foot (open)
    assert by_id["place_MOCK_SOUTH"]["reachable"] == {
        "fire_truck": False,
        "ambulance": True,
        "jeep": True,
        "foot": True,
    }

    # Fog is behind low-coverage unknown segment -> None (unknown), never True and never False
    assert all(by_id["place_MOCK_FOG"]["reachable"][m] is None for m in MODES)
    assert by_id["place_MOCK_FOG"]["facility"] == "shelter"
    assert by_id["place_MOCK_NORTH"]["facility"] is None

    # T5 Reopen plan checks:
    plan = rep["reopen_plan"]
    assert len(plan) >= 6
    # Top rank must be seg_NORTH_BLOCKED (400 known people) for ambulance
    assert plan[0]["rank"] == 1
    assert plan[0]["segment_id"] == "seg_NORTH_BLOCKED"
    assert plan[0]["mode"] == "ambulance"
    assert plan[0]["reconnects_people"] == 400
    assert plan[0]["reconnects_places"] == 1

    # seg_SOUTH_NARROW for fire_truck reconnects 150 people -> ranks after 400-person clearances
    south_ft = next(x for x in plan if x["segment_id"] == "seg_SOUTH_NARROW" and x["mode"] == "fire_truck")
    assert south_ft["reconnects_people"] == 150

    # seg_WEST_BLOCKED reconnects a settlement with unknown population -> reconnects_people MUST be None (never 0)
    west_entries = [x for x in plan if x["segment_id"] == "seg_WEST_BLOCKED"]
    assert len(west_entries) == 4
    for entry in west_entries:
        assert entry["reconnects_people"] is None
        assert entry["reconnects_places"] == 1


def test_neo4j_gds_matches_networkx_identically():
    driver = open_driver(timeout_s=1.5)
    if driver is None:
        pytest.skip("Neo4j GDS not reachable from current environment (e.g. socket-restricted sandbox)")
    driver.close()

    seg_fc, places_fc = _make_rich_mock_scenario()
    for feat in seg_fc["features"]:
        if feat["properties"]["segment_id"] == "seg_SOUTH_NARROW":
            feat["properties"]["width_tolerance_m"] = 0.10
            feat["properties"]["height_tolerance_m"] = 0.02
    state = assess_collection(seg_fc)

    nx_rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="pytest_parity_check",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    neo_rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="pytest_parity_check",
        base_place_id="place_MOCK_BASE",
        backend="neo4j",
    )

    jsonschema.validate(neo_rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert nx_rep["computed_with"] == "networkx-fallback"
    assert neo_rep["computed_with"] == "neo4j-gds"

    nx_cmp = copy.deepcopy(nx_rep)
    neo_cmp = copy.deepcopy(neo_rep)
    nx_cmp.pop("computed_with")
    neo_cmp.pop("computed_with")
    assert neo_cmp == nx_cmp
