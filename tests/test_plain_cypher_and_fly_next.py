"""Tests for F4 Plain-Cypher reachability and Idea 2 Fly Next uncertainty term.

Verifies:
1. Plain Cypher produces identical answers to NetworkX without GDS plugin.
2. Fly Next ranks unknown segments by dependent population x (1 + w * uncertainty).
3. Changing one segment's p_blocked flips the Fly Next ranking order (Idea 2).
4. Standalone plain-Cypher queries execute successfully.
"""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

from advisor import MODES
from advisor.assess import assess_collection
from advisor.graph import compute_fly_next
from advisor.neo4j_client import open_driver
from advisor.report import (
    compute_access_report,
    run_cypher_clear_first_query,
    run_cypher_fly_next_query,
    run_cypher_reach_query,
)
from tests.test_advisor_graph import ACCESS_SCHEMA, _make_rich_mock_scenario


def test_plain_cypher_matches_networkx_identically():
    """Verify that pure Cypher without GDS matches NetworkX with 100% parity."""
    driver = open_driver(timeout_s=1.5)
    if driver is None:
        pytest.skip("Neo4j not reachable from current environment")
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
        project="pytest_cypher_parity",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    cypher_rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="pytest_cypher_parity",
        base_place_id="place_MOCK_BASE",
        backend="cypher",
    )

    jsonschema.validate(cypher_rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)

    nx_cmp = copy.deepcopy(nx_rep)
    cypher_cmp = copy.deepcopy(cypher_rep)
    nx_cmp.pop("computed_with")
    cypher_cmp.pop("computed_with")

    # Identical places, reopen_plan, isolated, unverified, and fly_next
    assert cypher_cmp == nx_cmp


def test_southfork_parity_cypher_vs_networkx():
    """Verify that Plain Cypher matches NetworkX identically on the real South Fork project graph."""
    driver = open_driver(timeout_s=1.5)
    if driver is None:
        pytest.skip("Neo4j not reachable from current environment")
    driver.close()

    from advisor.report import generate_project_report
    rep_nx = generate_project_report("southfork_f01_4", backend="networkx")
    rep_cypher = generate_project_report("southfork_f01_4", backend="cypher")

    jsonschema.validate(rep_cypher, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)

    cmp_nx = copy.deepcopy(rep_nx)
    cmp_cy = copy.deepcopy(rep_cypher)
    cmp_nx.pop("computed_with")
    cmp_cy.pop("computed_with")
    assert cmp_cy == cmp_nx



