from __future__ import annotations

from app.core.config import load_settings
from app.core.db import connect, run_migrations
from app.worker.jobs import (
    run_daily_report_job,
    run_job_summary_job,
    run_notification_job,
    run_weekly_report_job,
)
from app.worker.main import start_worker_if_enabled
from app.worker.scheduler import build_schedule


def test_worker_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DAILY_REPORT_ENABLE_WORKER", raising=False)
    settings = load_settings()
    assert start_worker_if_enabled(settings) is False


def test_worker_enabled_builds_schedule(monkeypatch):
    monkeypatch.setenv("DAILY_REPORT_ENABLE_WORKER", "true")
    monkeypatch.setenv("DAILY_REPORT_DAILY_HOUR", "9")
    monkeypatch.setenv("DAILY_REPORT_DAILY_MINUTE", "30")
    monkeypatch.setenv("DAILY_REPORT_WEEKLY_DAY", "MON")
    settings = load_settings()
    schedule = build_schedule(settings)
    assert schedule.daily_hour == 9
    assert schedule.daily_minute == 30
    assert schedule.weekly_day == "MON"
    assert start_worker_if_enabled(settings) is True


def test_run_daily_report_job_invokes_builder_and_notifier():
    notified: list[object] = []
    report = run_daily_report_job(
        lambda: "daily-report",
        notify=lambda r: notified.append(r),
    )
    assert report == "daily-report"
    assert notified == ["daily-report"]


def test_run_weekly_report_job_invokes_builder_and_notifier():
    notified: list[object] = []
    report = run_weekly_report_job(
        lambda: "weekly-report",
        notify=lambda r: notified.append(r),
    )
    assert report == "weekly-report"
    assert notified == ["weekly-report"]


def test_run_job_summary_records_event(tmp_path):
    with connect(str(tmp_path / "n.db")) as conn:
        run_migrations(conn)
        summary = run_job_summary_job(conn, lambda: {"success": 3, "failed": 1})
        assert summary == {"success": 3, "failed": 1}
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "job.summary.built" in types


def test_notification_job_failure_does_not_raise(tmp_path):
    with connect(str(tmp_path / "n.db")) as conn:
        run_migrations(conn)

        def failing():
            raise RuntimeError("slack down")

        assert run_notification_job(conn, failing) is False
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "notification.failed" in types


def test_notification_job_success_records_event(tmp_path):
    with connect(str(tmp_path / "n.db")) as conn:
        run_migrations(conn)
        assert run_notification_job(conn, lambda: None) is True
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "notification.sent" in types
