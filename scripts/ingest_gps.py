#!/usr/bin/env python3
"""
Delhi Real-Time Bus Traffic Model & Journey Planner
Milestone 1: GPS Ingestion and Cleaning Pipeline

Features:
- Safe day-by-day streaming ingestion with disk space pre-checks
- Rule E01: Exact duplicate removal
- Rule E02: Conflicting duplicate resolution with deterministic ranking and quarantine logging
- Rule E03: Spatial bounding box validation ([28.0, 29.2] lat, [76.5, 77.8] lng)
- Type casting: lat/lng to float, speed to float, normalized route_id to string, trip_id prefix extraction
- Timestamps: preserves UTC Unix seconds, projects to Asia/Kolkata (IST), derives hour, minute, day of week
- Converts to compressed, partitioned Parquet
- Full verification of output before removing any temporary uncompressed raw files
"""

import os
import sys
import shutil
import json
import time
import argparse
from datetime import datetime, timezone
import duckdb

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_GPS_DIR = os.path.join(ROOT_DIR, "data", "raw", "gps")
PARQUET_DIR = os.path.join(ROOT_DIR, "data", "processed", "gps_parquet")
QUARANTINE_DIR = os.path.join(ROOT_DIR, "data", "processed", "quarantine")
METRICS_PATH = os.path.join(ROOT_DIR, "data", "processed", "ingestion_metrics.json")

# Minimum required free disk space in MB to begin processing
MIN_FREE_DISK_MB = 2048


def check_disk_space(path: str, required_mb: int = MIN_FREE_DISK_MB):
    usage = shutil.disk_usage(path)
    free_mb = usage.free // (1024 * 1024)
    if free_mb < required_mb:
        raise RuntimeError(f"Insufficient disk space on {path}: {free_mb} MB available, {required_mb} MB required.")
    return free_mb


