"""Unit and integration tests for Priority Live Bus Tracking and Route-Constrained Dead Reckoning.

Covers all 10 required verification scenarios:
1. Bus on correct trip, approaching boarding stop.
2. Bus on same route, opposite direction (excluded).
3. Bus that has already passed boarding stop (excluded).
4. Bus whose stop sequence does not reach destination (excluded).
5. Bus with unknown direction (excluded).
6. Bus with missing speed or bearing (handled safely).
7. Bus receiving no new GPS update for 15s (dead reckoning advances along route shape, marks DEAD_RECKONED, increments uncertainty).
8. New GPS update correcting dead-reckoned position (snaps to GPS, resets uncertainty).
9. Switching source/destination while requests in flight.
10. No suitable buses available (shows exact fallback message with clean list).
"""

import os
import time
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.realtime.gtfs_rt import LiveFeedCollector, FeedAvailabilityStatus, haversine_distance_m
from backend.realtime.matcher import JourneyBusMatcher, ValidatedVehiclePosition, project_point_onto_shape
from backend.app.api.v1.live import get_live_collector

DB_PATH = os.environ.get("DB_PATH", "/tmp/delhi_dlm1.db")
client = TestClient(app)


@pytest.fixture
def matcher():
    return JourneyBusMatcher(db_path=DB_PATH)


@pytest.fixture
def base_collector():
    collector = LiveFeedCollector(
        endpoint_url="http://mock-feed.local/gtfs-rt",
        poll_interval_seconds=15,
        max_staleness_seconds=900,
        is_enabled=True,
    )
    collector.known_route_ids = {"1598", "999"}
    collector.last_fetch_mono = time.monotonic()
    collector.availability_status = FeedAvailabilityStatus.AVAILABLE_VALIDATED
    return collector


def test_scenario_1_bus_on_correct_trip_approaching(matcher):
    """Scenario 1: Bus on correct trip approaching boarding stop is verified and marked GPS."""
    now = int(time.time())
    # Route 1598 from Stop 284 (Adarsh Nagar, seq 34) to Stop 5146 (Mukarba Chowk, seq 39)
    # Vehicle positioned upstream at New Sabzi Mandi (seq 33, ~28.712, 77.175), fresh GPS ping 5s ago
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC1001",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now)
    assert len(suitable) == 1
    bus = suitable[0]
    assert bus["vehicle_id"] == "DL1PC1001"
    assert bus["is_verified_suitable"] is True
    assert bus["is_verified_destination"] is True
    assert bus["position_source"] == "GPS"
    assert bus["is_dead_reckoned"] is False
    assert bus["uncertainty_meters"] == 15.0
    assert bus["progress_status"] in ("APPROACHING", "NEAR_BOARDING_STOP")


def test_scenario_2_opposite_direction_excluded(matcher):
    """Scenario 2: Bus on same route travelling in opposite direction is excluded."""
    now = int(time.time())
    # Route 1598, forward direction is ~325 deg (towards Mukarba Chowk).
    # Opposite vehicle has bearing 145 deg (heading towards Old Delhi)
    v_opposite = ValidatedVehiclePosition(
        vehicle_id="DL1PC1002",
        route_id="1598",
        trip_id=None,
        latitude=28.7120,
        longitude=77.1750,
        bearing=145.0,  # Opposite direction (> 120 deg difference)
        speed_kmh=30.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_opposite], now_ts=now)
    assert len(suitable) == 0


def test_scenario_3_passed_boarding_stop_excluded(matcher):
    """Scenario 3: Bus that has already passed the boarding stop is excluded."""
    now = int(time.time())
    # Stop 284 is at 28.7160. Vehicle is downstream at 28.7500 (passed boarding stop and alight stop)
    v_passed = ValidatedVehiclePosition(
        vehicle_id="DL1PC1003",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7500,
        longitude=77.1400,
        bearing=325.0,
        speed_kmh=35.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_passed], now_ts=now)
    assert len(suitable) == 0


