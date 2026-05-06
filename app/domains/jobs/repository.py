from __future__ import annotations

import sqlite3

from app.core.time import utc_now_iso
from app.domains.jobs.models import JobRun


def insert_job_run(
    conn: sqlite3.Connection,
    *,
    job_name: str,
    started_at: str,
    finished_at: str | None,
    status: str,
    exit_code: int | None,
    duration_seconds: int | None,
    stdout_tail: str | None,
    stderr_tail: str | None,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO job_runs
          (job_name, started_at, finished_at, status, exit_code,
           duration_seconds, stdout_tail, stderr_tail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_name,
            started_at,
            finished_at,
            status,
            exit_code,
            duration_seconds,
            stdout_tail,
            stderr_tail,
            utc_now_iso(),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_job_runs_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> list[JobRun]:
    rows = conn.execute(
        """
        SELECT * FROM job_runs
        WHERE started_at >= ? AND started_at < ?
        ORDER BY id DESC
        """,
        (start_iso, end_iso),
    ).fetchall()
    return [_row_to_job_run(row) for row in rows]


def list_failed_job_runs_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str, limit: int = 20
) -> list[JobRun]:
    rows = conn.execute(
        """
        SELECT * FROM job_runs
        WHERE started_at >= ? AND started_at < ?
          AND status != 'success'
        ORDER BY id DESC
        LIMIT ?
        """,
        (start_iso, end_iso, limit),
    ).fetchall()
    return [_row_to_job_run(row) for row in rows]


def count_by_status_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count FROM job_runs
        WHERE started_at >= ? AND started_at < ?
        GROUP BY status
        """,
        (start_iso, end_iso),
    ).fetchall()
    return {row["status"]: int(row["count"]) for row in rows}


def _row_to_job_run(row: sqlite3.Row) -> JobRun:
    return JobRun(
        id=int(row["id"]),
        job_name=row["job_name"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=row["status"],
        exit_code=None if row["exit_code"] is None else int(row["exit_code"]),
        duration_seconds=(
            None if row["duration_seconds"] is None else int(row["duration_seconds"])
        ),
        stdout_tail=row["stdout_tail"],
        stderr_tail=row["stderr_tail"],
        created_at=row["created_at"],
    )
