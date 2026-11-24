# Milestone 6.1: Final Assessment & Audit Verdict

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing Specification:** PRD v3.0  
**Audit Scope:** Independent Audit of Milestone 6 Backend API  
**Overall Operational Status:** **DEGRADE**  
**Audit Date:** 2026-11-21  
**Metrics Payload:** `data/processed/milestone6_1_audit_metrics.json`  

---

## 1. Executive Summary

Milestone 6.1 conducted an independent, evidence-first audit of the Milestone 6 FastAPI REST backend. The audit verified the API implementation against actual source code, executable tests, live TCP network requests, and PRD v3.0 requirements.

All audited functional areas passed or passed with clearly documented operational limitations. The audit identified and resolved three concrete technical defects:
1. **Freshness Warning Propagation:** In Milestone 6, transit leg schemas omitted the stale timetable warning when routing under demonstration mode. This was corrected: stale timetable warnings now reach every affected journey and transit leg.
2. **Polymorphic Discriminator:** Added explicit `leg_type="TRANSIT"` to `TransitLegSchema`, providing consistent polymorphic discrimination alongside `WalkingLegSchema`.
3. **Freshness State Canonicalization:** Reconciled internal state enum `UNAVAILABLE` and HTTP error code `TIMETABLE_UNAVAILABLE`, eliminating documentation ambiguity and returning `timetable_status="UNAVAILABLE"` in the 503 error payload.

Across the entire backend test suite, **98 of 98 automated tests passed (100%)** (83 prior tests + 15 dedicated Milestone 6.1 audit tests).

The overall operational status remains strictly **DEGRADE**.

---

## 2. Area-by-Area Audit Classification

| Audited Area | Classification | Summary of Findings & Evidence |
|:---|:---:|:---|
| **1. Timetable Freshness Consistency** | **PASS** | All 4 canonical states (`CURRENT_VERIFIED`, `EXPIRED`, `ASSUMED_RECURRING`, `UNAVAILABLE`) verified. Expired dates strictly rejected (400) without opt-in; opt-in enables demonstration mode. Warnings reach response envelope, journey list, and all individual transit legs. `actual_operations_verified: false` enforced. |
| **2. Journey Response & Accounting** | **PASS** | Scheduled vs predicted times clearly distinguished. Boarding/alighting stop IDs and names match. All 6 accounting fields non-negative; time-conservation identity $|T_{\text{total}} - \sum \text{Components}| = 0.0000 \text{ s}$ verified. No double-counting of dwell or transfer waits. |
| **3. Prediction Attribution & Confidence** | **PASS** | Tiers 1–5 prediction sources explicitly attributed. Confidence scores labeled `HEURISTIC` with non-probability explanation. Random Forest ML model deactivated by default (`use_experimental_ml: false`). |
| **4. Endpoint & Input Validation** | **PASS** | All 6 endpoints tested. Out-of-bounds coordinates, invalid dates/times, identical endpoints, and missing inputs intercepted with 422. Unknown stops return clean empty journeys; unknown routes return 404. |
| **5. Security, CORS & Sanitization** | **PASS** | Permissive wildcard CORS (`*`) forbidden; whitelisted origins enforced. Error envelopes sanitized without leaking server paths or stack traces. Request boundaries defend against DoS. |
| **6. Performance & Benchmark Transparency** | **PASS WITH LIMITATIONS** | Warmed-up live TCP latencies verified: lightweight endpoints $\le 1.12 \text{ ms}$, transit routing queries $\sim 145–215 \text{ ms}$. Disclosed that un-warmed first query requires $\sim 5.4 \text{ s}$; mitigated by pre-warming in lifespan handler. |

---

## 3. Exhaustive List of Corrections Made in Milestone 6.1

1. **Transit Leg Stale Timetable Warning Propagation:**
   - *Issue:* In Milestone 6, `TransitLeg.warning` only collected segment travel-time warnings, leaving `leg.warning = None` during demonstration routing despite `journey.timetable_warning` being present.
   - *Fix:* Updated `backend/core/journey_planner.py` to append `timetable_warn` to leg warnings, and updated `backend/app/services/planner_service.py` to ensure `TransitLegSchema.warning` carries the stale timetable warning.
