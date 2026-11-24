"""FastAPI Pydantic Schemas Package."""

from backend.app.schemas.common import CoordinateSchema, ErrorResponse
from backend.app.schemas.health import HealthResponse
from backend.app.schemas.timetable import TimetableStatusResponse
from backend.app.schemas.stops import (
    NearbyStopSchema,
    NearbyStopsResponse,
    StopSchema,
    StopSearchResponse,
)
from backend.app.schemas.routes import OrderedStopSchema, RouteDetailResponse
from backend.app.schemas.journey import (
    JourneyAccountingSchema,
    JourneyAlternativeSchema,
    JourneyPlanRequest,
    JourneyPlanResponse,
    TransitLegSchema,
    WalkingLegSchema,
)

__all__ = [
    "CoordinateSchema",
    "ErrorResponse",
    "HealthResponse",
    "TimetableStatusResponse",
    "StopSchema",
    "NearbyStopSchema",
    "StopSearchResponse",
    "NearbyStopsResponse",
    "OrderedStopSchema",
    "RouteDetailResponse",
    "JourneyPlanRequest",
    "JourneyPlanResponse",
    "JourneyAlternativeSchema",
    "JourneyAccountingSchema",
    "TransitLegSchema",
    "WalkingLegSchema",
]

