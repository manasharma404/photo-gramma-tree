"""Tests for T6 Wayanad (Chooralmala-Mundakkai) offline scenario builder and T3-T5-T11 pipeline."""
import json
from pathlib import Path

import jsonschema
import pytest

from advisor.assess import assess_collection
from advisor.priorities import compute_priorities
from advisor.report import compute_access_report, generate_project_report
from scripts.prefetch_wayanad import (
    CHOORALMALA_BRIDGE_WAY_ID,
    SCENARIO_LABEL,
    build_wayanad_files,
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
SEGMENTS_SCHEMA = json.loads((CONTRACTS / "segments.schema.json").read_text(encoding="utf-8"))
PLACES_SCHEMA = json.loads((CONTRACTS / "places.schema.json").read_text(encoding="utf-8"))
STATE_SCHEMA = json.loads((CONTRACTS / "advisor_state.schema.json").read_text(encoding="utf-8"))
ACCESS_SCHEMA = json.loads((CONTRACTS / "access_report.schema.json").read_text(encoding="utf-8"))
PRIORITIES_SCHEMA = json.loads((CONTRACTS / "priorities.schema.json").read_text(encoding="utf-8"))


def _synthetic_wayanad_overpass() -> dict:
    """Offline Overpass fixture mirroring Chooralmala -> Bridge (380928388) -> Mundakkai -> Punchirimattom."""
    return {
        "elements": [
            # Nodes from north (Meppadi/Chooralmala) across bridge to south (Mundakkai/Punchirimattom)
            {"type": "node", "id": 1001, "lon": 76.1585, "lat": 11.5030},
            {"type": "node", "id": 1002, "lon": 76.1598, "lat": 11.4992, "tags": {"place": "village", "name": "Chooralmala"}},
            {"type": "node", "id": 1003, "lon": 76.1602, "lat": 11.4991},
            {"type": "node", "id": 1004, "lon": 76.1600, "lat": 11.4981, "tags": {"amenity": "school", "name": "GVHSS Vellarmala"}},
            {"type": "node", "id": 1005, "lon": 76.1557, "lat": 11.4865, "tags": {"place": "village", "name": "Mundakkai"}},
            {"type": "node", "id": 1006, "lon": 76.1516, "lat": 11.4818, "tags": {"place": "hamlet", "name": "Punchirimattom"}},
            # Ways sharing junction nodes 1002, 1003, 1005
            {"type": "way", "id": 30778557, "nodes": [1001, 1002], "tags": {"highway": "primary"}},
            {"type": "way", "id": CHOORALMALA_BRIDGE_WAY_ID, "nodes": [1002, 1003], "tags": {"highway": "tertiary", "bridge": "yes"}},
            {"type": "way", "id": 380928408, "nodes": [1003, 1004, 1005], "tags": {"highway": "tertiary"}},
            {"type": "way", "id": 380928999, "nodes": [1005, 1006], "tags": {"highway": "residential"}},
        ]
    }


def test_build_wayanad_files_offline_fixture_runs_t3_to_t5(tmp_path: Path):
    out_dir = tmp_path / "wayanad"
    counts = build_wayanad_files(_synthetic_wayanad_overpass(), out_dir)
    assert counts["segments"] >= 4
    assert counts["places"] >= 5
    assert (out_dir / "wayanad_osm.gpkg").exists()
    assert (out_dir / "scenario_sources.json").exists()

    seg_fc = json.loads((out_dir / "roads" / "segments.geojson").read_text(encoding="utf-8"))
    places_fc = json.loads((out_dir / "places.geojson").read_text(encoding="utf-8"))
    sources_meta = json.loads((out_dir / "scenario_sources.json").read_text(encoding="utf-8"))

    jsonschema.validate(seg_fc, SEGMENTS_SCHEMA, cls=jsonschema.Draft202012Validator)
    jsonschema.validate(places_fc, PLACES_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert sources_meta["label"] == SCENARIO_LABEL
    assert all(f["properties"]["scenario_label"] == SCENARIO_LABEL for f in seg_fc["features"])

    state = assess_collection(seg_fc)
    jsonschema.validate(state, STATE_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert all(s["source"] == "scenario" for s in state["segments"])
    assert all(SCENARIO_LABEL in s["reasons_by_mode"]["ambulance"][0] for s in state["segments"])

    rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="wayanad_fixture",
        backend="networkx",
    )
    jsonschema.validate(rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)
    # Chooralmala bridge segment must appear in reopen_plan reconnecting Mundakkai & GVHSS Vellarmala!
    assert len(rep["reopen_plan"]) >= 1
    top_seg = rep["reopen_plan"][0]["segment_id"]
    bridge_segs = {
        f["properties"]["segment_id"]
        for f in seg_fc["features"]
        if f["properties"]["osm_way_id"] == CHOORALMALA_BRIDGE_WAY_ID
    }
    assert top_seg in bridge_segs

    prio = compute_priorities(places_fc, state, rep)
    jsonschema.validate(prio, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert prio["decision_support"] is True


def test_prefetched_wayanad_project_end_to_end_if_present():
    wayanad_dir = ROOT / "data" / "projects" / "wayanad"
    if not (wayanad_dir / "roads" / "segments.geojson").exists():
        pytest.skip("data/projects/wayanad not prefetched on this machine")

    seg_fc = json.loads((wayanad_dir / "roads" / "segments.geojson").read_text(encoding="utf-8"))
    places_fc = json.loads((wayanad_dir / "places.geojson").read_text(encoding="utf-8"))

    jsonschema.validate(seg_fc, SEGMENTS_SCHEMA, cls=jsonschema.Draft202012Validator)
    jsonschema.validate(places_fc, PLACES_SCHEMA, cls=jsonschema.Draft202012Validator)

    state = assess_collection(seg_fc)
    jsonschema.validate(state, STATE_SCHEMA, cls=jsonschema.Draft202012Validator)

    rep = generate_project_report("wayanad", backend="networkx")
    jsonschema.validate(rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)

    by_name = {p["name"]: p for p in rep["places"]}
    assert by_name["Chooralmala"]["reachable"]["ambulance"] is True
    assert by_name["Mundakai"]["reachable"]["ambulance"] is False

    # Reopen plan ranks the Chooralmala river bridge clearance to reconnect southern bank places!
    assert len(rep["reopen_plan"]) >= 1
    bridge_segs = {
        f["properties"]["segment_id"]
        for f in seg_fc["features"]
        if f["properties"]["osm_way_id"] == CHOORALMALA_BRIDGE_WAY_ID
    }
    reopen_seg_ids = {item["segment_id"] for item in rep["reopen_plan"]}
    assert bridge_segs & reopen_seg_ids

    prio = compute_priorities(places_fc, state, rep)
    jsonschema.validate(prio, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)
