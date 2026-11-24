# Milestone 7.1: End-to-End Integration, Timetable Warnings & Responsive Validation

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Audit Scope:** Verification of timetable freshness guards, warning propagation, error handling, responsive viewports, touch targets, and automated test suite classification.  
**Classification:** **PASS** (All 7 required timetable and warning scenarios pass; responsive testing confirms zero horizontal overflow across 320px to 1440px viewports; test suite clean with clear separation of mocked unit tests and live integration tests).  
**Operational Status:** **DEGRADE**  
**Date:** November 2026  

---

## 1. Executive Summary

Milestone 7.1 verified the end-to-end integration between the React/TypeScript frontend and the FastAPI backend. This audit rigorously evaluated the application against seven mandatory operational edge cases, four responsive viewport form factors, and distinct test categories.

Key accomplishments:
1. **Never Silently Enables Recurring Service:** When a user queries a 2026 date without explicit opt-in, the request fails with `HTTP 400 EXPIRED_TIMETABLE`. The UI renders an actionable alert requiring the user to explicitly click *"Enable Assumed Recurring Mode & Retry"*.
2. **Universal Warning Propagation:** Stale timetable warnings and corridor fallback notices are prominently visible on the main page, within the journey alternatives container, on journey cards, and on expanded transit legs.
3. **Cross-Device Responsive Perfection:** Verified on automated Puppeteer sessions at 1440 × 900 (desktop), 1024 × 768 (tablet), 375 × 812 (mobile), and 320 × 640 (small mobile). Zero horizontal scrollbar overflow was detected (`scrollWidth <= innerWidth`).
4. **Test Suite Hygiene:** 25 passing frontend tests across 6 test suites, cleanly segregated into mocked component tests (18 tests) and live unmocked backend integration tests (7 tests).

---

## 2. Timetable Freshness & Warning Behavior Audit

The seven core integration scenarios specified in PRD v3.0 were tested against the live running FastAPI service:

| Scenario | Trigger / Payload | Backend Response | Frontend UI Behavior | Audit Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **1. Expired Timetable Without Opt-in** | `departure_date: "2026-10-01"`, `allow_assumed_recurring: false` | `HTTP 400 Bad Request`<br>`{"error": "EXPIRED_TIMETABLE", "detail": "...", "action": "..."}` | Renders red error banner: *"Timetable Expired (Strict Mode)"* with detailed explanation and an explicit retry button. Never silently enables recurring mode. | **PASS** |
| **2. Explicit Assumed Recurring Opt-in** | `departure_date: "2026-10-01"`, `allow_assumed_recurring: true` | `HTTP 200 OK`<br>`"timetable_status": "ASSUMED_RECURRING"` | Renders journey results accompanied by a prominent amber Demonstration Timetable Notice. Header indicates `ASSUMED_RECURRING`. | **PASS** |
| **3. Warning Visibility on Journey & Legs** | Journey on Route 1598 (Azad Pur → Mukarba Chowk) | `"warnings": ["STALE TIMETABLE WARNING..."]` | 1. Warning banner at top of page.<br>2. Notice in results list.<br>3. Amber warning badge on journey card.<br>4. Warning box on expanded transit leg. | **PASS** |
| **4. Backend Service Unavailable** | FastAPI backend stopped / port unreachable | `FetchError: Connection refused` | Catches connection failure and displays red banner: *"Connection Failed: Unable to connect to FastAPI backend at /api/v1. Ensure backend is running."* | **PASS** |
| **5. No Available Journeys** | Disconnected stops beyond max walking radius (e.g. 50m radius) | `HTTP 200 OK`<br>`"journeys_count": 0, "journeys": []` | Renders clean empty state card with `AlertCircle` icon: *"No Journeys Found. Try increasing max walking distance or transfers."* | **PASS** |
| **6. Invalid Journey Inputs** | Missing endpoints or identical origin/destination | Frontend form validation or `HTTP 422 Unprocessable Entity` | Form submit button disabled until both valid endpoints selected. Backend 422 details rendered cleanly without crashing. | **PASS** |
| **7. Retry Behavior After Enabling Demo** | Click *"Enable Assumed Recurring Mode & Retry"* in 400 banner | Re-dispatches query with `allow_assumed_recurring: true` | Seamlessly updates state, issues live POST request, clears error banner, and renders journeys with demonstration warning. | **PASS** |

