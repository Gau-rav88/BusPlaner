"""GTFS-Realtime Live Feed Status and Vehicle Positions REST Router."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from backend.app.dependencies import get_live_collector
from backend.app.schemas.live import (
    LiveBusCandidateSchema,
    LiveFeedStatusResponse,
    LiveVehicleItem,
    LiveVehiclesResponse,
    SuitableVehicleItem,
    SuitableVehiclesResponse,
)
from backend.realtime.gtfs_rt import LiveFeedCollector
from backend.realtime.matcher import JourneyBusMatcher

router = APIRouter(prefix="/live", tags=["Real-Time GTFS"])

# Module-level matcher instance
_matcher = JourneyBusMatcher()


@router.get("/status", response_model=LiveFeedStatusResponse)
def get_live_feed_status(
    probe: bool = Query(
        False,
        description="Whether to dispatch a live network probe to the upstream Transport Stack endpoint",
    ),
    collector: LiveFeedCollector = Depends(get_live_collector),
) -> LiveFeedStatusResponse:
    """Query Delhi GTFS-RT feed availability, authentication status, and active vehicle counts."""
    if probe:
        collector.refresh_if_expired(force=True)
    elif collector.api_key:
        collector.refresh_if_expired()

    payload = collector.get_status_payload()
    return LiveFeedStatusResponse(**payload)


@router.get("/vehicles", response_model=LiveVehiclesResponse)
def get_live_vehicles(
    route_id: Optional[str] = Query(
        None,
        description="Optional transit route ID filter (e.g. '1598' or '1657')",
    ),
    lat: Optional[float] = Query(
        None,
        ge=-90.0,
        le=90.0,
        description="Optional latitude for proximity filtering around origin / passenger location / map center",
    ),
    lon: Optional[float] = Query(
        None,
        ge=-180.0,
        le=180.0,
        description="Optional longitude for proximity filtering around origin / passenger location / map center",
    ),
    radius_m: Optional[float] = Query(
        None,
        ge=50.0,
        le=50000.0,
        description="Optional spatial radius in meters around (lat, lon)",
    ),
    min_lat: Optional[float] = Query(
        None,
        ge=-90.0,
        le=90.0,
        description="Optional minimum latitude for viewport bounding box",
    ),
    max_lat: Optional[float] = Query(
        None,
        ge=-90.0,
        le=90.0,
        description="Optional maximum latitude for viewport bounding box",
    ),
    min_lon: Optional[float] = Query(
        None,
        ge=-180.0,
        le=180.0,
        description="Optional minimum longitude for viewport bounding box",
    ),
    max_lon: Optional[float] = Query(
        None,
        ge=-180.0,
        le=180.0,
        description="Optional maximum longitude for viewport bounding box",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=5000,
        description="Maximum number of active vehicles to return (default 500 when radius/viewport filtering, 5000 for diagnostics)",
    ),
    include_stale: bool = Query(
        True,
        description="Whether to include retained last-known vehicles not in the latest snapshot",
    ),
    include_out_of_area: bool = Query(
        True,
        description="Whether to include vehicles in NCR out-of-bounds area",
    ),
    collector: LiveFeedCollector = Depends(get_live_collector),
) -> LiveVehiclesResponse:
    """Query currently tracked real-time bus locations from Delhi Transport Stack GTFS-RT.

    Supports radius-based discovery around (lat, lon) and/or viewport bounding-box.
    Uses thread-safe 20s cache shared across all clients to avoid redundant upstream fetches.
    """
    if collector.api_key:
        collector.refresh_if_expired()

    # Determine effective limit: 500 when location/radius/viewport is requested, 5000 when citywide diagnostics
    if limit is not None:
        effective_limit = limit
    elif (lat is not None and lon is not None) or (min_lat is not None and max_lat is not None):
        effective_limit = 500
    else:
        effective_limit = 5000

    raw_items, summary = collector.get_live_vehicles(
        route_id=route_id,
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        limit=effective_limit,
        include_stale=include_stale,
        include_out_of_area=include_out_of_area,
        return_summary=True,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
    )
    items = [LiveVehicleItem(**item) for item in raw_items]

    status_payload = collector.get_status_payload()
    total_active = len(collector.active_vehicles) + len(collector.out_of_area_vehicles)

    return LiveVehiclesResponse(
        total_active_vehicles=total_active,
        returned_vehicles_count=len(items),
        current_vehicles_count=len(collector.active_vehicles),
        last_known_vehicles_count=len(collector.last_known_vehicles),
        out_of_area_count=len(collector.out_of_area_vehicles),
        route_filter=route_id,
        vehicles=items,
        latest_timestamp_utc=status_payload.get("latest_source_timestamp_utc"),
        feed_availability_status=collector.availability_status.value,
        disclaimer=(
            "Real-time positions reflect raw GTFS-RT telemetry from Delhi Transport Stack; "
            "agency attribution is mixed (Cluster/DTC). Operating under DEGRADE status."
        ),
        search_lat=summary.get("search_lat"),
        search_lon=summary.get("search_lon"),
        search_radius_m=summary.get("search_radius_m"),
        viewport_min_lat=summary.get("viewport_min_lat"),
        viewport_max_lat=summary.get("viewport_max_lat"),
        viewport_min_lon=summary.get("viewport_min_lon"),
        viewport_max_lon=summary.get("viewport_max_lon"),
        total_matching_count=summary.get("total_matching_count"),
        current_matching_count=summary.get("current_matching_count"),
        stale_matching_count=summary.get("stale_matching_count"),
    )


@router.get("/suitable-vehicles", response_model=SuitableVehiclesResponse)
def get_suitable_vehicles(
    route_id: str = Query(..., description="Transit route ID (e.g. '1598')"),
    board_stop_id: str = Query(..., description="Boarding GTFS stop ID"),
    alight_stop_id: str = Query(..., description="Alighting GTFS stop ID"),
    collector: LiveFeedCollector = Depends(get_live_collector),
) -> SuitableVehiclesResponse:
    """Retrieve ONLY live buses verified as suitable for the selected journey's boarding and alighting stops.

    Strictly excludes:
    - Vehicles travelling in the opposite direction.
    - Vehicles that do not serve the destination stop.
    - Vehicles that have already passed the boarding stop (PASSED).
    - Vehicles with unverified trips or off-corridor positions.
    """
    if collector.api_key:
        collector.refresh_if_expired()

    active_pool = (
        list(collector.active_vehicles.values())
        + list(collector.out_of_area_vehicles.values())
        + list(collector.last_known_vehicles.values())
    )
    suitable_items = _matcher.get_suitable_buses_for_leg(
        route_id=route_id,
        board_stop_id=board_stop_id,
        alight_stop_id=alight_stop_id,
        active_vehicles=active_pool,
    )

    fallback_msg = None
    diagnostic_detail = None
    if not suitable_items:
        fallback_msg = "No verified live bus is currently available for this journey."
        clean_route = str(route_id or "").strip()
        vehicles_on_route = [
            v for v in active_pool
            if str(v.route_id or "").strip() == clean_route and v.is_valid_coordinates
        ]
        if not vehicles_on_route:
            diagnostic_detail = (
                f"0 buses currently reporting on Route {clean_route} in live GTFS-RT feed (depot standby or off-peak hours)."
            )
        else:
            diagnostic_detail = (
                f"{len(vehicles_on_route)} bus(es) active on Route {clean_route}, but none currently approaching your boarding stop in this direction."
            )

    metrics = collector.get_upstream_feed_metrics()

    return SuitableVehiclesResponse(
        route_id=route_id,
        board_stop_id=board_stop_id,
        alight_stop_id=alight_stop_id,
        suitable_count=len(suitable_items),
        vehicles=[SuitableVehicleItem(**item) for item in suitable_items],
        fallback_message=fallback_msg,
        diagnostic_detail=diagnostic_detail,
        disclaimer=(
            "Live candidate bus based on real-time GTFS-RT feed (not guaranteed boarding assignment)."
        ),
        upstream_feed_timestamp_utc=metrics.get("latest_feed_header_timestamp"),
        upstream_feed_age_seconds=metrics.get("upstream_feed_age_seconds"),
        poll_interval_seconds=15,
    )


@router.get("/gps-audit-log")
def get_gps_audit_log(
    vehicle_id: Optional[str] = Query(None, description="Optional vehicle ID filter"),
    route_id: Optional[str] = Query(None, description="Optional route ID filter"),
    limit: int = Query(100, ge=1, le=1000, description="Max audit entries to return"),
):
    """Retrieve structured audit log of GPS observations, dead reckoning steps, and anomaly events."""
    return _matcher.get_gps_audit_log(vehicle_id=vehicle_id, route_id=route_id, limit=limit)


@router.get("/match-bus", response_model=LiveBusCandidateSchema)
def match_live_bus(
    route_id: str = Query(..., description="Transit route ID (e.g. '1598')"),
    board_stop_id: str = Query(..., description="Boarding GTFS stop ID"),
    alight_stop_id: str = Query(..., description="Alighting GTFS stop ID"),
    sched_departure_s: Optional[float] = Query(None, description="Scheduled departure time in seconds since midnight"),
    collector: LiveFeedCollector = Depends(get_live_collector),
) -> LiveBusCandidateSchema:
    """Cross-reference live GTFS-RT vehicles against static GTFS to identify the candidate bus to board."""
    if collector.api_key:
        collector.refresh_if_expired()

    active_list = list(collector.active_vehicles.values())
    match_dict = _matcher.match_bus_for_leg(
        route_id=route_id,
        board_stop_id=board_stop_id,
        alight_stop_id=alight_stop_id,
        active_vehicles=active_list,
        sched_departure_s=sched_departure_s,
    )
    return LiveBusCandidateSchema(**match_dict)


