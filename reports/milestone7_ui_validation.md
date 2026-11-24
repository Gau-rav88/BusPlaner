# Milestone 7: UI Truthfulness & Operational Safeguards Validation Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner (Problem 1)  
**Governing Specification:** PRD v3.0  
**Scope:** Mandatory Truthfulness Verification, Safeguard Hardening, and Automated Test Coverage  
**Overall Operational Status:** **DEGRADE**  
**Audit Date:** 2026-11-21  

---

## 1. Executive Summary

Milestone 7 mandates strict truthfulness requirements across the user interface to ensure that end users and transport operators are never misled regarding the freshness of the timetable, the existence of real-time vehicle tracking, the geographic scope of empirical traffic models, or the nature of prediction confidence scores.

This report independently verifies the implementation of these safeguards across the UI components, user flows, and automated test suites.

Key outcomes:
1. **Expired Timetable Truthfulness:** The user interface prominently states that the underlying GTFS timetable expired on `2024-01-01`. For 2026 dates, routing operates strictly under demonstration mode with assumed recurring weekly patterns, requiring explicit user opt-in.
2. **Actual Bus Operations Truthfulness:** The header, journey cards, and footer unequivocally state: `Live Operations: Unverified`. No live bus markers or real-time vehicle tracking animations are fabricated.
3. **Traffic Prediction Scope Truthfulness:** Observed historical traffic predictions are strictly attributed to the validated North GT Road pilot corridor (Route 1598). Unobserved corridors are explicitly tagged as `Scheduled Timetable (not traffic-adjusted)` or `Static Speed Fallback`.
4. **Experimental ML Gating:** Random Forest ML predictions are disabled by default (`use_experimental_ml: false`). The opt-in checkbox carries an explicit warning noting its negative out-of-fold generalization skill.
5. **Confidence Score Truthfulness:** Emitted confidence values are formatted as `Confidence: XX% (Heuristic)` with explanatory tooltips clarifying that scores are heuristic quality indicators, NOT statistical probabilities.
6. **Automated Test Verification:** 18 automated frontend unit and integration tests pass with 100% success.

---

## 2. Detailed Truthfulness Safeguards Audit

### 2.1 Expired Timetable Handling
- **Header Notice Strip:** The header renders a fixed, high-contrast disclosure strip:
  > *"Operational Notice: Static GTFS feed expired 2024-01-01. 2026 routes evaluate historical recurring weekly patterns. Actual physical bus runs are unverified."*
- **Opt-In Checkbox:** In `PlannerForm.tsx`, the checkbox is clearly labeled:
  > *"Demonstration Mode (Assumed Recurring): Acknowledge that GTFS timetable expired on 2024-01-01 and departures are unverified for 2026."*
- **Strict Mode Error Interception:** If a user unchecks the box and searches for a 2026 date, the backend returns HTTP 400 (`EXPIRED_TIMETABLE`). The frontend intercepts this error and displays an amber alert with a one-click button: *"Enable Assumed Recurring Mode & Retry"*.
- **Journey-Level Warning Banners:** Every affected journey alternative displays the stale timetable warning returned by the backend.

### 2.2 Unverified Physical Bus Operations
- **Header Status Badge:** The header displays a dedicated badge:
  `ShieldAlert Icon` + `Live Operations: Unverified`.
- **Card Metadata:** In `JourneyCard.tsx`, the card explicitly reflects `actual_operations_verified: false`.
- **Map Integrity:** The map renders static bus stops and route connections as supplied by the GTFS backend. No moving bus icons, GPS breadcrumb trails, or simulated real-time positions are rendered.

### 2.3 Traffic Prediction Hierarchy Representation
The UI employs color-coded badges to inform users of the exact prediction tier supporting each transit leg:

