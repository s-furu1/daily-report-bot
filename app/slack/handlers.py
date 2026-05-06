from __future__ import annotations

from typing import Any, Callable

from app.domains.events.service import record_event


Ack = Callable[[], None]


def handle_report_today_show(
    ack: Ack, build_today: Callable[[], Any], conn
) -> Any:
    ack()
    report = build_today()
    record_event(
        conn,
        "slack.report.today.show",
        "slack",
        {"target_date": getattr(report, "target_date", None)},
    )
    return report


def handle_report_week_show(
    ack: Ack, build_weekly: Callable[[], Any], conn
) -> Any:
    ack()
    report = build_weekly()
    record_event(
        conn,
        "slack.report.week.show",
        "slack",
        {"target_week_start": getattr(report, "target_week_start", None)},
    )
    return report


def handle_report_jobs_show(ack: Ack, conn) -> None:
    ack()
    record_event(conn, "slack.report.jobs.show", "slack", {})


def handle_report_github_show(ack: Ack, conn) -> None:
    ack()
    record_event(conn, "slack.report.github.show", "slack", {})
