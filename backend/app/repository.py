"""Validate and atomically publish one self-contained, checksummed snapshot."""

import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .config import DECISION_END, DECISION_START
from .errors import WindScopeError
from .schemas import Snapshot


def snapshot_digest(payload: dict) -> str:
    content = {key: value for key, value in payload.items() if key != "snapshot_id"}
    body = json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


def validate_snapshot(payload: dict) -> Snapshot:
    snapshot = Snapshot.model_validate(payload)
    if snapshot.decision_start != DECISION_START or snapshot.decision_end != DECISION_END:
        raise ValueError("Snapshot scope must match the fixed January 2026 pilot")
    if snapshot.publication_from >= snapshot.publication_to:
        raise ValueError("Invalid snapshot publication window")
    if not snapshot.sources:
        raise ValueError("Snapshot must include source provenance")
    if snapshot_digest(snapshot.model_dump(mode="json")) != snapshot.snapshot_id:
        raise ValueError("Snapshot integrity checksum does not match")
    for records in (snapshot.forecasts, snapshot.actuals):
        keys = [(r.start_time, r.publish_time) for r in records]
        if len(keys) != len(set(keys)):
            raise ValueError("Normalized snapshot contains duplicate revision keys")
    return snapshot


def atomic_write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".snapshot-", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def write_snapshot(snapshot: Snapshot, path: Path) -> None:
    validate_snapshot(snapshot.model_dump(mode="json"))
    atomic_write(path, gzip.compress(snapshot.model_dump_json().encode(), mtime=0))


def load_snapshot(path: Path) -> Snapshot:
    try:
        payload = json.loads(gzip.decompress(path.read_bytes()))
        return validate_snapshot(payload)
    except (OSError, EOFError, ValueError, TypeError, KeyError, ValidationError) as exc:
        raise WindScopeError(
            "snapshot_unavailable",
            "A valid historical snapshot is unavailable; run ingestion.",
            details={"reason": type(exc).__name__},
        ) from exc
