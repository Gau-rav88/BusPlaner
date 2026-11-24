# Milestone 5 Architecture Report: RAPTOR Transit Routing Engine & Prediction Integration

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5 – Journey Planner & RAPTOR Implementation  
**Status:** COMPLETE (Under Governing Status DEGRADE)  
**Date:** 2026-11-21  

---

## 1. Executive Summary

Milestone 5 implements a production-grade, transit-aware journey planner for Delhi using the **RAPTOR (Round-Based Public Transit Routing)** algorithm, strictly conforming to the specifications of **PRD v3.0 Section 8**. The engine directly addresses the limitations of standard graph search algorithms (e.g., Dijkstra or $A^*$) by natively operating on transit timetables, trip stop patterns, boarding times, service calendars, and bounded transfer rounds.

Furthermore, Milestone 5 connects transit routing directly to the empirical traffic models established in Milestones 2 through 4, enforcing a strict **4-tier prediction hierarchy**, non-decreasing timelines, and an exact mathematical **Journey-Time Accounting Identity** holding to the second.

```
+-----------------------------------------------------------------------------------+
|                            Journey Planning Architecture                          |
+-----------------------------------------------------------------------------------+
                                          |
                   [ Origin & Destination (Stops / Coordinates) ]
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 1. Spatial & Access Layer (pyproj EPSG:32643 UTM 43N + scipy KDTree)             |
|    - Default radius: 800m (expanded to 1500m if no stops within 800m)             |
|    - Walking speed: 4.5 km/h, Detour factor: 1.3 (Effective: 0.9615 m/s)          |
|    - Precomputed Transfer Footpaths: 36,640 pairs (<= 400m)                       |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. Core RAPTOR Engine (backend/core/raptor.py)                                    |
|    - Round 1 (Direct Transit, 0 Transfers)                                        |
|    - Round 2 (One Transfer, 1 Transfer)                                           |
|    - Round 3 (Two Transfers, 2 Transfers)                                         |
|    - Transfer Buffer: Strictly >= 120s enforced on all connections                |
|    - Timeline: Post-midnight trips (t >= 86400s) supported linearly               |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. Traffic Prediction Hierarchy (backend/core/journey_planner.py)                 |
|    - Level 1: Observed Ground Truth (North GT Road corridor, Conf = 1.0)          |
|    - Level 2: Historical Median Baseline M0 (Corridor Pooled, Conf = 0.8)         |
|    - Level 3: Candidate ML Model M2 Random Forest (Experimental Mode)             |
|    - Level 4: Timetable Fallback (Unobserved Corridors, Conf = 0.3, Low Conf Tag) |
|    - Safety Invariant: Detour factor 1.262 strictly isolated to corridor          |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 4. Journey-Time Accounting Identity & Ranking                                     |
|    - Total = AccessWalk + InitialWait + sum(Ride) + sum(TransWalk)                |
|            + sum(TransWait) + EgressWalk                                          |
|    - Verification: Discrepancy == 0.0s across 100% of planned itineraries         |
|    - Ranking: earliest_arrival, fewest_transfers, least_walking, most_reliable    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Timetable Data Representation (`backend/core/raptor_data.py`)

Transit networks possess intrinsic structure that standard flat graphs fail to capture: buses run along predetermined sequences of stops at fixed departure times without overtaking. RAPTOR leverages this structure through **Route Patterns**.

### 2.1 Route Pattern Grouping
Trips are partitioned into route patterns where every trip in a pattern shares the exact ordered sequence of stop IDs:
- In the full Mobility Database dataset (`/tmp/delhi_mdb.db`), 78,507 trips across 2,964 routes are partitioned into **2,473 distinct stop patterns**.
- For each pattern $p$, trips are sorted in ascending order of departure time at the origin stop $s_0$.
- Timetable arrays are stored as dense, contiguous 2D NumPy matrices:
  - `deps_matrix`: Shape $(N_{\text{trips}}, L_{\text{pattern}})$, integer departure seconds.
  - `arrs_matrix`: Shape $(N_{\text{trips}}, L_{\text{pattern}})$, integer arrival seconds.
- Earliest trip boarding lookup at stop index $i$ at or after timestamp $\tau$ is executed via vectorized binary search (`np.searchsorted(deps_matrix[:, i], tau)`), achieving $O(\log N_{\text{trips}})$ complexity per pattern evaluation.

### 2.2 Stop-to-Pattern Indexing
An inverted index maps each physical `stop_id` to a list of tuples `(pattern_id, stop_index)`. This ensures that during round $k$, only route patterns passing through stops marked in round $k-1$ are evaluated, avoiding redundant global network scans.

### 2.3 Spatial Footpath Precomputation
Transfer footpaths between stops are precomputed during timetable initialization:
- Physical stops are projected into metric coordinates using **EPSG:32643 (UTM Zone 43N)**.
- A `scipy.spatial.KDTree` indexes all 6,342 stops.
- `tree.query_pairs(r=400.0)` identifies all stop pairs within the maximum transfer walking distance ($d \le 400\text{ m}$).
- Across Delhi, **36,640 directional transfer footpaths** are generated (mean distance: $206.37\text{ m}$, median distance: $227.26\text{ m}$, max distance: $399.99\text{ m}$).
- Walking time is computed strictly according to PRD Section 8.4:
  $$v_{\text{walk}} = 4.5\text{ km/h} \approx 1.25\text{ m/s}, \quad k_{\text{detour}} = 1.3$$
  $$v_{\text{eff}} = \frac{v_{\text{walk}}}{k_{\text{detour}}} = \frac{4.5 / 3.6}{1.3} \approx 0.961538\text{ m/s}$$
  $$t_{\text{walk}} = \frac{d}{v_{\text{eff}}}$$

---

## 3. Core RAPTOR Routing Algorithm (`backend/core/raptor.py`)

The RAPTOR engine executes in discrete rounds, where Round $k$ computes the earliest arrival times at all stops using at most $k$ transit trips ($k-1$ transfers):
1. **Round 0 (Access Phase):**
   - Resolves origin (stop or coordinate). If coordinate, finds access stops within $r \le 800\text{m}$ (expanded to $1500\text{m}$ if empty) and sets initial arrival $\tau_0(s) = t_{\text{dep}} + t_{\text{walk}}(\text{orig}, s)$.
   - Marks all reachable access stops.
2. **Round $k$ Route Processing:**
   - Accumulates all route patterns passing through marked stops, recording the earliest marked stop index per pattern.
   - For each pattern, traverses stops from the earliest marked index to the end.
   - Evaluates alighting: updates $\tau_k(s)$ if the currently boarded trip reaches $s$ earlier than $\min(\tau_k(s), \tau_{\text{dest\_best}})$.
   - Evaluates boarding: checks whether an earlier trip can be boarded at $s$. For Round $k=1$, departure must satisfy $\text{dep} \ge \tau_0(s)$. For transfer rounds ($k > 1$), departure must satisfy:
     $$\text{dep} \ge \tau_{k-1}(s) + \text{min\_transfer\_buffer\_s} \quad (\ge 120\text{s})$$
3. **Round $k$ Footpath Relaxation:**
   - For every stop $s$ improved by a transit trip in Round $k$, relaxes precomputed footpaths $(s, s')$ with $d \le 400\text{m}$.
   - If $\tau_k(s) + t_{\text{walk}}(s, s') < \tau_k(s')$, updates $\tau_k(s')$ and marks $s'$ for Round $k+1$.
4. **Journey Reconstruction:**
   - Maintains exact backtrack pointers (`backtrack[k][stop_id]`) recording the trip, boarding stop, boarding departure time, alight stop, alight arrival time, and footpath legs.
   - Traverses backwards from destination to origin to build strongly typed `WalkingLeg` and `TransitLeg` sequences.

---

## 4. Prediction Hierarchy Integration (`backend/core/journey_planner.py`)

The journey planner wraps RAPTOR and integrates traffic travel-time predictions across each transit leg:
1. **Level 1 (Direct Observed Ground Truth):**
   - Applies to North GT Road corridor stop pairs (e.g., stops 239–251, 1194–1201) with $\ge 3$ historical GPS observations.
   - Confidence: $1.00$. Warning: `None`.
2. **Level 2 (Corridor Pooled M0 Baseline):**
   - Applies to physical stop pairs on North GT Road pooled across co-running lines.
   - Confidence: $0.80$. Warning: `"Pooled across co-running lines on matching physical stop pair."`
3. **Level 3 (Corridor Speed M0 Baseline):**
   - Applies hourly North GT Road corridor velocity where specific stop pairs are unobserved.
   - Confidence: $0.60$. Warning: `"Corridor-level hourly speed fallback applied."`
4. **Level 4 (Timetable Fallback):**
   - Applies to all unobserved transit corridors across the wider Delhi metropolitan region.
   - Confidence: $0.30$. Warning: `"Unobserved corridor: static GTFS timetable fallback applied. Low confidence."`
   - **Crucial Architectural Invariant:** The empirical detour factor ($k_{\text{detour}} = 1.262$) calibrated on the North GT Road corridor is strictly isolated and **NEVER** applied network-wide to unobserved corridors. Unobserved corridors use scheduled GTFS running times directly.

---

## 5. Strict Journey-Time Accounting Identity

In accordance with PRD Section 8.6, every journey generated by the planner must satisfy:

$$\text{TotalJourneyTime} = \text{AccessWalk} + \text{InitialWait} + \sum \text{RideTime} + \sum \text{TransferWalk} + \sum \text{TransferWait} + \text{EgressWalk}$$

The engine calculates:
- $\text{AccessWalk}$: Walk time from origin coordinate to initial boarding stop ($0.0\text{s}$ if origin is a stop).
- $\text{InitialWait} = T_{\text{board\_first\_bus}} - (T_{\text{query}} + \text{AccessWalk}) \ge 0.0\text{s}$.
- $\text{RideTime} = T_{\text{alight}} - T_{\text{board}} > 0.0\text{s}$ for each transit leg.
- $\text{TransferWalk}$: Walk time across transfer footpaths ($0.0\text{s}$ if platform transfer at same stop).
- $\text{TransferWait} = T_{\text{board\_next\_bus}} - (T_{\text{alight\_prev}} + \text{TransferWalk}) \ge 120.0\text{s}$.
- $\text{EgressWalk}$: Walk time from final alight stop to destination coordinate ($0.0\text{s}$ if destination is a stop).
- $\text{Discrepancy} = \text{TotalJourneyTime} - \text{SumOfComponents} \equiv 0.0000\text{s}$.

No double counting of dwell or transfer buffer occurs. If traffic delay increases running time on leg $i$, the passenger reaches the transfer stop later; the planner shifts the connecting boarding to the next feasible trip satisfying the $\ge 120\text{s}$ buffer, preserving physical realism and temporal continuity.

