import sqlite3
import time
import json
from backend.app.dependencies import get_live_collector
from backend.realtime.gtfs_rt import haversine_distance_m
from backend.realtime.matcher import JourneyBusMatcher

collector = get_live_collector()
collector.refresh_if_expired(force=True)
active_pool = list(collector.active_vehicles.values()) + list(collector.out_of_area_vehicles.values())
now_ts = int(time.time())

matcher = JourneyBusMatcher(db_path="/tmp/delhi_dlm1.db")

print("=" * 80)
print("TESTING MATCHER ON REAL LIVE BUSES AFTER FIX")
print("=" * 80)

# Test Route 1510: Azadpur Terminal (7587) -> Mukarba Chowk (5146)
suitable_1510 = matcher.get_suitable_buses_for_leg("1510", "7587", "5146", active_pool, now_ts=now_ts)
print(f"\n--- ROUTE 1510 (Azadpur Terminal -> Mukarba Chowk) ---")
print(f"Suitable buses returned: {len(suitable_1510)}")
for b in suitable_1510:
    print(f"  * Bus {b['vehicle_id']} (Trip: {b['trip_id']}, Spd: {b['speed_kmh']} km/h):")
    print(f"    Progress: {b['progress_status']}, Dist to Board: {b['distance_to_board_m']}m, Stops away: {b['stops_away']}")
    print(f"    Source: {b['position_source']}, Dead Reckoned: {b['is_dead_reckoned']}, Uncertainty: ±{b['uncertainty_meters']}m")
    print(f"    Guidance: {b['guidance_message']}")

# Test Route 1598: Azadpur Metro (7586) -> Mukarba Chowk (5146)
suitable_1598 = matcher.get_suitable_buses_for_leg("1598", "7586", "5146", active_pool, now_ts=now_ts)
print(f"\n--- ROUTE 1598 (Azadpur Metro -> Mukarba Chowk) ---")
print(f"Suitable buses returned: {len(suitable_1598)}")
for b in suitable_1598:
    print(f"  * Bus {b['vehicle_id']} (Trip: {b['trip_id']}, Spd: {b['speed_kmh']} km/h):")
    print(f"    Progress: {b['progress_status']}, Dist to Board: {b['distance_to_board_m']}m, Stops away: {b['stops_away']}")
    print(f"    Source: {b['position_source']}, Dead Reckoned: {b['is_dead_reckoned']}, Uncertainty: ±{b['uncertainty_meters']}m")
    print(f"    Guidance: {b['guidance_message']}")

# Save before/after comparison
results = {
    "route_1510": {
        "suitable_count": len(suitable_1510),
        "buses": suitable_1510
    },
    "route_1598": {
        "suitable_count": len(suitable_1598),
        "buses": suitable_1598
    }
}
with open("/tmp/live_suitable_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nSaved results to /tmp/live_suitable_results.json")
