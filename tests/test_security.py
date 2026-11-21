"""Proof for the attacks the story page says we stop (the rest are in tests/test_auth.py):
SQL injection, path tricks on map tiles, and the sign-in cookie's flags (HttpOnly, SameSite=Strict)."""
from fastapi.testclient import TestClient

from advisor.store import add_field_report, list_field_reports
from api.main import create_app


def test_sql_injection_is_stored_as_plain_text(tmp_path):
    db = tmp_path / "reports.db"
    evil = "x'); DROP TABLE field_reports; --"
    add_field_report("p", "dead_end", segment_id="s1", note=evil, reporter=evil, db_path=db)
    add_field_report("p", "dead_end", segment_id="s2", db_path=db)  # the table is still there
    rows = list_field_reports("p", db_path=db)
    assert len(rows) == 2 and rows[0]["note"] == evil


def test_tile_paths_cannot_leave_the_tiles_folder(monkeypatch):
    monkeypatch.setenv("VORTEX_AUTH", "off")
    c = TestClient(create_app())
    for p in ("/tiles/southfork_f01_4/..%2F..%2F..%2F..%2Fauth%2Fcore.py",
              "/tiles/southfork_f01_4/ortho/..%2F..%2F..%2F..%2F..%2F.env"):
        assert c.get(p).status_code == 404, p


def test_the_sign_in_cookie_cannot_be_read_by_scripts_or_sent_by_other_sites(monkeypatch):
    monkeypatch.setenv("VORTEX_AUTH", "on")
    monkeypatch.setenv("VORTEX_EVALUATOR_CODE", "test-evaluator-code")
    monkeypatch.setenv("VORTEX_SESSION_SECRET", "test-secret-not-real")
    from auth import core
    core._fails.clear()
    r = TestClient(create_app()).post("/auth/login", json={"code": "test-evaluator-code"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
