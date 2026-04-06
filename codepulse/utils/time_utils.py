"""Timestamp helpers."""
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def format_ts(dt: datetime) -> str:
    return dt.strftime("%H:%M:%S")
