"""Tests for Idea 7: Human verification loop ('needs checking', confirm/reject, segment history)."""
import json
from pathlib import Path

import jsonschema
import pytest

from advisor import MODES
from advisor.assess import assess_collection, assess_segment
from advisor.store import (
    add_field_report,
    get_segment_history,
    init_db,
    record_suspicion,
    record_verification,
)

ROOT = Path(__file__).resolve().parent.parent
ADVISOR_STATE_SCHEMA = json.loads(
    (ROOT / "contracts" / "advisor_state.schema.json").read_text(encoding="utf-8")
)


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "test_field_reports.db"
    init_db(db_file)
    return db_file


def test_suspicion_confirm_reject_lifecycle(tmp_db: Path):
    """Test full Idea 7 loop: suspicion -> confirm -> status=blocked; suspicion -> reject -> back to unknown."""
    project = "test_idea7"
    segment_id = "seg_TEST_001"

    # Base unmeasured segment (geometry status=unknown)
    seg_props = {
        "segment_id": segment_id,
        "measured": False,
        "coverage_fraction": None,
    }

    # 1. Model suspicion raised (p_blocked = 0.85 >= threshold)
    record_suspicion(
        project=project,
        segment_id=segment_id,
        p_blocked=0.85,
        evidence_crop="data/projects/test/evidence/seg_TEST_001.jpg",
        model="typhon_debris_resnet18",
        version="1.0.0",
        db_path=tmp_db,
    )

    ml_score = {
        "segment_id": segment_id,
        "p_blocked": 0.85,
        "p_partial": 0.10,
        "p_clear": 0.05,
        "model": "typhon_debris_resnet18",
        "version": "1.0.0",
        "evidence_crop": "data/projects/test/evidence/seg_TEST_001.jpg",
    }

    # Under suspicion alone, status is NEVER 'blocked' and NEVER 'open'
    state_suspect = assess_segment(seg_props, ml_score=ml_score, field_reports=[])
    assert state_suspect["needs_verification"] is True
    assert all(st == "unknown" for st in state_suspect["status_by_mode"].values())
    for mode in MODES:
        reasons = state_suspect["reasons_by_mode"][mode]
        assert any("rule=needs_checking" in r for r in reasons)

    # Check history contains the model suspicion
    hist1 = get_segment_history(project, segment_id, db_path=tmp_db)
    assert len(hist1) == 1
    assert hist1[0]["event"] == "model_suspicion"
    assert "typhon_debris_resnet18" in hist1[0]["model_said"]
    assert hist1[0]["p_blocked"] == 0.85
    assert hist1[0]["evidence_crop"] == "data/projects/test/evidence/seg_TEST_001.jpg"

    # 2. Responder confirms the suspicion via field report
    rep_confirm = add_field_report(
        project=project,
        kind="confirm",
        segment_id=segment_id,
        reporter="NDRF Unit 4",
        note="Confirmed heavy rockfall blocking carriageway",
        db_path=tmp_db,
    )
    assert rep_confirm["kind"] == "confirm"

    state_confirmed = assess_segment(seg_props, ml_score=ml_score, field_reports=[rep_confirm])
    assert state_confirmed["needs_verification"] is False
    assert state_confirmed["source"] == "field_report"
    assert all(st == "blocked" for st in state_confirmed["status_by_mode"].values())
    for mode in MODES:
        reasons = state_confirmed["reasons_by_mode"][mode]
        assert any("rule=field_report: confirmed" in r for r in reasons)

    # Check history contains both model suspicion and responder confirmation
    hist2 = get_segment_history(project, segment_id, db_path=tmp_db)
    assert len(hist2) == 2
    assert hist2[1]["event"] == "field_confirm"
    assert "NDRF Unit 4" in hist2[1]["person_said"]
    assert "Confirmed heavy rockfall" in hist2[1]["person_said"]

    # 3. Alternative scenario: Responder rejects suspicion (false alarm) -> back to unknown
    db_reject = tmp_db.parent / "test_reject.db"
    init_db(db_reject)
    record_suspicion(
        project=project,
        segment_id=segment_id,
        p_blocked=0.85,
        evidence_crop="data/projects/test/evidence/seg_TEST_001.jpg",
        db_path=db_reject,
    )
    rep_reject = add_field_report(
        project=project,
        kind="reject",
        segment_id=segment_id,
        reporter="Field Scout",
        note="Model false alarm: dark asphalt shadow, road is clear",
        db_path=db_reject,
    )
    assert rep_reject["kind"] == "reject"

    state_rejected = assess_segment(seg_props, ml_score=ml_score, field_reports=[rep_reject])
    assert state_rejected["needs_verification"] is False
    assert state_rejected["source"] == "field_report"
    # Status resets back to unknown
    assert all(st == "unknown" for st in state_rejected["status_by_mode"].values())
    for mode in MODES:
        reasons = state_rejected["reasons_by_mode"][mode]
        assert any("rule=field_report: rejected model suspicion" in r for r in reasons)

    hist_rej = get_segment_history(project, segment_id, db_path=db_reject)
    assert len(hist_rej) == 2
    assert hist_rej[1]["event"] == "field_reject"
    assert "Field Scout" in hist_rej[1]["person_said"]


def test_schema_compliance_with_human_verification(tmp_db: Path):
    """Verify that assessed state with needs_verification and confirm/reject strictly validates advisor_state schema."""
    project = "test_schema"
    seg_fc = {
        "type": "FeatureCollection",
        "mock": True,
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0.0, 0.0], [0.001, 0.0]]},
                "properties": {
                    "segment_id": "seg_001",
                    "measured": False,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": [[0.001, 0.0], [0.002, 0.0]]},
                "properties": {
                    "segment_id": "seg_002",
                    "measured": False,
                },
            },
        ],
    }

    ml_scores = {
        "scores": [
            {
                "segment_id": "seg_001",
                "p_blocked": 0.80,
                "p_partial": 0.10,
                "p_clear": 0.10,
                "model": "typhon_debris_resnet18",
                "version": "1.0.0",
            }
        ]
    }

    # Add confirm on seg_001 and reject on seg_002
    r1 = add_field_report(project, kind="confirm", segment_id="seg_001", reporter="Ops", db_path=tmp_db)
    r2 = add_field_report(project, kind="reject", segment_id="seg_002", reporter="Ops", db_path=tmp_db)

    state = assess_collection(
        seg_fc,
        ml_scores=ml_scores,
        field_reports=[r1, r2],
    )

    jsonschema.validate(state, ADVISOR_STATE_SCHEMA, cls=jsonschema.Draft202012Validator)
    s1 = next(s for s in state["segments"] if s["segment_id"] == "seg_001")
    s2 = next(s for s in state["segments"] if s["segment_id"] == "seg_002")

    assert s1["status_by_mode"]["ambulance"] == "blocked"
    assert s2["status_by_mode"]["ambulance"] == "unknown"
