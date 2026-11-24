# Milestone 2.2 Ingestion Coverage & Storage Audit Report

**Service Dates Processed:** October 1, 2, 3, 4, and 7, 2026 (`2026-10-01` to `2026-10-07`)  
**Pipeline Module:** `scripts/ingest_gps.py` & `scripts/process_historical_batch.py`  
**Underlying Storage Engine:** DuckDB + Apache Parquet (ZSTD Level 7 Compression)  
**Host Architecture:** macOS Apple Silicon (`darwin arm64`), Local APFS File System  
**Date of Audit:** November 21, 2026  

---

## 1. Multi-Day Ingestion & Cleaning Statistics

Across the 5 processed historical dates, a total of **147,869,768 raw GPS observations** were ingested, deduplicated, validated, and compressed into clean, partitioned Parquet format.

| Service Date | Day of Week | Operating Category | Raw Observations | Rule E01 Exact Dupes Removed | Rule E02 Conflicting Rows Quarantined | Rule E03 Out-of-Bounds Quarantined | Clean Parquet Rows Retained | Retention Rate (%) | Distinct Active Buses | Parquet Size on Disk | Compression Ratio |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **2026-10-01** | Thursday | Weekday Baseline | 31,290,299 | 0 (0.00%) | 12,071,325 | 3,466 | **19,215,508** | 61.41% | 6,264 | 483.99 MB | 6.5x |
| **2026-10-02** | Friday | Gandhi Jayanti (Holiday) | 29,314,267 | 0 (0.00%) | 10,476,757 | 3,676 | **18,833,834** | 64.25% | 6,104 | 472.13 MB | 6.2x |
| **2026-10-03** | Saturday | Weekend Service | 31,516,372 | 0 (0.00%) | 11,509,487 | 3,377 | **20,003,508** | 63.47% | 6,264 | 501.86 MB | 6.6x |
| **2026-10-04** | Sunday | Weekend Service | 30,213,040 | 0 (0.00%) | 10,653,529 | 3,335 | **19,556,176** | 64.73% | 6,197 | 492.51 MB | 6.4x |
| **2026-10-07** | Wednesday | Anomalous Partial Day | 25,535,790 | 0 (0.00%) | 9,752,262 | 2,902 | **15,780,626** | 61.80% | 6,258 | 398.57 MB | 6.7x |
| **Total** | **5 Full Days** | **Combined Archive** | **147,869,768** | **0 (0.00%)** | **54,463,360** | **16,756** | **93,389,652** | **63.16%** | **6,264 (peak)** | **2,349.06 MB** | **6.5x** |

---

## 2. Ingestion Quality Rule Breakdown

### Rule E01: Exact Duplicate Row Filtering
- Across all 5 dates, 0 rows exhibited exact byte-for-byte duplication across all columns simultaneously. The crawler polling architecture created record variations primarily in timestamps and speed.

### Rule E02: Conflicting Duplicate Resolution & Quarantine
- A total of **54,463,360 conflicting rows** ($36.83\%$ of raw observations) were quarantined to `data/processed/quarantine/conflicts_*.parquet`.
- In Delhi's real-time telemetry feed, the transit server crawler polled vehicle endpoints every 10 seconds. When vehicle onboard units re-transmitted or reported asynchronous positions at identical UTC seconds, multiple rows per `(vehicle_id, timestamp)` were recorded.
- **Deterministic Resolution Policy:** Rows were ordered by `speed DESC, lat, lng` using DuckDB window ranking (`ROW_NUMBER()`). The top-ranked row was retained in clean Parquet, while all conflicting rows were preserved in compressed quarantine with `conflict_rank`, `conflict_group_size`, and `quarantine_reason = 'E02_CONFLICTING_TIMESTAMP_POSITION'`.

### Rule E03: Spatial Bounding Box Validation
- A total of **16,756 out-of-bounds rows** ($0.011\%$ of raw observations) were quarantined to `data/processed/quarantine/out_of_bounds_*.parquet`.
- Bounding box: Latitude $[28.00^\circ, 29.20^\circ\text{ N}]$, Longitude $[76.50^\circ, 77.80^\circ\text{ E}]$.
- Spurious GNSS receiver lock coordinates (e.g. $[0.0, 0.0]$, inverted coordinates, or readings outside Delhi NCR) were quarantined.

---

## 3. Handling of the October 7 Partial-Day Telemetry Anomaly

Inspection of the raw October 7 partition confirmed the anomaly documented in Milestone 0:
- **Telemetry Span:** 2026-10-06 18:00:47 IST to 2026-10-07 14:23:23 IST (telemetry abruptly halted at 14:23:23 IST due to an upstream server outage).
- **Impact on Ingestion:** Total raw rows were 25,535,790 (approximately 5.7M fewer than full operating days).
- **Pipeline Handling:** The ingestion pipeline handled the truncated stream gracefully without error. Timestamps were projected to Asia/Kolkata, clean rows (15,780,626) were saved, and stop crossings (39 crossings, 30 segments) were extracted across the available morning and midday hours.

---

## 4. Host Storage Management & Disk Safety Lifecycle

A major engineering challenge of processing historical daily SQLite archives on a host machine with ~11–13 GiB free disk space was preventing disk exhaustion:
- The full 31-day uncompressed archive is **115.5 GiB**.
- The remote 7z archive is **15.0 GiB**.
- **Streaming Pipeline Architecture:** We implemented a custom `HttpRangeReader` in Python that requests only the specific byte offsets of individual daily SQLite files (`~440 MB` compressed / `~3.0 GiB` uncompressed) directly from the Cloudflare R2 bucket.
- **Immediate Lifecycle Deletion:**
  1. Check free disk space before extraction ($> 4,000\text{ MB}$ safety gate).
  2. Extract target `.db` into `/tmp/gps_extract_m22/`.
  3. Ingest and write typed Parquet partition into `data/processed/gps_parquet/service_date=YYYY-MM-DD/`.
  4. Write quarantine Parquet partitions into `data/processed/quarantine/`.
  5. Verify output row counts and non-null constraints.
  6. **Immediately unlink/delete the raw 3.0 GiB SQLite `.db`**.
- **Disk Headroom Audit:**
  - Initial free space: **10,774.1 MB**
  - Minimum free space during peak extraction: **6,951.0 MB** (comfortably above the 4,000 MB safety threshold)
  - Final free space at milestone completion: **9,074.0 MB**
  - Total Parquet data storage footprint: **2,349.06 MB** (2.29 GB for 93.38M clean rows across 5 dates).

