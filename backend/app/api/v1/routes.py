"""Transit Routes REST Router."""

from fastapi import APIRouter, Depends, HTTPException, status
from backend.app.dependencies import get_route_service
from backend.app.schemas.common import ErrorResponse
from backend.app.schemas.routes import RouteDetailResponse
from backend.app.services.route_service import RouteService

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get(
    "/{route_id}",
    response_model=RouteDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Route ID not found in timetable"},
    },
)
def get_route(
    route_id: str,
    service: RouteService = Depends(get_route_service),
) -> RouteDetailResponse:
    """Return GTFS route metadata and ordered stop sequences."""
    detail = service.get_route_detail(route_id=route_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' was not found in the GTFS timetable.",
        )
    return detail

