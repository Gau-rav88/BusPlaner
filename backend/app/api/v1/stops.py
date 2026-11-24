"""Transit Stops REST Router."""

from fastapi import APIRouter, Depends, HTTPException, Query
from backend.app.dependencies import get_stop_service
from backend.app.schemas.stops import NearbyStopsResponse, StopCrosswalkResponse, StopSearchResponse
from backend.app.services.stop_service import StopService

router = APIRouter(prefix="/stops", tags=["Stops"])


@router.get("/search", response_model=StopSearchResponse)
def search_stops(
    query: str = Query(..., min_length=1, description="Stop name substring to match"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results to return"),
    service: StopService = Depends(get_stop_service),
) -> StopSearchResponse:
    """Search GTFS physical stops by name substring."""
    stops = service.search_stops(query=query, limit=limit)
    return StopSearchResponse(
        query=query,
        total=len(stops),
        stops=stops,
    )


@router.get("/nearby", response_model=NearbyStopsResponse)
def get_nearby_stops(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Origin latitude in WGS84"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Origin longitude in WGS84"),
    radius_m: float = Query(800.0, ge=50.0, le=3000.0, description="Search radius in meters"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results to return"),
    service: StopService = Depends(get_stop_service),
) -> NearbyStopsResponse:
    """Find physical stops within walking radius of coordinate."""
    nearby = service.find_nearby_stops(lat=lat, lon=lon, radius_m=radius_m, limit=limit)
    return NearbyStopsResponse(
        origin_lat=lat,
        origin_lon=lon,
        radius_m=radius_m,
        total=len(nearby),
        stops=nearby,
    )


@router.get("/crosswalk/{legacy_stop_id}", response_model=StopCrosswalkResponse)
def get_stop_crosswalk(
    legacy_stop_id: str,
    service: StopService = Depends(get_stop_service),
) -> StopCrosswalkResponse:
    """Lookup legacy GTFS stop identifier crosswalk mapping to DLM1."""
    mapping = service.get_crosswalk(legacy_stop_id)
    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Legacy stop ID '{legacy_stop_id}' not found in crosswalk catalog.",
        )
    return mapping

