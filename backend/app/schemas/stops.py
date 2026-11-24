"""Transit Stops Schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class StopSchema(BaseModel):
    stop_id: str = Field(..., description="GTFS stop identifier")
    stop_name: str = Field(..., description="Human-readable physical stop name")
    lat: float = Field(..., description="WGS84 Latitude")
    lon: float = Field(..., description="WGS84 Longitude")


class NearbyStopSchema(StopSchema):
    distance_m: float = Field(..., description="Walking Euclidean distance in meters")
    walking_time_s: float = Field(..., description="Estimated walking time in seconds")


class StopSearchResponse(BaseModel):
    query: str = Field(..., description="Search query string")
    total: int = Field(..., description="Total stops returned")
    stops: List[StopSchema] = Field(default_factory=list, description="Matching stops")


class NearbyStopsResponse(BaseModel):
    origin_lat: float = Field(..., description="Search origin latitude")
    origin_lon: float = Field(..., description="Search origin longitude")
    radius_m: float = Field(..., description="Search radius in meters")
    total: int = Field(..., description="Total nearby stops found")
    stops: List[NearbyStopSchema] = Field(default_factory=list, description="Stops ordered by distance")


class StopCrosswalkResponse(BaseModel):
    legacy_stop_id: str = Field(..., description="Legacy GTFS stop identifier")
    legacy_stop_name: str = Field(..., description="Legacy stop name")
    dlm1_stop_id: Optional[str] = Field(None, description="Matched DLM1 stop identifier")
    dlm1_stop_name: Optional[str] = Field(None, description="Matched DLM1 stop name")
    distance_m: Optional[float] = Field(None, description="Spatial offset distance in meters")
    name_similarity: Optional[float] = Field(None, description="Name similarity ratio [0.0 - 1.0]")
    match_classification: str = Field(
        ..., description="Match confidence classification: HIGH_CONFIDENCE, REVIEW_REQUIRED, UNMATCHED"
    )
    notes: Optional[str] = Field(None, description="Crosswalk matching notes")


