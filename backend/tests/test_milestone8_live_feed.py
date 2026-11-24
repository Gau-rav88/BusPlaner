"""Milestone 8 Unit and Integration Tests: GTFS-Realtime Live Feed Readiness.

PRD v3.0 Milestone 8:
Verifies:
- Missing API key -> AUTH_REQUIRED
- Invalid API key (HTTP 401) -> AUTH_REQUIRED
- Feed timeout (requests.Timeout) -> UNAVAILABLE
- Malformed protobuf / HTML error response -> INVALID_DATA
- Empty feed -> AVAILABLE_PARTIAL
- Valid protobuf feed parsing -> AVAILABLE_VALIDATED
- Coordinate bounds validation (Delhi bounding box)
- Timestamp staleness rejection (> 900s)
- Vehicle update deduplication
- Static GTFS cross-referencing
- Failure counter and recovery
"""

import time
from unittest.mock import MagicMock, patch
import pytest
import requests

from backend.realtime.gtfs_rt import (
    FeedAvailabilityStatus,
    LiveFeedCollector,
    ValidatedVehiclePosition,
    DELHI_BBOX_LAT_MIN,
    DELHI_BBOX_LAT_MAX,
    DELHI_BBOX_LON_MIN,
    DELHI_BBOX_LON_MAX,
)

try:
    import google.transit.gtfs_realtime_pb2 as gtfs_rt
except ImportError:
    gtfs_rt = None


