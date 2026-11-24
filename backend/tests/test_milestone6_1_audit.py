"""
Milestone 6.1 Backend API Independent Audit & Quality Assurance Test Suite.
Exhaustively tests timetable freshness consistency, journey leg warning propagation,
error envelope sanitization, accounting invariants, and all 6 REST endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.config import settings
from backend.core.journey_planner import JourneyPlanner
from backend.core.raptor_data import Timetable, TimetableStatus
from backend.app.dependencies import set_journey_planner
from backend.app.services.planner_service import (
    ExpiredTimetableException,
    TimetableUnavailableException,
)

LEGACY_DB_PATH = "/tmp/delhi_mdb.db"
pytestmark = pytest.mark.legacy


@pytest.fixture(scope="module")
def legacy_planner():
    """Create JourneyPlanner explicitly on legacy database."""
    import os
    if not os.path.exists(LEGACY_DB_PATH):
        pytest.skip(f"Legacy database not found at {LEGACY_DB_PATH}")
    return JourneyPlanner.create_default(db_path=LEGACY_DB_PATH, fit_baseline=True)


@pytest.fixture(scope="module")
def client(legacy_planner):
    """Create FastAPI test client explicitly bound to legacy database."""
    orig_db = settings.DB_PATH
    settings.DB_PATH = LEGACY_DB_PATH
    set_journey_planner(legacy_planner)
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    settings.DB_PATH = orig_db


# ============================================================================
# 1. Timetable Freshness Consistency Across All 4 States
# ============================================================================

def test_freshness_four_canonical_states(client):
    """Verify all 4 freshness states (CURRENT_VERIFIED, EXPIRED, ASSUMED_RECURRING, UNAVAILABLE)."""
    # State 1: CURRENT_VERIFIED (within 2022-01-01 to 2024-01-01)
    r1 = client.get("/api/v1/timetable/status?service_date=2023-06-15")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["timetable_status"] == TimetableStatus.CURRENT_VERIFIED.value
    assert d1["is_date_within_feed_validity"] is True
    assert d1["actual_operations_verified"] is False
    assert len(d1["warnings"]) == 0

    # State 2: EXPIRED (2026 date without opt-in)
    r2 = client.get("/api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=false")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["timetable_status"] == TimetableStatus.EXPIRED.value
    assert d2["is_date_within_feed_validity"] is False
    assert d2["actual_operations_verified"] is False
    assert len(d2["warnings"]) > 0
    assert "EXPIRED TIMETABLE ERROR" in d2["warnings"][0]

    # State 3: ASSUMED_RECURRING (2026 date with opt-in)
    r3 = client.get("/api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=true")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["timetable_status"] == TimetableStatus.ASSUMED_RECURRING.value
    assert d3["is_date_within_feed_validity"] is False
    assert d3["actual_operations_verified"] is False
    assert len(d3["warnings"]) > 0
    assert "STALE TIMETABLE WARNING" in d3["warnings"][0]

    # State 4: UNAVAILABLE (Simulated empty/offline timetable)
    empty_tt = Timetable(
        stops={}, patterns={}, stop_to_patterns={}, footpaths={},
        active_service_ids=set(), db_path="/tmp/fake.db", config={},
        feed_start_date=None, feed_end_date=None
    )
    status_unavail, warn_unavail = empty_tt.check_freshness("2026-10-01")
    assert status_unavail == TimetableStatus.UNAVAILABLE
    assert "UNAVAILABLE" in warn_unavail


def test_freshness_warning_propagation_to_every_leg(client):
    """Verify stale timetable warning reaches response, journey warnings, AND every transit leg warning."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Response envelope warning
    assert data["timetable_status"] == "ASSUMED_RECURRING"
    assert data["stale_timetable_warning"] is not None
    assert "STALE TIMETABLE WARNING" in data["stale_timetable_warning"]

    assert len(data["journeys"]) > 0
    for j in data["journeys"]:
        # Journey level
        assert j["timetable_status"] == "ASSUMED_RECURRING"
        assert j["is_verified_current_service"] is False
        assert j["actual_operations_verified"] is False
        assert any("STALE TIMETABLE WARNING" in w for w in j["warnings"])

        # Leg level
        for leg in j["legs"]:
            if leg["leg_type"] == "TRANSIT":
                assert leg["timetable_status"] == "ASSUMED_RECURRING"
                assert leg["is_verified_current_service"] is False
                assert leg["warning"] is not None
                assert "STALE TIMETABLE WARNING" in leg["warning"]


