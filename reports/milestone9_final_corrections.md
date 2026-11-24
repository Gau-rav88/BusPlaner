# Milestone 9 — Final Corrections and Sign-off Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Final Operational Status:** **`DEGRADE`** *(Strictly Maintained)*  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Objective

This report provides the final, unambiguous test accounting and reconciliation for Milestone 9:
1. **Test Accounting Distinction:** Strictly separates **distinct test definitions** (176 separately defined tests/scenarios across backend, frontend, and E2E), **total executions** (176 live executions), and **functional overlap** (11 E2E scenarios that verify behavior also covered in frontend integration tests).
2. **Geographic & Data Composition Corrections:** Strictly qualifies the 136 ground-truth segment traversals across all 3 routes (Route 1598: 124, Route 1445: 11, Route 1657: 1), avoiding monolithic descriptions.
3. **Fresh Setup Reproducibility & Asset Inventory:** Distinguishes repository-bundled assets from local host files (e.g. `/tmp/delhi_mdb.db`), providing the exact MobilityData GTFS download URL (`mdb-1262`), generation commands, storage requirements, and clean-clone boundaries.
4. **Traceability Metric Nomenclature:** Redefines the "90.6%" figure to *"Requirements with at Least Partial Implementation (29/32)"*, displaying implemented (24), partially implemented (5), blocked (1), and not implemented (2) counts separately.
5. **Separate Final Command Verification:** Documents the isolated execution of all test suites, builds, and live HTTP scenarios with exact exit codes.

---

## 2. Test Accounting: Definitions, Executions & Functional Overlap

To eliminate ambiguity, test reporting distinguishes three separate concepts:
- **Test Definitions:** Separately authored test functions or standalone scenario code blocks in the codebase.
- **Total Executions:** The actual number of tests and scenarios invoked during verification.
- **Functional Overlap:** Distinct tests in different suites that verify overlapping runtime behavior or endpoints.

### 2.1 Distinct Test Definitions (176 Total Definitions)
The project codebase defines exactly **176 distinct test definitions and scenario blocks**:

1. **Backend Pytest Test Definitions:** **132 tests** across 12 test files in `backend/tests/`:
   - `test_milestone1_ingestion.py` (5 tests)
   - `test_milestone2_shape_matching.py` (6 tests)
   - `test_milestone2_stop_crossings.py` (5 tests)
   - `test_milestone3_baseline.py` (8 tests)
   - `test_milestone3_1_1_audit.py` (9 tests)
   - `test_milestone4_validation.py` (10 tests)
   - `test_milestone5_raptor.py` (22 tests)
   - `test_milestone5_routing.py` (12 tests)
   - `test_milestone5_footpaths.py` (6 tests)
   - `test_milestone6_api.py` (20 tests)
   - `test_milestone6_1_audit.py` (18 tests)
   - `test_milestone9_traceability.py` (11 tests)
2. **Frontend Vitest Component Test Definitions:** **18 tests** across 5 test files in `frontend/src/test/`:
   - `apiService.test.ts` (3 tests)
   - `formatters.test.ts` (4 tests)
   - `JourneyResults.test.tsx` (4 tests)
   - `PlannerForm.test.tsx` (5 tests)
   - `HeaderAndAlerts.test.tsx` (2 tests)
3. **Frontend Vitest Live Integration Test Definitions:** **8 tests** in `frontend/src/test/liveIntegration.test.ts`:
   - Genuine unmocked HTTP integration tests executed against `http://127.0.0.1:8000`.
4. **Standalone Operational E2E Scenario Definitions:** **18 scenario blocks** in `scripts/validate_milestone9_e2e.py`:
   - Standalone operational scenario functions testing full-stack HTTP endpoints, error envelopes, and data invariants.

$$\text{Total Distinct Test Definitions} = 132 + 18 + 8 + 18 = \mathbf{176}\text{ test definitions}$$

### 2.2 Total Test Executions (176 Executions)
Every test definition is executed once in a complete verification pass:
- Backend pytest suite: **132 executions** (132 passed, 0 failed, 6 warnings in 35.60s)
- Frontend vitest component suite: **18 executions** (18 passed, 0 failed in 1.29s)
- Frontend vitest live integration suite: **8 executions** (8 passed, 0 failed in 1.29s)
- Standalone E2E validation script: **18 executions** (18 passed, 0 failed in 0.85s)

$$\text{Total Test Executions} = 132 + 18 + 8 + 18 = \mathbf{176}\text{ executions (100\% pass rate)}$$

### 2.3 Functional Overlap Analysis (11 Overlapping Scenarios)
Rather than subtracting scenario definitions, functional overlaps between `validate_milestone9_e2e.py` and `liveIntegration.test.ts` are documented separately based on actual code assertions:

#### Group A: Core REST Endpoint Overlaps (Scenarios 1–6 and 15 — 7 Scenarios)
1. **Scenario 1 (`1_health_check`):** Calls `GET /health` $\leftrightarrow$ `liveIntegration.test.ts` Test 1 (`verifies live backend /health status and DEGRADE operational state`). Both assert `application_status: "ok"`, `DEGRADE`, and `AUTH_REQUIRED`.
2. **Scenario 2 (`2_timetable_status`):** Calls `GET /timetable/status` $\leftrightarrow$ `liveIntegration.test.ts` Test 2 (`verifies live /timetable/status with expired GTFS calendar disclosure`). Both assert `ASSUMED_RECURRING` and `feed_end_date: "2024-01-01"`.
3. **Scenario 3 (`3_stop_search`):** Calls `GET /stops/search?query=kashmere` $\leftrightarrow$ `liveIntegration.test.ts` Test 6 (`verifies live /stops/search finds stops with coordinates`). Both verify substring stop search results.
4. **Scenario 4 (`4_nearby_stops`):** Calls `GET /stops/nearby` $\leftrightarrow$ `liveIntegration.test.ts` Test 7 (`verifies live /stops/nearby discovers spatial stops within 800m`). Both verify spatial Haversine search results.
5. **Scenario 5 (`5_route_detail`):** Calls `GET /routes/1598` $\leftrightarrow$ `liveIntegration.test.ts` Test 5 (`verifies live /routes/1598 returns all 29 ordered stops for geometry mapping`). Both verify Route 1598 ordered stop sequence.
6. **Scenario 6 (`6_direct_journey`):** Calls `POST /journeys/plan` Stop 239 $\to$ 247 $\leftrightarrow$ `liveIntegration.test.ts` Test 4 (`verifies live North GT Road journey planning (Route 1598, Stop 239 -> 247)`). Both execute direct transit routing on Route 1598.
7. **Scenario 15 (`15_live_feed_auth_required`):** Calls `GET /live/status` $\leftrightarrow$ `liveIntegration.test.ts` Test 8 (`verifies live /live/status reports AUTH_REQUIRED and feed_enabled=false`). Both verify live collector disabled state on missing credentials.

#### Group B: Timetable Expiration Rejection Overlap (Scenario 10 — 1 Scenario)
8. **Scenario 10 (`10_expired_timetable_rejected`):** Calls `POST /journeys/plan` with `allow_assumed_recurring=false` asserting HTTP 400 with `error="EXPIRED_TIMETABLE"` $\leftrightarrow$ `liveIntegration.test.ts` Test 3 (`verifies strict 400 EXPIRED_TIMETABLE rejection when allow_assumed_recurring=false`). Both verify strict rejection of expired schedules without user consent.

#### Group C: Granular Journey Contract Overlaps (Scenarios 12, 16, 17 — 3 Scenarios)
These 3 standalone E2E scenarios verify individual fields of the same direct journey response that are also asserted inside Test 4 of `liveIntegration.test.ts`:
9. **Scenario 12 (`12_level_1_prediction`):** Asserts `prediction_tier == "LEVEL_1_DIRECT_OBSERVED"` $\leftrightarrow$ `liveIntegration.test.ts` Test 4 asserts `transitLeg.prediction_tier === 'LEVEL_1_DIRECT_OBSERVED'`.
10. **Scenario 16 (`16_confidence_disclosure`):** Asserts `confidence_score_type == "HEURISTIC"` $\leftrightarrow$ `liveIntegration.test.ts` Test 4 asserts `journey.confidence_score_type === 'HEURISTIC'`.
11. **Scenario 17 (`17_duration_accounting`):** Asserts `is_valid_identity is True` and `discrepancy_s < 0.1` $\leftrightarrow$ `liveIntegration.test.ts` Test 4 asserts `journey.accounting.is_valid_identity === true`.

$$\text{Total Functional Overlaps} = 7\text{ (Group A)} + 1\text{ (Group B)} + 3\text{ (Group C)} = \mathbf{11}\text{ functional overlaps}$$

#### Unique Functional Coverage in Standalone E2E Scenarios (7 Scenarios)
The remaining 7 scenarios in `scripts/validate_milestone9_e2e.py` introduce unique behavioral verifications not tested in `liveIntegration.test.ts`:
- **Scenario 7 (`7_transfer_journey`):** Multi-stop transfer routing (Stop 239 $\to$ 2024, `max_transfers=2`).
- **Scenario 8 (`8_no_route_journey`):** Isolated unreachable coordinates / early morning departure (`03:00:00`) returning clean 200 OK with `journeys_count: 0`.
- **Scenario 9 (`9_invalid_coordinates`):** Coordinate bounds validation (`999.0, 999.0`) returning strict HTTP 422 Unprocessable Content.
- **Scenario 11 (`11_assumed_recurring_accepted`):** Verification of explicit stale timetable warning payloads under demonstration consent.
- **Scenario 13 (`13_scheduled_fallback`):** Unobserved corridor scheduled running time fallback (`LEVEL_4_GTFS_SCHEDULED`).
- **Scenario 14 (`14_static_fallback`):** Walking leg static fallback (`LEVEL_5_STATIC_FALLBACK` at 4.5 km/h).
- **Scenario 18 (`18_mobile_and_map_disclaimer`):** Mobile viewport layout ($375 \times 812$, zero overflow) and stop-to-stop straight-line geometry disclaimer.

---

## 3. Geographic & Data Description Corrections

All descriptions across documentation and reports are corrected to state the exact multi-route composition:
- **Total Ground-Truth Observations:** Exactly **136** consecutive stop-to-stop traversals.
- **Observations by Route:**
  - **Route 1598 (129AUP):** 124 observations (91.18%) across 20 distinct physical stop pairs along North GT Road.
  - **Route 1445 (126AUP):** 11 observations (8.09%) across 5 distinct physical stop pairs (all 5 co-running and shared with Route 1598 along North GT Road).
  - **Route 1657 (103STLUP):** 1 observation (0.74%) across 1 skip-stop physical stop pair (`242 -> 1245`).
- **Stop Pairs:** Exactly **26 route-specific segment pairs** mapping onto **21 distinct physical stop pairs**.
- **Service Dates:** Exactly **5 pilot dates** (`2026-10-01`, `2026-10-02`, `2026-10-03`, `2026-10-04`, `2026-10-07`).
- **Unique Vehicles:** Exactly **31 unique vehicles** (25 on 1598, 5 on 1445, 1 on 1657; zero cross-route overlap).

> [!IMPORTANT]
> The dataset is **never described as solely Route 1598 or solely North GT Road**. While Routes 1598 and 1445 run along North GT Road, Route 1657 contains a skip-stop traversal (`242 -> 1245`). All documentation explicitly cites the 124 / 11 / 1 distribution.

---

## 4. Fresh Setup Reproducibility & Asset Inventory

The repository and local host environments are partitioned transparently:

### 4.1 Included Directly in Repository
- `data/processed/stop_crossings/service_date=*/observed_segments.parquet`: All 136 ground-truth segment traversals across the 5 pilot dates.
- `data/processed/historical_time_profiles.json`: All 720 pre-computed stop-pair, route, and corridor hourly profiles.
- `data/raw/gtfs/`: Sample DTC static GTFS files (agency, routes, trips, stops, stop_times, calendar).
- `data/serving/delhi_bus.db`: 94 KB sample SQLite serving database.

### 4.2 Local Host / External Data Assets
- **Full GTFS Serving Database (`/tmp/delhi_mdb.db`, 268 MB):**
  - **Authentic Upstream Source URL:** Mobility Database open catalog feed `mdb-1262` (Delhi Transport Corporation):
    - Primary Download URL: `https://files.mobilitydatabase.org/mdb-1262/mdb-1262-202506170152/mdb-1262-202506170152.zip` (19.8 MB ZIP / 120.3 MB uncompressed text).
    - Archive Mirror: `https://files.mobilitydatabase.org/mdb-1262/mdb-1262-202406071502/mdb-1262-202406071502.zip`
  - **Exact Download & Extraction Commands:**
    ```bash
    # 1. Download official MobilityData mdb-1262 GTFS archive (19.8 MB)
    curl -s -L "https://files.mobilitydatabase.org/mdb-1262/mdb-1262-202506170152/mdb-1262-202506170152.zip" -o /tmp/full_delhi_gtfs.zip

    # 2. Extract GTFS text files into /tmp/mdb_gtfs
    mkdir -p /tmp/mdb_gtfs
    unzip -q /tmp/full_delhi_gtfs.zip -d /tmp/mdb_gtfs

    # 3. Ingest into SQLite database (/tmp/delhi_mdb.db, 268 MB)
    python3 scripts/ingest_gtfs.py --gtfs-dir /tmp/mdb_gtfs --db-path /tmp/delhi_mdb.db
    ```
  - **Storage Requirement:** 268 MB disk; ~500 MB RAM for in-memory RAPTOR routing graph (2,964 routes, 78,515 trips, 3,276,092 stop-times).
