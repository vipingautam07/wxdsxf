import pytest
from conftest import actual, forecast

from app.errors import DataValidationError
from app.normalization import normalize


def test_exact_duplicate_is_collapsed():
    rows, report = normalize([forecast(), forecast()], "WINDFOR")
    assert len(rows) == 1
    assert report.exact_duplicate_rows == 1
    assert report.conflicting_keys == 0


def test_conflicting_duplicate_is_quarantined_in_either_order():
    for source in ([forecast(), forecast(200)], [forecast(200), forecast()]):
        rows, report = normalize(source, "WINDFOR")
        assert len(rows) == 1
        assert not rows[0].valid
        assert rows[0].generation_mw is None
        assert report.conflicting_keys == 1


def test_actual_conflict_and_other_fuel_handling():
    rows, report = normalize([actual(), actual(100), actual(fuel="CCGT")], "FUELHH")
    assert len(rows) == 1 and not rows[0].valid
    assert report.excluded_other_fuel == 1


def test_negative_wind_is_flagged_and_zero_preserved():
    rows, report = normalize([forecast(-1), forecast(0, "2026-01-01T10:00:00Z")], "WINDFOR")
    assert report.negative_generation_rows == 1
    assert rows[0].valid and rows[0].generation_mw == 0
    assert not rows[1].valid and rows[1].generation_mw == -1


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "100"])
def test_non_numeric_or_non_finite_source_is_rejected(value):
    with pytest.raises(DataValidationError):
        normalize([forecast(value)], "WINDFOR")


def test_settlement_metadata_consistency():
    row = actual()
    row["settlementPeriod"] = 2
    with pytest.raises(DataValidationError, match="failed validation"):
        normalize([row], "FUELHH")


@pytest.mark.parametrize(
    "change",
    [
        {"startTime": "2026-01-02T00:30:00Z"},
        {"publishTime": "2026-01-01T11:00:00"},
        {"dataset": "FUELINST"},
        {"unexpected": 1},
    ],
)
def test_schema_and_grid_changes_are_rejected(change):
    with pytest.raises(DataValidationError):
        normalize([forecast() | change], "WINDFOR")


def test_actual_publication_cannot_precede_period_completion():
    with pytest.raises(DataValidationError):
        normalize([actual(publish="2026-01-02T00:29:00Z")], "FUELHH")
