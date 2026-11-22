"""The map's demo scenario endpoints: served only when built, always marked simulated, reset touches only 'demo'."""
import json

from fastapi.testclient import TestClient

from advisor.store import add_field_report, list_field_reports
from api.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("VORTEX_AUTH", "off")
    monkeypatch.setenv("VORTEX_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(tmp_path / "reports.db"))
    return TestClient(create_app())


def test_no_demo_built_means_404(tmp_path, monkeypatch):
    assert _client(tmp_path, monkeypatch).get("/advisor/demo/scenario").status_code == 404


def test_demo_scenario_is_served_and_labelled_simulated(tmp_path, monkeypatch):
    d = tmp_path / "data" / "projects" / "demo"
    (d / "roads").mkdir(parents=True)
    fc = {"type": "FeatureCollection", "mock": True, "features": []}
    (d / "roads" / "segments.geojson").write_text(json.dumps(fc))
    (d / "places.geojson").write_text(json.dumps(fc))
    (d / "demo.json").write_text(json.dumps({"mock": True, "label": "SIMULATED demo", "blockages": [], "people": [], "blur_zones": []}))
    j = _client(tmp_path, monkeypatch).get("/advisor/demo/scenario").json()
    assert j["mock"] is True and "SIMULATED" in j["label"] and j["segments"]["type"] == "FeatureCollection"


def test_reset_clears_only_the_demo_project(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    db = tmp_path / "reports.db"
    add_field_report("demo", "dead_end", segment_id="s1", db_path=db)
    add_field_report("southfork", "dead_end", segment_id="s2", db_path=db)
    r = c.post("/advisor/demo/reset")
    assert r.status_code == 200 and r.json()["cleared"]["field_reports"] == 1
    assert list_field_reports("demo", db_path=db) == [] and len(list_field_reports("southfork", db_path=db)) == 1
