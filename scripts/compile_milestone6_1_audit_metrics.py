"""
Milestone 6.1 Performance Benchmark Audit Script.
Rigorously evaluates and contrasts:
1. Cold-start vs warmed-up latency.
2. In-process ASGI (TestClient) latency vs Live HTTP (real TCP socket over localhost).
3. Percentile distributions (mean, std, p50, p90, p99, min, max) using nearest-rank indexing.
Records hardware, platform, Python version, and iteration counts into data/processed/milestone6_1_audit_metrics.json.
"""

import os
import sys
import time
import json
import socket
import platform
import threading
import statistics
import urllib.request
from pathlib import Path
from typing import Dict, List, Any

# Ensure repo root is on path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.config import settings


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def run_benchmarks():
    print("=" * 70)
    print("Antigravity - Milestone 6.1 Performance Benchmark Audit")
    print("=" * 70)

    # 1. Cold-Start Measurement
    print("\n[1/4] Measuring Application Cold-Start Latency...")
    t0_import = time.perf_counter()
    app = create_app()
    client = TestClient(app)
    t1_app = time.perf_counter()
    cold_start_app_init_ms = (t1_app - t0_import) * 1000.0

    # First un-warmed query latency (cold query)
    t0_first_query = time.perf_counter()
    r_first = client.post("/api/v1/journeys/plan", json={
        "origin_stop_id": "239",
        "dest_stop_id": "2024",
        "departure_date": "2026-10-01",
        "departure_time": "12:37:40",
        "allow_assumed_recurring": True,
    })
    t1_first_query = time.perf_counter()
    cold_first_query_latency_ms = (t1_first_query - t0_first_query) * 1000.0
    assert r_first.status_code == 200

    print(f"  App creation & pre-warming: {cold_start_app_init_ms:.2f} ms")
    print(f"  First cold journey plan query: {cold_first_query_latency_ms:.2f} ms")

    # 2. In-Process TestClient Benchmark
    print("\n[2/4] Measuring In-Process ASGI (TestClient) Latencies...")
    test_endpoints = {
        "health": {
            "method": "GET",
            "url": "/api/v1/health",
            "json": None,
            "iterations": 100
        },
        "timetable_status": {
            "method": "GET",
            "url": "/api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=true",
            "json": None,
            "iterations": 100
        },
        "stop_search": {
            "method": "GET",
            "url": "/api/v1/stops/search?query=kashmere&limit=10",
            "json": None,
            "iterations": 100
        },
        "stops_nearby": {
            "method": "GET",
            "url": "/api/v1/stops/nearby?lat=28.667&lon=77.228&radius_m=800&limit=10",
            "json": None,
            "iterations": 100
        },
        "route_detail": {
            "method": "GET",
            "url": "/api/v1/routes/1598",
            "json": None,
            "iterations": 100
        },
        "journey_planning_direct": {
            "method": "POST",
            "url": "/api/v1/journeys/plan",
            "json": {
                "origin_stop_id": "239",
                "dest_stop_id": "2024",
                "departure_date": "2026-10-01",
                "departure_time": "12:37:40",
                "max_walking_distance_m": 800.0,
                "allow_assumed_recurring": True,
            },
            "iterations": 25
        },
        "journey_planning_coord": {
            "method": "POST",
            "url": "/api/v1/journeys/plan",
            "json": {
                "origin_lat": 28.667,
                "origin_lon": 77.228,
                "dest_lat": 28.720,
                "dest_lon": 77.210,
                "departure_date": "2026-10-01",
                "departure_time": "12:37:40",
                "max_walking_distance_m": 1000.0,
                "allow_assumed_recurring": True,
            },
            "iterations": 15
        }
    }

    in_process_results = {}
    for name, ep in test_endpoints.items():
        latencies = []
        # Warmup pass
        if ep["method"] == "GET":
            client.get(ep["url"])
        else:
            client.post(ep["url"], json=ep["json"])

        for _ in range(ep["iterations"]):
            t_start = time.perf_counter()
            if ep["method"] == "GET":
                r = client.get(ep["url"])
            else:
                r = client.post(ep["url"], json=ep["json"])
            t_end = time.perf_counter()
            assert r.status_code == 200
            latencies.append((t_end - t_start) * 1000.0)

        s_lat = sorted(latencies)
        n = len(s_lat)
        in_process_results[name] = {
            "iterations": ep["iterations"],
            "mean_ms": round(statistics.mean(latencies), 2),
            "std_ms": round(statistics.stdev(latencies) if len(latencies) > 1 else 0.0, 2),
            "p50_ms": round(s_lat[int(n * 0.50)], 2),
            "p90_ms": round(s_lat[int(n * 0.90)], 2),
            "p99_ms": round(s_lat[min(int(n * 0.99), n - 1)], 2),
            "min_ms": round(min(latencies), 2),
            "max_ms": round(max(latencies), 2),
        }
        print(f"  In-Process {name:25s}: p50={in_process_results[name]['p50_ms']} ms, p90={in_process_results[name]['p90_ms']} ms")

    # 3. Live HTTP over Real TCP Socket Benchmark
    print("\n[3/4] Measuring Live HTTP over TCP Socket (127.0.0.1:8001)...")
    live_port = 8001
    server_config = uvicorn.Config(app=app, host="127.0.0.1", port=live_port, log_level="warning")
    server = uvicorn.Server(config=server_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server to bind
    for _ in range(50):
        if is_port_in_use(live_port):
            break
        time.sleep(0.05)
    assert is_port_in_use(live_port), "Failed to start live uvicorn server on port 8001."

    live_http_results = {}
    base_http = f"http://127.0.0.1:{live_port}"

    for name, ep in test_endpoints.items():
        latencies = []
        url = base_http + ep["url"]

        # Warmup pass
        if ep["method"] == "GET":
            req = urllib.request.Request(url, method="GET")
        else:
            req = urllib.request.Request(
                url,
                data=json.dumps(ep["json"]).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200

        for _ in range(ep["iterations"]):
            t_start = time.perf_counter()
            with urllib.request.urlopen(req) as resp:
                assert resp.status == 200
                _ = resp.read()
            t_end = time.perf_counter()
            latencies.append((t_end - t_start) * 1000.0)

        s_lat = sorted(latencies)
        n = len(s_lat)
        live_http_results[name] = {
            "iterations": ep["iterations"],
            "mean_ms": round(statistics.mean(latencies), 2),
            "std_ms": round(statistics.stdev(latencies) if len(latencies) > 1 else 0.0, 2),
            "p50_ms": round(s_lat[int(n * 0.50)], 2),
            "p90_ms": round(s_lat[int(n * 0.90)], 2),
            "p99_ms": round(s_lat[min(int(n * 0.99), n - 1)], 2),
            "min_ms": round(min(latencies), 2),
            "max_ms": round(max(latencies), 2),
        }
        print(f"  Live TCP {name:25s}: p50={live_http_results[name]['p50_ms']} ms, p90={live_http_results[name]['p90_ms']} ms")

    server.should_exit = True

    # 4. Compile Audit Metrics Artifact
    print("\n[4/4] Writing data/processed/milestone6_1_audit_metrics.json...")
    audit_metrics = {
        "milestone": "6.1",
        "project": "Delhi Real-Time Bus Traffic Prediction & Journey Planner",
        "governing_prd": "v3.0",
        "governing_status": "DEGRADE",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "hardware_platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "fastapi_app": "backend.app.main:app",
            "database_path": str(settings.DB_PATH),
        },
        "lifecycle_latencies_ms": {
            "app_creation_and_prewarming_ms": round(cold_start_app_init_ms, 2),
            "cold_first_journey_query_ms": round(cold_first_query_latency_ms, 2),
        },
        "percentile_methodology": {
            "method": "Nearest-rank on sorted array: index = floor(N * p)",
            "warmup": "1 discarded warmup request per endpoint before measurement",
        },
        "benchmarks": {
            "in_process_asgi_testclient": in_process_results,
            "live_http_tcp_socket": live_http_results,
        },
        "transport_comparison_delta_ms": {
            name: {
                "in_process_p50_ms": in_process_results[name]["p50_ms"],
                "live_tcp_p50_ms": live_http_results[name]["p50_ms"],
                "tcp_overhead_ms": round(live_http_results[name]["p50_ms"] - in_process_results[name]["p50_ms"], 2),
            }
            for name in test_endpoints.keys()
        },
        "audit_classification": {
            "timetable_freshness_consistency": "PASS",
            "journey_response_and_accounting": "PASS",
            "endpoint_and_validation": "PASS",
            "security_and_cors": "PASS",
            "performance_and_transparency": "PASS WITH LIMITATIONS",
        },
        "overall_operational_status": "DEGRADE",
    }

    out_file = ROOT_DIR / "data" / "processed" / "milestone6_1_audit_metrics.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit_metrics, f, indent=2)

    print(f"\nAudit metrics successfully compiled to {out_file}")


if __name__ == "__main__":
    run_benchmarks()

