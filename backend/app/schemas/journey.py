"""Journey Planning Request and Response Schemas."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator

from backend.app.schemas.live import LiveBusCandidateSchema


class JourneyPlanRequest(BaseModel):
    origin_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Origin latitude in WGS84 (-90 to 90)")
    origin_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Origin longitude in WGS84 (-180 to 180)")
    dest_lat: Optional[float] = Field(None, ge=-90.0, le=90.0, description="Destination latitude in WGS84 (-90 to 90)")
    dest_lon: Optional[float] = Field(None, ge=-180.0, le=180.0, description="Destination longitude in WGS84 (-180 to 180)")
    origin_stop_id: Optional[str] = Field(None, description="Direct origin GTFS stop ID")
    dest_stop_id: Optional[str] = Field(None, description="Direct destination GTFS stop ID")
    departure_date: str = Field(
        default="2026-10-01", description="Service date in YYYY-MM-DD format"
    )
    departure_time: str = Field(
        default="08:00:00", description="Departure time in HH:MM:SS format"
    )
    max_walking_distance_m: float = Field(
        default=800.0, ge=50.0, le=3000.0, description="Max access/egress walk radius in meters"
    )
    max_transfers: int = Field(
        default=3, ge=0, le=5, description="Maximum number of transit transfers"
    )
    num_alternatives: int = Field(
        default=3, ge=1, le=5, description="Maximum number of Pareto-optimal alternatives to return"
    )
    use_experimental_ml: bool = Field(
        default=False,
        description="Explicitly opt in to experimental Random Forest candidate predictions (disabled by default)",
    )
    allow_assumed_recurring: bool = Field(
        default=False,
        description="Explicitly opt in to demonstration routing using expired timetable template (disabled by default)",
    )
    ranking_strategy: str = Field(
        default="earliest_arrival",
        description="Ranking strategy: earliest_arrival, fewest_transfers, least_walking, or most_reliable",
    )

    @model_validator(mode="after")
    def validate_endpoints_and_time(self) -> "JourneyPlanRequest":
        # 1. Validate Origin specification
        has_orig_coord = self.origin_lat is not None and self.origin_lon is not None
        has_orig_stop = self.origin_stop_id is not None and len(str(self.origin_stop_id).strip()) > 0
        if not (has_orig_coord or has_orig_stop):
            raise ValueError("Query must specify either (origin_lat, origin_lon) or origin_stop_id.")

        # 2. Validate Destination specification
        has_dest_coord = self.dest_lat is not None and self.dest_lon is not None
        has_dest_stop = self.dest_stop_id is not None and len(str(self.dest_stop_id).strip()) > 0
        if not (has_dest_coord or has_dest_stop):
            raise ValueError("Query must specify either (dest_lat, dest_lon) or dest_stop_id.")

        # 3. Check for identical endpoints
        if has_orig_stop and has_dest_stop and str(self.origin_stop_id) == str(self.dest_stop_id):
            raise ValueError("Origin stop and destination stop cannot be identical.")

        if has_orig_coord and has_dest_coord:
            if abs(self.origin_lat - self.dest_lat) < 1e-5 and abs(self.origin_lon - self.dest_lon) < 1e-5:
                raise ValueError("Origin and destination coordinates are too close (< 1 meter).")

        # 4. Validate Date format
        try:
            datetime.strptime(self.departure_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid departure_date format: '{self.departure_date}'. Expected YYYY-MM-DD.")

        # 5. Validate Time format
        time_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", self.departure_time)
        if not time_match:
            raise ValueError(f"Invalid departure_time format: '{self.departure_time}'. Expected HH:MM:SS.")
        hh, mm, ss = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3) or 0)
        if not (0 <= hh <= 28 and 0 <= mm <= 59 and 0 <= ss <= 59):
            raise ValueError(f"Invalid time values in departure_time: '{self.departure_time}'.")

        return self


class WalkingLegSchema(BaseModel):
    leg_type: str = Field(..., description="ACCESS, TRANSFER, EGRESS, or DIRECT_WALK")
    from_name: str = Field(..., description="Origin node description")
    to_name: str = Field(..., description="Destination node description")
    from_stop_id: Optional[str] = Field(None, description="Starting stop ID if applicable")
    to_stop_id: Optional[str] = Field(None, description="Ending stop ID if applicable")
    start_time_s: float = Field(..., description="Walk start in seconds since midnight")
    end_time_s: float = Field(..., description="Walk end in seconds since midnight")
    duration_s: float = Field(..., description="Walk duration in seconds")
    distance_m: float = Field(..., description="Walk distance in meters")


class TransitLegSchema(BaseModel):
    leg_type: str = Field(default="TRANSIT", description="Always 'TRANSIT' for transit legs")
    route_id: str = Field(..., description="Line route ID")
    trip_id: str = Field(..., description="Trip identifier")
    pattern_id: int = Field(..., description="Route pattern identifier")
    board_stop_id: str = Field(..., description="Boarding stop ID")
    board_stop_name: str = Field(..., description="Boarding stop name")
    alight_stop_id: str = Field(..., description="Alighting stop ID")
    alight_stop_name: str = Field(..., description="Alighting stop name")
    sched_departure_s: float = Field(..., description="Scheduled departure in seconds since midnight")
    sched_arrival_s: float = Field(..., description="Scheduled arrival in seconds since midnight")
    sched_duration_s: float = Field(..., description="Scheduled running duration in seconds")
    board_time_s: float = Field(..., description="Predicted/actual boarding time in seconds since midnight")
    alight_time_s: float = Field(..., description="Predicted/actual alighting time in seconds since midnight")
    ride_duration_s: float = Field(..., description="Predicted/actual in-vehicle ride duration in seconds")
    intermediate_stops: List[str] = Field(default_factory=list, description="Intermediate passed stop IDs")
    prediction_tier: str = Field(..., description="5-tier classification (e.g. LEVEL_1_DIRECT_OBSERVED)")
    prediction_source: str = Field(..., description="Prediction attribution source")
    heuristic_confidence_score: float = Field(
        ..., description="Heuristic ordinal confidence score from 0.0 to 1.0 (NOT a probability)"
    )
    confidence_score_type: str = Field(default="HEURISTIC", description="Explicitly 'HEURISTIC'")
    confidence_explanation: str = Field(..., description="Documented limitations and meaning of the score")
    is_fallback: bool = Field(..., description="Whether a fallback model was applied")
    fallback_reason: Optional[str] = Field(None, description="Fallback diagnostic explanation")
    warning: Optional[str] = Field(None, description="Operational prediction warning")
    timetable_status: str = Field(..., description="Freshness status for this leg's timetable data")
    is_verified_current_service: bool = Field(
        ..., description="Whether service is verified as currently operating (strictly False for expired feed)"
    )
    live_bus: Optional[LiveBusCandidateSchema] = Field(
        default=None,
        description="Verified live candidate bus to board for this transit leg with required safety fallbacks",
    )


class JourneyAccountingSchema(BaseModel):
    access_walking_time_s: float = Field(..., description="Access walk from origin to first stop")
    initial_waiting_time_s: float = Field(..., description="Wait at initial platform until bus departure")
    in_vehicle_duration_s: float = Field(..., description="Sum of all in-vehicle transit legs")
    transfer_walking_time_s: float = Field(..., description="Sum of all transfer footpath walks")
    transfer_waiting_time_s: float = Field(..., description="Sum of all transfer platform waits")
    egress_walking_time_s: float = Field(..., description="Egress walk from final alight stop to destination")
    total_duration_s: float = Field(..., description="Total elapsed journey time")
    discrepancy_s: float = Field(..., description="Identity discrepancy (must be 0.0000)")
    is_valid_identity: bool = Field(..., description="Whether identity mathematically conserves duration")


class JourneyAlternativeSchema(BaseModel):
    journey_id: str = Field(..., description="Unique journey identifier")
    num_transfers: int = Field(..., description="Number of transfers (0 = direct transit)")
    departure_time_s: float = Field(..., description="Origin departure in seconds since midnight")
    arrival_time_s: float = Field(..., description="Destination arrival in seconds since midnight")
    total_journey_duration_s: float = Field(..., description="Total elapsed duration in seconds")
    legs: List[Union[WalkingLegSchema, TransitLegSchema]] = Field(
        ..., description="Ordered list of walking and transit legs"
    )
    accounting: JourneyAccountingSchema = Field(..., description="Exact duration accounting breakdown")
    heuristic_confidence_score: float = Field(
        ..., description="Overall heuristic journey confidence score (NOT a probability)"
    )
    confidence_score_type: str = Field(default="HEURISTIC")
    timetable_status: str = Field(..., description="Timetable status: CURRENT_VERIFIED, ASSUMED_RECURRING, EXPIRED, or UNAVAILABLE")
    is_verified_current_service: bool = Field(
        ..., description="Whether service is verified as currently operating"
    )
    actual_operations_verified: bool = Field(
        default=False,
        description="Whether actual physical bus operations have been independently verified in real time (strictly False)",
    )
    long_transfer_advisory: Optional[str] = Field(
        default=None,
        description="Advisory message when transfer waiting time exceeds 7,200s (2 hours)",
    )
    has_long_transfer_wait: bool = Field(
        default=False,
        description="Whether any transfer waiting period exceeds 7,200s (2 hours)",
    )
    warnings: List[str] = Field(default_factory=list, description="Journey-level warnings and caveats")


class JourneyPlanResponse(BaseModel):
    query_summary: Dict[str, Any] = Field(..., description="Echo of query parameters and execution telemetry")
    journeys_count: int = Field(..., description="Number of alternatives found")
    journeys: List[JourneyAlternativeSchema] = Field(
        default_factory=list, description="Ranked Pareto-optimal journey alternatives"
    )
    timetable_status: str = Field(..., description="Timetable freshness status")
    stale_timetable_warning: Optional[str] = Field(
        None, description="Prominent stale-timetable warning if applicable"
    )