def test_fly_next_uncertainty_multiplier_flips_ranking():
    """Test Idea 2: uncertainty term changes the Fly Next ranking order."""
    def seg_f(sid, coords, cov=0.30):
        return {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "mock": True,
                "segment_id": sid,
                "highway": "secondary",
                "length_m": 50.0,
                "coverage_fraction": cov,
                "measured": True,
            },
        }

    def place_f(pid, name, coords, pop, nsid):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coords},
            "properties": {
                "mock": True,
                "place_id": pid,
                "name": name,
                "kind": "settlement",
                "population": pop,
                "population_source": "CENSUS",
                "nearest_segment_id": nsid,
            },
        }

    # Base at [0, 0]
    # seg_BASE_A [0, 0] -> [0.001, 0] (open)
    # seg_ROAD_HIGH_POP [0.001, 0] -> [0.002, 0] (unknown, leads to Place A with 100 people)
    # seg_ROAD_MED_POP  [0.001, 0] -> [0.001, 0.001] (unknown, leads to Place B with 90 people)
    seg_fc = {
        "type": "FeatureCollection",
        "mock": True,
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [0.001, 0.0]]},
                "properties": {
                    "mock": True,
                    "segment_id": "seg_BASE_A",
                    "highway": "primary",
                    "length_m": 50.0,
                    "coverage_fraction": 0.95,
                    "min_clear_width_m": 6.0,
                    "max_obstruction_m": 0.01,
                    "measured": True,
                },
            },
            seg_f("seg_ROAD_HIGH_POP", [[0.001, 0.0], [0.002, 0.0]], cov=0.30),
            seg_f("seg_ROAD_MED_POP", [[0.001, 0.0], [0.001, 0.001]], cov=0.30),
        ],
    }

    places_fc = {
        "type": "FeatureCollection",
        "mock": True,
        "features": [
            place_f("place_BASE", "Staging Base", [0.0, 0.0], None, "seg_BASE_A"),
            place_f("place_HIGH_POP", "High Pop Settlement", [0.002, 0.0], 100, "seg_ROAD_HIGH_POP"),
            place_f("place_MED_POP", "Med Pop Settlement", [0.001, 0.001], 90, "seg_ROAD_MED_POP"),
        ],
    }

    state = assess_collection(seg_fc)

    # Case 1: No ML scores -> High Pop (100) ranks #1, Med Pop (90) ranks #2
    rep_baseline = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="pytest_fly_next_test",
        base_place_id="place_BASE",
        backend="networkx",
        w=0.50,
    )
    fn1 = rep_baseline["fly_next"]
    assert len(fn1) == 2
    assert fn1[0]["segment_id"] == "seg_ROAD_HIGH_POP"
    assert fn1[0]["score"] == 100.0
    assert fn1[1]["segment_id"] == "seg_ROAD_MED_POP"
    assert fn1[1]["score"] == 90.0

    # Case 2: Model is highly unsure about Med Pop (p_blocked = 0.50 -> uncertainty = 1.0)
    # and certain about High Pop (p_blocked = 0.0 -> uncertainty = 0.0).
    # Med Pop score = 90 * (1 + 0.5 * 1.0) = 135.0.
    # High Pop score = 100 * (1 + 0.5 * 0.0) = 100.0.
    # Med Pop should now rank #1!
    ml_scores_unsure = {
        "scores": [
            {"segment_id": "seg_ROAD_HIGH_POP", "p_blocked": 0.0, "p_clear": 1.0},
            {"segment_id": "seg_ROAD_MED_POP", "p_blocked": 0.50, "p_clear": 0.50},
        ]
    }
    rep_uncertain = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="pytest_fly_next_test",
        base_place_id="place_BASE",
        backend="networkx",
        ml_scores=ml_scores_unsure,
        w=0.50,
    )
    fn2 = rep_uncertain["fly_next"]
    assert len(fn2) == 2
    # Med Pop flipped to Rank 1 due to high uncertainty!
    assert fn2[0]["rank"] == 1
    assert fn2[0]["segment_id"] == "seg_ROAD_MED_POP"
    assert fn2[0]["score"] == 135.0
    assert fn2[0]["uncertainty"] == 1.0
    assert fn2[1]["rank"] == 2
    assert fn2[1]["segment_id"] == "seg_ROAD_HIGH_POP"
    assert fn2[1]["score"] == 100.0

    # Case 3: Re-survey / new model run clarifies Med Pop (p_blocked = 0.0 -> uncertainty = 0.0).
    # Ranking flips back: High Pop (100) is #1, Med Pop (90) is #2!
    ml_scores_clear = {
        "scores": [
            {"segment_id": "seg_ROAD_HIGH_POP", "p_blocked": 0.0, "p_clear": 1.0},
            {"segment_id": "seg_ROAD_MED_POP", "p_blocked": 0.0, "p_clear": 1.0},
        ]
    }
    rep_clear = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="pytest_fly_next_test",
        base_place_id="place_BASE",
        backend="networkx",
        ml_scores=ml_scores_clear,
        w=0.50,
    )
    fn3 = rep_clear["fly_next"]
    assert fn3[0]["segment_id"] == "seg_ROAD_HIGH_POP"
    assert fn3[1]["segment_id"] == "seg_ROAD_MED_POP"


def test_standalone_cypher_queries_execute():
    """Verify that standalone Cypher reach, clear first, and fly next queries execute cleanly."""
    driver = open_driver(timeout_s=1.5)
    if driver is None:
        pytest.skip("Neo4j not reachable from current environment")

    try:
        seg_fc, places_fc = _make_rich_mock_scenario()
        state = assess_collection(seg_fc)
        compute_access_report(
            segments_geojson=seg_fc,
            places_geojson=places_fc,
            advisor_state=state,
            project="pytest_cypher_queries",
            base_place_id="place_MOCK_BASE",
            backend="cypher",
        )

        reach = run_cypher_reach_query(driver, project="pytest_cypher_queries", base_junction_id="junc_0001")
        assert "junc_0001" in reach
        assert len(reach) >= 3

        cf = run_cypher_clear_first_query(driver, project="pytest_cypher_queries")
        assert isinstance(cf, list)

        fn = run_cypher_fly_next_query(driver, project="pytest_cypher_queries")
        assert isinstance(fn, list)
    finally:
        driver.close()
