# GPS Data Quality and Cleaning Report
## Delhi Real-Time Bus Traffic Model & Journey Planner

**Date:** 21 November 2026  
**Milestone:** 1 – GTFS and GPS Data Ingestion  
**Status:** Ingested, Cleaned & Quarantined  
**Partition Output:** [`data/processed/gps_parquet/service_date=2026-10-01/data.parquet`](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/gps_parquet/service_date=2026-10-01/data.parquet)  
**Quarantine Output:** [`data/processed/quarantine/`](file:///Users/gauravchauhan/Downloads/delhi_hacks/data/processed/quarantine/)

---

## 1. Executive Summary

Milestone 1 implemented the end-to-end cleaning and ingestion pipeline (`scripts/ingest_gps.py`) executing rules E01 through E08 as specified in PRD Section 6.2. The pipeline safely ingests the daily SQLite database, eliminates polling duplicates, deterministically resolves timestamp conflicts without silent data loss, filters coordinate outliers into audit quarantine partitions, and outputs compressed, typed Parquet partitions with dual UTC and Asia/Kolkata local timestamps.

---

## 2. Day 1 GPS Ingestion & Cleaning Accounting

| Stage / Filter | Condition / Action | Records Before | Records Dropped / Quarantined | Records Retained | Retention % |
|---|---|---:|---:|---:|---:|
| **Raw Input** | Extracted from `bus_movements_2026_10_01.db` | — | — | **31,290,299** | 100.00% |
| **Duplicate Timestamp Resolution (E01 / E02)** | Same `(vehicle_id, timestamp)`. Ranked deterministically by `speed DESC, lat, lng`. Rank > 1 quarantined. | 31,290,299 | **12,071,325** | **19,218,974** | 61.42% |
| **Spatial Bounding Box Filter (E03)** | Lat outside `[28.0, 29.2]` or Lng outside `[76.5, 77.8]`. Quarantined. | 19,218,974 | **3,466** | **19,215,508** | 61.41% |
| **Final Clean Retained Partition** | Typed, compressed Parquet partition (`service_date=2026-10-01`) | — | — | **19,215,508** | **61.41%** |

---

## 3. Safe Duplicate Handling & Quarantine Auditing

Per PRD Section 6.2, conflicting duplicate observations must never be silently discarded.

1. **Quarantine Partition 1: Conflicting Duplicates (`E02`)**
   - **File:** `data/processed/quarantine/conflicts_2026-10-01.parquet`
   - **Quarantined Count:** **12,071,325 rows**
   - **Reason Code:** `E02_CONFLICTING_TIMESTAMP_POSITION`
   - **Deterministic Resolution Method:** For each `(vehicle_id, timestamp)` collision group, records were ordered by `speed DESC, lat, lng`. The highest-confidence row (rank 1) was retained in the clean partition, while all secondary rows (rank > 1) were serialized to the quarantine archive with group size and rank metadata.
2. **Quarantine Partition 2: Out-of-Bounds Coordinates (`E03`)**
   - **File:** `data/processed/quarantine/out_of_bounds_2026-10-01.parquet`
   - **Quarantined Count:** **3,466 rows** (0.018% of observations)
   - **Reason Code:** `E03_OUT_OF_BOUNDS_COORDINATE`

---

## 4. Final Output Partition Verification

The generated Parquet partition was validated using DuckDB:
```bash
python3 -c "import duckdb; print(duckdb.execute('SELECT COUNT(*), COUNT(DISTINCT vehicle_id) FROM read_parquet(\"data/processed/gps_parquet/service_date=2026-10-01/data.parquet\")').fetchall())"
```

### Partition Metadata
- **Path:** `data/processed/gps_parquet/service_date=2026-10-01/data.parquet`
- **Output File Size:** **483.99 MB** (Compressed using Zstandard `ZSTD`)
- **Raw Input Size:** 3,420,090,368 bytes (3.18 GiB)
- **Effective Storage Compression Ratio:** **6.7x**
- **Clean Observation Count:** **19,215,508**
- **Active Fleet on Day 1:** **6,264 distinct buses**
- **Active Routes on Day 1:** **2,201 distinct routes**
- **Canonical Trips Identified:** **80,637 distinct trips**

### Column Schema in Ingested Parquet
| Field | Type | Description |
|---|---|---|
| `vehicle_id` | VARCHAR | Delhi bus registration plate (e.g. `DL1PD6884`) |
| `lat` | DOUBLE | Validated WGS84 latitude (`[28.0, 29.2]`) |
| `lng` | DOUBLE | Validated WGS84 longitude (`[76.5, 77.8]`) |
| `speed_kmh` | DOUBLE | Instantaneous speed in km/h ($\ge 0.0$) |
| `route_id` | VARCHAR | Normalized route string without float artifact (e.g. `"1000"`) |
| `trip_id_raw` | VARCHAR | Original GPS trip string (e.g. `"1000_08_30_1234"`) |
| `trip_id_canonical` | VARCHAR | Scheduled departure trip prefix (e.g. `"1000_08_30"`) |
| `timestamp_utc` | BIGINT | Unix epoch seconds in UTC |
| `timestamp_ist` | TIMESTAMP WITH TIME ZONE | Explicitly projected local IST timestamp (`Asia/Kolkata`) |
| `service_date` | DATE | Service calendar date (`2026-10-01`) |
| `hour_ist` | INTEGER | Local service hour (`0` to `23`) |
| `minute_ist` | INTEGER | Local service minute (`0` to `59`) |
| `day_of_week` | INTEGER | Day of week (`0` = Sunday, `1` = Monday... `6` = Saturday) |
| `is_weekend` | BOOLEAN | `true` if Saturday or Sunday, else `false` |

---

## 5. Automated Data Quality Assertions

All automated tests in [`backend/tests/test_gps_cleaning.py`](file:///Users/gauravchauhan/Downloads/delhi_hacks/backend/tests/test_gps_cleaning.py) passed:
- `test_gps_cleaning_logic`: Verifies mock duplicate collapse, deterministic rank quarantine, and regex prefix extraction.
- `test_ingested_parquet_partition`: Asserts $>10\text{M}$ clean rows, zero out-of-bounds coordinates, and non-negative speeds.

