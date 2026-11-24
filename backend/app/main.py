"""FastAPI Main Application Module."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.router import api_router
from backend.app.config import settings
from backend.app.dependencies import get_journey_planner, get_live_collector

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("delhi_hacks.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown."""
    logger.info("Initializing Journey Planner and loading GTFS timetable into RAM...")
    # Pre-warm singleton during startup so first query doesn't pay cold-start latency
    try:
        planner = get_journey_planner()
        logger.info(
            f"Timetable pre-warmed successfully. Stops: {len(planner.timetable.stops)}, "
            f"Patterns: {len(planner.timetable.patterns)}, Footpaths: {len(planner.timetable.footpaths)}"
        )
        # Pre-warm baseline model, pyproj projection grids, and routing matrices
        planner.plan_journey(
            origin_stop_id="239",
            dest_stop_id="2024",
            departure_time_s=28800.0,
            service_date="2026-10-01",
            allow_assumed_recurring=True,
            max_transfers=1,
        )
        logger.info("Routing engine and M0 baseline model fully warmed.")
    except Exception as e:
        logger.error(f"Failed to pre-warm Journey Planner on startup: {e}")

    # Optionally probe GTFS-RT feed on startup if live streaming is configured
    try:
        collector = get_live_collector()
        if collector.is_enabled and collector.api_key:
            logger.info("Probing live Delhi GTFS-RT stream on startup...")
            status_code, msg = collector.check_feed_availability()
            logger.info(f"Live feed startup probe result: {status_code.value} - {msg}")
    except Exception as live_err:
        logger.warning(f"Live feed startup probe non-fatal exception: {live_err}")

    yield

    logger.info("Shutting down API server and releasing resources...")


def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "FastAPI REST backend exposing the RAPTOR transit journey planner, "
            "5-tier historical traffic prediction hierarchy, and GTFS freshness validation."
        ),
        lifespan=lifespan,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 1. CORS Middleware (Restricted to trusted configurable origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Global Validation Error Handler
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # Sanitize error detail
        errors = exc.errors()
        error_msgs = []
        for err in errors:
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            error_msgs.append(f"{loc}: {msg}")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "detail": "; ".join(error_msgs),
                "error_code": "INVALID_REQUEST_BODY",
            },
        )

    # 3. Global HTTPException Handler (Consistent JSON envelope)
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP_ERROR",
                "detail": str(exc.detail),
                "error_code": f"HTTP_{exc.status_code}",
            },
        )

    # 4. Global Unhandled Exception Handler (Information leakage prevention)
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled internal server error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": "An unexpected error occurred while processing your transit request.",
                "error_code": "INTERNAL_SERVER_ERROR",
            },
        )

    # 4. Root Endpoint
    @app.get("/", tags=["Root"])
    def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "operational_status": settings.OVERALL_OPERATIONAL_STATUS,
            "api_prefix": settings.API_V1_PREFIX,
            "docs": "/docs",
            "redoc": "/redoc",
        }

    # 5. Mount v1 REST API Router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
