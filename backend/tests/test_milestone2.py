"""Unit and Integration Tests for Milestone 2: Route Geometry, Map Matching,
Trajectory Reconstruction, and Stop-Crossing Extraction.
"""

import math
import pandas as pd
import pytest
from shapely.geometry import Point

from backend.core.geometry import RoutePattern, StopOccurrence, calculate_bearing
from backend.core.map_matching import match_trajectory_to_route
from backend.core.stop_crossings import extract_stop_crossings_from_trajectory
from backend.core.trajectory import reconstruct_vehicle_trajectories


@pytest.fixture
def sample_route_pattern():
    """Create a synthetic 4-stop linear route in UTM coordinates (EPSG:32643)."""
    # 4 stops spaced 500 meters apart heading North along x = 715000
    stops = [
        StopOccurrence(stop_sequence=1, stop_id="S1", stop_name="Origin Stop", utm_x=715000.0, utm_y=3170000.0, lat=28.64, lon=77.20, along_dist_m=0.0, segment_bearing_deg=0.0),
        StopOccurrence(stop_sequence=2, stop_id="S2", stop_name="Second Stop", utm_x=715000.0, utm_y=3170500.0, lat=28.645, lon=77.20, along_dist_m=500.0, segment_bearing_deg=0.0),
        StopOccurrence(stop_sequence=3, stop_id="S3", stop_name="Third Stop", utm_x=715000.0, utm_y=3171000.0, lat=28.65, lon=77.20, along_dist_m=1000.0, segment_bearing_deg=0.0),
        StopOccurrence(stop_sequence=4, stop_id="S4", stop_name="Terminal Stop", utm_x=715000.0, utm_y=3171500.0, lat=28.655, lon=77.20, along_dist_m=1500.0, segment_bearing_deg=0.0),
    ]
    return RoutePattern(
        pattern_id="TEST_ROUTE_DIR0",
        route_id="999",
        direction_id=0,
        stops=stops,
        total_length_m=1500.0,
        geometry_type="STOP_TOPOLOGY",
    )


def test_geometry_linear_referencing(sample_route_pattern):
    """Test along-route distance and perpendicular offset calculation."""
    # Point exactly on segment between Stop 1 and Stop 2
    along, perp, seg = sample_route_pattern.project_point(715000.0, 3170250.0)
    assert pytest.approx(along, 0.1) == 250.0
    assert pytest.approx(perp, 0.1) == 0.0
    assert seg == 0

    # Point offset 20m East of route at y = 3170750 (between Stop 2 and Stop 3)
    along2, perp2, seg2 = sample_route_pattern.project_point(715020.0, 3170750.0)
    assert pytest.approx(along2, 0.1) == 750.0
    assert pytest.approx(perp2, 0.1) == 20.0
    assert seg2 == 1


def test_trajectory_reconstruction_rules():
    """Test Trajectory Reconstruction: gap splitting (E07) and jump detection (E05)."""
    # 5 pings: first 3 normal (10s intervals), 4th ping after 400s gap (E07), 5th ping teleport jump (E05)
    data = {
        "vehicle_id": ["BUS_01"] * 5,
        "lat": [28.64, 28.641, 28.642, 28.643, 28.90],
        "lng": [77.20, 77.20, 77.20, 77.20, 77.50],
        "speed_kmh": [20.0, 22.0, 25.0, 15.0, 80.0],
        "route_id": ["999"] * 5,
        "trip_id_raw": ["999_1"] * 5,
        "trip_id_canonical": ["999_1"] * 5,
        "timestamp_utc": [1000, 1010, 1020, 1450, 1460],  # 1450 - 1020 = 430s gap; 1460 is jump
        "service_date": ["2026-10-01"] * 5,
    }
    df = pd.DataFrame(data)
    trajs = reconstruct_vehicle_trajectories(df, max_gap_seconds=300.0, max_speed_kmh=90.0)

    # Should be split into 3 segments due to gap (>300s) and jump
    traj_ids = trajs["trajectory_id"].unique()
    assert len(traj_ids) == 3

    # Check decisions
    assert trajs["filter_decision"].iloc[0] == "START_OF_FEED"
    assert trajs["filter_decision"].iloc[1] == "VALID_CONTINUOUS"
    assert "E07_GAP_EXCEEDED" in trajs["filter_decision"].iloc[3]
    assert "E05_IMPLAUSIBLE_JUMP" in trajs["filter_decision"].iloc[4]


