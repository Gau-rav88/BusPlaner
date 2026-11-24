# Milestone 3 Limitations & Operational Constraints Report

**Service Dates Analyzed:** October 1, 2, 3, 4, and 7, 2026 (`2026-10-01` to `2026-10-07`, Pilot Subset)  
**Corridor Scope:** North GT Road (National Highway 44) Arterial Spine  
**Operational Status:** **DEGRADE** (Approved per PRD Section 6.5 & Section 7.4)  
**Date of Report:** November 21, 2026  

---

## 1. Summary of Scientific & Engineering Limitations

In accordance with Section 1 and Section 9 of the user mandate, this report documents the explicit boundaries of what can and cannot be reliably predicted from the current historical evidence base:

### Limitation 1: Sample Size & Pilot Confinement
- The ground-truth dataset consists of **136 consecutive-stop observed segments** and **199 valid stop crossings** across **5 service dates** and **31 distinct buses**.
- While 136 observations are sufficient to compute a robust historical median baseline for the North GT Road corridor, this sample size is small for training high-capacity, multi-parameter machine learning models.
- Random Forest (M2) showed a 16.11% MAE reduction on 30 held-out test samples, but this improvement is derived from a single evaluation date (October 7) and must be treated as preliminary rather than proof of generalized performance across all seasons.

### Limitation 2: Geographic & Corridor Concentration
- **91.18% of all ground-truth segment observations** (124 of 136) originate from a single transit line: **Route 1598 (129AUP)** along North GT Road between Azadpur and Alipur.
- Co-running line **Route 1445** contributed 11 segments (8.09%), and **Route 1657** contributed 1 segment (0.74%).
- **Zero stop-level ground-truth observations exist for East, South, West, or Central Delhi corridors** (such as Ring Road, Mehrauli-Badarpur Road, Mathura Road, or Dwarka arterials).
- **Prohibition Enforced:** The system must never claim that these models represent traffic conditions across the entire city of Delhi.

### Limitation 3: Temporal & Hourly Coverage Gaps
- Ground-truth observations are concentrated between 07:00 and 21:59 IST.
- **11 out of 24 hours have ZERO empirical observations**:
  $$\text{Zero-Observation Hours: } [00:00–06:59, 11:00–11:59, 19:00–19:59, 22:00–23:59]$$
- Observations in Hour 10 ($n=1$), Hour 12 ($n=1$), Hour 20 ($n=3$), and Hour 21 ($n=3$) represent small-sample localized conditions and cannot be interpreted as general traffic state.

### Limitation 4: Detour Factor Localization
- The measured detour ratio of **1.262** was calculated from arterial curves on North GT Road.
- Grade-separated tangents exhibit detour ratios of **1.072 – 1.075**, while elevated flyover cloverleafs (Mukarba Chowk) exhibit detour ratios of **1.422 – 1.559**, and terminal turnaround loops reach **2.417**.
- **Prohibition Enforced:** The detour factor `1.262` must **never be applied as a global Delhi-wide multiplier**. Any unmeasured corridor must use an explicitly labeled geometric fallback rather than an assumed empirical detour factor.

### Limitation 5: Timetable Version Skew
- The open GTFS database (`mdb-1262`) reflects a 2022–2024 academic release, whereas the GPS telemetry stream reflects modernized October 2026 fleet operations (including electric bus inductions and reorganized cluster lines).
- Off-route depot deadheading accounts for 35% to 55% of raw telemetry. Map matching strictly rejects off-route runs to protect ground truth, which prevents 100% stop-to-stop network coverage without contemporary GTFS schedule tables.

---

## 2. What Is Reliably Predictable Today vs. What Requires Fallback

| Transit Query Domain | Predictability Status | Serving Model / Tier | Confidence Level | Fallback Mechanism |
| :--- | :---: | :--- | :---: | :--- |
| **North GT Road (Route 1598, Azadpur $\leftrightarrow$ Alipur)** | **Reliably Predictable** | Tier 1 Direct Observed & Tier 3 Corridor Median (M0/M2) | **High (0.8 – 1.0)** | Direct empirical distribution |
| **Co-Running Lines along North GT Road (1445, 125, 1578)** | **Reliably Predictable** | Tier 2 Physical Stop-Pair Pooling | **Moderate (0.8)** | Pooled across identical stop coordinates |
| **North GT Road (Unobserved Hours: 00-06, 11, 19, 22-23)** | *Derived Fallback* | Tier 4 Calibrated Route Baseline | **Low (0.4)** | Scheduled speed scaled by corridor median |
| **Other Delhi Corridors (Ring Road, South/East/West Delhi)** | *Derived Fallback* | Tier 4 Calibrated Route Baseline | **Low (0.4)** | Timetable speed with local detour scaling |
| **Unscheduled / Renumbered 2026 Cluster Routes** | **Unavailable** | Timetable Lookup Only | **Unrated** | Lacks GTFS timetable entry |

---

## 3. Justification for Continuing Under DEGRADE Status

In strict accordance with PRD Section 6.5:
> *"DEGRADE: Stop-level extraction is weak across unaligned routes, but longer-distance stop crossings and corridor observations are available $\to$ Merge stops into timepoint segments and mark allocations as derived."*

Continuing under **DEGRADE** status is the only scientifically defensible choice:
- **Why Not Full "GO"?** Claiming full "GO" would imply network-wide 100% stop-to-stop ground truth, which does not exist and would require manufacturing synthetic data.
- **Why Not "BLOCKED"?** The project has successfully established a high-fidelity empirical baseline on Delhi's major northern radial spine (North GT Road), verified leakage-free chronological holdouts, achieved 86.67% conformal interval coverage, and implemented an automated 4-tier fallback hierarchy that enables downstream journey planning without fabricating data.

---

## 4. Compliance with Explicit Prohibitions

1. **No Journey Planner Implemented:** No routing, RAPTOR, or journey planner algorithms have been built in this milestone.
2. **No Network-Wide Claims:** All reports and code explicitly constrain empirical predictions to the verified North GT Road corridor.
3. **No Target Leakage:** Chronological whole-date splits and out-of-fold feature engineering strictly prevent data leakage.
4. **No Synthetic Oversampling:** Zero artificial, jittered, or synthetic observations were manufactured.
5. **Raw Archives Preserved:** The Cloudflare R2 source archive and local Parquet partitions remain intact.
6. **Milestone 4 Not Started:** Modeling has stopped at Milestone 3 evaluation; no frontend or future milestone code has been written.

