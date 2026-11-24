# Milestone 6: API Validation & Quality Assurance Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing PRD:** v3.0  
**Operational Status:** **DEGRADE**  
**Evaluation Date:** 2026-11-21  
**Associated Metrics File:** `data/processed/milestone6_metrics.json`  
**Test Suite:** `backend/tests/test_milestone6_api.py` (16 tests) + full suite (83 tests total)

---

## 1. Executive Summary

Milestone 6 introduces a production-grade FastAPI REST application exposing the RAPTOR journey planner, GTFS stop/route discovery services, and the 5-tier traffic prediction hierarchy. 

To strictly prevent silent errors, unverified operational claims, and security risks, the API underwent rigorous automated verification against the governing PRD v3.0 requirements. Across **83 total automated tests** (including 16 dedicated Milestone 6 API tests), **100% passed with zero regressions**.

Key validation outcomes:
1. **GTFS Timetable Freshness & Operational Readiness:**
   - Queries targeting expired service dates (e.g., October 2026 vs. feed validity ending 2024-01-01) without explicit opt-in are strictly rejected with `HTTP 400 Bad Request` and `EXPIRED_TIMETABLE`.
   - Demonstration routing on expired schedules requires explicit `allow_assumed_recurring=true` and unequivocally tags responses with `timetable_status="ASSUMED_RECURRING"`, `is_verified_current_service=false`, and `actual_operations_verified=false`.
2. **Boundary & Schema Validation:**
   - Spatial bounds (latitude $\notin [-90, 90]$, longitude $\notin [-180, 180]$) and temporal strings (invalid dates or times) are intercepted at the schema boundary and return `HTTP 422 Unprocessable Content`.
   - Mutually exclusive or empty origin/destination specifications return clear validation error messages.
3. **Exact Accounting Invariant:**
   - Every returned transit journey strictly satisfies the time-conservation identity:
     $$\text{Total Duration} \equiv \text{Access Walk} + \text{Initial Wait} + \sum \text{Ride} + \sum \text{Transfer Walk} + \sum \text{Transfer Wait} + \text{Egress Walk}$$
     with measured numerical discrepancy $\Delta = 0.0000 \text{ s}$.
4. **Prediction Hierarchy & Heuristic Scoring Safeguards:**
   - Experimental Random Forest models remain deactivated by default (`use_experimental_ml=false`).
   - All confidence scores emitted in transit leg predictions are explicitly labeled `confidence_score_type="HEURISTIC"`, preventing false assumptions of calibrated statistical confidence.
5. **Information Leakage Prevention:**
   - Unhandled exceptions and missing database assets return sanitized payloads containing no internal file system paths, stack traces, or environment secrets.

---

## 2. Test Suite Execution & Coverage Matrix

The API test suite was executed against the active SQLite GTFS database (`/tmp/delhi_mdb.db`) and validated across all endpoints.

| Test Function | Target Endpoint | Scope / Scenarios Verified | Status |
|:---|:---|:---|:---:|
| `test_api_health` | `GET /api/v1/health` | Healthcheck, DB availability, `DEGRADE` status | **PASS** |
| `test_api_timetable_status_states` | `GET /api/v1/timetable/status` | `CURRENT_VERIFIED`, `EXPIRED`, `ASSUMED_RECURRING` states | **PASS** |
| `test_api_journey_planning_success` | `POST /api/v1/journeys/plan` | Valid North GT Road routing, duration accounting identity | **PASS** |
| `test_api_journey_planning_invalid_coordinates` | `POST /api/v1/journeys/plan` | Out-of-bounds lat/lon intercepted with 422 | **PASS** |
| `test_api_journey_planning_invalid_dates_and_times` | `POST /api/v1/journeys/plan` | Malformed date (`2026-13-45`) and time (`25:70:99`) return 422 | **PASS** |
| `test_api_journey_planning_expired_strict_mode` | `POST /api/v1/journeys/plan` | Expired timetable rejection (400) when opt-in is false | **PASS** |
| `test_api_journey_planning_missing_timetable` | `POST /api/v1/journeys/plan` | Missing timetable raised as clean 503 error | **PASS** |
| `test_api_journey_planning_no_journey_found` | `POST /api/v1/journeys/plan` | Unreachable destinations return empty journeys list (`count: 0`) | **PASS** |
| `test_api_stop_search` | `GET /api/v1/stops/search` | Substring query ("kashmere"), limit enforcement | **PASS** |
| `test_api_nearby_stops` | `GET /api/v1/stops/nearby` | Spatial KDTree radius lookup, walking duration estimation | **PASS** |
| `test_api_route_detail_and_404` | `GET /api/v1/routes/{id}` | Route 1598 stop sequence verification; missing route returns 404 | **PASS** |
| `test_api_prediction_source_metadata_and_heuristics` | `POST /api/v1/journeys/plan` | Leg metadata tags, `confidence_score_type="HEURISTIC"` | **PASS** |
| `test_api_experimental_ml_gating` | `POST /api/v1/journeys/plan` | `use_experimental_ml` default false; gated ML activation | **PASS** |
| `test_api_error_handling_sanitization` | All endpoints | 404/422/500/503 handlers return sanitized JSON without paths | **PASS** |
| `test_api_coordinate_routing_access_egress` | `POST /api/v1/journeys/plan` | Full lat/lon access and egress walking leg generation | **PASS** |
| `test_api_ranking_strategies` | `POST /api/v1/journeys/plan` | Sorting by earliest arrival, fewest transfers, least walking | **PASS** |

