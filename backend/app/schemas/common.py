"""Common Pydantic Schemas."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class CoordinateSchema(BaseModel):
    lat: float = Field(..., description="Latitude in WGS84 format (-90.0 to 90.0)")
    lon: float = Field(..., description="Longitude in WGS84 format (-180.0 to 180.0)")

    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude must be between -90.0 and 90.0, got {v}")
        return v

    @field_validator("lon")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude must be between -180.0 and 180.0, got {v}")
        return v


class ErrorResponse(BaseModel):
    error: str = Field(..., description="High-level error category or title")
    detail: Optional[str] = Field(None, description="Detailed actionable explanation")
    error_code: Optional[str] = Field(None, description="Domain error code")
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )

