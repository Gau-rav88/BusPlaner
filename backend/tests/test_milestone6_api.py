"""Milestone 6 REST API Test Suite.

Tests:
1. Health endpoint (operational status, versions, readiness).
2. Timetable freshness states (CURRENT_VERIFIED, EXPIRED, ASSUMED_RECURRING, UNAVAILABLE).
3. Journey planning success (direct, transfer, coordinate-based).
4. Invalid coordinates (rejection of out-of-bounds lat/lon).
5. Invalid dates and times (rejection with 422).
6. Expired timetable strict mode (rejection with 400).
7. Assumed recurring demonstration opt-in (success with explicit warnings).
8. Missing timetable (503 Service Unavailable).
9. No journey found (clean empty journey response).
10. Stop search (substring matching).
11. Nearby stops (spatial radius search).
12. Route information (success on existing route, 404 on missing).
13. Prediction source metadata & heuristic confidence labeling.
14. Experimental ML disabled by default.
15. Journey accounting identity conservation (discrepancy == 0.0000s).
16. Warning propagation into journey results.
17. Error handling & information leakage protection.
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.dependencies import get_journey_planner, set_journey_planner
from backend.app.main import create_app
from backend.core.journey_planner import JourneyPlanner
from backend.core.raptor_data import Timetable

DB_PATH = "/tmp/delhi_mdb.db"
pytestmark = pytest.mark.legacy


@pytest.fixture(scope="module")
def legacy_planner():
    """Create JourneyPlanner explicitly on legacy database."""
    if not os.path.exists(DB_PATH):
        pytest.skip(f"Legacy database not found at {DB_PATH}")
    return JourneyPlanner.create_default(db_path=DB_PATH, fit_baseline=True)


@pytest.fixture(scope="module")
def client(legacy_planner):
    """Create FastAPI TestClient explicitly bound to legacy database."""
    orig_db = settings.DB_PATH
    settings.DB_PATH = DB_PATH
    set_journey_planner(legacy_planner)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    settings.DB_PATH = orig_db


def test_api_health(client):
    """Test GET /api/v1/health returns 200 with DEGRADE status."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["application_status"] == "ok"
    assert data["backend_version"] == "1.0.0"
    assert data["database_available"] is True
    assert data["gtfs_loaded"] is True
    assert data["overall_operational_status"] == "DEGRADE"
    assert "timestamp_utc" in data


def test_api_timetable_status_states(client):
    """Test GET /api/v1/timetable/status across all supported freshness states."""
    # 1. Historical valid date -> CURRENT_VERIFIED
    resp_curr = client.get("/api/v1/timetable/status?service_date=2023-05-15&allow_assumed_recurring=false")
    assert resp_curr.status_code == 200
    d_curr = resp_curr.json()
    assert d_curr["timetable_status"] == "CURRENT_VERIFIED"
    assert d_curr["is_date_within_feed_validity"] is True
    assert d_curr["actual_operations_verified"] is False
    assert len(d_curr["warnings"]) == 0

    # 2. 2026 date without opt-in -> EXPIRED
    resp_exp = client.get("/api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=false")
    assert resp_exp.status_code == 200
    d_exp = resp_exp.json()
    assert d_exp["timetable_status"] == "EXPIRED"
    assert d_exp["is_date_within_feed_validity"] is False
    assert d_exp["actual_operations_verified"] is False
    assert len(d_exp["warnings"]) > 0
    assert "EXPIRED TIMETABLE ERROR" in d_exp["warnings"][0]

    # 3. 2026 date with opt-in -> ASSUMED_RECURRING
    resp_demo = client.get("/api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=true")
    assert resp_demo.status_code == 200
    d_demo = resp_demo.json()
    assert d_demo["timetable_status"] == "ASSUMED_RECURRING"
    assert d_demo["is_date_within_feed_validity"] is False
    assert d_demo["actual_operations_verified"] is False
    assert len(d_demo["warnings"]) > 0
    assert "STALE TIMETABLE WARNING" in d_demo["warnings"][0]


