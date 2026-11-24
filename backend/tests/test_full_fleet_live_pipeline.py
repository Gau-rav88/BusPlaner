"""Unit and Integration Tests for Full Fleet Live GTFS-RT Pipeline.

Verifies all 10 requirements from PRD v3.0 Milestone:
1. A vehicle without a static GTFS route match still appears on the map/API.
2. A vehicle without a trip ID still appears on the map/API.
3. A valid vehicle with an unknown direction still appears.
4. Duplicate vehicle IDs do not create duplicate markers/records.
5. Complete snapshots update the current vehicle set correctly.
6. Partial updates / missing vehicles are preserved until stale.
7. Missing vehicles are not falsely presented as current.
8. Failed upstream requests preserve last-known positions with stale labels.
9. A newer response cannot be overwritten by an older response.
10. Geographic classification separates Delhi Core from NCR Out-of-Bounds and Invalid Geography.
"""

import time
from typing import Set
import pytest

try:
    import google.transit.gtfs_realtime_pb2 as gtfs_rt
except ImportError:
    gtfs_rt = None

from backend.realtime.gtfs_rt import (
    DELHI_BBOX_LAT_MIN,
    DELHI_BBOX_LAT_MAX,
    DELHI_BBOX_LON_MIN,
    DELHI_BBOX_LON_MAX,
    FeedAvailabilityStatus,
    LiveFeedCollector,
    ValidatedVehiclePosition,
    classify_coordinates,
)


@pytest.fixture
def collector() -> LiveFeedCollector:
    known_routes: Set[str] = {"1598", "925"}
    return LiveFeedCollector(
        endpoint_url="https://mock.transportstack.in/VehiclePositions.pb",
        api_key="TEST_API_KEY",
        known_route_ids=known_routes,
        max_staleness_seconds=900,
    )


def test_classify_coordinates():
    """Verify coordinate classification into Delhi Core, NCR Corridor, and Invalid."""
    # Delhi Core
    valid, out_of_area, area_class = classify_coordinates(28.7075, 77.1782)
    assert valid is True
    assert out_of_area is False
    assert area_class == "DELHI_CORE"

    # NCR Corridor (e.g. Sonipat border on GT Road)
    valid, out_of_area, area_class = classify_coordinates(28.9624, 77.0919)
    assert valid is True
    assert out_of_area is True
    assert area_class == "NCR_OUT_OF_BOUNDS"

    # Invalid Geography (e.g. 0.0, 0.0 or outside India)
    valid, out_of_area, area_class = classify_coordinates(0.0, 0.0)
    assert valid is False
    assert out_of_area is True
    assert area_class == "INVALID_GEOGRAPHY"

    # None or NaN
    valid, out_of_area, area_class = classify_coordinates(None, 77.1782)
    assert valid is False
    assert area_class == "INVALID_GEOGRAPHY"


def test_1_vehicle_without_static_gtfs_route_match_appears(collector: LiveFeedCollector):
    """Req 1: A vehicle without a static GTFS route match still appears."""
    now_ts = int(time.time())
    pos = ValidatedVehiclePosition(
        vehicle_id="DL51_UNMATCHED",
        route_id="NON_EXISTENT_ROUTE_9999",
        trip_id="T_9999",
        latitude=28.7075,
        longitude=77.1782,
        bearing=90.0,
        speed_kmh=35.0,
        timestamp_utc=now_ts,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=False,
        validation_notes=["Route ID not in static GTFS"],
    )
    collector.active_vehicles[pos.vehicle_id] = pos

    vehicles = collector.get_live_vehicles()
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "DL51_UNMATCHED"
    assert vehicles[0]["route_id"] == "NON_EXISTENT_ROUTE_9999"
    assert vehicles[0]["is_matched_to_gtfs"] is False
    assert vehicles[0]["is_current"] is True


def test_2_vehicle_without_trip_id_appears(collector: LiveFeedCollector):
    """Req 2: A vehicle without a trip ID still appears."""
    now_ts = int(time.time())
    pos = ValidatedVehiclePosition(
        vehicle_id="DL51_NO_TRIP",
        route_id="1598",
        trip_id=None,
        latitude=28.7075,
        longitude=77.1782,
        bearing=180.0,
        speed_kmh=20.0,
        timestamp_utc=now_ts,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
    )
    collector.active_vehicles[pos.vehicle_id] = pos

    vehicles = collector.get_live_vehicles()
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "DL51_NO_TRIP"
    assert vehicles[0]["trip_id"] is None
    assert vehicles[0]["is_current"] is True


