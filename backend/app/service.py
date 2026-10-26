"""Application analytics over one immutable historical snapshot."""

from datetime import date, datetime, timedelta
from functools import lru_cache
from statistics import mean

from .config import ALIGNMENT, SCOPE
from .errors import WindScopeError
from .matching import coverage, index_records, match_hour
from .metrics import calculate_metrics, distribution
from .schemas import (
    AccuracyResponse,
    CoverageResponse,
    DailyResponse,
    DailySummary,
    DayResponse,
    HistoryResponse,
    Meta,
    OverviewResponse,
    Reliability,
    Revision,
    ScatterPoint,
    Snapshot,
)
from .selection import decision_cutoff, decision_date_for, delivery_grid, utc


def metrics_for(hours):
    return calculate_metrics([(hour.forecast_mw, hour.actual_mw) for hour in hours])


def available_mean(values):
    present = [value for value in values if value is not None]
    return mean(present) if present else None


class AnalyticsService:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.forecasts = index_records(snapshot.forecasts)
        self.actuals = index_records(snapshot.actuals)
        self.decision_dates = [
            snapshot.decision_start + timedelta(days=i)
            for i in range((snapshot.decision_end - snapshot.decision_start).days + 1)
        ]
        self.analysis = lru_cache(maxsize=16)(self._analysis)

    def meta(self, cutoff: str) -> Meta:
        snapshot = self.snapshot
        warnings = [
            "Accuracy and actual generation are retrospective.",
            "Forecast history is limited to the recorded publication window; "
            "global archive completeness is not guaranteed.",
            "Reliability before the pilot snapshot's earliest delivery cannot be assessed.",
        ]
        if snapshot.forecast_validation.invalid_rows or snapshot.actual_validation.invalid_rows:
            warnings.append("Invalid/conflicting records are retained as gaps; inspect coverage.")
        return Meta(
            snapshot_id=snapshot.snapshot_id,
            data_retrieved_at=max(s.retrieved_at for s in snapshot.sources),
            snapshot_built_at=snapshot.built_at,
            source_mode=snapshot.source_mode,
            decision_start=snapshot.decision_start,
            decision_end=snapshot.decision_end,
            delivery_start=snapshot.decision_start + timedelta(days=1),
            delivery_end=snapshot.decision_end + timedelta(days=1),
            cutoff_local=cutoff,
            alignment_assumption=ALIGNMENT,
            geographic_scope=SCOPE,
            history_completeness=snapshot.history_completeness,
            publication_from=snapshot.publication_from,
            publication_to=snapshot.publication_to,
            warnings=warnings,
        )

    def check_date(self, value: date):
        if not self.snapshot.decision_start <= value <= self.snapshot.decision_end:
            raise WindScopeError("out_of_scope", "Decision date must be in January 2026.", 404)

    def _analysis(self, cutoff: str):
        hours, days = [], []
        for decision in self.decision_dates:
            delivery = decision + timedelta(days=1)
            daily_hours = [
                match_hour(target, cutoff, self.forecasts, self.actuals)
                for target in delivery_grid(delivery)
            ]
            hours.extend(daily_hours)
            days.append(self.summarize(decision, cutoff, daily_hours))
        return hours, days

    @staticmethod
    def summarize(decision, cutoff, hours):
        return DailySummary(
            decision_date=decision,
            delivery_date=decision + timedelta(days=1),
            cutoff_utc=decision_cutoff(decision, cutoff),
            forecast_mean_mw=available_mean(h.forecast_mw for h in hours),
            actual_mean_mw=available_mean(h.actual_mw for h in hours),
            metrics=metrics_for(hours),
            coverage=coverage(hours),
        )

    def overview(self, cutoff: str):
        hours, _ = self.analysis(cutoff)
        return OverviewResponse(
            meta=self.meta(cutoff),
            metrics=metrics_for(hours),
            coverage=coverage(hours),
            available_decision_dates=self.decision_dates,
        )

    def day(self, decision: date, cutoff: str):
        self.check_date(decision)
        all_hours, days = self.analysis(cutoff)
        hours = [hour for hour in all_hours if hour.decision_date == decision]
        publications = [hour.selected_publish_time for hour in hours if hour.selected_publish_time]
        deadline = decision_cutoff(decision, cutoff)
        # Re-select actual revisions as of the requested decision, rather than reuse final outturns.
        earlier = [
            match_hour(h.start_time, cutoff, self.forecasts, self.actuals, actual_as_of=deadline)
            for h in all_hours
            if h.end_time <= deadline
        ]
        return DayResponse(
            meta=self.meta(cutoff),
            summary=next(d for d in days if d.decision_date == decision),
            hours=hours,
            selected_publication_from=min(publications, default=None),
            selected_publication_to=max(publications, default=None),
            historical_reliability=Reliability(as_of=deadline, metrics=metrics_for(earlier)),
        )

    def accuracy(self, cutoff: str):
        hours, days = self.analysis(cutoff)
        matched = [hour for hour in hours if hour.error_mw is not None]
        worst = sorted(
            (day for day in days if day.metrics.mae_mw is not None),
            key=lambda day: (-day.metrics.mae_mw, day.decision_date),
        )[:5]
        return AccuracyResponse(
            meta=self.meta(cutoff),
            metrics=metrics_for(hours),
            coverage=coverage(hours),
            error_distribution=distribution([hour.error_mw for hour in matched]),
            scatter=[
                ScatterPoint(
                    start_time=h.start_time,
                    forecast_mw=h.forecast_mw,
                    actual_mw=h.actual_mw,
                    error_mw=h.error_mw,
                )
                for h in matched
            ],
            worst_days=worst,
        )

    def daily(self, cutoff: str):
        return DailyResponse(meta=self.meta(cutoff), days=self.analysis(cutoff)[1])

    def coverage(self, cutoff: str):
        hours, days = self.analysis(cutoff)
        return CoverageResponse(
            meta=self.meta(cutoff),
            coverage=coverage(hours),
            days=days,
            forecast_validation=self.snapshot.forecast_validation,
            actual_validation=self.snapshot.actual_validation,
        )

    def history(self, target: datetime, cutoff: str):
        target = utc(target)
        self.check_date(decision_date_for(target))
        if target.minute or target.second or target.microsecond:
            raise WindScopeError(
                "invalid_interval", "Select an hourly delivery start timestamp.", 422
            )
        hour = match_hour(target, cutoff, self.forecasts, self.actuals)
        return HistoryResponse(
            meta=self.meta(cutoff),
            hour=hour,
            revisions=[
                Revision(
                    publish_time=r.publish_time,
                    forecast_mw=r.generation_mw,
                    eligible_at_cutoff=r.publish_time <= hour.cutoff_utc,
                    selected=r.publish_time == hour.selected_publish_time,
                    valid=r.valid,
                    invalid_reason=r.invalid_reason,
                )
                for r in sorted(self.forecasts.get(target, []), key=lambda r: r.publish_time)
            ],
        )