def create_mock_feed_message(entities_data):
    """Helper to synthesize GTFS-RT FeedMessage protobuf bytes for testing."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 is not available")

    feed = gtfs_rt.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.incrementality = gtfs_rt.FeedHeader.FULL_DATASET
    feed.header.timestamp = int(time.time())

    for idx, e in enumerate(entities_data):
        entity = feed.entity.add()
        entity.id = str(e.get("entity_id", f"e_{idx}"))
        v = entity.vehicle
        v.vehicle.id = str(e.get("vehicle_id", f"DL1P_{idx}"))
        if "route_id" in e:
            v.trip.route_id = str(e["route_id"])
        if "trip_id" in e:
            v.trip.trip_id = str(e["trip_id"])
        if "lat" in e and "lon" in e:
            v.position.latitude = float(e["lat"])
            v.position.longitude = float(e["lon"])
        if "speed" in e:
            v.position.speed = float(e["speed"])
        if "bearing" in e:
            v.position.bearing = float(e["bearing"])
        if "timestamp" in e:
            v.timestamp = int(e["timestamp"])

    return feed.SerializeToString()


def test_live_feed_missing_api_key():
    """Verify that omitting the API key results in AUTH_REQUIRED without dispatching network calls."""
    collector = LiveFeedCollector(api_key="")
    with patch("requests.get") as mock_get:
        status, msg = collector.check_feed_availability()
        mock_get.assert_not_called()

    assert status == FeedAvailabilityStatus.AUTH_REQUIRED
    assert "DELHI_TRANSPORTSTACK_API_KEY environment variable is not configured" in msg
    assert collector.consecutive_failure_count == 1
    assert collector.total_polls_count == 1
    assert collector.get_status_payload()["auth_configured"] is False


def test_live_feed_invalid_api_key_401():
    """Verify that HTTP 401 returns AUTH_REQUIRED with failure count increment."""
    collector = LiveFeedCollector(api_key="bad_token_123")
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error":"Invalid API key"}'

    with patch("requests.get", return_value=mock_resp):
        status, msg = collector.check_feed_availability()

    assert status == FeedAvailabilityStatus.AUTH_REQUIRED
    assert "HTTP 401" in msg
    assert collector.consecutive_failure_count == 1


def test_live_feed_timeout():
    """Verify that network timeout returns UNAVAILABLE without crashing."""
    collector = LiveFeedCollector(api_key="valid_token_xyz")
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        status, msg = collector.check_feed_availability()

    assert status == FeedAvailabilityStatus.UNAVAILABLE
    assert "timeout" in msg.lower()
    assert collector.consecutive_failure_count == 1


def test_live_feed_malformed_html_response():
    """Verify that HTML error pages or non-protobuf payloads return INVALID_DATA."""
    collector = LiveFeedCollector(api_key="valid_token_xyz")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"<!DOCTYPE html><html><body>Error 502 Bad Gateway</body></html>"

    with patch("requests.get", return_value=mock_resp):
        status, msg = collector.check_feed_availability()

    assert status == FeedAvailabilityStatus.INVALID_DATA
    assert "HTML/JSON text instead of GTFS-RT binary protobuf" in msg
    assert collector.consecutive_failure_count == 1


def test_live_feed_empty_feed():
    """Verify that a valid protobuf with 0 entities returns AVAILABLE_PARTIAL."""
    collector = LiveFeedCollector(api_key="valid_token_xyz")
    raw_empty = create_mock_feed_message([])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = raw_empty

    with patch("requests.get", return_value=mock_resp):
        status, msg = collector.check_feed_availability()

    assert status == FeedAvailabilityStatus.AVAILABLE_PARTIAL
    assert "0 vehicle entities" in msg


def test_live_feed_valid_entities_and_recovery():
    """Verify that valid protobuf returns AVAILABLE_VALIDATED and resets failure counters."""
    collector = LiveFeedCollector(api_key="valid_token_xyz")
    collector.consecutive_failure_count = 5

    raw_feed = create_mock_feed_message([
        {"vehicle_id": "DL1PD1001", "lat": 28.7075, "lon": 77.1782, "timestamp": int(time.time()), "route_id": "1598"},
        {"vehicle_id": "DL1PD1002", "lat": 28.7150, "lon": 77.1700, "timestamp": int(time.time()), "route_id": "1598"},
    ])
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = raw_feed

    with patch("requests.get", return_value=mock_resp):
        status, msg = collector.check_feed_availability()

    assert status == FeedAvailabilityStatus.AVAILABLE_VALIDATED
    assert "2 active vehicle position entities" in msg
    assert collector.consecutive_failure_count == 0
    assert collector.total_success_count == 1
    assert collector.last_success_timestamp_utc is not None


def test_coordinate_validation_delhi_bbox():
    """Verify out-of-bounds coordinates are rejected while within-bounds are retained."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 missing")

    collector = LiveFeedCollector()
    now_ts = int(time.time())

    feed = gtfs_rt.FeedMessage()
    # 1. Valid: In Delhi (Azadpur)
    e1 = feed.entity.add()
    e1.id = "v1"
    e1.vehicle.vehicle.id = "DL1PD1001"
    e1.vehicle.position.latitude = 28.7075
    e1.vehicle.position.longitude = 77.1782
    e1.vehicle.timestamp = now_ts

    # 2. Invalid: Outside Delhi (Mumbai lat 19.07, lon 72.87)
    e2 = feed.entity.add()
    e2.id = "v2"
    e2.vehicle.vehicle.id = "MH01_9999"
    e2.vehicle.position.latitude = 19.0760
    e2.vehicle.position.longitude = 72.8777
    e2.vehicle.timestamp = now_ts

    retained = collector.validate_and_filter_entities(feed, reference_time_utc=now_ts)
    assert len(retained) == 1
    assert retained[0].vehicle_id == "DL1PD1001"
    assert retained[0].is_valid_coordinates is True


