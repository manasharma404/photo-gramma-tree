"""FastAPI routes for accuracy and the spec sheet; mounted by api/main.py at /accuracy.

GET /accuracy/report -> accuracy.json of the active run
GET /accuracy/spec   -> spec.json (contract) assembled from accuracy.json, run.json and
                        machine.json. Missing values stay null ("not measured yet"), never guessed.
"""
import json
from datetime import datetime, timezone

import jsonschema
from fastapi import APIRouter, HTTPException

from pipeline.activate import ROOT, load_active

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


def _read(rel):
    p = ROOT / rel if rel else None
    # utf-8-sig: data/machine.json was written by PowerShell with a byte-order mark
    return json.loads(p.read_text(encoding="utf-8-sig")) if p and p.exists() else None


@router.get("/report")
def report():
    a = load_active()
    acc = _read(a.get("accuracy")) if a else None
    if acc is None:
        raise HTTPException(404, "accuracy not measured yet for the active run")
    return acc


def build_spec(active):
    acc = _read(active.get("accuracy")) if active else None
    run = _read(f"data/runs/{active['run_id']}/run.json") if active else None
    minutes = round(run["total_seconds"] / 60, 1) if run and run.get("total_seconds") else None
    area = run.get("area_ha") if run else None
    spec = {
        "mock": False,
        "accuracy": acc,
        "timing": {"area_ha": area, "total_minutes": minutes,
                   "minutes_per_ha": round(minutes / area, 2) if (minutes and area) else None,
                   "tier": run.get("tier") if run else None},
        "laptop": _read("data/machine.json"),
        "validation": [],  # tool vs tape: PENDING (docs/validation.md)
        "data_sources": ["USGS South Fork Campground debris-flow survey (public domain), doi:10.5066/P144KDGN",
                         "© OpenStreetMap contributors (ODbL)"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    schema = json.loads((ROOT / "contracts/spec.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(spec, schema)
    return spec


@router.get("/spec")
def spec():
    return build_spec(load_active())
