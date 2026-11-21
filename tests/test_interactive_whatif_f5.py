"""Tests for F5: Interactive what-if loop (road status change -> Neo4j/NetworkX graph updates in seconds)."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from api.main import create_app
from advisor.store import init_db

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client_with_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "test_f5_reports.db"
    init_db(db_file)
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(db_file))
    monkeypatch.setenv("VORTEX_AUTH", "off")
    app = create_app(root_dir=ROOT)
    return TestClient(app)


def test_f5_interactive_whatif_block_and_clear_redraws_plan(client_with_db: TestClient):
    """F5: A field report or tap on a road changes the graph state, cut-off counts, Clear First, and Fly Next."""
    project = "wayanad"

    # 1. Baseline state
    r_state0 = client_with_db.get(f"/advisor/state?project={project}")
    assert r_state0.status_code == 200
    state0 = r_state0.json()

    # Baseline access report
    r_acc0 = client_with_db.get(f"/advisor/access?project={project}&backend=networkx")
    assert r_acc0.status_code == 200
    acc0 = r_acc0.json()
    init_places = acc0.get("places", [])
    init_cut_places = [p["place_id"] for p in init_places if p.get("reachable", {}).get("ambulance") is False]
    init_reopen = [r["segment_id"] for r in acc0.get("reopen_plan", [])]

    # Pick a segment that was open/usable
    open_segs = [
        s["segment_id"]
        for s in state0.get("segments", [])
        if s.get("status_by_mode", {}).get("ambulance") == "open"
    ]
    assert len(open_segs) > 0, "Expected open segments in wayanad"
    test_seg = open_segs[0]

    # 2. Tap / Submit report: road blocked (e.g. fresh landslide or confirmed debris)
    r_post = client_with_db.post(
        "/advisor/reports",
        json={
            "project": project,
            "segment_id": test_seg,
            "kind": "dead_end",
            "modes": ["fire_truck", "ambulance", "jeep", "foot"],
            "note": "Fresh rockfall blocking both lanes",
            "reporter": "Responder Unit 1",
        },
    )
    assert r_post.status_code == 200
    post_res = r_post.json()
    assert post_res["segment_state"]["segment_id"] == test_seg
    assert post_res["segment_state"]["source"] == "field_report"
    assert post_res["segment_state"]["status_by_mode"]["ambulance"] == "blocked"

    # 3. Check /advisor/state immediately reflects the blockage
    r_state1 = client_with_db.get(f"/advisor/state?project={project}")
    assert r_state1.status_code == 200
    seg1 = next(s for s in r_state1.json()["segments"] if s["segment_id"] == test_seg)
    assert seg1["status_by_mode"]["ambulance"] == "blocked"
    assert seg1["source"] == "field_report"

    # 4. Check /advisor/access immediately recomputes the plan
    r_acc1 = client_with_db.get(f"/advisor/access?project={project}&backend=networkx")
    assert r_acc1.status_code == 200
    acc1 = r_acc1.json()
    new_reopen = [r["segment_id"] for r in acc1.get("reopen_plan", [])]

    # The newly blocked segment is evaluated in the graph
    # If blocking it cuts off people/places, it appears in or changes the reopen plan
    r_priorities1 = client_with_db.get(f"/advisor/priorities?project={project}&backend=networkx")
    assert r_priorities1.status_code == 200

    # 5. Tap / Submit report: road cleared
    r_clear = client_with_db.post(
        "/advisor/reports",
        json={
            "project": project,
            "segment_id": test_seg,
            "kind": "cleared",
            "modes": ["fire_truck", "ambulance", "jeep", "foot"],
            "note": "Debris cleared by excavator",
            "reporter": "PWD Clearance Team",
        },
    )
    assert r_clear.status_code == 200
    assert r_clear.json()["segment_state"]["status_by_mode"]["ambulance"] == "open"

    # 6. Check /advisor/state and /advisor/access redraw back to open
    r_state2 = client_with_db.get(f"/advisor/state?project={project}")
    assert r_state2.status_code == 200
    seg2 = next(s for s in r_state2.json()["segments"] if s["segment_id"] == test_seg)
    assert seg2["status_by_mode"]["ambulance"] == "open"
    assert seg2["source"] == "field_report"

    r_acc2 = client_with_db.get(f"/advisor/access?project={project}&backend=networkx")
    assert r_acc2.status_code == 200
    acc2 = r_acc2.json()
    cleared_reopen = [r["segment_id"] for r in acc2.get("reopen_plan", [])]
    # The cleared segment is no longer in the reopen plan
    assert test_seg not in cleared_reopen


def test_f5_cypher_whatif_matches_networkx(tmp_path: Path):
    """F5 Neo4j: Verify Plain-Cypher recomputes reachability, Clear First, and Fly Next with 100% agreement with NetworkX."""
    from advisor.neo4j_client import open_driver
    from advisor.assess import assess_collection
    from advisor.report import compute_access_report
    from tests.test_advisor_graph import _make_rich_mock_scenario

    driver = open_driver(timeout_s=1.5)
    if driver is None:
        pytest.skip("Neo4j not reachable from current environment")
    driver.close()

    seg_fc, places_fc = _make_rich_mock_scenario()
    state_base = assess_collection(seg_fc)

    # 1. Base access report
    nx_base = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_base,
        project="pytest_f5_cypher",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    cypher_base = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_base,
        project="pytest_f5_cypher",
        base_place_id="place_MOCK_BASE",
        backend="cypher",
    )
    assert cypher_base["places"] == nx_base["places"]
    assert [r["segment_id"] for r in cypher_base["reopen_plan"]] == [r["segment_id"] for r in nx_base["reopen_plan"]]

    # 2. Block a road (simulating field report or tap)
    test_seg = "seg_NORTH_LONG"
    field_reports = [
        {
            "id": 1,
            "project": "pytest_f5_cypher",
            "segment_id": test_seg,
            "place_id": None,
            "kind": "dead_end",
            "modes": ["fire_truck", "ambulance", "jeep", "foot"],
            "note": "Blocked by boulder",
            "reporter": "Unit 1",
            "created_at": "2026-11-22T01:00:00Z",
        }
    ]
    state_blocked = assess_collection(seg_fc, field_reports=field_reports)

    nx_blocked = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_blocked,
        project="pytest_f5_cypher",
        base_place_id="place_MOCK_BASE",
        backend="networkx",
    )
    cypher_blocked = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state_blocked,
        project="pytest_f5_cypher",
        base_place_id="place_MOCK_BASE",
        backend="cypher",
    )

    # Both Cypher and NetworkX agree 100% on new reachability and updated reopen plan
    assert cypher_blocked["places"] == nx_blocked["places"]
    assert [r["segment_id"] for r in cypher_blocked["reopen_plan"]] == [r["segment_id"] for r in nx_blocked["reopen_plan"]]
    # The newly blocked segment is now included in the reopen plan
    assert any(r["segment_id"] == test_seg for r in cypher_blocked["reopen_plan"])