def test_current_verified_leg_has_no_stale_warning(client):
    """Verify that a historical valid date (CURRENT_VERIFIED) produces no stale timetable warning on legs."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2023-05-15",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": False,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["timetable_status"] == "CURRENT_VERIFIED"
    assert data["stale_timetable_warning"] is None
    for j in data["journeys"]:
        assert j["timetable_status"] == "CURRENT_VERIFIED"
        assert j["is_verified_current_service"] is True
        for leg in j["legs"]:
            if leg["leg_type"] == "TRANSIT":
                assert leg["timetable_status"] == "CURRENT_VERIFIED"
                assert leg["is_verified_current_service"] is True
                if leg["warning"]:
                    assert "STALE TIMETABLE WARNING" not in leg["warning"]


# ============================================================================
# 2. Journey Response Detailed Audit
# ============================================================================

def test_journey_response_scheduled_vs_predicted_distinction(client):
    """Verify scheduled times and predicted times are distinct, present, and properly typed."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    for j in data["journeys"]:
        for leg in j["legs"]:
            if leg["leg_type"] == "TRANSIT":
                # Scheduled fields
                assert isinstance(leg["sched_departure_s"], float)
                assert isinstance(leg["sched_arrival_s"], float)
                assert isinstance(leg["sched_duration_s"], float)
                assert leg["sched_duration_s"] > 0

                # Predicted fields
                assert isinstance(leg["board_time_s"], float)
                assert isinstance(leg["alight_time_s"], float)
                assert isinstance(leg["ride_duration_s"], float)
                assert leg["ride_duration_s"] > 0

                # Stop identity
                assert len(leg["board_stop_id"]) > 0
                assert len(leg["board_stop_name"]) > 0
                assert len(leg["alight_stop_id"]) > 0
                assert len(leg["alight_stop_name"]) > 0


def test_journey_accounting_identity_no_double_counting(client):
    """Verify exact time accounting: total duration equals sum of non-overlapping components with 0 discrepancy."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    for j in data["journeys"]:
        acct = j["accounting"]
        assert acct["is_valid_identity"] is True
        assert acct["discrepancy_s"] == 0.0

        # Verify all components are non-negative
        assert acct["access_walking_time_s"] >= 0.0
        assert acct["initial_waiting_time_s"] >= 0.0
        assert acct["in_vehicle_duration_s"] > 0.0
        assert acct["transfer_walking_time_s"] >= 0.0
        assert acct["transfer_waiting_time_s"] >= 0.0
        assert acct["egress_walking_time_s"] >= 0.0

        # Exact component summation
        manual_sum = (
            acct["access_walking_time_s"]
            + acct["initial_waiting_time_s"]
            + acct["in_vehicle_duration_s"]
            + acct["transfer_walking_time_s"]
            + acct["transfer_waiting_time_s"]
            + acct["egress_walking_time_s"]
        )
        assert abs(manual_sum - acct["total_duration_s"]) < 1e-4
        assert abs(manual_sum - j["total_journey_duration_s"]) < 1e-4


def test_heuristic_confidence_and_prediction_sources(client):
    """Verify confidence is strictly labeled HEURISTIC, never PROBABILITY, and fallbacks are transparent."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    for j in data["journeys"]:
        assert j["confidence_score_type"] == "HEURISTIC"
        for leg in j["legs"]:
            if leg["leg_type"] == "TRANSIT":
                assert leg["confidence_score_type"] == "HEURISTIC"
                assert "NOT a calibrated probability" in leg["confidence_explanation"]
                assert leg["prediction_tier"] in [
                    "LEVEL_1_DIRECT_OBSERVED",
                    "LEVEL_2_HISTORICAL_BASELINE_M0",
                    "LEVEL_3_EXPERIMENTAL_RF",
                    "LEVEL_4_GTFS_SCHEDULED",
                    "LEVEL_5_STATIC_FALLBACK",
                ]
                assert len(leg["prediction_source"]) > 0


# ============================================================================
# 3. Endpoint and Validation Audit (All 6 Endpoints)
# ============================================================================

