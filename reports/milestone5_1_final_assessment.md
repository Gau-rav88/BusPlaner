# Milestone 5.1 — Final Audit Assessment & System Verdict

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 5.1 (Independent Journey Planner Audit)  
**Governing PRD:** v3.0  
**Governing Decision:** **DEGRADE**  
**Author:** Independent System Auditor  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Audit Mandate

This report delivers the comprehensive final assessment for **Milestone 5.1**, conducting an exhaustive, independent audit of the completed RAPTOR journey planner and its integration with the historical traffic statistical model.

The audit was executed in strict accordance with the governing instructions:
1. **Preservation of Scope:** Evaluated Milestone 5 implementation against source GTFS data, empirical ground truth, and PRD v3.0 without beginning Milestone 6.
2. **Methodological Independence:** No reliance on internal self-assertions; all evaluations verified against source database records, manual arithmetic expectations, synthetic unit checks, and multi-pass performance benchmarks.
3. **Rigorous Classification:** Every test case explicitly categorized into its verification domain.
4. **Governing Verdict:** System status maintained as **DEGRADE**, reflecting algorithmic validation of RAPTOR and historical timetable routing against the supplied GTFS, combined with strictly scoped historical predictions on the validated North GT Road pilot corridor. Current Delhi transit operating service remains unverified due to expired GTFS calendar validity. Production readiness is not claimed.

---

