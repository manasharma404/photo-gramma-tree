"""Access by role over HTTP: who may see and do what, sessions, lockout, redirects."""
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from auth import core

OP, EV = "test-operator-code", "test-evaluator-code"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VORTEX_AUTH", "on")
    monkeypatch.setenv("VORTEX_OPERATOR_CODE", OP)
    monkeypatch.setenv("VORTEX_EVALUATOR_CODE", EV)
    monkeypatch.setenv("VORTEX_TEAM_PINS", "Team A:111111,Team B:222222")
    monkeypatch.setenv("VORTEX_SESSION_SECRET", "test-secret-not-real")
    core._fails.clear()
    return TestClient(create_app())


def sign_in(c, code):
    r = c.post("/auth/login", json={"code": code})
    assert r.status_code == 200, r.text
    return r.json()


def test_nothing_private_without_signing_in(client):
    for path in ("/advisor/state", "/live/sets", "/accuracy/active", "/measure/helicopters", "/tiles/x/y.png"):
        assert client.get(path).status_code == 401, path
    assert client.post("/live/start", json={"set": "x"}).status_code == 401
    assert client.post("/advisor/reports", json={"kind": "dead_end", "segment_id": "s"}).status_code == 401


def test_a_browser_is_sent_to_the_sign_in_page(client):
    r = client.get("/app/", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login/?next=/app/"


def test_public_things_stay_public(client):
    assert client.get("/health").status_code == 200
    assert client.get("/auth/me").json() == {"auth": True, "role": None, "team": None}
    assert client.get("/accuracy/spec").status_code in (200, 404)  # public numbers; 404 only if nothing processed


def test_operator_and_evaluator(client):
    assert sign_in(client, OP)["role"] == "operator"
    assert client.get("/live/sets").status_code == 200
    client.post("/auth/logout")
    assert client.get("/live/sets").status_code == 401
    me = sign_in(client, EV)
    assert me["role"] == "evaluator" and me["next"] == "/app/"
    assert client.get("/advisor/state").status_code == 200
    assert client.post("/live/start", json={"set": "no_such_set"}).status_code == 404  # allowed through, set unknown


def test_field_team_sees_only_its_page_and_reports_carry_the_team(client):
    me = sign_in(client, "222222")
    assert me == {"role": "field", "team": "Team B", "next": "/field"}
    assert client.get("/advisor/context").status_code == 200
    assert client.get("/live/sets").status_code == 403
    assert client.post("/measure/span", json={"geometry": {}}).status_code == 403
    assert client.get("/accuracy/active").status_code == 403
    r = client.get("/app/", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/field"  # sent to its own page, not an error


def test_a_field_report_records_the_team_that_sent_it(client, tmp_path, monkeypatch):
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(tmp_path / "reports.db"))  # never the demo database
    sign_in(client, "111111")
    seg = client.get("/advisor/state", params={"project": "mock"}).json()["segments"][0]["segment_id"]
    r = client.post("/advisor/reports", json={"project": "mock", "kind": "dead_end", "segment_id": seg,
                                              "reporter": "Ravi"})  # no PIN needed: the sign-in already proved it
    assert r.status_code == 200, r.text
    assert r.json()["report"]["reporter"] == "Team A (Ravi)"


def test_wrong_codes_lock_the_device_out(client):
    for _ in range(core.MAX_FAILS):
        assert client.post("/auth/login", json={"code": "wrong"}).status_code == 403
    assert client.post("/auth/login", json={"code": OP}).status_code == 429  # even the right code waits


def test_tunnel_guesses_do_not_lock_out_the_laptop(client):
    # the test client counts as one device; tunnel visitors are counted by the address Cloudflare passes on
    from auth.routes import _device

    class R:
        def __init__(self, host, cf=None):
            self.client = type("C", (), {"host": host})()
            self.headers = {"cf-connecting-ip": cf} if cf else {}
    assert _device(R("127.0.0.1", "203.0.113.9")) == "tunnel:203.0.113.9"
    assert _device(R("127.0.0.1")) == "127.0.0.1"
    assert _device(R("192.168.43.20", "203.0.113.9")) == "192.168.43.20"  # a phone cannot fake it


def test_a_tampered_or_expired_cookie_is_refused(client, monkeypatch):
    sign_in(client, EV)
    good = client.cookies.get(core.COOKIE)
    body, sig = good.rsplit(".", 1)
    forged = core.make_session("operator", None).rsplit(".", 1)[0] + "." + sig  # operator body, evaluator signature
    client.cookies.set(core.COOKIE, forged)
    assert client.get("/live/sets").status_code == 401
    monkeypatch.setattr(core, "SESSION_S", -1)
    client.cookies.set(core.COOKIE, core.make_session("operator", None))
    assert client.get("/live/sets").status_code == 401


def test_after_sign_in_only_local_paths_are_followed(client):
    assert client.post("/auth/login", json={"code": EV, "next": "https://evil.example/"}).json()["next"] == "/app/"
    assert client.post("/auth/login", json={"code": EV, "next": "//evil.example/"}).json()["next"] == "/app/"
    assert client.post("/auth/login", json={"code": "111111", "next": "/app/"}).json()["next"] == "/field"


def test_with_sign_in_off_everything_works_as_before(monkeypatch):
    monkeypatch.setenv("VORTEX_AUTH", "off")
    assert TestClient(create_app()).get("/advisor/state").status_code == 200
