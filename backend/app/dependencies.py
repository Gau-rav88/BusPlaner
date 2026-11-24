"""FastAPI Dependency Injection Module."""

import os
from typing import Optional
from fastapi import Depends

from backend.app.config import Settings, settings
from backend.core.journey_planner import JourneyPlanner
from backend.app.services.planner_service import PlannerService
from backend.app.services.stop_service import StopService
from backend.app.services.route_service import RouteService
from backend.realtime.gtfs_rt import LiveFeedCollector

# In-memory singleton container
_planner_instance: Optional[JourneyPlanner] = None
_collector_instance: Optional[LiveFeedCollector] = None


def get_settings() -> Settings:
    """Return application configuration settings."""
    return settings


def get_journey_planner() -> JourneyPlanner:
    """Return cached JourneyPlanner singleton, initializing if necessary."""
    global _planner_instance
    if _planner_instance is None:
        db_path = settings.DB_PATH
        if not os.path.exists(db_path):
            # Check fallback to serving DB
            alt_db = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "data", "serving", "delhi_bus.db"
            )
            if os.path.exists(alt_db):
                db_path = alt_db

        _planner_instance = JourneyPlanner.create_default(
            db_path=db_path,
            fit_baseline=True,
        )
    return _planner_instance


def set_journey_planner(instance: JourneyPlanner):
    """Override JourneyPlanner instance (used for testing and teardown)."""
    global _planner_instance
    _planner_instance = instance


def get_live_collector() -> LiveFeedCollector:
    """Return cached LiveFeedCollector singleton, initializing with application settings."""
    global _collector_instance
    if _collector_instance is None:
        known_routes = set()
        try:
            if _planner_instance and _planner_instance.timetable:
                known_routes = set(_planner_instance.timetable.routes.keys())
        except Exception:
            pass

        # In automated test runner, preserve unconfigured default unless overridden
        in_pytest = "PYTEST_CURRENT_TEST" in os.environ
        api_key = os.getenv("DELHI_TRANSPORTSTACK_API_KEY", "") if in_pytest else (
            os.getenv("DELHI_TRANSPORTSTACK_API_KEY", "") or settings.DELHI_TRANSPORTSTACK_API_KEY
        )
        is_enabled = (
            os.getenv("LIVE_FEED_ENABLED", "false").lower() == "true"
            if in_pytest
            else settings.LIVE_FEED_ENABLED
        )

        _collector_instance = LiveFeedCollector(
            endpoint_url=settings.DELHI_GTFS_RT_URL,
            api_key=api_key,
            poll_interval_seconds=settings.LIVE_FEED_POLL_INTERVAL_SECONDS,
            is_enabled=is_enabled,
            known_route_ids=known_routes,
            max_staleness_seconds=settings.LIVE_FEED_STALENESS_SECONDS,
        )
    return _collector_instance


def get_planner_service(
    planner: JourneyPlanner = Depends(get_journey_planner),
    collector: LiveFeedCollector = Depends(get_live_collector),
) -> PlannerService:
    """Return PlannerService instance."""
    return PlannerService(planner, collector=collector)


def get_stop_service(
    planner: JourneyPlanner = Depends(get_journey_planner),
) -> StopService:
    """Return StopService instance."""
    return StopService(planner.timetable)


def get_route_service(
    planner: JourneyPlanner = Depends(get_journey_planner),
) -> RouteService:
    """Return RouteService instance."""
    return RouteService(planner.timetable)



def set_live_collector(instance: Optional[LiveFeedCollector]) -> None:
    """Override LiveFeedCollector instance (used for testing and teardown)."""
    global _collector_instance
    _collector_instance = instance


