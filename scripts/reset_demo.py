"""Reset the demo to its starting state: no field reports, no model or human-check history.

Run it before each rehearsal and each judging round, in your own terminal (the app can keep running):

    uv run python scripts/reset_demo.py            # back up the report database, then clear it
    uv run python scripts/reset_demo.py --dry-run  # only show what would be cleared

What it touches: the advisor's SQLite database (the same file the app uses, data/advisor/field_reports.db
unless VORTEX_ADVISOR_DB says otherwise). It first copies that file to data/advisor/backups/, so a reset can be
undone by copying the backup back. Road status is computed from these rows, so the map returns to its
pre-report state on its next refresh.

What it does not touch: the growing map (press Stop in the app; a replay lives only in the app's memory),
the maps and measurements in data/projects/, and anything stored on a phone (an unsent report in a phone's
outbox will still send when that phone reconnects).
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from advisor.store import init_db, resolve_db_path  # noqa: E402

TABLES = ("field_reports", "segment_history")


def counts(db: Path, project: str | None) -> dict[str, int]:
    out = {}
    with sqlite3.connect(db) as conn:
        for t in TABLES:
            if project:
                out[t] = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE project = ?", (project,)).fetchone()[0]
            else:
                out[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return out


def reset(db_path: Path | None = None, project: str | None = None, dry_run: bool = False,
          backup_dir: Path | None = None) -> dict:
    db = init_db(resolve_db_path(db_path))          # makes sure both tables exist
    before = counts(db, project)
    result = {"db": str(db), "project": project or "all", "before": before, "backup": None, "dry_run": dry_run}
    if dry_run or not any(before.values()):
        return result
    backup_dir = backup_dir or db.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{db.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{db.suffix}"
    with sqlite3.connect(db) as src, sqlite3.connect(backup) as dst:   # consistent copy even while the app writes
        src.backup(dst)
    result["backup"] = str(backup)
    with sqlite3.connect(db) as conn:
        for t in TABLES:
            if project:
                conn.execute(f"DELETE FROM {t} WHERE project = ?", (project,))
            else:
                conn.execute(f"DELETE FROM {t}")
    result["after"] = counts(db, project)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", help="clear only this project (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be cleared; change nothing")
    args = ap.parse_args()
    r = reset(project=args.project, dry_run=args.dry_run)
    b = r["before"]
    print(f"Report database: {r['db']}")
    print(f"Project: {r['project']}. Field reports: {b['field_reports']}. Model/human-check history: {b['segment_history']}.")
    if r["dry_run"]:
        print("Dry run: nothing changed.")
    elif r["backup"] is None:
        print("Already at the starting state: nothing to clear.")
    else:
        a = r["after"]
        print(f"Backed up to {r['backup']}")
        print(f"Cleared. Now: field reports {a['field_reports']}, history {a['segment_history']}.")
        print("The map shows the change on its next refresh. Press Stop on the growing map if it is running.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
