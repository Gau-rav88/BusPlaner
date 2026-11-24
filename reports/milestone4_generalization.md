# Milestone 4 Generalization & Fallback Diagnostics Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 4.0 – Extended Model Validation  
**Status:** **AUDITED & VALIDATED (DEGRADE STATUS)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone4_metrics.json`  

---

## 1. Executive Summary & Diagnostic Scope

A key objective of Milestone 4 is stress-testing models under real-world transit anomalies and edge cases. This report investigates model behavior across six specific operational challenges:
1. Sparse stop-pair historical observations.
2. Unseen physical stop pairs in the test partition.
3. Unseen transit routes.
4. Peak-hour extreme congestion regimes.
5. Telemetry feed outages and missing GPS data.
6. Fallback tier failure modes.

---

## 2. Sparse Stop-Pair History

### 2.1 The Case of Link `1598_dir0_pat0_seq9`
Link `seq9` represents a $1634.72\text{-meter}$ road segment along North GT Road between *Azadpur Metro Station* and *Model Town III*.
- **Training Representation:** Only 2 observations existed in the training partition ($n=2 < 3$).
- **M0 Behavior:** Disqualified from Tier 1 direct observation, M0 dropped to **Tier 4 Route Baseline**. Tier 4 applied the corridor-wide congested speed ($\approx 11\text{ km/h}$) scaled by the local detour factor ($k=1.262$):
  $$\hat{y}_{\text{Tier 4}} = \frac{1634.72 \times 1.262}{11.0 / 3.6} = 674.87 \text{ seconds}$$
- **Physical Reality:** In reality, `seq9` is an open arterial segment where buses ran at $23\text{--}25\text{ km/h}$ ($239.02\text{s}, 249.59\text{s}, 252.06\text{s}$).
- **Outcome:** M0 produced an error of **$427.98\text{ seconds}$** (overestimating travel time by nearly $3\times$).
- **Machine Learning Mitigation:** Random Forest (M2) utilized the continuous link distance feature ($1634.72\text{m}$) and learned that longer arterial sections operate at higher speeds, predicting $224\text{--}280\text{s}$ ($\text{MAE} = \mathbf{61.94\text{s}}$).

---

## 3. Unseen Physical Stop Pairs

On the held-out test date (October 7), vehicle `DL51EV1973` operated on Route 1445, traversing two physical stop pairs that **had zero prior observations in the training partition**:
1. `1445_dir0_pat0_seq2` (Stop 552 $\to$ Stop 553, $624.97\text{m}$)
2. `1445_dir0_pat0_seq3` (Stop 553 $\to$ Stop 554, $208.57\text{m}$)

### 3.1 Performance on Unseen Links

```
+---------------------------------------------------------------------------------------------------------------+
| Segment Key         | Obs | Actual Times (s)    | M0 Pred (s)     | M0 MAE (s) | M2 Pred (s)     | M2 MAE (s) |
+---------------------------------------------------------------------------------------------------------------+
| 1445_dir0_pat0_seq2 | 2   | 104.69 s, 202.57 s  | 169.52 s (T4)   | 48.94 s    | 123.58 s, 145.57s| 37.94 s    |
| 1445_dir0_pat0_seq3 | 2   | 28.47 s, 28.69 s    | 64.58 s, 20.16s | 22.32 s    | 105.27s, 119.19s| 83.65 s    |
+---------------------------------------------------------------------------------------------------------------+
```

### 3.2 Architectural Tradeoffs in Zero-Shot Situations
- **On `seq2` (Moderate Length, $625\text{m}$):** Both models adapted reasonably. M0's Tier 4 route baseline predicted $169.52\text{s}$ ($\text{MAE} = 48.94\text{s}$), while M2 predicted $123.58\text{s}$ and $145.57\text{s}$ ($\text{MAE} = 37.94\text{s}$).
- **On `seq3` (Short Link, $209\text{m}$):** M0 performed significantly better ($\text{MAE} = 22.32\text{s}$) than M2 ($\text{MAE} = 83.65\text{s}$). Because M2 does not have a separate dwell model or physical lower-bound threshold on short links, its tree predictions hovered around $105\text{--}119\text{s}$, overpredicting the fast $28\text{-second}$ clearance.
- **Rule Enforced:** In unobserved areas, M0's transparent fallback provides greater predictability than unconstrained decision trees.

---

## 4. Unseen Routes & Network-Wide Limitations

When a journey planner queries routes outside the North GT Road pilot corridor (e.g., routes operating in South or East Delhi):
1. **Zero GPS History:** No empirical GPS observations exist in the local dataset.
2. **Behavior of Models:**
   - M0 falls back to **Tier 4 Timetable Fallback** (scheduled GTFS runtime) with explicit low-confidence tagging (`confidence = 0.40`, `warning = "Unseen route; timetable schedule fallback applied"`).
   - M2 cannot be queried safely because its feature extractor has no historical route or stop-pair priors.
3. **Detour Factor Restriction:** The calibrated corridor detour factor ($k = 1.262$) must **never be applied globally**. Other Delhi corridors feature flyovers, signalized roundabouts, and elevated metro viaducts that do not match North GT Road geometry.

---

## 5. Peak-Hour Congestion Outliers

At 17:00 IST on October 7, vehicle `DL51EV4080` traversed segment `1598_dir0_pat0_seq2` ($771.60\text{m}$) during extreme evening rush-hour gridlock:
- **Actual Travel Time:** **$1643.58\text{ seconds}$ ($27.39\text{ minutes}$)**.
- **Effective Traversal Speed:** **$1.69\text{ km/h}$** (severe pedestrian crawl).
- **Model Predictions:**
  - M0 predicted $595.85\text{s}$ (Error: $-1047.73\text{s}$).
  - M1 predicted $767.12\text{s}$ (Error: $-876.46\text{s}$).
  - M2 predicted $631.97\text{s}$ (Error: $-1011.61\text{s}$).
- **Diagnostic Finding:** When road infrastructure suffers complete gridlock, historical statistical models and offline tree regressors underpredict significantly. Only real-time live telemetry (e.g. streaming speed deltas from co-running buses) can detect and adjust for sudden standstill events.

---

## 6. GPS Telemetry Feed Outages

On October 7, 2026, an upstream telemetry outage disabled the Delhi bus GPS feed:
- **Outage Window:** October 7, 14:23 UTC (19:53 IST) to October 8, 02:02 IST (**6.15 hours**).
- **Data Reality:** Zero GPS pings or ground-truth segments could be reconstructed during this period.
- **System Degradation Rule:** During feed outages, real-time map-matching is entirely disabled. The system must degrade to **Level 4 Static GTFS Timetables** and notify users with an explicit data outage banner. Empirical predictions must never be fabricated when live data is unavailable.