def test_3_valid_vehicle_with_unknown_direction_appears(collector: LiveFeedCollector):
    """Req 3: A valid vehicle with an unknown direction still appears."""
    now_ts = int(time.time())
    pos = ValidatedVehiclePosition(
        vehicle_id="DL51_NO_BEARING",
        route_id="1598",
        trip_id="T1",
        latitude=28.7075,
        longitude=77.1782,
        bearing=None,  # Unknown bearing
        speed_kmh=15.0,
        timestamp_utc=now_ts,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
    )
    collector.active_vehicles[pos.vehicle_id] = pos

    vehicles = collector.get_live_vehicles()
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "DL51_NO_BEARING"
    assert vehicles[0]["bearing"] is None
    assert vehicles[0]["is_current"] is True


def test_4_duplicate_vehicle_ids_deduplicated(collector: LiveFeedCollector):
    """Req 4: Duplicate vehicle IDs do not create duplicate markers."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 missing")

    now_ts = int(time.time())
    feed = gtfs_rt.FeedMessage()

    # First entity for DL1PD9999
    e1 = feed.entity.add()
    e1.id = "ent1"
    e1.vehicle.vehicle.id = "DL1PD9999"
    e1.vehicle.position.latitude = 28.7075
    e1.vehicle.position.longitude = 77.1782
    e1.vehicle.timestamp = now_ts

    # Duplicate entity for DL1PD9999 with newer timestamp and slightly moved position
    e2 = feed.entity.add()
    e2.id = "ent2"
    e2.vehicle.vehicle.id = "DL1PD9999"
    e2.vehicle.position.latitude = 28.7085
    e2.vehicle.position.longitude = 77.1792
    e2.vehicle.timestamp = now_ts + 5

    validated = collector.validate_and_filter_entities(feed, reference_time_utc=now_ts + 10)
    assert len(validated) == 1
    assert collector.last_duplicate_count == 1

    collector._update_active_vehicles(validated)
    vehicles = collector.get_live_vehicles()
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "DL1PD9999"
    assert pytest.approx(vehicles[0]["latitude"], rel=1e-5) == 28.7085
    assert vehicles[0]["timestamp_utc"] == now_ts + 5


def test_5_complete_snapshots_update_current_vehicle_set(collector: LiveFeedCollector):
    """Req 5: Complete snapshots update the current vehicle set correctly."""
    now_ts = int(time.time())

    # Snapshot 1: V1, V2
    s1_v1 = ValidatedVehiclePosition(
        vehicle_id="V1", route_id="101", trip_id=None,
        latitude=28.70, longitude=77.17, bearing=None, speed_kmh=20.0,
        timestamp_utc=now_ts, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    s1_v2 = ValidatedVehiclePosition(
        vehicle_id="V2", route_id="102", trip_id=None,
        latitude=28.71, longitude=77.18, bearing=None, speed_kmh=25.0,
        timestamp_utc=now_ts, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    collector._update_active_vehicles([s1_v1, s1_v2], header_timestamp=100)

    assert set(collector.active_vehicles.keys()) == {"V1", "V2"}
    assert len(collector.last_known_vehicles) == 0

    # Snapshot 2: V2 (moved), V3 (new) - V1 is missing from snapshot 2
    s2_v2 = ValidatedVehiclePosition(
        vehicle_id="V2", route_id="102", trip_id=None,
        latitude=28.72, longitude=77.19, bearing=None, speed_kmh=30.0,
        timestamp_utc=now_ts + 20, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    s2_v3 = ValidatedVehiclePosition(
        vehicle_id="V3", route_id="103", trip_id=None,
        latitude=28.73, longitude=77.20, bearing=None, speed_kmh=15.0,
        timestamp_utc=now_ts + 20, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    collector._update_active_vehicles([s2_v2, s2_v3], header_timestamp=120)

    # Active vehicles must be exactly V2 and V3
    assert set(collector.active_vehicles.keys()) == {"V2", "V3"}
    assert collector.active_vehicles["V2"].latitude == 28.72
    assert collector.active_vehicles["V2"].is_current is True

    # V1 must be retained in last_known_vehicles, marked not current and not fresh
    assert "V1" in collector.last_known_vehicles
    assert collector.last_known_vehicles["V1"].is_current is False
    assert collector.last_known_vehicles["V1"].is_fresh is False


def test_6_partial_updates_preserve_vehicles_until_stale(collector: LiveFeedCollector):
    """Req 6: Missing vehicles are preserved in last_known until max_staleness_seconds."""
    now_ts = int(time.time())

    # Initial snapshot with V_OLD
    v_old = ValidatedVehiclePosition(
        vehicle_id="V_OLD", route_id="101", trip_id=None,
        latitude=28.70, longitude=77.17, bearing=None, speed_kmh=0.0,
        timestamp_utc=now_ts - 800,  # 800s old (< 900s)
        is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    collector._update_active_vehicles([v_old], header_timestamp=100)

    # New snapshot with only V_NEW
    v_new = ValidatedVehiclePosition(
        vehicle_id="V_NEW", route_id="102", trip_id=None,
        latitude=28.71, longitude=77.18, bearing=None, speed_kmh=10.0,
        timestamp_utc=now_ts, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    collector._update_active_vehicles([v_new], header_timestamp=120)

    # V_OLD is preserved in last_known_vehicles
    assert "V_OLD" in collector.last_known_vehicles

    # When query is run with now_ts, V_OLD is included (with include_stale=True)
    all_vehicles = collector.get_live_vehicles(include_stale=True, now_ts=now_ts)
    ids = {v["vehicle_id"] for v in all_vehicles}
    assert "V_OLD" in ids
    assert "V_NEW" in ids

    # When time advances past max_staleness_seconds (900s):
    future_ts = now_ts + 200  # age of V_OLD is now 800 + 200 = 1000s (> 900s)
    # Next update evicts V_OLD
    collector._update_active_vehicles([v_new], header_timestamp=140)
    all_vehicles_future = collector.get_live_vehicles(include_stale=True, now_ts=future_ts)
    future_ids = {v["vehicle_id"] for v in all_vehicles_future}
    assert "V_OLD" not in future_ids


def test_7_missing_vehicles_not_falsely_presented_as_current(collector: LiveFeedCollector):
    """Req 7: Missing vehicles are not falsely presented as current."""
    now_ts = int(time.time())

    # Snapshot 1 with V_GONE
    v_gone = ValidatedVehiclePosition(
        vehicle_id="V_GONE", route_id="101", trip_id=None,
        latitude=28.70, longitude=77.17, bearing=None, speed_kmh=0.0,
        timestamp_utc=now_ts - 50, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    collector._update_active_vehicles([v_gone], header_timestamp=100)

    # Snapshot 2 without V_GONE
    collector._update_active_vehicles([], header_timestamp=120)

    vehicles = collector.get_live_vehicles(include_stale=True, now_ts=now_ts)
    assert len(vehicles) == 1
    v = vehicles[0]
    assert v["vehicle_id"] == "V_GONE"
    assert v["is_current"] is False
    assert v["is_fresh"] is False


def test_8_failed_upstream_preserves_last_known_with_stale_labels(collector: LiveFeedCollector):
    """Req 8: Failed upstream requests preserve last-known positions with stale labels."""
    now_ts = int(time.time())
    v1 = ValidatedVehiclePosition(
        vehicle_id="V1", route_id="101", trip_id=None,
        latitude=28.70, longitude=77.17, bearing=None, speed_kmh=20.0,
        timestamp_utc=now_ts - 10, is_valid_coordinates=True, is_fresh=True,
        is_matched_to_gtfs=False, validation_notes=[],
    )
    collector._update_active_vehicles([v1], header_timestamp=100)

    # Simulate upstream network failure
    collector._mark_all_vehicles_stale()

    vehicles = collector.get_live_vehicles()
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "V1"
    assert vehicles[0]["is_fresh"] is False
    assert vehicles[0]["is_current"] is False


def test_9_newer_response_cannot_be_overwritten_by_older_response(collector: LiveFeedCollector, monkeypatch):
    """Req 9: A newer response cannot be overwritten by an older response."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 missing")

    # Seed collector with header timestamp 2000
    collector.latest_feed_header_timestamp = 2000
    collector.active_vehicles = {
        "V_NEWEST": ValidatedVehiclePosition(
            vehicle_id="V_NEWEST", route_id="101", trip_id=None,
            latitude=28.70, longitude=77.17, bearing=None, speed_kmh=0.0,
            timestamp_utc=2000, is_valid_coordinates=True, is_fresh=True,
            is_matched_to_gtfs=False, validation_notes=[],
        )
    }

    # Create older protobuf with header timestamp 1000
    feed_older = gtfs_rt.FeedMessage()
    feed_older.header.gtfs_realtime_version = "2.0"
    feed_older.header.timestamp = 1000
    e = feed_older.entity.add()
    e.id = "e1"
    e.vehicle.vehicle.id = "V_OLDER"
    e.vehicle.position.latitude = 28.71
    e.vehicle.position.longitude = 77.18
    e.vehicle.timestamp = 1000

    raw_bytes = feed_older.SerializeToString()

    class MockResp:
        status_code = 200
        content = raw_bytes

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: MockResp())

    # Attempt fetch
    status, msg = collector.refresh_if_expired(force=True)

    # Older feed must be discarded without overwriting active_vehicles
    assert "Discarded older GTFS-RT feed snapshot" in str(msg)
    assert "V_NEWEST" in collector.active_vehicles
    assert "V_OLDER" not in collector.active_vehicles
    assert collector.latest_feed_header_timestamp == 2000


