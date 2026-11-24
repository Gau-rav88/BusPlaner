# Milestone 3.1 Observation Independence Audit Report (Revised)

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 3.1.1 – Statistical Audit Corrections  
**Status:** **AUDITED & VERIFIED (DEGRADE STATUS)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone3_1_audit_metrics.json`  

---

## 1. Executive Summary & Ground-Truth Scope

This revised audit report establishes exact terminology, inventories all ground-truth transit units across the 5-date pilot dataset, details the status of co-running routes including **Route 1657**, and evaluates the statistical independence of observations.

### 1.1 Strict Ground-Truth Terminology & Inventory
To ensure complete referential consistency across all reports and codebases, the hierarchy of ground-truth physical units is defined as follows:

```
+--------------------------------------------------------------------------------------------------+
| Unit Type                            | Exact Count | Definition & Source                         |
+--------------------------------------------------------------------------------------------------+
| Observed Stop Crossings              | 199         | Timestamped vehicle arrival events at GTFS   |
|                                      |             | physical stop locations via linear interp.   |
+--------------------------------------------------------------------------------------------------+
| Observed Stop-to-Stop Segments       | 136         | Consecutive crossing pairs forming complete  |
|                                      |             | travel-time link observation intervals.     |
+--------------------------------------------------------------------------------------------------+
| Distinct Physical Stop Pairs         | 26          | Unique (stop_id_from, stop_id_to) physical  |
|                                      |             | transit links along verified route patterns. |
+--------------------------------------------------------------------------------------------------+
| Unique Ingested Vehicles             | 31          | Distinct bus registration numbers.           |
+--------------------------------------------------------------------------------------------------+
| Verified Route IDs                   | 3           | Route 1598 (124 obs), Route 1445 (11 obs),   |
|                                      |             | Route 1657 (1 obs).                         |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Route Scope & Accounting of Route 1657

In the Milestone 2.2.1 and Milestone 3 discovery audits, Route 1657 appeared with a single observation. This audit clarifies its operational and data status:

### 2.1 Route 1657 Record Audit
- **Observation ID:** `DL1PD9231_c1657_seg0003_s3_to_s4`
- **Vehicle ID:** `DL1PD9231`
- **Service Date:** October 3, 2026 (13:23:14 IST to 13:27:47 IST)
- **Assigned Split:** **Training Partition ($n=84$)**
- **Pattern & Segment:** `1657_dir0_pat0_seq3` (Stop 242: *Sarai Peepal Thala* $\to$ Stop 1245: *Jahangirpuri GT Road*)
- **Distance:** $691.23\text{ meters}$
- **Travel Time & Speed:** $273.26\text{ seconds}$ ($9.11\text{ km/h}$)
- **Quality Status:** `VALID_SEGMENT` (confidence $= 0.70$)

### 2.2 Operational Context & Why It Must Be Included
Route 1657 is a co-running line that shares physical infrastructure with Route 1598 along North GT Road between Azadpur and Jahangirpuri. On October 3, vehicle `DL1PD9231` was map-matched to this pattern. 

Because Route 1657 traverses the exact same physical roadway as `1598_dir0_pat0_seq8`, its crossing interval represents valid ground truth on the pilot corridor. It was retained in the training partition, where it correctly informs Tier 2 pooled stop-pair statistics and corridor-level velocity aggregates. However, because no additional Route 1657 trips passed map-matching thresholds on October 4 or October 7, it had zero observations in validation or test partitions. It is not excluded from the training data.

```
Route Representation Across Splits:
- Route 1598: 80 Train | 22 Val | 22 Test | Total: 124 segments (91.18%)
- Route 1445:  3 Train |  0 Val |  8 Test | Total:  11 segments  (8.09%)
- Route 1657:  1 Train |  0 Val |  0 Test | Total:   1 segment   (0.74%)
Total:        84 Train | 22 Val | 30 Test | Total: 136 segments (100.0%)
```

---

## 3. Partition Inventory & Chronological Boundary Audit

The dataset consists of 136 ground-truth consecutive-stop segments extracted across 5 dates in October 2026, partitioned strictly by service date:

| Split | Service Dates | Day Types | Segments ($n$) | Share |
| :--- | :--- | :--- | :---: | :---: |
| **Train** | 2026-10-01, 2026-10-02, 2026-10-03 | Thu, Fri (Gandhi Jayanti), Sat | 84 | $61.76\%$ |
| **Validation** | 2026-10-04 | Sunday | 22 | $16.18\%$ |
| **Test** | 2026-10-07 | Wednesday (Partial-Day Outage) | 30 | $22.06\%$ |
| **Total** | 5 Distinct Dates | 4 Weekdays / 1 Weekend | **136** | **100.0%** |

