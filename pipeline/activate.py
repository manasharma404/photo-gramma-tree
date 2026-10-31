"""Choose which run the API measures on: writes data/active.json.

    python -m pipeline.activate --run <run_id> [--full <full_run_id>] [--accuracy <accuracy.json>]

The quick run supplies the orthophoto; the full run (if given) supplies DSM/DTM.
The API reads this file on every request, so switching runs needs no restart.
"""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE = Path(os.environ.get("VORTEX_ACTIVE", ROOT / "data" / "active.json"))


def load_active():
    if not ACTIVE.exists():
        return None
    return json.loads(ACTIVE.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, help="run id providing the orthophoto (and timing)")
    ap.add_argument("--full", default=None, help="run id providing DSM/DTM (default: same as --run)")
    ap.add_argument("--accuracy", type=Path, default=None)
    args = ap.parse_args()

    run = json.loads((ROOT / "data/runs" / args.run / "run.json").read_text(encoding="utf-8"))
    full = json.loads((ROOT / "data/runs" / (args.full or args.run) / "run.json").read_text(encoding="utf-8"))
    acc = args.accuracy or (ROOT / "data/runs" / args.run / "accuracy.json")
    active = {
        "project": run["project"],
        "run_id": run["run_id"],
        "full_run_id": full["run_id"],
        "orthophoto": run["products"]["orthophoto"],
        "dsm": full["products"]["dsm"],
        "dtm": full["products"]["dtm"],
        "accuracy": str(Path(acc).relative_to(ROOT)).replace("\\", "/") if Path(acc).exists() else None,
        "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(json.dumps(active, indent=2), encoding="utf-8")
    print(json.dumps(active, indent=2))


if __name__ == "__main__":
    main()
