"""Validate official stream records; retain conflicts as unusable revisions."""

from datetime import timedelta

from pydantic import ValidationError

from .errors import DataValidationError
from .schemas import ActualRecord, ForecastRecord, SourceActual, SourceForecast, ValidationReport
from .selection import LONDON, delivery_grid, utc


def deduplicate[Record: (ForecastRecord, ActualRecord)](
    records: list[Record], report: ValidationReport
) -> list[Record]:
    groups: dict[tuple, list[Record]] = {}
    for row in records:
        groups.setdefault((row.start_time, row.publish_time), []).append(row)
    result = []
    for group in groups.values():
        unique = {row.model_dump_json(): row for row in group}
        report.exact_duplicate_rows += len(group) - len(unique)
        row = next(iter(unique.values()))
        if len(unique) > 1:
            report.conflicting_keys += 1
            row = row.model_copy(
                update={
                    "valid": False,
                    "generation_mw": None,
                    "invalid_reason": "conflicting_duplicate",
                }
            )
        result.append(row)
    result.sort(key=lambda row: (row.start_time, row.publish_time))
    report.normalized_rows = len(result)
    report.invalid_rows = sum(not row.valid for row in result)
    return result


def normalize(rows: list[dict], dataset: str):
    report = ValidationReport(source_rows=len(rows))
    records = []
    for number, raw in enumerate(rows):
        try:
            source = (SourceActual if dataset == "FUELHH" else SourceForecast).model_validate(raw)
            if dataset == "FUELHH" and source.fuelType != "WIND":
                report.excluded_other_fuel += 1
                continue
            start, publish = utc(source.startTime), utc(source.publishTime)
            step = 30 if dataset == "FUELHH" else 60
            if start.second or start.microsecond or start.minute % step:
                raise ValueError(f"Target timestamp must align to {step}-minute UTC grid")
            value = source.generation
            report.null_generation_rows += value is None
            negative = value is not None and value < 0
            report.negative_generation_rows += negative
            fields = dict(
                start_time=start,
                publish_time=publish,
                generation_mw=value,
                valid=not negative,
                invalid_reason="negative_wind_generation" if negative else None,
            )
            if dataset == "FUELHH":
                local_date = start.astimezone(LONDON).date()
                expected = delivery_grid(local_date, 30)
                if (
                    source.settlementDate != local_date
                    or expected[source.settlementPeriod - 1] != start
                ):
                    raise ValueError(
                        "Settlement date/period does not match startTime in Europe/London"
                    )
                if publish < start + timedelta(minutes=30):
                    raise ValueError(
                        "Actual publication precedes completion of its settlement period"
                    )
                records.append(
                    ActualRecord(
                        **fields,
                        settlement_date=source.settlementDate,
                        settlement_period=source.settlementPeriod,
                    )
                )
            else:
                records.append(ForecastRecord(**fields))
        except (ValidationError, ValueError, IndexError) as exc:
            raise DataValidationError(
                f"{dataset} row {number} failed validation.", {"row": number, "reason": str(exc)}
            ) from exc
    return deduplicate(records, report), report