### 3.1 Chronological Boundary Verification
Timestamps were audited in UTC to verify non-overlapping temporal windows:
- $\max(t_{\text{Train}}) = \text{2026-10-03 16:43:30 UTC} \quad (1,791,042,610.14\text{s})$
- $\min(t_{\text{Val}}) = \text{2026-10-04 02:49:05 UTC} \quad (1,791,078,945.38\text{s})$
- $\max(t_{\text{Val}}) = \text{2026-10-04 14:11:04 UTC} \quad (1,791,119,864.59\text{s})$
- $\min(t_{\text{Test}}) = \text{2026-10-07 04:07:52 UTC} \quad (1,791,342,872.32\text{s})$

$$\max(t_{\text{Train}}) < \min(t_{\text{Val}}) < \max(t_{\text{Val}}) < \min(t_{\text{Test}})$$

> [!IMPORTANT]
> Chronological leakage prevention is **strictly satisfied**. There is zero forward-looking timestamp leakage across splits.

---

## 4. Vehicle Independence Audit

### 4.1 Mutual Exclusivity Across Splits
An exhaustive audit of the 31 unique vehicle IDs across the 136 observations yielded the following cross-split inventory:

| Partition Comparison | Split A Vehicles | Split B Vehicles | Overlapping Vehicle IDs | Overlap Count |
| :--- | :---: | :---: | :---: | :---: |
| **Train vs. Validation** | 21 | 3 | $\emptyset$ | **0** |
| **Train vs. Test** | 21 | 7 | $\emptyset$ | **0** |
| **Validation vs. Test** | 3 | 7 | $\emptyset$ | **0** |
| **Three-Way Intersection** | 21 | 3 | 7 | $\emptyset$ | **0** |
| **Union (Global Distinct)** | — | — | — | **31** |

> [!NOTE]
> Every vehicle in the dataset operated on exactly one date within the ground-truth set. There are **zero repeated vehicles across partitions**.

### 4.2 Intra-Split Vehicle Clustering
While vehicle IDs are strictly disjoint *across* splits, individual vehicles performed multiple trips and crossed consecutive stops *within* a split:
- **Train ($n=84, 21\text{ vehicles}$):** Average $4.00$ observations/vehicle.
  - Top vehicles: `DL51EV8634` (9 obs), `DL51EV3776` (9 obs), `DL51EV3533` (8 obs).
- **Validation ($n=22, 3\text{ vehicles}$):** Average $7.33$ observations/vehicle.
  - Top vehicles: `DL51EV3788` (12 obs), `DL1PD5209` (6 obs), `DL51EV3878` (4 obs).
- **Test ($n=30, 7\text{ vehicles}$):** Average $4.29$ observations/vehicle.
  - Top vehicles: `DL51EV4080` (9 obs), `DL51EV3114` (7 obs), `DL51EV1844` (4 obs), `DL51EV1973` (4 obs).

This clustering means observations generated by the same vehicle share driver behavior, acceleration profiles, and trip-level delay propagation.

---

## 5. Stop-Pair Independence Audit

Because the pilot focused on the North GT Road corridor, the same road links are repeatedly traversed across different dates:

### 5.1 Stop-Pair Overlap Summary
- **Total Unique Stop Pairs Globally:** 26
- **Train Stop Pairs:** 23
- **Validation Stop Pairs:** 15 (14 overlap with Train, 1 unique)
- **Test Stop Pairs:** 14 (12 overlap with Train, 2 unique)
- **Overlap Across All 3 Splits:** 9 stop pairs (`seq1` through `seq7`, `seq9`, `seq10` on Route 1598).
- **Unseen Test Stop Pairs:** Exactly 2 stop pairs in the test partition were never observed in training:
  1. `1445_dir0_pat0_seq2`
  2. `1445_dir0_pat0_seq3`

---

## 6. Chronological Separation vs. Statistical Independence

A core requirement of this audit is distinguishing **leakage prevention** from **statistical independence**:

### 6.1 Chronological Separation Does Not Imply Independent Observations
The pipeline guarantees that no future timestamps enter model training. However, the resulting observations **violate the ordinary independent and identically distributed (i.i.d.) assumption**:
1. **Spatial Autocorrelation:** Fixed physical bottlenecks, intersections, and signal timings along North GT Road correlate travel times across days.
2. **Vehicle Run Clustering:** A single bus traversing multiple stops in sequence introduces auto-correlated errors.
3. **Corridor-Wide Temporal Shocks:** On October 7, the GPS feed outage and evening peak gridlock affected all operating vehicles simultaneously.

### 6.2 Recommended Clustered Evaluation Strategy
For future model validation across the full October historical dataset:
1. **Date-Clustered Cross-Validation:** Group observations into 31 daily clusters. Implement Leave-One-Date-Out (LODO) evaluation so validation residuals and test observations never share calendar dates.
2. **Vehicle-Run Block Conformal Prediction:** Calibrate non-conformity scores at the level of complete vehicle trips (trajectories) rather than isolated individual segments.
3. **Cluster-Robust Variance Estimation:** Report confidence intervals adjusted for two-way clustering by $(\text{service\_date}, \text{segment\_key})$ using sandwich variance estimators.
