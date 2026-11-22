"""Test F3 Part 1 ML road scoring contract compliance and evidence crops."""
import json
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parent.parent


def test_ml_scores_schema_compliance():
    schema_path = ROOT / "contracts" / "ml_scores.schema.json"
    scores_path = ROOT / "data" / "projects" / "southfork_f01_4" / "ml_scores.json"

    assert schema_path.exists(), f"Schema missing: {schema_path}"
    assert scores_path.exists(), f"ml_scores.json missing: {scores_path}"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = json.loads(scores_path.read_text(encoding="utf-8"))

    # Must validate against frozen contract
    jsonschema.validate(instance=payload, schema=schema)

    assert payload["mock"] is False
    scores = payload["scores"]
    assert len(scores) == 498, f"Expected 498 segments, got {len(scores)}"

    # Check that scored segments inside footprint have non-null probabilities
    scored_inside = [s for s in scores if s["p_blocked"] is not None]
    assert len(scored_inside) == 16, f"Expected 16 covered segments, got {len(scored_inside)}"
    for s in scored_inside:
        assert s["p_blocked"] is not None
        assert s["p_partial"] is not None
        assert s["p_clear"] is not None
        assert round(s["p_blocked"] + s["p_partial"] + s["p_clear"], 2) == 1.0

    # Check evidence crops
    ev_dir = ROOT / "data" / "projects" / "southfork_f01_4" / "evidence"
    assert ev_dir.exists()
    ev_crops = list(ev_dir.glob("*.jpg"))
    assert len(ev_crops) == 16
