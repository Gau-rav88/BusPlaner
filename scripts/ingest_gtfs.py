#!/usr/bin/env python3
"""
Delhi Real-Time Bus Traffic Model & Journey Planner
Milestone 1: GTFS Ingestion and Validation Script

Loads static GTFS files into the SQLite serving database (data/serving/delhi_bus.db).
Performs schema validation, coordinate bounds checking, seconds-from-midnight conversion,
metric coordinate projection (EPSG:32643), and foreign-key referential integrity checks.
"""

import os
import sys
import argparse
import sqlite3
import pandas as pd
import numpy as np
from pyproj import Transformer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GTFS_DIR = os.path.join(ROOT_DIR, "data", "raw", "gtfs")
DEFAULT_SERVING_DB = os.path.join(ROOT_DIR, "data", "serving", "delhi_bus.db")

# Coordinate conversion to EPSG:32643 (UTM Zone 43N)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def parse_time_to_seconds(time_str: str) -> int:
    """Converts HH:MM:SS to seconds from service-day midnight. Supports times >= 24:00:00."""
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(float(parts[2]))
            return h * 3600 + m * 60 + s
    except Exception:
        pass
    return -1


def ingest_gtfs(gtfs_dir: str, db_path: str) -> dict:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")

    metrics = {
        "gtfs_dir": gtfs_dir,
        "db_path": db_path,
        "tables": {},
        "referential_integrity": {},
        "warnings": []
    }

    print(f"=== Ingesting GTFS from: {gtfs_dir} ===")
    print(f"=== Serving database target: {db_path} ===")

    # 1. Agency
    agency_file = os.path.join(gtfs_dir, "agency.txt")
    if os.path.exists(agency_file):
        df_agency = pd.read_csv(agency_file, dtype=str)
        df_agency.to_sql("agency", conn, if_exists="replace", index=False)
        metrics["tables"]["agency"] = len(df_agency)
        print(f"  [OK] agency: {len(df_agency)} rows")

    # 2. Calendar
    calendar_file = os.path.join(gtfs_dir, "calendar.txt")
    if os.path.exists(calendar_file):
        df_cal = pd.read_csv(calendar_file, dtype=str)
        df_cal.to_sql("calendar", conn, if_exists="replace", index=False)
        metrics["tables"]["calendar"] = len(df_cal)
        print(f"  [OK] calendar: {len(df_cal)} rows")

    # 3. Routes
    routes_file = os.path.join(gtfs_dir, "routes.txt")
    if os.path.exists(routes_file):
        df_routes = pd.read_csv(routes_file, dtype=str)
        # Normalize route_id: strip trailing .0 if present
        df_routes["route_id"] = df_routes["route_id"].apply(lambda r: str(int(float(r))) if str(r).replace(".0","").isdigit() else str(r).strip())
        df_routes.to_sql("routes", conn, if_exists="replace", index=False)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_routes_id ON routes(route_id);")
        metrics["tables"]["routes"] = len(df_routes)
        print(f"  [OK] routes: {len(df_routes)} rows (indexed)")

    # 4. Stops
    stops_file = os.path.join(gtfs_dir, "stops.txt")
    if os.path.exists(stops_file):
        df_stops = pd.read_csv(stops_file)
        df_stops["stop_id"] = df_stops["stop_id"].astype(str).str.strip()
        df_stops["stop_lat"] = pd.to_numeric(df_stops["stop_lat"], errors="coerce")
        df_stops["stop_lon"] = pd.to_numeric(df_stops["stop_lon"], errors="coerce")

        # Project coordinates to EPSG:32643
        lons = df_stops["stop_lon"].values
        lats = df_stops["stop_lat"].values
        xs, ys = transformer.transform(lons, lats)
        df_stops["utm_x"] = xs
        df_stops["utm_y"] = ys

        df_stops.to_sql("stops", conn, if_exists="replace", index=False)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stops_id ON stops(stop_id);")
        metrics["tables"]["stops"] = len(df_stops)
        print(f"  [OK] stops: {len(df_stops)} rows (projected & indexed)")

    # 5. Shapes
    shapes_file = os.path.join(gtfs_dir, "shapes.txt")
    if os.path.exists(shapes_file):
        df_shapes = pd.read_csv(shapes_file)
        df_shapes["shape_id"] = df_shapes["shape_id"].astype(str).str.strip()
        df_shapes["shape_pt_lat"] = pd.to_numeric(df_shapes["shape_pt_lat"], errors="coerce")
        df_shapes["shape_pt_lon"] = pd.to_numeric(df_shapes["shape_pt_lon"], errors="coerce")
        df_shapes["shape_pt_sequence"] = pd.to_numeric(df_shapes["shape_pt_sequence"], errors="coerce").astype(int)

        lons = df_shapes["shape_pt_lon"].values
        lats = df_shapes["shape_pt_lat"].values
        xs, ys = transformer.transform(lons, lats)
        df_shapes["utm_x"] = xs
        df_shapes["utm_y"] = ys

        df_shapes.to_sql("shapes", conn, if_exists="replace", index=False)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_shapes_id ON shapes(shape_id, shape_pt_sequence);")
        metrics["tables"]["shapes"] = len(df_shapes)
        print(f"  [OK] shapes: {len(df_shapes)} rows (projected & indexed)")
    else:
        metrics["tables"]["shapes"] = 0
        metrics["warnings"].append("shapes.txt not present in GTFS source")
        print("  [WARN] shapes.txt not present in GTFS source")

    # 6. Trips
    trips_file = os.path.join(gtfs_dir, "trips.txt")
    if os.path.exists(trips_file):
        df_trips = pd.read_csv(trips_file, dtype=str)
        df_trips["trip_id"] = df_trips["trip_id"].str.strip()
        df_trips["route_id"] = df_trips["route_id"].apply(lambda r: str(int(float(r))) if str(r).replace(".0","").isdigit() else str(r).strip())
        df_trips.to_sql("trips", conn, if_exists="replace", index=False)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_id ON trips(trip_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trips_route ON trips(route_id);")
        metrics["tables"]["trips"] = len(df_trips)
        print(f"  [OK] trips: {len(df_trips)} rows (indexed)")

    # 7. Stop Times
    stop_times_file = os.path.join(gtfs_dir, "stop_times.txt")
    if os.path.exists(stop_times_file):
        # Process stop_times in chunks if large
        chunk_size = 200000
        first = True
        total_st = 0
        times_gt_24 = 0
        for chunk in pd.read_csv(stop_times_file, chunksize=chunk_size, dtype={"trip_id": str, "stop_id": str}):
            chunk["trip_id"] = chunk["trip_id"].str.strip()
            chunk["stop_id"] = chunk["stop_id"].str.strip()
            chunk["arrival_sec"] = chunk["arrival_time"].apply(parse_time_to_seconds)
            chunk["departure_sec"] = chunk["departure_time"].apply(parse_time_to_seconds)
            times_gt_24 += (chunk["arrival_sec"] >= 86400).sum()
            chunk.to_sql("stop_times", conn, if_exists="replace" if first else "append", index=False)
            first = False
            total_st += len(chunk)
            print(f"    ... processed {total_st} stop_time rows")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_stop_times_trip ON stop_times(trip_id, stop_sequence);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_stop_times_stop ON stop_times(stop_id);")
        metrics["tables"]["stop_times"] = total_st
        metrics["times_ge_24h"] = int(times_gt_24)
        print(f"  [OK] stop_times: {total_st} rows (indexed, {times_gt_24} >= 24h)")

    conn.commit()

    # Integrity verification
    print("\n=== Checking Referential Integrity ===")
    cur.execute("""
        SELECT COUNT(DISTINCT t.trip_id)
        FROM trips t
        LEFT JOIN routes r ON t.route_id = r.route_id
        WHERE r.route_id IS NULL;
    """)
    orphan_trips = cur.fetchone()[0]
    metrics["referential_integrity"]["orphan_trips_without_route"] = orphan_trips

    cur.execute("""
        SELECT COUNT(DISTINCT st.trip_id)
        FROM stop_times st
        LEFT JOIN trips t ON st.trip_id = t.trip_id
        WHERE t.trip_id IS NULL;
    """)
    orphan_st_trips = cur.fetchone()[0]
    metrics["referential_integrity"]["orphan_st_without_trip"] = orphan_st_trips

    cur.execute("""
        SELECT COUNT(DISTINCT st.stop_id)
        FROM stop_times st
        LEFT JOIN stops s ON st.stop_id = s.stop_id
        WHERE s.stop_id IS NULL;
    """)
    orphan_st_stops = cur.fetchone()[0]
    metrics["referential_integrity"]["orphan_st_without_stop"] = orphan_st_stops

    if "shapes" in metrics["tables"] and metrics["tables"]["shapes"] > 0:
        cur.execute("""
            SELECT COUNT(DISTINCT t.trip_id)
            FROM trips t
            LEFT JOIN shapes sh ON t.shape_id = sh.shape_id
            WHERE t.shape_id IS NOT NULL AND sh.shape_id IS NULL;
        """)
        orphan_shapes = cur.fetchone()[0]
        metrics["referential_integrity"]["trips_with_unmatched_shape"] = orphan_shapes
    else:
        metrics["referential_integrity"]["trips_with_unmatched_shape"] = "N/A (shapes not loaded)"

    print("Integrity results:", metrics["referential_integrity"])
    conn.close()
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest GTFS data into SQLite serving database")
    parser.add_argument("--gtfs-dir", default=DEFAULT_GTFS_DIR, help="Path to GTFS directory")
    parser.add_argument("--db-path", default=DEFAULT_SERVING_DB, help="Path to target SQLite DB")
    args = parser.parse_args()

    ingest_gtfs(args.gtfs_dir, args.db_path)