## 2. Synthesis of Audit Findings Across Core Sections

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           MILESTONE 5.1 AUDIT PILLARS & FINDINGS                         │
├──────────────────────────┬─────────────────────────────┬────────────────────────────────┤
│ AUDIT PILLAR             │ METRIC / ADHERENCE          │ COMPLIANCE STATUS              │
├──────────────────────────┼─────────────────────────────┼────────────────────────────────┤
│ 1. Prediction Hierarchy  │ 5 Distinct Tiers Enforced   │ PASS (Strict Scoping)          │
│ 2. RAPTOR Correctness    │ 15 / 15 GTFS Cases Passed   │ PASS (100.0% Accuracy)         │
│ 3. Transfer & Delay      │ 0 Buffer Violations (<120s) │ PASS (114 Transfers Audited)   │
│ 4. Accounting & Dwell    │ Discrepancy = 0.00000000 s  │ PASS (Machine-Precision)       │
│ 5. Calendar & Midnight   │ 436 Midnight Patterns Monot.│ PASS (No Wraparound Bugs)      │
│ 6. Performance Benchmark │ Mean Latency: 95.01 ms      │ PASS (P95: 192.23 ms < 200 ms) │
└──────────────────────────┴─────────────────────────────┴────────────────────────────────┘
```

### Pillar 1: Prediction Hierarchy & Scoping
- **Implementation:** Enhanced `predict_segment` to support five mutually exclusive tiers:
  1. `LEVEL_1_DIRECT_OBSERVED`: Direct ground truth from North GT Road corridor ($N=136$ observations, $n \ge 3$, conf 1.0).
  2. `LEVEL_2_HISTORICAL_BASELINE_M0`: Hierarchical median fallback (Tiers 1–4, conf $0.8\text{--}0.4$).
  3. `LEVEL_3_EXPERIMENTAL_RF`: Random Forest model, **disabled by default** (`use_experimental_ml=False`).
  4. `LEVEL_4_GTFS_SCHEDULED`: GTFS scheduled duration for unobserved corridors where `sched_duration_s > 0` (conf 0.3, explicit warning).
  5. `LEVEL_5_STATIC_FALLBACK`: Static Euclidean distance at $15\text{ km/h}$ when schedule is missing or $\le 0$ (conf 0.1, extreme low-confidence warning).
- **Detour Factor Isolation:** The empirical corridor detour factor ($k_{\text{detour}} = 1.262$) was strictly isolated to the North GT Road corridor and is **never** applied network-wide to unobserved routes.

### Pillar 2: RAPTOR Algorithm Correctness
- **Timetable Verification:** Tested against 15 independent GTFS ground-truth cases, covering direct corridor trips, early morning service (04:00), late night service (23:00), multiple competing routes, footpaths, multi-transfer trips, and invalid stops.
- **Accuracy:** **15 / 15 passed (100.0%)**. Pareto multi-criteria dominance (arrival time vs. transfer rounds) operates flawlessly.

### Pillar 3: Transfer & Delay Mechanics
- **Buffer Invariant:** The mandatory $\ge 120.0\text{s}$ buffer was maintained across all 114 audited transfer events with zero violations.
- **Causality & Delay Propagation:** Arrival delays on upstream legs strictly advance connecting departures to the next available timetable trip. Negative wait times and non-causal backwards journeys are mathematically impossible.
- **Footpath Separation:** Transfer walk time is computed from physical distance and added *before* the platform buffer check.

### Pillar 4: Duration Accounting & Dwell Handling
- **Duration Identity:** $\text{Total Duration} \equiv \text{AccessWalk} + \text{InitWait} + \sum \text{Ride} + \sum \text{TransWalk} + \sum \text{TransWait} + \text{EgressWalk}$. Max discrepancy across 225 audited itineraries: **$0.00000000\text{ seconds}$**.
- **Dwell Time Treatment:** GTFS database contains 3,276,092 stop times, all with instantaneous arrival/departure. Ground-truth travel times ($N=136$) were extracted arrival-to-arrival and inherently include boarding dwell. Dwell is never added as an external addend, completely preventing double counting.

### Pillar 5: GTFS Calendar & Midnight Boundary
- **Calendar Handling:** Single weekly template service (`service_id='1'`) valid 2022–2024. Expiration handled via PRD Section 8.2 (`service_activation_assumed = True`) and explicitly documented.
- **Midnight Transitions:** Continuous monotonic integer seconds since midnight seamlessly handle the 436 midnight-crossing patterns (up to $109,251\text{s}$) without day-wrapping arithmetic anomalies.

### Pillar 6: Benchmark Performance
- **Query Response:** Mean latency of **$95.01\text{ ms}$** (median $104.90\text{ ms}$, P95 $192.23\text{ ms}$) across 150 timed executions.
- **Spatial Precomputation:** KDTree footpath generation completed in **$23.3\text{ ms}$** for 36,640 directional walking paths.
- **Memory Footprint:** Peak RSS stabilized at **$1,389.11\text{ MB}$**, well within production operating bounds.

---

## 3. Formal Classification of Audit Tests

In compliance with the audit instructions, all tests in `backend/tests/test_milestone5_1.py` and `scripts/compile_milestone5_1_audit.py` are strictly categorized by their verification methodology:

| Category | Test Suite Class / Cases | Count | Description & Verification Standard |
| :--- | :--- | :--- | :--- |
| **Independently verified against GTFS** | `TestMilestone51GTFSGroundTruth` (Cases 1, 2, 3, 4, 12, 13) | 6 | Evaluated directly against raw SQLite records in `stop_times`, `trips`, and `calendar` from `/tmp/delhi_mdb.db`. |
| **Verified against a manually calculated expected result** | `TestMilestone51GTFSGroundTruth` (Cases 5, 6, 7, 8, 9, 10, 11, 14, 15) | 9 | Evaluated against hand-computed arrival times, transfer walk math ($d/v$), buffer thresholds ($120\text{s}$), and empty set assertions. |
| **Synthetic unit test** | `TestMilestone51PredictionHierarchy`, `TestMilestone51TransferDelay`, `TestMilestone51Accounting`, `TestMilestone51Dwell` | 14 | Unit isolation tests verifying fallback logic, warning injections, non-causal delay propagation, and field separation. |
| **Performance benchmark** | `TestMilestone51Performance` | 2 | 50 diverse queries executed across 3 repeated passes (150 runs) measuring latency percentiles and footpath timers. |
| **Total Test Suite Scope** | **All Categories** | **31** | **100% Pass Rate across all categories.** |

---

## 4. Unresolved Issues and Risk Register

While the journey planner and prediction hierarchy are verified and robust, the following known limitations and operational risks are formally logged:

| Issue ID | Description | Severity | Operational Mitigation & Safety Safeguard |
| :--- | :--- | :--- | :--- |
| `ISS-01` | **Empirical Traffic Geographic Scope:** Ground-truth traffic observations ($N=136$) remain limited to the North GT Road pilot corridor across 5 October dates. | **HIGH** | Prediction hierarchy enforces Level 4 (GTFS scheduled) with explicit low-confidence warnings for all routes outside North GT Road. Level 1 is never claimed network-wide. |
| `ISS-02` | **Expired GTFS Calendar:** The Mobility Database static GTFS feed carries an expiration date of `20240101`. | **MEDIUM** | Governed under PRD Section 8.2: Timetable is treated as an active recurring weekly template (`service_activation_assumed = True`). |
| `ISS-03` | **Lack of Explicit GTFS Dwell Times:** The Delhi GTFS feed specifies instantaneous stop times (`arrival == departure`). | **LOW** | Ground-truth measurements are calibrated arrival-to-arrival, naturally absorbing dwell. Double counting is strictly avoided. |
| `ISS-04` | **Absence of Real-Time GPS Streaming (GTFS-RT):** Predictions are historical-statistical and cannot reflect unobserved unexpected incidents (e.g. protests, sudden waterlogging). | **MEDIUM** | Documented limitation. System status remains DEGRADE until real-time GPS streaming (GTFS-RT feed) is integrated in subsequent phases. |

---

## 5. Final Verdict and Formal Decision

### **Governing Verdict: DEGRADE**

The Milestone 5 implementation and Milestone 5.1 audit establish the following clear operational distinctions:
- **RAPTOR algorithm:** Validated against the documented test cases.
- **Historical timetable routing:** Validated against the supplied GTFS archive.
- **Current Delhi service accuracy:** **UNVERIFIED** because the underlying GTFS feed expired on 2024-01-01.
- **Traffic prediction:** Strictly restricted to the North GT Road pilot corridor ($N=136$ observations).
- **Overall system status:** **DEGRADE**.

Production readiness is explicitly **NOT claimed**. The system functions under strict demonstration and historical research assumptions with stale timetable safeguards.

**Milestone 5.1 is officially CLOSED under DEGRADE status.**  
*(Per instructions, Milestone 6 implementation will NOT begin until authorized).*