- **Raw October GPS Archive (`/tmp/delhi_archive_header.7z`, 15 GB):**
  - **Source:** Cloudflare R2 backup archive containing 31 daily SQLite files (`bus_movements_2026_10_01.db` to `bus_movements_2026_10_31.db`).
  - **Usage Note:** Pre-extracted Parquet files for the 5-date pilot subset are already checked into `data/processed/`, so an evaluator running the journey planner and tests does **NOT** need to download or extract the 15 GB archive.

### 4.3 Environment Variables
- `DELHI_TRANSPORTSTACK_API_KEY`: Kept blank in `.env.example`. Live collector defaults to `AUTH_REQUIRED`.
- `LIVE_FEED_ENABLED`: Defaults to `false`.
- `LIVE_FEED_STALENESS_SECONDS`: Defaults to `900` (configurable down to 600s PRD nominal).
- `DB_PATH`: Defaults to `/tmp/delhi_mdb.db`.

---

## 5. Requirements Traceability Metric Nomenclature

The compliance metric is explicitly defined and broken down across all 32 audited PRD requirements:

$$\text{Requirements with at Least Partial Implementation} = \frac{24\text{ (Implemented)} + 5\text{ (Partially Implemented)}}{32\text{ (Total)}} = \frac{29}{32} = \mathbf{90.6\%}$$

### Separate Classification Counts
- **`IMPLEMENTED` (Full Implementation):** **24 / 32 (75.0%)**
- **`PARTIALLY_IMPLEMENTED` (Pilot Scope / Demo Mode):** **5 / 32 (15.6%)**
- **`BLOCKED` (External API Key Required):** **1 / 32 (3.1%)**
- **`NOT_IMPLEMENTED` (Out of Scope / Absent in Feed):** **2 / 32 (6.3%)**

All disclosed limitations (DEGRADE status, expired GTFS calendar, straight-line map lines, heuristic confidence, disabled Random Forest) remain intact.

---

## 6. Final Isolated Command Verification

Each command was executed separately and recorded:

```text
========================================================================================================
#  Target / Scope             Exact Command Line Invocations                Exit Code  Tests / Scenarios
========================================================================================================
1  Backend Pytest Suite       pytest -q backend/tests/                             0   132 passed (33.96s)
2  Frontend Vitest Suite      cd frontend && npm test                              0   26 passed (1.26s)
3  Frontend TypeCheck/Build   cd frontend && npx tsc -b && npm run build           0   Built in 1.40s
4  Operational E2E Scenarios  python3 scripts/validate_milestone9_e2e.py           0   18/18 passed (0.85s)
========================================================================================================
TOTAL DISTINCT TEST DEFINITIONS: 176 / 176 PASSED (100% PASS RATE)
TOTAL TEST & SCENARIO EXECUTIONS: 176 EXECUTIONS PASSED (100% PASS RATE)
FUNCTIONAL OVERLAPS IDENTIFIED: 11 SCENARIOS (VERIFIED SEPARATELY)
========================================================================================================
```

- **Live Backend Confirmation:** Confirmed that `validate_milestone9_e2e.py` executed live HTTP requests against `http://127.0.0.1:8000` (TCP connect ~1ms, zero mock substitution).
- **Live Feed Gate Confirmation:** Confirmed that `GET /api/v1/live/status` returned `feed_availability_status: "AUTH_REQUIRED"` and `feed_enabled: false` with zero network requests dispatched.

---

## 7. Sign-off Declaration

All final reporting issues are resolved consistently across `README.md`, `reports/milestone9_requirements_traceability.md`, `reports/milestone9_final_assessment.md`, and `data/processed/milestone9_metrics.json`.

Milestone 9 is signed off under governing operational status **`DEGRADE`**.

