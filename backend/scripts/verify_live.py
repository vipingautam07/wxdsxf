"""Verify real HTTP endpoints and independently recompute metrics from the source snapshot.

Run with a local API already started: python scripts/verify_live.py
This performs no ingestion and makes no requests to external data services.
"""

import argparse
import gzip
import json
import math
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


def require_allowed_origin(response: httpx.Response, origin: str) -> None:
    if response.headers.get("access-control-allow-origin") != origin:
        raise AssertionError(
            f"CORS did not allow {origin} on {response.request.url}. "
            "Set CORS_ORIGINS on the backend project and redeploy it."
        )


def verify(base_url: str, output: Path | None = None, origin: str | None = None):
    paths = [
        "/api/health",
        "/api/overview",
        "/api/day?date=2026-01-15",
        "/api/accuracy",
        "/api/accuracy/daily",
        "/api/forecast-history?start_time=2026-01-16T12:00:00Z",
        "/api/coverage",
    ]
    checks, responses = [], {}
    with httpx.Client(timeout=15, headers={"Origin": origin} if origin else {}) as client:
        if origin:
            preflight = client.options(
                base_url + "/api/day",
                headers={"Access-Control-Request-Method": "GET"},
            )
            require_allowed_origin(preflight, origin)
            preflight.raise_for_status()
        for path in paths:
            start = time.perf_counter()
            response = client.get(base_url + path)
            elapsed = time.perf_counter() - start
            response.raise_for_status()
            if origin:
                require_allowed_origin(response, origin)
            responses[path] = response.json()
            checks.append(
                {
                    "path": path,
                    "status": response.status_code,
                    "elapsed_ms": round(elapsed * 1000, 2),
                }
            )
        accuracy = responses["/api/accuracy"]
        coverage = responses["/api/coverage"]["coverage"]
        assert coverage["matched_hours"] == 744
        assert coverage["missing_actual_settlement_periods"] == 0
        assert sum(item["count"] for item in accuracy["error_distribution"]) == 744
        history = responses[paths[5]]
        assert sum(row["selected"] for row in history["revisions"]) == 1
        assert all(
            not row["selected"] for row in history["revisions"] if not row["eligible_at_cutoff"]
        )
        first = client.get(base_url + "/api/day", params={"date": "2026-01-01"}).json()
        assert first["hours"][0]["forecast_mw"] == 18699
        assert first["historical_reliability"]["metrics"]["matched_hours"] == 0

    data = json.loads(
        gzip.decompress((ROOT / "backend/data/processed/snapshot.json.gz").read_bytes())
    )
    assert data["snapshot_id"] == accuracy["meta"]["snapshot_id"]

    def parse(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    actuals, candidates = {}, {}
    for row in data["actuals"]:
        target = parse(row["start_time"])
        if target not in actuals or row["publish_time"] > actuals[target]["publish_time"]:
            actuals[target] = row
    for row in data["forecasts"]:
        target = parse(row["start_time"])
        if not datetime(2026, 1, 2, tzinfo=UTC) <= target < datetime(2026, 2, 2, tzinfo=UTC):
            continue
        # January is GMT. This independent check deliberately uses no application functions.
        cutoff = (target - timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
        if parse(row["publish_time"]) <= cutoff and (
            target not in candidates or row["publish_time"] > candidates[target]["publish_time"]
        ):
            candidates[target] = row
    errors, outturn = [], []
    for target, row in candidates.items():
        actual = statistics.mean(
            [
                actuals[target]["generation_mw"],
                actuals[target + timedelta(minutes=30)]["generation_mw"],
            ]
        )
        errors.append(row["generation_mw"] - actual)
        outturn.append(actual)
    n = len(errors)
    ordered = sorted(abs(error) for error in errors)
    rank = 0.9 * (n - 1)
    low = int(rank)
    independent = {
        "matched_hours": n,
        "mae_mw": statistics.mean(abs(error) for error in errors),
        "rmse_mw": math.sqrt(statistics.mean(error * error for error in errors)),
        "mean_bias_mw": statistics.mean(errors),
        "wape_pct": 100
        * sum(abs(error) for error in errors)
        / sum(abs(value) for value in outturn),
        "p90_absolute_error_mw": ordered[low] + (ordered[low + 1] - ordered[low]) * (rank - low),
        "overforecast_pct": 100 * sum(error > 0 for error in errors) / n,
        "underforecast_pct": 100 * sum(error < 0 for error in errors) / n,
    }
    for key, value in independent.items():
        assert math.isclose(value, accuracy["metrics"][key], rel_tol=1e-12), key
    report = {
        "base_url": base_url,
        "cors_origin_checked": origin,
        "verified_at": datetime.now(UTC).isoformat(),
        "snapshot_id": data["snapshot_id"],
        "source_mode": data["source_mode"],
        "source_request_count": len(data["sources"]),
        "http_checks": checks,
        "metrics": accuracy["metrics"],
        "coverage": coverage,
        "independent_metric_recalculation": (
            "passed; standard-library arithmetic over captured records"
        ),
        "cutoff_example": "passed; 18699 MW at 2026-01-01T09:30:00Z",
        "history_selection": "passed; exactly one eligible selected revision",
        "archive_scope": "bounded publication window; no global history completeness claim",
    }
    (output or ROOT / "docs/PHASE_2_VERIFICATION.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--origin", help="Exact browser origin to verify, without a trailing slash")
    args = parser.parse_args()
    verify(args.base_url.rstrip("/"), args.output, args.origin)
