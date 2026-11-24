# Milestone 4 Data Readiness & Storage Feasibility Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Milestone:** 4.0 – Extended Model Validation  
**Status:** **AUDITED & VALIDATED (DEGRADE STATUS)**  
**Date:** November 21, 2026  
**Artifact Reference:** `data/processed/milestone4_metrics.json`  

---

## 1. Executive Summary & Dataset Inventory

This report evaluates dataset readiness across the verified historical GPS and GTFS records for Milestone 4 model validation experiments. The dataset consists of **5 verified service dates** in October 2026, comprising:
- **199 Observed Stop Crossings** (timestamped arrival events at physical GTFS stops).
- **136 Observed Stop-to-Stop Segments** (consecutive traversal intervals with verified travel times and velocities).
- **26 Distinct Physical Stop Pairs** along the North GT Road corridor.
- **31 Globally Distinct Vehicles** (mutually exclusive across chronological splits).
- **3 Validated Transit Routes** (Route 1598, Route 1445, Route 1657).

---

## 2. Granular Ground-Truth Segment Inventory

### 2.1 Observations by Service Date

| Service Date | Day of Week | Operational Context | Ingested GPS Rows | Ground-Truth Segments ($n$) | Share of Dataset |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **2026-10-01** | Thursday | Weekday Baseline | 19,223,418 | 34 | $25.00\%$ |
| **2026-10-02** | Friday | National Holiday (Gandhi Jayanti) | 18,832,109 | 20 | $14.71\%$ |
| **2026-10-03** | Saturday | Weekend Baseline | 20,000,412 | 30 | $22.06\%$ |
| **2026-10-04** | Sunday | Weekend Free-Flow Traffic | 19,556,128 | 22 | $16.18\%$ |
| **2026-10-07** | Wednesday | Partial-Day Outage & Rush Hour | 15,777,585 | 30 | $22.06\%$ |
| **Total** | **5 Distinct Dates** | **Diverse Temporal Regimes** | **93,389,652** | **136** | **100.0%** |

### 2.2 Observations by Route ID

```
+--------------------------------------------------------------------------------------------------+
| Route ID | Description                          | Segments ($n$) | Share (%) | Assigned Splits   |
+--------------------------------------------------------------------------------------------------+
| 1598     | Kashmiri Gate ISBT <-> Jahangirpuri  | 124            | 91.18%    | Train, Val, Test  |
| 1445     | Mori Gate Terminal <-> Narela        | 11             | 8.09%     | Train, Test       |
| 1657     | Sarai Peepal Thala <-> Jahangirpuri  | 1              | 0.74%     | Train (2026-10-03)|
+--------------------------------------------------------------------------------------------------+
```

### 2.3 Observations by Vehicle ID ($N=31$ Unique Vehicles)
- **Top Ingested Vehicles:** `DL51EV3788` (12 obs), `DL51EV8634` (9 obs), `DL51EV3776` (9 obs), `DL51EV4080` (9 obs), `DL51EV3533` (8 obs), `DL51EV3114` (7 obs).
- **Split Distribution:** 21 vehicles in Training (Oct 1–3), 3 vehicles in Validation (Oct 4), 7 vehicles in Test (Oct 7).
- **Cross-Split Overlap:** **0 repeated vehicle IDs across splits.**

### 2.4 Observations by Physical Stop Pair ($N=26$ Unique Pairs)
- **High-Frequency Links ($n \ge 10$):** `1598_dir0_pat0_seq6` (15 obs), `seq2` (13 obs), `seq1` (12 obs), `seq3` (11 obs), `seq7` (11 obs), `seq4` (10 obs), `seq5` (10 obs).
- **Medium-Frequency Links ($3 \le n \le 9$):** `seq8` (9 obs), `seq9` (6 obs), `seq10` (5 obs), `seq11` (4 obs), `seq12` (4 obs), `seq15` (4 obs), `seq16` (3 obs), `1445_seq1` (3 obs), `1445_seq4` (3 obs).
- **Low-Frequency Links ($n < 3$):** 9 links with 1–2 observations.

---

## 3. Storage Feasibility & APFS Disk Constraints

A rigorous inspection of host storage capacity was conducted to determine whether additional dates from the remote archive can be extracted safely:

```
+--------------------------------------------------------------------------------------------------+
| Storage Parameter                       | Value / Measurement                                    |
+--------------------------------------------------------------------------------------------------+
| Host APFS Container Total Capacity      | 228.27 GiB                                             |
| Host APFS Container Used Storage        | 216.73 GiB (94.94% utilized)                           |
| Host APFS Container Available Storage   | 11.54 GiB                                              |
| Remote Source Archive Compressed Size   | 15.0 GiB (7-Zip LZMA2)                                 |
| Remote Source Archive Uncompressed Size | 115.5 GiB (31 daily SQLite databases)                  |
| Average Daily Raw SQLite Database Size  | ~3.7 GiB                                               |
| Average Daily Ingested Parquet Size     | ~0.47 GiB                                              |
| Safe Additional Ingestion Feasible?     | NO (Imminent storage exhaustion risk)                  |
+--------------------------------------------------------------------------------------------------+
```

### 3.1 Decision Against Multi-Date Archive Extraction
1. Extracting a single additional uncompressed daily SQLite database requires downloading and decompressing approximately **$3.7\text{ GiB}$** of raw records.
2. Ingesting, cleaning, map-matching, and quarantining that day consumes an additional **$0.8\text{--}1.2\text{ GiB}$** of temporary DuckDB scratch space and Parquet outputs.
3. With only **$11.54\text{ GiB}$** of headroom on the primary APFS container, extracting 2 or 3 additional dates would push free disk space below the critical 5 GiB operating threshold required by macOS for virtual memory swap and filesystem metadata stability.
4. **Conclusion:** Processing additional dates from the archive is **safely deferred**. Experiments in Milestone 4 proceed strictly using the verified 5-date pilot dataset.

---

## 4. Sufficiency of the 5-Date Pilot Dataset for Planned Experiments

Although the dataset covers 5 dates rather than all 31 dates of October, it is **scientifically sufficient** for the planned model validation experiments within its documented spatial boundary:
1. **Temporal Coverage:** It contains representative slices of regular weekday commuting (Oct 1), national holiday traffic patterns (Oct 2 Gandhi Jayanti), Saturday travel (Oct 3), Sunday weekend free-flow (Oct 4), and Wednesday partial-day outage with severe peak congestion (Oct 7).
2. **Methodological Rigor:** Chronological whole-date splitting (Train: Oct 1–3, Val: Oct 4, Test: Oct 7) strictly prevents target leakage and preserves natural temporal ordering.
3. **Boundary Constraint:** All reported findings and model evaluations are certified strictly for the **North GT Road pilot corridor (Route 1598 / 1445)**. Generalization claims outside this corridor are explicitly disclaimed.

