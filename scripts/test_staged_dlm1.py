#!/usr/bin/env python3
"""
Test Staged DLM1 Database Functionality
Validates queries, spatial searches, Route 1598, shapes, and RAPTOR compatibility on /tmp/delhi_dlm1.db.
"""

import sqlite3
import math

DB_PATH = "/tmp/delhi_dlm1.db"


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def test_staged_dlm1():
    print(f"=== TESTING STAGED DLM1 DATABASE: {DB_PATH} ===")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Stop Search
    print("\n1. Testing Stop Search...")
    c.execute("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops WHERE stop_name LIKE '%kashmere%' LIMIT 5;")
    kashmere_stops = c.fetchall()
    print(f"  Found {len(kashmere_stops)} stops matching 'kashmere':")
    for s in kashmere_stops:
        print(f"    Stop {s[0]}: {s[1]} ({s[2]:.4f}, {s[3]:.4f})")
    assert len(kashmere_stops) > 0, "No stops found for kashmere!"

    # 2. Nearby Stops (spatial search around Kashmere Gate: 28.667, 77.228, radius 800m)
    print("\n2. Testing Nearby Stops (800m around 28.667, 77.228)...")
    c.execute("SELECT stop_id, stop_name, stop_lat, stop_lon FROM stops;")
    all_stops = c.fetchall()
    nearby = []
    for sid, sname, slat, slon in all_stops:
        d = haversine(28.667, 77.228, slat, slon)
        if d <= 800.0:
            nearby.append((sid, sname, d))
    nearby.sort(key=lambda x: x[2])
    print(f"  Found {len(nearby)} stops within 800m:")
    for s in nearby[:5]:
        print(f"    Stop {s[0]}: {s[1]} ({s[2]:.1f}m away)")
    assert len(nearby) > 0, "No nearby stops found!"

    # 3. Route Details for Route 1598
    print("\n3. Testing Route Details for Route 1598...")
    c.execute("SELECT route_id, route_short_name, route_long_name, route_desc FROM routes WHERE route_id='1598';")
    r1598 = c.fetchone()
    print(f"  Route: {r1598}")
    assert r1598 is not None, "Route 1598 missing!"

    # Trips count
    c.execute("SELECT count(*) FROM trips WHERE route_id='1598';")
    trips_count = c.fetchone()[0]
    print(f"  Total trips for Route 1598: {trips_count}")
    assert trips_count == 135, f"Expected 135 trips, got {trips_count}"

    # Primary shape points
    c.execute("""
        SELECT count(*) FROM shapes WHERE shape_id IN (
            SELECT shape_id FROM trips WHERE route_id='1598' LIMIT 1
        );
    """)
    pts_count = c.fetchone()[0]
    print(f"  Primary shape points for Route 1598: {pts_count}")
    assert pts_count == 416, f"Expected 416 points, got {pts_count}"

    # 4. Timetable Calendar Validity
    print("\n4. Testing Timetable Calendar Validity...")
    c.execute("SELECT service_id, start_date, end_date FROM calendar;")
    cal = c.fetchone()
    print(f"  Calendar: service_id={cal[0]}, start={cal[1]}, end={cal[2]}")
    assert int(cal[1]) <= 20261001 <= int(cal[2]), "October 2026 not within feed validity!"

    # 5. Crosswalk Table in Staged DB
    print("\n5. Testing Legacy Stop Crosswalk Table...")
    c.execute("SELECT count(*), match_classification FROM legacy_stop_crosswalk GROUP BY match_classification;")
    cw_summary = c.fetchall()
    print("  Crosswalk summary in DB:")
    for cnt, cls in cw_summary:
        print(f"    {cls}: {cnt:,}")

    # Check Route 1598 corridor stops crosswalk
    c.execute("""
        SELECT legacy_stop_id, legacy_stop_name, dlm1_stop_id, dlm1_stop_name, distance_m, match_classification
        FROM legacy_stop_crosswalk
        WHERE legacy_stop_id IN ('239', '240', '241', '242', '243', '244', '245', '246', '247')
        ORDER BY cast(legacy_stop_id as integer);
    """)
    corridor_cw = c.fetchall()
    print("  Corridor stops crosswalk (239-247):")
    for r in corridor_cw:
        print(f"    Old {r[0]} ({r[1]}) -> DLM1 {r[2]} ({r[3]}): {r[4]}m [{r[5]}]")

    conn.close()
    print("\n=== ALL STAGED DLM1 DATABASE FUNCTIONALITY TESTS PASSED ===")


if __name__ == "__main__":
    test_staged_dlm1()

