"""FastAPI routes for the growing map; mounted by api/main.py at /live.

One replay at a time: photos from a set in data/live_sets/ arrive at flight pace and are placed as they arrive
(pipeline/live_run.py). The web map polls /live/status and /live/footprints and draws each photo at its corners.
"""
from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from pipeline.live_run import Replay, list_sets

router = APIRouter(prefix="/live", tags=["live"])
_lock = threading.Lock()
_current: Replay | None = None


class StartIn(BaseModel):
    set: str = Field(..., pattern=r"^[A-Za-z0-9_-]{1,64}$")
    speed: float = Field(1.0, ge=0.0, le=20.0)  # 1 = real time; 0 = as fast as the laptop can


@router.get("/sets")
def get_sets() -> list[dict[str, Any]]:
    return list_sets()


@router.post("/start")
def start(body: StartIn) -> dict[str, Any]:
    global _current
    with _lock:
        if _current is not None and _current.state in ("running", "finishing"):
            _current.stop()
        try:
            rep = Replay(body.set, speed=body.speed)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _current = rep
        rep.start()
    return rep.status()


@router.post("/stop")
def stop() -> dict[str, Any]:
    with _lock:
        if _current is None:
            return {"state": "idle"}
        _current.stop()
        return _current.status()


@router.get("/status")
def status() -> dict[str, Any]:
    rep = _current
    return {"state": "idle"} if rep is None else rep.status()


@router.get("/footprints")
def footprints() -> dict[str, Any]:
    rep = _current
    if rep is None:
        return {"run_id": None, "photos": []}
    return {"run_id": rep.run_id, "photos": rep.footprints_lonlat()}


@router.get("/thumb/{run_id}/{idx}.jpg")
def thumb(run_id: str, idx: int) -> FileResponse:
    rep = _current
    if rep is None or rep.run_id != run_id or idx < 0:
        raise HTTPException(status_code=404, detail="no such photo in the current replay")
    path = rep.dir / "thumbs" / f"{idx}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="photo not placed yet")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})
