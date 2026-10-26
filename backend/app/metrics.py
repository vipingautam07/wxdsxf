"""Pure, deterministic analytics. No rounding until display."""

import math

import numpy as np
import pandas as pd

from .schemas import HistogramBin, Metrics


def calculate_metrics(pairs: list[tuple[float | None, float | None]]) -> Metrics:
    if any(value is not None and not math.isfinite(value) for pair in pairs for value in pair):
        raise ValueError("Metrics require finite MW values.")
    frame = pd.DataFrame(pairs, columns=["forecast", "actual"], dtype=float).dropna()
    if not np.isfinite(frame.to_numpy()).all():
        raise ValueError("Metrics require finite MW values.")
    errors = frame.forecast - frame.actual
    n = len(errors)
    denominator = float(frame.actual.abs().sum())
    over, under, exact = (
        int((errors > 0).sum()),
        int((errors < 0).sum()),
        int((errors == 0).sum()),
    )
    return Metrics(
        matched_hours=n,
        mae_mw=float(errors.abs().mean()) if n else None,
        rmse_mw=float(np.sqrt((errors**2).mean())) if n else None,
        mean_bias_mw=float(errors.mean()) if n else None,
        wape_pct=100 * float(errors.abs().sum()) / denominator if n and denominator else None,
        wape_unavailable_reason="no_matched_pairs"
        if not n
        else ("zero_actual_denominator" if not denominator else None),
        p90_absolute_error_mw=float(errors.abs().quantile(0.9, interpolation="linear"))
        if n
        else None,
        overforecast_hours=over,
        underforecast_hours=under,
        exact_hours=exact,
        overforecast_pct=100 * over / n if n else None,
        underforecast_pct=100 * under / n if n else None,
        exact_pct=100 * exact / n if n else None,
    )


def distribution(errors: list[float], bins: int = 12) -> list[HistogramBin]:
    if not errors:
        return []
    counts, edges = np.histogram(errors, bins=bins)
    return [
        HistogramBin(
            lower_mw=float(edges[i]),
            upper_mw=float(edges[i + 1]),
            upper_inclusive=i == len(counts) - 1,
            count=int(count),
        )
        for i, count in enumerate(counts)
    ]