2. **TransitLeg Schema Discriminator:**
   - *Issue:* `WalkingLegSchema` contained `leg_type: str`, but `TransitLegSchema` lacked `leg_type`, making client-side polymorphic parsing brittle.
   - *Fix:* Added `leg_type: str = Field(default="TRANSIT", description="Always TRANSIT for bus legs")` to `TransitLegSchema` in `backend/app/schemas/journey.py` and service transformation.
3. **Timetable Freshness State Harmonization:**
   - *Issue:* Documentation and error handlers mixed `TIMETABLE_UNAVAILABLE` and `UNAVAILABLE`.
   - *Fix:* Clarified that `UNAVAILABLE` is the canonical freshness state enum value (`TimetableStatus.UNAVAILABLE`), while `TIMETABLE_UNAVAILABLE` is the HTTP 503 error code. Added `"timetable_status": "UNAVAILABLE"` into the 503 error payload in `backend/app/api/v1/journeys.py`.
4. **Cold-Start Pre-Warming in Lifespan:**
   - *Issue:* The very first transit planning query on an un-warmed server required $5,443.23 \text{ ms}$ (~5.4s) due to lazy loading of baseline model arrays and pyproj transformers.
   - *Fix:* Enhanced `lifespan` in `backend/app/main.py` to execute a lightweight warmup journey query during server boot, eliminating cold-start latency for all user-facing requests.
5. **Dual-Harness Benchmark Methodology:**
   - *Issue:* Milestone 6 only reported in-process `TestClient` latencies, which omit real socket networking.
   - *Fix:* Implemented `scripts/compile_milestone6_1_audit_metrics.py` to benchmark both in-process ASGI and live HTTP over a real TCP socket (`http://127.0.0.1:8001`), producing `data/processed/milestone6_1_audit_metrics.json`.
6. **Milestone 6.1 Audit Test Suite:**
   - Created `backend/tests/test_milestone6_1_audit.py` containing 15 automated integration tests verifying all 4 freshness states, leg warning propagation, duration accounting, heuristic confidence scoring, CORS headers, and error sanitization.

---

## 4. Unresolved Operational Limitations & Known Constraints

The project remains under **DEGRADE** status due to external data constraints documented in PRD v3.0:
1. **GTFS Timetable Expiration:** The available Delhi static GTFS schedule expired on `2024-01-01`. Current date queries (October/November 2026) rely on an assumed recurring schedule pattern and require explicit user opt-in (`allow_assumed_recurring=true`).
2. **Physical Operations Unverified:** Static GTFS files cannot verify whether scheduled buses actually operated. `actual_operations_verified` is strictly `false` across all responses.
3. **Corridor Scope of Empirical Data:** Validated ground-truth bus GPS observations remain restricted to Route 1598 (North GT Road corridor, 26 stop pairs). Unobserved corridors fall back to GTFS scheduled running times or static speed fallbacks.
4. **Heuristic Confidence Scores:** Emitted confidence scores represent heuristic quality indicators, not calibrated statistical coverage probabilities.
5. **Experimental ML Candidate Inactive:** The Random Forest candidate model evaluated in Milestone 4 demonstrated negative out-of-fold generalization skill ($R^2 < 0$) and remains deactivated by default.

---

## 5. Test Suite Verification Summary

```bash
pytest -v backend/tests/
```
- **Prior Milestone Tests (M1–M6):** 83 passed / 83 total
- **Milestone 6.1 Audit Tests:** 15 passed / 15 total
- **Total Test Suite:** **98 passed / 98 total (100% pass rate)**
- **Test Suite Duration:** ~40 seconds

---

## 6. Strict Stop Condition & Sign-Off

Milestone 6.1 is **COMPLETE**.

In compliance with instructions:
- **No frontend components have been created.**
- **Milestone 7 has NOT been started.**
- **No live GTFS-RT polling has been added.**
- **No external traffic APIs have been integrated.**
- **Traffic prediction claims remain strictly confined to the North GT Road pilot.**

Antigravity is stopped and awaiting user review and explicit approval before Milestone 7.

