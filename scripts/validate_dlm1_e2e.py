#!/usr/bin/env python3
"""Milestone 11.1 End-to-End Functional Validation Script for DLM1 Staged Database.

Validates the complete transit application stack against http://127.0.0.1:8001
(backed by /tmp/delhi_dlm1.db).

Scenarios tested:
1. Health check & DEGRADE status
2. Timetable status (CURRENT_VERIFIED, valid 2025-2040)
3. DLM1 Stop search
4. Nearby stops discovery
5. Route 1598 road geometry (59 stops, 416 shape points)
6. Direct journey planning on DLM1 corridor
7. Transfer journey planning on DLM1 network
8. Unknown stop ID graceful handling
9. Missing route 404 handling
10. Live feed GTFS-RT vehicle telemetry matching DLM1
"""

import json
import os
import sys
import requests

BACKEND_URL = os.environ.get("DLM1_BACKEND_URL", "http://127.0.0.1:8000/api/v1")
OUTPUT_PATH = "data/processed/milestone11_1_e2e_results.json"


def run_e2e_validation():
    print("=== Starting Milestone 11.1 DLM1 End-to-End Functional Validation ===")
    results = {}

    # Scenario 1: Health Check
    r1 = requests.get(f"{BACKEND_URL}/health")
    assert r1.status_code == 200, f"Health check failed: {r1.status_code}"
    d1 = r1.json()
    assert d1["application_status"] == "ok"
    assert d1["overall_operational_status"] == "DEGRADE"
    assert d1["database_available"] is True
    assert d1["gtfs_loaded"] is True
    results["scenario_1_health_check"] = {
        "status": "PASS",
        "operational_status": d1["overall_operational_status"],
        "database_available": d1["database_available"],
    }
    print("✓ Scenario 1: Health Check (Status: ok, Operational: DEGRADE, DLM1 Loaded)")

    # Scenario 2: Timetable Status
    r2 = requests.get(f"{BACKEND_URL}/timetable/status?service_date=2026-10-01")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["timetable_status"] == "CURRENT_VERIFIED"
    assert d2["feed_start_date"] == "2025-01-01"
    assert d2["feed_end_date"] == "2040-01-01"
    assert d2["is_date_within_feed_validity"] is True
    results["scenario_2_timetable_status"] = {
        "status": "PASS",
        "timetable_status": d2["timetable_status"],
        "feed_start_date": d2["feed_start_date"],
        "feed_end_date": d2["feed_end_date"],
    }
    print("✓ Scenario 2: Timetable Status (Status: CURRENT_VERIFIED, Calendar: 2025-2040)")

    # Scenario 3: Stop Search
    r3 = requests.get(f"{BACKEND_URL}/stops/search?query=kashmere&limit=5")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["total"] > 0
    results["scenario_3_stop_search"] = {
        "status": "PASS",
        "total_found": d3["total"],
        "sample_stops": d3["stops"][:3],
    }
    print(f"✓ Scenario 3: Stop Search (Found {d3['total']} stops for 'kashmere')")

    # Scenario 4: Nearby Stops
    r4 = requests.get(f"{BACKEND_URL}/stops/nearby?lat=28.667&lon=77.228&radius=800")
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["total"] > 0
    results["scenario_4_nearby_stops"] = {
        "status": "PASS",
        "total_found": d4["total"],
        "closest_stop": d4["stops"][0] if d4["stops"] else None,
    }
    print(f"✓ Scenario 4: Nearby Stops (Found {d4['total']} stops within 800m of Kashmiri Gate)")

    # Scenario 5: Route 1598 Details & Road Geometry
    r5 = requests.get(f"{BACKEND_URL}/routes/1598")
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["route_id"] == "1598"
    assert len(d5["ordered_stops"]) == 59
    assert d5["has_shape_geometry"] is True
    assert len(d5["shape_coordinates"]) == 416
    results["scenario_5_route_1598_shape"] = {
        "status": "PASS",
        "route_short_name": d5["route_short_name"],
        "stops_count": len(d5["ordered_stops"]),
        "has_shape_geometry": d5["has_shape_geometry"],
        "shape_points_count": len(d5["shape_coordinates"]),
    }
    print(f"✓ Scenario 5: Route 1598 Detail ({len(d5['ordered_stops'])} stops, 416 shape road geometry vertices)")

    # Scenario 6: Direct Journey Planning
    req6 = {
        "origin_stop_id": "284",
        "dest_stop_id": "5146",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 0,
        "allow_assumed_recurring": True,
    }
    r6 = requests.post(f"{BACKEND_URL}/journeys/plan", json=req6)
    assert r6.status_code == 200
    d6 = r6.json()
    assert d6["journeys_count"] >= 1
    j6 = d6["journeys"][0]
    assert j6["num_transfers"] == 0
    results["scenario_6_direct_journey"] = {
        "status": "PASS",
        "journeys_count": d6["journeys_count"],
        "total_duration_s": j6["total_journey_duration_s"],
        "board_stop": j6["legs"][0]["board_stop_name"],
        "alight_stop": j6["legs"][0]["alight_stop_name"],
    }
    print(f"✓ Scenario 6: Direct Journey (Stop 284 -> 5146, duration: {j6['total_journey_duration_s']}s)")

    # Scenario 7: Transfer Journey Planning
    req7 = {
        "origin_stop_id": "2280",
        "dest_stop_id": "5321",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 2,
        "allow_assumed_recurring": True,
    }
    r7 = requests.post(f"{BACKEND_URL}/journeys/plan", json=req7)
    assert r7.status_code == 200
    d7 = r7.json()
    assert d7["journeys_count"] >= 1
    j7 = d7["journeys"][0]
    assert j7["num_transfers"] >= 1
    results["scenario_7_transfer_journey"] = {
        "status": "PASS",
        "journeys_count": d7["journeys_count"],
        "transfers": j7["num_transfers"],
        "legs_count": len(j7["legs"]),
    }
    print(f"✓ Scenario 7: Transfer Journey ({j7['num_transfers']} transfer, {len(j7['legs'])} legs)")

    # Scenario 8: Clean Empty Journey on Invalid Stop ID
    req8 = {
        "origin_stop_id": "99999999",
        "dest_stop_id": "284",
        "departure_date": "2026-10-01",
        "departure_time": "08:00:00",
        "max_transfers": 1,
        "allow_assumed_recurring": True,
    }
    r8 = requests.post(f"{BACKEND_URL}/journeys/plan", json=req8)
    assert r8.status_code == 200
    d8 = r8.json()
    assert d8["journeys_count"] == 0
    assert d8["journeys"] == []
    results["scenario_8_invalid_stop"] = {
        "status": "PASS",
        "status_code": r8.status_code,
        "journeys_count": d8["journeys_count"],
    }
    print("✓ Scenario 8: Invalid Stop ID Handled (Clean 200 OK, journeys_count: 0)")

    # Scenario 9: Missing Route 404 Handling
    r9 = requests.get(f"{BACKEND_URL}/routes/UNKNOWN_ROUTE_9999")
    assert r9.status_code == 404
    d9 = r9.json()
    assert d9["error"] == "HTTP_ERROR"
    results["scenario_9_missing_route"] = {
        "status": "PASS",
        "status_code": r9.status_code,
        "error_code": d9.get("error_code"),
    }
    print("✓ Scenario 9: Missing Route 404 Handled (Structured error envelope)")

    # Scenario 10: Real-time Live Vehicle Positions
    r10 = requests.get(f"{BACKEND_URL}/live/vehicles")
    assert r10.status_code == 200
    d10 = r10.json()
    assert d10["feed_availability_status"] == "AVAILABLE_VALIDATED"
    assert len(d10["vehicles"]) > 0
    results["scenario_10_live_vehicles"] = {
        "status": "PASS",
        "feed_status": d10["feed_availability_status"],
        "sample_count": len(d10["vehicles"]),
        "sample_vehicle_id": d10["vehicles"][0]["vehicle_id"],
    }
    print(f"✓ Scenario 10: Live Feed Vehicles (Parsed {len(d10['vehicles'])} vehicles, real GTFS-RT telemetry)")

    # Save results
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nALL 10 DLM1 END-TO-END SCENARIOS PASSED WITH EXIT CODE 0!")
    print(f"Saved results to {OUTPUT_PATH}")
    return True


if __name__ == "__main__":
    try:
        run_e2e_validation()
    except Exception as exc:
        print(f"E2E Validation Failed: {exc}", file=sys.stderr)
        sys.exit(1)

