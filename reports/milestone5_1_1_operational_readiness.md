# Milestone 5.1.1 — Operational Readiness & Confidence Score Correction Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5.1.1 (GTFS Freshness & Operational Readiness Correction)  
**Governing PRD:** v3.0  
**Governing Decision:** **DEGRADE**  
**Author:** Independent System Auditor  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Correction Mandate

This report executes two mandatory corrections required by the Milestone 5.1 review:
1. **Removal of Unsupported Production-Readiness Claims:** Prior reports described timetable routing as "production ready". Because the underlying GTFS feed expired on January 1, 2024, the engine cannot claim production readiness for current real-world passenger travel in Delhi. Operational readiness is formally redefined into five transparent domains.
2. **Prediction Confidence Recalibration:** Numeric confidence scores across the 5-level prediction hierarchy are formally documented and categorized as **heuristic confidence scores**, rather than calibrated statistical probabilities.

---

## 2. Five Operational Readiness Dimensions

The system's operational scope is formally delineated across five independent technical pillars:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           OPERATIONAL READINESS STATUS MATRIX                           │
├───────────────────────────────────┬───────────────────────────────┬─────────────────────┤
│ TECHNICAL PILLAR                  │ VERIFICATION STATUS           │ READINESS STATUS    │
├───────────────────────────────────┼───────────────────────────────┼─────────────────────┤
│ 1. RAPTOR Routing Algorithm       │ Validated (15 GTFS cases)     │ ALGORITHMIC PASS    │
│ 2. Historical Timetable Routing   │ Validated against GTFS feed   │ HISTORICAL PASS     │
│ 3. Current Delhi Service Accuracy │ Unverified (expired feed)     │ UNVERIFIED / STALE  │
│ 4. Traffic Prediction Model       │ Restricted to North GT Road   │ PILOT SCOPE ONLY    │
│ 5. Overall System Status          │ DEGRADE Status Preserved      │ EXPERIMENTAL/DEGRADE│
└───────────────────────────────────┴───────────────────────────────┴─────────────────────┤
│ PRODUCTION READINESS FOR CURRENT DELHI PASSENGER ROUTING: NOT CLAIMED / UNSUPPORTED     │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Assessment of Pillars
1. **RAPTOR Routing Engine:**
   - Evaluated against 15 independent GTFS ground-truth test cases and 150 benchmark query runs.
   - Core Pareto multi-criteria optimization, round progression, $\ge 120\text{s}$ transfer buffer enforcement, and machine-precision duration conservation ($\Delta = 0.00000000\text{s}$) are fully verified and bug-free.
2. **Historical Timetable Routing:**
   - Correctly processes and reconstructs trips from the supplied Delhi Mobility Database archive.
   - Handles midnight transitions and continuous monotonic second timestamps without integer overflow.
3. **Current Delhi Service Accuracy:**
   - **UNVERIFIED.** The static feed ended validity on 2024-01-01. Current DTC routes, frequencies, stops, and schedules in November 2026 cannot be verified from this archive.
4. **Traffic Prediction Scope:**
   - Ground-truth traffic observations ($N=136$ consecutive-stop segments) exist strictly on the North GT Road corridor (Route 1598 and co-running lines).
   - All network corridors outside North GT Road fall back to scheduled times (Level 4) or static distance metrics (Level 5).
5. **Production Readiness Verdict:**
   - **Production readiness is explicitly NOT claimed.** The system is an advanced research and demonstration prototype operating under **DEGRADE** status.

---

## 3. Prediction Hierarchy Confidence Score Recalibration

Previously, confidence values in `backend/core/journey_planner.py` (e.g. `1.0`, `0.8`, `0.7`, `0.3`, `0.1`) could be misinterpreted by external callers as calibrated probabilities of on-time arrival or schedule adherence. 

