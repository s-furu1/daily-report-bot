from __future__ import annotations

from app.core.db import connect, run_migrations
from app.core.time import utc_now_iso
from app.domains.jobs.service import (
    failed_jobs_in_range,
    record_job_run,
    success_rate_in_range,
)


def _record(conn, name, status, exit_code, started_at):
    record_job_run(
        conn,
        job_name=name,
        started_at=started_at,
        finished_at=started_at,
        status=status,
        exit_code=exit_code,
        duration_seconds=1,
        stdout_tail="",
        stderr_tail="",
    )


def test_record_success_and_failed_jobs(tmp_path):
    with connect(str(tmp_path / "j.db")) as conn:
        run_migrations(conn)
        now = utc_now_iso()
        _record(conn, "backup-life-db", "success", 0, now)
        _record(conn, "backup-life-db", "failed", 1, now)

        rows = conn.execute(
            "SELECT job_name, status, exit_code FROM job_runs ORDER BY id"
        ).fetchall()
        assert [(r["job_name"], r["status"], r["exit_code"]) for r in rows] == [
            ("backup-life-db", "success", 0),
            ("backup-life-db", "failed", 1),
        ]
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "job.success" in types
        assert "job.failed" in types


def test_success_rate_in_range_uses_status_counts(tmp_path):
    with connect(str(tmp_path / "j.db")) as conn:
        run_migrations(conn)
        started = "2026-05-05T01:00:00+00:00"
        for _ in range(3):
            _record(conn, "j", "success", 0, started)
        _record(conn, "j", "failed", 1, started)
        rate = success_rate_in_range(
            conn, "2026-05-05T00:00:00+00:00", "2026-05-06T00:00:00+00:00"
        )
        assert rate is not None
        assert abs(rate - 0.75) < 1e-9


def test_success_rate_in_range_returns_none_when_empty(tmp_path):
    with connect(str(tmp_path / "j.db")) as conn:
        run_migrations(conn)
        rate = success_rate_in_range(
            conn, "2026-05-05T00:00:00+00:00", "2026-05-06T00:00:00+00:00"
        )
        assert rate is None


def test_failed_jobs_filtered_to_range(tmp_path):
    with connect(str(tmp_path / "j.db")) as conn:
        run_migrations(conn)
        _record(conn, "a", "failed", 1, "2026-05-05T01:00:00+00:00")
        _record(conn, "b", "success", 0, "2026-05-05T02:00:00+00:00")
        _record(conn, "c", "failed", 2, "2026-05-04T01:00:00+00:00")
        failed = failed_jobs_in_range(
            conn, "2026-05-05T00:00:00+00:00", "2026-05-06T00:00:00+00:00"
        )
        assert [j.job_name for j in failed] == ["a"]
