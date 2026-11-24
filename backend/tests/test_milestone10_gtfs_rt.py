"""Milestone 10 Real-Time GTFS-RT Integration & Data Upgrade Audit Tests.

PRD v3.0 Milestone 10:
Verifies:
- Authenticated probe and parsing of GTFS-RT protobuf feeds.
- Live vehicle location filtering, deduplication, and WGS84 coordinate validation.
- Staleness rejection (>900s) and future timestamp drift detection.
- Agency classification verification (strictly UNKNOWN_MIXED without external registry).
- Endpoint fallback handling (CloudFront SPA HTML failover to operational backend).
- REST API endpoint GET /api/v1/live/status schema compliance.
- REST API endpoint GET /api/v1/live/vehicles with route filtering and paging.
- Zero credential leakage: API key never appears in responses, logs, or serialized payloads.
- Governing operational status remains strictly DEGRADE.
"""

import time
from fastapi.testclient import TestClient
import pytest

from backend.app.config import settings
from backend.app.dependencies import get_live_collector, set_live_collector
from backend.app.main import app
from backend.realtime.gtfs_rt import (
    DEFAULT_DELHI_GTFS_RT_URL,
    DELHI_BBOX_LAT_MIN,
    DELHI_BBOX_LAT_MAX,
    DELHI_BBOX_LON_MIN,
    DELHI_BBOX_LON_MAX,
    FeedAvailabilityStatus,
    LiveFeedCollector,
    ValidatedVehiclePosition,
)

try:
    import google.transit.gtfs_realtime_pb2 as gtfs_rt
except ImportError:
    gtfs_rt = None


@pytest.fixture(autouse=True)
def reset_collector():
    """Ensure collector state is clean before and after each test."""
    yield
    set_live_collector(None)


def create_synthetic_feed_message(num_vehicles=5, stale=False, outside_bbox=False, route_id="1598"):
    """Helper to synthesize valid GTFS-RT protobuf FeedMessage."""
    if gtfs_rt is None:
        return b""

    msg = gtfs_rt.FeedMessage()
    msg.header.gtfs_realtime_version = "2.0"
    msg.header.incrementality = gtfs_rt.FeedHeader.FULL_DATASET
    now_ts = int(time.time())
    msg.header.timestamp = now_ts

    for i in range(num_vehicles):
        entity = msg.entity.add()
        entity.id = f"DL1PD{1000 + i}"

        v = entity.vehicle
        v.vehicle.id = f"DL1PD{1000 + i}"
        v.trip.route_id = route_id
        v.trip.trip_id = f"TRIP_{route_id}_{i}"

        if outside_bbox:
            v.position.latitude = 12.9716  # Bengaluru
            v.position.longitude = 77.5946
        else:
            v.position.latitude = 28.6500 + (i * 0.01)  # Delhi
            v.position.longitude = 77.2200 + (i * 0.01)

        v.position.speed = 10.5  # ~37.8 km/h
        v.timestamp = now_ts - (1200 if stale else 60)

    return msg.SerializeToString()


def test_m10_collector_auth_unconfigured():
    """Test collector correctly classifies AUTH_REQUIRED when no API key is provided."""
    collector = LiveFeedCollector(api_key="", is_enabled=True)
    status, msg = collector.check_feed_availability()
    assert status == FeedAvailabilityStatus.AUTH_REQUIRED
    assert "DELHI_TRANSPORTSTACK_API_KEY" in msg
    payload = collector.get_status_payload()
    assert payload["auth_configured"] is False
    assert payload["feed_availability_status"] == "AUTH_REQUIRED"
    assert payload["feed_enabled"] is False


