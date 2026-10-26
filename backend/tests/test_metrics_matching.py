import math

import pytest
from conftest import actual, forecast, timestamp

from app.matching import coverage, index_records, match_hour
from app.metrics import calculate_metrics, distribution
from app.normalization import normalize


def hour(forecasts, actuals):
    f, _ = normalize(forecasts, "WINDFOR")
    a, _ = normalize(actuals, "FUELHH")
    return match_hour(
        timestamp("2026-01-02T00:00:00Z"), "11:00", index_records(f), index_records(a)
    )


def test_mean_of_both_actual_half_hours_and_bias_sign():
    result = hour([forecast(100)], [actual(80), actual(100, "2026-01-02T00:30:00Z")])
    assert result.actual_mw == 90
    assert result.error_mw == 10
    assert result.status == "matched"
    assert result.actual_settlement_period_count == 2


def test_incomplete_actual_hour_is_missing_not_partial_average():
    result = hour([forecast()], [actual(0)])
    assert result.actual_mw is None
    assert result.error_mw is None
    assert result.status == "missing_actual"
    report = coverage([result])
    assert report.available_actual_settlement_periods == 1
    assert report.missing_actual_settlement_periods == 1
    assert report.missing_actual_hours == 1
    assert report.matched_hours == 0


def test_missing_both_count_does_not_double_count_unmatched():
    report = coverage([hour([], [])])
    assert (
        report.missing_forecast_hours
        == report.missing_actual_hours
        == report.both_missing_hours
        == 1
    )
    assert report.unmatched_hours == 1


def test_invalid_latest_forecast_cannot_fall_back():
    result = hour([forecast(90, "2026-01-01T10:00:00Z"), forecast(-1)], [])
    assert result.status == "invalid"
    assert result.forecast_mw is None


def test_hand_calculated_metrics_and_exact_frequency():
    result = calculate_metrics([(100, 90), (100, 120), (0, 0), (None, 50)])
    assert result.mae_mw == 10
    assert result.rmse_mw == pytest.approx(math.sqrt(500 / 3))
    assert result.mean_bias_mw == pytest.approx(-10 / 3)
    assert result.wape_pct == pytest.approx(100 * 30 / 210)
    assert result.p90_absolute_error_mw == 18
    assert result.overforecast_hours == result.underforecast_hours == result.exact_hours == 1
    assert result.overforecast_pct == pytest.approx(100 / 3)


@pytest.mark.parametrize("forecast_value,expected", [(110, 10), (90, -10)])
def test_bias_direction(forecast_value, expected):
    result = calculate_metrics([(forecast_value, 100)])
    assert result.mean_bias_mw == expected


def test_zero_wape_denominator_is_undefined():
    result = calculate_metrics([(5, 0), (0, 0)])
    assert result.wape_pct is None
    assert result.wape_unavailable_reason == "zero_actual_denominator"
    assert result.matched_hours == 2


def test_no_pairs_has_null_metrics_and_frequencies():
    result = calculate_metrics([(None, 0), (0, None)])
    assert result.matched_hours == 0
    assert result.mae_mw is result.rmse_mw is result.mean_bias_mw is result.overforecast_pct is None
    assert result.wape_unavailable_reason == "no_matched_pairs"


def test_pooled_rmse_is_not_mean_of_daily_rmse():
    result = calculate_metrics([(0, 0), (20, 10)])
    assert result.rmse_mw == pytest.approx(math.sqrt(50))
    assert result.wape_pct == 100


def test_infinite_value_is_rejected():
    with pytest.raises(ValueError, match="finite"):
        calculate_metrics([(float("inf"), 1)])


def test_histogram_accounts_for_all_errors_including_edges():
    result = distribution([-20, -1, 0, 1, 20], bins=4)
    assert sum(item.count for item in result) == 5
    assert result[0].lower_mw == -20
    assert result[-1].upper_mw == 20 and result[-1].upper_inclusive
    assert distribution([]) == []
