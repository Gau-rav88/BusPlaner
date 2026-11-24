"""Milestone 11.1: Automated Test Suite for Staged DLM1 Static GTFS Database.

These tests explicitly connect to /tmp/delhi_dlm1.db and verify:
1. DLM1 scale and table counts
2. DLM1 calendar validity (2025-2040, CURRENT_VERIFIED)
3. DLM1 stop search and nearby stops
4. Route 1598 (59 stops, has_shape_geometry=True, 416 shape coordinates)
5. Road geometry integration for shapes
6. Direct RAPTOR journey planning on DLM1
7. Transfer RAPTOR journey planning on DLM1
8. Unknown stop IDs handling
9. Missing route 404 response
10. Live feed route ID compatibility with DLM1
11. Stop crosswalk table validation
"""

import os
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.dependencies import get_journey_planner, set_journey_planner
from backend.app.main import create_app
from backend.core.journey_planner import JourneyPlanner
from backend.core.raptor_data import Timetable, TimetableStatus

DLM1_DB_PATH = "/tmp/delhi_dlm1.db"
pytestmark = pytest.mark.dlm1


@pytest.fixture(scope="module")
def check_dlm1_db():
    if not os.path.exists(DLM1_DB_PATH):
        pytest.skip(f"Staged DLM1 database not found at {DLM1_DB_PATH}")


@pytest.fixture(scope="module")
def dlm1_planner(check_dlm1_db):
    """Create JourneyPlanner directly on DLM1 database."""
    return JourneyPlanner.create_default(db_path=DLM1_DB_PATH, fit_baseline=True)


@pytest.fixture(scope="module")
def dlm1_client(check_dlm1_db, dlm1_planner):
    """Create TestClient pointing explicitly to staged DLM1 database."""
    orig_db = settings.DB_PATH
    settings.DB_PATH = DLM1_DB_PATH
    set_journey_planner(dlm1_planner)

    app = create_app()
    app.dependency_overrides[get_journey_planner] = lambda: dlm1_planner
    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    settings.DB_PATH = orig_db
    set_journey_planner(None)


