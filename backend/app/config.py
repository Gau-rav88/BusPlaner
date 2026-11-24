"""Application Configuration Module using Pydantic Settings."""

import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILES = (
    os.path.join(ROOT_DIR, ".env"),
    os.path.join(ROOT_DIR, "backend", ".env"),
    ".env",
    "backend/.env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Delhi Bus Traffic & Journey Planner API"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    OVERALL_OPERATIONAL_STATUS: str = "DEGRADE"

    # Database and assets
    DB_PATH: str = "/tmp/delhi_mdb.db"
    CONFIG_PATH: str = "config/planner.yaml"

    # CORS configuration
    CORS_ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Journey Planner constraints
    DEFAULT_MAX_WALKING_M: float = 800.0
    EXPANDED_MAX_WALKING_M: float = 1500.0
    DEFAULT_MAX_TRANSFERS: int = 3
    MIN_TRANSFER_BUFFER_S: float = 120.0
    DEFAULT_WALKING_SPEED_KMH: float = 4.5
    DEFAULT_DETOUR_FACTOR: float = 1.3

    # Live GTFS-RT Configuration (Delhi Transport Stack)
    DELHI_TRANSPORTSTACK_API_KEY: str = ""
    DELHI_GTFS_RT_URL: str = (
        "https://dts-backend.transportstack.in/api/dataset/otd/get-file"
        "?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb"
    )
    LIVE_FEED_ENABLED: bool = True
    LIVE_FEED_POLL_INTERVAL_SECONDS: int = 30
    LIVE_FEED_STALENESS_SECONDS: int = 900


settings = Settings()