def test_10_ncr_out_of_area_vehicles_tracked_and_classified(collector: LiveFeedCollector):
    """Req 10: NCR interstate buses outside Delhi Core are tracked and classified cleanly."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 missing")

    now_ts = int(time.time())
    feed = gtfs_rt.FeedMessage()

    # Core Delhi bus
    e1 = feed.entity.add()
    e1.id = "e1"
    e1.vehicle.vehicle.id = "BUS_CORE"
    e1.vehicle.position.latitude = 28.7075
    e1.vehicle.position.longitude = 77.1782
    e1.vehicle.timestamp = now_ts

    # NCR Sonipat corridor bus (28.9624, 77.0919)
    e2 = feed.entity.add()
    e2.id = "e2"
    e2.vehicle.vehicle.id = "BUS_NCR_SONIPAT"
    e2.vehicle.position.latitude = 28.9624
    e2.vehicle.position.longitude = 77.0919
    e2.vehicle.timestamp = now_ts

    # Invalid geography (lat=0, lon=0)
    e3 = feed.entity.add()
    e3.id = "e3"
    e3.vehicle.vehicle.id = "BUS_INVALID_COORDS"
    e3.vehicle.position.latitude = 0.0
    e3.vehicle.position.longitude = 0.0
    e3.vehicle.timestamp = now_ts

    validated = collector.validate_and_filter_entities(feed, reference_time_utc=now_ts)
    collector._update_active_vehicles(validated)

    assert "BUS_CORE" in collector.active_vehicles
    assert collector.active_vehicles["BUS_CORE"].area_classification == "DELHI_CORE"
    assert collector.active_vehicles["BUS_CORE"].is_out_of_area is False

    assert "BUS_NCR_SONIPAT" in collector.out_of_area_vehicles
    assert collector.out_of_area_vehicles["BUS_NCR_SONIPAT"].area_classification == "NCR_OUT_OF_BOUNDS"
    assert collector.out_of_area_vehicles["BUS_NCR_SONIPAT"].is_out_of_area is True

    # Invalid coordinates are not tracked in active or out_of_area
    assert "BUS_INVALID_COORDS" not in collector.active_vehicles
    assert "BUS_INVALID_COORDS" not in collector.out_of_area_vehicles

    # get_live_vehicles with include_out_of_area=True returns both
    all_v = collector.get_live_vehicles(include_out_of_area=True)
    vids = {v["vehicle_id"] for v in all_v}
    assert "BUS_CORE" in vids
    assert "BUS_NCR_SONIPAT" in vids
    assert "BUS_INVALID_COORDS" not in vids
