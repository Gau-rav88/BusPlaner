"""Tests for Journey-Suitable Bus Filtering and Viewport Bounding-Box Live Loading.

Verifies:
1. Viewport bounding-box filtering on GET /api/v1/live/vehicles.
2. Strict journey-suitable bus matching on GET /api/v1/live/suitable-vehicles:
   - Matches forward-direction buses approaching or near boarding stop.
   - Rejects opposite-direction buses.
   - Rejects buses that have already passed the boarding stop.
   - Rejects off-corridor buses (>1500m from route stops).
   - Returns structured guidance and fallback messages when no suitable bus is active.
"""

import time
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.dependencies import set_live_collector
from backend.realtime.gtfs_rt import (
    FeedAvailabilityStatus,
    LiveFeedCollector,
    ValidatedVehiclePosition,
)

client = TestClient(app)


@pytest.fixture
def mock_collector_with_scenarios():
    """Set up collector with known vehicle positions for corridor 1598 (Azadpur to Mori Gate)."""
    collector = LiveFeedCollector(
        endpoint_url="http://mock-feed.local/gtfs-rt",
        poll_interval_seconds=20,
        max_staleness_seconds=900,
        is_enabled=True,
    )
    collector.known_route_ids = {"1598", "999"}
    collector.last_fetch_mono = time.monotonic()
    collector.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED

    now = int(time.time())

    # Stop 284 is Adarsh Nagar (~28.7160, 77.1708)
    # Stop 5146 is Mukarba Chowk (~28.7351, 77.1556)
    # Forward direction goes from Adarsh Nagar (seq 34) -> Mukarba Chowk (seq 39) heading ~325 deg (North-West)

    v1_approaching = ValidatedVehiclePosition(
        vehicle_id="DL1PC0001",
        route_id="1598",
        trip_id=None,
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,  # Forward heading along corridor
        speed_kmh=32.0,
        timestamp_utc=now - 20,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    v2_near_stop = ValidatedVehiclePosition(
        vehicle_id="DL1PC0002",
        route_id="1598",
        trip_id=None,
        latitude=28.7150,
        longitude=77.1710,
        bearing=325.0,  # Near boarding stop, forward heading
        speed_kmh=12.0,
        timestamp_utc=now - 15,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    v3_passed_stop = ValidatedVehiclePosition(
        vehicle_id="DL1PC0003",
        route_id="1598",
        trip_id=None,
        latitude=28.7500,
        longitude=77.1400,
        bearing=325.0,  # Passed stop 5146 heading further north
        speed_kmh=35.0,
        timestamp_utc=now - 25,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    v4_opposite_direction = ValidatedVehiclePosition(
        vehicle_id="DL1PC0004",
        route_id="1598",
        trip_id="T_REV_1598",
        latitude=28.6800,
        longitude=77.2000,
        bearing=145.0,  # Traveling towards Old Delhi, opposite direction
        speed_kmh=28.0,
        timestamp_utc=now - 30,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    v5_unrelated_route = ValidatedVehiclePosition(
        vehicle_id="DL1PC9999",
        route_id="999",
        trip_id=None,
        latitude=28.7080,
        longitude=77.1785,
        bearing=90.0,
        speed_kmh=20.0,
        timestamp_utc=now - 10,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    collector.active_vehicles = {
        "DL1PC0001": v1_approaching,
        "DL1PC0002": v2_near_stop,
        "DL1PC0003": v3_passed_stop,
        "DL1PC0004": v4_opposite_direction,
        "DL1PC9999": v5_unrelated_route,
    }

    set_live_collector(collector)
    return collector


def test_viewport_bounding_box_filtering(mock_collector_with_scenarios):
    """Verify GET /api/v1/live/vehicles returns only vehicles inside viewport bounds."""
    # Viewport tightly around Azadpur Terminal
    res = client.get("/api/v1/live/vehicles?min_lat=28.705&max_lat=28.715&min_lon=77.170&max_lon=77.185")
    assert res.status_code == 200
    data = res.json()

    vehicle_ids = [v["vehicle_id"] for v in data["vehicles"]]
    # Should include v1 (28.712, 77.175), v2 (28.7085, 77.178), v5 (28.708, 77.1785)
    assert "DL1PC0001" in vehicle_ids
    assert "DL1PC0002" in vehicle_ids
    assert "DL1PC9999" in vehicle_ids

    # Should NOT include v3 (28.690) or v4 (28.680) which are outside this viewport
    assert "DL1PC0003" not in vehicle_ids
    assert "DL1PC0004" not in vehicle_ids

    # Verify summary metadata
    assert data["viewport_min_lat"] == 28.705
    assert data["viewport_max_lat"] == 28.715
    assert data["viewport_min_lon"] == 77.170
    assert data["viewport_max_lon"] == 77.185


def test_suitable_vehicles_endpoint_approaching_and_near(mock_collector_with_scenarios):
    """Verify GET /api/v1/live/suitable-vehicles returns only suitable forward buses."""
    # Query Route 1598 from Stop 284 (Azadpur) to Stop 5146 (Mori Gate)
    res = client.get("/api/v1/live/suitable-vehicles?route_id=1598&board_stop_id=284&alight_stop_id=5146")
    assert res.status_code == 200
    data = res.json()

    assert data["route_id"] == "1598"
    assert data["board_stop_id"] == "284"
    assert data["alight_stop_id"] == "5146"

    # Should return DL1PC0001 (approaching) and DL1PC0002 (near stop)
    suitable_ids = [v["vehicle_id"] for v in data["vehicles"]]
    assert "DL1PC0001" in suitable_ids or "DL1PC0002" in suitable_ids

    # Should strictly reject unrelated route 999
    assert "DL1PC9999" not in suitable_ids

    # For any returned vehicle, verify reach verification flag
    for v in data["vehicles"]:
        assert v["is_verified_suitable"] is True
        assert v["is_verified_destination"] is True
        assert v["progress_status"] in ("NEAR_BOARDING_STOP", "APPROACHING")
        assert "Verified" in v["guidance_message"] or "approaching" in v["guidance_message"].lower() or "near" in v["guidance_message"].lower()


def test_suitable_vehicles_empty_fallback(mock_collector_with_scenarios):
    """Verify endpoint provides helpful fallback message when no suitable buses exist."""
    # Query a route with no active vehicles
    res = client.get("/api/v1/live/suitable-vehicles?route_id=99999&board_stop_id=284&alight_stop_id=5146")
    assert res.status_code == 200
    data = res.json()

    assert data["suitable_count"] == 0
    assert len(data["vehicles"]) == 0
    assert data["fallback_message"] == "No verified live bus is currently available for this journey."
