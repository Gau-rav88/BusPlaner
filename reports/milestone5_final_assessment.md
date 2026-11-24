# Milestone 5 Final Assessment & Synthesis Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5 – Journey Planner & RAPTOR Implementation  
**Status:** COMPLETE (Under Governing Status DEGRADE)  
**Date:** 2026-11-21  

---

## 1. Milestone Objectives and Final Verdict

Milestone 5 tasked the engineering team with designing, implementing, and validating a full-scale public transit journey planner using the **RAPTOR (Round-Based Public Transit Routing)** algorithm, connecting transit routing to the historical traffic models and prediction hierarchy developed in Milestones 0 through 4.

### Final Verdict: ACCEPTED (Under Governing Status DEGRADE)

All technical requirements, acceptance criteria, accounting identities, and defensive boundaries defined in **PRD v3.0 Section 8** and the Milestone 5 specification have been fully satisfied and validated through 51 passing automated tests.

---

## 2. Acceptance Criteria Verification Matrix

| # | Acceptance Criterion | Verification Method | Result | Status |
|---|---|---|---|:---:|
| 1 | **RAPTOR Transit Routing** | Implemented in `backend/core/raptor.py` with route patterns, stop-to-pattern indices, and bounded rounds | Direct (0 transfers), 1-transfer, and 2-transfer journeys verified | PASS |
| 2 | **Full GTFS Integration** | Evaluated on full Mobility Database GTFS dataset (`/tmp/delhi_mdb.db`) | 6,342 stops, 2,964 routes, 78,507 trips, 2,473 patterns | PASS |
| 3 | **Walking Access & Egress** | Projected UTM 43N KDTree lookup with $800\text{m}$ radius (expanded to $1,500\text{m}$) and $4.5\text{ km/h} \times 1.3$ detour | Verified in `test_coordinate_to_coordinate_routing` | PASS |
| 4 | **Transfer Connections** | Precomputed 36,640 footpaths ($\le 400\text{m}$) with $4.5\text{ km/h} \times 1.3$ detour | Verified in `test_timetable_loading_and_patterns` | PASS |
| 5 | **Transfer Buffer Guarantee** | Strict minimum transfer buffer $\ge 120\text{ seconds}$ enforced on all connections | 100.0% pass rate across 44 transfer connections | PASS |
| 6 | **Post-Midnight Trips** | Linear time indexing supporting GTFS departures with $t \ge 86,400\text{s}$ | Verified on Pattern 0 (arrives $86,901\text{s}$) | PASS |
| 7 | **4-Tier Prediction Hierarchy** | Direct Observed (L1) $\to$ Pooled (L2) $\to$ Speed (L3) $\to$ Timetable Fallback (L4) | Verified in `test_prediction_hierarchy_integration` | PASS |
| 8 | **Provenance Integrity** | Detour factor $1.262$ isolated to North GT Road; unobserved routes use timetable directly | Verified in `test_detour_factor_safety_and_dwell` | PASS |
| 9 | **Dwell Time Consistency** | No double counting; segment running time is arrival-to-arrival | Verified zero scheduled dwell in Delhi GTFS | PASS |
| 10 | **Journey Time Accounting** | $\text{Total} \equiv \text{AccessWalk} + \text{InitWait} + \sum \text{Ride} + \sum \text{TransWalk} + \sum \text{TransWait} + \text{EgressWalk}$ | Discrepancy $\equiv 0.0000\text{s}$ on 100.0% of journeys | PASS |
| 11 | **No-Service / Edge Cases** | Graceful empty return `[]` on impossible destinations or remote coordinates | Verified in `test_no_service_and_unreachable_cases` | PASS |
| 12 | **Query Performance** | Mean latency $< 500\text{ ms}$; config budget $< 3,000\text{ ms}$ | Mean: $94.27\text{ ms}$, Median: $108.49\text{ ms}$, P95: $192.91\text{ ms}$ | PASS |
| 13 | **Automated Test Suite** | 12 tests in `test_milestone5.py`; 51 tests total across codebase | 51 passed in $14.39\text{s}$ (100% pass) | PASS |

