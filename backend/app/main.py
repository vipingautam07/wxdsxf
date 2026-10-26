import logging
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .errors import WindScopeError
from .repository import load_snapshot
from .routes import router
from .service import AnalyticsService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    application = FastAPI(
        title="WindScope API",
        version="0.1.0",
        description=(
            "Historical GB wind forecast intelligence. Error = forecast − actual; units MW."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )
    lock = Lock()

    def get_service():
        with lock:
            if not hasattr(application.state, "analytics"):
                application.state.analytics = AnalyticsService(
                    load_snapshot(settings.snapshot_path)
                )
            return application.state.analytics

    application.state.get_service = get_service

    @application.exception_handler(WindScopeError)
    async def domain_error(request: Request, exc: WindScopeError):
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def request_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Request parameters failed validation.",
                    "details": {
                        "fields": [
                            {"location": list(e["loc"]), "message": e["msg"], "type": e["type"]}
                            for e in exc.errors()
                        ]
                    },
                }
            },
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logger.error("Unhandled API error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred.",
                    "details": None,
                }
            },
        )

    application.include_router(router)
    return application


app = create_app()
