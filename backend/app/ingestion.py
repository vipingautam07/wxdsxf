"""Explicit ingestion CLI. Never executed at API startup or while serving requests."""

import argparse
import gzip
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .clients.elexon import ElexonClient
from .config import BACKEND_ROOT, DECISION_END, DECISION_START, Settings
from .errors import DataValidationError, WindScopeError
from .normalization import normalize
from .repository import atomic_write, snapshot_digest, write_snapshot
from .schemas import Capture, Snapshot

PUBLICATION_FROM = datetime(2025, 12, 30, tzinfo=UTC)
PUBLICATION_TO = datetime(2026, 2, 3, tzinfo=UTC)
logger = logging.getLogger(__name__)


def windows(start: datetime, end: datetime, days: int = 7):
    while start < end:
        stop = min(start + timedelta(days=days), end)
        yield start, stop
        start = stop  # Inclusive Elexon bounds deliberately overlap; normalization deduplicates.


def build_snapshot(forecast_rows, actual_rows, sources, mode) -> Snapshot:
    forecasts, forecast_report = normalize(forecast_rows, "WINDFOR")
    actuals, actual_report = normalize(actual_rows, "FUELHH")
    payload = Snapshot(
        snapshot_id="pending",
        built_at=datetime.now(UTC),
        decision_start=DECISION_START,
        decision_end=DECISION_END,
        source_mode=mode,
        sources=sources,
        publication_from=PUBLICATION_FROM,
        publication_to=PUBLICATION_TO,
        forecasts=forecasts,
        actuals=actuals,
        forecast_validation=forecast_report,
        actual_validation=actual_report,
    )
    return payload.model_copy(
        update={"snapshot_id": snapshot_digest(payload.model_dump(mode="json"))}
    )


def verified_archive(directory: Path):
    """Promote actual recorded Elexon bodies only after verifying their manifest hashes."""
    manifest = json.loads((directory / "manifest.json").read_text())
    rows, sources = {}, []
    for dataset, filename in (
        ("WINDFOR", "windfor-publications.json.gz"),
        ("FUELHH", "fuelhh-deliveries.json.gz"),
    ):
        item = next(item for item in manifest if Path(item["file"]).name == filename)
        expected_path = directory / "responses" / filename
        body = gzip.decompress(expected_path.read_bytes())
        if hashlib.sha256(body).hexdigest() != item["sha256_uncompressed"]:
            raise DataValidationError("Archived Elexon response failed its provenance checksum.")
        expected_url = "https://data.elexon.co.uk/bmrs/api/v1/datasets/" + dataset + "/stream?"
        if item["status"] != 200 or not item["url"].startswith(expected_url):
            raise DataValidationError("Archive is not a successful official Elexon stream capture.")
        rows[dataset] = json.loads(body)
        if not isinstance(rows[dataset], list) or len(rows[dataset]) != item["row_count"]:
            raise DataValidationError("Archive row count does not match provenance.")
        sources.append(
            Capture(
                url=item["url"],
                retrieved_at=item["retrieved_at"],
                sha256_uncompressed=item["sha256_uncompressed"],
                row_count=len(rows[dataset]),
                raw_file=str(expected_path.resolve()),
            )
        )
    return rows["WINDFOR"], rows["FUELHH"], sources


def fetch_live(client: ElexonClient, raw_directory: Path):
    forecasts, actuals, sources = [], [], []
    # Adjacent-day probes document whether the buffer boundary cuts through relevant revisions.
    bounds = [
        (PUBLICATION_FROM - timedelta(days=1), PUBLICATION_FROM),
        *windows(PUBLICATION_FROM, PUBLICATION_TO),
        (PUBLICATION_TO, PUBLICATION_TO + timedelta(days=1)),
    ]
    for start, end in bounds:
        result = client.stream(
            "WINDFOR",
            {"publishDateTimeFrom": start.isoformat(), "publishDateTimeTo": end.isoformat()},
        )
        save_capture(result, raw_directory, sources)
        if start < PUBLICATION_FROM or end > PUBLICATION_TO:
            normalized, _ = normalize(result.rows, "WINDFOR")
            if any(
                DECISION_START + timedelta(days=1)
                <= row.start_time.date()
                <= DECISION_END + timedelta(days=1)
                for row in normalized
            ):
                raise DataValidationError(
                    "Relevant revisions exist beyond the publication buffer; "
                    "widen it before ingestion."
                )
        else:
            forecasts.extend(result.rows)
    start = DECISION_START + timedelta(days=1)
    delivery_end = DECISION_END + timedelta(days=1)
    while start <= delivery_end:
        end = min(start + timedelta(days=6), delivery_end)
        result = client.stream(
            "FUELHH",
            {
                "settlementDateFrom": start.isoformat(),
                "settlementDateTo": end.isoformat(),
                "fuelType": "WIND",
            },
        )
        save_capture(result, raw_directory, sources)
        actuals.extend(result.rows)
        start = end + timedelta(days=1)
    return forecasts, actuals, sources


def save_capture(result, directory: Path, sources: list[Capture]):
    filename = f"{result.capture.sha256_uncompressed}.json.gz"
    atomic_write(directory / filename, gzip.compress(result.body, mtime=0))
    sources.append(result.capture.model_copy(update={"raw_file": filename}))


def ingest(output: Path, archive: Path | None = None, client: ElexonClient | None = None):
    attempt_path = output.parent / "last-attempt.json"
    owned = client is None and archive is None
    try:
        if archive is not None:
            forecasts, actuals, sources = verified_archive(archive)
            mode = "verified_elexon_archive"
        else:
            client = client or ElexonClient()
            forecasts, actuals, sources = fetch_live(client, BACKEND_ROOT / "data/raw")
            mode = "live_elexon"
        snapshot = build_snapshot(forecasts, actuals, sources, mode)
        write_snapshot(snapshot, output)
        atomic_write(
            attempt_path,
            json.dumps(
                {
                    "status": "success",
                    "at": datetime.now(UTC).isoformat(),
                    "snapshot_id": snapshot.snapshot_id,
                }
            ).encode(),
        )
        return snapshot
    except Exception as exc:
        atomic_write(
            attempt_path,
            json.dumps(
                {
                    "status": "failed",
                    "at": datetime.now(UTC).isoformat(),
                    "reason": str(exc),
                    "last_good_snapshot_preserved": True,
                }
            ).encode(),
        )
        raise
    finally:
        if owned and client is not None:
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Settings().snapshot_path)
    parser.add_argument("--from-verified-archive", type=Path, metavar="RESEARCH_DIRECTORY")
    args = parser.parse_args()
    try:
        snapshot = ingest(args.output, args.from_verified_archive)
    except (WindScopeError, OSError, ValueError, KeyError, StopIteration) as exc:
        parser.exit(1, f"Ingestion failed: {exc}\n")
    print(
        json.dumps(
            {
                "snapshot_id": snapshot.snapshot_id,
                "source_mode": snapshot.source_mode,
                "forecast_revisions": len(snapshot.forecasts),
                "actual_records": len(snapshot.actuals),
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
