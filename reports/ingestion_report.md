# Ingestion Report
## Delhi Real-Time Bus Traffic Model & Journey Planner

**Date:** 21 November 2026  
**Milestone:** 1 – GTFS and GPS Data Ingestion  
**Status:** Ingested, Tested & Verified (All 5 Automated Tests Passing)  
**Deliverables:**
- [`scripts/ingest_gtfs.py`](file:///Users/gauravchauhan/Downloads/delhi_hacks/scripts/ingest_gtfs.py)
- [`scripts/ingest_gps.py`](file:///Users/gauravchauhan/Downloads/delhi_hacks/scripts/ingest_gps.py)
- [`reports/gtfs_validation.md`](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/gtfs_validation.md)
- [`reports/gps_quality_report.md`](file:///Users/gauravchauhan/Downloads/delhi_hacks/reports/gps_quality_report.md)
- [`data/processed/ingestion_metrics.json`](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/ingestion_metrics.json)

---

## 1. Executive Summary

Milestone 1 successfully established the data ingestion and validation infrastructure for the Delhi Bus Traffic Model. 

Key results achieved:
1. **GTFS Serving Layer:** Fully structured SQLite database created at `data/serving/delhi_bus.db` with indexed stops, routes, trips, shapes, and stop-times.
2. **Full Dataset Integrity:** Verified complete open-data GTFS feed (`mdb-1262`): **2,964 routes, 78,515 trips, 6,342 stops, 3,276,092 stop-times** with **100.0% referential integrity** (zero orphan records across all foreign keys).
3. **GPS Streaming Pipeline:** Ingested Day 1 (`2026-10-01`) of the October 2026 GPS archive. Safely processed **31,290,299 raw observations**, resolved **12,071,325 conflicting duplicates** into quarantine audit partitions, and produced **19,215,508 clean records** stored in compressed ZSTD Parquet format (**483.99 MB**, a **6.7x compression ratio** from raw SQLite).
4. **Automated Testing:** All 5 unit and integration tests passed cleanly (`pytest backend/tests/ -v`).

---

## 2. Ingestion Inventory

| Source Dataset | Format | Raw Size | Processed Output | Rows Ingested | Status |
|---|---|---:|---|---:|:---:|
| Static GTFS (Serving) | Text CSVs $\to$ SQLite | 120.3 MB | `data/serving/delhi_bus.db` | 3,276,092 (stop_times) | **VERIFIED** |
| Historical GPS (Day 1) | SQLite $\to$ Parquet | 3.18 GiB | `data/processed/gps_parquet/service_date=2026-10-01/` | **19,215,508** (clean) | **VERIFIED** |
| GPS Conflict Quarantine | SQLite $\to$ Parquet | — | `data/processed/quarantine/conflicts_2026-10-01.parquet` | **12,071,325** | **AUDITED** |
| GPS Bounds Quarantine | SQLite $\to$ Parquet | — | `data/processed/quarantine/out_of_bounds_2026-10-01.parquet` | **3,466** | **AUDITED** |

---

## 3. Storage Validation & Safe Streaming Strategy

### 3.1 Current Disk Storage Status
- **Disk Volume:** `/dev/disk3s5` (`/System/Volumes/Data`)
- **Total Capacity:** 228 GiB
- **Available Free Space:** **11.2 GiB**
- **Disk Safety Guard:** `scripts/ingest_gps.py` includes a pre-flight disk check (`check_disk_space(required_mb=2048)`) that halts immediately if free disk drops below 2 GB.

### 3.2 Full-Month Storage Forecast & Streaming Ingestion
- **Archive Compressed Size:** 14.97 GiB (31 independent blocks)
- **Archive Uncompressed Size:** 115.50 GiB
- **Parquet Storage Efficiency:** Day 1 compressed from 3.18 GiB SQLite to 0.48 GiB Parquet (**6.7x compression**).
- **Full Month Parquet Estimate:** $31 \times 0.48\text{ GB} \approx 14.8\text{ GB}$.
- **Safe Streaming Ingestion Procedure:**
  Because the 7z archive is non-solid (`Solid = -`), each day's SQLite database is extracted individually, converted into Parquet, verified for row count and schema completeness, and then the temporary uncompressed SQLite `.db` is removed before extracting the next day. This ensures peak temporary disk consumption never exceeds ~4.0 GB at any single point in time.

---

## 4. Anomaly Handling Across October 2026

The pipeline configuration (`config/split.yaml` and `scripts/ingest_gps.py`) explicitly accounts for key anomalies identified during data discovery:
1. **October 7 Partial-Day Anomaly:**
   - Raw database file is 2.80 GB (ending ~19:51:50 IST, ~18% lower volume than typical weekdays).
   - Ingestion script processes all available pings and flags the partition metadata with `partial_day=true`.
2. **October 14 Fleet Step-Change:**
   - Daily uncompressed database size jumps from ~3.2 GB to ~4.5 GB as Cluster Bus feeds were integrated alongside DTC buses.
   - Distinct vehicle count rises from ~6,200 to ~9,500.
   - The chronological training split (October 1–18) covers days on both sides of this transition (13 pre-expansion days and 5 post-expansion days), allowing the model to adapt to both DTC and Cluster bus characteristics.
3. **Festival Dips (Oct 2 Gandhi Jayanti, Oct 20 Dussehra, Oct 31 Diwali):**
   - Volume drops to weekend levels (2.8 to 4.2 GB). Handled via holiday day-type flags in `config/model.yaml`.

---

## 5. Automated Test Results

Executed test suite: `pytest -v`:
```text
backend/tests/test_gps_cleaning.py::test_gps_cleaning_logic PASSED        [ 20%]
backend/tests/test_gps_cleaning.py::test_ingested_parquet_partition PASSED  [ 40%]
backend/tests/test_gtfs_ingestion.py::test_time_conversion PASSED         [ 60%]
backend/tests/test_gtfs_ingestion.py::test_gtfs_serving_database PASSED   [ 80%]
backend/tests/test_gtfs_ingestion.py::test_full_mdb_referential_integrity PASSED [100%]

============================== 5 passed in 1.23s ===============================
```

All acceptance criteria for Milestone 1 are satisfied.

