"""Tests for T7 FastAPI shell, T8 offline /field page, SQLite reports, and scripts/qr.py."""
from __future__ import annotations

import contextlib
import json
import socket
import threading
from pathlib import Path

import jsonschema
import pytest
from fastapi import HTTPException

from advisor.routes import (
    FieldReportIn,
    get_advisor_access,
    get_advisor_priorities,
    get_advisor_state,
    get_field_context,
    get_field_reports,
    post_field_report,
)
from api.main import FIELD_STATIC_DIR, check_internet_reachable, create_app
from scripts.qr import build_field_url, render_qr_ascii

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
STATE_SCHEMA = json.loads((CONTRACTS / "advisor_state.schema.json").read_text(encoding="utf-8"))
ACCESS_SCHEMA = json.loads((CONTRACTS / "access_report.schema.json").read_text(encoding="utf-8"))
PRIORITIES_SCHEMA = json.loads((CONTRACTS / "priorities.schema.json").read_text(encoding="utf-8"))


def _loopback_socket_allowed() -> bool:
    """Detect whether the current environment allows local 127.0.0.1 TCP socket pairs (required by asyncio/TestClient)."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cli.settimeout(0.2)
        try:
            cli.connect(("127.0.0.1", port))
            return True
        finally:
            cli.close()
    except OSError:
        return False
    finally:
        srv.close()


def test_app_shell_mounts_advisor_and_starts_without_optional_lead_routers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(tmp_path / "reports.db"))
    app = create_app(root_dir=ROOT)
    openapi_paths = set(app.openapi()["paths"].keys())
    assert "/health" in openapi_paths
    assert "/field" in openapi_paths
    assert "/advisor/state" in openapi_paths
    assert "/advisor/access" in openapi_paths
    assert "/advisor/priorities" in openapi_paths
    assert "/advisor/reports" in openapi_paths
    assert "/tiles/{project}/{tile_path}" in openapi_paths


def test_health_socket_probe_truthfulness(monkeypatch: pytest.MonkeyPatch):
    # Closed/unreachable probe -> False
    assert check_internet_reachable(host="127.0.0.1", port=1, timeout_s=0.2) is False

    # Simulated reachable socket -> True
    @contextlib.contextmanager
    def _ok_conn(addr, timeout=1.0):
        yield object()

    monkeypatch.setattr("api.main.socket.create_connection", _ok_conn)
    assert check_internet_reachable(host="1.1.1.1", port=53, timeout_s=1.0) is True


def test_field_page_and_static_assets_have_zero_external_urls():
    for fname in ("field.html", "field.css", "field.js"):
        fpath = FIELD_STATIC_DIR / fname
        assert fpath.is_file(), f"Missing {fpath}"
        text = fpath.read_text(encoding="utf-8")
        assert "http://" not in text, f"External http:// URL found in {fname}"
        assert "https://" not in text, f"External https:// URL found in {fname}"

    html = (FIELD_STATIC_DIR / "field.html").read_text(encoding="utf-8")
    assert "freshness-line" in html
    assert "dead_end" in html
    assert "cleared" in html
    assert "new_debris" in html


def test_advisor_handlers_and_sqlite_reports_validate_against_contracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    db_file = tmp_path / "advisor" / "field_reports.db"
    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(db_file))
    monkeypatch.setenv("VORTEX_DEFAULT_PROJECT", "mock")

    st0 = get_advisor_state(project="mock")
    jsonschema.validate(st0, STATE_SCHEMA, cls=jsonschema.Draft202012Validator)

    acc0 = get_advisor_access(project="mock", base=None, backend="networkx")
    jsonschema.validate(acc0, ACCESS_SCHEMA, cls=jsonschema.Draft202012Validator)

    prio0 = get_advisor_priorities(project="mock", base=None, backend="networkx")
    jsonschema.validate(prio0, PRIORITIES_SCHEMA, cls=jsonschema.Draft202012Validator)
    assert prio0["decision_support"] is True

    ctx0 = get_field_context(project="mock")
    assert ctx0["freshness"]["field_report_count"] == 0
    first_seg = ctx0["segments"][0]["segment_id"]

    # Post a dead_end report for wheeled modes
    out1 = post_field_report(
        FieldReportIn(
            project="mock",
            segment_id=first_seg,
            kind="dead_end",
            modes=["fire_truck", "ambulance", "jeep"],
            note="Boulder across carriageway",
            reporter="NDRF-1",
        )
    )
    assert out1["ok"] is True
    assert db_file.is_file()
    assert out1["freshness"]["field_report_count"] == 1
    assert out1["segment_state"]["source"] == "field_report"
    assert out1["segment_state"]["status_by_mode"]["ambulance"] == "blocked"

    st1 = get_advisor_state(project="mock")
    jsonschema.validate(st1, STATE_SCHEMA, cls=jsonschema.Draft202012Validator)
    seg1 = next(s for s in st1["segments"] if s["segment_id"] == first_seg)
    assert seg1["source"] == "field_report"
    assert any("Boulder across carriageway" in r for r in seg1["reasons_by_mode"]["ambulance"])

    # Post a place-based 'cleared' report -> resolves nearest_segment_id automatically
    place_with_seg = next(p for p in ctx0["places"] if p.get("nearest_segment_id"))
    out2 = post_field_report(
        FieldReportIn(
            project="mock",
            place_id=place_with_seg["place_id"],
            kind="cleared",
            modes=["ambulance", "jeep", "foot"],
            note="Single lane opened by JCB",
        )
    )
    assert out2["freshness"]["field_report_count"] == 2
    assert out2["segment_state"]["status_by_mode"]["ambulance"] == "open"

    rep_list = get_field_reports(project="mock")
    assert rep_list["count"] == 2

    # Unknown segment raises 404
    with pytest.raises(HTTPException) as exc_info:
        post_field_report(FieldReportIn(project="mock", segment_id="seg_DOES_NOT_EXIST", kind="other"))
    assert exc_info.value.status_code == 404


def test_qr_generator_url_and_ascii(tmp_path: Path):
    url = build_field_url(ip="192.168.137.1", port=8000, path="/field")
    assert url == "http://192.168.137.1:8000/field"
    art = render_qr_ascii(url)
    assert len(art.splitlines()) >= 15


def test_full_http_asgi_stack_via_testclient(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not _loopback_socket_allowed():
        pytest.skip("Loopback TCP socketpair blocked by sandbox; full ASGI TestClient runs outside sandbox")

    from fastapi.testclient import TestClient

    monkeypatch.setenv("VORTEX_ADVISOR_DB", str(tmp_path / "http_reports.db"))
    monkeypatch.setenv("VORTEX_HEALTH_PROBE_HOST", "127.0.0.1")
    monkeypatch.setenv("VORTEX_HEALTH_PROBE_PORT", "1")

    # Create a sample tile in tmp_path while symlinking/copying contracts for mock
    tile_file = tmp_path / "data" / "projects" / "demo" / "tiles" / "15" / "10" / "20.png"
    tile_file.parent.mkdir(parents=True, exist_ok=True)
    tile_file.write_bytes(b"\x89PNG\r\n\x1a\nmocktile")

    with TestClient(create_app(root_dir=ROOT)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").json()["offline_mode"] is True
        assert client.get("/field").status_code == 200
        assert client.get("/field-static/field.css").status_code == 200
        assert client.get("/field-static/field.js").status_code == 200

        r_state = client.get("/advisor/state?project=mock")
        assert r_state.status_code == 200
        jsonschema.validate(r_state.json(), STATE_SCHEMA, cls=jsonschema.Draft202012Validator)

        r_post = client.post(
            "/advisor/reports",
            json={
                "project": "mock",
                "segment_id": r_state.json()["segments"][0]["segment_id"],
                "kind": "new_debris",
                "modes": ["fire_truck", "ambulance"],
                "note": "Fresh slope slip",
            },
        )
        assert r_post.status_code == 200
        assert r_post.json()["segment_state"]["source"] == "field_report"

        assert client.get("/advisor/access?project=mock&backend=networkx").status_code == 200
        assert client.get("/advisor/priorities?project=mock&backend=networkx").status_code == 200

    with TestClient(create_app(root_dir=tmp_path)) as tile_client:
        t_ok = tile_client.get("/tiles/demo/15/10/20.png")
        assert t_ok.status_code == 200
        assert t_ok.content == b"\x89PNG\r\n\x1a\nmocktile"
        assert tile_client.get("/tiles/demo/15/10/99.png").status_code == 404
