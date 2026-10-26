from collections import defaultdict
from datetime import datetime, timedelta

from .schemas import ActualPeriod, ActualRecord, Coverage, DeliveryHour, ForecastRecord
from .selection import LONDON, decision_cutoff, decision_date_for, delivery_grid, latest_at


def index_records(records):
    index = defaultdict(list)
    for record in records:
        index[record.start_time].append(record)
    return dict(index)


def usable(record) -> bool:
    return record is not None and record.valid and record.generation_mw is not None


def match_hour(
    target: datetime,
    cutoff: str,
    forecasts: dict[datetime, list[ForecastRecord]],
    actuals: dict[datetime, list[ActualRecord]],
    actual_as_of: datetime | None = None,
) -> DeliveryHour:
    decision = decision_date_for(target)
    deadline = decision_cutoff(decision, cutoff)
    forecast = latest_at(forecasts.get(target, []), deadline)
    periods, issues = [], []
    for offset in (0, 30):
        start = target + timedelta(minutes=offset)
        actual = latest_at(actuals.get(start, []), actual_as_of)
        local_date = start.astimezone(LONDON).date()
        period_number = delivery_grid(local_date, 30).index(start) + 1
        periods.append(
            ActualPeriod(
                start_time=start,
                settlement_date=local_date,
                settlement_period=period_number,
                generation_mw=actual.generation_mw if usable(actual) else None,
                publish_time=actual.publish_time if actual else None,
                valid=actual.valid if actual else False,
            )
        )
        if actual is not None and not actual.valid:
            issues.append(f"actual_{offset}: {actual.invalid_reason}")
    if forecast is not None and not forecast.valid:
        issues.append(f"forecast: {forecast.invalid_reason}")
    count = sum(p.generation_mw is not None for p in periods)
    actual_mw = sum(p.generation_mw for p in periods) / 2 if count == 2 else None
    forecast_mw = forecast.generation_mw if usable(forecast) else None
    if issues:
        status = "invalid"
    elif forecast_mw is None and actual_mw is None:
        status = "missing_both"
    elif forecast_mw is None:
        status = "missing_forecast"
    elif actual_mw is None:
        status = "missing_actual"
    else:
        status = "matched"
    return DeliveryHour(
        start_time=target,
        end_time=target + timedelta(hours=1),
        decision_date=decision,
        cutoff_utc=deadline,
        forecast_mw=forecast_mw,
        selected_publish_time=forecast.publish_time if forecast else None,
        actual_mw=actual_mw,
        actual_periods=periods,
        actual_settlement_period_count=count,
        error_mw=forecast_mw - actual_mw
        if forecast_mw is not None and actual_mw is not None
        else None,
        status=status,
        issues=issues,
    )


def coverage(hours: list[DeliveryHour]) -> Coverage:
    matched = sum(hour.error_mw is not None for hour in hours)
    missing_forecast = sum(hour.forecast_mw is None for hour in hours)
    missing_actual = sum(hour.actual_mw is None for hour in hours)
    periods = sum(hour.actual_settlement_period_count for hour in hours)
    return Coverage(
        expected_hours=len(hours),
        matched_hours=matched,
        unmatched_hours=len(hours) - matched,
        missing_forecast_hours=missing_forecast,
        missing_actual_hours=missing_actual,
        both_missing_hours=sum(h.forecast_mw is None and h.actual_mw is None for h in hours),
        invalid_hours=sum(h.status == "invalid" for h in hours),
        expected_actual_settlement_periods=2 * len(hours),
        available_actual_settlement_periods=periods,
        missing_actual_settlement_periods=2 * len(hours) - periods,
        settlement_periods_in_matched_hours=2 * matched,
        matched_pct=100 * matched / len(hours) if hours else None,
    )
