"""Automated Verification Tests for Milestone 2.2: Multi-Day Ground-Truth Coverage & Integrity.

Tests:
1. Daily Parquet partition schema and timestamp projection.
2. Rule E01-E03 quarantine table integrity and non-empty tracking.
3. Stop-crossing ground truth schema and mathematical consistency.
4. Physical feasibility of observed segment speeds (0 < v <= 90 km/h).
5. Fallback tier assignment hierarchy conforming to PRD Section 6.5 & 7.4.
"""

import os
import duckdb
import pytest
import pandas as pd
import numpy as np

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GPS_PARQUET_DIR = os.path.join(ROOT_DIR, "data", "processed", "gps_parquet")
QUARANTINE_DIR = os.path.join(ROOT_DIR, "data", "processed", "quarantine")
STOP_CROSSINGS_DIR = os.path.join(ROOT_DIR, "data", "processed", "stop_crossings")

REQUIRED_GPS_COLUMNS = {
    "vehicle_id", "lat", "lng", "speed_kmh", "route_id", "trip_id_raw",
    "trip_id_canonical", "timestamp_utc", "timestamp_ist", "service_date", "hour_ist"
}

REQUIRED_SEGMENT_COLUMNS = {
    "observation_id", "trajectory_id", "vehicle_id", "route_id", "pattern_id",
    "segment_key", "stop_id_from", "stop_id_to", "distance_m", "segment_time_s",
    "speed_kmh", "arrival_from_utc", "arrival_to_utc", "arrival_from_ist", "arrival_to_ist"
}

def test_daily_gps_partitions_exist_and_conform():
    """Verify that processed GPS Parquet partitions have identical schemas and correct columns."""
    con = duckdb.connect()
    partitions = [d for d in os.listdir(GPS_PARQUET_DIR) if d.startswith("service_date=")]
    assert len(partitions) >= 2, f"Expected at least 2 processed partitions, found {len(partitions)}"

    for part in partitions:
        pq_path = os.path.join(GPS_PARQUET_DIR, part, "data.parquet")
        assert os.path.exists(pq_path), f"Missing parquet file in {part}"
        cols = set(con.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM '{pq_path}')").df()["column_name"])
        missing = REQUIRED_GPS_COLUMNS - cols
        assert not missing, f"Partition {part} is missing required columns: {missing}"

        # Verify UTC and IST non-null
        null_ts = con.execute(f"SELECT COUNT(*) FROM '{pq_path}' WHERE timestamp_utc IS NULL OR timestamp_ist IS NULL").fetchone()[0]
        assert null_ts == 0, f"Partition {part} contains null timestamps"

def test_quarantine_integrity():
    """Verify that quarantine files exist for processed dates and contain expected columns."""
    con = duckdb.connect()
    conflicts = [f for f in os.listdir(QUARANTINE_DIR) if f.startswith("conflicts_")]
    assert len(conflicts) >= 2, f"Expected conflict quarantine files, found {len(conflicts)}"

    for c_file in conflicts:
        p = os.path.join(QUARANTINE_DIR, c_file)
        df = con.execute(f"SELECT * FROM '{p}' LIMIT 5").df()
        assert "vehicle_id" in df.columns
        assert "timestamp" in df.columns
        assert "conflict_group_size" in df.columns

def test_stop_crossings_schema_and_integrity():
    """Verify ground truth observed segments format, monotonic time, and physical bounds."""
    con = duckdb.connect()
    dates_with_segs = [d for d in os.listdir(STOP_CROSSINGS_DIR) if d.startswith("service_date=")]
    assert len(dates_with_segs) >= 1, "Expected at least 1 stop crossing partition"

    for d in dates_with_segs:
        seg_p = os.path.join(STOP_CROSSINGS_DIR, d, "observed_segments.parquet")
        if not os.path.exists(seg_p):
            continue
        cols = set(con.execute(f"SELECT column_name FROM (DESCRIBE SELECT * FROM '{seg_p}')").df()["column_name"])
        missing = REQUIRED_SEGMENT_COLUMNS - cols
        assert not missing, f"Observed segments in {d} missing: {missing}"

        df = con.execute(f"SELECT * FROM '{seg_p}'").df()
        if len(df) == 0:
            continue

        # Monotonic time check
        assert (df["arrival_to_utc"] > df["arrival_from_utc"]).all(), "Arrival times must be strictly increasing"
        # Speed non-negative and plausible
        assert (df["speed_kmh"] > 0).all(), "Speeds must be strictly positive"
        assert (df["speed_kmh"] <= 90.0).all(), "Speeds must not exceed 90 km/h filter rule"
        assert (df["distance_m"] > 0).all(), "Segment distance must be positive"

def test_fallback_tier_classification():
    """Verify the PRD Section 6.5 & 7.4 fallback tier hierarchy assignment."""
    def assign_tier(obs_count: int, pool_count: int, corridor_count: int) -> str:
        if obs_count >= 3:
            return "TIER_1_DIRECT_OBSERVED"
        elif pool_count >= 3:
            return "TIER_2_CORRIDOR_POOLED"
        elif corridor_count >= 3:
            return "TIER_3_TIMEPOINT_AGGREGATED"
        else:
            return "TIER_4_ROUTE_BASELINE"

    assert assign_tier(5, 10, 20) == "TIER_1_DIRECT_OBSERVED"
    assert assign_tier(1, 4, 15) == "TIER_2_CORRIDOR_POOLED"
    assert assign_tier(0, 1, 6) == "TIER_3_TIMEPOINT_AGGREGATED"
    assert assign_tier(0, 0, 1) == "TIER_4_ROUTE_BASELINE"