def test_scenario_4_unreached_destination_excluded(matcher):
    """Scenario 4: Bus whose trip stop sequence does not reach destination is excluded."""
    now = int(time.time())
    # Query with non-existent or reversed stop sequence (e.g. from Mukarba Chowk to Adarsh Nagar on 1598)
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC1004",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    # 5146 (seq 39) -> 284 (seq 34) has board_seq > alight_seq
    suitable = matcher.get_suitable_buses_for_leg("1598", "5146", "284", [v], now_ts=now)
    assert len(suitable) == 0


def test_scenario_5_unknown_direction_excluded(matcher):
    """Scenario 5: Bus with no trip_id and unknown/unaligned bearing is excluded."""
    now = int(time.time())
    v_unknown = ValidatedVehiclePosition(
        vehicle_id="DL1PC1005",
        route_id="1598",
        trip_id=None,  # No trip_id
        latitude=28.7120,
        longitude=77.1750,
        bearing=None,  # No bearing
        speed_kmh=30.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_unknown], now_ts=now)
    assert len(suitable) == 0


def test_scenario_6_missing_speed_or_bearing_handled_safely(matcher):
    """Scenario 6: Missing speed or bearing is handled safely without exception."""
    now = int(time.time())
    # Vehicle has verified trip_id, but speed is None and bearing is None
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC1006",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=None,
        speed_kmh=None,  # Missing speed
        timestamp_utc=now - 45,  # Stale GPS > 15s
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now)
    assert len(suitable) == 1
    bus = suitable[0]
    # Since speed is missing, it should hold at last known GPS without crash
    assert bus["position_source"] == "DEAD_RECKONED"
    assert bus["is_dead_reckoned"] is True
    assert bus["latitude"] == 28.7120
    assert bus["longitude"] == 77.1750


def test_scenario_7_dead_reckoning_advances_along_route_shape(matcher):
    """Scenario 7: When GPS update is > 15s old, dead reckoning extrapolates along GTFS corridor."""
    now = int(time.time())
    start_lat = 28.7120
    start_lon = 77.1750

    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC1007",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=start_lat,
        longitude=start_lon,
        bearing=325.0,
        speed_kmh=36.0,  # 10 m/s
        timestamp_utc=now - 35,  # 35s since last GPS ping
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now)
    assert len(suitable) == 1
    bus = suitable[0]
    assert bus["position_source"] == "DEAD_RECKONED"
    assert bus["is_dead_reckoned"] is True
    assert bus["last_gps_latitude"] == start_lat
    assert bus["last_gps_longitude"] == start_lon
    assert bus["last_gps_timestamp"] == now - 35
    assert bus["prediction_age_seconds"] == 35

    # Coordinates have advanced along corridor towards destination
    assert (bus["latitude"], bus["longitude"]) != (start_lat, start_lon)
    # Uncertainty has increased beyond 15m
    assert bus["uncertainty_meters"] > 15.0


def test_scenario_8_new_gps_update_resets_dead_reckoning(matcher):
    """Scenario 8: Fresh GPS update snaps position and resets uncertainty to 15m."""
    now = int(time.time())
    v_fresh = ValidatedVehiclePosition(
        vehicle_id="DL1PC1008",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7140,
        longitude=77.1730,
        bearing=325.0,
        speed_kmh=25.0,
        timestamp_utc=now - 8,  # Only 8s old (<= 15s)
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_fresh], now_ts=now)
    assert len(suitable) == 1
    bus = suitable[0]
    assert bus["position_source"] == "GPS"
    assert bus["is_dead_reckoned"] is False
    assert bus["latitude"] == 28.7140
    assert bus["longitude"] == 77.1730
    assert bus["uncertainty_meters"] == 15.0


def test_scenario_9_request_switching_in_flight(base_collector):
    """Scenario 9: Switching route/stops returns only suitable buses for the active query."""
    now = int(time.time())
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC1009",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    base_collector.active_vehicles = {"DL1PC1009": v}
    app.dependency_overrides[get_live_collector] = lambda: base_collector

    try:
        # Leg 1: Route 1598 serves Stop 284 -> 5146
        res1 = client.get("/api/v1/live/suitable-vehicles?route_id=1598&board_stop_id=284&alight_stop_id=5146")
        assert res1.status_code == 200
        assert res1.json()["suitable_count"] == 1

        # Leg 2: Unrelated route 999
        res2 = client.get("/api/v1/live/suitable-vehicles?route_id=999&board_stop_id=284&alight_stop_id=5146")
        assert res2.status_code == 200
        assert res2.json()["suitable_count"] == 0
    finally:
        app.dependency_overrides.clear()


