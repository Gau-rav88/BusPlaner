# Milestone 7.1: Prediction Interval Attribution & Integrity Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Audit Scope:** Verification of conformal prediction intervals, backend vs frontend schema contracts, absence of synthetic interval fabrication, and heuristic confidence attribution.  
**Classification:** **PASS** (The frontend strictly renders backend-provided telemetry and does not calculate, hallucinate, or fabricate conformal intervals for scheduled or static fallbacks; heuristic confidence scores are unequivocally labeled).  
**Operational Status:** **DEGRADE**  
**Date:** November 2026  

---

## 1. Executive Summary

Milestones 3, 3.1, and 4 established split-conformal prediction intervals for empirical transit segments on the verified North GT Road corridor, computing a calibrated finite-sample conformal radius of $q = 349.10$ seconds on the pilot validation set.

This audit inspected the journey planning pipeline across both backend and frontend layers to verify how prediction intervals and confidence scores are handled in the web interface:
1. **Backend API Schema Contract:** The FastAPI response schema (`TransitLegSchema` in `backend/app/schemas/journey.py`) exposes `sched_duration_s`, `ride_duration_s`, `prediction_tier`, `prediction_source`, `heuristic_confidence_score`, `confidence_score_type`, `is_fallback`, `warning`, `timetable_status`, and `is_verified_current_service`. Conformal prediction intervals are internal to the ML evaluation pipeline and are **not emitted as public fields** on individual `TransitLeg` objects in the REST API.
2. **Frontend Zero-Fabrication Rule:** The frontend component (`frontend/src/components/JourneyCard.tsx`) renders the exact values returned by the backend. It contains zero logic to compute, approximate, or fabricate prediction intervals.
3. **No Synthetic Intervals on Fallbacks:** In accordance with PRD v3.0, GTFS scheduled running times (Level 4) and static-speed fallbacks (Level 5) receive **no prediction intervals**.
4. **Heuristic Confidence Attribution:** Every journey alternative and transit leg explicitly displays `(Heuristic)` alongside its percentage rating, with an explanatory tooltip:  
   `"Heuristic quality score based on empirical data depth. NOT a statistical probability."`
5. **Resolution of Prior Report Discrepancy:** Previous Milestone 7 text reports referenced hypothetical intervals (`[9.0 min - 12.0 min]`) in narrative examples. This audit confirms that the running frontend code never rendered those fabricated numbers, and all reports are now aligned with the true API contract.

---

## 2. Layer-by-Layer Verification

### 2.1 Backend Router & Schemas (`backend/app/`)
- **Schema Inspection:** `TransitLegSchema` in `backend/app/schemas/journey.py`:
  ```python
  class TransitLegSchema(BaseModel):
      leg_type: str = Field(default="TRANSIT")
      route_id: str
      trip_id: str
      pattern_id: int
      board_stop_id: str
      board_stop_name: str
      alight_stop_id: str
      alight_stop_name: str
      sched_departure_s: float
      sched_arrival_s: float
      sched_duration_s: float
      board_time_s: float
      alight_time_s: float
      ride_duration_s: float
      intermediate_stops: List[str]
      prediction_tier: str
      prediction_source: str
      heuristic_confidence_score: float
      confidence_score_type: str = Field(default="HEURISTIC")
      confidence_explanation: str
      is_fallback: bool
      fallback_reason: Optional[str]
      warning: Optional[str]
      timetable_status: str
      is_verified_current_service: bool
  ```
  *Finding:* Neither `conformal_lower_s` nor `conformal_upper_s` are present in `TransitLegSchema`.

### 2.2 Frontend Service & Types (`frontend/src/`)
- **TypeScript Type Definitions:** `frontend/src/types/api.ts` accurately mirrors `TransitLegSchema`.
- **Component Rendering:** `frontend/src/components/JourneyCard.tsx` renders:
  - Duration: `formatDuration(leg.ride_duration_s)`
  - Board/Alight times: `formatSecondsToTime(leg.board_time_s)` vs `(Sched: formatSecondsToTime(leg.sched_departure_s))`
  - Prediction Tier Badge: `legTierInfo.badgeClass` and `legTierInfo.shortLabel`
  - Attribution Source: `Source: {leg.prediction_source}`
  - Heuristic Confidence: `Confidence: {(journey.heuristic_confidence_score * 100).toFixed(0)}% (Heuristic)`
  - Warning Banners: Rendered if `leg.warning` is present.
  *Finding:* No synthetic bounds, intervals, or margin-of-error calculations exist in TypeScript.

---

## 3. Fallback Tier Integrity Matrix

| Prediction Hierarchy Level | Prediction Source | Conformal Interval Presence | Frontend Display Behavior | Integrity Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **Level 1: Direct Observed** | `GROUND_TRUTH_OBSERVED` | None emitted in REST schema. | Displays ride duration, departure/arrival deltas, 93% heuristic confidence, and observed source label. | **PASS** |
| **Level 2: Historical Baseline** | `M0_HISTORICAL_MEDIAN` | None emitted in REST schema. | Displays baseline ride duration, departure/arrival deltas, 80% heuristic confidence, and M0 source label. | **PASS** |
| **Level 3: Experimental ML (Gated)** | `M2_RANDOM_FOREST` | Internal calibration $q = 349.10$s; not in public schema. | Displays predicted duration and explicit negative-skill advisory if opted in. | **PASS** |
| **Level 4: GTFS Scheduled** | `GTFS_TIMETABLE` | Strictly None. | Displays scheduled timetable running time, Level 4 badge, 30% heuristic confidence, and fallback notice. | **PASS** |
| **Level 5: Static Fallback** | `STATIC_SPEED_FALLBACK` | Strictly None. | Displays static speed duration, Level 5 badge, 10% heuristic confidence, and low-confidence warning. | **PASS** |

---

## 4. Heuristic Confidence Enforcement

To guarantee that users never mistake heuristic ratings for calibrated probabilities:
1. Every score is followed by the literal string `(Heuristic)`.
2. The HTML `title` tooltip explicitly warns:
   `"Heuristic quality score based on empirical data depth. NOT a statistical probability."`
3. The underlying backend API echoes `confidence_score_type: "HEURISTIC"` on every leg and journey response.

---

## 5. Audit Classification & Conclusion

**Classification: PASS**

The frontend faithfully adheres to backend data contracts. It never fabricates conformal intervals, never applies artificial bounds to scheduled or static fallbacks, and maintains rigorous scientific honesty regarding heuristic confidence scores under **DEGRADE** operational status.