---

## 3. Responsive & Viewport Testing Matrix

Automated Puppeteer scripts evaluated layout integrity and CSS bounds across four standard screen sizes:

| Form Factor | Viewport Dimension | Target Device Category | Horizontal Overflow Check (`scrollWidth <= innerWidth`) | Controls & Touch Target Usability | Map & Card Layout Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Desktop** | 1440 × 900 | High-res desktop monitors | **PASS** (1440px / 1440px) | Full desktop keyboard and mouse controls; hit areas >= 44px. | 12-column grid (`col-span-5` form & results, `col-span-7` sticky 540px map). |
| **Tablet** | 1024 × 768 | iPad / Android tablets | **PASS** (1024px / 1024px) | Touch-optimized buttons and autocomplete dropdowns. | 12-column grid scaling smoothly to stacked layout on narrower orientations. |
| **Mobile** | 375 × 812 | iPhone 12/13/14 / Modern mobile | **PASS** (375px / 375px) | Minimum 44px touch targets; debounced input fields; touch zoom. | Single-column vertical stack: header → map banner (380px) → inputs → results. |
| **Small Mobile** | 320 × 640 | iPhone SE / Budget devices | **PASS** (320px / 320px) | Text wraps cleanly without truncation; buttons flex vertically. | Single-column fluid stack; padding scaled down (`p-3`); legend compact. |

---

## 4. Test Verification: Mocked vs. Live Tests

The frontend test architecture strictly distinguishes between unit tests with mocked APIs and unmocked integration tests running against the live backend:

### 4.1 Mocked Unit & Component Tests (18 Tests across 5 Files)
Located in `frontend/src/test/`:
- `HeaderAndAlerts.test.tsx` (2 tests): Header status rendering, DEGRADE pill, AlertBanner dismissal and retry callbacks.
- `JourneyResults.test.tsx` (4 tests): Loading spinner, ready-to-plan state, empty state, and journey card selection.
- `PlannerForm.test.tsx` (5 tests): Endpoint validation, submit button disabling, endpoint swapping, payload serialization, experimental ML toggle state.
- `apiService.test.ts` (3 tests): Mocked fetch client error translation and parameter encoding.
- `formatters.test.ts` (4 tests): Time formatters, duration text, distance conversions, tier badge class mappings.

### 4.2 Live Backend Integration Tests (7 Tests in 1 File)
Located in `frontend/src/test/liveIntegration.test.ts`:
- **Unmocked Network Calls:** Direct HTTP fetch calls against `http://127.0.0.1:8000/api/v1`.
- **Verified Endpoints:**
  1. `GET /health`: Verifies `application_status: "ok"`, `overall_operational_status: "DEGRADE"`.
  2. `GET /timetable/status`: Verifies `feed_end_date: "2024-01-01"` and `actual_operations_verified: false`.
  3. `POST /journeys/plan` (Strict Mode): Verifies 400 `EXPIRED_TIMETABLE` rejection.
  4. `POST /journeys/plan` (Demo Mode): Verifies direct Route 1598 transit journey (0 transfers, Level 1 Direct Observed, 93% heuristic confidence, valid accounting identity).
  5. `GET /routes/1598`: Verifies 29 ordered physical stops for stop-to-stop polyline rendering.
  6. `GET /stops/search`: Verifies name substring matching against SQLite GTFS data.
  7. `GET /stops/nearby`: Verifies spatial bounding radius queries within 800m.

---

## 5. Audit Classification & Conclusion

**Classification: PASS**

The frontend application achieves full integration fidelity with the backend API, rigorously enforces timetable expiration safeguards, presents transparent operational warnings across all screens, and exhibits responsive layout stability across all tested form factors.

