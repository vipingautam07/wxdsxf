import gzip
import json
from pathlib import Path

import httpx
import pytest
from conftest import forecast, timestamp

from app.clients.elexon import ElexonClient
from app.errors import DataValidationError, SourceError, WindScopeError
from app.ingestion import ingest, verified_archive, windows
from app.repository import load_snapshot, write_snapshot


def mock_client(handler, **kwargs):
    http = httpx.Client(
        base_url="https://data.elexon.co.uk/bmrs/api/v1/", transport=httpx.MockTransport(handler)
    )
    return ElexonClient(http, **kwargs)


def test_official_stream_contract_and_query_parameters():
    def handler(request):
        assert request.url.path == "/bmrs/api/v1/datasets/WINDFOR/stream"
        assert request.url.params["publishDateTimeFrom"] == "2026-01-01T00:00:00Z"
        return httpx.Response(200, json=[forecast()])

    client = mock_client(handler)
    result = client.stream("WINDFOR", {"publishDateTimeFrom": "2026-01-01T00:00:00Z"})
    assert result.rows == [forecast()]
    assert result.capture.row_count == 1
    assert len(result.capture.sha256_uncompressed) == 64


def test_429_honors_retry_after_and_recovers():
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "2"})
            if len(calls) == 1
            else httpx.Response(200, json=[])
        )

    result = mock_client(handler, sleep=sleeps.append).stream("WINDFOR", {})
    assert result.rows == []
    assert len(calls) == 2 and sleeps == [2]


def test_transport_failures_and_server_errors_have_bounded_retries():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("test transport failure", request=request)
        return httpx.Response(503)

    with pytest.raises(SourceError, match="bounded retries"):
        mock_client(handler, attempts=3, sleep=lambda _: None).stream("FUELHH", {})
    assert len(calls) == 3


def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400)

    with pytest.raises(SourceError, match="rejected"):
        mock_client(handler).stream("WINDFOR", {})
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [{"data": []}, [1], None])
def test_wrong_stream_envelope_is_rejected(payload):
    with pytest.raises(DataValidationError, match="JSON array"):
        mock_client(lambda _: httpx.Response(200, content=json.dumps(payload).encode())).stream(
            "WINDFOR", {}
        )


def test_invalid_json_is_rejected():
    with pytest.raises(DataValidationError, match="invalid JSON"):
        mock_client(lambda _: httpx.Response(200, content=b"<html>unavailable</html>")).stream(
            "WINDFOR", {}
        )


def test_long_retry_delay_fails_without_retrying_early():
    with pytest.raises(SourceError, match="long retry delay"):
        mock_client(lambda _: httpx.Response(429, headers={"Retry-After": "600"})).stream(
            "WINDFOR", {}
        )


def test_only_requested_datasets_allowed():
    with pytest.raises(ValueError, match="Only FUELHH"):
        mock_client(lambda _: httpx.Response(200, json=[])).stream("FUELINST", {})


def test_publication_windows_share_inclusive_boundaries():
    result = list(windows(timestamp("2026-01-01T00:00:00Z"), timestamp("2026-01-16T00:00:00Z")))
    assert len(result) == 3
    assert result[0][1] == result[1][0]
    assert result[-1][1] == timestamp("2026-01-16T00:00:00Z")


def test_snapshot_roundtrip_and_integrity(small_snapshot, tmp_path):
    path = tmp_path / "snapshot.json.gz"
    write_snapshot(small_snapshot, path)
    assert load_snapshot(path).snapshot_id == small_snapshot.snapshot_id
    body = json.loads(gzip.decompress(path.read_bytes()))
    body["forecasts"][0]["generation_mw"] = 123456
    path.write_bytes(gzip.compress(json.dumps(body).encode()))
    with pytest.raises(WindScopeError, match="valid historical snapshot"):
        load_snapshot(path)


def test_failed_ingestion_preserves_last_good_snapshot(small_snapshot, tmp_path, monkeypatch):
    path = tmp_path / "snapshot.json.gz"
    write_snapshot(small_snapshot, path)
    original = path.read_bytes()
    monkeypatch.setattr(
        "app.ingestion.verified_archive",
        lambda _: ([forecast(float("inf"))], [], small_snapshot.sources),
    )
    with pytest.raises(DataValidationError):
        ingest(path, archive=tmp_path)
    assert path.read_bytes() == original
    attempt = json.loads((tmp_path / "last-attempt.json").read_text())
    assert attempt["status"] == "failed" and attempt["last_good_snapshot_preserved"]


def test_archive_checksum_is_verified(tmp_path):
    (tmp_path / "responses").mkdir()
    (tmp_path / "responses/windfor-publications.json.gz").write_bytes(gzip.compress(b"[]"))
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            [
                {
                    "file": "responses/windfor-publications.json.gz",
                    "sha256_uncompressed": "wrong",
                }
            ]
        )
    )
    with pytest.raises(DataValidationError, match="provenance checksum"):
        verified_archive(tmp_path)


def test_live_ingestion_rejects_revisions_outside_buffer(tmp_path, monkeypatch):
    from app.ingestion import fetch_live

    client = mock_client(lambda _: httpx.Response(200, json=[forecast()]))
    with pytest.raises(DataValidationError, match="beyond the publication buffer"):
        fetch_live(client, tmp_path)


def test_verified_research_archive_is_real_and_complete():
    root = Path(__file__).resolve().parents[2] / "docs/research"
    forecasts, actuals, sources = verified_archive(root)
    assert len(forecasts) == 20440 and len(actuals) == 1488
    assert all(source.url.startswith("https://data.elexon.co.uk/") for source in sources)
