"""FastAPI router for /advisor endpoints (T7, T8, T11)."""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from advisor.assess import assess_collection, load_vehicle_config
from advisor.neo4j_client import project_paths
from advisor.priorities import compute_priorities
from advisor.report import compute_access_report
from advisor.store import (
    add_field_report,
    get_freshness,
    get_segment_history,
    list_field_reports,
)

ROOT = Path(__file__).resolve().parent.parent
router = APIRouter(tags=["advisor"])

ModeLiteral = Literal["fire_truck", "ambulance", "jeep", "foot"]
KindLiteral = Literal["dead_end", "cleared", "new_debris", "other", "confirm", "reject", "confirmed", "rejected"]


class FieldReportIn(BaseModel):
    project: str | None = Field(default=None, description="Project slug (e.g. southfork, wayanad, mock)")
    segment_id: str | None = Field(default=None, description="Road segment ID")
    place_id: str | None = Field(default=None, description="Nearby settlement/facility place_id")
    kind: KindLiteral
    modes: list[ModeLiteral] | None = Field(
        default=None,
        description="Affected vehicle modes; defaults to all four modes when omitted",
    )
    note: str | None = Field(default=None, max_length=500)
    reporter: str | None = Field(default=None, max_length=120)


LOCAL_HOSTS = {"127.0.0.1", "::1"}
PIN_MAX_FAILS, PIN_LOCKOUT_S = 5, 600
_pin_fails: dict[str, list[float]] = {}


def check_field_pin(client_host: str | None, pin: str | None) -> None:
    """Phones on the hotspot must send the PIN shown in the laptop's console; the laptop itself is trusted.

    VORTEX_FIELD_PIN unset or "off" disables the check. After 5 wrong PINs a device waits 10 minutes.
    """
    expected = os.environ.get("VORTEX_FIELD_PIN", "").strip()
    if not expected or expected.lower() == "off" or client_host in LOCAL_HOSTS:
        return
    now = time.monotonic()
    fails = [t for t in _pin_fails.get(client_host or "", []) if now - t < PIN_LOCKOUT_S]
    if len(fails) >= PIN_MAX_FAILS:
        raise HTTPException(status_code=429, detail="Too many wrong PINs from this device. Wait 10 minutes.")
    if pin and secrets.compare_digest(pin.strip(), expected):
        _pin_fails.pop(client_host or "", None)
        return
    _pin_fails[client_host or ""] = fails + [now]
    raise HTTPException(status_code=403, detail="Wrong or missing field PIN. Ask the laptop operator for it.")


def _data_root() -> Path:
    env_root = os.environ.get("VORTEX_DATA_ROOT", "").strip()
    return Path(env_root) if env_root else ROOT


def available_projects(data_root: Path | None = None) -> list[str]:
    root = data_root or _data_root()
    projs: list[str] = []
    projects_dir = root / "data" / "projects"
    if projects_dir.exists():
        for child in sorted(projects_dir.iterdir()):
            if child.is_dir() and (
                (child / "roads" / "segments.geojson").exists()
                or (child / "segments.geojson").exists()
            ):
                projs.append(child.name)
    projs.append("mock")
    return projs


def resolve_project(project: str | None = None, data_root: Path | None = None) -> str:
    if project:
        return project
    env_proj = os.environ.get("VORTEX_DEFAULT_PROJECT", "").strip()
    if env_proj:
        return env_proj
    projs = available_projects(data_root=data_root)
    # the map the dashboard shows (pipeline.activate), so /field reports land on the same project by default
    active_file = Path(os.environ.get("VORTEX_ACTIVE", "") or (data_root or _data_root()) / "data" / "active.json")
    try:
        active_proj = json.loads(active_file.read_text(encoding="utf-8")).get("project")
    except (OSError, ValueError, AttributeError):
        active_proj = None
    if active_proj in projs:
        return active_proj
    for preferred in ("southfork", "wayanad"):
        if preferred in projs:
            return preferred
    return "mock"


def _load_project_inputs(project: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    root = _data_root()
    paths = project_paths(project, data_root=root)
    if not paths["segments"].exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project}' segments.geojson not found at {paths['segments']}",
        )
    seg_fc = json.loads(paths["segments"].read_text(encoding="utf-8"))
    if paths["places"].exists():
        places_fc = json.loads(paths["places"].read_text(encoding="utf-8"))
    else:
        places_fc = {"type": "FeatureCollection", "mock": bool(seg_fc.get("mock", False)), "features": []}
    ml_data = (
        json.loads(paths["ml_scores"].read_text(encoding="utf-8"))
        if paths["ml_scores"].exists()
        else None
    )
    return seg_fc, places_fc, ml_data


