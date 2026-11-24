import os
import sys
import time
import requests
from dotenv import dotenv_values
import google.transit.gtfs_realtime_pb2 as gtfs_rt

# Load .env
env = dotenv_values(".env")
api_key = env.get("DELHI_TRANSPORTSTACK_API_KEY", "").strip()

print(f"API Key configured: {bool(api_key)}")
print(f"API Key length: {len(api_key)}")

urls = [
    "https://delhi.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb",
    "https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb"
]

for url in urls:
    print(f"\n========================================================")
    print(f"Testing URL: {url}")
    t0 = time.time()
    try:
        r = requests.get(url, headers={"x-api-key": api_key}, timeout=12)
        dur = round((time.time() - t0) * 1000, 1)
        print(f"Response Time: {dur} ms")
        print(f"HTTP Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('content-type')}")
        print(f"Bytes received: {len(r.content)}")
        
        if r.status_code == 200:
            feed = gtfs_rt.FeedMessage()
            feed.ParseFromString(r.content)
            print("Protobuf Parse: SUCCESS")
            print(f"Header timestamp: {feed.header.timestamp}")
            print(f"GTFS Realtime Version: {feed.header.gtfs_realtime_version}")
            print(f"Total Entities Count: {len(feed.entity)}")
            
            # Analyze entities
            vehicles = []
            routes = set()
            trips = set()
            agencies = set()
            lat_bounds = []
            lon_bounds = []
            timestamps = []
            has_speed_count = 0
            has_bearing_count = 0
            
            for e in feed.entity:
                if not e.HasField("vehicle"):
                    continue
                v = e.vehicle
                v_id = v.vehicle.id if v.HasField("vehicle") and v.vehicle.HasField("id") else e.id
                vehicles.append(v_id)
                
                if v.HasField("trip") and v.trip.HasField("route_id"):
                    routes.add(v.trip.route_id)
                if v.HasField("trip") and v.trip.HasField("trip_id"):
                    trips.add(v.trip.trip_id)
                    
                if v.HasField("position"):
                    lat_bounds.append(v.position.latitude)
                    lon_bounds.append(v.position.longitude)
                    if v.position.HasField("speed"):
                        has_speed_count += 1
                    if v.position.HasField("bearing"):
                        has_bearing_count += 1
                        
                if v.HasField("timestamp"):
                    timestamps.append(v.timestamp)
                    
            print(f"Parsed Vehicles: {len(vehicles)}")
            print(f"Unique Vehicle IDs: {len(set(vehicles))}")
            print(f"Unique Routes: {len(routes)}")
            print(f"Unique Trips: {len(trips)}")
            print(f"Vehicles with Speed: {has_speed_count}")
            print(f"Vehicles with Bearing: {has_bearing_count}")
            
            if timestamps:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                now_ts = int(time.time())
                print(f"Current UTC time: {now_ts}")
                print(f"Min timestamp: {min_ts} ({now_ts - min_ts}s ago)")
                print(f"Max timestamp: {max_ts} ({now_ts - max_ts}s ago)")
                
            if lat_bounds:
                print(f"Lat range: [{min(lat_bounds):.4f}, {max(lat_bounds):.4f}]")
                print(f"Lon range: [{min(lon_bounds):.4f}, {max(lon_bounds):.4f}]")
                
            # Sample first 3 vehicles
            print("\nFirst 3 sample vehicle records:")
            for e in feed.entity[:3]:
                v = e.vehicle
                print(f"  Entity ID: {e.id}")
                print(f"    vehicle.id: {v.vehicle.id if v.HasField('vehicle') else 'N/A'}")
                print(f"    trip.route_id: {v.trip.route_id if v.HasField('trip') else 'N/A'}")
                print(f"    trip.trip_id: {v.trip.trip_id if v.HasField('trip') else 'N/A'}")
                print(f"    position: lat={v.position.latitude}, lon={v.position.longitude}")
                print(f"    timestamp: {v.timestamp}")
        else:
            print(f"Response body snippet: {r.text[:200]}")
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")

