"""The lead's routers mounted through the teammate's api/main.py, end to end over HTTP."""
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from pipeline import activate
from tests.test_measure import X0, Y0, grid, ll, write

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    x, _ = grid(400)
    dsm = np.full(x.shape, 1003.0)
    dsm[(x >= 14) & (x < 26)] = 1000.0  # 12 m wide channel
    write(tmp_path / "dsm.tif", dsm)
    run_dir = tmp_path / "runs"
    active = {"project": "synthetic", "run_id": "synthetic_quick", "full_run_id": "synthetic_full",
              "orthophoto": None, "dsm": str(tmp_path / "dsm.tif"), "dtm": None, "accuracy": None}
    # paths in active.json are relative to ROOT; absolute tmp paths still work with ROOT / abs
    (tmp_path / "active.json").write_text(json.dumps(active), encoding="utf-8")
    monkeypatch.setattr(activate, "ACTIVE", tmp_path / "active.json")
    return TestClient(create_app(root_dir=ROOT))


def test_routers_are_mounted(client):
    # this FastAPI wraps included routers lazily, so ask the published API description, not app.routes
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {"/measure/span", "/measure/volume", "/measure/landing-zones", "/measure/working-space",
            "/accuracy/spec", "/accuracy/report"} <= paths


def test_span_over_http(client):
    r = client.post("/measure/span", json={"geometry": {"type": "LineString", "coordinates": [ll(5, 20), ll(35, 20)]}})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["span_m"] == pytest.approx(12.0, abs=0.3)


def test_wrong_geometry_is_422(client):
    r = client.post("/measure/span", json={"geometry": {"type": "Point", "coordinates": ll(5, 5)}})
    assert r.status_code == 422


def test_active_and_layers(client):
    a = client.get("/accuracy/active").json()
    assert a["project"] == "synthetic" and a["has_roads"] is False and a["tiles"] is None
    assert client.get("/accuracy/layers/segments").status_code == 404  # not produced yet
    assert client.get("/accuracy/layers/nonsense").status_code == 404


def test_accuracy_missing_is_404_and_spec_has_nulls(client):
    assert client.get("/accuracy/report").status_code == 404
    spec = client.get("/accuracy/spec").json()
    assert spec["accuracy"] is None and spec["timing"]["total_minutes"] is None
