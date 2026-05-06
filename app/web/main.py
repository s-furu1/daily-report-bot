from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator

from fastapi import FastAPI

from app.core.config import load_settings
from app.core.db import connect, run_migrations
from app.core.time import utc_now
from app.domains.jobs import repository as jobs_repository
from app.domains.reports.service import (
    build_daily_report,
    build_weekly_report,
    render_daily_report_text,
    render_weekly_report_text,
)
from app.github.client import GitHubClient
from app.github.repositories import resolve_repositories
from app.metrics.server import collect_server_metrics


@contextmanager
def open_db() -> Iterator[sqlite3.Connection]:
    settings = load_settings()
    conn = connect(settings.daily_report_db_path)
    try:
        run_migrations(conn)
        yield conn
    finally:
        conn.close()


def create_app() -> FastAPI:
    app = FastAPI(title="daily-report-bot internal API")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/internal/reports/today")
    def today_report() -> dict:
        settings = load_settings()
        with open_db() as conn:
            github_client = GitHubClient(settings.github_token)
            repositories = resolve_repositories(conn, github_client)
            target_date = utc_now().strftime("%Y-%m-%d")
            report = build_daily_report(
                conn,
                github_client=github_client,
                repositories=repositories,
                metrics=collect_server_metrics(),
                target_date=target_date,
            )
            return {
                "ok": True,
                "target_date": report.target_date,
                "text": render_daily_report_text(report),
                "github": _github_status(settings.github_token, repositories),
            }

    @app.get("/internal/reports/week")
    def week_report() -> dict:
        settings = load_settings()
        with open_db() as conn:
            github_client = GitHubClient(settings.github_token)
            repositories = resolve_repositories(conn, github_client)
            now = utc_now()
            week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
            report = build_weekly_report(
                conn,
                github_client=github_client,
                repositories=repositories,
                target_week_start=week_start,
            )
            return {
                "ok": True,
                "target_week_start": report.target_week_start,
                "text": render_weekly_report_text(report),
                "github": _github_status(settings.github_token, repositories),
            }

    @app.get("/internal/reports/jobs")
    def jobs_report() -> dict:
        with open_db() as conn:
            rows = conn.execute(
                "SELECT * FROM job_runs ORDER BY id DESC LIMIT 10"
            ).fetchall()
            runs = [jobs_repository._row_to_job_run(row) for row in rows]
            return {
                "ok": True,
                "jobs": [
                    {
                        "id": run.id,
                        "job_name": run.job_name,
                        "status": run.status,
                        "exit_code": run.exit_code,
                        "started_at": run.started_at,
                        "finished_at": run.finished_at,
                    }
                    for run in runs
                ],
                "text": _jobs_text(runs),
            }

    @app.get("/internal/reports/github")
    def github_report() -> dict:
        settings = load_settings()
        with open_db() as conn:
            github_client = GitHubClient(settings.github_token)
            repositories = resolve_repositories(conn, github_client)
            status = _github_status(settings.github_token, repositories)
            return {
                "ok": True,
                "github": status,
                "repositories": list(repositories),
                "text": _github_text(status, repositories),
            }

    return app


def _github_status(token: str | None, repositories: tuple[str, ...]) -> dict:
    if not token:
        return {"status": "skipped", "reason": "GITHUB_TOKEN is not set"}
    if not repositories:
        return {"status": "failed", "reason": "no repositories resolved"}
    return {"status": "ok", "repository_count": len(repositories)}


def _jobs_text(runs) -> str:
    if not runs:
        return "ジョブ履歴はありません。"
    lines = ["ジョブ状況"]
    for run in runs[:10]:
        lines.append(f"- {run.job_name}: {run.status}")
    return "\n".join(lines)


def _github_text(status: dict, repositories: tuple[str, ...]) -> str:
    if status["status"] == "ok":
        return "GitHub repositories: " + ", ".join(repositories[:10])
    return f"GitHub {status['status']}: {status['reason']}"


app = create_app()


def main() -> None:
    import uvicorn

    settings = load_settings()
    uvicorn.run("app.web.main:app", host=settings.web_host, port=settings.web_port)
