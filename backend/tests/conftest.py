"""Small synthetic fixtures for tests only. Dashboard data always comes from Elexon."""

from datetime import UTC, datetime, timedelta

import pytest

from app.ingestion import build_snapshot
from app.schemas import Capture
from app.selection import LONDON, delivery_grid


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def forecast(generation=100, publish="2026-01-01T11:00:00Z", start="2026-01-02T00:00:00Z"):
    return {
        "dataset": "WINDFOR",
        "publishTime": publish,
        "startTime": start,
        "generation": generation,
    }


def actual(generation=90, start="2026-01-02T00:00:00Z", publish=None, fuel="WIND"):
    target = timestamp(start)
    day = target.astimezone(LONDON).date()
    return {
        "dataset": "FUELHH",
        "startTime": start,
        "publishTime": publish or (target + timedelta(minutes=30)).isoformat(),
        "generation": generation,
        "fuelType": fuel,
        "settlementDate": day.isoformat(),
        "settlementPeriod": delivery_grid(day, 30).index(target.astimezone(UTC)) + 1,
    }


@pytest.fixture
def small_snapshot():
    return build_snapshot(
        [forecast(95, "2026-01-01T09:30:00Z"), forecast(), forecast(200, "2026-01-01T11:01:00Z")],
        [actual(80), actual(100, "2026-01-02T00:30:00Z")],
        [
            Capture(
                url="https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream",
                retrieved_at="2026-10-26T00:00:00Z",
                sha256_uncompressed="test-fixture",
                row_count=3,
            )
        ],
        "verified_elexon_archive",
    )
