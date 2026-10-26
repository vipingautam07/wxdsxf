from pathlib import Path

import pytest
from conftest import timestamp
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repository import write_snapshot
from app.schemas import ActualRecord
from app.service import AnalyticsService


@pytest.fixture
def api(small_snapshot, tmp_path):
    path = tmp_path / "snapshot.json.gz"
    write_snapshot(small_snapshot, path)
    with TestClient(create_app(Settings(snapshot_path=path))) as client:
        yield client


@pytest.mark.parametrize(
    "path",
    [
        "/api/health",
        "/api/overview",
        "/api/day?date=2026-01-01",
        "/api/accuracy",
        "/api/accuracy/daily",
        "/api/forecast-history?start_time=2026-01-02T00:00:00Z",
        "/api/coverage",
    ],
)
def test_all_seven_api_contracts(api, path):
    response = api.get(path)
    assert response.status_code == 200, response.text
    assert "NaN" not in response.text and "Infinity" not in response.text


def test_day_is_decision_date_and_has_full_expected_grid(api):
    body = api.get("/api/day", params={"date": "2026-01-01"}).json()
    assert body["summary"]["delivery_date"] == "2026-01-02"
    assert len(body["hours"]) == 24
    first = body["hours"][0]
    assert first["forecast_mw"] == 100 and first["actual_mw"] == 90 and first["error_mw"] == 10
    assert first["selected_publish_time"] == "2026-01-01T11:00:00Z"
    assert body["summary"]["coverage"]["expected_actual_settlement_periods"] == 48
    assert body["historical_reliability"]["metrics"]["matched_hours"] == 0


def test_cutoff_filter_changes_selected_revision(api):
    body = api.get("/api/day", params={"date": "2026-01-01", "cutoff": "10:00"}).json()
    assert body["hours"][0]["forecast_mw"] == 95


def test_history_exposes_post_cutoff_revisions_but_does_not_select_them(api):
    body = api.get("/api/forecast-history", params={"start_time": "2026-01-02T00:00:00Z"}).json()
    assert len(body["revisions"]) == 3
    assert sum(revision["selected"] for revision in body["revisions"]) == 1
    assert body["revisions"][-1]["eligible_at_cutoff"] is False
    assert body["revisions"][-1]["selected"] is False
    assert body["meta"]["history_completeness"] == "bounded_publication_window"


@pytest.mark.parametrize(
    "path,code",
    [
        ("/api/day?date=2025-12-31", 404),
        ("/api/day?date=2026-02-01", 404),
        ("/api/day?date=not-a-date", 422),
        ("/api/day", 422),
        ("/api/accuracy?cutoff=24:00", 422),
        ("/api/forecast-history?start_time=2026-01-02T00:00:00", 422),
        ("/api/forecast-history?start_time=2026-01-02T00:30:00Z", 422),
        ("/api/forecast-history?start_time=2026-02-02T00:00:00Z", 404),
    ],
)
def test_invalid_or_out_of_scope_requests(api, path, code):
    response = api.get(path)
    assert response.status_code == code
    assert response.json()["error"]["code"]


def test_missing_snapshot_has_clear_503(tmp_path):
    with TestClient(create_app(Settings(snapshot_path=tmp_path / "absent.json.gz"))) as client:
        response = client.get("/api/health")
        assert response.status_code == 503
        assert response.json()["process_alive"] is True
        assert response.json()["snapshot_ready"] is False
        response = client.get("/api/overview")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "snapshot_unavailable"


def test_historical_reliability_reselects_actuals_at_cutoff(small_snapshot):
    revised = ActualRecord(
        start_time="2026-01-02T00:00:00Z",
        publish_time="2026-01-03T12:00:00Z",
        generation_mw=800,
        settlement_date="2026-01-02",
        settlement_period=1,
    )
    snapshot = small_snapshot.model_copy(update={"actuals": [*small_snapshot.actuals, revised]})
    service = AnalyticsService(snapshot)
    # Retrospective outturn uses the later revision; January 2 reliability cannot see it.
    assert service.day(timestamp("2026-01-01T00:00:00Z").date(), "11:00").hours[0].actual_mw == 450
    historical = service.day(
        timestamp("2026-01-02T00:00:00Z").date(), "11:00"
    ).historical_reliability
    assert historical.metrics.matched_hours == 1
    assert historical.metrics.mean_bias_mw == 10


def test_coverage_preserves_missing_grid_and_histogram_sample_count(api):
    body = api.get("/api/coverage").json()["coverage"]
    assert body["expected_hours"] == 744
    assert body["matched_hours"] == 1
    assert body["unmatched_hours"] == 743
    assert body["expected_actual_settlement_periods"] == 1488
    assert body["settlement_periods_in_matched_hours"] == 2
    accuracy = api.get("/api/accuracy").json()
    assert sum(item["count"] for item in accuracy["error_distribution"]) == 1
    assert len(accuracy["scatter"]) == 1


def test_cors_permits_configured_origin_only(api):
    allowed = api.options(
        "/api/overview",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = api.options(
        "/api/overview",
        headers={"Origin": "https://unconfigured.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_real_elexon_snapshot_integration():
    path = Path(__file__).resolve().parents[1] / "data/processed/snapshot.json.gz"
    with TestClient(create_app(Settings(snapshot_path=path))) as client:
        body = client.get("/api/day", params={"date": "2026-01-01"}).json()
        assert body["hours"][0]["forecast_mw"] == 18699
        assert body["hours"][0]["selected_publish_time"] == "2026-01-01T09:30:00Z"
        coverage = client.get("/api/coverage").json()["coverage"]
        assert coverage["matched_hours"] == 744
        assert coverage["available_actual_settlement_periods"] == 1488
        assert coverage["unmatched_hours"] == 0
        final_day = client.get("/api/day", params={"date": "2026-01-31"}).json()
        assert final_day["summary"]["delivery_date"] == "2026-02-01"
        assert final_day["summary"]["metrics"]["matched_hours"] == 24
