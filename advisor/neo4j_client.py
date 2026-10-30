"""Neo4j connection helper reading local gitignored .env (no hardcoded secrets)."""
from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import dotenv_values
from neo4j import Driver, GraphDatabase

ROOT = Path(__file__).resolve().parent.parent


def get_neo4j_settings(env_path: Path | None = None) -> tuple[str, str, str] | None:
    """Return (uri, user, password) from environment or .env, or None if unconfigured."""
    merged: dict[str, str] = {}
    p = env_path or (ROOT / ".env")
    if p.exists():
        for k, v in dotenv_values(p).items():
            if v is not None:
                merged[k] = v
    for k in ("VORTEX_NEO4J_URI", "NEO4J_URI", "NEO4J_AUTH", "NEO4J_USER", "NEO4J_PASSWORD"):
        if k in os.environ:
            merged[k] = os.environ[k]

    uri = merged.get("VORTEX_NEO4J_URI") or merged.get("NEO4J_URI") or "bolt://127.0.0.1:7687"
    auth = merged.get("NEO4J_AUTH", "")
    if "/" in auth:
        user, password = auth.split("/", 1)
    else:
        user = merged.get("NEO4J_USER", "neo4j")
        password = merged.get("NEO4J_PASSWORD", "")

    if not password or password == "CHANGE_ME_LOCAL_ONLY":
        return None
    return uri, user, password


def open_driver(env_path: Path | None = None, timeout_s: float = 2.0) -> Driver | None:
    """Open and verify a Neo4j driver with GDS available, returning None on failure."""
    settings = get_neo4j_settings(env_path)
    if settings is None:
        return None
    uri, user, password = settings
    parsed = urlparse(uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7687
    try:
        with socket.create_connection((host, port), timeout=min(timeout_s, 0.5)):
            pass
    except OSError:
        return None

    driver = GraphDatabase.driver(
        uri,
        auth=(user, password),
        connection_timeout=timeout_s,
        max_transaction_retry_time=timeout_s,
    )
    try:
        rec = driver.execute_query("RETURN gds.version() AS v")
        if not rec.records or not rec.records[0]["v"]:
            driver.close()
            return None
        return driver
    except Exception:
        driver.close()
        return None


def project_paths(project: str, data_root: Path | None = None) -> dict[str, Path]:
    """Resolve segments.geojson, places.geojson, and optional ml_scores.json for a project."""
    root = data_root or ROOT
    if project == "mock":
        ex = root / "contracts" / "examples"
        return {
            "segments": ex / "segments.example.geojson",
            "places": ex / "places.example.geojson",
            "ml_scores": ex / "ml_scores.example.json",
            "project_dir": ex,
        }

    proj_dir = root / "data" / "projects" / project
    seg_candidates = [
        proj_dir / "roads" / "segments.geojson",
        proj_dir / "segments.geojson",
    ]
    place_candidates = [
        proj_dir / "places.geojson",
        proj_dir / "roads" / "places.geojson",
    ]
    seg_path = next((c for c in seg_candidates if c.exists()), seg_candidates[0])
    place_path = next((c for c in place_candidates if c.exists()), place_candidates[0])
    return {
        "segments": seg_path,
        "places": place_path,
        "ml_scores": proj_dir / "ml_scores.json",
        "project_dir": proj_dir,
    }