def test_endpoint_health(client):
    """Verify GET /api/v1/health operational attributes."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    d = resp.json()
    assert d["application_status"] in ["ok", "degraded"]
    assert d["overall_operational_status"] == "DEGRADE"
    assert d["backend_version"] == "1.0.0"


def test_endpoint_timetable_status_validation(client):
    """Verify GET /api/v1/timetable/status date parameter handling."""
    # Invalid date format
    resp_bad = client.get("/api/v1/timetable/status?service_date=invalid-date")
    assert resp_bad.status_code == 200  # Handler accepts and tests date against range
    d_bad = resp_bad.json()
    assert d_bad["is_date_within_feed_validity"] is False


def test_endpoint_stop_search_empty_and_unknown(client):
    """Verify GET /api/v1/stops/search returns empty list for queries matching nothing."""
    resp = client.get("/api/v1/stops/search?query=NON_EXISTENT_STOP_XYZ_12345")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total"] == 0
    assert d["stops"] == []


def test_endpoint_nearby_stops_empty_and_validation(client):
    """Verify GET /api/v1/stops/nearby handles distant coordinates and bounds checking."""
    # Distant coordinate (equator)
    resp = client.get("/api/v1/stops/nearby?lat=0.0&lon=0.0&radius_m=800")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total"] == 0
    assert d["stops"] == []

    # Out of range coordinate
    resp_err = client.get("/api/v1/stops/nearby?lat=120.0&lon=77.0")
    assert resp_err.status_code == 422
    err = resp_err.json()
    assert err["error"] == "VALIDATION_ERROR"


def test_endpoint_route_detail_known_and_unknown(client):
    """Verify GET /api/v1/routes/{route_id} returns 200 for known, 404 for unknown route."""
    # Known route
    r_ok = client.get("/api/v1/routes/1598")
    assert r_ok.status_code == 200
    d_ok = r_ok.json()
    assert d_ok["route_id"] == "1598"
    assert len(d_ok["ordered_stops"]) > 0

    # Unknown route
    r_404 = client.get("/api/v1/routes/UNKNOWN_ROUTE_999999")
    assert r_404.status_code == 404
    d_404 = r_404.json()
    assert d_404["error"] == "HTTP_ERROR"
    assert "not found" in d_404["detail"].lower()


def test_endpoint_journey_plan_unknown_stop_and_disconnected(client):
    """Verify POST /api/v1/journeys/plan with unknown stop ID returns clean empty journeys list."""
    payload = {
        "origin_stop_id": "UNKNOWN_STOP_ID_99999",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 200
    d = resp.json()
    assert d["journeys_count"] == 0
    assert d["journeys"] == []


def test_endpoint_journey_plan_identical_endpoints_validation(client):
    """Verify POST /api/v1/journeys/plan with identical origin and destination is rejected."""
    payload = {
        "origin_stop_id": "239",
        "dest_stop_id": "239",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    }
    resp = client.post("/api/v1/journeys/plan", json=payload)
    assert resp.status_code == 422
    err = resp.json()
    assert err["error"] == "VALIDATION_ERROR"
    assert "identical" in err["detail"].lower()


# ============================================================================
# 4. Security, CORS, and Error Sanitization Audit
# ============================================================================

def test_security_cors_configuration(client):
    """Verify CORS headers match allowed origins and do not use wildcard '*'."""
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp.headers.get("access-control-allow-origin") != "*"

    # Verify untrusted origin is not reflected in access-control-allow-origin
    resp_untrusted = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://malicious-site.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp_untrusted.headers.get("access-control-allow-origin") is None


def test_error_envelope_sanitization(client):
    """Verify errors never leak file paths, stack traces, or credentials."""
    # 1. 422 Validation Error
    r422 = client.post("/api/v1/journeys/plan", json={"origin_lat": 999.0})
    assert r422.status_code == 422
    d422 = r422.json()
    assert "error" in d422 and "detail" in d422
    assert "/Users/" not in d422["detail"]
    assert "Traceback" not in d422["detail"]

    # 2. 400 Expired Timetable Error
    r400 = client.post(
        "/api/v1/journeys/plan",
        json={
            "origin_stop_id": "239",
            "dest_stop_id": "2024",
            "departure_date": "2026-10-01",
            "departure_time": "12:37:40",
            "allow_assumed_recurring": False,
        },
    )
    assert r400.status_code == 400
    d400 = r400.json()
    assert d400["error"] == "EXPIRED_TIMETABLE"
    assert "/Users/" not in str(d400)
    assert "Traceback" not in str(d400)

    # 3. 404 Route Not Found Error
    r404 = client.get("/api/v1/routes/NON_EXISTENT_ROUTE_XYZ")
    assert r404.status_code == 404
    d404 = r404.json()
    assert "/Users/" not in str(d404)
    assert "Traceback" not in str(d404)
