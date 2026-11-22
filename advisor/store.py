"""SQLite store for ground responder field reports and freshness metadata (T8)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from advisor import MODES
from advisor.neo4j_client import project_paths

ROOT = Path(__file__).resolve().parent.parent
REPORT_KINDS = ("dead_end", "cleared", "new_debris", "other", "confirm", "reject", "confirmed", "rejected")


def resolve_db_path(db_path: Path | None = None) -> Path:
    if db_path is not None:
        return db_path
    env_val = os.environ.get("VORTEX_ADVISOR_DB", "").strip()
    if env_val:
        return Path(env_val)
    return ROOT / "data" / "advisor" / "field_reports.db"


def init_db(db_path: Path | None = None) -> Path:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS field_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                segment_id TEXT,
                place_id TEXT,
                kind TEXT NOT NULL,
                modes_json TEXT NOT NULL,
                note TEXT,
                reporter TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_field_reports_project ON field_reports(project, id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS segment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                segment_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                model_name TEXT,
                model_version TEXT,
                p_blocked REAL,
                evidence_crop TEXT,
                reporter TEXT,
                note TEXT,
                recorded_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_segment_history_proj ON segment_history(project, segment_id)"
        )
        conn.commit()
    return path


def record_suspicion(
    project: str,
    segment_id: str,
    p_blocked: float,
    evidence_crop: str | None = None,
    model: str = "typhon_debris_resnet18",
    version: str = "1.0.0",
    recorded_at: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Record a model-detected debris suspicion into the segment history (Idea 7)."""
    ts = recorded_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = init_db(db_path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO segment_history (project, segment_id, event_type, model_name, model_version, p_blocked, evidence_crop, recorded_at)
            VALUES (?, ?, 'model_suspicion', ?, ?, ?, ?, ?)
            """,
            (project, segment_id, model, version, float(p_blocked), evidence_crop, ts),
        )
        rec_id = int(cur.lastrowid)
        conn.commit()
    return {
        "id": rec_id,
        "project": project,
        "segment_id": segment_id,
        "event": "model_suspicion",
        "model_said": f"{model} v{version}: p_blocked={float(p_blocked):.2f}" + (f" (crop: {evidence_crop})" if evidence_crop else ""),
        "person_said": None,
        "when": ts,
        "p_blocked": float(p_blocked),
        "evidence_crop": evidence_crop,
    }


def record_verification(
    project: str,
    segment_id: str,
    action: str,
    reporter: str | None = None,
    note: str | None = None,
    recorded_at: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Record human responder confirmation or rejection of a suspicion into segment history (Idea 7)."""
    ts = recorded_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    clean_reporter = (reporter or "").strip() or None
    clean_note = (note or "").strip() or None
    event_type = "field_confirm" if action in ("confirm", "confirmed") else ("field_reject" if action in ("reject", "rejected") else f"field_{action}")

    path = init_db(db_path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO segment_history (project, segment_id, event_type, reporter, note, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project, segment_id, event_type, clean_reporter, clean_note, ts),
        )
        rec_id = int(cur.lastrowid)
        conn.commit()

    person_summary = f"{clean_reporter or 'responder'} ({event_type}): {clean_note or 'no note'}"
    return {
        "id": rec_id,
        "project": project,
        "segment_id": segment_id,
        "event": event_type,
        "model_said": None,
        "person_said": person_summary,
        "when": ts,
        "reporter": clean_reporter,
        "note": clean_note,
    }


def get_segment_history(
    project: str,
    segment_id: str,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return chronological verification history for a road segment (model said, person said, when)."""
    path = resolve_db_path(db_path)
    if not path.exists():
        return []
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, project, segment_id, event_type, model_name, model_version, p_blocked, evidence_crop, reporter, note, recorded_at
            FROM segment_history
            WHERE project = ? AND segment_id = ?
            ORDER BY id ASC
            """,
            (project, segment_id),
        ).fetchall()

    history: list[dict[str, Any]] = []
    for r in rows:
        evt = str(r["event_type"])
        p_blk = r["p_blocked"]
        m_name = r["model_name"]
        m_ver = r["model_version"]
        crop = r["evidence_crop"]
        rep = r["reporter"]
        note = r["note"]
        when = str(r["recorded_at"])

        if evt == "model_suspicion":
            model_said = f"{m_name or 'model'} {m_ver or ''} flagged p_blocked={float(p_blk or 0):.2f}".strip()
            if crop:
                model_said += f" [crop: {crop}]"
            person_said = None
        else:
            model_said = None
            rep_label = rep or "responder"
            person_said = f"{rep_label} ({evt})" + (f": {note}" if note else "")

        history.append(
            {
                "id": int(r["id"]),
                "project": str(r["project"]),
                "segment_id": str(r["segment_id"]),
                "event": evt,
                "model_said": model_said,
                "person_said": person_said,
                "when": when,
                "p_blocked": float(p_blk) if p_blk is not None else None,
                "evidence_crop": crop,
                "reporter": rep,
                "note": note,
            }
        )
    return history


def add_field_report(
    project: str,
    kind: str,
    segment_id: str | None = None,
    place_id: str | None = None,
    modes: list[str] | None = None,
    note: str | None = None,
    reporter: str | None = None,
    created_at: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if kind not in REPORT_KINDS:
        raise ValueError(f"Invalid report kind '{kind}'; expected one of {REPORT_KINDS}")
    if not segment_id and not place_id:
        raise ValueError("Either segment_id or place_id must be provided")

    clean_modes = [m for m in (modes or list(MODES)) if m in MODES]
    if not clean_modes:
        clean_modes = list(MODES)

    ts = created_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    clean_note = (note or "").strip() or None
    clean_reporter = (reporter or "").strip() or None

    path = init_db(db_path)
    with sqlite3.connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO field_reports (project, segment_id, place_id, kind, modes_json, note, reporter, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project,
                segment_id,
                place_id,
                kind,
                json.dumps(clean_modes),
                clean_note,
                clean_reporter,
                ts,
            ),
        )
        report_id = int(cur.lastrowid)

        if segment_id:
            evt_type = (
                "field_confirm"
                if kind in ("confirm", "confirmed")
                else ("field_reject" if kind in ("reject", "rejected") else f"field_{kind}")
            )
            conn.execute(
                """
                INSERT INTO segment_history (project, segment_id, event_type, reporter, note, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (project, segment_id, evt_type, clean_reporter, clean_note, ts),
            )

        conn.commit()

    return {
        "id": report_id,
        "project": project,
        "segment_id": segment_id,
        "place_id": place_id,
        "kind": kind,
        "modes": clean_modes,
        "note": clean_note,
        "reporter": clean_reporter,
        "created_at": ts,
    }


def list_field_reports(project: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    path = resolve_db_path(db_path)
    if not path.exists():
        return []
    init_db(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, project, segment_id, place_id, kind, modes_json, note, reporter, created_at
            FROM field_reports
            WHERE project = ?
            ORDER BY id ASC
            """,
            (project,),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "project": str(r["project"]),
                "segment_id": r["segment_id"],
                "place_id": r["place_id"],
                "kind": str(r["kind"]),
                "modes": json.loads(r["modes_json"]),
                "note": r["note"],
                "reporter": r["reporter"],
                "created_at": str(r["created_at"]),
            }
        )
    return out