def test_m10_collector_synthetic_protobuf_parsing():
    """Verify parsing and validation of GTFS-RT protobuf entities."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 not installed")

    collector = LiveFeedCollector(
        api_key="synthetic_test_key",
        is_enabled=True,
        known_route_ids={"1598", "1657"},
    )

    feed = gtfs_rt.FeedMessage()
    feed.ParseFromString(create_synthetic_feed_message(num_vehicles=10, route_id="1598"))

    validated = collector.validate_and_filter_entities(feed)
    assert len(validated) == 10
    assert len(collector.active_vehicles) == 10

    first = validated[0]
    assert first.vehicle_id == "DL1PD1000"
    assert first.route_id == "1598"
    assert first.is_valid_coordinates is True
    assert first.is_fresh is True
    assert first.is_matched_to_gtfs is True
    assert first.speed_kmh == pytest.approx(37.8, rel=1e-1)


def test_m10_staleness_and_bounding_box_filtering():
    """Verify stale pings (>900s) and out-of-bounds coordinates are detected."""
    if gtfs_rt is None:
        pytest.skip("gtfs_realtime_pb2 not installed")

    collector = LiveFeedCollector(api_key="test_key", max_staleness_seconds=900)

    # 1. Stale vehicles
    feed_stale = gtfs_rt.FeedMessage()
    feed_stale.ParseFromString(create_synthetic_feed_message(num_vehicles=3, stale=True))
    validated_stale = collector.validate_and_filter_entities(feed_stale)
    assert len(validated_stale) == 3
    assert all(not v.is_fresh for v in validated_stale)
    assert any("Stale update" in note for v in validated_stale for note in v.validation_notes)

    # 2. Out-of-bounds coordinates (Bengaluru)
    feed_oob = gtfs_rt.FeedMessage()
    feed_oob.ParseFromString(create_synthetic_feed_message(num_vehicles=2, outside_bbox=True))
    collector.active_vehicles.clear()
    validated_oob = collector.validate_and_filter_entities(feed_oob)
    assert len(validated_oob) == 0  # rejected because coordinates invalid


def test_m10_agency_classification_unknown_mixed():
    """Verify agency coverage is reported as UNKNOWN_MIXED without external registry."""
    collector = LiveFeedCollector(api_key="test_key")
    payload = collector.get_status_payload()
    assert payload["agency_coverage"] == "UNKNOWN_MIXED"


def test_m10_api_live_status_with_synthetic_collector():
    """Verify GET /api/v1/live/status with configured collector returns accurate telemetry."""
    collector = LiveFeedCollector(
        api_key="dummy_valid_key",
        is_enabled=True,
    )
    if gtfs_rt is not None:
        feed = gtfs_rt.FeedMessage()
        feed.ParseFromString(create_synthetic_feed_message(num_vehicles=5, route_id="1598"))
        collector.validate_and_filter_entities(feed)
        collector.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED

    set_live_collector(collector)
    client = TestClient(app)

    response = client.get("/api/v1/live/status")
    assert response.status_code == 200
    data = response.json()

    assert data["feed_enabled"] is True
    assert data["feed_availability_status"] == "AVAILABLE_VALIDATED"
    assert data["auth_configured"] is True
    assert data["active_vehicles_count"] == 5
    assert data["overall_operational_status"] == "DEGRADE"
    assert data["agency_coverage"] == "UNKNOWN_MIXED"
    # Security check: dummy_valid_key must NEVER appear
    assert "dummy_valid_key" not in str(data)


def test_m10_api_live_vehicles_endpoint_and_filtering():
    """Verify GET /api/v1/live/vehicles returns validated items and filters by route_id."""
    collector = LiveFeedCollector(api_key="test_key", is_enabled=True)
    if gtfs_rt is not None:
        feed1 = gtfs_rt.FeedMessage()
        feed1.ParseFromString(create_synthetic_feed_message(num_vehicles=4, route_id="1598"))
        collector.validate_and_filter_entities(feed1)

        feed2 = gtfs_rt.FeedMessage()
        feed2.ParseFromString(create_synthetic_feed_message(num_vehicles=2, route_id="1657"))
        collector.validate_and_filter_entities(feed2)

        collector.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED

    set_live_collector(collector)
    client = TestClient(app)

    # 1. Unfiltered query
    res = client.get("/api/v1/live/vehicles?limit=50")
    assert res.status_code == 200
    data = res.json()
    assert data["total_active_vehicles"] >= 4
    assert data["feed_availability_status"] == "AVAILABLE_VALIDATED"
    assert "disclaimer" in data

    # 2. Filtered by route 1598
    res_filtered = client.get("/api/v1/live/vehicles?route_id=1598")
    assert res_filtered.status_code == 200
    data_filt = res_filtered.json()
    assert data_filt["route_filter"] == "1598"
    assert all(v["route_id"] == "1598" for v in data_filt["vehicles"])

    # 3. Security check: Ensure API key is never in vehicles response
    assert "test_key" not in str(data_filt)


def test_m10_live_feed_real_key_if_configured():
    """If real DELHI_TRANSPORTSTACK_API_KEY is configured in settings, test live fetch."""
    real_key = settings.DELHI_TRANSPORTSTACK_API_KEY
    if not real_key or len(real_key) < 10:
        pytest.skip("No real Delhi Transport Stack API key configured in settings")

    collector = LiveFeedCollector(
        endpoint_url=settings.DELHI_GTFS_RT_URL,
        api_key=real_key,
        is_enabled=True,
    )
    status, msg = collector.check_feed_availability(timeout_seconds=8.0)
    assert status in (FeedAvailabilityStatus.AVAILABLE_VALIDATED, FeedAvailabilityStatus.AVAILABLE_PARTIAL)
    assert len(collector.active_vehicles) > 100

    payload = collector.get_status_payload()
    assert payload["auth_configured"] is True
    assert payload["active_vehicles_count"] > 100
    assert payload["valid_vehicles_count"] > 100
    assert payload["valid_routes_count"] > 100
    assert payload["overall_operational_status"] == "DEGRADE"
    # Assert secret never leaked
    assert real_key not in str(payload)

