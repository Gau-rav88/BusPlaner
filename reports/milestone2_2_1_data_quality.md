# Milestone 2.2.1 Data Quality, Quarantine Accounting & Detour Audit Report

**Service Dates Audited:** October 1, 2, 3, 4, and 7, 2026 (`2026-10-01` to `2026-10-07`, Pilot Subset)  
**Total Raw Observations Audited:** 147,869,768 records across 5 historical databases  
**Audit Artifact:** `data/processed/milestone2_2_1_audit_metrics.json`  
**Date of Audit:** November 21, 2026  

---

## 1. Reconciled Duplicate & Quarantine Accounting (Mutually Exclusive Breakdown)

In Milestone 2.2, a total of 54,463,360 records were quarantined under Rule E02 and broadly described as *"conflicting duplicates"*. A deep forensic audit of the underlying records was performed by joining every quarantined record in `conflicts_*.parquet` against its retained peer in `data.parquet` on `(vehicle_id, timestamp)`.

The audit revealed that **99.91% of quarantined records are NOT conflicting telemetry, but identical telemetry payloads repeated by crawler metadata variations**.

### Mutually Exclusive Accounting (Sum = Raw Observations)
| Data Category | Mutually Exclusive Definition | Exact Count (5 Pilot Dates) | Share of Raw (%) | Technical Description |
| :--- | :--- | :---: | :---: | :--- |
| **Retained Clean Observations** | Rank-1 valid spatial observations within bounding box | **93,389,652** | **63.157%** | Clean, deduplicated, UTC-validated Parquet partitions |
| **Identical Telemetry Repeats** | Repeated records where `lat`, `lng`, and `speed` are identical to the retained record | **54,411,931** | **36.797%** | Upstream crawler polled vehicle endpoint multiple times within same second or logged minor string variations (`date`/`time`) |
| **Genuine Conflicting Telemetry** | Records where `lat`, `lng`, or `speed` physically conflict with the retained record | **42,659** | **0.029%** | Sensor multi-reporting or asynchronous hardware clock collisions on identical `(vehicle_id, timestamp)` |
| **Rule E02 Out-of-Bounds Peer Drops** | Quarantined duplicate peers whose rank-1 peer was later dropped by Rule E03 | **8,770** | **0.006%** | Dropped alongside out-of-bounds coordinates |
| **Rule E03 Spatial Out-of-Bounds** | Rank-1 coordinates outside Delhi bounding box $[28.0, 29.2]^\circ\text{N}, [76.5, 77.8]^\circ\text{E}$ | **16,756** | **0.011%** | Spurious GNSS fixes ($[0,0]$, inverted coordinates, out-of-state lock) |
| **Total Raw Observations** | **Mutually Exclusive Sum** | **147,869,768** | **100.000%** | **Exact mathematical balance across all 5 dates** |

### Per-Date Mutually Exclusive Accounting
| Date | Raw Observations | Retained Clean | Identical Telemetry Repeats | Genuine Telemetry Conflicts | Rule E02 Peer Drops | Rule E03 Out-of-Bounds | Balance Check |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2026-10-01** | 31,290,299 | 19,215,508 | 12,059,383 | 10,083 | 1,859 | 3,466 | **Exact (0 error)** |
| **2026-10-02** | 29,314,267 | 18,833,834 | 10,468,506 | 6,643 | 1,608 | 3,676 | **Exact (0 error)** |
| **2026-10-03** | 31,516,372 | 20,003,508 | 11,498,613 | 8,946 | 1,928 | 3,377 | **Exact (0 error)** |
| **2026-10-04** | 30,213,040 | 19,556,176 | 10,643,589 | 8,494 | 1,446 | 3,335 | **Exact (0 error)** |
| **2026-10-07** | 25,535,790 | 15,780,626 | 9,741,840 | 8,493 | 1,929 | 2,902 | **Exact (0 error)** |
| **Total** | **147,869,768** | **93,389,652** | **54,411,931** | **42,659** | **8,770** | **16,756** | **Exact (100.00%)** |

> [!IMPORTANT]
> **Terminology Correction:** Moving forward, the 54.41M records are categorized as **"Metadata Duplicate Repeats"**, while true **"Conflicting Telemetry"** is recognized as a rare occurrence affecting only **42,659 records (0.029%)**.

---

## 2. October 7 Outage Forensic Verification

Previous reports stated that an outage halted telemetry at `14:23:23 IST`. Forensic inspection of raw Unix timestamps in both `bus_movements_2026_10_07.db` and `bus_movements_2026_10_08.db` proved that this was a **UTC-to-IST transcription error**:

