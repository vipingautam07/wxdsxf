"""Source, snapshot and public API contracts. All power values are finite MW."""

import math
from datetime import date, datetime
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from .selection import utc


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SourceForecast(Model):
    dataset: Literal["WINDFOR"]
    publishTime: AwareDatetime
    startTime: AwareDatetime
    generation: float | None

    @field_validator("generation", mode="before")
    @classmethod
    def numeric_generation(cls, value):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("generation must be a finite JSON number or null")
        return value


class SourceActual(SourceForecast):
    dataset: Literal["FUELHH"]
    settlementDate: date
    settlementPeriod: int = Field(ge=1, le=50, strict=True)
    fuelType: str


class ForecastRecord(Model):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
    start_time: AwareDatetime
    publish_time: AwareDatetime
    generation_mw: float | None
    valid: bool = True
    invalid_reason: str | None = None

    @field_validator("start_time", "publish_time")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return utc(value)


class ActualRecord(ForecastRecord):
    settlement_date: date
    settlement_period: int = Field(ge=1, le=50)


class ValidationReport(Model):
    source_rows: int = 0
    normalized_rows: int = 0
    excluded_other_fuel: int = 0
    exact_duplicate_rows: int = 0
    conflicting_keys: int = 0
    negative_generation_rows: int = 0
    null_generation_rows: int = 0
    invalid_rows: int = 0


class Capture(Model):
    url: str
    retrieved_at: AwareDatetime
    sha256_uncompressed: str
    row_count: int
    raw_file: str | None = None


class Snapshot(Model):
    schema_version: Literal[1] = 1
    snapshot_id: str
    built_at: AwareDatetime
    decision_start: date
    decision_end: date
    source_mode: Literal["live_elexon", "verified_elexon_archive"]
    sources: list[Capture]
    history_completeness: Literal["bounded_publication_window"] = "bounded_publication_window"
    publication_from: AwareDatetime
    publication_to: AwareDatetime
    forecasts: list[ForecastRecord]
    actuals: list[ActualRecord]
    forecast_validation: ValidationReport
    actual_validation: ValidationReport


class Metrics(Model):
    matched_hours: int
    mae_mw: float | None
    rmse_mw: float | None
    mean_bias_mw: float | None
    wape_pct: float | None
    wape_unavailable_reason: str | None
    p90_absolute_error_mw: float | None
    overforecast_hours: int
    underforecast_hours: int
    exact_hours: int
    overforecast_pct: float | None
    underforecast_pct: float | None
    exact_pct: float | None


class Coverage(Model):
    expected_hours: int
    matched_hours: int
    unmatched_hours: int
    missing_forecast_hours: int
    missing_actual_hours: int
    both_missing_hours: int
    invalid_hours: int
    expected_actual_settlement_periods: int
    available_actual_settlement_periods: int
    missing_actual_settlement_periods: int
    settlement_periods_in_matched_hours: int
    matched_pct: float | None


class ActualPeriod(Model):
    start_time: AwareDatetime
    settlement_date: date
    settlement_period: int
    generation_mw: float | None
    publish_time: AwareDatetime | None
    valid: bool


class DeliveryHour(Model):
    start_time: AwareDatetime
    end_time: AwareDatetime
    decision_date: date
    cutoff_utc: AwareDatetime
    forecast_mw: float | None
    selected_publish_time: AwareDatetime | None
    actual_mw: float | None
    actual_periods: list[ActualPeriod]
    actual_settlement_period_count: int
    error_mw: float | None
    status: Literal["matched", "missing_forecast", "missing_actual", "missing_both", "invalid"]
    issues: list[str]


class DailySummary(Model):
    decision_date: date
    delivery_date: date
    cutoff_utc: AwareDatetime
    forecast_mean_mw: float | None
    actual_mean_mw: float | None
    metrics: Metrics
    coverage: Coverage


class Meta(Model):
    snapshot_id: str
    data_retrieved_at: AwareDatetime
    snapshot_built_at: AwareDatetime
    source_mode: str
    source_datasets: list[str] = ["FUELHH", "WINDFOR"]
    decision_start: date
    decision_end: date
    delivery_start: date
    delivery_end: date
    cutoff_local: str
    timezone: Literal["Europe/London"] = "Europe/London"
    evaluation_resolution: Literal["hourly"] = "hourly"
    alignment_assumption: str
    geographic_scope: str
    cutoff_assumption: str = "Pilot purchasing cutoff; not a verified market gate-closure rule."
    error_convention: str = "forecast minus actual; positive means overforecast"
    p90_method: str = "linear interpolation"
    history_completeness: str
    publication_from: AwareDatetime
    publication_to: AwareDatetime
    warnings: list[str]


class OverviewResponse(Model):
    meta: Meta
    metrics: Metrics
    coverage: Coverage
    available_decision_dates: list[date]


class Reliability(Model):
    as_of: AwareDatetime
    label: str = "Earlier deliveries with actual publications available by this decision cutoff"
    metrics: Metrics


class DayResponse(Model):
    meta: Meta
    summary: DailySummary
    hours: list[DeliveryHour]
    selected_publication_from: AwareDatetime | None
    selected_publication_to: AwareDatetime | None
    historical_reliability: Reliability


class HistogramBin(Model):
    lower_mw: float
    upper_mw: float
    upper_inclusive: bool
    count: int


class ScatterPoint(Model):
    start_time: AwareDatetime
    forecast_mw: float
    actual_mw: float
    error_mw: float


class AccuracyResponse(Model):
    meta: Meta
    metrics: Metrics
    coverage: Coverage
    error_distribution: list[HistogramBin]
    scatter: list[ScatterPoint]
    worst_days: list[DailySummary]


class DailyResponse(Model):
    meta: Meta
    days: list[DailySummary]


class Revision(Model):
    publish_time: AwareDatetime
    forecast_mw: float | None
    eligible_at_cutoff: bool
    selected: bool
    valid: bool
    invalid_reason: str | None


class HistoryResponse(Model):
    meta: Meta
    hour: DeliveryHour
    revisions: list[Revision]
    uncertainty_note: str = "Revision range describes published changes, not a confidence interval."


class CoverageResponse(Model):
    meta: Meta
    coverage: Coverage
    forecast_validation: ValidationReport
    actual_validation: ValidationReport
    days: list[DailySummary]


class HealthResponse(Model):
    status: Literal["ok", "degraded"]
    process_alive: bool = True
    snapshot_ready: bool
    snapshot_id: str | None = None
    data_retrieved_at: AwareDatetime | None = None
    validation_status: str
    issue: str | None = None


class ErrorDetail(Model):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(Model):
    error: ErrorDetail
