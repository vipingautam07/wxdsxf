from datetime import UTC, date, datetime

import pytest
from conftest import forecast

from app.errors import WindScopeError
from app.normalization import normalize
from app.selection import decision_cutoff, decision_date_for, delivery_grid, latest_at, utc


@pytest.mark.parametrize("cutoff,expected", [("10:59", 90), ("11:00", 100), ("11:01", 200)])
def test_latest_eligible_revision_including_equality(cutoff, expected):
    rows, _ = normalize(
        [forecast(200, "2026-01-01T11:01:00Z"), forecast(), forecast(90, "2026-01-01T10:00:00Z")],
        "WINDFOR",
    )
    selected = latest_at(rows, decision_cutoff(date(2026, 1, 1), cutoff))
    assert selected.generation_mw == expected


def test_no_eligible_forecast():
    rows, _ = normalize([forecast()], "WINDFOR")
    assert latest_at(rows, decision_cutoff(date(2026, 1, 1), "10:59")) is None


def test_latest_null_is_not_replaced_with_older_value():
    rows, _ = normalize([forecast(80, "2026-01-01T10:00:00Z"), forecast(None)], "WINDFOR")
    selected = latest_at(rows, decision_cutoff(date(2026, 1, 1)))
    assert selected.generation_mw is None
    assert selected.publish_time.hour == 11


def test_utc_normalization_and_naive_rejection():
    rows, _ = normalize([forecast(publish="2026-01-01T12:00:00+01:00")], "WINDFOR")
    assert rows[0].publish_time == datetime(2026, 1, 1, 11, tzinfo=UTC)
    with pytest.raises(ValueError, match="offset"):
        utc(datetime(2026, 1, 1))


@pytest.mark.parametrize("day,hour", [(date(2026, 1, 1), 11), (date(2026, 7, 1), 10)])
def test_cutoff_uses_uk_timezone(day, hour):
    assert decision_cutoff(day).hour == hour


@pytest.mark.parametrize("day,count", [(date(2026, 3, 29), 46), (date(2026, 10, 25), 50)])
def test_dst_delivery_grid(day, count):
    grid = delivery_grid(day, 30)
    assert len(grid) == count
    assert len(set(grid)) == count


@pytest.mark.parametrize("day", [date(2026, 3, 29), date(2026, 10, 25)])
def test_nonexistent_or_ambiguous_local_cutoff_rejected(day):
    with pytest.raises(WindScopeError, match="ambiguous or nonexistent"):
        decision_cutoff(day, "01:30")


def test_decision_date_is_prior_local_calendar_day():
    assert decision_date_for(datetime(2026, 7, 1, 23, tzinfo=UTC)) == date(2026, 7, 1)


@pytest.mark.parametrize("value", ["24:00", "9:00", "11:60", "11:00:00", "abc"])
def test_invalid_cutoff(value):
    with pytest.raises(WindScopeError):
        decision_cutoff(date(2026, 1, 1), value)
