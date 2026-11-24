# Milestone 2.2.1 Date Coverage & Archive Inventory Report

**Source Archive URL:** `https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z`  
**Archive Format:** 7-Zip (`lzma2` compressed, 15.0 GiB compressed / 115.5 GiB uncompressed)  
**Host Architecture:** macOS Apple Silicon (`darwin arm64`), 11 GiB Available Local APFS Storage  
**Audit Date:** November 21, 2026  
**Pipeline Tools:** `py7zr`, `HttpRangeReader`, DuckDB  

---

## 1. Complete Archive Date Inventory (October 1 – 31, 2026)

Inspection of the remote 7z archive header over HTTP range requests confirmed that **all 31 daily SQLite database files exist in the source archive** (`bus_movements_2026_10_01.db` through `bus_movements_2026_10_31.db`).

The table below documents the exact status of every date in the source archive:

| Date | Database File Name | Available in Archive | Extraction Attempted | Extraction Successful | Ingestion Successful | Stop-Crossing Processing | Partial-Day / Corrupted Status | Processing Status & Accounting Reason |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **2026-10-01** | `bus_movements_2026_10_01.db` | Yes | Yes | Yes | Yes | Yes | Complete | **Pilot Subset: Processed** (19.22M clean rows, 483.99 MB Parquet) |
| **2026-10-02** | `bus_movements_2026_10_02.db` | Yes | Yes | Yes | Yes | Yes | Complete (Holiday) | **Pilot Subset: Processed** (18.83M clean rows, 472.13 MB Parquet) |
| **2026-10-03** | `bus_movements_2026_10_03.db` | Yes | Yes | Yes | Yes | Yes | Complete (Weekend) | **Pilot Subset: Processed** (20.00M clean rows, 501.86 MB Parquet) |
| **2026-10-04** | `bus_movements_2026_10_04.db` | Yes | Yes | Yes | Yes | Yes | Complete (Weekend) | **Pilot Subset: Processed** (19.56M clean rows, 492.51 MB Parquet) |
| **2026-10-05** | `bus_movements_2026_10_05.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-06** | `bus_movements_2026_10_06.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-07** | `bus_movements_2026_10_07.db` | Yes | Yes | Yes | Yes | Yes | **Partial-Day Outage** | **Pilot Subset: Processed** (15.78M clean rows, 398.57 MB Parquet; halted 14:23 UTC / 19:53 IST) |
| **2026-10-08** | `bus_movements_2026_10_08.db` | Yes | Yes (Audit) | Yes | No | No | Complete (30.21M rows) | *Forensic Audit Only: Telemetry resumes 20:32 UTC / 02:02 IST* |
| **2026-10-09** | `bus_movements_2026_10_09.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-10** | `bus_movements_2026_10_10.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-11** | `bus_movements_2026_10_11.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-12** | `bus_movements_2026_10_12.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-13** | `bus_movements_2026_10_13.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-14** | `bus_movements_2026_10_14.db` | Yes | No | No | No | No | Complete (Fleet Exp.) | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-15** | `bus_movements_2026_10_15.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-16** | `bus_movements_2026_10_16.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-17** | `bus_movements_2026_10_17.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-18** | `bus_movements_2026_10_18.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-19** | `bus_movements_2026_10_19.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-20** | `bus_movements_2026_10_20.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-21** | `bus_movements_2026_10_21.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-22** | `bus_movements_2026_10_22.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-23** | `bus_movements_2026_10_23.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-24** | `bus_movements_2026_10_24.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-25** | `bus_movements_2026_10_25.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-26** | `bus_movements_2026_10_26.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-27** | `bus_movements_2026_10_27.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-28** | `bus_movements_2026_10_28.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-29** | `bus_movements_2026_10_29.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-30** | `bus_movements_2026_10_30.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |
| **2026-10-31** | `bus_movements_2026_10_31.db` | Yes | No | No | No | No | Complete in archive | *Unprocessed: Preserving host disk headroom (see Section 2)* |

---

## 2. Storage Capacity Limitation & Pilot Subset Classification

The current processed dataset consists of **5 representative service dates** (October 1, 2, 3, 4, and 7, 2026) and is explicitly designated as a **Pilot Subset**, NOT full-month historical coverage.

### Storage Capacity Audit
- **Host Machine Total Disk:** 228 GiB
- **Host Machine Currently Available Free Space:** **11 GiB**
- **Average Size of One Ingested Daily Parquet Partition:** `~470 MB`
- **Average Size of One Daily Quarantine Parquet File:** `~280 MB`
- **Combined Daily Storage Requirement:** `~750 MB per date`
- **Projected Storage for Remaining 26 Dates:** $26 \times 750\text{ MB} \approx \mathbf{19.5\text{ GB}}$
- **Total Combined Storage for 31 Dates:** $31 \times 750\text{ MB} \approx \mathbf{23.25\text{ GB}}$

Because **23.25 GB exceeds the available 11 GiB host disk headroom**, bulk processing of all 31 days would cause disk exhaustion and fatal crash around Day 12. 

The 5 processed dates were strategically selected to capture all critical operational regimes:
1. `2026-10-01` (Thursday): Regular Weekday Commute Baseline
2. `2026-10-02` (Friday): Gandhi Jayanti (National Public Holiday)
3. `2026-10-03` (Saturday): Weekend High-Commercial Operations
4. `2026-10-04` (Sunday): Weekend Off-Peak Free Flow
5. `2026-10-07` (Wednesday): Anomalous Midweek Outage Day

This pilot subset encompasses **147,869,768 raw observations** and **93,389,652 clean Parquet records** while safely maintaining **11 GiB of free disk space** on the host machine.

