"""Tap-on-the-map field view (/field/map) and its compact data endpoint /advisor/fieldmap."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from advisor.store import init_db
from api.main import FIELD_STATIC_DIR, create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_file = tmp_path / "fieldmap.db"
    init_db(db_file)
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(db_file))
    monkeypatch.setenv("VORTEX_AUTH", "off")
    monkeypatch.delenv("VORTEX_FIELD_PIN", raising=False)
    return TestClient(create_app(root_dir=ROOT))


def test_field_map_page_is_served_and_offline():
    for fname in ("field_map.html", "field_map.css", "field_map.js"):
        text = (FIELD_STATIC_DIR / fname).read_text(encoding="utf-8")
        assert "http://" not in text and "https://" not in text, f"external URL in {fname}"


def test_field_map_route(client: TestClient):
    r = client.get("/field/map")
    assert r.status_code == 200
    assert "fm-canvas" in r.text


def test_fieldmap_payload_and_tap_report_recolours_road(client: TestClient):
    r = client.get("/advisor/fieldmap?project=wayanad")
    assert r.status_code == 200
    data = r.json()
    assert data["project"] == "wayanad"
    assert len(data["roads"]) > 1000
    road = next(x for x in data["roads"] if x["st"].get("fire_truck") != "blocked" and x["c"])
    assert isinstance(road["c"][0][0], list) and len(road["c"][0][0]) == 2
    assert all(p["c"] and len(p["c"]) == 2 for p in data["places"])

    # Severity "Narrowed": only the fire truck is blocked; other vehicles keep their status
    before = road["st"]
    out = client.post("/advisor/reports", json={
        "project": "wayanad", "segment_id": road["id"], "kind": "new_debris",
        "modes": ["fire_truck"], "note": "[Fallen tree · Narrowed]",
    })
    assert out.status_code == 200
    after = next(x for x in client.get("/advisor/fieldmap?project=wayanad").json()["roads"] if x["id"] == road["id"])
    assert after["st"]["fire_truck"] == "blocked"
    assert after["st"]["foot"] == before["foot"]
    assert after["src"] == "field_report"


def test_evidence_rejects_paths_outside_projects(client: TestClient):
    assert client.get("/advisor/evidence", params={"path": "pyproject.toml"}).status_code == 404
    assert client.get("/advisor/evidence", params={"path": "data/projects/../../pyproject.toml"}).status_code == 404
