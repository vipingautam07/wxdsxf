# WindScope

**UK Wind Forecast Intelligence — a point-in-time GB wind analytics pilot.**

WindScope reconstructs the wind generation forecast available when a day-ahead purchasing decision was made, compares it with subsequently reported generation, and makes forecast error and revision history inspectable.

**Live application:** `[TODO: add verified Vercel frontend URL]`  
**Demo video:** `[TODO: add recorded walkthrough URL]`

The full application is implemented and verified locally, including both Docker containers. Vercel deployment configurations and exact steps are provided; **no live Vercel deployment has been performed or verified** in this environment.

## 1. Business problem and scope

A utility buying day-ahead electricity needs to understand the wind forecast it could have known at a purchasing cutoff and how that forecast later performed. Using a subsequently revised forecast would introduce look-ahead bias.

This pilot covers purchasing decisions **1–31 January 2026**, for deliveries **2 January–1 February 2026**. The configurable purchasing cutoff defaults to **11:00 Europe/London**. That time is a **pilot assumption, not a verified market gate-closure rule**.

Only national-level wind forecasts and actuals are in scope. WindScope does not execute trades, optimize purchases, forecast prices, or recommend procurement quantities. The Elexon series describe **Great Britain system-operator-visible wind**, not complete wind generation across every UK asset or Northern Ireland.

## 2. Features

- **Day-ahead dashboard:** decision date and cutoff filters, following-day forecast versus retrospective actuals, publication provenance, signed average error, prior reliability available by cutoff, and source coverage.
- **Forecast accuracy:** MAE, RMSE, bias, WAPE, P90 absolute error, daily trends, comparison scatter, over/under/exact frequencies, worst days, and error distribution.
- **Forecast explorer:** delivery date/hour selection, retained revisions, publication times, cutoff marker, selected forecast, and actual reference.
- Exact-value tables alongside charts, explicit missing values, loading skeletons, retry/error/empty states, responsive navigation, accessible controls and legends.
- Reproducible ingestion, source checksums, validated historical snapshot, seven typed FastAPI endpoints, and deterministic tests.

No calculated metric is hardcoded in the frontend. All statistics, rankings, histogram bins, and comparison observations come from backend calculations over real Elexon records.

## 3. Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts, React Router |
| Backend | Python 3.12, FastAPI, Pydantic, Pandas, NumPy, HTTPX, Uvicorn |
| Verification | Pytest, Vitest, Testing Library, Ruff, Prettier, real HTTP checks |
| Local delivery | Docker Compose, Python slim image, Node build stage, Nginx static serving/proxy |
| Deployment target | Separate Vercel Vite and native FastAPI projects |
| Storage | Checksummed compressed JSON snapshot; no database, Redis, queue, or authentication service |

Python runtime and development dependencies are pinned in `backend/requirements*.txt`; the complete runtime pins are also declared in `backend/pyproject.toml` for Python deployment tooling. Frontend dependency resolution is committed in `frontend/package-lock.json`.

## 4. Architecture

```mermaid
flowchart LR
    E[Elexon FUELHH and WINDFOR streams] --> I[Explicit HTTPX ingestion CLI]
    I --> R[Raw responses and provenance hashes]
    R --> V[Schema, time and duplicate validation]
    V --> S[Atomic versioned snapshot]
    S --> A[FastAPI selection, matching and analytics]
    A --> U[React dashboard, accuracy and explorer]
```

Ingestion is an explicit operation. API startup and dashboard requests never fetch historical data from Elexon. This keeps the dashboard fast and useful during an upstream outage without substituting fake observations.

The API loads a validated snapshot once per process and caches a bounded number of cutoff analyses. Refresh the snapshot explicitly, then restart the process. Failed refreshes leave the previous valid snapshot intact and record the failed attempt. Missing/corrupt snapshots produce a clear 503; partial observations produce nulls and coverage gaps.

See [technical architecture](docs/ARCHITECTURE.md) for module responsibilities and tradeoffs.

## 5. Project directory

