from __future__ import annotations

from dataclasses import dataclass

from app.domains.jobs.models import JobRun


@dataclass(frozen=True)
class DailyReport:
    target_date: str
    job_success_rate: float | None
    job_total: int
    failed_jobs: tuple[JobRun, ...]
    commit_counts: tuple[tuple[str, int | None], ...]
    server_metrics_text: str
    alerts: tuple[str, ...]


@dataclass(frozen=True)
class WeeklyReport:
    target_week_start: str
    weekly_commit_count: int
    active_repositories: tuple[str, ...]
    job_success_rate: float | None
    job_total: int
    failed_jobs: tuple[JobRun, ...]
    backup_success_count: int
    notable_alerts: tuple[str, ...]