1. **Exact Outage Boundary:**
   - Latest Observation in October 7 Partition:
     - **UTC:** `2026-10-07 14:23:23 UTC`
     - **IST (UTC + 05:30):** **`2026-10-07 19:53:23 IST`**
   - Earliest Observation in October 8 Partition:
     - **UTC:** `2026-10-07 20:32:10 UTC`
     - **IST (UTC + 05:30):** **`2026-10-08 02:02:10 IST`**
   - **Exact Outage Interval:** **22,127 seconds** = **6 hours 8 minutes 47 seconds** (from 19:53:23 IST to 02:02:10 IST the next morning).
2. **Did Telemetry Resume in the October 7 Database?**
   - **No.** The October 7 database abruptly ends at `14:23:23 UTC` (`19:53:23 IST`). Telemetry resumed in the subsequent day's file (`bus_movements_2026_10_08.db`) at `02:02:10 IST`.
3. **Data Yields Before vs. After 14:23:23 IST on October 7:**
   - Because the outage occurred at **19:53:23 IST** (not 14:23 IST), normal operations continued through the afternoon and early evening:
     - Clean GPS Pings between 00:00 and 14:23:23 IST: **11,772,808 pings**
     - Clean GPS Pings between 14:23:24 and 19:53:23 IST: **4,007,818 pings**
     - Stop Crossings before 14:23:23 IST: **25 crossings** (producing 20 consecutive segments)
     - Stop Crossings after 14:23:23 IST: **14 crossings** (producing 10 consecutive segments)
     - Total Stop Crossings on October 7: **39 crossings** (30 consecutive segments)

---

## 3. Detour Factor Calibration Audit & Limitations

In Milestone 2.1, an empirical detour ratio of `1.262` was reported. To establish scientific reproducibility, the table below documents the exact eight physical roadway sections measured along Route 129A (North GT Road):

| Section # | From GTFS Stop | To GTFS Stop | Straight Euclidean Distance ($D_{\text{straight}}$) | Cumulative GPS Path Distance ($D_{\text{GPS}}$) | Detour Ratio ($k_{\text{detour}}$) | Roadway Character | Measurement Status |
| :---: | :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **1** | New Sabzi Mandi | Adarsh Nagar / Bharola | 274.7 m | 318.1 m | **1.158** | Curvilinear arterial curve | Exploratory (Corridor-Specific) |
| **2** | Adarsh Nagar / Bharola | Sarai Peepal Thala | 626.8 m | 1,514.9 m | **2.417** | Terminal loop maneuver | Local Feature Only |
| **3** | Sarai Peepal Thala | Mahindra Park | 156.6 m | 197.7 m | **1.262** | Arterial curve & bus bay weave | Exploratory (Corridor-Specific) |
| **4** | Jahangirpuri GT Road | Jahangirpuri Metro | 291.5 m | 312.4 m | **1.072** | Grade-separated highway tangent | Local Tangent Feature |
| **5** | GTK Depot | Mukarba Chowk | 474.5 m | 739.7 m | **1.559** | Elevated flyover ramp loop | Local Interchange Only |
| **6** | Mukarba Chowk | Sanjay Gandhi Tpt Nagar | 434.7 m | 618.0 m | **1.422** | Cloverleaf highway merge weave | Local Interchange Only |
| **7** | Swaroop Nagar GT Road | Gurudwara Siraspur | 788.6 m | 1,164.6 m | **1.477** | Arterial curve & underpass | Exploratory (Corridor-Specific) |
| **8** | Budhpur GT Road | BDO Office | 1,258.8 m | 1,353.7 m | **1.075** | Straight radial highway tangent | Local Tangent Feature |

*(Note: Section 9 from exploratory drafts, Alipur to PWD Office, exhibited $D_{\text{GPS}} < D_{\text{straight}}$ due to lateral GNSS receiver jitter artifacts, and has been disqualified from calibration).*

### Limitations of Detour Factor 1.262
1. **Single Corridor Confinement:**
   All 8 calibrated sections are located along a single radial spine: **North GT Road (National Highway 44)**. Zero sections were measured on Ring Road, Outer Ring Road, Mathura Road, or Trans-Yamuna arterials.
2. **How 1.262 Was Selected:**
   The value `1.262` corresponds directly to Section 3 (Sarai Peepal Thala $\to$ Mahindra Park, $197.7\text{m} / 156.6\text{m} = 1.262$), representing the median of standard urban arterial sections on this corridor. It is **NOT a weighted network-wide median for the entire city of Delhi**.
3. **Application Rule for Downstream Milestones:**
   The detour ratio `1.262` must **NOT be applied globally**. Downstream journey planning and traffic modeling must:
   - Apply highway tangent factor ($1.07$) on straight, grade-separated corridors.
   - Apply interchange factor ($1.42$–$1.56$) at complex flyovers and cloverleafs.
   - Restrict arterial scaling ($1.16$–$1.26$) to verified urban corridors.

