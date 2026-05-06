from __future__ import annotations

import sqlite3
from typing import Iterable

from app.core.time import day_bounds_utc, week_bounds_utc
from app.domains.events.service import record_event
from app.domains.jobs.service import (
    all_runs_in_range,
    failed_jobs_in_range,
    success_rate_in_range,
)
from app.domains.reports.models import DailyReport, WeeklyReport
from app.github.client import GitHubError
from app.metrics.server import ServerMetrics, format_server_metrics


def collect_commit_counts(
    conn: sqlite3.Connection,
    github_client,
    repositories: Iterable[str],
    since_iso: str,
    until_iso: str,
) -> tuple[tuple[str, int | None], ...]:
    counts: list[tuple[str, int | None]] = []
    for repo in repositories:
        try:
            commits = github_client.list_commits(
                repo, since_iso=since_iso, until_iso=until_iso
            )
            counts.append((repo, len(commits)))
        except GitHubError as exc:
            record_event(
                conn,
                "github.commit.failed",
                "github",
                {"repo": repo, "error": str(exc)},
            )
            counts.append((repo, None))
    return tuple(counts)


def build_daily_report(
    conn: sqlite3.Connection,
    *,
    github_client,
    repositories: Iterable[str],
    metrics: ServerMetrics,
    target_date: str,
) -> DailyReport:
    start_iso, end_iso = day_bounds_utc(target_date)
    success_rate = success_rate_in_range(conn, start_iso, end_iso)
    runs = all_runs_in_range(conn, start_iso, end_iso)
    failed = failed_jobs_in_range(conn, start_iso, end_iso, limit=20)
    commit_counts = collect_commit_counts(
        conn, github_client, repositories, start_iso, end_iso
    )
    alerts = tuple(
        f"job failed: {run.job_name} ({run.status})" for run in failed
    )
    record_event(
        conn,
        "report.daily.built",
        "reports",
        {"target_date": target_date, "job_total": len(runs)},
    )
    return DailyReport(
        target_date=target_date,
        job_success_rate=success_rate,
        job_total=len(runs),
        failed_jobs=tuple(failed),
        commit_counts=commit_counts,
        server_metrics_text=format_server_metrics(metrics),
        alerts=alerts,
    )


def build_weekly_report(
    conn: sqlite3.Connection,
    *,
    github_client,
    repositories: Iterable[str],
    target_week_start: str,
) -> WeeklyReport:
    start_iso, end_iso = week_bounds_utc(target_week_start)
    success_rate = success_rate_in_range(conn, start_iso, end_iso)
    runs = all_runs_in_range(conn, start_iso, end_iso)
    failed = failed_jobs_in_range(conn, start_iso, end_iso, limit=50)
    commit_counts = collect_commit_counts(
        conn, github_client, repositories, start_iso, end_iso
    )
    weekly_total = sum(count for _repo, count in commit_counts if count is not None)
    active_repos = tuple(
        repo for repo, count in commit_counts if count and count > 0
    )
    backup_success_count = sum(
        1
        for run in runs
        if run.status == "success" and "backup" in run.job_name.lower()
    )
    notable_alerts = tuple(f"failed: {run.job_name}" for run in failed[:5])
    record_event(
        conn,
        "report.weekly.built",
        "reports",
        {
            "target_week_start": target_week_start,
            "weekly_commit_count": weekly_total,
        },
    )
    return WeeklyReport(
        target_week_start=target_week_start,
        weekly_commit_count=weekly_total,
        active_repositories=active_repos,
        job_success_rate=success_rate,
        job_total=len(runs),
        failed_jobs=tuple(failed),
        backup_success_count=backup_success_count,
        notable_alerts=notable_alerts,
    )


def render_daily_report_text(report: DailyReport) -> str:
    lines = [f"【Server Report (daily) {report.target_date}】", ""]
    if report.job_success_rate is None:
        lines.append("ジョブ成功率: 集計対象なし")
    else:
        lines.append(
            f"ジョブ成功率: {int(round(report.job_success_rate * 100))}%"
            f" ({report.job_total} runs)"
        )
    if report.failed_jobs:
        lines.append("失敗ジョブ:")
        for run in report.failed_jobs[:5]:
            lines.append(
                f"  - {run.job_name} ({run.status}, exit={run.exit_code})"
            )
    else:
        lines.append("失敗ジョブ: 0")
    lines.append("")
    lines.append("GitHub commits:")
    if not report.commit_counts:
        lines.append("  (リポジトリ未設定)")
    for repo, count in report.commit_counts:
        if count is None:
            lines.append(f"  - {repo}: unavailable")
        else:
            lines.append(f"  - {repo}: {count}")
    lines.append("")
    lines.append("Server metrics:")
    lines.append(report.server_metrics_text)
    if report.alerts:
        lines.append("")
        lines.append("Alerts:")
        for alert in report.alerts[:5]:
            lines.append(f"  - {alert}")
    return "\n".join(lines)


def render_weekly_report_text(report: WeeklyReport) -> str:
    lines = [f"【Server Report (weekly) since {report.target_week_start}】", ""]
    lines.append(f"weekly commit count: {report.weekly_commit_count}")
    lines.append(
        "active repositories: "
        + (", ".join(report.active_repositories) if report.active_repositories else "(なし)")
    )
    if report.job_success_rate is None:
        lines.append("ジョブ成功率: 集計対象なし")
    else:
        lines.append(
            f"ジョブ成功率: {int(round(report.job_success_rate * 100))}%"
            f" ({report.job_total} runs)"
        )
    lines.append(f"backup success count: {report.backup_success_count}")
    if report.notable_alerts:
        lines.append("notable alerts:")
        for alert in report.notable_alerts:
            lines.append(f"  - {alert}")
    return "\n".join(lines)