def _compute_state_for_project(project: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    seg_fc, places_fc, ml_data = _load_project_inputs(project)
    reports = list_field_reports(project)
    cfg = load_vehicle_config()
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state = assess_collection(
        seg_fc,
        config=cfg,
        ml_scores=ml_data,
        field_reports=reports,
        updated_at=now_iso,
    )
    return seg_fc, places_fc, reports, state


@router.get("/state")
def get_advisor_state(project: str | None = Query(default=None)) -> dict[str, Any]:
    """Return authoritative road passability per vehicle with rule reasons (validates advisor_state.schema.json)."""
    proj = resolve_project(project)
    _, _, _, state = _compute_state_for_project(proj)
    return state


@router.get("/access")
def get_advisor_access(
    project: str | None = Query(default=None),
    base: str | None = Query(default=None),
    backend: Literal["auto", "neo4j", "networkx"] = Query(default="auto"),
) -> dict[str, Any]:
    """Return multi-vehicle reachability and T5 reopen plan (validates access_report.schema.json)."""
    proj = resolve_project(project)
    seg_fc, places_fc, _, state = _compute_state_for_project(proj)
    t0 = time.perf_counter()
    rep = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project=proj,
        base_place_id=base,
        backend=backend,
    )
    # extra, optional fields (the contract allows them): how long the graph answer took, and on what
    rep["timing_s"] = round(time.perf_counter() - t0, 2)
    rep["graph_size"] = {"roads": len(seg_fc.get("features", [])), "places": len(places_fc.get("features", []))}
    return rep


# ---- the map's DEMO scenario (scripts/build_demo_scenario.py): real OSM roads, SIMULATED damage and people ----
def _demo_dir() -> Path:
    return _data_root() / "data" / "projects" / "demo"


@router.get("/demo/scenario")
def get_demo_scenario() -> dict[str, Any]:
    """Everything the map needs to draw the demo: its roads, places, blockages, blurred patch and people."""
    d = _demo_dir()
    if not (d / "demo.json").exists():
        raise HTTPException(status_code=404, detail="no demo scenario on this laptop (scripts/build_demo_scenario.py)")
    demo = json.loads((d / "demo.json").read_text(encoding="utf-8"))
    demo["segments"] = json.loads((d / "roads" / "segments.geojson").read_text(encoding="utf-8"))
    demo["places"] = json.loads((d / "places.geojson").read_text(encoding="utf-8"))
    return demo


@router.post("/demo/reset")
def reset_demo_scenario() -> dict[str, Any]:
    """Clear the demo's field reports and history (only project 'demo'), so the next run starts clean."""
    import sqlite3

    from advisor.store import init_db, resolve_db_path

    db = init_db(resolve_db_path())
    with sqlite3.connect(db) as conn:
        n = {t: conn.execute(f"DELETE FROM {t} WHERE project = 'demo'").rowcount for t in ("field_reports", "segment_history")}
    return {"project": "demo", "cleared": n}


@router.get("/priorities")
def get_advisor_priorities(
    project: str | None = Query(default=None),
    base: str | None = Query(default=None),
    backend: Literal["auto", "neo4j", "networkx"] = Query(default="auto"),
) -> dict[str, Any]:
    """Return weighted decision-support rescue/clearance priorities (validates priorities.schema.json)."""
    proj = resolve_project(project)
    seg_fc, places_fc, _, state = _compute_state_for_project(proj)
    acc = compute_access_report(
        segments_geojson=seg_fc,
        places_geojson=places_fc,
        advisor_state=state,
        project=proj,
        base_place_id=base,
        backend=backend,
    )
    return compute_priorities(places_fc, state, acc, generated_at=state.get("updated_at"))


