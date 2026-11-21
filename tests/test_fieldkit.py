"""Field kit: the saved map PDF for phones (item 4)."""
from fastapi.testclient import TestClient

from api.main import create_app
from fieldkit import routes as fk


def test_map_pdf_is_a_pdf_and_is_reused_until_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(fk, "CACHE", tmp_path / "maps")
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(tmp_path / "reports.db"))
    built = []
    real_build = fk.build
    monkeypatch.setattr(fk, "build", lambda p: built.append(p) or real_build(p))
    c = TestClient(create_app())
    r = c.get("/field/map.pdf", params={"project": "mock"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    assert "typhon_map_mock_" in r.headers["content-disposition"]
    assert c.get("/field/map.pdf", params={"project": "mock"}).status_code == 200
    assert built == ["mock"]  # the second phone got the same file, no 30 s redraw


def test_unknown_project_is_refused():
    assert TestClient(create_app()).get("/field/map.pdf", params={"project": "nope"}).status_code == 404


def test_a_field_team_may_fetch_its_map(monkeypatch):
    from auth import core
    assert core.allowed("field", "GET", "/field/map.pdf")
    assert not core.allowed(None, "GET", "/field/map.pdf")
