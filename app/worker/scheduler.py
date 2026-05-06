from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class WorkerSchedule:
    daily_hour: int
    daily_minute: int
    weekly_day: str
    weekly_hour: int
    weekly_minute: int
    timezone: str


def build_schedule(settings: Settings) -> WorkerSchedule:
    return WorkerSchedule(
        daily_hour=settings.daily_hour,
        daily_minute=settings.daily_minute,
        weekly_day=settings.weekly_day,
        weekly_hour=settings.weekly_hour,
        weekly_minute=settings.weekly_minute,
        timezone=settings.timezone,
    )
