"""Comprehensive tests for Task A (Live Vehicle Position Updates) and Task B (Live Journey Bus Identification).

PRD v3.0 & Milestone 12 Verification Suite:
1. 20s cache expiry and refresh behavior.
2. Shared cache across multiple calls and thread safety.
3. Source coordinate updates on new protobuf decode without synthetic GPS.
4. Stale marking on failed fetch while preserving last known positions.
5. Minor clock skew tolerance.
6. Static GTFS trip sequence verification (stop_sequence(board) < stop_sequence(alight)).
7. Approaching bus identification.
8. Near boarding stop bus identification (<= 400m).
9. Passed-stop vehicle rejection (never recommended as approaching).
10. Route matches but direction unverified fallback ('Route matches — direction unverified.').
11. Unidentified bus fallback ('Live bus not identified — follow the scheduled route...').
12. Direct and transfer journey bus identification integration.
13. Live REST endpoint GET /api/v1/live/match-bus.
"""

from concurrent.futures import ThreadPoolExecutor
import time
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.core.journey_planner import JourneyPlanner
from backend.app.services.planner_service import PlannerService
from backend.app.schemas.journey import JourneyPlanRequest
from backend.realtime.gtfs_rt import (
    DELHI_BBOX_LAT_MIN,
    DELHI_BBOX_LON_MIN,
    FeedAvailabilityStatus,
    LiveFeedCollector,
    ValidatedVehiclePosition,
)
from backend.realtime.matcher import (
    FALLBACK_ROUTE_MATCH_UNVERIFIED,
    FALLBACK_UNIDENTIFIED,
    JourneyBusMatcher,
)

# Test database
DB_PATH = "/tmp/delhi_dlm1.db"


class TestLiveFeedCollector20sCache:
    """Task A: 20-second cache, thread-safety, coordinate update & stale marking tests."""

    def test_20s_cache_expiry_and_refresh(self):
        """Verify that requests within 20s reuse the cached snapshot and fetch only after 20s expires."""
        collector = LiveFeedCollector(api_key="test_key_12345", is_enabled=True)

        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b""  # Empty body
            mock_get.return_value = mock_resp

            # 1. First fetch at t=0
            status, _ = collector.refresh_if_expired(force=True)
            assert mock_get.call_count == 1

            # 2. Add an active vehicle to simulate populated cache
            collector.active_vehicles["TEST_01"] = ValidatedVehiclePosition(
                vehicle_id="TEST_01",
                route_id="1598",
                trip_id="1598_01",
                latitude=28.70,
                longitude=77.15,
                bearing=180.0,
                speed_kmh=30.0,
                timestamp_utc=int(time.time()),
                is_valid_coordinates=True,
                is_fresh=True,
                is_matched_to_gtfs=True,
                validation_notes=[],
            )

            # 3. Call within 20 seconds (e.g. 5s later) -> must NOT trigger upstream fetch
            collector.last_fetch_mono = time.monotonic()  # Just fetched
            status2, _ = collector.refresh_if_expired(force=False)
            assert mock_get.call_count == 1  # Unchanged!

            # 4. Simulate passage of 21 seconds -> MUST trigger upstream fetch
            collector.last_fetch_mono = time.monotonic() - 21.0
            status3, _ = collector.refresh_if_expired(force=False)
            assert mock_get.call_count == 2  # New fetch occurred!

    def test_shared_cache_thread_safety(self):
        """Verify multiple simultaneous client requests share the single cache without overlapping fetches."""
        collector = LiveFeedCollector(api_key="test_key_12345", is_enabled=True)

        with patch("requests.get") as mock_get:
            def slow_fetch(*args, **kwargs):
                time.sleep(0.05)  # Simulate network latency
                resp = MagicMock()
                resp.status_code = 200
                resp.content = b""
                return resp

            mock_get.side_effect = slow_fetch

            # 10 threads call refresh_if_expired at the exact same instant
            collector.last_fetch_mono = 0.0  # Expired
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(collector.refresh_if_expired, False) for _ in range(10)]
                results = [f.result() for f in futures]

            # Even with 10 concurrent clients, thread-safety lock ensures only 1 upstream request is made
            assert mock_get.call_count == 1
            for res_status, _ in results:
                assert res_status == FeedAvailabilityStatus.AVAILABLE_PARTIAL

    def test_source_coordinates_updated_on_decode(self):
        """Verify vehicle coordinates update strictly from decoded provider messages without interpolating."""
        collector = LiveFeedCollector(api_key="test_key_12345", is_enabled=True)

        # First position
        pos1 = ValidatedVehiclePosition(
            vehicle_id="DL1PD1234",
            route_id="1598",
            trip_id="1598_01",
            latitude=28.7000,
            longitude=77.1500,
            bearing=90.0,
            speed_kmh=25.0,
            timestamp_utc=1700000000,
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )
        collector._update_active_vehicles([pos1])
        assert collector.active_vehicles["DL1PD1234"].latitude == 28.7000

        # Second position with updated real GPS telemetry
        pos2 = ValidatedVehiclePosition(
            vehicle_id="DL1PD1234",
            route_id="1598",
            trip_id="1598_01",
            latitude=28.7050,
            longitude=77.1550,
            bearing=95.0,
            speed_kmh=35.0,
            timestamp_utc=1700000030,
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )
        collector._update_active_vehicles([pos2])
        updated = collector.active_vehicles["DL1PD1234"]
        assert updated.latitude == 28.7050
        assert updated.longitude == 77.1550
        assert updated.timestamp_utc == 1700000030

    def test_stale_marking_on_failed_fetch(self):
        """Verify on fetch failure, last known positions are preserved and marked stale."""
        collector = LiveFeedCollector(api_key="test_key_12345", is_enabled=True)

        # Seed active vehicle
        collector.active_vehicles["DL1PD9999"] = ValidatedVehiclePosition(
            vehicle_id="DL1PD9999",
            route_id="1598",
            trip_id="1598_01",
            latitude=28.7000,
            longitude=77.1500,
            bearing=90.0,
            speed_kmh=25.0,
            timestamp_utc=int(time.time()),
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )

        with patch("requests.get") as mock_get:
            # Simulate upstream 500 error
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_get.return_value = mock_resp

            collector.last_fetch_mono = 0.0  # Expired
            status, msg = collector.refresh_if_expired(force=True)

            assert status == FeedAvailabilityStatus.UNAVAILABLE
            # Last known position preserved!
            assert "DL1PD9999" in collector.active_vehicles
            # Marked stale!
            assert collector.active_vehicles["DL1PD9999"].is_fresh is False

    def test_clock_skew_tolerance(self):
        """Verify minor forward clock drift (up to 120s) is accepted and marked fresh."""
        collector = LiveFeedCollector(api_key="test_key_12345")
        now_ts = 1700000000

        # Create mock entity with timestamp 20s in the future
        mock_entity = MagicMock()
        mock_entity.HasField.side_effect = lambda f: f == "vehicle"
        mock_entity.id = "DRIFT_BUS"
        mock_entity.vehicle.HasField.side_effect = lambda f: f in ("position", "timestamp", "trip")
        mock_entity.vehicle.position.HasField.side_effect = lambda f: f in ("latitude", "longitude")
        mock_entity.vehicle.position.latitude = 28.7000
        mock_entity.vehicle.position.longitude = 77.1500
        mock_entity.vehicle.timestamp = now_ts + 20  # 20s ahead
        mock_entity.vehicle.trip.HasField.side_effect = lambda f: f == "route_id"
        mock_entity.vehicle.trip.route_id = "1598"

        mock_feed = MagicMock()
        mock_feed.entity = [mock_entity]

        validated = collector.validate_and_filter_entities(mock_feed, reference_time_utc=now_ts)
        assert len(validated) == 1
        assert validated[0].is_fresh is True
        assert any("clock skew" in n for n in validated[0].validation_notes)


