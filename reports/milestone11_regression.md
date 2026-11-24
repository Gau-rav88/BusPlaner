# Milestone 11: Comprehensive Regression Test Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 11 (Controlled DLM1 Static GTFS Migration)  
**Governing Status:** `DEGRADE`  
**Regression Status:** 100% Passing (0 Regressions)  
**Audit Date:** 2026-11-21  

---

## 1. Executive Summary

Milestone 11 executed a controlled static GTFS migration audit without degrading, altering, or destabilizing the running application. The existing active database (`/tmp/delhi_mdb.db`) was preserved untouched. All schema extensions for shapes and crosswalks were designed to be backwards-compatible with automatic fallbacks.

A full regression sweep was conducted across all backend, frontend, E2E, live-feed, and staged database verification targets. Every test target passed with exit code 0.

---

## 2. Test Execution Matrix

| Test Suite | Execution Command | Test Cases / Checks | Exit Code | Result | Duration |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Staged DLM1 DB Checks** | `python3 scripts/test_staged_dlm1.py` | 5 checks | 0 | **PASS** | 0.8s |
| **Backend Pytest Suite** | `pytest backend/tests -q` | 139 unit & integration tests | 0 | **PASS** | 41.0s |
| **Frontend Component Tests** | `npm test -- --run` (in `frontend/`) | 18 component tests | 0 | **PASS** | 1.7s |
| **Frontend Integration Tests** | `npm test -- --run` (in `frontend/`) | 8 live integration tests | 0 | **PASS** | (included above) |
| **Frontend TypeScript Check** | `npx tsc -b` (in `frontend/`) | Full strict typecheck | 0 | **PASS** | 1.1s |
| **Frontend Production Build** | `npm run build` (in `frontend/`) | Vite production bundling | 0 | **PASS** | 1.59s |
| **Standalone E2E Scenarios** | `python3 scripts/validate_milestone9_e2e.py` | 18 operational scenarios | 0 | **PASS** | 0.4s |
| **GTFS-RT Live Feed Probe** | `python3 scripts/probe_live_feed.py` | Authenticated live protobuf probe | 0 | **PASS** | 2.2s |
| **TOTAL** | — | **188 checks / test cases** | **0** | **ALL PASS** | — |

---

## 3. Detailed Suite Results

### 3.1 Staged DLM1 Database Verification (`scripts/test_staged_dlm1.py`)
- **Stop Search:** Verified stop name matching (found 5 stops for 'kashmere').
- **Nearby Stops:** Discovered 33 stops within 800m of Kashmiri Gate coordinates.
- **Route 1598 Details:** Verified 135 trips and primary shape `shp_3_2423` with 416 vertices.
- **Calendar Validity:** Verified `service_id=1` active from 2025-01-01 to 2040-01-01.
- **Crosswalk Table:** Verified 2,581 high confidence, 3,413 review required, and 348 unmatched stops in `/tmp/delhi_dlm1.db`.
- **Exit Code:** 0

### 3.2 Backend Pytest Suite (139 Tests)
- **Covered Modules:** RAPTOR routing engine, M0 historical baseline predictor, Level 1–4 prediction hierarchy, timetable freshness and user consent enforcement, security input sanitization, error envelopes, and live GTFS-RT protobuf ingestion.
- **Summary:** 139 passed, 0 failed, 6 deprecation warnings.
- **Exit Code:** 0

### 3.3 Frontend Vitest Suite (26 Tests)
- **Component Tests (18):** Header and alerts, journey planning form, result card formatting, prediction source badges, geometry disclaimers.
- **Live Integration Tests (8):** Unmocked live requests to `/health`, `/timetable/status`, `/timetable/consent`, `/journey/plan`, `/routes/1598`, `/stops/search`, `/stops/nearby`, `/live/status`.
- **Summary:** 26 passed, 0 failed across 6 test files.
- **Exit Code:** 0

### 3.4 Frontend TypeScript & Vite Production Build
- `npx tsc -b`: Verified strict zero-error compilation with newly added `has_shape_geometry` and `shape_coordinates` fields.
- `vite build`: Transformed 1,624 modules, outputting optimized production bundle in 1.59s:
  - `dist/index.html` (1.20 kB)
  - `dist/assets/index-CzOOi7N8.css` (26.92 kB)
  - `dist/assets/index-CaQsNbKH.js` (356.89 kB)
- **Exit Code:** 0

### 3.5 Standalone E2E Functional Validation (18 Scenarios)
All 18 end-to-end operational scenarios executed cleanly against the live backend:
- Scenario 1: Health check (`status: ok`, `operational_status: DEGRADE`)
- Scenario 2: Timetable status (`ASSUMED_RECURRING`, `verified_current: false`)
- Scenario 3: Stop search
- Scenario 4: Nearby stops
- Scenario 5: Route detail (Route 1598, 29 ordered stops)
- Scenario 6: Direct journey (Stop 239 -> 247)
- Scenario 7: Transfer journey
- Scenario 8: Clean 200 OK for no route available
- Scenario 9: 422 Unprocessable Content for invalid coordinates
- Scenario 10: Strict 400 rejection when consent=false
- Scenario 11: Assumed recurring consent acceptance
- Scenario 12: Historical North GT Road prediction (`LEVEL_1_DIRECT_OBSERVED`)
- Scenario 13: Scheduled fallback (`LEVEL_4_GTFS_SCHEDULED`)
- Scenario 14: Static fallback (walking at 4.5 km/h)
- Scenario 15: Live feed status
- Scenario 16: Heuristic confidence disclosure
- Scenario 17: Duration accounting consistency ($\Delta = 0.0\text{s}$)
- Scenario 18: Mobile layout & geometry disclaimer
- **Exit Code:** 0

### 3.6 GTFS-RT Live Feed Probe (`scripts/probe_live_feed.py`)
- **Target URL:** `https://dts-backend.transportstack.in/api/dataset/otd/get-file?agency=delhi-buses&category=realtime_gtfs&filename=VehiclePositions.pb`
- **HTTP Status:** 200 OK
- **Content-Type:** `application/octet-stream`
- **Payload Size:** 290,712 bytes
- **Protobuf Parsing:** SUCCESS
- **Entities Parsed:** 2,658 live vehicle positions
- **Unique Routes:** 1,078 routes in snapshot
- **Exit Code:** 0

---

## 4. Operational Status & Governance Confirmation

The application's operational status remains strictly **`DEGRADE`**. 

No cutover or elevation to `NORMAL` was performed during Milestone 11. Staging operations and backwards-compatible route geometry were implemented with complete safety.

