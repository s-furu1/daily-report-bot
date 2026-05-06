from __future__ import annotations

from app.core.config import Settings
from app.worker.scheduler import build_schedule


def start_worker_if_enabled(settings: Settings) -> bool:
    if not settings.enable_worker:
        return False
    schedule = build_schedule(settings)
    print(
        "daily-report worker enabled: "
        f"daily {schedule.daily_hour:02d}:{schedule.daily_minute:02d}, "
        f"weekly {schedule.weekly_day} "
        f"{schedule.weekly_hour:02d}:{schedule.weekly_minute:02d}, "
        f"tz={schedule.timezone}"
    )
    return True
