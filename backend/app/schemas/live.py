"""Pydantic schemas for GTFS-RT Live Feed Status and Vehicle Positions."""

from typing import List, Optional
from pydantic import BaseModel, Field


class LiveVehicleItem(BaseModel):
    vehicle_id: str = Field(..., description="Unique bus registration or vehicle ID")
    route_id: Optional[str] = Field(None, description="Assigned transit route ID")
    trip_id: Optional[str] = Field(None, description="Assigned trip ID if provided")
    latitude: float = Field(..., description="Current WGS84 latitude")
    longitude: float = Field(..., description="Current WGS84 longitude")
    bearing: Optional[float] = Field(None, description="Bearing in degrees if provided")
    speed_kmh: Optional[float] = Field(None, description="Speed in km/h if provided")
    timestamp_utc: int = Field(..., description="UTC Unix timestamp of last GPS ping")
    age_seconds: int = Field(..., description="Age in seconds relative to server query time")
    is_fresh: bool = Field(..., description="Whether ping is within staleness limit (900s)")
    is_current: bool = Field(default=True, description="Whether vehicle was reported in the latest snapshot")
    is_out_of_area: bool = Field(default=False, description="Whether vehicle is outside Delhi core bounding box")
    area_classification: str = Field(default="DELHI_CORE", description="DELHI_CORE or NCR_OUT_OF_BOUNDS")
    is_matched_to_gtfs: bool = Field(..., description="Whether route_id matches static GTFS")
    agency: str = Field(default="UNKNOWN_MIXED", description="Operating agency (DTC / Cluster mixed fleet)")
    distance_m: Optional[float] = Field(None, description="Distance from requested proximity coordinate in meters")


class LiveVehiclesResponse(BaseModel):
    total_active_vehicles: int = Field(..., description="Total active vehicles tracked by collector")
    returned_vehicles_count: int = Field(..., description="Number of vehicles in this response")
    current_vehicles_count: Optional[int] = Field(None, description="Number of current snapshot vehicles")
    last_known_vehicles_count: Optional[int] = Field(None, description="Number of retained last-known vehicles")
    out_of_area_count: Optional[int] = Field(None, description="Number of vehicles in NCR out-of-bounds area")
    route_filter: Optional[str] = Field(None, description="Route ID filter applied if any")
    vehicles: List[LiveVehicleItem] = Field(..., description="List of validated live vehicle positions")
    latest_timestamp_utc: Optional[str] = Field(None, description="Latest vehicle timestamp in ISO 8601")
    feed_availability_status: str = Field(..., description="Current feed operational classification")
    disclaimer: str = Field(
        default="Real-time positions reflect raw GTFS-RT telemetry; agency attribution is mixed (Cluster/DTC).",
        description="Disclaimer on data completeness and agency identification",
    )
    search_lat: Optional[float] = Field(None, description="Search center latitude if radius filtering was requested")
    search_lon: Optional[float] = Field(None, description="Search center longitude if radius filtering was requested")
    search_radius_m: Optional[float] = Field(None, description="Search radius in meters if radius filtering was requested")
    viewport_min_lat: Optional[float] = Field(None, description="Viewport minimum latitude if bounding box was requested")
    viewport_max_lat: Optional[float] = Field(None, description="Viewport maximum latitude if bounding box was requested")
    viewport_min_lon: Optional[float] = Field(None, description="Viewport minimum longitude if bounding box was requested")
    viewport_max_lon: Optional[float] = Field(None, description="Viewport maximum longitude if bounding box was requested")
    total_matching_count: Optional[int] = Field(None, description="Total matching vehicles within requested radius before limit truncation")
    current_matching_count: Optional[int] = Field(None, description="Number of current snapshot vehicles within radius")
    stale_matching_count: Optional[int] = Field(None, description="Number of stale/last-known vehicles within radius")


