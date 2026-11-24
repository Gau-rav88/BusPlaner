"""Timetable Freshness Schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class TimetableStatusResponse(BaseModel):
    timetable_status: str = Field(
        ...,
        description="Freshness state: CURRENT_VERIFIED, EXPIRED, ASSUMED_RECURRING, or UNAVAILABLE",
    )
    feed_start_date: Optional[str] = Field(None, description="Start date of published GTFS feed")
    feed_end_date: Optional[str] = Field(None, description="Expiration date of published GTFS feed")
    feed_provenance: str = Field(..., description="Documented origin and source archive of GTFS feed")
    is_date_within_feed_validity: bool = Field(
        ..., description="Whether requested service date falls inside [feed_start_date, feed_end_date]"
    )
    actual_operations_verified: bool = Field(
        default=False,
        description="Whether actual physical bus operations have been independently verified in real time. Strictly False.",
    )
    demonstration_mode_available: bool = Field(
        default=True,
        description="Whether historical template schedules can be evaluated under demonstration assumption",
    )
    service_date_evaluated: str = Field(..., description="Service date evaluated for this status")
    warnings: List[str] = Field(default_factory=list, description="Actionable stale timetable warnings")

