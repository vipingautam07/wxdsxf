# WindScope demo walkthrough

Audience: utility purchasing team and technical lead. Suggested duration: 6–8 minutes.

**Recording URL:** `[TODO: insert recorded demo URL]`  
**Live application URL:** `[TODO: insert verified deployment URL]`  
**Local application:** http://127.0.0.1:8080 after `docker compose up --build`.

## 1. Frame the decision — 45 seconds

“WindScope shows what wind forecast was available when a purchasing decision was made, then measures how that forecast compared with later reported generation. It evaluates forecasts; it does not execute purchases or recommend trading positions.”

Explain the fixed study: January 1–31 purchasing decisions, including February 1 delivery for January 31. The initial 11:00 UK cutoff is a pilot assumption. The sources describe GB system-operator-visible wind, not complete UK generation.

## 2. Day-ahead dashboard — 90 seconds

1. Select January 15 as the decision date. Show January 16 as the delivery day.
2. Identify the forecast available at cutoff and its publication timestamp.
3. Contrast the solid forecast line with the dashed retrospective actual line. Explain that actuals were not known when the decision was made.
4. Show the average signed error and explain positive = overforecast.
5. Point out 24 evaluation hours / 48 source actual settlement periods, and expand the exact interval table.
6. Explain prior reliability: only earlier completed deliveries with actual publications available by this cutoff contribute. January 1 correctly has no prior sample in the snapshot.

## 3. Monthly accuracy — 90 seconds

Show the four main cards at the 11:00 cutoff:

- MAE: approximately 2,013 MW — typical absolute error size.
- RMSE: approximately 2,506 MW — larger misses receive greater weight.
- Mean bias: approximately +1,730 MW — average overforecast in this sample.
- WAPE: approximately 17.84% — absolute error relative to actual generation.

Show the daily trend, forecast-vs-actual scatter, signed-error distribution, and over/under frequency. Explain that January's observed overforecast tendency is descriptive and does not identify its causes or guarantee future behavior. Open a worst-day link, then return to accuracy. Show definitions and exact daily values.

## 4. Prove the cutoff rule — 90 seconds

Open this reproducible example:

```text
/explorer?date=2026-01-01&cutoff=11%3A00&hour=00
```

This means January 1 decision, January 2 midnight delivery. Show:

1. The January 1 09:30 publication, 18,699 MW, is selected.
2. The 11:30 publication, 18,800 MW, is visible but excluded at an 11:00 cutoff.
3. Change the cutoff to 11:30, or use the corresponding deep link if presenting remotely. That revision becomes eligible at equality and is selected.
4. Revisions after the cutoff remain excluded. The retrospective actual reference does not influence forecast selection.

“A revision range shows how the forecast changed. It is not a confidence interval.”

## 5. Explain the engineering — 90 seconds

For the technical lead, show the architecture diagram and a test run:

```sh
cd backend
python -m pytest -q
python scripts/verify_live.py --base-url http://127.0.0.1:8080 --output ../docs/PHASE_4_VERIFICATION.json
```

Discuss the explicit ingestion CLI, source hashes, preserved revisions, strict validation, atomic last-good snapshot, pure statistics, typed API, cancelled stale frontend requests, and Docker proxy. Explain that snapshots avoid putting Elexon availability on the dashboard request path.

The most important modeling choice is resolution: hourly forecasts are compared with the mean of both actual half-hours. Missing half-hours produce a missing evaluation hour, never a partial average or zero. Metrics use hourly samples and report actual settlement-period coverage separately.

## 6. Close with evidence and limits — 45 seconds

State the checks actually completed: 83 backend tests, 8 frontend tests, production build, independent real-data recalculation, real API requests, browser review, and both healthy Docker services.

State that Vercel configuration and deployment instructions are ready, but hosted deployment has not been verified in this environment. Do not present the local Docker URL as a public live deployment. The video and live URL placeholders remain until recording and deployment are complete.

Disclose that Codex/AI assisted with research, implementation, debugging, testing and documentation, and that all application observations and metrics derive from Elexon.
