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
    backup_success_count = sum(
        1
        for run in runs
        if run.status == "success" and "backup" in run.job_name.lower()
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
        backup_success_count=backup_success_count,
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
        commit_counts=commit_counts,
        job_success_rate=success_rate,
        job_total=len(runs),
        failed_jobs=tuple(failed),
        backup_success_count=backup_success_count,
        notable_alerts=notable_alerts,
    )


def render_daily_report_text(report: DailyReport) -> str:
    active, inactive = split_commit_counts(report.commit_counts)
    total_commits = sum(count for _repo, count in active)
    lines = [f"【今日のサーバーレポート】{report.target_date}", ""]
    lines.append("概要:")
    lines.append(f"- GitHub活動: {len(active)} repo / {total_commits} commits")
    lines.append(
        "- ジョブ: "
        + ("wrapper未連携" if report.job_total == 0 else f"{report.job_total} runs")
    )
    lines.append("- サーバー: 正常")
    lines.append(
        "- 注意: "
        + ("backup成功記録なし" if report.backup_success_count == 0 else "なし")
    )
    lines.append("")
    lines.append("今日動いたリポジトリ:")
    if active:
        for index, (repo, count) in enumerate(active[:10], start=1):
            lines.append(f"{index}. {short_repo(repo)}: {count} commits")
    else:
        lines.append("なし")
    if inactive:
        lines.append("")
        lines.append("動きなし:")
        lines.append(", ".join(short_repo(repo) for repo in inactive[:10]))
    if report.failed_jobs:
        lines.append("")
        lines.append("失敗ジョブ:")
        for run in report.failed_jobs[:5]:
            lines.append(f"- {run.job_name} ({run.status}, exit={run.exit_code})")
    lines.append("")
    lines.append("サーバー状態:")
    lines.extend(format_server_metrics_for_report(report.server_metrics_text))
    if report.job_total == 0:
        lines.append("")
        lines.append("補足:")
        lines.append("cron/job記録はまだありません。")
        lines.append("run-and-log.py 経由に置き換えると成功率を集計できます。")
    return "\n".join(lines)


def render_weekly_report_text(report: WeeklyReport) -> str:
    active, _inactive = split_commit_counts(report.commit_counts)
    lines = [f"【今週の活動サマリー】{report.target_week_start}〜", ""]
    lines.append("概要:")
    lines.append(f"- 合計 commits: {report.weekly_commit_count}")
    lines.append(f"- active repos: {len(report.active_repositories)}")
    lines.append(f"- failed jobs: {len(report.failed_jobs)}")
    lines.append(f"- backup成功記録: {report.backup_success_count}")
    lines.append("")
    lines.append("主に動いたリポジトリ:")
    if active:
        for index, (repo, count) in enumerate(active[:10], start=1):
            lines.append(f"{index}. {short_repo(repo)}: {count} commits")
    else:
        lines.append("なし")
    lines.append("")
    lines.append("未連携:")
    if report.job_total == 0:
        lines.append("- job_runs: wrapper未連携")
    if report.backup_success_count == 0:
        lines.append("- backup: 成功記録なし")
    if report.notable_alerts:
        lines.append("")
        lines.append("notable alerts:")
        for alert in report.notable_alerts:
            lines.append(f"- {alert}")
    return "\n".join(lines)


def split_commit_counts(
    commit_counts: tuple[tuple[str, int | None], ...]
) -> tuple[list[tuple[str, int]], list[str]]:
    active = sorted(
        [(repo, count) for repo, count in commit_counts if count and count > 0],
        key=lambda item: item[1],
        reverse=True,
    )
    inactive = [repo for repo, count in commit_counts if count == 0]
    return active, inactive


def short_repo(repo: str) -> str:
    return repo.rsplit("/", maxsplit=1)[-1]


def format_server_metrics_for_report(metrics_text: str) -> list[str]:
    lines = []
    for line in metrics_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("disk:"):
            text = stripped.removeprefix("disk: ").replace("used ", "")
            text = text.replace("(free ", "（空き ").replace(")", "）")
            lines.append("- Disk: " + text + " 使用中")
        elif stripped.startswith("memory:"):
            text = stripped.removeprefix("memory: ").replace("available ", "")
            lines.append("- Memory: " + text + " 空き")
        elif stripped.startswith("load average:"):
            text = stripped.removeprefix("load average: ").replace(" ", " / ")
            lines.append("- Load: " + text)
        elif stripped:
            lines.append("- " + stripped)
    return lines or ["- unavailable"]
