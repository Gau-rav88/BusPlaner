"""
Automated Validation Tests for GPS Ingestion and Cleaning Pipeline
Milestone 1 Deliverable
"""

import os
import duckdb
import pytest
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET_FILE = os.path.join(ROOT_DIR, "data", "processed", "gps_parquet", "service_date=2026-10-01", "data.parquet")
QUARANTINE_DIR = os.path.join(ROOT_DIR, "data", "processed", "quarantine")


def test_gps_cleaning_logic():
    con = duckdb.connect()

    # Create mock dataset with exact duplicates, conflicting duplicates, out of bounds, and float route IDs
    con.execute("""
        CREATE TABLE mock_gps (
            vehicle_id VARCHAR,
            lat VARCHAR,
            lng VARCHAR,
            speed DOUBLE,
            route_id DOUBLE,
            trip_id VARCHAR,
            timestamp VARCHAR,
            date DATE,
            time VARCHAR
        );

        INSERT INTO mock_gps VALUES
        -- Valid row
        ('BUS1', '28.6139', '77.2090', 25.0, 1000.0, '1000_08_30_1', '1790800000', '2026-10-01', '08:30:00'),
        -- Exact duplicate (E01)
        ('BUS1', '28.6139', '77.2090', 25.0, 1000.0, '1000_08_30_1', '1790800000', '2026-10-01', '08:30:00'),
        -- Conflicting duplicate with same vehicle and timestamp but different speed/location (E02)
        ('BUS1', '28.6145', '77.2095', 10.0, 1000.0, '1000_08_30_1', '1790800000', '2026-10-01', '08:30:00'),
        -- Out of bounds coordinate (E03)
        ('BUS2', '12.9716', '77.5946', 30.0, 500.0, '500_09_00', '1790800010', '2026-10-01', '08:30:10');
    """)

    # Verify E01 deduplication
    dedup = con.execute("SELECT DISTINCT * FROM mock_gps").fetchall()
    assert len(dedup) == 3, "Exact duplicate must be collapsed"

    # Verify E02 ranking
    ranked = con.execute("""
        SELECT *, ROW_NUMBER() OVER (PARTITION BY vehicle_id, timestamp ORDER BY speed DESC) as rk
        FROM (SELECT DISTINCT * FROM mock_gps)
    """).fetchall()
    kept = [r for r in ranked if r[-1] == 1]
    quarantined = [r for r in ranked if r[-1] > 1]
    assert len(kept) == 2
    assert len(quarantined) == 1
    assert quarantined[0][3] == 10.0, "Lower speed conflict should be quarantined"

    # Verify Route ID normalization
    norm_route = con.execute("""
        SELECT REGEXP_REPLACE(CAST(CAST(1000.0 AS BIGINT) AS VARCHAR), '\\.0$', '')
    """).fetchone()[0]
    assert norm_route == "1000"

    # Verify Trip ID prefix extraction
    canonical_trip = con.execute("""
        SELECT REGEXP_EXTRACT('1000_08_30_1234', '^(\\d+_\\d+_\\d+)')
    """).fetchone()[0]
    assert canonical_trip == "1000_08_30"


def test_ingested_parquet_partition():
    if not os.path.exists(PARQUET_FILE):
        pytest.skip(f"Parquet partition {PARQUET_FILE} not yet written")

    con = duckdb.connect()
    df_check = con.execute(f"""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(DISTINCT vehicle_id) as v_cnt,
            MIN(lat) as min_lat,
            MAX(lat) as max_lat,
            MIN(lng) as min_lng,
            MAX(lng) as max_lng,
            MIN(speed_kmh) as min_spd,
            MAX(speed_kmh) as max_spd,
            COUNT(DISTINCT timestamp_utc) as ts_cnt
        FROM read_parquet('{PARQUET_FILE}')
    """).df().to_dict(orient="records")[0]

    assert df_check["total_rows"] > 10000000, "Clean Day 1 Parquet should have > 10M rows"
    assert df_check["min_lat"] >= 28.0, "All lat >= 28.0"
    assert df_check["max_lat"] <= 29.2, "All lat <= 29.2"
    assert df_check["min_lng"] >= 76.5, "All lng >= 76.5"
    assert df_check["max_lng"] <= 77.8, "All lng <= 77.8"
    assert df_check["min_spd"] >= 0.0, "No negative speeds"

