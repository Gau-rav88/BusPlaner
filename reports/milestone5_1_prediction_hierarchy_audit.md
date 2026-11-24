# Milestone 5.1 Prediction Hierarchy Audit Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5.1 – Independent Journey Planner Audit  
**Status:** COMPLETE (Under Governing Status DEGRADE)  
**Date:** 2026-11-21  

---

## 1. Executive Summary & Verification Objectives

This audit independently evaluates the multi-tier travel-time prediction hierarchy implemented in `backend/core/journey_planner.py`. Under the governing **DEGRADE** status, empirical observations from historical GPS data are strictly bounded to the North GT Road pilot corridor ($N=136$ consecutive-stop segments across 5 dates in October 2026). Over $99\%$ of the Delhi transit network is unobserved in historical GPS logs.

The audit verified whether:
1. All five intended prediction levels exist distinctly in code.
2. The candidate Random Forest ML model is disabled by default.
3. Every prediction records its data source, confidence score, and fallback reason.
4. The empirical North GT Road detour factor ($k_{\text{detour}} = 1.262$) is isolated strictly to its calibrated scope.
5. Unobserved corridor timetables and static fallbacks are never falsely presented as observed or real-time predictions.

---

## 2. Five-Tier Hierarchy Implementation & Audit Findings

The audit confirmed that `predict_segment` in `backend/core/journey_planner.py` implements five distinct, mutually exclusive prediction levels:

```
[ Transit Leg Segment Query: (Route R, Stop A -> Stop B, Timestamp T) ]
                                |
                                v
             +-------------------------------------+
             | Level 1: Observed Ground Truth?     |----> YES: Level 1 (Confidence = 1.0)
             | - Stop pair in North GT Road cache  |     Source: GROUND_TRUTH_OBSERVED
             | - Sample count >= 3                 |     is_fallback: False
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 2: M0 Historical Baseline?    |----> YES: Level 2 (Confidence = 0.8..0.4)
             | - Physical stop pair / corridor     |     Source: M0_TIER_1..4
             | - North GT Road corridor lines      |     is_fallback: True (except Tier 1)
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 3: Experimental RF Enabled?   |----> YES: Level 3 (Confidence = 0.7)
             | - use_experimental_ml == True       |     Source: M2_RANDOM_FOREST
             | - Conformal lower bound >= 5.0s     |     Warning: Candidate Model Tag
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 4: GTFS Timetable Duration?   |----> YES: Level 4 (Confidence = 0.3)
             | - sched_duration_s > 0              |     Source: GTFS_TIMETABLE
             | - Detour factor 1.262 FORBIDDEN     |     Warning: Low Confidence Tag
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 5: Static Distance Fallback   |----> Level 5 (Confidence = 0.1)
             | - sched_duration_s <= 0 or missing  |     Source: STATIC_VELOCITY_FALLBACK
             | - City bus velocity: 15.0 km/h      |     Warning: Extreme Low Confidence
             +-------------------------------------+
```

### Detailed Tier Audit Breakdown

| Level | Tier Identifier | Underlying Mechanism | Default Confidence | Is Fallback | Source Tag | Validation Status |
|---|---|---|---:|:---:|---|:---:|
| **Level 1** | `LEVEL_1_DIRECT_OBSERVED` | Direct historical GPS crossings ($n \ge 3$) on North GT Road | $1.00$ | `False` | `GROUND_TRUTH_OBSERVED` | **VERIFIED** |
| **Level 2** | `LEVEL_2_HISTORICAL_BASELINE_M0` | M0 hierarchical median (Tiers 1–4) on North GT Road | $0.80\text{--}0.40$ | `True`* | `M0_TIER_1..4` | **VERIFIED** |
| **Level 3** | `LEVEL_3_EXPERIMENTAL_RF` | M2 Random Forest regressor with split-conformal bounds ($q = 349.10\text{s}$) | $0.70$ | `False` | `M2_RANDOM_FOREST` | **VERIFIED** |
| **Level 4** | `LEVEL_4_GTFS_SCHEDULED` | Static GTFS timetable duration ($\Delta t_{\text{sched}} > 0$) for unobserved corridors | $0.30$ | `True` | `GTFS_TIMETABLE` | **VERIFIED** |
| **Level 5** | `LEVEL_5_STATIC_FALLBACK` | Distance-based velocity fallback ($15\text{ km/h}$) for missing/corrupt schedule times | $0.10$ | `True` | `STATIC_VELOCITY_FALLBACK` | **VERIFIED** |

*\*Note: Level 2 Tier 1 direct matching carries `is_fallback = False`, whereas Tiers 2–4 carry `is_fallback = True` with explicit fallback reasons.*

---

## 3. Defensive Boundaries and Provenance Safeguards

### 3.1 Gating of Candidate Machine Learning (Level 3)
The governing PRD Section 7 and Milestone 4 audit established that Random Forest (M2) did not demonstrate statistically superior performance over the M0 historical median baseline on out-of-corridor or sparse data.
- **Audit Verification:** In `backend/core/journey_planner.py`, `use_experimental_ml` is parameter-gated and strictly defaults to `False` across all entrypoints (`plan_journey`, `predict_segment`).
- **Safety Rule:** Random Forest predictions are never returned to callers unless explicitly opted into via `use_experimental_ml=True`.

### 3.2 Conformal Prediction Lower-Bound Invariant
In Milestone 3.1.1, the statistical audit proved that naive symmetric conformal intervals $(\hat{y} \pm 349.10\text{s})$ could produce negative physical travel times on short segments.
- **Audit Verification:** Level 3 enforces `lower_b = max(base_pred - q_conformal, 5.0)`. All generated lower bounds are non-negative and satisfy the physical minimum transit duration ($\ge 5.0\text{s}$).

### 3.3 Strict Isolation of the North GT Road Detour Factor ($1.262$)
In Milestone 2.2.1, an empirical detour factor $k = 1.262$ was calibrated against the straight-line stop geometry of the North GT Road corridor.
- **Audit Verification:**
  - In Level 4 (`LEVEL_4_GTFS_SCHEDULED`), the engine returns `predicted_time_s = sched_duration_s` directly. The scheduled time is **never** multiplied by $1.262$.
  - In Level 5 (`LEVEL_5_STATIC_FALLBACK`), velocity is derived from Euclidean stop distance without applying $1.262$.
  - Confirmed via automated test `test_synthetic_unit_prediction_hierarchy_five_distinct_levels`.

### 3.4 Elimination of False Precision / Label Integrity
- Timetable and static fallbacks are **never** labelled as "real-time", "live", or "observed".
- Level 4 explicitly sets `confidence = 0.30`, `is_fallback = True`, and attaches the warning:
  `"Unobserved corridor: static GTFS timetable running time applied. Low confidence."`
- Level 5 explicitly sets `confidence = 0.10`, `is_fallback = True`, and attaches:
  `"Missing or invalid timetable running time: static distance-based fallback applied. Extreme low confidence."`

