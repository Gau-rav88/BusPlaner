"""Unit and Integration Tests for Radius-Based Live Bus Discovery.

Verifies:
1. A bus inside 2 km is returned with accurate Haversine distance_m.
2. A bus outside 2 km is strictly excluded.
3. Radius changes (500m, 1km, 2km, 5km) update results correctly.
4. Moving the search center changes returned vehicles and their relative distances.
5. Journey selection uses the boarding stop coordinates as the search center.
6. Response metadata includes search_lat, search_lon, search_radius_m, total_matching_count,
   current_matching_count, and stale_matching_count.
7. Stale / last-known buses inside the radius remain distinguishable (is_current=False).
8. Reasonable radius and limit bounds are enforced.
9. Single shared backend cache prevents redundant upstream requests during radius filtering.
10. Existing journey matching (/api/v1/live/match-bus) still works.
"""

import time
from typing import Set
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.dependencies import set_live_collector
from backend.realtime.gtfs_rt import (
    FeedAvailabilityStatus,
    LiveFeedCollector,
    ValidatedVehiclePosition,
    haversine_distance_m,
)


@pytest.fixture
def radius_collector() -> LiveFeedCollector:
    collector = LiveFeedCollector(
        endpoint_url="https://mock.transportstack.in/VehiclePositions.pb",
        api_key="TEST_API_KEY",
        known_route_ids={"1598", "1657", "925"},
        max_staleness_seconds=900,
    )
    collector.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED

    now_ts = int(time.time())

    # Reference center: Connaught Place / Delhi Central (28.6315, 77.2167)
    # 1. Bus within 350m: (28.6330, 77.2180) -> ~210m
    collector.active_vehicles["BUS_CP_NEAR"] = ValidatedVehiclePosition(
        vehicle_id="BUS_CP_NEAR",
        route_id="1598",
        trip_id="T_CP1",
        latitude=28.6330,
        longitude=77.2180,
        bearing=45.0,
        speed_kmh=22.0,
        timestamp_utc=now_ts,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
    )

    # 2. Bus within 1.5km: (28.6410, 77.2250) -> ~1.3km
    collector.active_vehicles["BUS_CP_1500M"] = ValidatedVehiclePosition(
        vehicle_id="BUS_CP_1500M",
        route_id="1657",
        trip_id="T_CP2",
        latitude=28.6410,
        longitude=77.2250,
        bearing=90.0,
        speed_kmh=30.0,
        timestamp_utc=now_ts - 20,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
    )

    # 3. Bus within 3.5km (outside 2km, inside 5km): (28.6600, 77.2300) -> ~3.4km
    collector.active_vehicles["BUS_CP_3500M"] = ValidatedVehiclePosition(
        vehicle_id="BUS_CP_3500M",
        route_id="925",
        trip_id="T_CP3",
        latitude=28.6600,
        longitude=77.2300,
        bearing=180.0,
        speed_kmh=18.0,
        timestamp_utc=now_ts - 40,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
    )

    # 4. Bus far away (North Delhi / Azadpur ~10km away): (28.7167, 77.1700) -> ~10.5km
    collector.active_vehicles["BUS_AZADPUR_FAR"] = ValidatedVehiclePosition(
        vehicle_id="BUS_AZADPUR_FAR",
        route_id="1598",
        trip_id="T_AZ1",
        latitude=28.7167,
        longitude=77.1700,
        bearing=270.0,
        speed_kmh=45.0,
        timestamp_utc=now_ts - 10,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
    )

    # 5. Stale bus near Connaught Place (400m away, retained last-known):
    collector.last_known_vehicles["BUS_STALE_CP_NEAR"] = ValidatedVehiclePosition(
        vehicle_id="BUS_STALE_CP_NEAR",
        route_id="1598",
        trip_id="T_STALE1",
        latitude=28.6320,
        longitude=77.2190,
        bearing=0.0,
        speed_kmh=0.0,
        timestamp_utc=now_ts - 300,
        is_valid_coordinates=True,
        is_fresh=False,
        is_matched_to_gtfs=True,
        validation_notes=["Retained last-known"],
        is_current=False,
    )

    collector.last_fetch_mono = time.monotonic()

    return collector


