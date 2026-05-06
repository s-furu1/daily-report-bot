from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from typing import Callable, ContextManager, Iterator

from app.core.config import Settings
from app.core.db import connect, run_migrations
from app.core.time import utc_now
from app.domains.reports.service import build_daily_report, build_weekly_report
from app.github.client import GitHubClient
from app.github.repositories import resolve_repositories
from app.metrics.server import collect_server_metrics
from app.slack.handlers import (
    handle_report_github_show,
    handle_report_jobs_show,
    handle_report_today_show,
    handle_report_week_show,
)


@contextmanager
def _open_db(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        run_migrations(conn)
        yield conn
    finally:
        conn.close()


def post_alert(
    client_post: Callable[[str, str], None],
    channel_id: str | None,
    text: str,
) -> bool:
    if not channel_id:
        return False
    try:
        client_post(channel_id, text)
    except Exception:
        return False
    return True


def register_action_handlers(
    app,
    settings: Settings,
    *,
    today_report_factory: Callable[[sqlite3.Connection], object] | None = None,
    weekly_report_factory: Callable[[sqlite3.Connection], object] | None = None,
    db_context_factory: Callable[[], ContextManager[sqlite3.Connection]] | None = None,
) -> None:
    db_ctx = db_context_factory or (lambda: _open_db(settings.daily_report_db_path))

    def _default_today(conn: sqlite3.Connection):
        github_client = GitHubClient(settings.github_token)
        repositories = resolve_repositories(conn, github_client)
        target_date = utc_now().strftime("%Y-%m-%d")
        return build_daily_report(
            conn,
            github_client=github_client,
            repositories=repositories,
            metrics=collect_server_metrics(),
            target_date=target_date,
        )

    def _default_weekly(conn: sqlite3.Connection):
        github_client = GitHubClient(settings.github_token)
        repositories = resolve_repositories(conn, github_client)
        now = utc_now()
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        return build_weekly_report(
            conn,
            github_client=github_client,
            repositories=repositories,
            target_week_start=week_start,
        )

    today_factory = today_report_factory or _default_today
    weekly_factory = weekly_report_factory or _default_weekly

    def _on_today(ack, body=None):
        with db_ctx() as conn:
            handle_report_today_show(ack, lambda: today_factory(conn), conn)

    app.action("report.today.show")(_on_today)

    def _on_week(ack, body=None):
        with db_ctx() as conn:
            handle_report_week_show(ack, lambda: weekly_factory(conn), conn)

    app.action("report.week.show")(_on_week)

    def _on_jobs(ack, body=None):
        with db_ctx() as conn:
            handle_report_jobs_show(ack, conn)

    app.action("report.jobs.show")(_on_jobs)

    def _on_github(ack, body=None):
        with db_ctx() as conn:
            handle_report_github_show(ack, conn)

    app.action("report.github.show")(_on_github)


def start_slack_if_configured(settings: Settings) -> bool:
    missing = [
        name
        for name, value in {
            "SLACK_BOT_TOKEN": settings.slack_bot_token,
            "SLACK_APP_TOKEN": settings.slack_app_token,
            "SLACK_SIGNING_SECRET": settings.slack_signing_secret,
            "SLACK_CHANNEL_SERVER_REPORT": settings.slack_channel_server_report,
        }.items()
        if not value
    ]
    if missing:
        print(f"Slack disabled: missing {', '.join(missing)}")
        return False
    try:
        from slack_bolt import App
        from slack_bolt.adapter.socket_mode import SocketModeHandler
    except ImportError:
        print("Slack disabled: slack-bolt is not installed")
        return False

    app = App(
        token=settings.slack_bot_token,
        signing_secret=settings.slack_signing_secret,
    )

    register_action_handlers(app, settings)

    SocketModeHandler(app, settings.slack_app_token).start()
    return True


if __name__ == "__main__":
    from app.core.config import load_settings

    start_slack_if_configured(load_settings())
