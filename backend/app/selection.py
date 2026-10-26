"""Timezone and exact-target publication selection, independent of HTTP and storage."""

import re
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, TypeVar
from zoneinfo import ZoneInfo

from .errors import WindScopeError

if TYPE_CHECKING:
    from .schemas import ActualRecord, ForecastRecord

LONDON = ZoneInfo("Europe/London")
Record = TypeVar("Record", "ForecastRecord", "ActualRecord")


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must contain a UTC offset or Z.")
    return value.astimezone(UTC)


def parse_cutoff(value: str) -> time:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise WindScopeError("invalid_cutoff", "Cutoff must be HH:MM in UK local time.", 422)
    return time.fromisoformat(value)


def decision_cutoff(decision_date: date, cutoff: str = "11:00") -> datetime:
    naive = datetime.combine(decision_date, parse_cutoff(cutoff))
    candidates = set()
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=LONDON, fold=fold).astimezone(UTC)
        if candidate.astimezone(LONDON).replace(tzinfo=None) == naive:
            candidates.add(candidate)
    if len(candidates) != 1:
        raise WindScopeError(
            "invalid_local_time", "Cutoff is ambiguous or nonexistent in Europe/London.", 422
        )
    return candidates.pop()


def decision_date_for(target: datetime) -> date:
    return utc(target).astimezone(LONDON).date() - timedelta(days=1)


def delivery_grid(delivery_date: date, minutes: int = 60) -> list[datetime]:
    start = datetime.combine(delivery_date, time(), tzinfo=LONDON).astimezone(UTC)
    end = datetime.combine(delivery_date + timedelta(days=1), time(), tzinfo=LONDON).astimezone(UTC)
    count = int((end - start).total_seconds() / (60 * minutes))
    return [start + timedelta(minutes=minutes * i) for i in range(count)]


def latest_at(  # noqa: UP047 -- Forward references avoid the selection/schema import cycle.
    records: list[Record] | tuple[Record, ...], cutoff: datetime | None = None
) -> Record | None:
    """Keep null/invalid latest records: never silently fall back to an older good value."""
    eligible = records if cutoff is None else [r for r in records if r.publish_time <= utc(cutoff)]
    return max(eligible, key=lambda record: record.publish_time, default=None)