```text
backend/
  app/
    clients/elexon.py       Official streams, timeouts and bounded retries
    ingestion.py           Live/archive ingestion and atomic publishing
    normalization.py       Source schemas, grid/settlement checks, duplicates
    selection.py           UK local cutoff and exact-target revision selection
    matching.py            Expected grids, paired actuals, coverage gaps
    metrics.py             Pure numerical statistics and distributions
    repository.py          Snapshot integrity and storage
    service.py             Application analytics and bounded caching
    schemas.py             Pydantic source, snapshot and response contracts
    routes.py, main.py     Seven endpoints, errors and CORS
  data/processed/          Included real Elexon snapshot
  scripts/verify_live.py   HTTP smoke test and independent metric verification
  tests/                  Deterministic unit and integration tests
  Dockerfile, vercel.json
frontend/
  src/api/                Central client, typed contracts and hook tests
  src/components/         Shared analytics and official shadcn/ui components
  src/pages/              Dashboard, Accuracy, Explorer
  src/lib/                UK time and unit formatting
  Dockerfile, nginx.conf, vercel.json
docs/
  research/               Official contracts, captures, hashes and availability audit
  PHASE_*                 Phase plans, reports and verification results
  ARCHITECTURE.md
  DEMO_WALKTHROUGH.md
docker-compose.yml
.env.example
```

## 6. Elexon sources and verified API behavior

Only these two datasets supply application observations:

- [FUELHH stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream): half-hourly average MW outturn; only `fuelType=WIND` is used.
- [WINDFOR stream](https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream): hourly wind forecast targets and historical publications.

