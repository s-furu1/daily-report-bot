from __future__ import annotations

from dataclasses import dataclass


JOB_STATUSES = {"success", "failed", "timeout"}


@dataclass(frozen=True)
class JobRun:
    id: int
    job_name: str
    started_at: str
    finished_at: str | None
    status: str
    exit_code: int | None
    duration_seconds: int | None
    stdout_tail: str | None
    stderr_tail: str | None
    created_at: str
