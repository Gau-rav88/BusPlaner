# Milestone 2.2.1 Audit Report: Final Data Audit & Coverage Corrections

**Service Dates Analyzed:** October 1, 2, 3, 4, and 7, 2026 (`2026-10-01` to `2026-10-07`, Pilot Subset)  
**Host Architecture:** macOS Apple Silicon (`darwin arm64`), 11 GiB Available Local APFS Storage  
**Audit Artifacts Created:**  
- [data/processed/milestone2_2_1_audit_metrics.json](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/milestone2_2_1_audit_metrics.json)  
- [reports/milestone2_2_1_date_coverage.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone2_2_1_date_coverage.md)  
- [reports/milestone2_2_1_ground_truth_coverage.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone2_2_1_ground_truth_coverage.md)  
- [reports/milestone2_2_1_data_quality.md](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/milestone2_2_1_data_quality.md)  
- [backend/tests/test_milestone2_2_1.py](file:///Users/gauravchauhan/Downloads/delhi_hacks/backend/tests/test_milestone2_2_1.py)  
**Date of Audit:** November 21, 2026  

---

## 1. Executive Summary & Purpose

This audit report resolves all remaining discrepancies, over-generalizations, and terminology ambiguities identified in the Milestone 2.2 completion report. Every metric reported herein is strictly calculated from the underlying Parquet, SQLite, and JSON source artifacts without extrapolation.

Key audit conclusions:
1. **Pilot Classification:** The 5-date dataset is formally classified as a **Pilot Subset**, NOT full-month historical coverage. The remote archive contains all 31 dates, but processing all 31 dates requires ~24 GB storage, exceeding the host machine's 11 GiB available capacity.
2. **True Global Ground Truth:** The ground-truth dataset contains **31 globally unique vehicles**, **26 globally unique physical stop pairs**, and **3 routes** producing **136 consecutive observed segments** and **199 valid stop crossings**.
3. **Quarantine Terminology Reconciled:** Of the 54,463,360 quarantined records, **99.91% (54,411,931 records) are identical telemetry repeats** caused by upstream crawler polling variations. True conflicting telemetry affects only **42,659 records (0.029%)**.
4. **October 7 Outage Forensic Verification:** The telemetry outage occurred at **14:23:23 UTC**, which was **19:53:23 IST** (the evening commute, not midday 14:23 IST). The exact outage gap lasted **22,127 seconds (6 hours 8 minutes 47 seconds)**, resuming at 02:02:10 IST on October 8.
5. **Detour Factor Limitations:** The detour ratio `1.262` was derived from arterial sections on a single corridor (North GT Road) and **cannot be applied as a validated network-wide median**. Detour factors must remain corridor-specific and geometry-specific.
6. **Hourly Coverage Correction:** Exactly **11 of 24 hours have ZERO observations** across all 5 dates. All reported hourly medians are accompanied by their exact sample size $n$.
7. **Automated Verification:** All 20 automated tests pass with 100% success.

---

## 2. Direct Answers to Milestone 2.2.1 Audit Questions (Stop Condition)

In strict accordance with Section 8 of the prompt, here are the explicit answers before proceeding:

### 1. Whether all available October dates were processed
- **NO.** All 31 dates exist in the remote Cloudflare R2 7z archive (`bus_movements_2026_10_01.db` to `bus_movements_2026_10_31.db`).
- **5 dates were processed** (`2026-10-01`, `2026-10-02`, `2026-10-03`, `2026-10-04`, `2026-10-07`) as a representative **Pilot Subset** covering regular weekdays, national holidays (Gandhi Jayanti), weekends, and data outages.
- **Physical Reason for Unprocessed Dates:** Ingesting all 31 dates into clean Parquet (~15 GB) and quarantine tables (~9 GB) requires **~24 GB of disk space**, which exceeds the host machine's **11 GiB available APFS headroom**. Attempting full-month processing on local disk would trigger host disk exhaustion.

### 2. The true global unique vehicle, route, and stop-pair counts
Calculated directly across the combined underlying Parquet partitions:
- **Globally Distinct Vehicles:** **31 buses** (e.g., `DL51EV3788` [12 segs], `DL51EV8634` [9 segs], `DL51EV3776` [9 segs], `DL51EV4080` [9 segs]).
- **Globally Distinct Physical Stop Pairs:** **26 stop pairs** (ranging from New Sabzi Mandi to Alipur PWD Office).
- **Globally Distinct Routes with Valid Ground Truth:** **3 routes**:
  - Route `1598` (129AUP): **124 observed segments** (91.18%)
  - Route `1445` (126AUP co-running sibling): **11 observed segments** (8.09%)
  - Route `1657` (103STLUP): **1 observed segment** (0.74%)
- **Total Valid Stop Crossings:** **199 crossings**
- **Total Consecutive Observed Segments:** **136 segments**

### 3. The corrected ground-truth coverage by date and hour
- **By Date:**
  - `2026-10-01` (Thu, Weekday): 34 segments, 7 vehicles, 9 stop pairs
  - `2026-10-02` (Fri, Holiday): 20 segments, 5 vehicles, 15 stop pairs
  - `2026-10-03` (Sat, Weekend): 30 segments, 9 vehicles, 15 stop pairs
  - `2026-10-04` (Sun, Weekend): 22 segments, 3 vehicles, 15 stop pairs
  - `2026-10-07` (Wed, Weekday Outage): 30 segments, 7 vehicles, 14 stop pairs
- **By Hour (IST):**
  - **11 Hours with ZERO Observations:** `[00:00–06:59, 11:00–11:59, 19:00–19:59, 22:00–23:59]`
  - **13 Active Hours:** 
    - 07:00 ($n=24$, med 23.37 km/h, weekend only)
    - 08:00 ($n=17$, med 18.61 km/h)
    - 09:00 ($n=4$, med 23.01 km/h)
    - 10:00 ($n=1$, med 20.78 km/h, single holiday bus)
    - 12:00 ($n=1$, med 1.80 km/h, localized dwell)
    - 13:00 ($n=10$, med 21.67 km/h)
    - 14:00 ($n=17$, med 21.67 km/h)
    - 15:00 ($n=12$, med 21.69 km/h)
    - 16:00 ($n=13$, med 7.30 km/h)
    - 17:00 ($n=17$, med 4.88 km/h, severe Mukarba Chowk peak bottleneck)
    - 18:00 ($n=14$, med 12.07 km/h)
    - 20:00 ($n=3$, med 1.29 km/h, localized signal crawl at Jahangirpuri)
    - 21:00 ($n=3$, med 20.83 km/h, night recovery)

### 4. The corrected duplicate and quarantine accounting
Mutually exclusive accounting across all 147,869,768 raw observations:
- **Retained Clean Parquet Records:** **93,389,652** ($63.157\%$)
- **Metadata Duplicate Repeats (Identical Telemetry):** **54,411,931** ($36.797\%$)
- **Genuine Telemetry Sensor Conflicts:** **42,659** ($0.029\%$)
- **Rule E02 Peer Drops (Rank-1 Out-of-Bounds):** **8,770** ($0.006\%$)
- **Rule E03 Spatial Out-of-Bounds Quarantined:** **16,756** ($0.011\%$)
- **Exact Accounting Balance:** $93,389,652 + 54,411,931 + 42,659 + 8,770 + 16,756 = \mathbf{147,869,768}$ ($100.000\%$).

### 5. The evidence supporting or limiting detour calibration
- **Evidence Base:** 8 valid measured sections along Route 129A (North GT Road):
  - Highway tangents: $1.072$ – $1.075$
  - Curvilinear arterials: $1.158$ – $1.262$
  - Elevated flyovers / interchanges: $1.422$ – $1.559$
  - Terminal turnaround loops: $2.417$
- **Limitations:** The value `1.262` represents an exploratory arterial median on North GT Road only. **It cannot be applied globally across Delhi**. Detour factors must remain localized by road type and corridor geometry.

### 6. Whether the data supports only a corridor-level baseline or something broader
- **Data Supports:** **A Verified Corridor-Level Baseline along Aligned Arterials (North GT Road), accompanied by a 4-Tier Fallback Hierarchy for the broader network** (PRD Section 6.5 & Section 7.4).
- Stop-level empirical ground truth is established for the 26 stop pairs along North GT Road.
- Network-wide stop-level modeling is constrained by timetable version skew (2022 static GTFS vs. 2026 GPS). Network-wide predictions must rely on Tier 2 (corridor pooling), Tier 3 (timepoint corridor aggregation), and Tier 4 (calibrated route baselines).

### 7. Remaining blockers for Milestone 3
1. **Lack of Contemporary 2026 GTFS:**
   - Without an updated GTFS release reflecting cluster bus reorganizations, network-wide stop-to-stop ML training is blocked.
   - **Mitigation:** Milestone 3 must operate under the **DEGRADE** operational classification specified in PRD Section 6.5, restricting high-resolution ML models to Tier 1 verified corridors and applying timepoint/corridor aggregation across the remainder of the network.
2. **Model Training Scope:**
   - ML training must be explicitly evaluated against the 136 ground-truth segments and 26 stop pairs, rather than attempting to train a 100% stop-to-stop network model that would overfit to timetable mismatch noise.

---

### Stop Condition Status
Milestone 2.2.1 is complete. No machine learning models, traffic prediction scripts, or journey planning features have been implemented. I am stopped and awaiting your explicit approval.