class LiveFeedStatusResponse(BaseModel):
    feed_enabled: bool = Field(
        ..., description="Whether live GTFS-RT streaming is actively enabled and operating"
    )
    feed_configured_enabled: bool = Field(
        ..., description="Whether LIVE_FEED_ENABLED env flag was set to true"
    )
    feed_availability_status: str = Field(
        ..., description="Classification: AVAILABLE_VALIDATED, AVAILABLE_PARTIAL, AUTH_REQUIRED, UNAVAILABLE, or INVALID_DATA"
    )
    endpoint_url: str = Field(
        ..., description="Target Delhi Transport Stack GTFS-RT feed endpoint"
    )
    auth_required: bool = Field(
        default=True, description="Whether authentication is required by the upstream feed"
    )
    auth_configured: bool = Field(
        ..., description="Whether an API key was found in the environment"
    )
    poll_interval_seconds: int = Field(
        ..., description="Configured polling frequency in seconds"
    )
    max_staleness_seconds: int = Field(
        default=900, description="Configured staleness rejection threshold in seconds"
    )
    last_attempt_timestamp_utc: Optional[str] = Field(
        None, description="ISO 8601 timestamp of last probe/poll attempt"
    )
    last_success_timestamp_utc: Optional[str] = Field(
        None, description="ISO 8601 timestamp of last successful feed fetch"
    )
    latest_source_timestamp_utc: Optional[str] = Field(
        None, description="ISO 8601 timestamp of the newest vehicle location ping in feed"
    )
    consecutive_failure_count: int = Field(
        ..., description="Number of consecutive network/auth failures"
    )
    total_polls_count: int = Field(
        ..., description="Total polling attempts dispatched since startup"
    )
    total_success_count: int = Field(
        ..., description="Total successful polls since startup"
    )
    active_vehicles_count: int = Field(
        ..., description="Number of deduplicated, validated vehicle positions currently tracked"
    )
    valid_vehicles_count: Optional[int] = Field(
        None, description="Number of valid in-bounds vehicle positions"
    )
    valid_routes_count: Optional[int] = Field(
        None, description="Number of unique transit routes active in the live stream"
    )
    stale_vehicles_count: Optional[int] = Field(
        None, description="Number of tracked vehicles exceeding the staleness threshold"
    )
    feed_error_category: Optional[str] = Field(
        None, description="Standardized error category if feed is not AVAILABLE_VALIDATED"
    )
    agency_coverage: str = Field(
        default="UNKNOWN_MIXED", description="Agency coverage classification (DTC, Cluster, or UNKNOWN_MIXED)"
    )
    warning: str = Field(
        ..., description="Operational disclaimer and setup guidance"
    )
    overall_operational_status: str = Field(
        default="DEGRADE", description="Governing project status (strictly DEGRADE)"
    )


class LiveBusCandidateSchema(BaseModel):
    identification_status: str = Field(
        ...,
        description="IDENTIFIED_APPROACHING, IDENTIFIED_NEAR, ROUTE_MATCH_UNVERIFIED, PASSED_STOP, or UNIDENTIFIED",
    )
    guidance_message: str = Field(
        ...,
        description="Human-readable passenger boarding guidance and fallbacks",
    )
    vehicle_id: Optional[str] = Field(None, description="Actual bus registration or vehicle ID from GTFS-RT feed")
    route_id: Optional[str] = Field(None, description="Assigned transit route ID")
    trip_id: Optional[str] = Field(None, description="Assigned trip ID from provider")
    trip_headsign: Optional[str] = Field(None, description="Verified trip destination / headsign from GTFS static")
    progress_status: Optional[str] = Field(None, description="APPROACHING, NEAR_BOARDING_STOP, PASSED, or UNVERIFIED")
    distance_to_board_m: Optional[float] = Field(None, description="Distance from vehicle to boarding stop in meters")
    stops_away: Optional[int] = Field(None, description="Number of stops away from boarding stop along trip")
    speed_kmh: Optional[float] = Field(None, description="Current reported speed in km/h")
    source_timestamp_utc: Optional[int] = Field(None, description="UTC Unix timestamp of last GPS ping from feed")
    age_seconds: Optional[int] = Field(None, description="Age in seconds relative to server query time")
    is_fresh: Optional[bool] = Field(None, description="Whether ping is within staleness threshold")
    is_candidate_only: bool = Field(default=True, description="Candidate advisory, not guaranteed boarding assignment")
    disclaimer: str = Field(
        default="Live candidate bus based on real-time GTFS-RT feed (not guaranteed boarding assignment).",
        description="Operational disclaimer",
    )


