"""Sign in / out; mounted by api/main.py at /auth. The page itself is web/login/ (built to web/dist/login/)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from auth import core

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    next: str | None = Field(default=None, max_length=300)


def _device(request: Request) -> str:
    """who to count wrong codes against. Through the Cloudflare tunnel every request arrives from this laptop
    (127.0.0.1), so a scanner's wrong guesses would lock the laptop's own operator out; for those requests the
    visitor's real address is in CF-Connecting-IP. That header is trusted ONLY on requests that really come from
    127.0.0.1 (the tunnel): a phone on the hotspot cannot use it to dodge its own lockout."""
    host = request.client.host if request.client else "unknown"
    cf = request.headers.get("cf-connecting-ip", "").strip()
    if host in ("127.0.0.1", "::1") and cf:
        return f"tunnel:{cf}"
    return host


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    dev = _device(request)
    if core.locked_out(dev):
        raise HTTPException(status_code=429, detail="Too many wrong codes from this device. Wait 10 minutes.")
    hit = core.check_code(body.code)
    if hit is None:
        core.record_fail(dev)
        raise HTTPException(status_code=403, detail="That code is not right. Ask the laptop operator.")
    core.clear_fails(dev)
    role, team = hit
    response.set_cookie(core.COOKIE, core.make_session(role, team), max_age=core.SESSION_S,
                        httponly=True, samesite="strict", path="/")
    return {"role": role, "team": team, "next": core.safe_next(body.next, role)}


@router.post("/logout")
def logout(response: Response) -> dict[str, Any]:
    response.delete_cookie(core.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    s = core.read_session(request.cookies.get(core.COOKIE))
    return {"auth": core.enabled(), "role": s["role"] if s else None, "team": s["team"] if s else None}
