"""scripts/reset_demo.py: clears reports and history, backs up first, and can stay within one project."""
import importlib.util
from pathlib import Path

from advisor.store import add_field_report, list_field_reports, record_suspicion

spec = importlib.util.spec_from_file_location("reset_demo", Path(__file__).resolve().parents[1] / "scripts" / "reset_demo.py")
reset_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset_demo)


def _seed(db):
    add_field_report("a", "dead_end", segment_id="s1", db_path=db)
    add_field_report("b", "dead_end", segment_id="s2", db_path=db)
    record_suspicion("a", "s1", 0.9, db_path=db)


def test_reset_backs_up_then_clears(tmp_path):
    db = tmp_path / "reports.db"
    _seed(db)
    r = reset_demo.reset(db_path=db, backup_dir=tmp_path / "bk")
    assert r["before"]["field_reports"] == 2 and r["before"]["segment_history"] >= 1  # reports also log history
    assert r["after"] == {"field_reports": 0, "segment_history": 0}
    backup = Path(r["backup"])
    assert backup.exists() and len(list_field_reports("a", db_path=backup)) == 1  # the backup still has them


def test_dry_run_changes_nothing(tmp_path):
    db = tmp_path / "reports.db"
    _seed(db)
    r = reset_demo.reset(db_path=db, dry_run=True, backup_dir=tmp_path / "bk")
    assert r["backup"] is None and not (tmp_path / "bk").exists()
    assert len(list_field_reports("a", db_path=db)) == 1


def test_one_project_only(tmp_path):
    db = tmp_path / "reports.db"
    _seed(db)
    reset_demo.reset(db_path=db, project="a", backup_dir=tmp_path / "bk")
    assert list_field_reports("a", db_path=db) == [] and len(list_field_reports("b", db_path=db)) == 1
