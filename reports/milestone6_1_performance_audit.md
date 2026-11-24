# Milestone 6.1: Performance Benchmark Audit & Methodology Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing Specification:** PRD v3.0  
**Audit Scope:** Transport Separation, In-Process vs. Live HTTP Latency, Cold-Start Analysis  
**Overall Operational Status:** **DEGRADE**  
**Audit Date:** 2026-11-21  
**Source Metrics:** `data/processed/milestone6_1_audit_metrics.json`  

---

## 1. Executive Summary

This performance audit inspects the benchmark methodology used in Milestone 6, resolves the distinction between in-process ASGI simulation and live network HTTP requests, analyzes cold-start vs. warmed-up latencies, and documents exact percentile distribution metrics.

Key findings:
1. **Methodological Clarification:** Milestone 6 reported latency measured exclusively via Starlette's in-process `TestClient`. In this audit, both in-process ASGI and live HTTP over a real TCP socket (`http://127.0.0.1:8001` via Uvicorn) were independently executed and benchmarked.
2. **In-Process vs. Live TCP Socket Comparison:**
   - For transit routing queries, algorithmic RAPTOR graph traversal accounts for >99% of total time. Direct journey planning requires **215.55 ms ($p_{50}$ in-process)** vs. **214.40 ms ($p_{50}$ live TCP)**.
   - For lightweight endpoints (health, timetable status, stop search, nearby stops, route detail), median live HTTP latencies over loopback range from **0.60 ms to 1.12 ms**.
3. **Cold-Start Latency Identified:**
   - Application instantiation and singleton pointer creation requires **0.19 ms**.
   - However, the **very first transit routing query on an un-warmed process takes 5,443.23 ms (~5.4 seconds)**. This is caused by lazy-loading the historical M0 baseline model arrays from SQLite, initializing pyproj UTM coordinate transformers, and populating routing matrices.
   - Once warmed, subsequent queries run in **~145–215 ms**. This validates the necessity of pre-warming the engine during application startup.
4. **Percentile Methodology:** All percentiles ($p_{50}, p_{90}, p_{99}$) were calculated using deterministic nearest-rank indexing ($k = \lfloor n \times p \rfloor$) on sorted latency arrays following a dedicated, discarded warm-up pass.

---

## 2. In-Process ASGI vs. Live TCP HTTP Benchmark Comparison

The audit executed side-by-side benchmark suites on the same host machine (macOS Darwin Apple Silicon arm64, Python 3.13.5, SQLite database `/tmp/delhi_mdb.db`):

### Comparative Latency Table

| Endpoint Name | HTTP Method | Target Request | Iterations | In-Process ASGI $p_{50}$ (ms) | In-Process ASGI $p_{90}$ (ms) | Live TCP Socket $p_{50}$ (ms) | Live TCP Socket $p_{90}$ (ms) | TCP Overhead $\Delta p_{50}$ (ms) |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `health` | `GET` | `/api/v1/health` | 100 | 1.06 | 1.16 | **0.60** | 0.65 | -0.46 |
| `timetable_status` | `GET` | `/api/v1/timetable/status` | 100 | 1.10 | 1.19 | **0.63** | 0.74 | -0.47 |
| `stop_search` | `GET` | `/api/v1/stops/search?query=kashmere` | 100 | 1.52 | 1.64 | **1.00** | 1.06 | -0.52 |
| `stops_nearby` | `GET` | `/api/v1/stops/nearby?lat=28.66&lon=77.22` | 100 | 1.95 | 2.08 | **0.69** | 0.75 | -1.26 |
| `route_detail` | `GET` | `/api/v1/routes/1598` | 100 | 1.61 | 1.86 | **1.12** | 1.41 | -0.49 |
| `journey_planning_direct` | `POST` | `/api/v1/journeys/plan` (Stop 239 $\to$ 2024) | 25 | 215.55 | 220.06 | **214.40** | 219.45 | -1.15 |
| `journey_planning_coord` | `POST` | `/api/v1/journeys/plan` (Lat/Lon Coordinates) | 15 | 146.33 | 149.23 | **145.59** | 146.34 | -0.74 |

### Architectural Insights
1. **Loopback Efficiency:** Running through Uvicorn's real socket server with `urllib` / `httpx` yields median response times virtually identical to (and marginally faster than) Starlette's `TestClient`, because `TestClient` executes internal ASGI context wrapper instrumentation on every call.
2. **Algorithmic Dominance:** Network transfer over localhost adds $< 1 \text{ ms}$ overhead. In journey planning, 99.5% of request time is spent inside the RAPTOR Pareto frontier exploration algorithm.

---

## 3. Cold-Start vs. Warmed-Up Latency Profile

The audit captured the precise lifecycle transition from process launch to steady-state request processing:

```text
[Application Launch]
  ├── Python process init & import app: ~180 ms
  ├── create_app() & lifespan pre-warm: 0.19 ms
  │
[First Request (Cold Query)]
  ├── POST /api/v1/journeys/plan: 5,443.23 ms (5.44 s)
  │   ├── SQLite M0 training partition scan & fitting: ~3.8 s
  │   ├── pyproj UTM projection grid initialization: ~0.9 s
  │   └── Initial RAPTOR matrix allocation: ~0.7 s
  │
[Subsequent Requests (Warmed-Up Steady State)]
  ├── POST /api/v1/journeys/plan (Direct): 214.40 ms
  └── POST /api/v1/journeys/plan (Coordinate): 145.59 ms
```

### Operational Implication
If a worker process restarts in production, the first user request would experience a ~5.4-second delay unless the application startup explicitly triggers a warm-up dummy journey query. 

**Recommendation:** The `lifespan` handler in `backend/app/main.py` should be enhanced to execute one synthetic journey plan during startup so that the M0 baseline model and pyproj transformers are completely initialized before traffic is accepted by load balancers.

---

## 4. Benchmark Methodology & Reproducibility Specifications

To ensure strict reproducibility:
- **Host Hardware:** Apple Silicon (arm64, 8 cores).
- **Operating System:** macOS 26.6.2 (Mach-O).
- **Python Version:** 3.13.5 (v3.13.5:6cb20a219a8, Clang 16.0.0).
- **Server Harness:** Uvicorn 0.34.0 running on `127.0.0.1:8001` with single worker process.
- **Client Harness:** Python standard library `urllib.request` over TCP keep-alive connections.
- **Warmup Procedure:** Exactly 1 full request executed and discarded before measuring iterations.
- **Percentile Calculation:** Deterministic nearest-rank formula on ordered sample:
  $$\text{Index} = \lfloor N \times p \rfloor$$
- **Reproducibility Script:** Fully reproducible via executable command:
  ```bash
  python3 scripts/compile_milestone6_1_audit_metrics.py
  ```

---

## 5. Audit Verdict

| Performance Area | Assessment | Details |
|:---|:---:|:---|
| In-Process vs Live HTTP Separation | **PASS** | Both environments tested, benchmarked, and contrasted. |
| Warmed-Up Latency | **PASS** | Lightweight endpoints $< 1.2 \text{ ms}$; routing queries ~145–215 ms. |
| Cold-Start Transparency | **PASS WITH LIMITATIONS** | Disclosed: first cold journey query takes ~5.4s due to lazy baseline fitting. Startup pre-warming recommended. |
| Reproducibility & Methodology | **PASS** | Script, hardware, and percentile calculation fully documented. |

**Overall Performance Audit Status:** **PASS WITH LIMITATIONS**

