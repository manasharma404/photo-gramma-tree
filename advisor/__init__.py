"""Vortex route advisor: passability assessment, reachability graph, priorities, and field reports."""
from __future__ import annotations

from typing import Any

MODES = ("fire_truck", "ambulance", "jeep", "foot")
STATUSES = ("open", "partial", "blocked", "unknown")


def __getattr__(name: str) -> Any:
    if name == "router":
        from advisor.routes import router

        return router
    raise AttributeError(f"module 'advisor' has no attribute {name!r}")
