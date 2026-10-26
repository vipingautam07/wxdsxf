"""Phase 1 evidence capture only; this is not the application ingestion pipeline.

Run from the repository root: python3 docs/research/probe_elexon.py
Uses only the Python standard library and the two permitted Elexon datasets.
"""

import collections
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
BASE = "https://data.elexon.co.uk/bmrs/api/v1"
UTC = dt.timezone.utc


def capture(name, url):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read()
        metadata = {
            "url": url,
            "status": response.status,
            "content_type": response.headers.get("Content-Type"),
            "retrieved_at": dt.datetime.now(UTC).isoformat(),
            "sha256_uncompressed": hashlib.sha256(body).hexdigest(),
            "bytes_uncompressed": len(body),
        }
    value = json.loads(body)
    (OUT / "responses").mkdir(parents=True, exist_ok=True)
    target = OUT / "responses" / f"{name}.json.gz"
    target.write_bytes(gzip.compress(body, mtime=0))
    metadata["file"] = str(target.relative_to(OUT))
    metadata["row_count"] = len(value) if isinstance(value, list) else None
    print(name, metadata["status"], metadata["row_count"], flush=True)
    return value, metadata


def dataset(name, endpoint, **params):
    value, metadata = capture(name, f"{BASE}/datasets/{endpoint}/stream?{urllib.parse.urlencode(params)}")
    if not isinstance(value, list):
        raise ValueError(f"Expected a bare array for {endpoint}")
    return value, metadata


def main():
    captures = []
    schema, meta = capture("openapi", "https://data.elexon.co.uk/swagger/v1/swagger.json")
    captures.append(meta)
    selected_paths = [f"/datasets/{name}/stream" for name in ("FUELHH", "WINDFOR")]
    refs = [schema["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["items"]["$ref"].split("/")[-1] for path in selected_paths]
    (OUT / "official-contract.json").write_text(json.dumps({
        "source": meta["url"], "retrieved_at": meta["retrieved_at"],
        "servers": schema.get("servers"),
        "paths": {path: schema["paths"][path] for path in selected_paths},
        "schemas": {ref: schema["components"]["schemas"][ref] for ref in refs},
    }, indent=2) + "\n")

    forecasts, meta = dataset("windfor-publications", "WINDFOR",
        publishDateTimeFrom="2025-12-30T00:00:00Z", publishDateTimeTo="2026-02-03T00:00:00Z")
    captures.append(meta)
    actuals, meta = dataset("fuelhh-deliveries", "FUELHH",
        settlementDateFrom="2026-01-02", settlementDateTo="2026-02-01", fuelType="WIND")
    captures.append(meta)
    boundary, meta = dataset("windfor-inclusive-boundary", "WINDFOR",
        publishDateTimeFrom="2026-01-01T09:30:00Z", publishDateTimeTo="2026-01-01T09:30:00Z")
    captures.append(meta)
    single, meta = dataset("fuelhh-single-date", "FUELHH",
        settlementDateFrom="2026-02-01", settlementDateTo="2026-02-01", fuelType="WIND")
    captures.append(meta)

    begin = dt.datetime(2026, 1, 2, tzinfo=UTC)
    end = dt.datetime(2026, 2, 2, tzinfo=UTC)
    expected = [begin + dt.timedelta(minutes=30 * i) for i in range(int((end-begin).total_seconds()/1800))]
    iso = lambda value: value.isoformat().replace("+00:00", "Z")
    actual_index = collections.defaultdict(list)
    forecast_index = collections.defaultdict(list)
    for row in actuals:
        if row["fuelType"] == "WIND":
            actual_index[row["startTime"]].append(row)
    for row in forecasts:
        forecast_index[row["startTime"]].append(row)
    missing_actuals = [iso(t) for t in expected if not any(r["generation"] is not None for r in actual_index[iso(t)])]
    missing_forecasts = []
    selected = []
    daily = []
    for day in range(31):
        delivery = begin + dt.timedelta(days=day)
        decision_date = (delivery-dt.timedelta(days=1)).date()
        cutoff = dt.datetime.combine(decision_date, dt.time(11), tzinfo=ZoneInfo("Europe/London")).astimezone(UTC)
        available = 0
        for hour in range(24):
            target = delivery + dt.timedelta(hours=hour)
            eligible = [r for r in forecast_index[iso(target)] if dt.datetime.fromisoformat(r["publishTime"].replace("Z", "+00:00")) <= cutoff]
            if not eligible:
                missing_forecasts.append(iso(target))
            else:
                available += 1
                selected.append(max(eligible, key=lambda r: r["publishTime"]))
        daily.append({"decision_date": (delivery-dt.timedelta(days=1)).date().isoformat(), "eligible_forecast_hours": available,
            "actual_settlement_periods": sum(bool(actual_index[iso(delivery+dt.timedelta(minutes=30*i))]) for i in range(48))})

    keys = collections.Counter((r["startTime"], r["publishTime"]) for r in forecasts)
    audit = {
        "decision_dates": ["2026-01-01", "2026-01-31"],
        "delivery_dates": ["2026-01-02", "2026-02-01"],
        "cutoff_uk_local": "11:00",
        "expected_forecast_hours": 744, "expected_actual_settlement_periods": 1488,
        "forecast_rows_downloaded": len(forecasts), "actual_rows_downloaded": len(actuals),
        "forecast_target_minutes": dict(collections.Counter(r["startTime"][14:16] for r in forecasts)),
        "forecast_publish_bounds": [min(r["publishTime"] for r in forecasts), max(r["publishTime"] for r in forecasts)],
        "forecast_publication_batches": len(set(r["publishTime"] for r in forecasts)),
        "actual_target_bounds": [min(r["startTime"] for r in actuals), max(r["startTime"] for r in actuals)],
        "actual_fuel_types": sorted(set(r["fuelType"] for r in actuals)),
        "missing_actual_periods": missing_actuals, "missing_eligible_forecast_hours": missing_forecasts,
        "duplicate_forecast_keys": sum(n-1 for n in keys.values()),
        "duplicate_actual_targets": sum(max(len(rows)-1, 0) for rows in actual_index.values()),
        "null_forecast_generation": sum(r["generation"] is None for r in forecasts),
        "null_actual_generation": sum(r["generation"] is None for r in actuals),
        "equal_publication_bounds_rows": len(boundary),
        "equal_publication_bounds_values": sorted(set(r["publishTime"] for r in boundary)),
        "single_settlement_date_rows": len(single),
        "single_settlement_date_values": sorted(set(r["settlementDate"] for r in single)),
        "selected_publications_utc": sorted(set(r["publishTime"][11:] for r in selected)),
        "jan_2_midnight_selected_example": selected[0] if selected else None,
        "daily": daily,
    }
    (OUT / "manifest.json").write_text(json.dumps(captures, indent=2) + "\n")
    (OUT / "coverage-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({k:v for k,v in audit.items() if k != "daily"}, indent=2))


if __name__ == "__main__":
    main()