def process_daily_db(db_path: str, service_date: str) -> dict:
    t0 = time.time()
    os.makedirs(PARQUET_DIR, exist_ok=True)
    os.makedirs(QUARANTINE_DIR, exist_ok=True)

    free_mb = check_disk_space(os.path.dirname(PARQUET_DIR))
    print(f"\n=======================================================")
    print(f"Ingesting: {db_path} (Service Date: {service_date})")
    print(f"Free Disk Space: {free_mb} MB")
    print(f"=======================================================")

    con = duckdb.connect()
    con.execute("LOAD sqlite;")
    con.execute(f"ATTACH '{db_path}' AS sqlite (TYPE SQLITE);")

    # 1. Total Raw Rows
    raw_count = con.execute("SELECT COUNT(*) FROM sqlite.vehicle_feed").fetchone()[0]
    print(f"1. Raw Observations: {raw_count:,}")

    # 2. Rule E01: Deduplicate exact duplicate rows across all columns
    print("2. Deduplicating exact duplicate records (Rule E01)...")
    con.execute("""
        CREATE TEMP TABLE stage_e01 AS
        SELECT DISTINCT
            vehicle_id,
            lat,
            lng,
            speed,
            route_id,
            trip_id,
            timestamp,
            date,
            time
        FROM sqlite.vehicle_feed;
    """)
    e01_count = con.execute("SELECT COUNT(*) FROM stage_e01").fetchone()[0]
    e01_dropped = raw_count - e01_count
    print(f"   Distinct after E01: {e01_count:,} (Removed {e01_dropped:,} exact duplicates, {e01_dropped/raw_count*100:.2f}%)")

    # 3. Rule E02: Conflicting duplicate records on (vehicle_id, timestamp)
    print("3. Resolving conflicting duplicates (Rule E02)...")
    con.execute("""
        CREATE TEMP TABLE stage_ranked AS
        SELECT
            vehicle_id,
            lat,
            lng,
            speed,
            route_id,
            trip_id,
            timestamp,
            date,
            time,
            ROW_NUMBER() OVER (
                PARTITION BY vehicle_id, timestamp
                ORDER BY speed DESC, lat, lng
            ) as conflict_rank,
            COUNT(*) OVER (
                PARTITION BY vehicle_id, timestamp
            ) as conflict_group_size
        FROM stage_e01;
    """)

    # Quarantine conflicting records (rank > 1)
    quarantine_conflict_file = os.path.join(QUARANTINE_DIR, f"conflicts_{service_date}.parquet")
    con.execute(f"""
        COPY (
            SELECT 
                vehicle_id,
                timestamp,
                lat,
                lng,
                speed,
                route_id,
                trip_id,
                conflict_rank,
                conflict_group_size,
                'E02_CONFLICTING_TIMESTAMP_POSITION' as quarantine_reason,
                '{service_date}' as service_date
            FROM stage_ranked
            WHERE conflict_rank > 1
        ) TO '{quarantine_conflict_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    conflict_quarantined = con.execute("SELECT COUNT(*) FROM stage_ranked WHERE conflict_rank > 1").fetchone()[0]
    print(f"   Conflicting records quarantined to {quarantine_conflict_file}: {conflict_quarantined:,}")

    # Keep rank 1
    con.execute("""
        CREATE TEMP TABLE stage_e02 AS
        SELECT * EXCLUDE (conflict_rank, conflict_group_size)
        FROM stage_ranked
        WHERE conflict_rank = 1;
    """)
    e02_count = con.execute("SELECT COUNT(*) FROM stage_e02").fetchone()[0]
    print(f"   Distinct after E02 resolution: {e02_count:,}")

    # 4. Rule E03: Spatial bounding box check [28.0, 29.2] lat, [76.5, 77.8] lng
    print("4. Applying coordinate bounding box filter (Rule E03)...")
    quarantine_bounds_file = os.path.join(QUARANTINE_DIR, f"out_of_bounds_{service_date}.parquet")
    con.execute(f"""
        COPY (
            SELECT 
                *,
                'E03_OUT_OF_BOUNDS_COORDINATE' as quarantine_reason,
                '{service_date}' as service_date
            FROM stage_e02
            WHERE TRY_CAST(lat AS DOUBLE) < 28.0 OR TRY_CAST(lat AS DOUBLE) > 29.2
               OR TRY_CAST(lng AS DOUBLE) < 76.5 OR TRY_CAST(lng AS DOUBLE) > 77.8
               OR TRY_CAST(lat AS DOUBLE) IS NULL OR TRY_CAST(lng AS DOUBLE) IS NULL
        ) TO '{quarantine_bounds_file}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    bounds_quarantined = con.execute("""
        SELECT COUNT(*) FROM stage_e02
        WHERE TRY_CAST(lat AS DOUBLE) < 28.0 OR TRY_CAST(lat AS DOUBLE) > 29.2
           OR TRY_CAST(lng AS DOUBLE) < 76.5 OR TRY_CAST(lng AS DOUBLE) > 77.8
           OR TRY_CAST(lat AS DOUBLE) IS NULL OR TRY_CAST(lng AS DOUBLE) IS NULL
    """).fetchone()[0]
    print(f"   Out-of-bounds records quarantined to {quarantine_bounds_file}: {bounds_quarantined:,}")

    # 5. Type casting and timestamp enrichment
    print("5. Formatting types and projecting timestamps to Asia/Kolkata...")
    date_partition_dir = os.path.join(PARQUET_DIR, f"service_date={service_date}")
    os.makedirs(date_partition_dir, exist_ok=True)
    out_parquet_path = os.path.join(date_partition_dir, "data.parquet")

    con.execute(f"""
        COPY (
            SELECT
                vehicle_id,
                CAST(lat AS DOUBLE) as lat,
                CAST(lng AS DOUBLE) as lng,
                CAST(speed AS DOUBLE) as speed_kmh,
                -- Route normalization: strip trailing .0
                REGEXP_REPLACE(CAST(CAST(route_id AS BIGINT) AS VARCHAR), '\\.0$', '') as route_id,
                trip_id as trip_id_raw,
                -- Trip ID prefix extraction (^(\\d+_\\d+_\\d+))
                REGEXP_EXTRACT(trip_id, '^(\\d+_\\d+_\\d+)') as trip_id_canonical,
                CAST(timestamp AS BIGINT) as timestamp_utc,
                -- Project UTC to Asia/Kolkata (UTC + 05:30)
                TO_TIMESTAMP(CAST(timestamp AS BIGINT)) AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata' as timestamp_ist,
                TRY_CAST(date AS DATE) as service_date,
                EXTRACT(hour FROM (TO_TIMESTAMP(CAST(timestamp AS BIGINT)) AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')) as hour_ist,
                EXTRACT(minute FROM (TO_TIMESTAMP(CAST(timestamp AS BIGINT)) AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')) as minute_ist,
                DAYOFWEEK(TO_TIMESTAMP(CAST(timestamp AS BIGINT)) AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') as day_of_week,
                CASE WHEN DAYOFWEEK(TO_TIMESTAMP(CAST(timestamp AS BIGINT)) AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata') IN (0, 6) THEN TRUE ELSE FALSE END as is_weekend
            FROM stage_e02
            WHERE TRY_CAST(lat AS DOUBLE) >= 28.0 AND TRY_CAST(lat AS DOUBLE) <= 29.2
              AND TRY_CAST(lng AS DOUBLE) >= 76.5 AND TRY_CAST(lng AS DOUBLE) <= 77.8
        ) TO '{out_parquet_path}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    # 6. Verify written Parquet partition
    print("6. Verifying Parquet output...")
    if not os.path.exists(out_parquet_path) or os.path.getsize(out_parquet_path) == 0:
        raise RuntimeError(f"Parquet file {out_parquet_path} was not created or is empty!")

    parquet_size_mb = os.path.getsize(out_parquet_path) / (1024 * 1024)
    final_count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out_parquet_path}')").fetchone()[0]
    distinct_vehicles = con.execute(f"SELECT COUNT(DISTINCT vehicle_id) FROM read_parquet('{out_parquet_path}')").fetchone()[0]
    distinct_routes = con.execute(f"SELECT COUNT(DISTINCT route_id) FROM read_parquet('{out_parquet_path}')").fetchone()[0]
    distinct_trips = con.execute(f"SELECT COUNT(DISTINCT trip_id_canonical) FROM read_parquet('{out_parquet_path}')").fetchone()[0]

    elapsed = time.time() - t0
    metrics = {
        "service_date": service_date,
        "raw_records": raw_count,
        "e01_exact_duplicates_removed": e01_dropped,
        "e02_conflicts_quarantined": conflict_quarantined,
        "e03_out_of_bounds_removed": bounds_quarantined,
        "clean_records_retained": final_count,
        "retention_rate_pct": round(final_count / raw_count * 100.0, 2),
        "distinct_vehicles": distinct_vehicles,
        "distinct_routes": distinct_routes,
        "distinct_trips_canonical": distinct_trips,
        "parquet_path": out_parquet_path,
        "parquet_size_mb": round(parquet_size_mb, 2),
        "elapsed_seconds": round(elapsed, 2)
    }

    print(f"\n[OK] Partition verified successfully!")
    print(f"  Clean Rows Retained: {final_count:,} / {raw_count:,} ({metrics['retention_rate_pct']}%)")
    print(f"  Distinct Vehicles: {distinct_vehicles:,}")
    print(f"  Parquet Output Size: {parquet_size_mb:.2f} MB (Compression ratio: {os.path.getsize(db_path) / os.path.getsize(out_parquet_path):.1f}x)")
    print(f"  Elapsed Time: {elapsed:.2f}s")
    con.close()
    return metrics


def save_metrics(daily_metrics: dict):
    existing = {}
    if os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    date_key = daily_metrics["service_date"]
    existing[date_key] = daily_metrics

    with open(METRICS_PATH, "w") as f:
        json.dump(existing, f, indent=2)
    print(f"Updated ingestion metrics at {METRICS_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest and clean daily GPS SQLite database to Parquet")
    parser.add_argument("--db-path", default=os.path.join(RAW_GPS_DIR, "bus_movements_2026_10_01.db"), help="Path to daily SQLite database")
    parser.add_argument("--date", default="2026-10-01", help="Service date in YYYY-MM-DD")
    args = parser.parse_args()

    metrics = process_daily_db(args.db_path, args.date)
    save_metrics(metrics)

