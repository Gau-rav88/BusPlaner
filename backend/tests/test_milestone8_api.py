"""Milestone 8 API Integration and Regression Tests.

PRD v3.0 Milestone 8:
Verifies:
- GET /api/v1/live/status returns accurate availability status (AUTH_REQUIRED) and schema.
- GET /api/v1/health echoes live feed status without breaking existing clients.
- Journey planning operates reliably with zero regressions.
"""

import os
from fastapi.testclient import TestClient
import pytest

from backend.app.config import settings
from backend.app.dependencies import set_journey_planner
from backend.app.main import create_app
from backend.core.journey_planner import JourneyPlanner

LEGACY_DB_PATH = "/tmp/delhi_mdb.db"
pytestmark = pytest.mark.legacy


@pytest.fixture(scope="module")
def legacy_planner():
    """Create JourneyPlanner explicitly on legacy database."""
    if not os.path.exists(LEGACY_DB_PATH):
        pytest.skip(f"Legacy database not found at {LEGACY_DB_PATH}")
    return JourneyPlanner.create_default(db_path=LEGACY_DB_PATH, fit_baseline=True)


@pytest.fixture(scope="module")
def client(legacy_planner):
    """Create TestClient explicitly bound to legacy database."""
    orig_db = settings.DB_PATH
    settings.DB_PATH = LEGACY_DB_PATH
    set_journey_planner(legacy_planner)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    settings.DB_PATH = orig_db


def test_api_live_feed_status_default(client):
    """Verify GET /api/v1/live/status returns AUTH_REQUIRED with full telemetry."""
    response = client.get("/api/v1/live/status")
    assert response.status_code == 200
    data = response.json()

    assert data["feed_enabled"] is False
    assert data["feed_availability_status"] == "AUTH_REQUIRED"
    assert data["auth_required"] is True
    assert data["auth_configured"] is False
    assert data["overall_operational_status"] == "DEGRADE"
    assert "https://dts-backend.transportstack.in" in data["endpoint_url"]
    assert "Transport Stack" in data["warning"]
    assert data["active_vehicles_count"] == 0


def test_api_health_includes_live_feed_telemetry(client):
    """Verify GET /api/v1/health includes live_feed_status and live_feed_enabled."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["application_status"] == "ok"
    assert data["overall_operational_status"] == "DEGRADE"
    assert data["live_feed_status"] == "AUTH_REQUIRED"
    assert data["live_feed_enabled"] is False


def test_journey_planner_regression_north_gt_road(client):
    """Verify RAPTOR journey planning on Route 1598 (Stop 239 -> 247) functions with zero regression."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "247",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    response = client.post("/api/v1/journeys/plan", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["journeys_count"] >= 1
    j = data["journeys"][0]
    assert j["num_transfers"] == 0
    assert j["actual_operations_verified"] is False
    assert j["timetable_status"] == "ASSUMED_RECURRING"

    # Transit leg verification
    t_leg = [l for l in j["legs"] if l["leg_type"] == "TRANSIT"][0]
    assert t_leg["route_id"] == "1598"
    assert t_leg["board_stop_id"] == "239"
    assert t_leg["alight_stop_id"] == "247"
    assert t_leg["prediction_tier"] == "LEVEL_1_DIRECT_OBSERVED"
    assert t_leg["heuristic_confidence_score"] >= 0.8
    assert t_leg["confidence_score_type"] == "HEURISTIC"

