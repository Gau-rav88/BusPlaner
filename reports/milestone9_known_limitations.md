# Milestone 9 — Known Technical Limitations & Operational Disclosure

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 (Appendix B)  
**Current Operational Status:** **`DEGRADE`** *(Strictly Maintained)*  
**Audit Milestone:** Milestone 9: Final Validation, Demo Readiness & Submission Package  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Disclosure Policy

In strict accordance with PRD v3.0 Appendix B and the core principles of scientific integrity, this document details all architectural, data, and empirical limitations of the Delhi Bus Traffic Prediction and Journey Planning system.

The system makes **no exaggerated claims** of network-wide real-time intelligence, live fleet tracking, or production deployment readiness. It is designed and presented as a **disciplined, evidence-backed transit research prototype operating under verified `DEGRADE` status**.

---

## 2. Comprehensive Inventory of Known Limitations

### Limitation 1: Governing Operational Status is `DEGRADE`
- **Condition:** Assigned in Milestone 0 and preserved across all milestones through Milestone 9.
- **Rationale:** Assigned due to the combination of an expired static GTFS calendar, lack of live vehicle telemetry authentication, and geographic confinement of empirical traffic observations to a single pilot corridor.
- **System Impact:** Disclosed in all API health checks (`/api/v1/health`), timetable status endpoints (`/api/v1/timetable/status`), journey planning metadata, and prominent UI badges.

---

### Limitation 2: Expired Static GTFS Timetable Calendar
- **Condition:** The official Delhi Transport Corporation (DTC) GTFS timetable calendar has a validity range of **January 1, 2022 to January 1, 2024**.
- **Current Query Date:** October / November 2026.
- **Handling & Safeguards:**
  - Standard queries for 2026 dates without explicit consent are **strictly rejected with HTTP 400 Bad Request (`EXPIRED_TIMETABLE`)**.
  - Demonstration queries are evaluated only when the client explicitly passes `allow_assumed_recurring: true`.
  - The API emits `timetable_status: "ASSUMED_RECURRING"` and `actual_operations_verified: false`, warning passengers that trips may have been altered or cancelled since 2024.

---

### Limitation 3: Live GTFS-Realtime Feed Gated (`AUTH_REQUIRED`)
- **Condition:** Upstream vehicle position endpoint (`https://dts-backend.transportstack.in/.../VehiclePositions.pb`) requires an authenticated `x-api-key` header from the Delhi Transport Stack.
- **System State:** The local environment variable `DELHI_TRANSPORTSTACK_API_KEY` is unconfigured.
- **Handling & Safeguards:**
  - Live feed is classified strictly as **`AUTH_REQUIRED`**.
  - Live feed ingestion is safely held in a **disabled state (`feed_enabled: false`)**.
  - Zero synthetic moving buses, fake GPS streams, or simulated vehicles are injected into the journey planner.
  - Missing credentials return `AUTH_REQUIRED` immediately with zero network polling.

---

### Limitation 4: Confinement of Empirical Traffic Predictions to North GT Road
- **Condition:** Ground-truth bus GPS data was ingested and map-matched for a 5-date pilot subset (October 1–4, 7, 2026), yielding 136 consecutive stop-to-stop traversals across Route 1598 (124 obs), Route 1445 (11 obs), and Route 1657 (1 obs).
- **Network Scope:** Confined to 26 route-specific stop pairs (21 physical pairs) along the North GT Road corridor between Azad Pur Terminal and Mukarba Chowk / Alipur.
- **Handling & Safeguards:**
  - The system **does NOT predict traffic Delhi-wide**.
  - Journeys outside Route 1598 cleanly fall back to **`LEVEL_4_GTFS_SCHEDULED`** (scheduled timetable durations) or **`LEVEL_5_STATIC_FALLBACK`** (walking speeds at 4.5 km/h).

---

### Limitation 5: Approximate Stop-to-Stop Map Geometry (No `shapes.txt`)
- **Condition:** The Delhi static GTFS package contains no official `shapes.txt` table (row count: 0).
- **Visual Impact:** Plotted bus route paths connect sequential bus stops using straight-line segments. Actual road curves, turns, roundabouts, and flyover ramps are not rendered.
- **Handling & Safeguards:**
  - The map view includes an unmissable orange banner:
    > *"Approximate Stop-to-Stop Geometry: Delhi GTFS feed lacks shapes.txt. Plotted paths connect stop coordinates via straight segments; actual road curvature and street geometry are not represented."*
  - The system refuses to fabricate road geometry curves from third-party non-reproducible routing engines.

---

### Limitation 6: Heuristic Confidence Scoring
- **Condition:** Confidence indicators emitted in transit legs range from 0.0 to 1.0 based on sample size and fallback tier.
- **Handling & Safeguards:**
  - All confidence fields are explicitly typed as `confidence_score_type: "HEURISTIC"`.
  - The UI and API explicitly state that these numbers are heuristic quality indicators, **not calibrated frequentist or Bayesian probabilities**.

---

### Limitation 7: Candidate Random Forest Model Disabled by Default
- **Condition:** During Milestone 4 extended validation, chronological evaluation revealed that the candidate Random Forest regressor exhibited negative out-of-fold generalization skill ($R^2 < 0$) against the historical median baseline (M0), driven by extreme sample sparsity (136 total observations).
- **Handling & Safeguards:**
  - The candidate ML model is deactivated by default (`use_experimental_ml: false`).
  - The historical median baseline (M0) remains the governing Level 1/Level 2 empirical prediction engine.

---

### Limitation 8: Detour Factor ($k = 1.262$) Restriction
- **Condition:** An exploratory detour ratio of $1.262$ was computed on North GT Road as the ratio of road network distance to Euclidean distance.
- **Handling & Safeguards:**
  - This ratio is **never applied globally** across Delhi. It is used strictly for distance fallbacks on Route 1598.
  - Walking connections use a standard grid conversion ($k = 1.3$).

---

### Limitation 9: Temporal Profile Gaps
- **Condition:** Out of 24 hours of the day (IST), the historical pilot dataset contains observations during exactly 13 hours. Exactly 11 hours (00:00–06:00, 11:00, 19:00, 22:00–23:00) contain zero observations.
- **Handling & Safeguards:**
  - Unobserved hours are strictly reported as `profile_status: "UNAVAILABLE"` with `None` statistics.
  - The system refuses to impute fictitious traffic speeds for unobserved time windows.

---

## 3. Summary Assessment

By rigorously documenting and enforcing these limitations in code, APIs, and user interfaces, the project ensures complete transparency. Evaluators and transit analysts can inspect every component with confidence that no unverified claims or synthetic data compromise the system.