They are now explicitly defined as **heuristic confidence scores** with documented meanings, limitations, and no probability guarantees.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        PREDICTION HIERARCHY CONFIDENCE AUDIT                           │
├─────────┬──────────────────────────────┬────────┬───────────┬──────────────────────────┤
│ LEVEL   │ TIER IDENTIFIER              │ SCORE  │ TYPE      │ EMPIRICAL EXPLANATION    │
├─────────┼──────────────────────────────┼────────┼───────────┼──────────────────────────┤
│ Level 1 │ LEVEL_1_DIRECT_OBSERVED      │ 1.0    │ HEURISTIC │ High sample GPS ground   │
│         │                              │        │           │ truth on corridor (n>=3).│
│ Level 2 │ LEVEL_2_HISTORICAL_BASELINE  │ 0.4-1.0│ HEURISTIC │ M0 median hierarchy.     │
│         │                              │        │           │ Reflects pooling level.  │
│ Level 3 │ LEVEL_3_EXPERIMENTAL_RF      │ 0.70   │ HEURISTIC │ Random Forest model with │
│         │                              │        │           │ conformal intervals.     │
│ Level 4 │ LEVEL_4_GTFS_SCHEDULED       │ 0.30   │ HEURISTIC │ Unobserved corridor;     │
│         │                              │        │           │ static timetable applied.│
│ Level 5 │ LEVEL_5_STATIC_FALLBACK      │ 0.10   │ HEURISTIC │ Missing timetable; 15km/h│
│         │                              │        │           │ Euclidean distance proxy.│
└─────────┴──────────────────────────────┴────────┴───────────┴──────────────────────────┘
```

### Detailed Breakdown of Tiers

#### Level 1: `LEVEL_1_DIRECT_OBSERVED`
- **Heuristic Score:** `1.0`
- **Score Type:** `HEURISTIC` (Not a calibrated probability).
- **Meaning:** Represents direct empirical support from $N=136$ GPS stop-crossing observations on the North GT Road corridor where sample count $n \ge 3$.
- **Limitations:** Limited to October 2026 conditions on Route 1598. Does not guarantee on-time arrival during unforeseen weather, incidents, or detours.

#### Level 2: `LEVEL_2_HISTORICAL_BASELINE_M0`
- **Heuristic Score:** Tier 1: `1.0` | Tier 2: `0.8` | Tier 3: `0.6` | Tier 4: `0.4`
- **Score Type:** `HEURISTIC` (Not a calibrated probability).
- **Meaning:** Represents historical median travel time from the M0 hierarchical baseline. Scores monotonically decrease as the model falls back from line-stop-hour (Tier 1) to pooled physical stops (Tier 2), corridor velocity (Tier 3), and default velocity (Tier 4).
- **Limitations:** Heuristic weighting scale indicating degrees of aggregation and pooling; no statistical likelihood is asserted.

#### Level 3: `LEVEL_3_EXPERIMENTAL_RF`
- **Heuristic Score:** `0.70`
- **Score Type:** `HEURISTIC` (Disabled by default via `use_experimental_ml = False`).
- **Meaning:** Candidate machine learning model (Random Forest) producing point estimates and conformal prediction intervals.
- **Limitations:** Although conformal calibration provides statistical coverage radii under exchangeability, the point confidence score is a heuristic ordinal rank, NOT an empirical probability.

#### Level 4: `LEVEL_4_GTFS_SCHEDULED`
- **Heuristic Score:** `0.30`
- **Score Type:** `HEURISTIC` (Low confidence).
- **Meaning:** Applied to all unobserved corridors across Delhi where scheduled timetable duration is strictly positive (`sched_duration_s > 0`).
- **Limitations:** Low confidence because static schedules fail to capture Delhi traffic delays and recurring congestion. A warning is attached to every prediction.

#### Level 5: `LEVEL_5_STATIC_FALLBACK`
- **Heuristic Score:** `0.10`
- **Score Type:** `HEURISTIC` (Extreme low confidence).
- **Meaning:** Applied when GTFS schedule data is missing or non-positive ($\le 0\text{s}$), estimating travel time via Euclidean stop distance divided by $15\text{ km/h}$ ($4.167\text{ m/s}$) bus velocity.
- **Limitations:** Highly speculative proxy calculation.

---

## 4. Conclusion and Status

All confidence metrics have been corrected and documented. Unsupported production readiness claims have been removed. System status remains firmly governed under **DEGRADE**.

**Operational Status:** **PASS (Under DEGRADE Scope)**.

