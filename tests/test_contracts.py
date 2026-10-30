"""Every contract example must validate against its schema and be marked mock."""
import copy
import json
from pathlib import Path

import jsonschema
import pytest

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"
EXAMPLES = CONTRACTS / "examples"
SCHEMAS = sorted(CONTRACTS.glob("*.schema.json"))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def example_for(schema_path):
    name = schema_path.name.removesuffix(".schema.json")
    matches = list(EXAMPLES.glob(f"{name}.example.*"))
    assert len(matches) == 1, f"expected one example for {name}, found {matches}"
    return matches[0]


def test_found_schemas():
    assert len(SCHEMAS) >= 10


@pytest.mark.parametrize("schema_path", SCHEMAS, ids=lambda p: p.name)
def test_schema_is_valid(schema_path):
    jsonschema.Draft202012Validator.check_schema(load(schema_path))


@pytest.mark.parametrize("schema_path", SCHEMAS, ids=lambda p: p.name)
def test_example_validates_and_is_mock(schema_path):
    example = load(example_for(schema_path))
    jsonschema.validate(example, load(schema_path), cls=jsonschema.Draft202012Validator)
    assert example.get("mock") is True


def test_every_example_has_a_schema():
    schema_names = {p.name.removesuffix(".schema.json") for p in SCHEMAS}
    for ex in EXAMPLES.iterdir():
        assert ex.name.split(".example.")[0] in schema_names, f"orphan example {ex.name}"


def test_accuracy_rejects_gcp_use():
    # The brief forbids GCPs in the main pipeline; the contract must refuse it.
    bad = copy.deepcopy(load(EXAMPLES / "accuracy.example.json"))
    bad["used_gcps"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load(CONTRACTS / "accuracy.schema.json"))


def test_segments_rejects_unknown_status():
    bad = copy.deepcopy(load(EXAMPLES / "segments.example.geojson"))
    bad["features"][0]["properties"]["status_by_mode"]["ambulance"] = "maybe"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load(CONTRACTS / "segments.schema.json"))


def test_advisor_state_rejects_old_mode_names():
    # Modes are fire_truck / ambulance / jeep / foot since 31 Oct 02:00 (PLAN.md)
    bad = copy.deepcopy(load(EXAMPLES / "advisor_state.example.json"))
    bad["segments"][0]["status_by_mode"]["truck"] = "open"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load(CONTRACTS / "advisor_state.schema.json"))


def test_priorities_must_be_decision_support():
    bad = copy.deepcopy(load(EXAMPLES / "priorities.example.json"))
    bad["decision_support"] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, load(CONTRACTS / "priorities.schema.json"))
