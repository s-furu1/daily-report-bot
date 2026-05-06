from __future__ import annotations

import sqlite3
from typing import Callable

from app.domains.events.service import record_event


def run_daily_report_job(
    build_daily: Callable[[], object],
    notify: Callable[[object], None] | None = None,
) -> object:
    report = build_daily()
    if notify is not None:
        notify(report)
    return report


def run_weekly_report_job(
    build_weekly: Callable[[], object],
    notify: Callable[[object], None] | None = None,
) -> object:
    report = build_weekly()
    if notify is not None:
        notify(report)
    return report


def run_job_summary_job(
    conn: sqlite3.Connection,
    summarize: Callable[[], dict],
) -> dict:
    summary = summarize()
    record_event(
        conn,
        "job.summary.built",
        "worker",
        {"summary_keys": sorted(summary.keys())},
    )
    return summary


def run_notification_job(
    conn: sqlite3.Connection,
    notify: Callable[[], None],
) -> bool:
    try:
        notify()
    except Exception as exc:
        record_event(
            conn,
            "notification.failed",
            "worker",
            {"error": str(exc)},
        )
        return False
    record_event(conn, "notification.sent", "worker", {})
    return True
