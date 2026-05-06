from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_level: str
    daily_report_db_path: str
    enable_slack: bool
    enable_worker: bool
    timezone: str
    daily_hour: int
    daily_minute: int
    weekly_day: str
    weekly_hour: int
    weekly_minute: int
    github_token: str | None
    slack_bot_token: str | None
    slack_app_token: str | None
    slack_signing_secret: str | None
    slack_channel_server_report: str | None
    slack_channel_server_alert: str | None


def load_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        daily_report_db_path=os.getenv("DAILY_REPORT_DB_PATH", "/data/daily-report.db"),
        enable_slack=_env_bool("DAILY_REPORT_ENABLE_SLACK", False),
        enable_worker=_env_bool("DAILY_REPORT_ENABLE_WORKER", False),
        timezone=os.getenv("DAILY_REPORT_TIMEZONE", "Asia/Tokyo"),
        daily_hour=_env_int("DAILY_REPORT_DAILY_HOUR", 8),
        daily_minute=_env_int("DAILY_REPORT_DAILY_MINUTE", 0),
        weekly_day=os.getenv("DAILY_REPORT_WEEKLY_DAY", "MON").strip().upper(),
        weekly_hour=_env_int("DAILY_REPORT_WEEKLY_HOUR", 8),
        weekly_minute=_env_int("DAILY_REPORT_WEEKLY_MINUTE", 15),
        github_token=os.getenv("GITHUB_TOKEN") or None,
        slack_bot_token=os.getenv("SLACK_BOT_TOKEN") or None,
        slack_app_token=os.getenv("SLACK_APP_TOKEN") or None,
        slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET") or None,
        slack_channel_server_report=os.getenv("SLACK_CHANNEL_SERVER_REPORT") or None,
        slack_channel_server_alert=os.getenv("SLACK_CHANNEL_SERVER_ALERT") or None,
    )
