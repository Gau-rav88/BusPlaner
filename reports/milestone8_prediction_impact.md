# Milestone 8: Prediction Hierarchy Impact & Replay Safety Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Phase:** Milestone 8 — Prediction Hierarchy & Operational Impact  
**Operational Status:** **DEGRADE**  
**Date:** November 2026  

---

## 1. Executive Summary

Milestone 8 investigated the impact of real-time GTFS-RT feed availability on the core transit prediction hierarchy and journey planner.

PRD v3.0 Section 7.9 and Section 5 of the Milestone 8 mandate specify:
> *"Preserve the existing hierarchy: 1. Validated historical observations where sufficient evidence exists; 2. M0 historical median fallback; 3. Experimental Random Forest only with explicit opt-in; 4. Valid timetable estimates with freshness disclosures; 5. Static fallback with low-confidence disclosure. Live information may be added as a bounded correction only after replay testing demonstrates measurable improvement. Do not silently replace the existing prediction source. Never describe scheduled timetable estimates as real-time traffic predictions."*

Because the live GTFS-RT feed is classified as **`AUTH_REQUIRED`** (requiring an unconfigured `x-api-key`), the live feed was **not injected into active journey predictions**. This audit confirms that:
1. **Zero Degradation or Distortion:** Historical ground truth observations and the M0 median baseline remain completely uncontaminated.
2. **Strict Hierarchy Maintained:** All five prediction levels operate exactly as specified in Milestone 5.1 and 6.1.
3. **Bounded Correction Formulation Ready:** A mathematically bounded speed-ratio fusion formula has been designed for future activation when valid live feeds become available.

---

## 2. Preserved Five-Tier Prediction Hierarchy

The prediction hierarchy continues to resolve transit leg durations in strict hierarchical order:

| Hierarchy Level | Prediction Source | Trigger Condition & Empirical Scope | Typical Confidence | Public Schema Attribution |
| :---: | :--- | :--- | :---: | :--- |
| **Level 1** | `GROUND_TRUTH_OBSERVED` | Direct empirical stop-pair segment on North GT Road (Route 1598) with $\ge 3$ observations in matching hour/day-type. | $0.85 - 0.95$ (Heuristic) | `LEVEL_1_DIRECT_OBSERVED` |
| **Level 2** | `M0_HISTORICAL_MEDIAN` | Physical stop pair observed across co-running lines or corridor-level hourly speed. | $0.70 - 0.85$ (Heuristic) | `LEVEL_2_HISTORICAL_BASELINE_M0` |
| **Level 3** | `M2_RANDOM_FOREST` | Candidate Random Forest model. **Gated: Requires explicit `use_experimental_ml: true`.** | $0.60 - 0.70$ (Heuristic) | `LEVEL_3_EXPERIMENTAL_RF` |
| **Level 4** | `GTFS_TIMETABLE` | Unobserved corridors across Delhi. Uses static GTFS scheduled running duration. | $0.30$ (Heuristic) | `LEVEL_4_GTFS_SCHEDULED` |
| **Level 5** | `STATIC_SPEED_FALLBACK` | Missing or zero scheduled running times. Derived from Euclidean distance at $18.0$ km/h. | $0.10$ (Heuristic) | `LEVEL_5_STATIC_FALLBACK` |

---

## 3. Mathematical Design for Future Live Speed-Ratio Fusion

When live GTFS-RT streams become accessible with authenticated credentials, real-time vehicle velocities will be integrated as a bounded multiplicative adjustment rather than an outright replacement:

$$v_{\text{live}} = \frac{1}{|V_{\text{seg}}|} \sum_{v \in V_{\text{seg}}} v_{\text{speed}}$$

$$\alpha = \text{clip}\left(\frac{v_{\text{live}}}{v_{\text{baseline}}}, 0.5, 2.0\right)$$

$$T_{\text{predicted}} = \frac{T_{\text{baseline}}}{\alpha}$$

### Built-in Safeguards:
1. **Clamping Bounds ($[0.5, 2.0]$):** Live observations cannot cause travel time predictions to drop below half of baseline or exceed double baseline, preventing runaway distortion from momentary GPS jitter.
2. **Replay Validation Gate:** Under PRD Section 7.9, live fusion will be enabled only after an offline historical replay test demonstrates lower MAE and RMSE than the unadjusted M0 baseline on holdout data.
3. **Attribution Integrity:** When live fusion is active, the prediction source will be explicitly labeled `LIVE_FUSED_M0` with `live_adjustment_ratio: alpha`. Timetable estimates will **never** be labeled as real-time predictions.

---

## 4. Replay Safety & Regression Verification

To guarantee that Milestone 8 introduced zero regressions to journey planning or prediction accuracy:
1. **Direct Route 1598 Regression Test:**
   - Query: Stop 239 (Azad Pur Terminal) → Stop 247 (Mukarba Chowk).
   - Departure: `2026-10-01 12:37:40` with `allow_assumed_recurring: true`.
   - Verified Output: 0 transfers, duration 1220.5s (~20 min), `prediction_tier: "LEVEL_1_DIRECT_OBSERVED"`, `prediction_source: "GROUND_TRUTH_OBSERVED"`, heuristic confidence $0.93$.
2. **Transfer Route Regression Test:**
   - Query: Stop 239 (Azad Pur Terminal) → Stop 2024 (Toll Tax Post).
   - Verified Output: 1 transfer (Route 925 + Route 5959), duration 8591s, `prediction_tier: "LEVEL_4_GTFS_SCHEDULED"`, heuristic confidence $0.30$.
3. **Full Suite Execution:** All 116 backend tests and 26 frontend tests pass without deviation.

---

## 5. Audit Conclusion

The prediction hierarchy remains rigorously intact. In the absence of live feed credentials, no synthetic adjustments or speculative claims were introduced. The journey planner continues to deliver honest, evidence-grounded predictions under **DEGRADE** operational status.