def test_map_matching_decision_gates(sample_route_pattern):
    """Test Map Matching confidence, distance rejection, and sparse rejection."""
    # Case 1: Confident match (points along route)
    pings_valid = pd.DataFrame({
        "trajectory_id": ["T_VALID"] * 6,
        "vehicle_id": ["BUS_01"] * 6,
        "utm_x": [715005.0, 715002.0, 715008.0, 715004.0, 715006.0, 715003.0],
        "utm_y": [3170100.0, 3170300.0, 3170600.0, 3170850.0, 3171100.0, 3171350.0],
        "timestamp_utc": [100, 120, 150, 180, 210, 240],
        "speed_kmh": [25.0] * 6,
    })
    res_valid = match_trajectory_to_route(pings_valid, [sample_route_pattern])
    assert res_valid.status == "MATCHED_CONFIDENT"
    assert res_valid.confidence >= 0.70
    assert res_valid.mean_perp_dist_m < 10.0

    # Case 2: Sparse pings (< 5 pings)
    pings_sparse = pings_valid.iloc[:3].copy()
    res_sparse = match_trajectory_to_route(pings_sparse, [sample_route_pattern])
    assert res_sparse.status == "UNMATCHED_TOO_FEW_PINGS"

    # Case 3: Off-route trajectory (500m away)
    pings_off = pings_valid.copy()
    pings_off["utm_x"] = pings_off["utm_x"] + 500.0
    res_off = match_trajectory_to_route(pings_off, [sample_route_pattern])
    assert res_off.status == "UNMATCHED_EXCESSIVE_DISTANCE"

    # Case 4: Reverse direction (along-distance decreases)
    pings_rev = pings_valid.sort_values(by="timestamp_utc", ascending=False).copy()
    pings_rev["timestamp_utc"] = [100, 120, 150, 180, 210, 240]  # chronological time but decreasing y
    res_rev = match_trajectory_to_route(pings_rev, [sample_route_pattern])
    assert res_rev.status == "UNMATCHED_REVERSE_OR_ERRATIC"


def test_stop_crossing_linear_interpolation(sample_route_pattern):
    """Test stop crossing extraction and verification that nearest-ping is NOT used."""
    # Stop 2 is at along_dist = 500m.
    # Ping A: along_dist = 400m, timestamp = 1000
    # Ping B: along_dist = 600m, timestamp = 1020
    # True interpolated crossing time should be 1000 + (500-400)/(600-400) * 20 = 1010.0
    # Stop 3 is at along_dist = 1000m.
    # Ping C: along_dist = 900m, timestamp = 1060
    # Ping D: along_dist = 1100m, timestamp = 1080
    # Interpolated crossing for Stop 3 = 1070.0
    matched_df = pd.DataFrame({
        "trajectory_id": ["T_TEST"] * 4,
        "vehicle_id": ["BUS_TEST"] * 4,
        "timestamp_utc": [1000, 1020, 1060, 1080],
        "along_dist_m": [400.0, 600.0, 900.0, 1100.0],
        "speed_kmh": [36.0, 36.0, 36.0, 36.0],
    })

    crossings, segments = extract_stop_crossings_from_trajectory(
        matched_df, sample_route_pattern, max_interpolation_gap_s=120.0
    )

    # Crossings for Stop 2 and Stop 3 should be extracted
    assert len(crossings) == 2
    c2 = next(c for c in crossings if c.stop_id == "S2")
    c3 = next(c for c in crossings if c.stop_id == "S3")

    # Verify interpolation formula
    assert pytest.approx(c2.arrival_time_utc, 0.01) == 1010.0
    # Nearest ping was at 1000 (400m) or 1020 (600m); exact interpolated is 1010.0!
    assert c2.arrival_time_utc != 1000
    assert c2.arrival_time_utc != 1020

    assert pytest.approx(c3.arrival_time_utc, 0.01) == 1070.0

    # Consecutive segment S2 -> S3
    assert len(segments) == 1
    seg = segments[0]
    assert seg.stop_id_from == "S2"
    assert seg.stop_id_to == "S3"
    assert pytest.approx(seg.distance_m, 0.1) == 500.0
    assert pytest.approx(seg.segment_time_s, 0.1) == 60.0  # 1070 - 1010
    # Speed: 500m / 60s * 3.6 = 30.0 km/h
    assert pytest.approx(seg.speed_kmh, 0.1) == 30.0


def test_stop_crossing_rejection_on_excessive_gap(sample_route_pattern):
    """Test that stop crossing is rejected when bracketing gap > 120s."""
    # Stop 2 is at along_dist = 500m.
    # Ping A: along_dist = 400m, timestamp = 1000
    # Ping B: along_dist = 600m, timestamp = 1150 (gap = 150s > 120s max gap)
    matched_df = pd.DataFrame({
        "trajectory_id": ["T_GAP"] * 2,
        "vehicle_id": ["BUS_TEST"] * 2,
        "timestamp_utc": [1000, 1150],
        "along_dist_m": [400.0, 600.0],
        "speed_kmh": [5.0, 5.0],
    })

    crossings, segments = extract_stop_crossings_from_trajectory(
        matched_df, sample_route_pattern, max_interpolation_gap_s=120.0
    )

    # Should reject crossing for Stop 2 because 150s > 120s
    assert len(crossings) == 0
    assert len(segments) == 0