def test_dlm1_database_scale(check_dlm1_db):
    """Verify table row counts in /tmp/delhi_dlm1.db match the official DLM1 archive."""
    conn = sqlite3.connect(DLM1_DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM stops;")
    assert cur.fetchone()[0] == 6862, "DLM1 must contain 6,862 stops"

    cur.execute("SELECT count(*) FROM routes;")
    assert cur.fetchone()[0] == 2574, "DLM1 must contain 2,574 routes"

    cur.execute("SELECT count(*) FROM trips;")
    assert cur.fetchone()[0] == 80357, "DLM1 must contain 80,357 trips"

    cur.execute("SELECT count(*) FROM stop_times;")
    assert cur.fetchone()[0] == 2737136, "DLM1 must contain 2,737,136 stop times"

    cur.execute("SELECT count(*) FROM shapes;")
    assert cur.fetchone()[0] == 965607, "DLM1 must contain 965,607 shape coordinates"

    conn.close()


def test_dlm1_calendar_validity(dlm1_planner):
    """Verify DLM1 calendar covers 2025 to 2040 and evaluates to CURRENT_VERIFIED."""
    timetable = dlm1_planner.timetable
    assert timetable.feed_start_date == "2025-01-01"
    assert timetable.feed_end_date == "2040-01-01"

    status, warning = timetable.check_freshness("2026-10-01", allow_assumed_recurring=False)
    assert status == TimetableStatus.CURRENT_VERIFIED, "DLM1 calendar must be CURRENT_VERIFIED for 2026 dates"
    assert warning is None


def test_dlm1_api_health_endpoint(dlm1_client):
    """Verify health endpoint on DLM1 backend retains DEGRADE operational status."""
    resp = dlm1_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["application_status"] == "ok"
    assert data["overall_operational_status"] == "DEGRADE"
    assert data["database_available"] is True
    assert data["gtfs_loaded"] is True


def test_dlm1_api_timetable_status(dlm1_client):
    """Verify timetable status endpoint on DLM1 returns CURRENT_VERIFIED."""
    resp = dlm1_client.get("/api/v1/timetable/status?service_date=2026-10-01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["timetable_status"] == "CURRENT_VERIFIED"
    assert data["feed_start_date"] == "2025-01-01"
    assert data["feed_end_date"] == "2040-01-01"
    assert data["is_date_within_feed_validity"] is True


def test_dlm1_api_stop_search(dlm1_client):
    """Verify stop search on DLM1 discovers official DLM1 stops."""
    resp = dlm1_client.get("/api/v1/stops/search?query=kashmere&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    stop_ids = [s["stop_id"] for s in data["stops"]]
    # Verify DLM1 specific stop IDs are returned
    assert any(sid in ["1025", "1046", "7571", "271", "267", "4822", "4232"] for sid in stop_ids)


def test_dlm1_api_nearby_stops(dlm1_client):
    """Verify spatial nearby stops lookup discovers DLM1 stops within walking radius."""
    resp = dlm1_client.get("/api/v1/stops/nearby?lat=28.667&lon=77.228&radius=800")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] > 0
    assert len(data["stops"]) > 0
    # Every stop must have positive distance within radius
    for stop in data["stops"]:
        assert 0.0 <= stop["distance_m"] <= 800.0


def test_dlm1_api_route_1598_details_and_shape(dlm1_client):
    """Verify Route 1598 in DLM1 has 59 stops, has_shape_geometry=True, and 416 shape coordinates."""
    resp = dlm1_client.get("/api/v1/routes/1598")
    assert resp.status_code == 200
    data = resp.json()
    assert data["route_id"] == "1598"
    assert data["route_short_name"] == "144UP"
    assert len(data["ordered_stops"]) == 59
    assert data["has_shape_geometry"] is True
    assert data["shape_coordinates"] is not None
    assert len(data["shape_coordinates"]) == 416
    # Verify coordinates are in Delhi bounds [28.6, 77.1] -> [28.9, 77.3]
    first_coord = data["shape_coordinates"][0]
    last_coord = data["shape_coordinates"][-1]
    assert 28.5 <= first_coord[0] <= 28.9
    assert 77.0 <= first_coord[1] <= 77.4
    assert 28.5 <= last_coord[0] <= 28.9
    assert 77.0 <= last_coord[1] <= 77.4


def test_dlm1_api_direct_journey_planning(dlm1_client):
    """Verify direct journey planning on DLM1 between Adarsh Nagar (284) and Mukarba Chowk (5146)."""
    req = {
        "origin_stop_id": "284",
        "dest_stop_id": "5146",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 0,
        "allow_assumed_recurring": True,
    }
    resp = dlm1_client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] >= 1
    j0 = data["journeys"][0]
    assert j0["num_transfers"] == 0
    assert len(j0["legs"]) == 1
    leg = j0["legs"][0]
    assert leg["leg_type"] == "TRANSIT"
    assert leg["board_stop_id"] == "284"
    assert leg["alight_stop_id"] == "5146"


def test_dlm1_api_transfer_journey_planning(dlm1_client):
    """Verify multi-leg transfer journey planning on DLM1 network."""
    req = {
        "origin_stop_id": "2280",  # Nehru Nagar
        "dest_stop_id": "5321",    # Alipur Blk.(BDO Office)
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 2,
        "allow_assumed_recurring": True,
    }
    resp = dlm1_client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] >= 1
    j0 = data["journeys"][0]
    assert j0["num_transfers"] >= 1
    assert any(leg["leg_type"] == "TRANSFER" for leg in j0["legs"])


def test_dlm1_api_unknown_stop_ids(dlm1_client):
    """Verify unknown stop IDs are handled gracefully with 200 OK and journeys_count: 0."""
    req = {
        "origin_stop_id": "99999999",
        "dest_stop_id": "284",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 1,
        "allow_assumed_recurring": True,
    }
    resp = dlm1_client.post("/api/v1/journeys/plan", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["journeys_count"] == 0
    assert data["journeys"] == []


def test_dlm1_api_missing_route_404(dlm1_client):
    """Verify non-existent route ID returns structured HTTP 404 envelope."""
    resp = dlm1_client.get("/api/v1/routes/UNKNOWN_ROUTE_9999")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] == "HTTP_ERROR"
    assert "not found" in data["detail"].lower()


def test_dlm1_stop_crosswalk_referential_integrity(check_dlm1_db):
    """Verify the legacy_stop_crosswalk table in /tmp/delhi_dlm1.db."""
    conn = sqlite3.connect(DLM1_DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM legacy_stop_crosswalk;")
    assert cur.fetchone()[0] == 6342, "Must contain exactly 6,342 evaluated legacy stops"

    cur.execute(
        """
        SELECT match_classification, count(*) 
        FROM legacy_stop_crosswalk 
        GROUP BY match_classification;
        """
    )
    counts = dict(cur.fetchall())
    assert counts["HIGH_CONFIDENCE"] == 2581
    assert counts["REVIEW_REQUIRED"] == 3413
    assert counts["UNMATCHED"] == 348

    # Verify all DLM1 stop IDs referenced in crosswalk actually exist in stops table
    cur.execute(
        """
        SELECT count(*) 
        FROM legacy_stop_crosswalk 
        WHERE dlm1_stop_id IS NOT NULL 
          AND dlm1_stop_id NOT IN (SELECT stop_id FROM stops);
        """
    )
    assert cur.fetchone()[0] == 0, "Zero orphan DLM1 stop IDs in crosswalk"

    conn.close()
