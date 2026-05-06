from __future__ import annotations

from app.core.db import connect, run_migrations
from app.domains.jobs.service import record_job_run
from app.domains.reports.service import (
    build_daily_report,
    build_weekly_report,
    render_daily_report_text,
    render_weekly_report_text,
)
from app.metrics.server import ServerMetrics


class FakeGitHubClient:
    def __init__(self, mapping):
        self.mapping = mapping

    def list_commits(self, repo, *, since_iso=None, until_iso=None, **_):
        return list(self.mapping.get(repo, []))


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


def test_build_daily_report_renders_body(tmp_path):
    with connect(str(tmp_path / "r.db")) as conn:
        run_migrations(conn)
        _record(conn, "backup-life-db", "success", 0, "2026-05-05T01:00:00+00:00")
        _record(conn, "backup-life-db", "failed", 1, "2026-05-05T02:00:00+00:00")
        client = FakeGitHubClient(
            {"example-owner/life-bot": [{"sha": "a"}, {"sha": "b"}]}
        )
        metrics = ServerMetrics(disk=None, memory=None, load_average=None)
        report = build_daily_report(
            conn,
            github_client=client,
            repositories=("example-owner/life-bot",),
            metrics=metrics,
            target_date="2026-05-05",
        )
        assert report.target_date == "2026-05-05"
        assert report.job_total == 2
        assert report.job_success_rate == 0.5
        body = render_daily_report_text(report)
        assert "Server Report (daily) 2026-05-05" in body
        assert "example-owner/life-bot: 2" in body
        assert "ジョブ成功率: 50%" in body
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "report.daily.built" in types


def test_build_weekly_report_renders_body(tmp_path):
    with connect(str(tmp_path / "r.db")) as conn:
        run_migrations(conn)
        _record(conn, "backup-life-db", "success", 0, "2026-05-05T01:00:00+00:00")
        _record(conn, "deploy", "failed", 1, "2026-05-06T01:00:00+00:00")
        client = FakeGitHubClient(
            {
                "example-owner/life-bot": [{"sha": "a"}],
                "example-owner/ai-feed-bot": [],
            }
        )
        report = build_weekly_report(
            conn,
            github_client=client,
            repositories=(
                "example-owner/life-bot",
                "example-owner/ai-feed-bot",
            ),
            target_week_start="2026-05-04",
        )
        assert report.weekly_commit_count == 1
        assert "example-owner/life-bot" in report.active_repositories
        assert "example-owner/ai-feed-bot" not in report.active_repositories
        assert report.backup_success_count == 1
        body = render_weekly_report_text(report)
        assert "Server Report (weekly) since 2026-05-04" in body
        assert "weekly commit count: 1" in body
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "report.weekly.built" in types