def get_freshness(
    project: str,
    analysis_time: str | None = None,
    data_root: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return honest freshness metadata (survey time, analysis time, field report count)."""
    reports = list_field_reports(project, db_path=db_path)
    paths = project_paths(project, data_root=data_root)
    proj_dir = paths["project_dir"]

    survey_time: str | None = None
    survey_note: str | None = None

    if project == "mock":
        survey_note = "mock contract fixture (not a real survey)"
    else:
        run_json = proj_dir / "run.json"
        scen_json = proj_dir / "scenario_sources.json"
        if run_json.exists():
            try:
                rj = json.loads(run_json.read_text(encoding="utf-8"))
                survey_time = rj.get("captured_at") or rj.get("survey_time") or rj.get("started_at")
            except Exception:
                survey_time = None
        elif scen_json.exists():
            try:
                sj = json.loads(scen_json.read_text(encoding="utf-8"))
                survey_time = sj.get("generated_at")
                survey_note = sj.get("label")
            except Exception:
                survey_time = None

    last_report_at = reports[-1]["created_at"] if reports else None
    return {
        "project": project,
        "survey_time": survey_time,
        "survey_note": survey_note,
        "analysis_time": analysis_time,
        "field_report_count": len(reports),
        "last_report_at": last_report_at,
    }