class TestJourneyBusMatcherTaskB:
    """Task B: GTFS trip sequence verification, direction guards, and bus boarding guidance."""

    @pytest.fixture
    def matcher(self):
        return JourneyBusMatcher(db_path=DB_PATH)

    def test_approaching_bus_identification(self, matcher):
        """Verify approaching candidate bus is identified with exact stops away and distance."""
        # Route 1598: Board at stop 295 (seq 45), alight at stop 1026 (seq 55)
        # Vehicle positioned near stop seq 42 (~28.74, ~77.15)
        approaching_veh = ValidatedVehiclePosition(
            vehicle_id="DL1PD5555",
            route_id="1598",
            trip_id="1598_11_55_3761",
            latitude=28.7361,
            longitude=77.1543,
            bearing=180.0,
            speed_kmh=35.0,
            timestamp_utc=int(time.time()),
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )

        res = matcher.match_bus_for_leg(
            route_id="1598",
            board_stop_id="295",
            alight_stop_id="1026",
            active_vehicles=[approaching_veh],
        )

        assert res["identification_status"] == "IDENTIFIED_APPROACHING"
        assert res["vehicle_id"] == "DL1PD5555"
        assert res["route_id"] == "1598"
        assert res["trip_headsign"] == "Singhu Border GT Road"
        assert res["progress_status"] == "APPROACHING"
        assert res["stops_away"] is not None and res["stops_away"] > 0
        assert res["distance_to_board_m"] is not None and res["distance_to_board_m"] > 400
        assert "approaching" in res["guidance_message"].lower()
        assert "DL1PD5555" in res["guidance_message"]
        assert res["is_candidate_only"] is True

    def test_near_boarding_stop_identification(self, matcher):
        """Verify bus within 400m of boarding stop is classified as IDENTIFIED_NEAR."""
        # Stop 295 is at (28.777757, 77.142048). Place bus ~50m away.
        near_veh = ValidatedVehiclePosition(
            vehicle_id="DL1PD7777",
            route_id="1598",
            trip_id="1598_11_55_3761",
            latitude=28.7780,
            longitude=77.1422,
            bearing=180.0,
            speed_kmh=12.0,
            timestamp_utc=int(time.time()),
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )

        res = matcher.match_bus_for_leg(
            route_id="1598",
            board_stop_id="295",
            alight_stop_id="1026",
            active_vehicles=[near_veh],
        )

        assert res["identification_status"] == "IDENTIFIED_NEAR"
        assert res["vehicle_id"] == "DL1PD7777"
        assert res["progress_status"] == "NEAR_BOARDING_STOP"
        assert res["stops_away"] == 0
        assert res["distance_to_board_m"] <= 400.0
        assert "currently near boarding stop" in res["guidance_message"].lower()

    def test_passed_stop_vehicle_strictly_rejected_as_approaching(self, matcher):
        """Verify vehicles that have passed the boarding stop are NEVER recommended as approaching."""
        # Board at stop 7572 (seq 0 - Old Delhi Railway Station), alight at stop 114 (seq 5)
        # Vehicle is at stop seq 40 (far past stop 0)
        passed_veh = ValidatedVehiclePosition(
            vehicle_id="DL1PD9999",
            route_id="1598",
            trip_id="1598_11_55_3761",
            latitude=28.7361,
            longitude=77.1543,
            bearing=180.0,
            speed_kmh=45.0,
            timestamp_utc=int(time.time()),
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )

        res = matcher.match_bus_for_leg(
            route_id="1598",
            board_stop_id="7572",
            alight_stop_id="114",
            active_vehicles=[passed_veh],
        )

        assert res["identification_status"] == "PASSED_STOP"
        # Must NOT recommend the passed vehicle!
        assert res["vehicle_id"] is None
        assert res["progress_status"] == "PASSED"
        assert res["guidance_message"] == FALLBACK_UNIDENTIFIED

    def test_route_matches_direction_unverified_fallback(self, matcher):
        """Verify when route matches but direction cannot be verified, exact fallback is returned."""
        # Query stops in reverse sequence or off-corridor
        off_corridor_veh = ValidatedVehiclePosition(
            vehicle_id="DL1PD1111",
            route_id="1598",
            trip_id="1598_UNKNOWN",
            latitude=28.5000,  # South Delhi (far from Route 1598 North Delhi corridor)
            longitude=77.2000,
            bearing=None,
            speed_kmh=30.0,
            timestamp_utc=int(time.time()),
            is_valid_coordinates=True,
            is_fresh=True,
            is_matched_to_gtfs=True,
            validation_notes=[],
        )

        res = matcher.match_bus_for_leg(
            route_id="1598",
            board_stop_id="295",
            alight_stop_id="1026",
            active_vehicles=[off_corridor_veh],
        )

        assert res["identification_status"] == "ROUTE_MATCH_UNVERIFIED"
        assert res["guidance_message"] == FALLBACK_ROUTE_MATCH_UNVERIFIED
        assert res["vehicle_id"] is None

    def test_unidentified_fallback_empty_vehicles(self, matcher):
        """Verify fallback when no active vehicles exist on route."""
        res = matcher.match_bus_for_leg(
            route_id="1598",
            board_stop_id="295",
            alight_stop_id="1026",
            active_vehicles=[],
        )

        assert res["identification_status"] == "UNIDENTIFIED"
        assert res["guidance_message"] == FALLBACK_UNIDENTIFIED
        assert res["vehicle_id"] is None


