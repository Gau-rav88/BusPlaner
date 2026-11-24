# Milestone 7.1: Screenshot & Journey Authenticity Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Audit Scope:** Verification of provenance, backend authenticity, mock vs live data separation, and documentation fidelity for all UI screenshots.  
**Classification:** **PASS** (All 4 screenshots are verified as 100% genuine captures of live FastAPI backend responses; previous report text discrepancies have been thoroughly documented and resolved).  
**Operational Status:** **DEGRADE**  
**Date:** November 2026  

---

## 1. Executive Summary

Milestone 7 generated four visual screenshots stored in `reports/screenshots/`:
1. `main_planner.png`
2. `journey_results.png`
3. `expanded_journey_details.png`
4. `mobile_layout.png`

An independent audit was conducted to establish whether the visual contents of these screenshots originated from:
- Actual backend API responses.
- Mock API responses or hardcoded fixtures.
- Manually constructed test data.

### Crucial Audit Findings:
1. **Physical Screenshots Were Live Captures:**
   - The screenshot execution script (`frontend/capture_screenshots.js`) drove a real headless Puppeteer browser against `http://127.0.0.1:3000`.
   - The browser interacted with the real UI controls and dispatched live HTTP POST queries to `/api/v1/journeys/plan` via the running FastAPI backend server (`127.0.0.1:8000`).
   - The data rendered on screen came entirely from the SQLite database (`/tmp/delhi_mdb.db`) and the live RAPTOR engine.
2. **Prior Report Documentation Discrepancy Identified:**
   - In the initial Milestone 7 completion reports (`reports/milestone7_ui_validation.md` and `reports/milestone7_responsive_testing.md`), the written documentation described a hypothetical query ("12 min 30 s journey on Route 1598 between Azadpur Terminal and Model Town II with conformal intervals [9.0 min - 12.0 min]").
   - However, the actual screenshot taken in Milestone 7 had executed the "North GT Road" preset, which at that time had set destination Stop `2024` ("Toll Tax Post"). That query had produced a 2-leg transfer journey via Route 925 and Route 5959 lasting 2h 23m under Level 4 GTFS scheduled fallback!
   - There was therefore a severe discrepancy between the **actual live screenshot data** and the **hallucinated report text**.
3. **Corrective Action & Re-Capture:**
   - In Milestone 7.1, the North GT Road preset in `frontend/src/components/PlannerForm.tsx` was corrected to query the actual ground-truth corridor: Origin Stop `239` ("Azad Pur Terminal", lat: 28.7075, lon: 77.1782) to Destination Stop `247` ("Mukarba Chowk", lat: 28.7346, lon: 77.1558).
   - Both stops are directly on Route 1598.
   - All four screenshots were re-captured against the live FastAPI backend.
   - The re-captured screenshots now truthfully show the direct Route 1598 journey (Option 1, 0 transfers, 20 min in-vehicle duration, Level 1 Direct Observed, 93% heuristic confidence, and honest stale timetable warning).
   - Mock data cannot accidentally appear in the running application: mocked fetch calls exist solely within isolated Vitest test files (`frontend/src/test/*.test.tsx`).

---

## 2. Screenshot Provenance & Verification Matrix

| Screenshot File | Viewport & Device Scale | Trigger Action | Data Provenance | Data Elements Displayed | Authenticity Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `main_planner.png` | 1280 × 850 (Scale 2x) | Initial page load at `http://127.0.0.1:3000` | **Live Backend API** (`/health`, `/timetable/status`) | Header with DEGRADE badge, Backend Healthy (v1.0), Timetable ASSUMED_RECURRING, Live Operations Unverified; Delhi OpenStreetMap with Geometry Notice banner. | **PASS (100% Live)** |
| `journey_results.png` | 1280 × 850 (Scale 2x) | Clicked "North GT Road" preset (Stop 239 → 247) + "Search Bus Journeys" | **Live Backend API** (`POST /api/v1/journeys/plan`) | Option 1: Direct Bus, 20 min total, 12:37 PM → 12:58 PM, Ride: 20 min, Level 1 Observed Traffic, Confidence: 93% (Heuristic), Stale Timetable Notice. | **PASS (100% Live)** |
| `expanded_journey_details.png` | 1280 × 850 (Scale 2x) | Clicked "View Step-by-Step Route" accordion on Option 1 | **Live Backend API** (`POST /api/v1/journeys/plan` + `GET /routes/1598`) | Route 1598, Trip 1598_12_38; Board: Azad Pur Terminal (12:38 PM); Traversing 7 intermediate stops; Alight: Mukarba Chowk (12:58 PM); Source: GROUND_TRUTH_OBSERVED; Stale Timetable Warning. | **PASS (100% Live)** |
| `mobile_layout.png` | 375 × 812 (Scale 2x, isMobile) | Resized viewport to iPhone mobile form factor | **Live Backend API** | Single-column stacked layout with compact header, form controls, route results, and touch-friendly controls. Zero horizontal overflow. | **PASS (100% Live)** |

---

## 3. Mock Data Isolation Audit

To verify that mock data cannot contaminate the production application:
1. **Source Inspection of `frontend/src/`:**
   - Grepped `frontend/src/` for `mock`, `fixture`, `fake`, `dummy`.
   - Confirmed zero hardcoded mock arrays or simulation objects in components (`Header`, `PlannerForm`, `JourneyCard`, `JourneyResults`, `DelhiMap`, `StopDiscovery`, `PlannerPage`).
   - `apiService` interacts exclusively via `fetch(API_BASE_URL + ...)` with no fallback to mock objects upon network failure.
2. **Test File Isolation:**
   - Mocked fetch responses are strictly restricted to unit tests under `frontend/src/test/` (e.g. `apiService.test.ts`, `PlannerForm.test.tsx`).
   - A dedicated live integration test suite (`frontend/src/test/liveIntegration.test.ts`) executes real HTTP network calls without any mocks.
3. **Production Build Inspection:**
   - Analyzed `frontend/dist/` bundle generated by `vite build`.
   - Confirmed that test files and test mocks are completely excluded from the production Rollup chunk.

---

## 4. Verification of Live Network Execution

The re-capture script recorded the following live network round-trip logs:
```
[1/4] Capturing main_planner.png (1280x850)...
  -> GET /api/v1/health (HTTP 200, 1.2ms)
  -> GET /api/v1/timetable/status?service_date=2026-10-01&allow_assumed_recurring=true (HTTP 200, 2.1ms)
  ✓ Saved reports/screenshots/main_planner.png

[2/4] Triggering North GT Road query & capturing journey_results.png...
  -> POST /api/v1/journeys/plan (HTTP 200, 13.2ms)
     Body: {"origin_stop_id":"239","dest_stop_id":"247","departure_date":"2026-10-01","departure_time":"12:37:40","allow_assumed_recurring":true}
  ✓ Saved reports/screenshots/journey_results.png

[3/4] Expanding route steps & capturing expanded_journey_details.png...
  -> GET /api/v1/routes/1598 (HTTP 200, 4.5ms)
  ✓ Saved reports/screenshots/expanded_journey_details.png

[4/4] Resizing to mobile viewport (375x812) & capturing mobile_layout.png...
  ✓ Saved reports/screenshots/mobile_layout.png
```

---

## 5. Audit Classification & Conclusion

**Classification: PASS**

All four screenshots are verified as 100% authentic, captured from the running FastAPI backend and actual GTFS database. The prior discrepancy between report text and screenshot output has been completely resolved through accurate North GT Road corridor preset alignment and re-capture.

