"""Transit Routes Schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class OrderedStopSchema(BaseModel):
    sequence: int = Field(..., description="Ordered stop sequence index (0-based)")
    stop_id: str = Field(..., description="GTFS stop identifier")
    stop_name: str = Field(..., description="Stop name")
    lat: float = Field(..., description="Stop latitude")
    lon: float = Field(..., description="Stop longitude")


class RouteDetailResponse(BaseModel):
    route_id: str = Field(..., description="GTFS Route identifier")
    agency_id: Optional[str] = Field(None, description="Operating agency (e.g. DTC, DIMTS)")
    route_short_name: Optional[str] = Field(None, description="Short commercial line name")
    route_long_name: Optional[str] = Field(None, description="Long corridor description")
    patterns_count: int = Field(..., description="Number of distinct directional route patterns")
    trips_count: int = Field(..., description="Total scheduled daily trips")
    ordered_stops: List[OrderedStopSchema] = Field(
        default_factory=list, description="Ordered physical stops for the primary pattern"
    )
    has_shape_geometry: bool = Field(
        False, description="Whether true road geometry from shapes.txt is available"
    )
    shape_coordinates: Optional[List[List[float]]] = Field(
        None, description="Ordered [[lat, lon], ...] road centerline coordinates from shapes.txt"
    )

