"""Health Endpoint Schemas."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    application_status: str = Field(..., description="Operational status: 'ok' or 'degraded'")
    backend_version: str = Field(..., description="Semantic backend version")
    database_available: bool = Field(..., description="Whether primary GTFS SQLite database is reachable")
    gtfs_loaded: bool = Field(..., description="Whether GTFS transit network is indexed in memory")
    model_available: bool = Field(..., description="Whether baseline prediction models are initialized")
    overall_operational_status: str = Field(..., description="Governing project status, e.g. 'DEGRADE'")
    live_feed_status: str = Field(default="AUTH_REQUIRED", description="Real-time GTFS-RT feed availability state")
    live_feed_enabled: bool = Field(default=False, description="Whether live GTFS-RT streaming is actively enabled")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )

