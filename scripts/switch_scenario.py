"""Switch active scenario in data/active.json (e.g. for iPad live demo).

Usage:
    uv run python scripts/switch_scenario.py wayanad
    uv run python scripts/switch_scenario.py southfork
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_FILE = ROOT / "data" / "active.json"

SCENARIOS = {
    "wayanad": {
        "project": "wayanad",
        "run_id": "wayanad",
        "full_run_id": "wayanad",
        "orthophoto": "data/projects/wayanad/worldpop_wayanad_2020.tif",
        "dsm": None,
        "dtm": None,
        "accuracy": None,
        "bounds_wsen": [76.1321, 11.4788, 76.1776, 11.5139],
    },
    "southfork": {
        "project": "southfork_f01_4",
        "run_id": "southfork_f01_4_middle",
        "full_run_id": "southfork_f01_4_middle",
        "orthophoto": "data/projects/southfork_f01_4/odm_orthophoto/odm_orthophoto.tif",
        "dsm": None,
        "dtm": None,
        "accuracy": "samples/southfork_f01_4/accuracy.json",
        "bounds_wsen": [-118.4900, 36.5200, -118.4700, 36.5400],
    },
    "southfork_f01_4": {
        "project": "southfork_f01_4",
        "run_id": "southfork_f01_4_middle",
        "full_run_id": "southfork_f01_4_middle",
        "orthophoto": "data/projects/southfork_f01_4/odm_orthophoto/odm_orthophoto.tif",
        "dsm": None,
        "dtm": None,
        "accuracy": "samples/southfork_f01_4/accuracy.json",
        "bounds_wsen": [-118.4900, 36.5200, -118.4700, 36.5400],
    },
}


def switch_scenario(name: str) -> dict:
    key = name.lower().strip()
    if key not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{name}'. Choose from: {list(SCENARIOS.keys())}")
    cfg = dict(SCENARIOS[key])
    cfg["set_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ACTIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default="wayanad", help="Scenario name (wayanad | southfork)")
    args = parser.parse_args()

    cfg = switch_scenario(args.scenario)
    print(f"Switched active scenario to: {cfg['project']}")
    print(json.dumps(cfg, indent=2))


if __name__ == "__main__":
    main()