def test_scenario_10_no_suitable_buses_fallback_message(base_collector):
    """Scenario 10: When no suitable bus exists, return exact required fallback message."""
    base_collector.active_vehicles = {}
    app.dependency_overrides[get_live_collector] = lambda: base_collector

    try:
        res = client.get("/api/v1/live/suitable-vehicles?route_id=1598&board_stop_id=284&alight_stop_id=5146")
        assert res.status_code == 200
        data = res.json()
        assert data["suitable_count"] == 0
        assert data["vehicles"] == []
        assert data["fallback_message"] == "No verified live bus is currently available for this journey."
        assert data["poll_interval_seconds"] == 15
    finally:
        app.dependency_overrides.clear()


def test_scenario_11_dispatch_trip_id_with_missing_bearing_qualifies(matcher):
    """Scenario 11: Real-world Delhi operational dispatch trip ID (e.g. 1598_17_33_1559)
    with missing bearing qualifies as suitable when approaching upstream along corridor.
    """
    now = int(time.time())
    # Upstream at New Sabzi Mandi (seq 33, ~28.712, 77.175), board stop is 284 (Adarsh Nagar, seq 34), alight is 5146 (Mukarba Chowk, seq 39)
    v_dispatch = ValidatedVehiclePosition(
        vehicle_id="DL1PD5191",
        route_id="1598",
        trip_id="1598_17_33_1559",  # Real-time operational dispatch format
        latitude=28.7120,
        longitude=77.1750,
        bearing=None,  # Missing bearing (standard in Delhi GTFS-RT feed)
        speed_kmh=42.0,
        timestamp_utc=now - 8,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_dispatch], now_ts=now)
    assert len(suitable) == 1
    bus = suitable[0]
    assert bus["vehicle_id"] == "DL1PD5191"
    assert bus["trip_id"] == "1598_17_33_1559"
    assert bus["is_verified_suitable"] is True
    assert bus["is_verified_destination"] is True
    assert bus["progress_status"] in ("APPROACHING", "NEAR_BOARDING_STOP")


def test_scenario_12_approaching_bus_beyond_400m_qualifies(matcher):
    """Scenario 12: Bus approaching from 3.5 km away qualifies as APPROACHING within MAX_APPROACH_DISTANCE_M."""
    now = int(time.time())
    # INS Hostel (seq 15, ~3.0 km upstream from Stop 284)
    v_approaching = ValidatedVehiclePosition(
        vehicle_id="DL1PD8661",
        route_id="1598",
        trip_id="1598_17_39_4374",
        latitude=28.6961,
        longitude=77.2117,
        bearing=None,
        speed_kmh=35.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_approaching], now_ts=now)
    assert len(suitable) == 1
    bus = suitable[0]
    assert bus["vehicle_id"] == "DL1PD8661"
    assert bus["progress_status"] == "APPROACHING"
    assert bus["distance_to_board_m"] > 400.0
    assert bus["distance_to_board_m"] <= 7000.0


def test_scenario_13_incompatible_route_trip_id_excluded(matcher):
    """Scenario 13: Bus with trip_id from an incompatible route is excluded."""
    now = int(time.time())
    v_incompat = ValidatedVehiclePosition(
        vehicle_id="DL1PC9999",
        route_id="1598",
        trip_id="883_16_20_1111",  # Incompatible route dispatch
        latitude=28.7120,
        longitude=77.1750,
        bearing=None,
        speed_kmh=30.0,
        timestamp_utc=now - 5,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    suitable = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_incompat], now_ts=now)
    assert len(suitable) == 0


