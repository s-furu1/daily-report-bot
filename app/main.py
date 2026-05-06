from __future__ import annotations

from app.core.config import load_settings
from app.core.db import connect, run_migrations
from app.domains.events.service import record_event
from app.worker.main import start_worker_if_enabled


def main() -> int:
    settings = load_settings()
    with connect(settings.daily_report_db_path) as conn:
        run_migrations(conn)
        record_event(conn, "app.started", "app", {"env": settings.app_env})

    print("daily-report-bot started")

    if settings.enable_slack:
        from app.slack.main import start_slack_if_configured

        start_slack_if_configured(settings)

    start_worker_if_enabled(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
