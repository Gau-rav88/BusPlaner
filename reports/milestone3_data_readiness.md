# Milestone 3 Data Readiness & Independence Audit Report

**Service Dates Analyzed:** October 1, 2, 3, 4, and 7, 2026 (`2026-10-01` to `2026-10-07`, Pilot Subset)  
**Evaluated Dataset:** `data/processed/stop_crossings/service_date=*/observed_segments.parquet`  
**Pipeline Modules:** `backend/ml/features.py`, `scripts/train_and_evaluate_m3.py`, DuckDB  
**Date of Audit:** November 21, 2026  

---

## 1. Ground-Truth Data Readiness Audit

Prior to baseline formulation and machine learning modeling, a complete data audit was performed across the 5 processed historical partitions to verify sample independence, column completeness, and physical plausibility.

### Dataset Overview
| Audit Dimension | Value / Count | Verification Status | Notes |
| :--- | :---: | :---: | :--- |
| **Total Segment Observations** | **136** | **Verified** | Extracted from consecutive stop crossings bracketed by $\le 120\text{s}$ pings |
| **Distinct Service Dates** | **5** | **Verified** | Oct 1 (Thu), Oct 2 (Fri/Holiday), Oct 3 (Sat), Oct 4 (Sun), Oct 7 (Wed) |
| **Distinct Vehicle Registration IDs** | **31** | **Verified** | Real DTC fleet buses (electric low-floor and CNG) |
| **Distinct Physical Stop Pairs** | **26** | **Verified** | Sequential stops along North GT Road (Azadpur to Alipur) |
| **Distinct GTFS Route IDs** | **3** | **Verified** | Route 1598 (124 segs), Route 1445 (11 segs), Route 1657 (1 seg) |
| **Duplicate `observation_id` Records** | **0** | **Passed** | 100% unique primary keys across all partitions |
| **Missing / Null Feature Values** | **0** | **Passed** | Distance, speed, travel time, and timestamps are 100% populated |
| **Physical Speed Bounds Check** | **Passed** | **Passed** | Min = 1.27 km/h, Max = 44.84 km/h (within $0 < v \le 90\text{ km/h}$) |
| **Travel Time Plausibility Check** | **Passed** | **Passed** | Min = 21.45 s, Median = 107.93 s, Max = 1,779.14 s (Mukarba peak jam) |
| **Distance Bounds Check** | **Passed** | **Passed** | Min = 156.65 m, Median = 479.85 m, Max = 2,092.36 m |

---

## 2. Sample Independence & Exclusion Rules

To ensure strict scientific validity:
1. **No Synthetic Oversampling:** Zero synthetic observations, jittered duplicates, or interpolated phantom runs were manufactured.
2. **Duplicate Independence:** Trajectory segmentation rules (E05 jump detection, E07 gap splitting $> 300\text{s}$, terminal dwell splitting) ensured that every observation represents an independent physical traversal of a stop-to-stop link.
3. **Data Exclusions Logged:**
   - Observations where ping gap exceeded 120 seconds were rejected during stop-crossing extraction (PRD Section 6.2).
   - Trajectories with lateral offset $> 65\text{m}$ (depot deadheading) were excluded during map matching (PRD Section 6.1).
   - Incomplete stop bracketings ($< 2$ consecutive stops) were retained as single stop crossings (199 total) but excluded from consecutive running segment modeling (136 total).

---

## 3. Data Provenance Categorization

Every segment observation is mapped to its exact data provenance tier:

| Provenance Category | Segment Count | Share (%) | Verification Method |
| :--- | :---: | :---: | :--- |
| **Direct Empirical Observation (Tier 1)** | **124** | 91.18% | Linear interpolation between hardware GPS pings along Route 1598 |
| **Co-Running Corridor Pooled (Tier 2)** | **11** | 8.09% | Route 1445 observations sharing physical road geometry along North GT Road |
| **Cross-Line Tangent Segment (Tier 2/3)** | **1** | 0.74% | Route 1657 observation traversing common GT Road stop pair |
| **Derived / Synthesized Records** | **0** | 0.00% | **Zero manufactured data permitted in training set** |
| **Total Ground Truth Observations** | **136** | **100.00%** | **Strict empirical basis** |

---

## 4. Modeling Suitability Assessment

- **Sufficiency for Corridor Baseline:** 136 observations across 26 stop pairs and 5 dates are sufficient to construct a robust, empirical **Historical Median Baseline (M0)** for North GT Road.
- **Sufficiency for Complex ML:** 136 samples is a **small dataset for high-parameter machine learning**. Fitting complex models risks overfitting. Therefore, ML candidate models (Ridge M1, Random Forest M2) must be evaluated with strict chronological holdout gates, and retained only if they demonstrate genuine, statistically defensible error reductions over M0 without data leakage.