def test_timestamp_staleness_rejection():
    """Verify vehicle pings older than 900 seconds are flagged as stale."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 missing")

    collector = LiveFeedCollector()
    now_ts = int(time.time())

    feed = gtfs_rt.FeedMessage()
    # Fresh: 60s ago
    e1 = feed.entity.add()
    e1.id = "fresh"
    e1.vehicle.vehicle.id = "BUS_FRESH"
    e1.vehicle.position.latitude = 28.7075
    e1.vehicle.position.longitude = 77.1782
    e1.vehicle.timestamp = now_ts - 60

    # Stale: 1800s ago (30 min)
    e2 = feed.entity.add()
    e2.id = "stale"
    e2.vehicle.vehicle.id = "BUS_STALE"
    e2.vehicle.position.latitude = 28.7100
    e2.vehicle.position.longitude = 77.1800
    e2.vehicle.timestamp = now_ts - 1800

    retained = collector.validate_and_filter_entities(feed, reference_time_utc=now_ts)
    by_id = {v.vehicle_id: v for v in retained}

    assert by_id["BUS_FRESH"].is_fresh is True
    assert by_id["BUS_STALE"].is_fresh is False
    assert any("Stale update" in n for n in by_id["BUS_STALE"].validation_notes)


def test_deduplication_and_gtfs_matching():
    """Verify deduplication by vehicle_id and static GTFS route matching."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 missing")

    known_routes = {"1598", "925"}
    collector = LiveFeedCollector(known_route_ids=known_routes)
    now_ts = int(time.time())

    feed = gtfs_rt.FeedMessage()
    # Vehicle with matched route
    e1 = feed.entity.add()
    e1.id = "e1"
    e1.vehicle.vehicle.id = "BUS_MATCHED"
    e1.vehicle.trip.route_id = "1598"
    e1.vehicle.position.latitude = 28.7075
    e1.vehicle.position.longitude = 77.1782
    e1.vehicle.timestamp = now_ts

    # Vehicle with unmatched route
    e2 = feed.entity.add()
    e2.id = "e2"
    e2.vehicle.vehicle.id = "BUS_UNMATCHED"
    e2.vehicle.trip.route_id = "UNKNOWN_9999"
    e2.vehicle.position.latitude = 28.7100
    e2.vehicle.position.longitude = 77.1800
    e2.vehicle.timestamp = now_ts

    # Duplicate of vehicle 1 in same batch
    e3 = feed.entity.add()
    e3.id = "e3"
    e3.vehicle.vehicle.id = "BUS_MATCHED"
    e3.vehicle.trip.route_id = "1598"
    e3.vehicle.position.latitude = 28.7080
    e3.vehicle.position.longitude = 77.1790
    e3.vehicle.timestamp = now_ts + 10

    retained = collector.validate_and_filter_entities(feed, reference_time_utc=now_ts + 10)
    # active_vehicles dictionary deduplicates by vehicle_id
    assert len(collector.active_vehicles) == 2
    assert collector.active_vehicles["BUS_MATCHED"].is_matched_to_gtfs is True
    assert collector.active_vehicles["BUS_UNMATCHED"].is_matched_to_gtfs is False


def test_spatial_proximity_and_haversine_filtering():
    """Verify get_live_vehicles calculates distance and sorts by proximity within radius."""
    collector = LiveFeedCollector()
    now_ts = int(time.time())

    # Add 3 mock vehicles at different distances from Azadpur (28.7075, 77.1782)
    # v1: ~50m away
    # v2: ~800m away
    # v3: ~15km away (in South Delhi)
    collector.active_vehicles = {
        "V_NEAR": ValidatedVehiclePosition(
            vehicle_id="V_NEAR",
            route_id="1598",
            trip_id="T1",
            latitude=28.7079,
            longitude=77.1785,
            bearing=90.0,
            speed_kmh=22.0,
            timestamp_utc=now_ts,
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        ),
        "V_MID": ValidatedVehiclePosition(
            vehicle_id="V_MID",
            route_id="1598",
            trip_id="T2",
            latitude=28.7140,
            longitude=77.1750,
            bearing=180.0,
            speed_kmh=15.0,
            timestamp_utc=now_ts,
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        ),
        "V_FAR": ValidatedVehiclePosition(
            vehicle_id="V_FAR",
            route_id="1598",
            trip_id="T3",
            latitude=28.5500,
            longitude=77.2000,
            bearing=None,
            speed_kmh=0.0,
            timestamp_utc=now_ts,
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        ),
    }

    # Query with radius 2000m around Azadpur
    res = collector.get_live_vehicles(lat=28.7075, lon=77.1782, radius_m=2000.0)
    assert len(res) == 2
    assert res[0]["vehicle_id"] == "V_NEAR"
    assert res[1]["vehicle_id"] == "V_MID"
    assert res[0]["distance_m"] is not None
    assert res[0]["distance_m"] < res[1]["distance_m"]


def test_collector_10s_backend_cache():
    """Verify check_feed_availability caches responses within 10 seconds to protect upstream provider."""
    collector = LiveFeedCollector(api_key="TEST_KEY")
    collector.active_vehicles = {"V1": MagicMock()}
    collector.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED
    collector.last_fetch_mono = time.monotonic()  # Just fetched

    # Second call within 10s should NOT trigger requests.get
    with patch("requests.get") as mock_get:
        status, _ = collector.check_feed_availability()
        mock_get.assert_not_called()
        assert status == FeedAvailabilityStatus.AVAILABLE_VALIDATED

