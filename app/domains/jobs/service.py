from __future__ import annotations

import sqlite3

from app.domains.events.service import record_event
from app.domains.jobs import repository
from app.domains.jobs.models import JOB_STATUSES, JobRun


def record_job_run(
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
    if status not in JOB_STATUSES:
        raise ValueError(f"invalid job status: {status}")
    job_id = repository.insert_job_run(
        conn,
        job_name=job_name,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        exit_code=exit_code,
        duration_seconds=duration_seconds,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )
    record_event(
        conn,
        f"job.{status}",
        "jobs",
        {"job_run_id": job_id, "job_name": job_name, "exit_code": exit_code},
    )
    return job_id


def success_rate_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> float | None:
    counts = repository.count_by_status_in_range(conn, start_iso, end_iso)
    total = sum(counts.values())
    if total == 0:
        return None
    success = counts.get("success", 0)
    return success / total


def failed_jobs_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str, limit: int = 20
) -> list[JobRun]:
    return repository.list_failed_job_runs_in_range(conn, start_iso, end_iso, limit)


def all_runs_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> list[JobRun]:
    return repository.list_job_runs_in_range(conn, start_iso, end_iso)