---

## 3. Summary of Project Milestones (0 through 5)

With the completion of Milestone 5, the entire backend transit prediction and journey planning pipeline is fully functional and validated:

```
[ Milestone 0 ] Discovery & Schema Audit (Discovered 100-row sample limitation)
       |
[ Milestone 1 ] Data Ingestion & Full Mobility Database Ingestion (3.27M stop_times)
       |
[ Milestone 2 / 2.1 / 2.2 / 2.2.1 ] Map Matching, Ground Truth Extraction (5-date pilot dataset)
       |
[ Milestone 3 / 3.1 / 3.1.1 ] Historical Traffic Statistical Baseline M0 & ML Validation
       |
[ Milestone 4 ] Extended Chronological Validation (Held-out Test Oct 7; MAPE filtering resolved)
       |
[ Milestone 5 ] RAPTOR Transit Routing & 4-Tier Prediction Integration (COMPLETE)
```

---

## 4. Remaining Limitations & Governing Status Recommendation

### 4.1 Known Empirical Limitations
1. **Pilot Dataset Scope:** Empirical ground truth is restricted to 5 dates (Oct 1, 2, 3, 4, 7, 2026) along the North GT Road corridor ($N=136$ consecutive-stop segments across Routes 1598, 1445, and 1657).
2. **Unobserved City Corridors:** Over $99\%$ of bus routes in Delhi operate under **Level 4 Timetable Fallback** ($45.45\%$ of evaluated test legs), which relies on static GTFS schedule times with a conservative confidence score of $0.30$.
3. **Host Storage Feasibility:** The primary APFS host container has $11.5\text{ GiB}$ free space, which safely supports the serving databases and Parquet partitions but precludes decompressing the remaining $115.5\text{ GiB}$ raw GPS archive.
4. **Time-Profile Comparisons:** Quiet-hour comparisons are restricted to corridors with genuine empirical observations (Levels 1–2). The engine explicitly refuses to invent comparisons for unobserved corridors.

### 4.2 Recommendation on Governing Status
The governing status must remain **DEGRADE**. While the journey planning engine, RAPTOR algorithm, and prediction integration are technically complete and computationally robust, the underlying empirical traffic coverage remains a focused corridor pilot rather than city-wide ground truth. Transparent communication of confidence levels and data tiers protects end-users from false precision.

---

## 5. Artifact Manifest

All deliverables for Milestone 5 are committed and verified in the repository:

1. **Core Routing & Data Modules:**
   - `backend/core/raptor_data.py`: Timetable, RoutePattern, KDTree spatial indexing, footpath precomputation.
   - `backend/core/raptor.py`: RAPTOR transit routing engine, bounded transfer rounds, journey reconstruction.
   - `backend/core/journey_planner.py`: High-level JourneyPlanner, 4-tier prediction hierarchy, accounting verification, time-profile comparison.
2. **Automated Test Suite:**
   - `backend/tests/test_milestone5.py`: 12 comprehensive unit and integration tests (100% pass).
   - Full test suite: 51 tests in `backend/tests/` passing in $14.39\text{s}$.
3. **Metrics & Evaluation Artifacts:**
   - `scripts/run_milestone5_evaluation.py`: Benchmark runner across 50 queries.
   - `data/processed/milestone5_metrics.json`: Full benchmark metrics and accounting audit.
4. **Documentation & Reports:**
   - `reports/milestone5_architecture.md`: System architecture and data structures.
   - `reports/milestone5_routing_validation.md`: Functional correctness and edge-case validation.
   - `reports/milestone5_prediction_integration.md`: 4-tier hierarchy and provenance integrity.
   - `reports/milestone5_performance.md`: Query latency and algorithmic benchmarks.
   - `reports/milestone5_final_assessment.md`: Synthesis and final assessment.