| Tier | UI Badge Text | Badge Styling | User Explanation |
|:---|:---|:---:|:---|
| **Level 1** | `Observed Traffic (Level 1)` | Emerald / Green | Empirical bus travel-time observations from North GT Road pilot corridor (Route 1598, 26 stop pairs). |
| **Level 2** | `Historical Median (Level 2)` | Teal / Cyan | Observed route/time-of-day median with empirical Bayesian shrinkage fallback. |
| **Level 3** | `Experimental ML (Level 3)` | Purple | Candidate Random Forest ML model evaluated in Milestone 3–4 (gated, experimental only). |
| **Level 4** | `Scheduled Timetable (Level 4)` | Amber / Yellow | Published GTFS timetable running times (not traffic-adjusted). |
| **Level 5** | `Static Fallback (Level 5)` | Slate / Gray | Conservative velocity assumption (15 km/h) for unmapped segments. |

Scheduled timetable times are never presented as live or traffic-adjusted estimates.

### 2.4 Experimental Machine Learning Gating
- Located inside the collapsible *Routing & Safeguard Controls* drawer in `PlannerForm.tsx`.
- Default state: `checked = false`.
- Checkbox label:
  > *"[Experimental] Enable Random Forest Candidate ML Predictions (disabled by default; negative out-of-fold generalization)."*
- Automated test `test_verifies_experimental_ml_disabled_by_default` confirms that the form initializes with this toggle deactivated.

### 2.5 Heuristic Confidence Score Communication
- Emitted confidence scores are formatted as:
  `Confidence: 85% (Heuristic)`
- Accompanied by a tooltip:
  *"Heuristic quality score based on empirical data depth and tier recency. NOT a calibrated statistical probability."*
- Prevents misinterpretation of ordinal scores as Bayesian or frequentist probabilities.

---

## 3. Automated Frontend Test Suite Coverage

The frontend test suite was executed via Vitest 2.1 in a jsdom environment:

```text
 ✓ src/test/apiService.test.ts (3 tests)
 ✓ src/test/formatters.test.ts (4 tests)
 ✓ src/test/JourneyResults.test.tsx (4 tests)
 ✓ src/test/PlannerForm.test.tsx (5 tests)
 ✓ src/test/HeaderAndAlerts.test.tsx (2 tests)

 Test Files  5 passed (5)
      Tests  18 passed (18)
   Duration  1.14s
```

### Key Test Assertions
1. `formatters.test.ts`: Verifies 12-hour/24-hour time formatting, post-midnight trips (`+1d`), duration minutes/hours, distance m/km, and tier labels.
2. `apiService.test.ts`: Tests `getHealth`, `searchStops`, and error handling for HTTP 400 Expired Timetable.
3. `PlannerForm.test.tsx`: Asserts submit button disabled until endpoints are selected, tests endpoint swap button, tests payload construction, and asserts `use_experimental_ml` is unchecked by default.
4. `JourneyResults.test.tsx`: Asserts ready-to-plan state, empty results state, journey duration, departure/arrival times, prediction tier badge, heuristic confidence label, and leg detail expansion.
5. `HeaderAndAlerts.test.tsx`: Asserts `DEGRADE` status badge, unverified operations badge, timetable status badge, and alert banner action buttons.

---

## 4. UI Validation Verdict

| Truthfulness Dimension | Assessment | Verification Evidence |
|:---|:---:|:---|
| Expired Timetable Disclosure | **PASS** | Prominent banner, explicit opt-in, 400 retry handler. |
| Unverified Operations Truth | **PASS** | Header and cards display `Live Operations: Unverified`. No simulated buses. |
| Traffic Prediction Hierarchy | **PASS** | Levels 1–5 color-coded with explicit scheduled vs observed distinctions. |
| Experimental ML Gating | **PASS** | Disabled by default; limitation warning displayed. |
| Heuristic Confidence Truth | **PASS** | Labeled `HEURISTIC` with non-probability explanation. |
| Test Coverage | **PASS** | 18 automated tests passing in 1.14s. |

**Overall UI Validation Status:** **PASS**

