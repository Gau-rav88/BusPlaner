"""Timetable Freshness REST Router."""

from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_planner_service
from backend.app.schemas.timetable import TimetableStatusResponse
from backend.app.services.planner_service import PlannerService

router = APIRouter(prefix="/timetable", tags=["Timetable"])


@router.get("/status", response_model=TimetableStatusResponse)
def get_timetable_status(
    service_date: str = Query("2026-10-01", description="Service date to evaluate (YYYY-MM-DD)"),
    allow_assumed_recurring: bool = Query(
        False, description="Whether demonstration recurring mode is opted into (default False)"
    ),
    service: PlannerService = Depends(get_planner_service),
) -> TimetableStatusResponse:
    """Return GTFS timetable feed validity, expiration status, and demonstration mode availability."""
    meta = service.get_timetable_status(
        service_date=service_date,
        allow_assumed_recurring=allow_assumed_recurring,
    )
    return TimetableStatusResponse(**meta)

