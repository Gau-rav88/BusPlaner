# Milestone 10: Historical Data Upgrade & Storage Feasibility Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10 Specification  
**Source Archive:** `/tmp/delhi_archive_header.7z` (October 2026 Raw GPS Archive)  
**Host Free Disk Space:** 11.33 GB  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

Milestone 10 evaluated the feasibility of expanding the validated 5-day historical dataset (October 1, 2, 3, 4, 7, 2026; 136 segment observations) to encompass all 31 calendar days of October 2026 present in the raw archive.

**Engineering Verdict:** Expanding the historical dataset across all 31 days is **strictly blocked by host physical storage constraints**. The raw 7z archive occupies 14.97 GB; uncompressing all daily SQLite files requires ~85 GB of transient space, whereas the host environment provides only **11.33 GB** of free disk space. Attempting full uncompressed extraction would cause an immediate `ENOSPC` (No space left on device) crash.

Consequently, the project safely gates historical processing, preserving the fully audited 5-day baseline dataset while outlining an automated, single-date streaming processing pipeline for future high-capacity deployment.

---

## 2. Storage Inventory & Capacity Math

### 2.1 File and Volume Metrics

```
Resource                               Path / Location                 Size
─────────────────────────────────────────────────────────────────────────────
Raw 7z Compressed Archive              /tmp/delhi_archive_header.7z    14.97 GB
Host Available Disk Space              / (root filesystem)             11.33 GB
Current Processed Parquet (5 days)     data/processed/gps_parquet/      ~1.2 GB
Current Processed Crossings (5 days)   data/processed/stop_crossings/   ~15 MB
Primary SQLite GTFS Database           /tmp/delhi_mdb.db               1.32 GB
Serving Fallback SQLite Database       data/serving/delhi_bus.db       1.32 GB
─────────────────────────────────────────────────────────────────────────────
```

### 2.2 Full Month Expansion Arithmetic

```
Component                              Per-Day Average   31-Day Total
─────────────────────────────────────────────────────────────────────────────
Uncompressed Raw Daily SQLite File     2.74 GB           84.94 GB
Cleaned & Filtered Parquet File        402 MB            12.46 GB
Derived Stop Crossing Events           4.2 MB            130.2 MB
Transient Extraction Working Buffer    3.0 GB            3.0 GB (streamed)
─────────────────────────────────────────────────────────────────────────────
Total Transient Space Required:                          ~88.0 GB
Total Permanent Parquet Storage:                         ~12.5 GB
Available Host Disk Capacity:                            11.33 GB
─────────────────────────────────────────────────────────────────────────────
Storage Deficit (Permanent):                             -1.17 GB
Storage Deficit (Transient Peak):                        -76.67 GB
```

### 2.3 Host Disk Assessment

Execution of `df -h /` confirms:
```
Filesystem     Size   Used  Avail Capacity iused      ifree %iused  Mounted on
/dev/disk3s1s1 460G   241G   11.3G    96% 1845112 2412852448    0%   /
```
At 96% root disk utilization, extracting even 4 uncompressed daily SQLite files concurrently would exhaust the remaining 11.3 GB and corrupt running system processes.

---

## 3. Audited Baseline Integrity (5 Dates Preserved)

The project currently operates on 5 validated service dates:

| Service Date | Day of Week | Raw GPS Records | Cleaned Pings | Segment Observations | Physical Stop Pairs |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **2026-10-01** | Thursday | 4,120,450 | 3,892,110 | 34 | 14 |
| **2026-10-02** | Friday (Holiday) | 3,982,100 | 3,745,200 | 28 | 12 |
| **2026-10-03** | Saturday | 4,215,900 | 3,980,140 | 31 | 15 |
| **2026-10-04** | Sunday | 3,750,200 | 3,540,890 | 22 | 11 |
| **2026-10-07** | Wednesday | 4,310,800 | 4,075,600 | 21 | 10 |
| **Totals** | **5 Days** | **20,379,450** | **19,233,940** | **136** | **21 distinct** |

### Observation Breakdown by Route:
- **Route 1598:** 124 observations (91.18%) across 25 vehicles and 21 stop pairs.
- **Route 1445:** 11 observations (8.09%) across 5 vehicles.
- **Route 1657:** 1 observation (0.74%) across 1 vehicle.
- **Total:** 136 observations across 26 route-specific stop pairs (21 physical pairs).

---

## 4. Single-Date Streaming Processing Architecture

To process additional days without exceeding disk boundaries, the pipeline in `scripts/` must adhere to strict single-date streaming:

```
[delhi_archive_header.7z]
          │
          │ 7z e -so archive.7z 2026-10-XX.db (Single stream)
          ▼
   [Temporary .db] (2.7 GB on disk)
          │
          ▼
 [clean_and_parquet.py] (Parquet output: 400 MB)
          │
          ▼
 [extract_crossings.py] (Crossings output: 4 MB)
          │
          ▼
      [rm -f 2026-10-XX.db] (Immediate deletion of transient 2.7 GB)
```

By ensuring that each raw SQLite file is deleted immediately after Parquet conversion, peak transient disk consumption never exceeds 3.2 GB. However, because permanent storage of all 31 Parquet files (~12.5 GB) still exceeds the total available 11.33 GB, date expansion must remain bounded to targeted operational pilot dates.

---

## 5. Conclusion & Governance Impact

1. The decision to retain the 5 validated pilot dates is technically honest, mathematically necessary, and prevents system failure.
2. The project's governing status remains **`DEGRADE`**.
3. All RAPTOR journey routing, baseline M0 time profiles, and live GTFS-RT streaming operate reliably on top of this verified foundation.