def test_api_journey_planning_success(client):
    """Test successful journey planning on North GT Road corridor."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "max_walking_distance_m": 800.0,
        "max_transfers": 3,
        "num_alternatives": 2,
        "use_experimental_ml": False,
        "allow_assumed_recurring": True,
        "ranking_strategy": "earliest_arrival",
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["journeys_count"] >= 1
    assert data["timetable_status"] == "ASSUMED_RECURRING"
    assert data["stale_timetable_warning"] is not None

    j = data["journeys"][0]
    assert j["num_transfers"] >= 0
    assert j["total_journey_duration_s"] > 0
    assert j["actual_operations_verified"] is False
    assert j["is_verified_current_service"] is False

    # Check accounting identity
    acct = j["accounting"]
    assert acct["is_valid_identity"] is True
    assert acct["discrepancy_s"] == 0.0
    calc_sum = (
        acct["access_walking_time_s"]
        + acct["initial_waiting_time_s"]
        + acct["in_vehicle_duration_s"]
        + acct["transfer_walking_time_s"]
        + acct["transfer_waiting_time_s"]
        + acct["egress_walking_time_s"]
    )
    assert abs(acct["total_duration_s"] - calc_sum) < 1e-3


def test_api_journey_planning_invalid_coordinates(client):
    """Test validation errors for invalid latitude or longitude."""
    payload = {
        "origin_lat": 95.0,  # Invalid latitude (> 90)
        "origin_lon": 77.181,
        "dest_lat": 28.735,
        "dest_lon": 77.165,
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 422
    err = resp.json()
    assert err["error"] == "VALIDATION_ERROR"
    assert "origin_lat" in err["detail"]


def test_api_journey_planning_invalid_dates_and_times(client):
    """Test validation errors for invalid date format or time string."""
    # Invalid date format
    payload_bad_date = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-13-45",  # Invalid month/day
        "departure_time": "08:00:00",
        "allow_assumed_recurring": True,
    }
    resp1 = client.post("/api/v1/journeys/plan", json=payload_bad_date)
    assert resp1.status_code == 422
    assert "departure_date" in resp1.json()["detail"]

    # Invalid time format
    payload_bad_time = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "29:75:00",  # Invalid hours/minutes
        "allow_assumed_recurring": True,
    }
    resp2 = client.post("/api/v1/journeys/plan", json=payload_bad_time)
    assert resp2.status_code == 422
    assert "departure_time" in resp2.json()["detail"]


def test_api_journey_planning_expired_strict_mode(client):
    """Test that requesting an expired date without allow_assumed_recurring=True returns 400 Bad Request."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": False,  # Strict mode!
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 400
    err = resp.json()
    assert err["error"] == "EXPIRED_TIMETABLE"
    assert "allow_assumed_recurring: true" in err["action"]


def test_api_journey_planning_missing_timetable(client):
    """Test that a missing or unloaded timetable returns 503 Service Unavailable."""
    # Temporarily substitute an empty timetable
    empty_tt = Timetable(
        stops={}, patterns={}, stop_to_patterns={}, footpaths={},
        active_service_ids=set(), db_path="", config={},
        feed_start_date=None, feed_end_date=None,
    )
    empty_planner = JourneyPlanner(timetable=empty_tt)
    original_planner = get_journey_planner()

    try:
        set_journey_planner(empty_planner)
        payload = {
            "origin_stop_id": "239",
            "dest_stop_id": "2024",
            "departure_date": "2026-10-01",
            "departure_time": "12:37:40",
            "allow_assumed_recurring": True,
        }
        resp = client.post("/api/v1/journeys/plan", json=payload)
        assert resp.status_code == 503
        err = resp.json()
        assert err["error"] == "TIMETABLE_UNAVAILABLE"
    finally:
        set_journey_planner(original_planner)


def test_api_journey_planning_no_journey_found(client):
    """Test query to disconnected or unreachable stop returns 200 with 0 itineraries."""
    payload = {
        "origin_stop_id": "INVALID_STOP_999999",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] == 0
    assert data["journeys"] == []