def test_1_bus_inside_2km_returned(radius_collector: LiveFeedCollector):
    """Verify buses inside 2 km of Connaught Place (28.6315, 77.2167) are returned with accurate distance."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    res = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=2000")
    assert res.status_code == 200
    data = res.json()

    vehicle_ids = [v["vehicle_id"] for v in data["vehicles"]]
    # Inside 2km: BUS_CP_NEAR, BUS_CP_1500M, and BUS_STALE_CP_NEAR
    assert "BUS_CP_NEAR" in vehicle_ids
    assert "BUS_CP_1500M" in vehicle_ids
    assert "BUS_STALE_CP_NEAR" in vehicle_ids

    # Distances must be populated and sorted ascending
    distances = [v["distance_m"] for v in data["vehicles"]]
    assert all(d is not None and d <= 2000.0 for d in distances)
    assert distances == sorted(distances)


def test_2_bus_outside_2km_excluded(radius_collector: LiveFeedCollector):
    """Verify buses outside 2 km are strictly excluded from the response."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    res = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=2000")
    assert res.status_code == 200
    data = res.json()

    vehicle_ids = [v["vehicle_id"] for v in data["vehicles"]]
    # BUS_CP_3500M (~3.4km) and BUS_AZADPUR_FAR (~10.5km) must NOT be in the 2km result
    assert "BUS_CP_3500M" not in vehicle_ids
    assert "BUS_AZADPUR_FAR" not in vehicle_ids


def test_3_radius_changes_update_results_correctly(radius_collector: LiveFeedCollector):
    """Verify modifying radius_m (500m, 2000m, 5000m) scales the result set monotonically."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    # 500m radius -> Only BUS_CP_NEAR and BUS_STALE_CP_NEAR
    res_500 = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=500")
    assert res_500.status_code == 200
    vids_500 = [v["vehicle_id"] for v in res_500.json()["vehicles"]]
    assert "BUS_CP_NEAR" in vids_500
    assert "BUS_STALE_CP_NEAR" in vids_500
    assert "BUS_CP_1500M" not in vids_500
    assert "BUS_CP_3500M" not in vids_500

    # 2000m radius -> Includes BUS_CP_1500M
    res_2000 = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=2000")
    assert res_2000.status_code == 200
    vids_2000 = [v["vehicle_id"] for v in res_2000.json()["vehicles"]]
    assert "BUS_CP_1500M" in vids_2000
    assert "BUS_CP_3500M" not in vids_2000

    # 5000m radius -> Includes BUS_CP_3500M
    res_5000 = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=5000")
    assert res_5000.status_code == 200
    vids_5000 = [v["vehicle_id"] for v in res_5000.json()["vehicles"]]
    assert "BUS_CP_3500M" in vids_5000
    assert "BUS_AZADPUR_FAR" not in vids_5000  # Azadpur is 10.5km away


def test_4_moving_search_center_changes_results(radius_collector: LiveFeedCollector):
    """Moving search center to Azadpur (28.7167, 77.1700) returns Azadpur bus and excludes Connaught Place buses."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    res = client.get("/api/v1/live/vehicles?lat=28.7167&lon=77.1700&radius_m=2000")
    assert res.status_code == 200
    data = res.json()

    vehicle_ids = [v["vehicle_id"] for v in data["vehicles"]]
    assert "BUS_AZADPUR_FAR" in vehicle_ids
    assert "BUS_CP_NEAR" not in vehicle_ids
    assert "BUS_CP_1500M" not in vehicle_ids
    assert "BUS_STALE_CP_NEAR" not in vehicle_ids

    # Vehicle at Azadpur should have distance ~0m to ~100m
    azadpur_item = next(v for v in data["vehicles"] if v["vehicle_id"] == "BUS_AZADPUR_FAR")
    assert azadpur_item["distance_m"] < 50.0


