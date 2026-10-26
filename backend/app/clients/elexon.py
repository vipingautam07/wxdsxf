"""Bounded, retrying client for the two permitted official JSON stream endpoints."""

import hashlib
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from ..config import ELEXON_BASE
from ..errors import DataValidationError, SourceError
from ..schemas import Capture


@dataclass(frozen=True)
class StreamResult:
    rows: list[dict]
    body: bytes
    capture: Capture


class ElexonClient:
    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.client = client or httpx.Client(
            base_url=ELEXON_BASE + "/",
            timeout=httpx.Timeout(45, connect=10),
            headers={"Accept": "application/json", "User-Agent": "WindScope-pilot/0.1"},
        )
        self.owns_client = client is None
        if attempts < 1:
            raise ValueError("At least one request attempt is required")
        self.attempts, self.sleep = attempts, sleep

    def close(self):
        if self.owns_client:
            self.client.close()

    @staticmethod
    def retry_delay(response: httpx.Response | None, attempt: int) -> float:
        if response is not None and (value := response.headers.get("Retry-After")):
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    delay = 2**attempt
            # Never retry sooner than requested. An excessive delay becomes an explicit failure.
            if delay > 60:
                raise SourceError("Elexon requested a long retry delay; retry ingestion later.")
            return max(0.0, delay)
        return min(2**attempt + random.uniform(0, 0.25), 10)

    def stream(self, dataset: str, params: dict[str, str]) -> StreamResult:
        if dataset not in {"FUELHH", "WINDFOR"}:
            raise ValueError("Only FUELHH and WINDFOR datasets are supported")
        for attempt in range(self.attempts):
            response = None
            try:
                response = self.client.get(f"datasets/{dataset}/stream", params=params)
            except httpx.TransportError as exc:
                if attempt == self.attempts - 1:
                    raise SourceError(
                        "Cannot reach Elexon; no replacement data was generated."
                    ) from exc
            else:
                if response.status_code == 200:
                    try:
                        rows = response.json()
                    except (json.JSONDecodeError, UnicodeError) as exc:
                        raise DataValidationError("Elexon returned invalid JSON.") from exc
                    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                        raise DataValidationError(
                            "Expected Elexon stream to return a JSON array of objects."
                        )
                    return StreamResult(
                        rows,
                        response.content,
                        Capture(
                            url=str(response.request.url),
                            retrieved_at=datetime.now(UTC),
                            sha256_uncompressed=hashlib.sha256(response.content).hexdigest(),
                            row_count=len(rows),
                        ),
                    )
                if response.status_code != 429 and response.status_code < 500:
                    raise SourceError(
                        "Elexon rejected the dataset request.",
                        {"upstream_status": response.status_code, "dataset": dataset},
                    )
                if attempt == self.attempts - 1:
                    raise SourceError(
                        "Elexon remains unavailable after bounded retries.",
                        {"upstream_status": response.status_code, "dataset": dataset},
                    )
            self.sleep(self.retry_delay(response, attempt))
        raise AssertionError("Unreachable request state")