def test_15s_bus_movement_along_gtfs_route_shape(matcher):
    """Test 1: Verify vehicle coordinates advance along route shape every 15s."""
    t0 = 1700000000
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC2001",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=36.0,  # 10 m/s
        timestamp_utc=t0,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    history = []
    # Test sequence: T0, T+15, T+30, T+45, T+60
    for step in range(5):
        now_ts = t0 + step * 15
        res = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now_ts)
        assert len(res) == 1
        history.append(res[0])

    # 1. Coordinates must physically change on each 15s step
    coords = [(h["latitude"], h["longitude"]) for h in history]
    for i in range(len(coords) - 1):
        assert coords[i] != coords[i + 1], f"Step {i} and {i+1} have identical coordinates {coords[i]}"

    # 2. Route progress must monotonically increase along the shape
    progresses = [h["route_progress_meters"] for h in history]
    for i in range(len(progresses) - 1):
        assert progresses[i] < progresses[i + 1], f"Progress not increasing: {progresses}"

    # 3. Provenance and status checks
    assert history[0]["position_source"] == "GPS"
    assert history[0]["is_dead_reckoned"] is False
    assert history[1]["position_source"] == "DEAD_RECKONED"
    assert history[1]["is_dead_reckoned"] is True
    assert history[1]["correction_status"] == "DEAD_RECKONING_ACTIVE"


def test_bus_strictly_adheres_to_shape_curvature_not_straight_line(matcher):
    """Test 2: Predicted coordinates lie along GTFS shape polyline curvature."""
    t0 = 1700000000
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC2002",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=36.0,
        timestamp_utc=t0,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    # Predict 30s ahead
    res = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=t0 + 30)
    assert len(res) == 1
    bus = res[0]
    pred_lat, pred_lon = bus["latitude"], bus["longitude"]

    # Verify that the predicted position is strictly on the shape corridor
    shape_coords = matcher._shape_cache["1598_FULL_05_50"]
    cum_dists = matcher._shape_cum_dist_cache["1598_FULL_05_50"]
    proj_progress = project_point_onto_shape(shape_coords, cum_dists, pred_lat, pred_lon)
    assert abs(proj_progress - bus["route_progress_meters"]) < 1.0


def test_stationary_bus_holds_position_without_drift(matcher):
    """Test 3: Stationary bus (speed < 1 km/h or None) holds coordinates at genuine GPS anchor."""
    t0 = 1700000000
    v_stat = ValidatedVehiclePosition(
        vehicle_id="DL1PC2003",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=0.0,  # Zero speed
        timestamp_utc=t0,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    for step in range(1, 4):
        now_ts = t0 + step * 15
        res = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_stat], now_ts=now_ts)
        assert len(res) == 1
        bus = res[0]
        assert bus["latitude"] == 28.7120
        assert bus["longitude"] == 77.1750
        assert bus["correction_status"] == "STATIONARY_HOLD"
        assert bus["position_source"] == "DEAD_RECKONED"
        assert bus["is_dead_reckoned"] is True


def test_genuine_gps_recalibration_resets_anchor_and_calculates_error(matcher):
    """Test 4: Genuine GPS recalibration calculates drift error in meters and resets anchor."""
    t0 = 1700000000
    # Initial GPS at T0
    v_t0 = ValidatedVehiclePosition(
        vehicle_id="DL1PC2004",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=36.0,  # 10 m/s
        timestamp_utc=t0,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    # Step 1: Dead reckon at T+45s
    res_pred = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_t0], now_ts=t0 + 45)
    assert len(res_pred) == 1

    # Step 2: New genuine GPS arrives at T+50s at actual position (~80m away from dead reckoned point)
    v_t50 = ValidatedVehiclePosition(
        vehicle_id="DL1PC2004",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7160,
        longitude=77.1710,
        bearing=325.0,
        speed_kmh=32.0,
        timestamp_utc=t0 + 50,  # New GPS timestamp
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    res_calibrated = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_t50], now_ts=t0 + 50)
    assert len(res_calibrated) == 1
    cal = res_calibrated[0]

    # Verify recalibration metrics
    assert cal["correction_status"] == "CALIBRATED_ERROR_CORRECTED"
    assert cal["last_prediction_error_meters"] is not None
    assert cal["last_prediction_error_meters"] > 0.0
    assert cal["last_correction_distance_meters"] is not None
    # Position snaps to genuine GPS
    assert cal["latitude"] == 28.7160
    assert cal["longitude"] == 77.1710
    assert cal["last_gps_latitude"] == 28.7160
    assert cal["last_gps_longitude"] == 77.1710
    assert cal["last_gps_timestamp"] == t0 + 50