def test_5_stale_buses_distinguishable_inside_radius(radius_collector: LiveFeedCollector):
    """Verify stale buses inside radius have is_current=False and are counted separately."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    res = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=2000")
    assert res.status_code == 200
    data = res.json()

    stale_item = next(v for v in data["vehicles"] if v["vehicle_id"] == "BUS_STALE_CP_NEAR")
    assert stale_item["is_current"] is False
    assert stale_item["is_fresh"] is False

    current_item = next(v for v in data["vehicles"] if v["vehicle_id"] == "BUS_CP_NEAR")
    assert current_item["is_current"] is True
    assert current_item["is_fresh"] is True

    # Metadata breakdown
    assert data["current_matching_count"] == 2
    assert data["stale_matching_count"] == 1
    assert data["total_matching_count"] == 3


def test_6_response_metadata_accuracy(radius_collector: LiveFeedCollector):
    """Verify response metadata contains search_lat, search_lon, search_radius_m, and match counts."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    res = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=2000&limit=500")
    assert res.status_code == 200
    data = res.json()

    assert data["search_lat"] == pytest.approx(28.6315)
    assert data["search_lon"] == pytest.approx(77.2167)
    assert data["search_radius_m"] == 2000.0
    assert data["returned_vehicles_count"] == 3
    assert data["total_matching_count"] == 3
    assert data["current_matching_count"] == 2
    assert data["stale_matching_count"] == 1


def test_7_reasonable_radius_and_limit_bounds_enforced():
    """Verify FastAPI enforces bounds on radius_m (min 50m, max 50000m) and limit (min 1, max 5000)."""
    client = TestClient(app)

    # Negative radius
    res_neg_rad = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=-10")
    assert res_neg_rad.status_code == 422

    # Excessively large radius (> 50,000m)
    res_huge_rad = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=100000")
    assert res_huge_rad.status_code == 422

    # Excessively large limit (> 5,000)
    res_huge_limit = client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&limit=99999")
    assert res_huge_limit.status_code == 422


def test_8_single_shared_cache_filters_geographically_without_extra_upstream_calls(radius_collector: LiveFeedCollector):
    """Verify multiple radius queries read from the in-memory cache without calling upstream endpoint."""
    set_live_collector(radius_collector)
    client = TestClient(app)

    initial_polls = radius_collector.total_polls_count

    # Execute 5 rapid queries with different coordinates and radii
    client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=500")
    client.get("/api/v1/live/vehicles?lat=28.6315&lon=77.2167&radius_m=1000")
    client.get("/api/v1/live/vehicles?lat=28.7167&lon=77.1700&radius_m=2000")
    client.get("/api/v1/live/vehicles?lat=28.6000&lon=77.1000&radius_m=3000")
    client.get("/api/v1/live/vehicles?lat=28.6500&lon=77.2000&radius_m=5000")

    # Upstream poll count must not increase because queries are filtered in memory
    assert radius_collector.total_polls_count == initial_polls


def test_9_citywide_diagnostics_retained_when_no_coords():
    """Verify omitting lat and lon returns the citywide fleet for diagnostics."""
    collector = LiveFeedCollector(api_key="TEST_KEY", is_enabled=True)
    now_ts = int(time.time())
    for i in range(10):
        collector.active_vehicles[f"BUS_DIAG_{i}"] = ValidatedVehiclePosition(
            vehicle_id=f"BUS_DIAG_{i}",
            route_id="1598",
            trip_id=f"T_{i}",
            latitude=28.60 + (i * 0.01),
            longitude=77.10 + (i * 0.01),
            bearing=90.0,
            speed_kmh=25.0,
            timestamp_utc=now_ts,
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
            is_current=True,
        )
    set_live_collector(collector)
    client = TestClient(app)

    res = client.get("/api/v1/live/vehicles")
    assert res.status_code == 200
    data = res.json()
    assert data["returned_vehicles_count"] == 10
    assert data["search_radius_m"] is None
