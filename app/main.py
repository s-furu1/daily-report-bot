from __future__ import annotations

import signal
import threading

from app.core.config import load_settings
from app.core.db import connect, run_migrations
from app.domains.events.service import record_event
from app.worker.main import start_worker_if_enabled


def wait_forever() -> None:
    stop_event = threading.Event()

    def _request_stop(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)
    stop_event.wait()


def main() -> int:
    settings = load_settings()
    with connect(settings.daily_report_db_path) as conn:
        run_migrations(conn)
        record_event(conn, "app.started", "app", {"env": settings.app_env})

    print("daily-report-bot started")

    started = False
    if settings.enable_slack:
        from app.slack.main import start_slack_if_configured

        started = start_slack_if_configured(settings) or started

    started = start_worker_if_enabled(settings) or started
    if started:
        wait_forever()
    else:
        print(
            "daily-report-bot stopped: both DAILY_REPORT_ENABLE_SLACK and "
            "DAILY_REPORT_ENABLE_WORKER are disabled or unavailable"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
