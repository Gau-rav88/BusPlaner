# Milestone 8: Operational Validation & Resilience Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Phase:** Milestone 8 — Comprehensive Operational & Failure Mode Testing  
**Operational Status:** **DEGRADE**  
**Date:** November 2026  

---

## 1. Executive Summary

Milestone 8 conducted exhaustive operational validation across the newly implemented live feed client (`backend/realtime/gtfs_rt.py`), historical time-profile engine (`backend/analytics/time_profiles.py`), and FastAPI REST endpoints (`/api/v1/live/status`, `/api/v1/health`).

All 14 test scenarios specified in PRD v3.0 Milestone 8 were formally validated via automated test suites in `backend/tests/test_milestone8_*.py` and `frontend/src/test/`. Every test passed with 100% compliance.

---

## 2. Operational & Failure Mode Validation Matrix

| Test Scenario | Module / Trigger | Expected Behavior | Actual Observed Outcome | Verdict |
| :--- | :--- | :--- | :--- | :---: |
| **1. Missing API Key** | `LiveFeedCollector(api_key="")` | Immediate classification as `AUTH_REQUIRED`; no network calls dispatched; informative warning returned. | Returned `FeedAvailabilityStatus.AUTH_REQUIRED`, failure counter incremented, auth_configured=False. | **PASS** |
| **2. Invalid API Key** | `LiveFeedCollector(api_key="bad")` with mock HTTP 401 | Intercepts 401; classifies as `AUTH_REQUIRED`; increments consecutive failures. | Returned `FeedAvailabilityStatus.AUTH_REQUIRED`; message indicates HTTP 401. | **PASS** |
| **3. Feed Timeout** | Mock `requests.exceptions.Timeout` | Catches timeout; classifies as `UNAVAILABLE`; suppresses unhandled exceptions. | Returned `FeedAvailabilityStatus.UNAVAILABLE`; consecutive failures incremented. | **PASS** |
| **4. Malformed Protobuf / HTML** | Mock response containing HTML `<html>...</html>` | Detects non-protobuf payload; classifies as `INVALID_DATA`. | Returned `FeedAvailabilityStatus.INVALID_DATA`; failure counter incremented. | **PASS** |
| **5. Empty Feed (0 Entities)** | Protobuf with 0 vehicle entities | Classifies as `AVAILABLE_PARTIAL`; logs warning; preserves telemetry. | Returned `FeedAvailabilityStatus.AVAILABLE_PARTIAL`; message indicates 0 entities. | **PASS** |
| **6. Stale Vehicle Updates** | Vehicle ping with age $> 900$s | Flags update as stale; adds warning to validation notes. | `is_fresh: False`; validation note confirms age $> 900$s. | **PASS** |
| **7. Vehicle Deduplication** | Multiple updates for same `vehicle_id` in single batch | In-memory `active_vehicles` dictionary deduplicates by ID. | Exactly 1 entry retained per vehicle ID; latest timestamp preserved. | **PASS** |
| **8. Static GTFS Match Check** | Vehicle reporting route not in static GTFS | Flags vehicle with `is_matched_to_gtfs: False`. | Matched routes flagged `True`; unknown routes flagged `False`. | **PASS** |
| **9. Geographic Bounds Check** | Coordinates outside Delhi (e.g. Mumbai) | Rejects out-of-bounds vehicles; retains only valid Delhi coordinates. | Mumbai coordinates dropped; Azadpur coordinates retained. | **PASS** |
| **10. Failure Recovery** | Successful poll after 5 consecutive failures | Resets consecutive failure counter to 0; increments total success count. | Counter reset from 5 to 0; status updated to `AVAILABLE_VALIDATED`. | **PASS** |
| **11. Time Profile Calculation** | `HistoricalTimeProfileEngine` on 136 segments | Exact statistical calculations across quartiles, mean, std, median. | All statistical identities verified; $p_{25} \le p_{50} \le p_{75}$. | **PASS** |
| **12. Empty Time Bins Handling** | Profile bins for hours with 0 observations | Explicitly marked `UNAVAILABLE`; all metrics set to `None`; zero value invention. | 11 unobserved hours marked `UNAVAILABLE` with null statistics. | **PASS** |
| **13. API Live Status Endpoint** | `GET /api/v1/live/status` | Returns structured JSON adhering to Pydantic schema and `AUTH_REQUIRED`. | HTTP 200; `feed_enabled: false`, `overall_operational_status: "DEGRADE"`. | **PASS** |
| **14. Journey Planner Regression** | `POST /api/v1/journeys/plan` (Route 1598) | RAPTOR transit routing operates with zero regressions. | HTTP 200; direct bus, 20 min ride, Level 1 Observed, 93% confidence. | **PASS** |

---

## 3. Frontend UI Live Feed Status Display

The frontend web interface (`frontend/src/components/Header.tsx`) was verified in headless browser tests:
- **Header Badge Display:** Renders `Live Feed: Auth Required (Disabled)`.
- **Accessible Tooltip:** `"Transport Stack live GTFS-RT feed requires API key registration. Operating on historical baseline under DEGRADE status."`
- **Notice Strip:** `"Operational Notice: Static GTFS feed expired 2024-01-01. Live GTFS-RT stream requires API key (disabled). 2026 routes evaluate historical recurring weekly patterns and North GT Road traffic models. Actual physical bus runs are unverified."`
- **Zero Hallucination:** No fake buses, synthetic moving markers, or simulated live pings are rendered on the map.

---

## 4. Test Suite Execution Summary

### Python Backend Suite (`pytest -q backend/tests/`):
- **Total Tests:** **116 passed** out of 116 (100% pass rate)
- **Execution Time:** ~34.5 seconds
- **Milestone 8 Test Coverage:** 18 dedicated tests across live feed failure modes, time profiles, and API routes.

### Frontend Vitest Suite (`vitest run`):
- **Total Tests:** **26 passed** out of 26 (100% pass rate) across 6 test files.
- **Unmocked Live Backend Integration Tests:** 8 tests in `liveIntegration.test.ts` verifying `/health`, `/timetable/status`, `/live/status`, `/routes/1598`, `/stops/search`, `/stops/nearby`, and `/journeys/plan`.

---

## 5. Audit Conclusion

All operational failure modes, circuit breakers, and statistical calculations have been validated. The application operates in robust, fault-tolerant historical mode with zero live data contamination under **DEGRADE** operational status.

