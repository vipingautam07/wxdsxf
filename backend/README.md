# WindScope backend

FastAPI application for point-in-time January 2026 day-ahead wind analysis. Only the official Elexon `WINDFOR` and `FUELHH` streams supply application data. A validated Elexon snapshot is included at `data/processed/snapshot.json.gz` so dashboard requests do not depend on upstream availability.

## Run locally

Requires Python 3.12 or newer (3.12 is the deployment baseline). From the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [API documentation](http://127.0.0.1:8000/docs) or [health](http://127.0.0.1:8000/api/health). Runtime-only installations use `requirements.txt`. Both dependency files pin the complete resolved dependency sets; `.in` files express the direct dependency constraints for future deliberate upgrades.

All routes are GET requests:

| Route | Query |
| --- | --- |
| `/api/health` | None |
| `/api/overview` | Optional `cutoff=11:00` |
| `/api/day` | Required decision `date=2026-01-15`; optional cutoff |
| `/api/accuracy` | Optional cutoff |
| `/api/accuracy/daily` | Optional cutoff |
| `/api/forecast-history` | Required offset-aware hourly `start_time=2026-01-16T12:00:00Z`; optional cutoff |
| `/api/coverage` | Optional cutoff |

`date` is the purchasing decision date, not the delivery date. January 31 decisions concern February 1 delivery. The cutoff is UK local time, interpreted with Europe/London and converted to UTC. This is a pilot assumption, not a verified market gate-closure rule.

Requests outside the pilot scope return 404. Invalid dates, cutoffs, or naive timestamps return 422. An unavailable/corrupt snapshot returns 503 with a structured error. A valid but partially covered period returns 200 with nulls and explicit gaps. Health distinguishes process availability from snapshot readiness.

## Refresh the source snapshot

From `backend/` with the environment activated:

```sh
python -m app.ingestion
```

This explicitly fetches bounded publication windows, two adjacent-day forecast probes, and delivery-date-filtered WIND actuals. It uses HTTPX timeouts, bounded retries, and Retry-After handling. Unmodified responses are stored by checksum in `data/raw/` (ignored by Git). Normalization checks source schemas, timestamps, settlement periods, finite generation, nulls, and duplicates. Conflicting revisions and negative wind values are flagged as unusable rather than silently corrected.

If an adjacent probe contains revisions for a pilot delivery target, ingestion fails and explains that the publication buffer must be widened. History is always labeled as bounded to the recorded publication window, not globally complete.

Ingestion publishes one checksummed compressed snapshot through an atomic file replacement. A failed refresh leaves the previous snapshot intact and records the failure in `data/processed/last-attempt.json`; the CLI exits unsuccessfully. Partial coverage remains visible in the API rather than being filled with zeros. An all-empty response will produce an explicitly empty analytical grid, not fabricated observations.

To reproduce from the verified, previously recorded official captures without network access:

```sh
python -m app.ingestion --from-verified-archive ../docs/research
```

This checks the raw response hashes and official endpoint provenance before normalization. It is not a synthetic demo-data mode. The snapshot records whether it came from live requests or verified official archives.

The API lazily loads a snapshot once per process and retains a small bounded response cache. Restart the API after a successful ingestion to use the new snapshot. There are no upstream requests at import time, startup, or while serving analytical routes.

## Methodology

For every exact hourly target, select the latest record published at or before the previous UK calendar day's purchasing cutoff. Null or invalid latest revisions never fall back silently to an older value. Post-cutoff revisions remain available in the explorer response but are ineligible for selection.

The observed forecast source is hourly; actuals are half-hourly average MW. The pilot treats each hourly forecast as representative of that delivery hour, and compares it with the mean of **both** constituent actual half-hours. This alignment is an explicit assumption. If either actual half-hour is missing, the hourly actual is null. No forecast interpolation or half-hour forward fill is performed. Coverage separately reports native actual settlement periods and settlement periods represented by complete matched hours.

Error is **forecast − actual**. Positive bias means overforecasting. Metrics include MAE, RMSE, mean bias, WAPE, linear-interpolated P90 absolute error, and over/under/exact frequencies. Monthly metrics pool all matched hours. No matched pairs yield null metrics; a zero WAPE denominator yields null with a reason. Exact matches remain in the frequency denominator.

Day-specific historical reliability reselects actual revisions as of that decision's cutoff and includes only completed earlier delivery intervals. It cannot use later actual corrections. January 1 has no earlier deliveries in this snapshot and therefore no historical reliability sample. Whole-month accuracy and actuals are retrospective. Revision ranges describe forecast changes and are not confidence intervals.

The series cover GB system-operator-visible wind, not complete UK wind generation. Reported outturn can differ from available unconstrained wind energy; the pilot does not infer the causes of forecast errors.

## Tests and verification

From `backend/`:

```sh
python -m pytest -q
ruff check .
ruff format --check .
python -m pip check
```

With a local API already running, verify every real HTTP endpoint and independently recompute all monthly metrics from the snapshot with standard-library arithmetic:

```sh
python scripts/verify_live.py
```

This writes `docs/PHASE_2_VERIFICATION.json`. The check intentionally expects the complete, real January snapshot at the default 11:00 cutoff. Synthetic test fixtures occur only in `tests/` and never become dashboard data. One upstream Starlette deprecation warning currently accompanies its HTTPX-based TestClient; test behavior remains supported and all cases pass.

## Configuration and architecture

- `WINDSCOPE_SNAPSHOT_PATH`: override the snapshot file; defaults to a path derived from the backend package location, independent of shell working directory.
- `CORS_ORIGINS`: comma-separated explicit browser origins; defaults to `http://localhost:5173,http://localhost:8080`.

`clients/elexon.py` handles HTTP; `ingestion.py` captures and publishes data; `normalization.py` validates source records; `selection.py` handles timezones/cutoffs; `matching.py` preserves expected intervals and aggregates actuals; `metrics.py` calculates statistics; `repository.py` checks snapshot integrity; `service.py` orchestrates analytics; `schemas.py` defines Pydantic contracts; `routes.py` and `main.py` expose the API and error/CORS handling.

Docker and the frontend are now implemented and verified locally; see the root README for the complete workflow. The source exports `app.main:app`, matching the configured Vercel FastAPI entrypoint. Hosted Vercel deployment remains unverified; no deployment success is claimed.

Codex/AI assisted with research, implementation, debugging, testing, and this documentation.
