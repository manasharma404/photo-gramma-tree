"""FastAPI routes for the measurements; mounted by api/main.py at /measure.

The frontend sends geometry (GeoJSON, WGS84); all maths happens here (brief section 11).
Measurements run on the run named in data/active.json (see pipeline/activate.py).
"""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from measure import core
from pipeline.activate import ROOT, load_active

router = APIRouter(prefix="/measure", tags=["measure"])


class GeometryIn(BaseModel):
    geometry: dict[str, Any]


class WorkingSpaceIn(GeometryIn):
    width_m: Optional[float] = None
    length_m: Optional[float] = None


class LandingZonesIn(BaseModel):
    helicopter: str
    area: Optional[dict[str, Any]] = None


def _surfaces():
    a = load_active()
    if not a or not a.get("dsm"):
        raise HTTPException(503, "No run with a height model is active yet (data/active.json).")
    return core.Surfaces(ROOT / a["dsm"], ROOT / a["dtm"] if a.get("dtm") else None,
                         ROOT / a["accuracy"] if a.get("accuracy") else None, a["full_run_id"])


def _check(geom, kind):
    if geom.get("type") != kind:
        raise HTTPException(422, f"geometry must be a {kind}")


def _run(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/span")
def span(body: GeometryIn):
    _check(body.geometry, "LineString")
    return _run(core.span, _surfaces(), body.geometry)


@router.post("/volume")
def volume(body: GeometryIn):
    _check(body.geometry, "Polygon")
    return _run(core.volume, _surfaces(), body.geometry)


@router.post("/working-space")
def working_space(body: WorkingSpaceIn):
    _check(body.geometry, "Point")
    return _run(core.working_space, _surfaces(), body.geometry, body.width_m, body.length_m)


@router.post("/landing-zones")
def landing_zones(body: LandingZonesIn):
    if body.helicopter not in core.HELI:
        raise HTTPException(422, f"unknown helicopter; choose from {sorted(core.HELI)}")
    return _run(core.landing_zones, _surfaces(), body.helicopter, body.area)


@router.get("/helicopters")
def helicopters():
    return core.HELI
