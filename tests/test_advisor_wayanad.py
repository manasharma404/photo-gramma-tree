"""Tests for T6 Wayanad offline scenario, C1 WorldPop population, and C2 offline situation report."""
from __future__ import annotations

import json
from pathlib import Path
import re

import jsonschema
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

from advisor.assess import assess_collection
from advisor.priorities import compute_priorities
from advisor.report import compute_access_report, generate_project_report
from advisor.sitrep import generate_sitrep
from scripts.prefetch_wayanad import (
    CHOORALMALA_BRIDGE_WAY_ID,
    SCENARIO_LABEL,
    build_wayanad_files,
)
from scripts.prefetch_worldpop_wayanad import attach_worldpop_to_places_fc

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


def test_c1_worldpop_attachment_and_c2_offline_sitrep(tmp_path: Path):
    proj_root = tmp_path / "data" / "projects" / "wayanad_c1"
    build_wayanad_files(_synthetic_wayanad_overpass(), proj_root)

    # Create a tiny offline WorldPop-style GeoTIFF with positive grid counts and NoData outside
    tif_path = proj_root / "worldpop_wayanad_2020.tif"
    arr = np.full((12, 12), -99999.0, dtype=np.float32)
    arr[2:10, 2:10] = 140.0
    transform = from_bounds(76.145, 11.475, 76.170, 11.510, 12, 12)
    with rasterio.open(
        tif_path,
        "w",
        driver="GTiff",
        height=12,
        width=12,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=transform,
        nodata=-99999.0,
    ) as dst:
        dst.write(arr, 1)

    places_fc = json.loads((proj_root / "places.geojson").read_text(encoding="utf-8"))
    # Add an out-of-raster settlement to verify missing cells stay null (never 0)
    places_fc["features"].append(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [76.2500, 11.6000]},
            "properties": {
                "mock": False,
                "place_id": "place_OUTSIDE",
                "name": "Uninhabited Edge Point",
                "kind": "settlement",
                "source": "osm",
                "population": None,
                "population_source": "PLACEHOLDER",
                "nearest_segment_id": None,
            },
        }
    )

    summary = attach_worldpop_to_places_fc(places_fc, tif_path, radius_m=750.0)
    assert summary["settlements_filled"] == 3
    assert summary["settlements_null"] == 1
    jsonschema.validate(places_fc, PLACES_SCHEMA, cls=jsonschema.Draft202012Validator)

    by_name = {f["properties"]["name"]: f["properties"] for f in places_fc["features"]}
    assert by_name["Mundakkai"]["population"] > 0
    assert "750 m" in by_name["Mundakkai"]["population_source"]
    # Non-settlement school and out-of-coverage settlement stay null, never 0
    assert by_name["GVHSS Vellarmala"]["population"] is None
    assert by_name["Uninhabited Edge Point"]["population"] is None
    (proj_root / "places.geojson").write_text(json.dumps(places_fc, indent=2), encoding="utf-8")

    sitrep_dir = proj_root / "sitrep"
    written = generate_sitrep(
        project="wayanad_c1",
        out_dir=sitrep_dir,
        data_root=tmp_path,
        backend="networkx",
    )
    md_text = written["markdown"].read_text(encoding="utf-8")
    html_text = written["html"].read_text(encoding="utf-8")

    assert "scenario reconstructed from reports, not drone-measured" in md_text
    assert "decision support" in md_text.lower()
    assert "Sarvam Translate" in md_text
    # Self-contained offline HTML must have zero external http/https CDN or stylesheet links
    assert re.findall(r"https?://", html_text) == []


def test_prefetched_wayanad_project_end_to_end_if_present():
    wayanad_dir = ROOT / "data" / "projects" / "wayanad"
    if not (wayanad_dir / "roads" / "segments.geojson").exists():
        pytest.skip("data/projects/wayanad not prefetched on this machine")

    seg_fc = json.loads((wayanad_dir / "roads" / "segments.geojson").read_text(encoding="utf-8"))
    places_fc = json.loads((wayanad_dir / "places.geojson").read_text(encoding="utf-8"))

    jsonschema.validate(seg_fc, SEGMENTS_SCHEMA, cls=jsonschema.Draft202012Validator)
    jsonschema.validate(places_fc, PLACES_SCHEMA, cls=jsonschema.Draft202012Validator)

    # C1 verification on real prefetched Wayanad settlements
    settlement_pops = [
        f["properties"]["population"]
        for f in places_fc["features"]
        if f["properties"]["kind"] == "settlement"
    ]
    assert len(settlement_pops) >= 5
    assert all(isinstance(p, int) and p > 0 for p in settlement_pops)

    state = assess_collection(seg_fc)
    jsonschema.validate(state, STATE_SCHEMA, cls=jsonschema.Draft202012Validator)

    rep = generate_project_report("wayanad", backend="networkx")
    jsonschema.validate(rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)

    by_name = {p["name"]: p for p in rep["places"]}
    assert by_name["Chooralmala"]["reachable"]["ambulance"] is True
    assert by_name["Mundakai"]["reachable"]["ambulance"] is False

    assert len(rep["reopen_plan"]) >= 1
    assert rep["reopen_plan"][0]["reconnects_people"] is not None
    assert rep["reopen_plan"][0]["reconnects_people"] > 0
    bridge_segs = {
        f["properties"]["segment_id"]
        for f in seg_fc["features"]
        if f["properties"]["osm_way_id"] == CHOORALMALA_BRIDGE_WAY_ID
    }
    reopen_seg_ids = {item["segment_id"] for item in rep["reopen_plan"]}
    assert bridge_segs & reopen_seg_ids

    prio = compute_priorities(places_fc, state, rep)
    jsonschema.validate(prio, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)
