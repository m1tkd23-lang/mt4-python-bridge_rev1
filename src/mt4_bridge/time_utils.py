# src\mt4_bridge\time_utils.py
from __future__ import annotations

from datetime import datetime


MT4_DATETIME_FORMAT = "%Y.%m.%d %H:%M:%S"


def parse_mt4_datetime(value: str) -> datetime:
    return datetime.strptime(value, MT4_DATETIME_FORMAT)


def age_seconds(reference: datetime, target: datetime) -> float:
    return (reference - target).total_seconds()


def is_stale(reference: datetime, target: datetime, threshold_seconds: int) -> bool:
    return age_seconds(reference, target) > threshold_seconds