def test_subsequent_predictions_resume_from_newly_calibrated_anchor(matcher):
    """Test 5: Subsequent dead reckoning resumes from newly calibrated genuine GPS anchor."""
    t0 = 1700000000
    v_t0 = ValidatedVehiclePosition(
        vehicle_id="DL1PC2005",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=36.0,
        timestamp_utc=t0,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_t0], now_ts=t0 + 45)

    # GPS calibration at T+50
    new_gps_lat = 28.7160
    new_gps_lon = 77.1710
    v_t50 = ValidatedVehiclePosition(
        vehicle_id="DL1PC2005",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=new_gps_lat,
        longitude=new_gps_lon,
        bearing=325.0,
        speed_kmh=36.0,
        timestamp_utc=t0 + 50,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_t50], now_ts=t0 + 50)

    # Next 15s dead reckoning at T+65 (15s after T+50)
    res_t65 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_t50], now_ts=t0 + 65)
    assert len(res_t65) == 1
    b65 = res_t65[0]

    # Baseline anchor is strictly the calibrated GPS
    assert b65["last_gps_latitude"] == new_gps_lat
    assert b65["last_gps_longitude"] == new_gps_lon
    assert b65["last_gps_timestamp"] == t0 + 50
    assert b65["prediction_age_seconds"] == 15
    # Position has advanced forward from new GPS anchor
    assert (b65["latitude"], b65["longitude"]) != (new_gps_lat, new_gps_lon)
    assert b65["route_progress_meters"] > matcher._tracking_state["DL1PC2005"]["anchor_route_progress_m"]


# ==============================================================================
# SECOND AUDIT TEST CASES (A THROUGH G)
# ==============================================================================

def test_audit_case_a_route_with_loop_bounded_projection():
    """Test Case A: Loop GTFS shape where bounded window prevents jumping across the loop."""
    from backend.realtime.matcher import project_point_onto_shape_bounded
    # Shape with a loop:
    # Segment 1: (28.700, 77.100) -> (28.710, 77.100) (~1111m)
    # Loop: (28.710, 77.100) -> (28.712, 77.105) -> (28.708, 77.105) -> (28.705, 77.1001) (~2500m)
    # Segment 2 continues: (28.705, 77.1001) -> (28.720, 77.1001) (~4000m)
    coords = [
        (28.700, 77.100),
        (28.710, 77.100),
        (28.712, 77.105),
        (28.708, 77.105),
        (28.705, 77.1001),
        (28.720, 77.1001),
    ]
    cum_dists = [0.0] * len(coords)
    for i in range(1, len(coords)):
        cum_dists[i] = cum_dists[i - 1] + haversine_distance_m(
            coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]
        )

    # Point at (28.705, 77.10005) is physically close to Segment 1 (~555m progress)
    # AND to Segment 2 (~2500m progress after the loop).
    test_lat, test_lon = 28.705, 77.10005

    # 1. Without bounds (global nearest), it might snap to Segment 1
    unbounded_prog, _ = project_point_onto_shape_bounded(coords, cum_dists, test_lat, test_lon)
    assert unbounded_prog < 1000.0  # Snaps to early segment

    # 2. With bounded window around progress 2400m, it is constrained to the post-loop segment
    bounded_prog, _ = project_point_onto_shape_bounded(
        coords, cum_dists, test_lat, test_lon, min_progress_m=2200.0, max_progress_m=3000.0
    )
    assert 2200.0 <= bounded_prog <= 3000.0
    # It does not jump back to the earlier segment (<1000m)!