Base URL: `https://data.elexon.co.uk/bmrs/api/v1`. The official APIs are public and require no API key. The exact schema was inspected at [Elexon's OpenAPI URL](https://data.elexon.co.uk/swagger/v1/swagger.json), and verified against real responses before implementation.

Both stream endpoints return **bare JSON arrays**, without a `data` envelope or stream pagination fields. WINDFOR accepts `publishDateTimeFrom` and `publishDateTimeTo`, filtering **publication time, not delivery time**. FUELHH supports those publication filters or settlement-date filters; do not combine the modes. Actual ingestion uses `settlementDateFrom`, `settlementDateTo`, and `fuelType=WIND`.

Boundary probes showed inclusive publication timestamps and inclusive settlement end dates. Adjacent publication windows therefore share endpoints and are deduplicated. The live pipeline fetches bounded windows plus adjacent-day probes. Returned source publication times determine selection; no publication schedule is hardcoded.

The included snapshot retains **20,440 forecast revisions** in the buffered publication window and **1,488 actual settlement-period records**. At the default cutoff all **744 hourly evaluation targets** are matched. Records targeting outside the pilot delivery range remain in the source snapshot but do not enter pilot metrics. Global archive retention/completeness is not claimed.

The research captures and manifests are in [docs/research](docs/research/README.md). Elexon Insights Solution is the source of the data; see its [methodology](https://bmrs.elexon.co.uk/wind-generation) and [developer portal](https://developer.data.elexon.co.uk/).

## 7. Forecast selection methodology

For every delivery hour:

1. Derive the previous **UK calendar date** as the decision date.
2. Combine that date with the configured UK local cutoff using Europe/London, then convert to aware UTC.
3. Find forecast records targeting that exact hour and exclude publications after the cutoff.
4. Select the latest publication at or before the cutoff. Equality is eligible.
5. Match with the same delivery hour's actual generation and calculate `forecast − actual`.

Null or conflicting latest eligible revisions are not silently replaced by older good values. Exact duplicates collapse with counts recorded. Conflicting duplicates and negative wind values are retained as unusable records; missing generation is not replaced with zero.

Example from the real source: for January 2 midnight delivery, the January 1 **09:30 publication is 18,699 MW**. At an 11:00 cutoff that revision is selected. The **11:30 revision is 18,800 MW** and is excluded; it becomes eligible at an 11:30 cutoff.

**Resolution assumption:** WINDFOR is hourly in the verified period; FUELHH is half-hourly. The pilot treats an hourly forecast as representative of `[start, start + 1 hour)` and compares it with the mean of **both** actual half-hours. If either is missing, the hourly actual is null. Primary metrics use hourly pairs. No half-hour forecasts are interpolated or invented. Native actual settlement-period coverage is reported separately.

All internal timestamps are aware UTC. UI times explicitly use Europe/London. January is GMT, while conversion, calendar-day logic, DST day lengths, and ambiguous/nonexistent cutoff handling are tested beyond January.

## 8. Accuracy metrics

Let `e = forecast − actual` over `n` matched hourly pairs. **Positive error means overforecasting.**

| Metric | Definition |
| --- | --- |
| MAE (MW) | `sum(abs(e)) / n` |
| RMSE (MW) | `sqrt(sum(e²) / n)` |
| Mean Bias Error (MW) | `sum(e) / n` |
| WAPE (%) | `100 × sum(abs(e)) / sum(abs(actual))` |
| Overforecast frequency (%) | `100 × count(e > 0) / n` |
| Underforecast frequency (%) | `100 × count(e < 0) / n` |
| Exact frequency (%) | `100 × count(e = 0) / n` |
| P90 absolute error (MW) | 90th percentile of `abs(e)`, using linear interpolation |

Empty matched sets yield null metrics. WAPE is null with an explicit reason when its denominator is zero. Exact matches remain in frequency denominators. Monthly statistics pool observations rather than averaging daily statistics. Coverage includes expected, matched, missing-forecast, missing-actual and both-missing hours, plus native actual settlement periods; overlapping missing counts are explicit.

Real January results at the default cutoff: MAE **2,013.01 MW**, RMSE **2,505.94 MW**, bias **+1,729.93 MW**, WAPE **17.84%**. These are documented observations, not application constants. The [verification record](docs/PHASE_4_VERIFICATION.json) contains full precision and independent recalculation results.

Whole-month statistics and actuals are retrospective. The dashboard's prior-reliability indicator uses only completed earlier deliveries and actual revisions published by that decision's cutoff. January 1 has no prior observations in this snapshot. Revision ranges describe forecast changes, not probabilistic confidence intervals.

## 9. Local setup

Requires Python **3.12–3.14** (3.12 recommended) and Node **22.12+** (Node 24 is used in Docker).

Backend, from the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, from the repository root:

```sh
cd frontend
npm ci
npm run dev
```

Open [WindScope](http://127.0.0.1:5173). Vite proxies relative `/api` requests to port 8000. Standalone backend [Swagger documentation](http://127.0.0.1:8000/docs) describes every response contract.

The committed snapshot makes initial startup network-independent after dependency installation. To refresh it, stop/restart the API around an explicit ingestion:

```sh
cd backend
python -m app.ingestion
```

For a reproducible rebuild from the checksummed official research captures:

```sh
python -m app.ingestion --from-verified-archive ../docs/research
```

`CORS_ORIGINS` configures explicit browser origins; `WINDSCOPE_SNAPSHOT_PATH` overrides the snapshot path. Defaults work locally. `frontend/.env.example` describes `VITE_API_BASE_URL`; leave it as `/api` for local Vite or Docker.

## 10. Docker

With Docker Desktop/Engine and Compose running, from the repository root:

```sh
docker compose up --build
```

Open [WindScope in Docker](http://127.0.0.1:8080). Nginx serves the production React build and proxies `/api/` to `backend:8000` on the Compose network. The browser never needs to resolve a Docker service hostname. The backend is internal to Compose; use the frontend `/api` routes for HTTP access.

Optional port/environment overrides are documented in `.env.example`; copy it to `.env` if needed. To run detached with readiness checks or stop:

```sh
docker compose up -d --build --wait
docker compose ps
docker compose down
```

The backend runs as an unprivileged user. Both services have health checks; frontend startup waits for backend readiness. No database migration or runtime data download is required. After refreshing the source snapshot, rebuild the backend image so the updated snapshot is packaged.

## 11. Tests and verification

From the repository root with the Python environment activated:

```sh
cd backend
python -m pytest -q
ruff check .
ruff format --check .
python -m pip check
```

In another terminal, from the repository root:

```sh
cd frontend
npm test
npm run build
npm run format:check
```

The backend suite covers cutoff boundaries, repeated target revisions, no eligible forecast, null latest values, missing/incomplete actuals, duplicates/conflicts, timezone and DST behavior, deterministic metrics, percentage edge cases, upstream retries, snapshot integrity, last-good preservation, CORS, validation, and real source integration.

Frontend tests cover structured/network errors, unreadable responses, retry recovery, stale-request cancellation, missing-versus-zero formatting, UK time conversion, and the January/February boundary.

For real HTTP checks with the API or Docker already running:

```sh
cd backend
python scripts/verify_live.py
python scripts/verify_live.py --base-url http://127.0.0.1:8080 --output ../docs/PHASE_4_VERIFICATION.json
```

The verifier independently recomputes all monthly metrics using standard-library arithmetic over the included snapshot, without importing application metric functions.

**Verified:** 83 backend tests, 8 frontend tests, TypeScript/Vite production build, backend lint/format, frontend formatting, dependency consistency, both Docker image builds, both container health checks, all seven API endpoints through Nginx, and browser checks of the UI. One upstream Starlette warning concerns its HTTPX-based TestClient deprecation; tests pass and the warning is not suppressed. Small synthetic fixtures exist only in tests.

## 12. Vercel deployment

Deploy **two projects from this repository**. No Vercel CLI login/project connection is configured in the development environment, so hosted build/runtime behavior remains unverified.

| Setting | Backend project | Frontend project |
| --- | --- | --- |
| Root Directory | `backend` | `frontend` |
| Framework | FastAPI | Vite |
| Runtime | Python 3.12 (`.python-version`) | Node 24 recommended |
| Entrypoint | `app/main.py` exports `app`; `tool.vercel.entrypoint = "app.main:app"` | `src/main.tsx` |
| Dependencies | Pinned runtime manifest; no test dependencies required | `npm ci` |
| Build | Native Python framework handling | `npm run build` |
| Output | Native Python ASGI function | `dist` |

Exact dashboard procedure:

1. Put this source in a Git repository and push it to a provider connected to your Vercel account. Ensure `backend/data/processed/snapshot.json.gz` is included.
2. Import the repository into a new **backend project**, selecting Root Directory `backend` and the FastAPI framework preset. Keep the native runtime; do not configure a legacy custom Python builder. Deploy and record its HTTPS origin.
3. Open backend `/api/health`; require `snapshot_ready: true`. Verify all seven routes, including `/api/day?date=2026-01-31` returning February 1 delivery.
4. Import the same repository as a separate **frontend project**, selecting Root Directory `frontend`, Vite, Node 24, build command `npm run build`, and output `dist`.
5. Before frontend deployment, set **`VITE_API_BASE_URL=https://YOUR-BACKEND-PROJECT.vercel.app/api`** in its Production environment. This is a build-time value. Deploy and record the frontend origin.
6. Set backend **`CORS_ORIGINS=https://YOUR-FRONTEND-PROJECT.vercel.app`** and redeploy the backend. Add any approved preview frontend origins explicitly to the corresponding backend environment; do not assume production CORS covers every preview domain.
7. Open the frontend dashboard, accuracy and explorer directly, refresh each route, change filters, and compare displayed values with API responses. Confirm backend access is permitted by the deployment's access settings. A reachable frontend alone does not verify backend integration.
8. Run `python scripts/verify_live.py --base-url https://YOUR-BACKEND-PROJECT.vercel.app --output ../docs/VERCEL_VERIFICATION.json` from `backend/` against the matching committed snapshot. Add verified URLs to the placeholders only after this and browser integration checks pass.

CLI alternative, using an account you control:

```sh
npx vercel@latest login
cd backend
npx vercel@latest link
npx vercel@latest deploy --prod
```

From the repository root in another terminal:

```sh
cd frontend
npx vercel@latest link
npx vercel@latest env add VITE_API_BASE_URL production
npx vercel@latest deploy --prod
```

After the frontend origin is known, from `backend/`:

```sh
npx vercel@latest env add CORS_ORIGINS production
npx vercel@latest deploy --prod
```

The `env add` commands prompt for values; enter the URLs described above. Choose a separate project when linking each directory. The per-directory `vercel.json` files configure current framework presets, function exclusions, and SPA deep-link fallback. The snapshot is bundled and read relative to the Python package; production requests do not write to the deployment filesystem.

Configuration follows the current official [FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python), [Vite SPA](https://vercel.com/docs/frameworks/frontend/vite), and [monorepo](https://vercel.com/docs/monorepos) guidance. Docker verification does not prove Vercel deployment success.

## 13. API reference

All analysis routes support optional `cutoff=HH:MM`, default `11:00`, interpreted in Europe/London.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Process and snapshot readiness |
| `GET /api/overview` | Scope, available decision dates, monthly metrics and coverage |
| `GET /api/day?date=2026-01-15` | Decision-specific following-day forecast/actual analysis |
| `GET /api/accuracy` | Metrics, distribution, comparison points and worst days |
| `GET /api/accuracy/daily` | Ordered daily metrics and coverage |
| `GET /api/forecast-history?start_time=2026-01-16T12:00:00Z` | Retained revisions, eligibility and selected publication |
| `GET /api/coverage` | Hour/settlement-period availability and validation findings |

`date` is the decision date. `start_time` must be offset-aware and an hourly target. Data values are MW; chart axes can display GW. JSON nulls preserve missing values. Errors use a structured `error` envelope; health has a separate readiness response. Bad parameters return 422, out-of-scope dates 404, and unavailable snapshots 503.

## 14. Assumptions and limitations

- The 11:00 local cutoff is configurable and unverified as a market rule.
- Public `publishTime` proxies availability; actual utility receipt times are not available.
- Hourly forecast representativeness and actual aggregation are explicit pilot assumptions; no native half-hour forecast is claimed.
- Actuals are reported retrospective outturns, not certified final settlement or unconstrained wind availability.
- Source geography is GB/system-operator-visible wind. No complete UK or embedded-generation total is implied.
- Historical revisions are retained within a bounded publication window. Adjacent probes found no relevant targets beyond its edges; global archive completeness is not guaranteed.
- Prior reliability is limited to observations available within this pilot snapshot; January 1 has none.
- Revision spread is descriptive, not a calibrated uncertainty interval. No causal or future-performance conclusions are inferred from January error statistics.
- Snapshot refresh and process restart/redeployment are explicit. This is a focused pilot without authentication, live trading, or production monitoring infrastructure.
- Vercel deployment and hosted integration remain unverified until an authorized account runs the documented steps. Demo recording and public URL placeholders remain open.

## 15. Development workflow and verification evidence

The implementation followed research → data/backend → frontend → tests/deployment preparation → documentation. The planned budget was 16 hours: 2 research, 4.5 backend, 4.5 frontend, 3 testing/deployment, 2 documentation. These are allocations, not a fabricated time-tracking record.

Phase summaries include changed files, actual checks, issues and remaining work:

- [Phase 1 plan and API research](docs/PHASE_1_PLAN.md)
- [Phase 2 backend report](docs/PHASE_2_REPORT.md)
- [Phase 3 frontend report](docs/PHASE_3_REPORT.md)
- [Phase 4 verification and deployment status](docs/PHASE_4_REPORT.md)
- [Phase 5 documentation report](docs/PHASE_5_REPORT.md)

## 16. AI assistance disclosure

**Codex/AI tools assisted with planning, official API research, product design, implementation, debugging, test creation/execution, and documentation.** Analytical observations originate from Elexon. Generated tests use small explicitly synthetic fixtures only to validate behavior; no fabricated data or metrics are presented as real dashboard observations. Research evidence, source hashes, implementation and verification commands are available for review.

## 17. Demo and application links

- **Demo video:** `[TODO: record the walkthrough and insert URL]`
- **Live frontend:** `[TODO: deploy and verify, then insert URL]`
- **Live backend:** `[TODO: deploy and verify, then insert URL]`
- **Local Docker application:** [http://127.0.0.1:8080](http://127.0.0.1:8080)

Use the [demo walkthrough](docs/DEMO_WALKTHROUGH.md) for a client and technical-lead presentation.
