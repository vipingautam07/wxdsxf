# Phase 1 Elexon evidence

This directory contains research evidence, not the application ingestion pipeline or a production snapshot. Only the official FUELHH and WINDFOR datasets were queried. The OpenAPI response is documentation, not a third analytical dataset.

- `official-contract.json`: exact selected paths and referenced schemas extracted from the official OpenAPI response.
- `manifest.json`: request URLs, retrieval timestamps, status/content type, raw byte lengths and uncompressed SHA-256 checksums.
- `responses/*.json.gz`: five captured, unmodified HTTP response bodies, gzip-compressed for storage. Includes the full OpenAPI response.
- `coverage-audit.json`: expected-grid coverage for all January purchasing decisions and the resulting January 2–February 1 delivery period.
- `verification.json`: results of offline checksum, boundary, selection, and coverage checks; explicitly distinguishes these from application tests not yet run.
- `probe_elexon.py`: standard-library-only read-only capture probe.

From the repository root, reproduce the live captures with:

```sh
python3 docs/research/probe_elexon.py
```

This overwrites the captured response files and manifests with newly retrieved Elexon evidence. The historical source can change; retain previous captures if comparing versions. `verification.json` describes the original offline verification and is not refreshed by the capture probe.

The captured forecast publication window includes targets outside the pilot delivery range. Do not calculate pilot metrics over the whole response. Filter by delivery target, apply the preceding-day local cutoff, and select the latest eligible revision separately for each target. Forecast history retains post-cutoff revisions for retrospective exploration only.

The source forecast is hourly and actuals are half-hourly. Read `../PHASE_1_PLAN.md` for the explicit hourly alignment assumption, coverage semantics, and remaining implementation work.

Source: Elexon Insights Solution, https://data.elexon.co.uk/bmrs/api/v1. Captured 26 October 2026. Codex/AI assisted with this research, validation, and implementation planning.
