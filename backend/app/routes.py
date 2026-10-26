from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import AwareDatetime

from .errors import WindScopeError
from .schemas import (
    AccuracyResponse,
    CoverageResponse,
    DailyResponse,
    DayResponse,
    ErrorResponse,
    HealthResponse,
    HistoryResponse,
    OverviewResponse,
)
from .selection import parse_cutoff
from .service import AnalyticsService

router = APIRouter(
    prefix="/api", responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}
)


def get_service(request: Request) -> AnalyticsService:
    return request.app.state.get_service()


def get_cutoff(cutoff: Annotated[str, Query()] = "11:00") -> str:
    parse_cutoff(cutoff)
    return cutoff


Service = Annotated[AnalyticsService, Depends(get_service)]
Cutoff = Annotated[str, Depends(get_cutoff)]


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health(request: Request, response: Response):
    try:
        service = request.app.state.get_service()
        snapshot = service.snapshot
        invalid = (
            snapshot.forecast_validation.invalid_rows + snapshot.actual_validation.invalid_rows
        )
        return HealthResponse(
            status="degraded" if invalid else "ok",
            snapshot_ready=True,
            snapshot_id=snapshot.snapshot_id,
            data_retrieved_at=max(source.retrieved_at for source in snapshot.sources),
            validation_status="gaps_flagged" if invalid else "validated",
        )
    except WindScopeError as exc:
        response.status_code = 503
        return HealthResponse(
            status="degraded",
            snapshot_ready=False,
            validation_status="unavailable",
            issue=exc.message,
        )


@router.get("/overview", response_model=OverviewResponse)
def overview(service: Service, cutoff: Cutoff):
    return service.overview(cutoff)


@router.get("/day", response_model=DayResponse, responses={404: {"model": ErrorResponse}})
def day(service: Service, cutoff: Cutoff, decision: Annotated[date, Query(alias="date")]):
    return service.day(decision, cutoff)


@router.get("/accuracy", response_model=AccuracyResponse)
def accuracy(service: Service, cutoff: Cutoff):
    return service.accuracy(cutoff)


@router.get("/accuracy/daily", response_model=DailyResponse)
def daily(service: Service, cutoff: Cutoff):
    return service.daily(cutoff)


@router.get(
    "/forecast-history", response_model=HistoryResponse, responses={404: {"model": ErrorResponse}}
)
def history(service: Service, cutoff: Cutoff, start_time: Annotated[AwareDatetime, Query()]):
    return service.history(start_time, cutoff)


@router.get("/coverage", response_model=CoverageResponse)
def coverage(service: Service, cutoff: Cutoff):
    return service.coverage(cutoff)
