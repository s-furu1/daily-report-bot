from __future__ import annotations

from datetime import UTC, datetime, timedelta


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def day_bounds_utc(date_str: str) -> tuple[str, str]:
    year, month, day = date_str.split("-")
    start = datetime(int(year), int(month), int(day), tzinfo=UTC)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def week_bounds_utc(week_start_date: str) -> tuple[str, str]:
    year, month, day = week_start_date.split("-")
    start = datetime(int(year), int(month), int(day), tzinfo=UTC)
    end = start + timedelta(days=7)
    return start.isoformat(), end.isoformat()
