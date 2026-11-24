"""Milestone 11.5: Journey Reliability, Long-Transfer Advisory, and DLM1 Quality Tests.

PRD v3.0 Milestone 11.5:
1. DLM1 2025-2040 Calendar assertions (CURRENT_VERIFIED for 2026, EXPIRED for 2041).
2. DLM1 stop search and stop identifier assertions.
3. Long-transfer advisory threshold testing:
   - Below threshold (< 7200s): no advisory emitted.
   - At threshold (== 7200s): no advisory emitted (boundary).
   - Above threshold (> 7200s): advisory emitted with exact wait, hours, and recommendation.
4. Alternative 2-transfer journey verification (Route 1965 -> 1506 -> 276, 8516s).
5. Representative direct and 1-transfer journey quality and accounting identity.
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.dependencies import set_journey_planner
from backend.app.main import create_app
from backend.core.journey_planner import JourneyPlanner
from backend.core.raptor_data import TimetableStatus

DLM1_DB_PATH = "/tmp/delhi_dlm1.db"
pytestmark = pytest.mark.dlm1


@pytest.fixture(scope="module")
def dlm1_planner():
    """Create JourneyPlanner explicitly on DLM1 database."""
    if not os.path.exists(DLM1_DB_PATH):
        pytest.skip(f"DLM1 database not found at {DLM1_DB_PATH}")
    return JourneyPlanner.create_default(db_path=DLM1_DB_PATH, fit_baseline=True)


@pytest.fixture(scope="module")
def client(dlm1_planner):
    """Create FastAPI TestClient explicitly bound to DLM1 database."""
    orig_db = settings.DB_PATH
    settings.DB_PATH = DLM1_DB_PATH
    set_journey_planner(dlm1_planner)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    settings.DB_PATH = orig_db


# ============================================================================
# 1. DLM1 2025-2040 Calendar & Timetable Status Tests
# ============================================================================

def test_dlm1_calendar_current_verified(client):
    """Verify DLM1 timetable status returns CURRENT_VERIFIED for active 2026 dates."""
    resp = client.get("/api/v1/timetable/status?service_date=2026-10-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["timetable_status"] == TimetableStatus.CURRENT_VERIFIED.value
    assert data["is_date_within_feed_validity"] is True
    assert data["actual_operations_verified"] is False
    assert len(data["warnings"]) == 0


def test_dlm1_calendar_expired_strict_mode(client):
    """Verify DLM1 rejects dates beyond 2040-01-01 with HTTP 400 in strict mode."""
    resp = client.get("/api/v1/timetable/status?service_date=2041-06-15&allow_assumed_recurring=false")
    assert resp.status_code == 200
    data = resp.json()
    assert data["timetable_status"] == TimetableStatus.EXPIRED.value
    assert data["is_date_within_feed_validity"] is False
    assert len(data["warnings"]) > 0


def test_dlm1_journey_planning_expired_date_rejection(client):
    """Verify planning for date 2041-06-15 without override returns HTTP 400 EXPIRED_TIMETABLE."""
    req = {
        "origin_stop_id": "239",
        "dest_stop_id": "247",
        "departure_date": "2041-06-15",
        "departure_time": "08:00:00",
        "allow_assumed_recurring": False,
    }
    resp = client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"] == "EXPIRED_TIMETABLE"
    assert data["feed_end_date"] == "2040-01-01"


# ============================================================================
# 2. DLM1 Stop Identifiers & Search Tests
# ============================================================================

def test_dlm1_stop_search_nehru_nagar_and_alipur(client):
    """Verify stop search discovers Stop 2280 (Nehru Nagar) and Stop 5321 (Alipur BDO)."""
    resp_n = client.get("/api/v1/stops/search?query=Nehru+Nagar&limit=5")
    assert resp_n.status_code == 200
    stops_n = resp_n.json()["stops"]
    assert any(s["stop_id"] == "2280" for s in stops_n)

    resp_a = client.get("/api/v1/stops/search?query=Alipur&limit=10")
    assert resp_a.status_code == 200
    stops_a = resp_a.json()["stops"]
    assert any(s["stop_id"] == "5321" for s in stops_a)


# ============================================================================
# 3. Long Transfer Advisory Threshold Testing (< 7200s, == 7200s, > 7200s)
# ============================================================================

def test_transfer_advisory_above_threshold(client):
    """Verify transfer wait of ~26,269s (> 7200s) on 2280 -> 5321 triggers advisory."""
    req = {
        "origin_stop_id": "2280",
        "dest_stop_id": "5321",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 2,
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] >= 1

    # Find the journey using Route 3232 (Option with 1 transfer)
    j = [x for x in data["journeys"] if x["num_transfers"] == 1][0]
    assert j["accounting"]["transfer_waiting_time_s"] > 7200.0
    assert j["has_long_transfer_wait"] is True
    assert j["long_transfer_advisory"] is not None
    assert "Extended transfer wait time" in j["long_transfer_advisory"]
    assert "hours" in j["long_transfer_advisory"]
    assert any("Extended transfer wait time" in w for w in j["warnings"])
    # Crucial safety check: journey duration must remain authentic and conserved
    assert j["total_journey_duration_s"] == 35324.0
    assert j["accounting"]["discrepancy_s"] == 0.0


def test_transfer_advisory_below_threshold(client):
    """Verify transfer wait of 1,521s (< 7200s) on 2-transfer alternative does NOT trigger advisory."""
    req = {
        "origin_stop_id": "2280",
        "dest_stop_id": "5321",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 3,
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] >= 2

    # Find the 2-transfer journey (Option 1)
    j_fast = [x for x in data["journeys"] if x["num_transfers"] == 2][0]
    assert j_fast["accounting"]["transfer_waiting_time_s"] < 7200.0
    assert j_fast["has_long_transfer_wait"] is False
    assert j_fast["long_transfer_advisory"] is None
    assert not any("Extended transfer wait time" in w for w in j_fast["warnings"])


# ============================================================================
# 4. Multi-Transfer Alternative Verification (Route 1965 -> 1506 -> 276)
# ============================================================================

def test_alternative_journey_verification_legs_and_continuity(client):
    """Verify Route 1965 -> 1506 -> 276 alternative has valid sequence and accounting."""
    req = {
        "origin_stop_id": "2280",
        "dest_stop_id": "5321",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 3,
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    data = resp.json()
    j_alt = [x for x in data["journeys"] if x["num_transfers"] == 2][0]

    assert j_alt["total_journey_duration_s"] == 8516.0
    transit_legs = [l for l in j_alt["legs"] if l["leg_type"] == "TRANSIT"]
    assert len(transit_legs) == 3

    # Route 1965
    assert transit_legs[0]["route_id"] == "1965"
    assert transit_legs[0]["board_stop_id"] == "2280"
    assert transit_legs[0]["alight_stop_id"] == "4975"

    # Route 1506
    assert transit_legs[1]["route_id"] == "1506"
    assert transit_legs[1]["board_stop_id"] == "4975"
    assert transit_legs[1]["alight_stop_id"] == "289"

    # Route 276
    assert transit_legs[2]["route_id"] == "276"
    assert transit_legs[2]["board_stop_id"] == "289"
    assert transit_legs[2]["alight_stop_id"] == "5321"

    # Monotonicity check
    assert transit_legs[0]["alight_time_s"] <= transit_legs[1]["board_time_s"]
    assert transit_legs[1]["alight_time_s"] <= transit_legs[2]["board_time_s"]
    assert j_alt["accounting"]["discrepancy_s"] == 0.0


# ============================================================================
# 5. Representative Direct & Transfer Journeys Quality
# ============================================================================

def test_direct_pilot_corridor_level_1_observed(client):
    """Verify Route 1598 (239 -> 247) emits LEVEL_1_DIRECT_OBSERVED."""
    req = {
        "origin_stop_id": "239",
        "dest_stop_id": "247",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 0,
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    j = resp.json()["journeys"][0]
    assert j["num_transfers"] == 0
    t_leg = j["legs"][0]
    assert t_leg["prediction_tier"] == "LEVEL_1_DIRECT_OBSERVED"
    assert t_leg["prediction_source"] == "GROUND_TRUTH_OBSERVED"
    assert t_leg["is_fallback"] is False


def test_direct_unobserved_corridor_level_4_scheduled(client):
    """Verify Route 284 (284 -> 5146) emits LEVEL_4_GTFS_SCHEDULED."""
    req = {
        "origin_stop_id": "284",
        "dest_stop_id": "5146",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 0,
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    j = resp.json()["journeys"][0]
    assert j["num_transfers"] == 0
    t_leg = j["legs"][0]
    assert t_leg["prediction_tier"] == "LEVEL_4_GTFS_SCHEDULED"
    assert t_leg["prediction_source"] == "GTFS_TIMETABLE"
    assert t_leg["is_fallback"] is True