**Aggregate Test Suite Summary:**
- **Milestone 6 API Tests:** 16 passed / 16 total (100%)
- **Milestones 1–5.1.1 Tests:** 67 passed / 67 total (100%)
- **Total Backend Tests:** **83 passed / 83 total (100%)**
- **Execution Time:** ~32.5 seconds

---

## 3. Deep-Dive Validation Results

### 3.1 Timetable Freshness & Opt-In Enforcement
In strict compliance with Milestone 5.1.1 and PRD v3.0 Section 4, the API prevents silent assumptions regarding timetable validity:

1. **Direct Rejection without Opt-In:**
   - Request: `POST /api/v1/journeys/plan` with `departure_date="2026-10-01"` and `allow_assumed_recurring=false`.
   - Result: `HTTP 400 Bad Request`
   ```json
   {
     "error": "EXPIRED_TIMETABLE",
     "detail": "Requested service date 2026-10-01 is outside feed validity (2022-01-01 to 2024-01-01). Demonstrating journeys on expired timetables requires explicit opt-in.",
     "action": "Set allow_assumed_recurring=true in your request to proceed in demonstration mode.",
     "error_code": "EXPIRED_TIMETABLE"
   }
   ```
2. **Opt-In Demonstration Mode:**
   - Request: `POST /api/v1/journeys/plan` with `allow_assumed_recurring=true`.
   - Result: `HTTP 200 OK`
   - Payload explicitly tags:
     - `timetable_status`: `"ASSUMED_RECURRING"`
     - `actual_operations_verified`: `false`
     - `is_verified_current_service`: `false`
     - Prominent warning message attached to the root response.

### 3.2 Journey Time Accounting Conservation Invariant
A core transit algorithm requirement is the conservation of journey duration. To verify this, the test suite and benchmark scripts assert:
$$|T_{\text{total}} - (T_{\text{access}} + T_{\text{init\_wait}} + \sum T_{\text{ride}} + \sum T_{\text{trans\_walk}} + \sum T_{\text{trans\_wait}} + T_{\text{egress}})| \le 10^{-4} \text{ s}$$

- **Validation Check:** Evaluated across all alternatives generated during benchmarking.
- **Maximum Discrepancy Observed:** **`0.0000 s`**
- **Accounting Invariant Satisfied:** **`True`**

### 3.3 Prediction Hierarchy Gating & Heuristic Scoring
The API enforces the 5-tier prediction hierarchy:
1. **Empirical North GT Road Corridor:** Travel times for observed stop pairs (Route 1598) utilize the M0 historical median.
2. **Experimental ML Gating:** Random Forest predictions are only invoked when the request explicitly sets `use_experimental_ml=true`. When `false` (the default), `is_experimental_ml` is `false`.
3. **Confidence Scoring Truth:** All confidence scores emitted in transit legs are accompanied by:
   - `confidence_score_type`: `"HEURISTIC"`
   - Documentation stating that confidence scores represent heuristic ranking metrics, NOT calibrated probabilities.

### 3.4 Error Sanitization & Security Validation
To ensure production readiness:
- All unhandled exceptions are caught by a global exception handler.
- Payloads return structured `{ "error": ..., "detail": ..., "error_code": ... }`.
- No internal filesystem paths (e.g., `/Users/...` or `/tmp/...`), internal tracebacks, or Python object representations are leaked to clients.

---

## 4. Verification Conclusion

Milestone 6 API validation confirms that the FastAPI REST service faithfully and safely wraps the underlying RAPTOR journey planner and prediction infrastructure without altering established scientific baselines or introducing regressions.

The backend is fully operational in local environments under governing status **DEGRADE**.

