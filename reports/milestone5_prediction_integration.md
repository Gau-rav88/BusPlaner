# Milestone 5 Prediction Integration Report: 4-Tier Hierarchy & Provenance Integrity

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5 – Journey Planner & RAPTOR Implementation  
**Status:** COMPLETE (Under Governing Status DEGRADE)  
**Date:** 2026-11-21  

---

## 1. Provenance and Scope Constraints

Under the governing **DEGRADE** operational status established in Milestone 2.2.1 and maintained through Milestones 3, 3.1, and 4, empirical traffic predictions are strictly bounded by available ground-truth evidence:
- **Spatial Scope:** Empirical ground truth is confined exclusively to the **North GT Road corridor** (Route 1598, Route 1445, and Route 1657; physical stops 239–251 and 1194–1201).
- **Temporal Scope:** Bounded by the 5-date pilot dataset (October 1, 2, 3, 4, and 7, 2026; $N=136$ consecutive-stop segments).
- **Network Reality:** The remaining $>2,900$ bus routes and $>6,300$ stops across Delhi have zero GPS observations in the active serving environment.

The journey planner must never fabricate real-time predictions for unobserved routes, and must never claim network-wide machine learning coverage.

---

## 2. The 4-Tier Prediction Hierarchy

To bridge the gap between empirical corridor evidence and city-wide routing, `backend/core/journey_planner.py` implements a disciplined **4-tier prediction hierarchy**:

```
[ Transit Leg Segment Query: (Route R, Stop A -> Stop B, Timestamp T) ]
                                |
                                v
             +-------------------------------------+
             | Level 1: Observed Ground Truth?     |----> YES: Level 1 (Confidence = 1.0)
             | - Stop pair in North GT Road cache  |     Median of observed crossings
             | - Sample count >= 3                 |
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 2: M0 Historical Baseline?    |----> YES: Level 2 (Confidence = 0.8)
             | - Physical stop pair pooled         |     Co-running route median
             | - Sample count >= 3                 |
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 3: Corridor Speed Baseline?   |----> YES: Level 3 (Confidence = 0.6)
             | - Hourly velocity on North GT Road  |     Hourly corridor speed
             +-------------------------------------+
                                | NO
                                v
             +-------------------------------------+
             | Level 4: Static Timetable Fallback  |----> Level 4 (Confidence = 0.3)
             | - Unobserved Delhi transit corridor |     Scheduled GTFS running time
             | - Detour factor 1.262 FORBIDDEN     |     Mandatory Low Confidence Warning
             +-------------------------------------+
```

### 2.1 Level 1: Direct Observed Ground Truth
- **Criteria:** Segment stop pair $(s_{\text{from}}, s_{\text{to}})$ exists in the Parquet ground truth cache with $n \ge 3$ verified crossings.
- **Output:** Exact historical median segment time, 10th percentile, and 90th percentile bounds.
- **Confidence Score:** $1.00$.
- **Warning:** `None`.

### 2.2 Level 2: Corridor-Pooled Historical Baseline (M0)
- **Criteria:** Physical stop pair on North GT Road pooled across co-running routes (e.g., Route 1445 sharing stops 240–246 with Route 1598) with $n \ge 3$.
- **Output:** Pooled median segment travel time from `HistoricalMedianBaseline.tier2_stats`.
- **Confidence Score:** $0.80$.
- **Warning:** `"Pooled across co-running lines on matching physical stop pair."`

### 2.3 Level 3: Corridor-Level Velocity Baseline (M0)
- **Criteria:** Segment is located within the North GT Road corridor, but specific stop pair has $<3$ direct samples; hourly corridor velocity applies.
- **Output:** Distance divided by hourly median speed.
- **Confidence Score:** $0.60$.
- **Warning:** `"Corridor-level hourly speed fallback applied."`

### 2.4 Level 4: Static Timetable Fallback
- **Criteria:** Any segment outside the North GT Road corridor (comprising $>99\%$ of the Delhi transit network).
- **Output:** Scheduled GTFS running time directly ($\Delta t_{\text{sched}} = \text{arr}_{\text{sched}} - \text{dep}_{\text{sched}}$).
- **Confidence Score:** $0.30$.
- **Warning:** `"Unobserved corridor: static GTFS timetable fallback applied. Low confidence."`

---

## 3. Strict Detour Factor Isolation

A critical finding from Milestones 2.2.1 and 3.1 is that the empirical detour factor ($k_{\text{detour}} = 1.262$) was calibrated strictly on the straight-line topology vs road geometry of the **North GT Road arterial corridor**.

### Mandatory Invariant: No Global Scaling
Applying $k = 1.262$ across winding residential streets, congested ring roads, or ring railway transfers elsewhere in Delhi would artificially inflate timetable estimates by $26.2\%$ without empirical justification.

The implementation in `backend/core/journey_planner.py` enforces:
1. `predict_segment` applies $k = 1.262$ **only** within `HistoricalMedianBaseline` for North GT Road.
2. For Level 4 Timetable Fallbacks, the engine uses the GTFS timetable running time directly without multiplying by $1.262$.
3. Verified in automated test `test_detour_factor_safety_and_dwell_consistency`.

---

## 4. Empirical Evaluation Distribution

In the 50-query benchmark evaluation (`data/processed/milestone5_metrics.json`), 132 transit legs were evaluated across the network:

| Prediction Level | Category | Leg Count | Share (%) | Mean Confidence | Typical Corridor |
|---|---|---:|---:|---:|---|
| **Level 1** | Direct Observed Ground Truth | 72 | 54.55% | 1.00 | North GT Road (Stops 239–251) |
| **Level 2** | Corridor-Pooled M0 Baseline | 0 | 0.00% | 0.80 | Co-running North GT Road lines |
| **Level 3** | Corridor Velocity Baseline | 0 | 0.00% | 0.60 | North GT Road timepoint bins |
| **Level 4** | Static Timetable Fallback | 60 | 45.45% | 0.30 | Central, South, and Outer Delhi |
| **Total** | All Transit Legs | **132** | **100.00%** | **0.68** | Delhi Metropolitan Area |

---

## 5. Dwell Time Semantics and Delay Propagation

### 5.1 Dwell Time Consistency
In the Delhi Mobility Database GTFS feed (`/tmp/delhi_mdb.db`), across all 3,276,092 stop_times rows:
$$\text{arrival\_sec} \equiv \text{departure\_sec} \quad (100.0\%\text{ of rows})$$
There is zero scheduled dwell time in the feed. Concurrently, empirical ground-truth observations ($N=136$) were extracted arrival-to-arrival between consecutive stops. Therefore:
- The segment travel time inherently includes dwell at the intermediate stop.
- Adding a separate synthetic dwell time would violate the ground truth target definition and double-count waiting time.
- The journey planner preserves the arrival-to-arrival definition:
  $$\text{AlightTime} = \text{BoardTime} + \text{PredictedRideTime}$$

### 5.2 Delay Propagation to Connecting Trips
When traffic prediction increases the ride time on leg $i$:
1. The passenger arrives at the transfer platform at $T_{\text{reach}} = T_{\text{board}} + \text{PredictedRideTime} + \text{TransferWalk}$.
2. If the connecting bus departs at $T_{\text{connect}} < T_{\text{reach}} + 120.0\text{s}$, the connection is physically missed.
3. The engine automatically advances to the next available departure on that route pattern satisfying $T'_{\text{connect}} \ge T_{\text{reach}} + 120.0\text{s}$.
4. The transfer wait is updated to $T'_{\text{connect}} - T_{\text{reach}}$, preserving the exact total journey time and accounting identity.