@router.get("/history")
def get_segment_history_route(
    segment_id: str = Query(..., description="Road segment ID to get history for"),
    project: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return chronological verification history for a segment (Idea 7: model said, person said, when)."""
    proj = resolve_project(project)
    history = get_segment_history(proj, segment_id)
    return {
        "project": proj,
        "segment_id": segment_id,
        "count": len(history),
        "history": history,
    }


@router.get("/reports")
def get_field_reports(project: str | None = Query(default=None)) -> dict[str, Any]:
    """List responder field reports and freshness metadata for a project."""
    proj = resolve_project(project)
    _, _, reports, state = _compute_state_for_project(proj)
    freshness = get_freshness(
        project=proj,
        analysis_time=state.get("updated_at"),
        data_root=_data_root(),
    )
    return {
        "project": proj,
        "count": len(reports),
        "freshness": freshness,
        "reports": reports,
    }


@router.post("/reports")
def post_field_report(
    payload: FieldReportIn,
    request: Request = None,  # type: ignore[assignment]  # None when called directly (tests, scripts)
    x_field_pin: str | None = Header(default=None),
) -> dict[str, Any]:
    """Record a ground responder field report into SQLite and update /advisor/state immediately."""
    # Signed in (auth/core.py, finale item 6): the sign-in already proved who this is, and a field team's
    # reports carry its team name. Not signed in (only when VORTEX_AUTH=off): the original per-report PIN.
    session = getattr(getattr(request, "state", None), "auth", None) if request is not None else None
    if session:
        reporter = session.get("team") or {"operator": "Laptop operator", "evaluator": "Evaluator"}.get(session["role"])
        if payload.reporter and session.get("team"):
            reporter = f"{session['team']} ({payload.reporter})"
        payload.reporter = reporter
    else:
        client = request.client.host if request is not None and request.client else None
        check_field_pin(client, x_field_pin if isinstance(x_field_pin, str) else None)
    proj = resolve_project(payload.project)
    seg_fc, places_fc, _ = _load_project_inputs(proj)

    seg_ids = {str(f["properties"]["segment_id"]) for f in seg_fc.get("features", [])}
    place_map = {
        str(f["properties"]["place_id"]): f["properties"]
        for f in places_fc.get("features", [])
    }

    target_seg = payload.segment_id
    target_place = payload.place_id

    if not target_seg and not target_place:
        raise HTTPException(status_code=422, detail="Either segment_id or place_id is required.")

    if target_place and target_place not in place_map:
        raise HTTPException(status_code=404, detail=f"Unknown place_id '{target_place}' in project '{proj}'.")

    if not target_seg and target_place:
        nsid = place_map[target_place].get("nearest_segment_id")
        if nsid:
            target_seg = str(nsid)

    if target_seg and target_seg not in seg_ids:
        raise HTTPException(status_code=404, detail=f"Unknown segment_id '{target_seg}' in project '{proj}'.")

    saved = add_field_report(
        project=proj,
        kind=payload.kind,
        segment_id=target_seg,
        place_id=target_place,
        modes=list(payload.modes) if payload.modes else None,
        note=payload.note,
        reporter=payload.reporter,
    )

    _, _, _, updated_state = _compute_state_for_project(proj)
    freshness = get_freshness(
        project=proj,
        analysis_time=updated_state.get("updated_at"),
        data_root=_data_root(),
    )
    seg_state = next(
        (s for s in updated_state["segments"] if s["segment_id"] == target_seg),
        None,
    )
    return {
        "ok": True,
        "report": saved,
        "segment_state": seg_state,
        "freshness": freshness,
    }


@router.get("/context")
def get_field_context(project: str | None = Query(default=None)) -> dict[str, Any]:
    """Bundle local places, road segments, recent reports, and freshness line for offline /field UI."""
    root = _data_root()
    projs = available_projects(data_root=root)
    proj = resolve_project(project, data_root=root)
    seg_fc, places_fc, reports, state = _compute_state_for_project(proj)
    state_by_id = {s["segment_id"]: s for s in state["segments"]}

    places_list: list[dict[str, Any]] = []
    for f in places_fc.get("features", []):
        pr = f["properties"]
        places_list.append(
            {
                "place_id": pr["place_id"],
                "name": pr.get("name") or pr["place_id"],
                "kind": pr.get("kind", "settlement"),
                "nearest_segment_id": pr.get("nearest_segment_id"),
            }
        )

    linked_segs = {p["nearest_segment_id"] for p in places_list if p.get("nearest_segment_id")}
    raw_segs: list[dict[str, Any]] = []
    for f in seg_fc.get("features", []):
        pr = f["properties"]
        sid = str(pr["segment_id"])
        st = state_by_id.get(sid, {})
        st_modes = st.get("status_by_mode", {})
        is_key = (
            sid in linked_segs
            or st.get("source") == "field_report"
            or any(v in ("blocked", "partial") for v in st_modes.values())
        )
        raw_segs.append(
            {
                "segment_id": sid,
                "highway": pr.get("highway", "road"),
                "length_m": pr.get("length_m"),
                "status_by_mode": st_modes,
                "source": st.get("source", "geometry"),
                "_sort": (0 if sid in linked_segs else (1 if is_key else 2), sid),
            }
        )
    raw_segs.sort(key=lambda x: x["_sort"])
    for item in raw_segs:
        item.pop("_sort", None)

    freshness = get_freshness(
        project=proj,
        analysis_time=state.get("updated_at"),
        data_root=root,
    )
    return {
        "project": proj,
        "available_projects": projs,
        "mock": bool(state.get("mock", False)),
        "freshness": freshness,
        "places": places_list,
        "segments": raw_segs[:300],
        "total_segments": len(raw_segs),
        "reports": list(reversed(reports[-20:])),
    }


def _compact_coords(geom: dict[str, Any]) -> list[list[list[float]]]:
    """LineString / MultiLineString -> list of lines, coordinates rounded to ~1 m (5 decimals)."""
    if not geom:
        return []
    gtype = geom.get("type")
    lines = [geom.get("coordinates", [])] if gtype == "LineString" else geom.get("coordinates", []) if gtype == "MultiLineString" else []
    return [[[round(float(c[0]), 5), round(float(c[1]), 5)] for c in line] for line in lines if line]


@router.get("/fieldmap")
def get_field_map(project: str | None = Query(default=None)) -> dict[str, Any]:
    """Compact road + place geometry with per-vehicle status for the tap-on-the-map field view (/field/map).

    Same rules and data as /advisor/state; this only trims the payload so a phone or iPad on the hotspot
    can draw every road of the project offline (no tile server, no internet).
    """
    root = _data_root()
    projs = available_projects(data_root=root)
    proj = resolve_project(project, data_root=root)
    seg_fc, places_fc, reports, state = _compute_state_for_project(proj)
    state_by_id = {s["segment_id"]: s for s in state["segments"]}
    ml_by_id: dict[str, dict[str, Any]] = {}
    _, _, ml_data = _load_project_inputs(proj)
    for sc in (ml_data or {}).get("scores", []) or []:
        ml_by_id[str(sc.get("segment_id"))] = sc

    roads: list[dict[str, Any]] = []
    for f in seg_fc.get("features", []):
        pr = f.get("properties", {})
        sid = str(pr.get("segment_id"))
        st = state_by_id.get(sid, {})
        ml = ml_by_id.get(sid)
        roads.append(
            {
                "id": sid,
                "hw": pr.get("highway") or "road",
                "name": pr.get("name"),
                "len": pr.get("length_m"),
                "c": _compact_coords(f.get("geometry") or {}),
                "st": st.get("status_by_mode", {}),
                "src": st.get("source", "geometry"),
                "verify": bool(st.get("needs_verification")),
                "reasons": (st.get("reasons_by_mode", {}) or {}).get("ambulance", [])[:3],
                "p_blocked": ml.get("p_blocked") if ml else None,
                "crop": ml.get("evidence_crop") if ml else None,
            }
        )

    places: list[dict[str, Any]] = []
    for f in places_fc.get("features", []):
        pr = f.get("properties", {})
        geom = f.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        c = geom.get("coordinates", [None, None])
        places.append(
            {
                "id": pr.get("place_id"),
                "name": pr.get("name") or pr.get("place_id"),
                "kind": pr.get("kind", "settlement"),
                "pop": pr.get("population"),
                "seg": pr.get("nearest_segment_id"),
                "c": [round(float(c[0]), 5), round(float(c[1]), 5)],
            }
        )

    return {
        "project": proj,
        "available_projects": projs,
        "mock": bool(state.get("mock", False)),
        "scenario_label": seg_fc.get("scenario_label"),
        "updated_at": state.get("updated_at"),
        "report_count": len(reports),
        "last_report_id": reports[-1]["id"] if reports else 0,
        "roads": roads,
        "places": places,
    }


@router.get("/evidence")
def get_evidence_crop(path: str = Query(..., description="evidence_crop path from ml_scores.json")):
    """Serve one model evidence crop (read-only, only image files under data/projects/)."""
    from fastapi.responses import FileResponse

    base = (_data_root() / "data" / "projects").resolve()
    target = (_data_root() / path).resolve()
    if not target.is_relative_to(base) or target.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(status_code=404, detail="Evidence crop not found")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Evidence crop not found")
    return FileResponse(target)
