"""Access by role (finale item 6): who may see and do what.

Roles
- operator:  the person at the laptop; everything.
- evaluator: judges and mentors on the iPad or any device; sees everything and uses every judge input
             (flight replay, measuring, field reports, tapping roads). Not admin actions.
- field:     a field team on a phone; the report page and the data it needs, nothing else. One PIN per team,
             so every report says which team sent it.

Access codes live in the git-ignored .env (written by `python -m auth.codes`), never in the repo:
  VORTEX_OPERATOR_CODE, VORTEX_EVALUATOR_CODE, VORTEX_TEAM_PINS="Team A:123456,Team B:654321"
  VORTEX_SESSION_SECRET (signs the session cookie)
VORTEX_AUTH=off turns the whole check off (tests of other modules; never on the demo laptop).

A session is a signed cookie (HMAC-SHA256), HttpOnly, SameSite=Strict, 12 hours. Five wrong codes from one device
lock it out for 10 minutes. The laptop itself gets no free pass: a tunnel (as a security scanner might use) makes
every request look local, so "local means trusted" would let anyone in.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
COOKIE = "typhon_session"
SESSION_S = 12 * 3600
MAX_FAILS, LOCKOUT_S = 5, 600
_fails: dict[str, list[float]] = {}

# ---------- what each role may do (method, path prefix); anything not listed is refused ----------
PUBLIC = [
    ("GET", "/"), ("GET", "/index.html"), ("GET", "/assets/"), ("GET", "/login"), ("GET", "/field-static/"),
    ("GET", "/favicon"), ("GET", "/health"), ("GET", "/accuracy/spec"),  # spec numbers are public (landing page)
    # the public home pages' own pictures, and the earlier home page kept at /classic/ (web/public, web/classic)
    ("GET", "/landing/"), ("GET", "/art/"), ("GET", "/hero.webp"), ("GET", "/contours.svg"), ("GET", "/classic/"),
    ("POST", "/auth/login"), ("POST", "/auth/logout"), ("GET", "/auth/me"),
]
FIELD = [("GET", "/field"), ("GET", "/advisor/"), ("POST", "/advisor/reports")]
EVALUATOR = [("GET", "/"), ("POST", "/live/"), ("POST", "/measure/"), ("POST", "/advisor/reports")]
OPERATOR_ONLY: list[tuple[str, str]] = []  # admin actions go here (none yet); evaluators never get them
EXACT_ONLY = {"/", "/index.html"}  # in PUBLIC these match only themselves, not everything under them


def enabled() -> bool:
    return os.environ.get("VORTEX_AUTH", "on").strip().lower() != "off"


def _match(rules: list[tuple[str, str]], method: str, path: str) -> bool:
    m = "GET" if method == "HEAD" else method
    for rm, prefix in rules:
        if rm != m:
            continue
        if prefix in EXACT_ONLY and rules is PUBLIC:
            if path == prefix:
                return True
        elif path == prefix.rstrip("/") or path.startswith(prefix):
            return True
    return False


def is_public(method: str, path: str) -> bool:
    return _match(PUBLIC, method, path)


def allowed(role: str | None, method: str, path: str) -> bool:
    if is_public(method, path):
        return True
    if role == "operator":
        return True
    if role == "evaluator":
        return _match(EVALUATOR, method, path) and not _match(OPERATOR_ONLY, method, path)
    if role == "field":
        return _match(FIELD, method, path)
    return False


# ---------- codes ----------
def _settings() -> dict[str, str]:
    env = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None} if (ROOT / ".env").exists() else {}
    for k in ("VORTEX_OPERATOR_CODE", "VORTEX_EVALUATOR_CODE", "VORTEX_TEAM_PINS", "VORTEX_SESSION_SECRET"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def teams() -> dict[str, str]:
    """team name -> PIN"""
    out = {}
    for part in _settings().get("VORTEX_TEAM_PINS", "").split(","):
        if ":" in part:
            name, pin = part.rsplit(":", 1)
            if name.strip() and pin.strip():
                out[name.strip()] = pin.strip()
    return out


def configured() -> bool:
    s = _settings()
    return bool(s.get("VORTEX_OPERATOR_CODE") and s.get("VORTEX_EVALUATOR_CODE") and s.get("VORTEX_SESSION_SECRET"))


def check_code(code: str) -> tuple[str, str | None] | None:
    """an access code -> (role, team) or None; constant-time comparisons"""
    code = (code or "").strip()
    if not code:
        return None
    s = _settings()
    hit = None
    for role, key in (("operator", "VORTEX_OPERATOR_CODE"), ("evaluator", "VORTEX_EVALUATOR_CODE")):
        if s.get(key) and hmac.compare_digest(code, s[key]):
            hit = (role, None)
    for name, pin in teams().items():
        if hmac.compare_digest(code, pin):
            hit = hit or ("field", name)
    return hit


def locked_out(device: str) -> bool:
    now = time.time()
    _fails[device] = [t for t in _fails.get(device, []) if now - t < LOCKOUT_S]
    return len(_fails[device]) >= MAX_FAILS


def record_fail(device: str) -> None:
    _fails.setdefault(device, []).append(time.time())


def clear_fails(device: str) -> None:
    _fails.pop(device, None)


# ---------- sessions ----------
def _secret() -> bytes:
    return _settings().get("VORTEX_SESSION_SECRET", "").encode()


def make_session(role: str, team: str | None) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"r": role, "t": team, "e": int(time.time()) + SESSION_S}).encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_session(token: str | None) -> dict | None:
    if not token or "." not in token or not _secret():
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None
    if data.get("e", 0) < time.time() or data.get("r") not in ("operator", "evaluator", "field"):
        return None
    return {"role": data["r"], "team": data.get("t")}


def safe_next(nxt: str | None, role: str) -> str:
    """where to go after signing in: only a path on this server (no open redirect)"""
    default = "/field" if role == "field" else "/app/"
    if not nxt or not nxt.startswith("/") or nxt.startswith("//") or "\\" in nxt:
        return default
    return nxt if allowed(role, "GET", nxt.split("?")[0]) else default


def new_code(n_digits: int | None = None) -> str:
    if n_digits:
        return f"{secrets.randbelow(10 ** n_digits):0{n_digits}d}"
    return secrets.token_urlsafe(9)
