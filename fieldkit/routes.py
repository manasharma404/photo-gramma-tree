"""Field kit (finale item 4): "Save the map to this phone".

GET /field/map.pdf?project=<p> returns the latest printable map (the existing PDF export: map, road status, accuracy
line, legend), so a field team carries a copy that opens with no signal. Drawing it takes about 30 s on the laptop,
so it is kept ready: rebuilt only when a newer field report exists or it is more than 15 minutes old, and drawn once
in the background when the server starts.

Why a PDF and not an offline web page: phones reach the laptop over plain http on the hotspot, and browsers only
let a page keep itself for offline use over https. A PDF opens anywhere.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from advisor.routes import available_projects, resolve_project
from advisor.store import list_field_reports

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "exports" / "field_maps"
MAX_AGE_S = 15 * 60
router = APIRouter(prefix="/field", tags=["field"])
logger = logging.getLogger("vortex.fieldkit")
_build_lock = threading.Lock()


def _latest_report_ts(project: str) -> float:
    reports = list_field_reports(project)
    if not reports:
        return 0.0
    try:
        return datetime.fromisoformat(str(reports[-1]["created_at"]).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()  # unknown format: treat as new, rebuild


def _fresh(path: Path, project: str) -> bool:
    if not path.is_file():
        return False
    m = path.stat().st_mtime
    return time.time() - m < MAX_AGE_S and m >= _latest_report_ts(project)


def build(project: str) -> Path:
    """draw the map PDF for a project (about 30 s); returns its path"""
    from export.inputs import load_export_inputs
    from export.layers import build_all_layers
    from export.pdf_map import write_pdf_map
    from pipeline.activate import load_active

    active = load_active() or {}
    same = active.get("project") == project
    acc = ROOT / active["accuracy"] if same and active.get("accuracy") else None
    ortho = ROOT / active["orthophoto"] if same and active.get("orthophoto") else None
    inp = load_export_inputs(project, accuracy_override=acc if acc and acc.is_file() else None,
                             orthophoto_override=ortho if ortho and ortho.is_file() else None)
    CACHE.mkdir(parents=True, exist_ok=True)
    out = CACHE / f"{project}.pdf"
    tmp = CACHE / f"{project}.{os.getpid()}.tmp.pdf"
    write_pdf_map(inp, build_all_layers(inp), tmp)
    tmp.replace(out)  # a phone never gets a half-written file
    return out


@router.get("/map.pdf")
def map_pdf(project: str | None = None) -> FileResponse:
    proj = resolve_project(project)
    if proj not in available_projects():
        raise HTTPException(status_code=404, detail=f"Unknown project '{proj}'.")
    path = CACHE / f"{proj}.pdf"
    with _build_lock:  # one drawing at a time; a second phone waits for the same file
        if not _fresh(path, proj):
            try:
                build(proj)
            except Exception as exc:  # said plainly on the phone, never a broken file
                logger.exception("field map PDF failed for %s", proj)
                raise HTTPException(status_code=503, detail=f"Could not draw the map for '{proj}': {exc}") from exc
    stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y%m%d_%H%M")
    return FileResponse(path, media_type="application/pdf", filename=f"typhon_map_{proj}_{stamp}.pdf")


def warm(project: str | None = None) -> None:
    """draw the active project's map once in the background, so the first phone does not wait"""
    def run():
        try:
            proj = resolve_project(project)
            with _build_lock:
                if not _fresh(CACHE / f"{proj}.pdf", proj):
                    build(proj)
        except Exception:
            logger.exception("field map warm-up failed")
    threading.Thread(target=run, daemon=True, name="field-map-warm").start()
