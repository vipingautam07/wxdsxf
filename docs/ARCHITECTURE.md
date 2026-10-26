# WindScope technical architecture

The pilot has two deployable services and one immutable historical data artifact. The design prioritizes temporal correctness, inspectable provenance, deterministic metrics, and a small operational surface.

## Data path

1. The explicit `app.ingestion` command requests only official WINDFOR and FUELHH streams through HTTPX. Publication windows preserve superseded forecasts. Actual requests use settlement dates and WIND filtering.
2. Each unmodified response receives a SHA-256 hash, request URL, retrieval time, and row count. Raw responses are gzip-compressed locally; the normalized snapshot retains all revision values and capture provenance.
3. Pydantic validates source shape, aware time and finite numbers. Normalization checks target-grid and settlement-date/period consistency. Exact duplicates collapse; conflicting duplicate revisions and negative wind values are flagged rather than selected by array order.
4. A complete new snapshot is checksummed and atomically replaces the old file. A failed ingestion preserves the previous snapshot and writes a failure record. A valid partial dataset remains partial, with no synthetic gap filling.
5. FastAPI loads and checks the snapshot once per process. A small per-instance LRU cache reuses analyses keyed by cutoff. No upstream request occurs on an API request or import.
6. React receives typed responses, handles request cancellation/retry/errors, and renders three workflows. Numerical calculations, histogram bins, rankings and source selection remain in Python.

## Temporal correctness

The key is `(target start_time, publication publish_time)`. A delivery's decision date is its preceding UK calendar day. The configurable Europe/London cutoff is converted to UTC and compared inclusively with publication timestamps. Selection is performed independently for each exact target.

A null or invalid latest eligible revision remains missing/invalid; older good values cannot silently replace it. Explorer responses retain later revisions with `eligible_at_cutoff=false`, while only one latest eligible publication can have `selected=true`.

Retrospective accuracy uses the latest reported actual in the snapshot. Prior-reliability analysis instead reselects actual revisions at the decision cutoff and requires completed earlier delivery intervals, preventing later corrections from entering the indicator.

## Resolution and units

WINDFOR's verified targets are hourly. FUELHH reports average MW over half-hours. For the pilot, each hourly forecast represents that delivery hour and is compared with the mean of the two actual periods. Both actuals are required. This is documented as an alignment assumption, not a claim that the source supplies native half-hour forecasts.

Power remains MW in storage, calculations and API responses. Charts may scale axis labels to GW. Coverage separately reports matched evaluation hours and native actual settlement periods. This avoids presenting 1,488 source half-hours as 1,488 independent forecast observations.

## Service boundaries

| Module | Responsibility |
| --- | --- |
| `clients/elexon.py` | Official endpoint access, timeout and bounded retry policy |
| `ingestion.py` | Publication/delivery windows, adjacent probes, source capture and snapshot publishing |
| `normalization.py` | Schema validation, UTC/grid/settlement checks and duplicate rules |
| `selection.py` | Local calendars, DST/cutoff conversion and latest eligible revision |
| `matching.py` | Exact target joins, complete actual hours and gap-aware coverage |
| `metrics.py` | Deterministic metrics and distributions |
| `repository.py` | Snapshot digest validation and atomic storage |
| `service.py` | Monthly/daily/day/history orchestration and caching |
| `schemas.py` | Source, snapshot, and public API contracts |
| `routes.py`, `main.py` | HTTP requests, readiness, error mapping and CORS |
| `frontend/src/api/` | Centralized HTTP, typed contracts and cancellation |

## Deployment paths

Docker: Nginx serves the static Vite build and proxies relative `/api/` requests over the internal Compose network to Uvicorn. Health checks establish readiness. The browser sees one loopback origin.

Vercel: two root-directory projects, Vite and native FastAPI. A build-time frontend API base URL points at the backend. Explicit CORS origins permit the frontend. The Python entrypoint exports `app`, and the snapshot is included in the function bundle. Hosted deployments have not been verified here.

## Practical tradeoffs

- A compressed JSON file avoids database/schema migration services and a separate columnar engine for fewer than 25,000 source records.
- Dynamic selection supports arbitrary cutoff changes without network requests or precomputing a snapshot per cutoff.
- Strict validation makes upstream schema changes visible instead of accepting potentially misinterpreted data.
- The bounded history window and adjacent probes support this period without promising a complete global archive.
- The pilot has no authentication or trading action surface. It contains public historical observations and descriptive analytics.
- Expanding to multiple years or many fuels would justify more efficient columnar storage and a more deliberate refresh/observability pipeline; that complexity is outside this assignment.

Verification includes deterministic edge cases, independent arithmetic over real data, real HTTP checks, a React production build, and complete Docker execution. Those are distinct from a successful hosted deployment.
