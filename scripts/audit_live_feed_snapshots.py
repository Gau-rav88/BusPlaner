#!/usr/bin/env python3
"""Milestone 11.4: Multi-Snapshot Authenticated Live GTFS-RT Audit Script.

Captures 3 independent snapshots from the Delhi Transport Stack endpoint,
evaluates entity counts, bounding box validity, timestamp freshness, and
computes route matching against the primary DLM1 database (/tmp/delhi_dlm1.db).

Zero credentials or secret keys are printed or logged.
"""

import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
import requests
import google.transit.gtfs_realtime_pb2 as gtfs_rt

DLM1_DB_PATH = "/tmp/delhi_dlm1.db"

# Load settings from .env without printing secrets
API_KEY = os.environ.get("DELHI_TRANSPORTSTACK_API_KEY", "")
ENDPOINT_URL = os.environ.get(
    "DELHI_GTFS_RT_URL",
    "https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb",
)

if not API_KEY and os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if line.startswith("DELHI_TRANSPORTSTACK_API_KEY="):
                API_KEY = line.strip().split("=", 1)[1]
            elif line.startswith("DELHI_GTFS_RT_URL="):
                ENDPOINT_URL = line.strip().split("=", 1)[1]

assert API_KEY, "ERROR: DELHI_TRANSPORTSTACK_API_KEY is not configured!"

# Delhi bbox
LAT_MIN, LAT_MAX = 28.30, 28.95
LON_MIN, LON_MAX = 76.80, 77.45
STALENESS_THRESHOLD_S = 900


def get_dlm1_known_routes():
    conn = sqlite3.connect(DLM1_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT route_id FROM routes;")
    routes = {str(row[0]) for row in cur.fetchall()}
    conn.close()
    return routes


def capture_snapshot(snapshot_index: int, known_routes: set):
    headers = {
        "x-api-key": API_KEY.strip(),
        "Accept": "application/octet-stream, application/x-protobuf, */*",
    }
    t0 = time.time()
    resp = requests.get(ENDPOINT_URL, headers=headers, timeout=12.0)
    latency_s = time.time() - t0

    assert resp.status_code == 200, f"Snapshot {snapshot_index} failed with HTTP {resp.status_code}"
    raw_bytes = resp.content
    byte_size = len(raw_bytes)

    # Parse protobuf
    feed = gtfs_rt.FeedMessage()
    feed.ParseFromString(raw_bytes)

    raw_entity_count = len(feed.entity)
    now_ts = int(time.time())

    valid_vehicles = 0
    rejected_positions = 0
    stale_vehicles = 0
    fresh_vehicles = 0

    unique_routes = set()
    timestamps = []

    for entity in feed.entity:
        if not entity.HasField("vehicle"):
            continue
        v = entity.vehicle
        pos = v.position if v.HasField("position") else None
        if not pos:
            rejected_positions += 1
            continue

        lat = pos.latitude
        lon = pos.longitude
        ts = int(v.timestamp) if v.timestamp else 0

        # Validate bbox
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            rejected_positions += 1
            continue

        valid_vehicles += 1
        if ts > 0:
            timestamps.append(ts)
            age = now_ts - ts
            if age > STALENESS_THRESHOLD_S or age < -300:
                stale_vehicles += 1
            else:
                fresh_vehicles += 1

        route_id = None
        if v.HasField("trip") and v.trip.route_id:
            route_id = str(v.trip.route_id).strip()
        elif v.HasField("vehicle") and getattr(v, "route_id", None):
            route_id = str(v.route_id).strip()

        if route_id:
            unique_routes.add(route_id)

    # Check route matching against DLM1
    matched_routes = unique_routes.intersection(known_routes)
    unmatched_routes = unique_routes - known_routes
    match_pct = (len(matched_routes) / len(unique_routes) * 100.0) if unique_routes else 0.0

    min_ts = min(timestamps) if timestamps else 0
    max_ts = max(timestamps) if timestamps else 0
    now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()

    stats = {
        "snapshot_index": snapshot_index,
        "timestamp_utc": now_dt,
        "latency_seconds": round(latency_s, 3),
        "payload_bytes": byte_size,
        "raw_entities": raw_entity_count,
        "valid_vehicles": valid_vehicles,
        "rejected_positions": rejected_positions,
        "fresh_vehicles": fresh_vehicles,
        "stale_vehicles": stale_vehicles,
        "unique_active_routes_count": len(unique_routes),
        "dlm1_matched_routes_count": len(matched_routes),
        "dlm1_unmatched_routes_count": len(unmatched_routes),
        "route_match_percentage": round(match_pct, 2),
        "min_timestamp_age_s": now_ts - max_ts if max_ts else 0,
        "max_timestamp_age_s": now_ts - min_ts if min_ts else 0,
        "unmatched_sample": sorted(list(unmatched_routes))[:5],
    }

    print(f"Snapshot {snapshot_index}: {valid_vehicles} valid buses ({fresh_vehicles} fresh), "
          f"{len(unique_routes)} active routes -> {len(matched_routes)} matched in DLM1 ({match_pct:.2f}%), "
          f"latency={latency_s:.2f}s, size={byte_size} bytes")
    return stats


def main():
    print("=" * 70)
    print("MILESTONE 11.4: 3-SNAPSHOT AUTHENTICATED GTFS-RT AUDIT")
    print(f"Endpoint: {ENDPOINT_URL}")
    print(f"Primary DLM1 Database: {DLM1_DB_PATH}")
    print("=" * 70)

    known_routes = get_dlm1_known_routes()
    print(f"Loaded {len(known_routes)} routes from DLM1 routes table.\n")

    snapshots = []
    for i in range(1, 4):
        stats = capture_snapshot(i, known_routes)
        snapshots.append(stats)
        if i < 3:
            time.sleep(6)  # Pause between snapshots

    out_file = "data/processed/milestone11_4_live_snapshots.json"
    import json
    with open(out_file, "w") as f:
        json.dump(snapshots, f, indent=2)
    print(f"\nAll 3 snapshots captured and saved to {out_file}")


if __name__ == "__main__":
    main()

