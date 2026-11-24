"""Transit Journey Planning REST Router."""

from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.dependencies import get_planner_service
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.journey import JourneyPlanRequest, JourneyPlanResponse
from backend.app.services.planner_service import (
    ExpiredTimetableException,
    PlannerService,
    TimetableUnavailableException,
)

router = APIRouter(prefix="/journeys", tags=["Journeys"])


@router.post(
    "/plan",
    response_model=JourneyPlanResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Expired timetable without demonstration opt-in"},
        422: {"model": ErrorResponse, "description": "Validation error or invalid coordinates/time"},
        503: {"model": ErrorResponse, "description": "Timetable data unavailable"},
    },
)
def plan_journey(
    request: JourneyPlanRequest,
    service: PlannerService = Depends(get_planner_service),
) -> JourneyPlanResponse:
    """Plan transit journeys using RAPTOR and 5-tier traffic prediction hierarchy."""
    try:
        return service.plan_journey(request)
    except ExpiredTimetableException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "EXPIRED_TIMETABLE",
                "detail": e.message,
                "feed_end_date": e.feed_end_date,
                "requested_date": e.requested_date,
                "action": "Set allow_assumed_recurring: true in your request body to evaluate under demonstration mode.",
            },
        )
    except TimetableUnavailableException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "TIMETABLE_UNAVAILABLE",
                "detail": str(e),
                "timetable_status": "UNAVAILABLE",
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVALID_QUERY_PARAMETERS",
                "detail": str(e),
            },
        )

