"""FastAPI application shell for Vortex offline landslide map & route advisor (T7).

Run offline on 0.0.0.0:8000:
    uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
    # or:
    uv run python -m api.main
"""
from __future__ import annotations

import importlib
import logging
import os
import secrets
import socket
from pathlib import Path
from typing import Any

from urllib.parse import quote

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import advisor
import auth
from auth import core as auth_core

logger = logging.getLogger("vortex.api")
ROOT = Path(__file__).resolve().parent.parent
FIELD_STATIC_DIR = ROOT / "advisor" / "static"


def check_internet_reachable(
    host: str | None = None,
    port: int | None = None,
    timeout_s: float = 1.0,
) -> bool:
    """Truthful 1-second TCP socket probe to detect whether internet is reachable."""
    probe_host = host or os.environ.get("VORTEX_HEALTH_PROBE_HOST", "1.1.1.1")
    probe_port = int(port or os.environ.get("VORTEX_HEALTH_PROBE_PORT", "53"))
    try:
        with socket.create_connection((probe_host, probe_port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _try_mount_optional_router(app: FastAPI, module_name: str, default_prefix: str) -> bool:
    """Mount lead's router (e.g. measure.router, accuracy.router) if importable; else log and continue."""
    candidates = (module_name, f"{module_name}.routes", f"{module_name}.router", f"{module_name}.api")
    for mod_path in candidates:
        try:
            mod = importlib.import_module(mod_path)
        except ImportError:
            continue
        r = getattr(mod, "router", None)
        if r is not None and not isinstance(r, APIRouter):
            r = getattr(r, "router", None)
        if isinstance(r, APIRouter):
            existing_prefix = getattr(r, "prefix", "") or ""
            if existing_prefix.startswith("/"):
                app.include_router(r)
            else:
                app.include_router(r, prefix=default_prefix)
            logger.info("Mounted optional router from %s", mod_path)
            return True
    logger.warning(
        "Optional router '%s.router' is not available yet; starting API without %s routes.",
        module_name,
        default_prefix,
    )
    return False


def create_app(root_dir: Path | None = None) -> FastAPI:
    base_root = root_dir or Path(os.environ.get("VORTEX_DATA_ROOT", "").strip() or ROOT)
    app = FastAPI(
        title="Vortex Offline Landslide Map & Route Advisor",
        version="0.1.0",
    )

    mounted: dict[str, bool] = {"advisor": True, "measure": False, "accuracy": False, "live": False}

    # Access by role (auth/core.py): every request is checked against one permission table; nothing is open by
    # default. A browser that is not signed in is sent to /login; an API call gets 401 (not signed in) or 403.
    @app.middleware("http")
    async def access_by_role(request: Request, call_next):
        if not auth_core.enabled():
            request.state.auth = None
            return await call_next(request)
        session = auth_core.read_session(request.cookies.get(auth_core.COOKIE))
        request.state.auth = session
        role = session["role"] if session else None
        path = request.url.path
        if auth_core.allowed(role, request.method, path):
            return await call_next(request)
        if request.method in ("GET", "HEAD") and "text/html" in request.headers.get("accept", ""):
            if role is None:
                return RedirectResponse(f"/login/?next={quote(path, safe='/')}", status_code=303)
            return RedirectResponse(auth_core.safe_next(None, role), status_code=303)  # e.g. a field team → /field
        if role is None:
            return JSONResponse({"detail": "Sign in first."}, status_code=401)
        return JSONResponse({"detail": f"Not allowed for the {role} role."}, status_code=403)

    app.include_router(auth.router)
    app.include_router(advisor.router, prefix="/advisor")
    mounted["measure"] = _try_mount_optional_router(app, "measure", "/measure")
    mounted["accuracy"] = _try_mount_optional_router(app, "accuracy", "/accuracy")
    mounted["live"] = _try_mount_optional_router(app, "live", "/live")

    @app.get("/health")
    def get_health() -> dict[str, Any]:
        internet = check_internet_reachable(timeout_s=1.0)
        return {
            "status": "ok",
            "internet_reachable": internet,
            "offline_mode": not internet,
            "probe_timeout_s": 1.0,
            "mounted_routers": mounted,
            "web_dist_present": (base_root / "web" / "dist").is_dir(),
        }

    if FIELD_STATIC_DIR.is_dir():
        app.mount(
            "/field-static",
            StaticFiles(directory=str(FIELD_STATIC_DIR)),
            name="field_static",
        )

    @app.get("/field", response_class=HTMLResponse)
    def serve_field_page() -> HTMLResponse:
        html_path = FIELD_STATIC_DIR / "field.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="field.html not found")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    def _serve_project_tile(project: str, tile_path: str) -> FileResponse:
        tiles_root = (base_root / "data" / "projects" / project / "tiles").resolve()
        if not tiles_root.is_dir():
            raise HTTPException(status_code=404, detail=f"No tiles directory for project '{project}'")
        target = (tiles_root / tile_path).resolve()
        if not target.is_relative_to(tiles_root) or not target.is_file():
            raise HTTPException(status_code=404, detail="Tile not found")
        return FileResponse(target)

    @app.get("/tiles/{project}/{tile_path:path}")
    def get_tile_short(project: str, tile_path: str) -> FileResponse:
        return _serve_project_tile(project, tile_path)

    @app.get("/data/projects/{project}/tiles/{tile_path:path}")
    def get_tile_canonical(project: str, tile_path: str) -> FileResponse:
        return _serve_project_tile(project, tile_path)

    web_dist = base_root / "web" / "dist"
    if web_dist.is_dir():
        logger.info("Serving built frontend from %s at /", web_dist)
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web_dist")
    else:
        logger.info("web/dist/ not built yet; serving API index stub at /")

        @app.get("/")
        def root_index() -> dict[str, Any]:
            return {
                "service": "vortex-api",
                "web_dist": "not built yet (expected from lead's web/ build)",
                "endpoints": {
                    "health": "/health",
                    "field_page": "/field",
                    "advisor_state": "/advisor/state",
                    "advisor_access": "/advisor/access",
                    "advisor_priorities": "/advisor/priorities",
                    "advisor_reports": "/advisor/reports",
                },
            }

    return app


app = create_app()


def main() -> None:
    host = os.environ.get("VORTEX_HOST", "0.0.0.0")
    port = int(os.environ.get("VORTEX_PORT", "8000"))
    if auth_core.enabled():
        # access by role: codes live in the git-ignored .env; create any that are missing, never print them here
        from auth.codes import ensure
        written = ensure()
        print("Sign-in is ON." + (f" New access codes were added to .env ({', '.join(written)})." if written else "")
              + " Show them in your own terminal with: uv run python -m auth.codes")
    else:
        # sign-in off (VORTEX_AUTH=off): the original single field PIN, a new one each start unless set
        if not os.environ.get("VORTEX_FIELD_PIN", "").strip():
            os.environ["VORTEX_FIELD_PIN"] = f"{secrets.randbelow(10 ** 6):06d}"
        pin = os.environ["VORTEX_FIELD_PIN"]
        print("Sign-in is OFF. " + (f"Field page PIN for phones: {pin}" if pin.lower() != "off" else "Field page PIN: off"))
    uvicorn.run("api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