def test_audit_case_b_nearby_parallel_shape_sections():
    """Test Case B: Two nearby parallel shape sections where bounded window prevents lane jumping."""
    from backend.realtime.matcher import project_point_onto_shape_bounded
    # Northbound lane: progress 0m to 1000m
    # Southbound return lane: progress 1500m to 2500m (only 15m away eastward)
    coords = [
        (28.700, 77.100),
        (28.709, 77.100),
        (28.710, 77.105),  # hairpin turn
        (28.709, 77.10015), # 15m east of northbound lane
        (28.700, 77.10015),
    ]
    cum_dists = [0.0] * len(coords)
    for i in range(1, len(coords)):
        cum_dists[i] = cum_dists[i - 1] + haversine_distance_m(
            coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1]
        )

    # Vehicle is on northbound lane, previously at progress 400m.
    # GPS jitter puts coordinates slightly closer to the southbound return lane
    jitter_lat, jitter_lon = 28.704, 77.10010

    # Search window bounded around 400m (e.g. 350m to 550m)
    prog, _ = project_point_onto_shape_bounded(
        coords, cum_dists, jitter_lat, jitter_lon, min_progress_m=350.0, max_progress_m=550.0
    )
    assert 350.0 <= prog <= 550.0
    # Did not jump to the southbound lane (>1500m)
    assert prog < 1000.0


def test_audit_case_c_gps_point_closer_to_earlier_shape_section(matcher):
    """Test Case C: GPS point closer to earlier shape section cannot cause backward progress."""
    now = 1700000000
    v1 = ValidatedVehiclePosition(
        vehicle_id="DL1PC3001",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res1 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v1], now_ts=now)
    assert len(res1) == 1
    prog1 = res1[0]["route_progress_meters"]

    # At T+10, GPS coordinates have a slight backwards jitter (e.g. 20m south)
    v2 = ValidatedVehiclePosition(
        vehicle_id="DL1PC3001",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7118,  # Slightly further south
        longitude=77.1751,
        bearing=325.0,
        speed_kmh=25.0,
        timestamp_utc=now + 10,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res2 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v2], now_ts=now + 10)
    assert len(res2) == 1
    prog2 = res2[0]["route_progress_meters"]

    # Monotonicity guaranteed: progress must not decrease!
    assert prog2 >= prog1


def test_audit_case_d_out_of_order_gps_rejected(matcher):
    """Test Case D: Out-of-order GPS observation is rejected and does not overwrite newer anchor."""
    now = 1700000000
    v_new = ValidatedVehiclePosition(
        vehicle_id="DL1PC3002",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now,  # Newer timestamp
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_new], now_ts=now)
    assert matcher._tracking_state["DL1PC3002"]["anchor_gps_ts"] == now

    # Delayed out-of-order packet arrives with timestamp (now - 30)
    v_old = ValidatedVehiclePosition(
        vehicle_id="DL1PC3002",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7100,
        longitude=77.1770,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now - 30,  # Older timestamp
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v_old], now_ts=now + 5)
    assert len(res) == 1
    bus = res[0]

    # The anchor was NOT replaced by the older timestamp!
    assert matcher._tracking_state["DL1PC3002"]["anchor_gps_ts"] == now
    assert bus["last_gps_timestamp"] == now
    # Out of order flag is recorded
    assert "OUT_OF_ORDER_GPS_TIMESTAMP" in bus["anomaly_flags"]
    assert bus["has_anomalies"] is True


def test_audit_case_e_large_gps_correction_error_flagged_as_anomaly(matcher):
    """Test Case E: Large GPS correction error (>250m) is flagged as an anomaly."""
    now = 1700000000
    v1 = ValidatedVehiclePosition(
        vehicle_id="DL1PC3003",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v1], now_ts=now)

    # Next GPS ping arrives with a huge 400m jump
    v2 = ValidatedVehiclePosition(
        vehicle_id="DL1PC3003",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7160,  # ~450m jump north
        longitude=77.1720,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now + 15,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v2], now_ts=now + 15)
    assert len(res) == 1
    bus = res[0]

    assert bus["last_prediction_error_meters"] is not None
    assert bus["last_prediction_error_meters"] > 250.0
    assert "LARGE_PREDICTION_ERROR" in bus["anomaly_flags"]
    assert bus["has_anomalies"] is True
    # SAFETY REQUIREMENT: Must NOT appear as verified approaching bus; position frozen at last genuine GPS
    assert bus["is_verified_suitable"] is False
    assert bus["progress_status"] == "UNVERIFIED_STALE"
    assert bus["latitude"] == bus["last_gps_latitude"]
    assert bus["longitude"] == bus["last_gps_longitude"]
    assert bus["correction_status"] == "UNVERIFIED_ANOMALY_FROZEN"


