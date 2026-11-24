"""Health Check REST Router."""

import os
from fastapi import APIRouter, Depends
from backend.app.config import Settings
from backend.app.dependencies import get_journey_planner, get_live_collector, get_settings
from backend.app.schemas.health import HealthResponse
from backend.core.journey_planner import JourneyPlanner
from backend.realtime.gtfs_rt import LiveFeedCollector

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
def get_health(
    settings: Settings = Depends(get_settings),
    planner: JourneyPlanner = Depends(get_journey_planner),
    collector: LiveFeedCollector = Depends(get_live_collector),
) -> HealthResponse:
    """Return backend operational status, versions, and data readiness."""
    db_ok = os.path.exists(settings.DB_PATH)
    gtfs_ok = planner.timetable is not None and len(planner.timetable.stops) > 0
    model_ok = planner.baseline_model is not None and planner.baseline_model.is_fitted

    return HealthResponse(
        application_status="ok" if (db_ok and gtfs_ok) else "degraded",
        backend_version=settings.APP_VERSION,
        database_available=db_ok,
        gtfs_loaded=gtfs_ok,
        model_available=model_ok,
        overall_operational_status=settings.OVERALL_OPERATIONAL_STATUS,
        live_feed_status=collector.availability_status.value,
        live_feed_enabled=collector.is_enabled and (collector.availability_status.value == "AVAILABLE_VALIDATED"),
    )

