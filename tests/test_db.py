from __future__ import annotations

from app.core.db import connect, run_migrations


def test_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "daily-report.db"
    with connect(str(db_path)) as conn:
        first = run_migrations(conn)
        second = run_migrations(conn)
        assert first == ["001_initial"]
        assert second == []
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM schema_migrations"
        ).fetchone()
        assert row["count"] == 1


def test_pragmas_are_applied_per_connection(tmp_path):
    db_path = tmp_path / "daily-report.db"
    with connect(str(db_path)) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert journal_mode.lower() == "wal"
        assert busy_timeout == 5000
        assert foreign_keys == 1


def test_daily_report_db_path_can_point_to_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(db_path))
    from app.core.config import load_settings

    settings = load_settings()
    with connect(settings.daily_report_db_path) as conn:
        run_migrations(conn)
    assert db_path.exists()