class TestJourneyPlanIntegration:
    """Integration test verifying full planner output attaches live_bus to transit legs."""

    @pytest.fixture
    def client(self):
        app = create_app()
        return TestClient(app)

    def test_plan_journey_attaches_live_bus(self, client):
        """Verify planned transit legs contain valid LiveBusCandidateSchema with required fields."""
        res = client.post(
            "/api/v1/journeys/plan",
            json={
                "origin_lat": 28.6668,
                "origin_lon": 77.2280,
                "dest_lat": 28.7155,
                "dest_lon": 77.1788,
                "departure_date": "2026-10-01",
                "departure_time": "08:00:00",
                "allow_assumed_recurring": True,
                "max_transfers": 2,
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["journeys_count"] >= 1

        journey = data["journeys"][0]
        transit_legs = [l for l in journey["legs"] if l["leg_type"] == "TRANSIT"]
        assert len(transit_legs) >= 1

        for tleg in transit_legs:
            assert "live_bus" in tleg
            live_bus = tleg["live_bus"]
            assert live_bus is not None
            assert "identification_status" in live_bus
            assert "guidance_message" in live_bus
            assert live_bus["is_candidate_only"] is True
            assert live_bus["identification_status"] in (
                "IDENTIFIED_APPROACHING",
                "IDENTIFIED_NEAR",
                "ROUTE_MATCH_UNVERIFIED",
                "PASSED_STOP",
                "UNIDENTIFIED",
            )

    def test_api_match_bus_endpoint(self, client):
        """Verify GET /api/v1/live/match-bus REST endpoint directly."""
        res = client.get(
            "/api/v1/live/match-bus",
            params={
                "route_id": "1598",
                "board_stop_id": "295",
                "alight_stop_id": "1026",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "identification_status" in data
        assert "guidance_message" in data
        assert data["route_id"] == "1598"