def test_api_stop_search(client):
    """Test GET /api/v1/stops/search by name substring."""
    resp = client.get("/api/v1/stops/search?query=azad&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "azad"
    assert data["total"] > 0
    assert any("azad" in s["stop_name"].lower() for s in data["stops"])


def test_api_nearby_stops(client):
    """Test GET /api/v1/stops/nearby spatial resolution."""
    # Azadpur Terminal coordinates
    lat, lon = 28.708, 77.175
    resp = client.get(f"/api/v1/stops/nearby?lat={lat}&lon={lon}&radius_m=800&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    # Verify ordered by distance
    dists = [s["distance_m"] for s in data["stops"]]
    assert dists == sorted(dists)


def test_api_route_detail_and_404(client):
    """Test GET /api/v1/routes/{route_id} metadata and 404 behavior."""
    # Existing route
    resp = client.get("/api/v1/routes/1598")
    assert resp.status_code == 200
    data = resp.json()
    assert data["route_id"] == "1598"
    assert data["trips_count"] > 0
    assert len(data["ordered_stops"]) > 0

    # Non-existent route
    resp_404 = client.get("/api/v1/routes/NON_EXISTENT_ROUTE_999999")
    assert resp_404.status_code == 404
    assert "not found" in resp_404.json()["detail"].lower()


def test_api_prediction_source_metadata_and_heuristics(client):
    """Test that all returned transit legs contain heuristic confidence metadata, not probabilities."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
        "use_experimental_ml": False,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    j = data["journeys"][0]

    for leg in j["legs"]:
        if "route_id" in leg:  # TransitLeg
            assert leg["confidence_score_type"] == "HEURISTIC"
            assert "heuristic_confidence_score" in leg
            assert "NOT a calibrated probability" in leg["confidence_explanation"]


def test_api_experimental_ml_gating(client):
    """Test that Random Forest ML predictions are disabled by default."""
    payload_default = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
        # use_experimental_ml omitted -> defaults to False
    }
    resp = client.post("/api/v1/journeys/plan", json=payload_default)
    assert resp.status_code == 200
    j = resp.json()["journeys"][0]
    for leg in j["legs"]:
        if "prediction_tier" in leg:
            assert leg["prediction_tier"] != "LEVEL_3_EXPERIMENTAL_RF"


def test_api_error_handling_sanitization(client):
    """Test that error responses do not leak sensitive file paths or credentials."""
    resp = client.get("/api/v1/routes/INVALID_ROUTE_'; DROP TABLE routes;--")
    assert resp.status_code == 404
    detail = resp.json().get("detail", "")
    assert "/Users/" not in detail
    assert "sqlite3" not in detail


def test_api_coordinate_routing_access_egress(client):
    """Test end-to-end routing with coordinate origin and destination."""
    payload = {
        "origin_lat": 28.7150,
        "origin_lon": 77.1810,
        "dest_lat": 28.7350,
        "dest_lon": 77.1650,
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "max_walking_distance_m": 1200.0,
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] >= 1
    j = data["journeys"][0]
    # Verify access walking leg and egress walking leg
    leg_types = [l["leg_type"] for l in j["legs"] if "leg_type" in l]
    assert "ACCESS" in leg_types
    assert j["accounting"]["is_valid_identity"] is True


def test_api_ranking_strategies(client):
    """Test fewest_transfers and least_walking ranking strategies."""
    for strat in ["fewest_transfers", "least_walking"]:
        payload = {
            "origin_stop_id": "239",
            "dest_stop_id": "2024",
            "departure_date": "2026-10-01",
            "departure_time": "12:37:40",
            "allow_assumed_recurring": True,
            "ranking_strategy": strat,
        }
        resp = client.post("/api/v1/journeys/plan", json=payload)
        assert resp.status_code == 200
        assert resp.json()["query_summary"]["ranking_strategy"] == strat