class SuitableVehicleItem(BaseModel):
    vehicle_id: str = Field(..., description="Unique bus registration number / vehicle ID")
    route_id: str = Field(..., description="Route number")
    trip_id: Optional[str] = Field(None, description="Trip ID")
    trip_headsign: Optional[str] = Field(None, description="Verified destination headsign")
    destination_stop_name: Optional[str] = Field(None, description="Verified destination stop name")
    progress_status: str = Field(..., description="NEAR_BOARDING_STOP or APPROACHING")
    distance_to_board_m: float = Field(..., description="Distance to boarding stop in meters")
    stops_away: Optional[int] = Field(None, description="Number of stops away from boarding stop")
    speed_kmh: Optional[float] = Field(None, description="Speed in km/h")
    latitude: float = Field(..., description="Current latitude (actual GPS or dead-reckoned)")
    longitude: float = Field(..., description="Current longitude (actual GPS or dead-reckoned)")
    bearing: Optional[float] = Field(None, description="Bearing in degrees")
    timestamp_utc: int = Field(..., description="Unix UTC timestamp of genuine GPS ping")
    age_seconds: int = Field(..., description="Telemetry age in seconds")
    is_fresh: bool = Field(..., description="Freshness status (within 900s)")
    is_current: bool = Field(default=True, description="Reported in latest snapshot")
    is_verified_suitable: bool = Field(default=True, description="Verified suitable for this journey")
    is_verified_destination: bool = Field(default=True, description="Trip is verified to reach destination")
    guidance_message: str = Field(..., description="Actionable passenger guidance")
    # Dead reckoning & GPS provenance fields
    position_source: str = Field(default="GPS", description="'GPS' or 'DEAD_RECKONED'")
    is_dead_reckoned: bool = Field(default=False, description="True if position is estimated between GPS pings")
    last_gps_latitude: float = Field(..., description="Last genuine GPS latitude")
    last_gps_longitude: float = Field(..., description="Last genuine GPS longitude")
    last_gps_timestamp: int = Field(..., description="Unix UTC timestamp of last genuine GPS ping")
    position_timestamp: int = Field(..., description="Unix UTC timestamp when current position was estimated")
    prediction_age_seconds: int = Field(default=0, description="Seconds elapsed since last genuine GPS update")
    uncertainty_meters: float = Field(default=15.0, description="Spatial uncertainty in meters")
    route_progress_meters: Optional[float] = Field(None, description="Distance along route corridor shape in meters")
    last_prediction_error_meters: Optional[float] = Field(None, description="Drift error in meters between predicted position and genuine GPS")
    last_correction_distance_meters: Optional[float] = Field(None, description="Distance delta in meters applied during last GPS recalibration")
    correction_status: str = Field(default="GPS_ANCHOR_VERIFIED", description="Tracking status: GPS_ANCHOR_VERIFIED, CALIBRATED_ERROR_CORRECTED, DEAD_RECKONING_ACTIVE, STATIONARY_HOLD, EXCEEDED_MAX_AGE_STALE")
    last_gps_observation_time: Optional[str] = Field(None, description="IST formatted timestamp of last genuine GPS observation")
    latest_position_calculation_time: Optional[str] = Field(None, description="IST formatted timestamp of current position calculation")
    next_expected_update_time: Optional[str] = Field(None, description="IST formatted timestamp of next expected 15-second calculation")
    anomaly_flags: List[str] = Field(default_factory=list, description="Anomaly flags detected for this vehicle")
    has_anomalies: bool = Field(default=False, description="True if any anomaly is flagged")
    gps_accuracy_status: str = Field(default="NOMINAL", description="NOMINAL, ANOMALY_FLAGGED, or REJECTED")


class SuitableVehiclesResponse(BaseModel):
    route_id: str = Field(..., description="Transit route ID")
    board_stop_id: str = Field(..., description="Boarding stop ID")
    alight_stop_id: str = Field(..., description="Alighting stop ID")
    suitable_count: int = Field(..., description="Number of verified suitable vehicles")
    vehicles: List[SuitableVehicleItem] = Field(default_factory=list, description="Verified suitable vehicles")
    fallback_message: Optional[str] = Field(None, description="Fallback message when no suitable bus is available")
    diagnostic_detail: Optional[str] = Field(None, description="Diagnostic explanation of why no live bus is available")
    disclaimer: str = Field(
        default="Live candidate bus based on real-time GTFS-RT feed (not guaranteed boarding assignment).",
        description="Disclaimer on real-time candidate nature"
    )
    upstream_feed_timestamp_utc: Optional[int] = Field(None, description="UTC timestamp of upstream GTFS-RT feed snapshot")
    upstream_feed_age_seconds: Optional[int] = Field(None, description="Age in seconds of upstream GTFS-RT feed snapshot")
    poll_interval_seconds: int = Field(default=15, description="Target priority polling interval in seconds")


