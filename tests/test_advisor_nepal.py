"""Tests for T4 Nepal 26 August 2026 flash flood scenario pack."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from advisor.assess import assess_collection
from advisor.priorities import compute_priorities
from advisor.report import compute_access_report
from scripts.prefetch_nepal import (
    SCENARIO_LABEL,
    _build_nepal_corridor_fixture,
    build_nepal_files,
)

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
SEGMENTS_SCHEMA = json.loads((CONTRACTS / "segments.schema.json").read_text(encoding="utf-8"))
PLACES_SCHEMA = json.loads((CONTRACTS / "places.schema.json").read_text(encoding="utf-8"))
STATE_SCHEMA = json.loads((CONTRACTS / "advisor_state.schema.json").read_text(encoding="utf-8"))
ACCESS_SCHEMA = json.loads((CONTRACTS / "access_report.schema.json").read_text(encoding="utf-8"))
PRIORITIES_SCHEMA = json.loads((CONTRACTS / "priorities.schema.json").read_text(encoding="utf-8"))


def test_build_nepal_files_and_run_advisor(tmp_path: Path):
    out_dir = tmp_path / "nepal"
    counts = build_nepal_files(_build_nepal_corridor_fixture(), out_dir)
    assert counts["segments"] >= 10
    assert counts["places"] >= 5
    assert (out_dir / "scenario_sources.json").exists()

    seg_fc = json.loads((out_dir / "roads" / "segments.geojson").read_text(encoding="utf-8"))
    places_fc = json.loads((out_dir / "places.geojson").read_text(encoding="utf-8"))
    sources_meta = json.loads((out_dir / "scenario_sources.json").read_text(encoding="utf-8"))

    # Validates schemas
    jsonschema.validate(seg_fc, SEGMENTS_SCHEMA, cls=jsonschema.Draft202012Validator)
    jsonschema.validate(places_fc, PLACES_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert sources_meta["label"] == SCENARIO_LABEL
    assert all(f["properties"]["scenario_label"] == SCENARIO_LABEL for f in seg_fc["features"])

    state = assess_collection(seg_fc)
    jsonschema.validate(state, STATE_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert all(s["source"] == "scenario" for s in state["segments"])

    rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project="nepal_fixture",
        backend="networkx",
    )
    jsonschema.validate(rep, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert len(rep["reopen_plan"]) >= 1

    prio = compute_priorities(places_fc, state, rep)
    jsonschema.validate(prio, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert prio["decision_support"] is True