def test_audit_case_h_ambiguous_shape_projection_frozen_unverified(matcher):
    """Test Case H: Vehicle with ambiguous shape distance (>200m) is frozen and marked unverified."""
    now = 1700000000
    # Position vehicle 300m away from corridor shape
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC3008",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1850,  # ~1000m east of corridor (corridor is ~77.175)
        bearing=325.0,
        speed_kmh=20.0,
        timestamp_utc=now,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now)
    assert len(res) == 1
    bus = res[0]

    assert "AMBIGUOUS_SHAPE_PROJECTION" in bus["anomaly_flags"]
    assert bus["has_anomalies"] is True
    assert bus["is_verified_suitable"] is False
    assert bus["progress_status"] == "UNVERIFIED_STALE"
    assert bus["latitude"] == bus["last_gps_latitude"]
    assert bus["longitude"] == bus["last_gps_longitude"]
    assert bus["correction_status"] == "UNVERIFIED_ANOMALY_FROZEN"


def test_audit_case_f_legitimate_trip_change_resets_state(matcher):
    """Test Case F: Legitimate trip change resets tracking state without corrupting progress."""
    now = 1700000000
    v1 = ValidatedVehiclePosition(
        vehicle_id="DL1PC3004",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=30.0,
        timestamp_utc=now,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res1 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v1], now_ts=now)
    assert len(res1) == 1
    assert matcher._tracking_state["DL1PC3004"]["trip_id"] == "1598_FULL_05_50"

    # Vehicle finishes trip and starts new trip "1598_FULL_06_30"
    v2 = ValidatedVehiclePosition(
        vehicle_id="DL1PC3004",
        route_id="1598",
        trip_id="1598_FULL_06_30",  # Changed trip ID
        latitude=28.7110,
        longitude=77.1760,
        bearing=325.0,
        speed_kmh=20.0,
        timestamp_utc=now + 60,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )
    res2 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v2], now_ts=now + 60)
    assert len(res2) == 1
    # State reset: trip_id updated to new trip, new anchor initialized cleanly
    assert matcher._tracking_state["DL1PC3004"]["trip_id"] == "1598_FULL_06_30"
    assert res2[0]["correction_status"] == "GPS_ANCHOR_VERIFIED"


def test_audit_case_g_backward_progress_prevention_monotonicity(matcher):
    """Test Case G: Route progress along a trip is strictly monotonic (never decreases)."""
    now = 1700000000
    v = ValidatedVehiclePosition(
        vehicle_id="DL1PC3005",
        route_id="1598",
        trip_id="1598_FULL_05_50",
        latitude=28.7120,
        longitude=77.1750,
        bearing=325.0,
        speed_kmh=36.0,  # 10 m/s
        timestamp_utc=now,
        is_valid_coordinates=True,
        is_fresh=True,
        is_matched_to_gtfs=True,
        validation_notes=[],
        is_current=True,
        is_out_of_area=False,
        area_classification="DELHI_CORE",
    )

    t0 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now)[0]["route_progress_meters"]
    t15 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now + 15)[0]["route_progress_meters"]
    t30 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now + 30)[0]["route_progress_meters"]
    t45 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now + 45)[0]["route_progress_meters"]
    t60 = matcher.get_suitable_buses_for_leg("1598", "284", "5146", [v], now_ts=now + 60)[0]["route_progress_meters"]

    # Verify strict monotonicity:
    assert t0 <= t15, f"Reversal at T+15: {t0} > {t15}"
    assert t15 <= t30, f"Reversal at T+30: {t15} > {t30}"
    assert t30 <= t45, f"Reversal at T+45: {t30} > {t45}"
    assert t45 <= t60, f"Reversal at T+60: {t45} > {t60}"


def test_gps_audit_log_endpoint(matcher):
    """Test that /api/v1/live/gps-audit-log returns structured audit records."""
    response = client.get("/api/v1/live/gps-audit-log")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)




