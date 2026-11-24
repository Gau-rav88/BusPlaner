"""Master API v1 Router."""

from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.timetable import router as timetable_router
from backend.app.api.v1.journeys import router as journeys_router
from backend.app.api.v1.stops import router as stops_router
from backend.app.api.v1.routes import router as routes_router
from backend.app.api.v1.live import router as live_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(timetable_router)
api_router.include_router(journeys_router)
api_router.include_router(stops_router)
api_router.include_router(routes_router)
api_router.include_router(live_router)

