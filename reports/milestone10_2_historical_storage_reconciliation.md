# Milestone 10.2: Historical GPS Archive Storage Reconciliation & Disk Feasibility Audit

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0 & Milestone 10.2 Specification  
**Raw Archive Inspected:** `/tmp/delhi_archive_header.7z` (31 daily SQLite files)  
**Host Storage Volume:** `/dev/disk3s1s1` mounted on `/`  
**Audit Timestamp:** November 21, 2026  

---

## 1. Executive Summary

This report reconciles the storage metrics of the October 2026 historical Delhi bus GPS archive across all project phases. By auditing the actual 7z archive headers using 7-Zip v26.06 and measuring disk filesystem blocks, we reconcile the previously reported discovery figure of **115.50 GiB uncompressed** with the extraction estimates from Milestone 10.1.

### Core Reconciled Findings:
1. **Mathematical Units Consistency:**
   - **Binary GiB ($2^{30} = 1,073,741,824$ bytes):** Total uncompressed size is **115.50 GiB**.
   - **Decimal GB ($10^9 = 1,000,000,000$ bytes):** Total uncompressed size is **124.02 GB**.
2. **Compressed Archive:**
   - **16,077,235,732 bytes** = **14.97 GiB** = **16.08 GB**.
3. **Current Available Storage on Host:**
   - Total volume capacity: 228.27 GiB (245.11 GB).
   - Used capacity: 216.99 GiB (232.99 GB, **95.06% full**).
   - **Available free space:** **11.29 GiB** (**12.12 GB**).
4. **Deficit Analysis:**
   - Total uncompressed size of the 26 remaining days: **100.43 GiB** (**107.84 GB**).
   - Permanent Parquet storage required for remaining 26 days: **15.29 GiB** (**16.42 GB**).
   - Because even the permanent compressed Parquet requirement (15.29 GiB) exceeds the available free space (11.29 GiB), processing the full month on this host without external storage is **physically impossible**.
5. **Operational Safeguard:**
   - The verified 5-day baseline (136 ground-truth segment observations) is safely preserved.

---

## 2. Exact 7-Zip Archive Header Inventory

Direct measurement via `/opt/homebrew/bin/7z l /tmp/delhi_archive_header.7z`:

- **Archive Type:** 7z non-solid archive (`Solid = -`, Method `LZMA2:24`, 31 independent blocks).
- **Physical Compressed Size:** 16,077,235,732 bytes (**14.97 GiB** / **16.08 GB**).
- **Total Uncompressed Size (31 files):** 124,016,046,080 bytes (**115.50 GiB** / **124.02 GB**).

### Daily Breakdown:

```
Service Date   File Name                      Uncompressed (Bytes)  Uncompressed (GiB)  Uncompressed (GB)  Compressed (Bytes)
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
2026-10-01 *   bus_movements_2026_10_01.db    3,420,090,368         3.18 GiB            3.42 GB            467,018,574
2026-10-02 *   bus_movements_2026_10_02.db    3,204,751,360         2.98 GiB            3.20 GB            448,757,283
2026-10-03 *   bus_movements_2026_10_03.db    3,450,224,640         3.21 GiB            3.45 GB            479,907,099
2026-10-04 *   bus_movements_2026_10_04.db    3,306,258,432         3.08 GiB            3.31 GB            465,294,074
2026-10-05     bus_movements_2026_10_05.db    3,428,802,560         3.19 GiB            3.43 GB            448,206,273
2026-10-06     bus_movements_2026_10_06.db    3,374,170,112         3.14 GiB            3.37 GB            457,564,908
2026-10-07 *   bus_movements_2026_10_07.db    2,796,498,944         2.60 GiB            2.80 GB            381,903,738
2026-10-08     bus_movements_2026_10_08.db    3,308,322,816         3.08 GiB            3.31 GB            456,915,647
2026-10-09     bus_movements_2026_10_09.db    3,225,186,304         3.00 GiB            3.23 GB            425,154,424
2026-10-10     bus_movements_2026_10_10.db    2,934,251,520         2.73 GiB            2.93 GB            405,277,656
2026-10-11     bus_movements_2026_10_11.db    2,870,554,624         2.67 GiB            2.87 GB            394,348,822
2026-10-12     bus_movements_2026_10_12.db    2,871,775,232         2.67 GiB            2.87 GB            394,693,960
2026-10-13     bus_movements_2026_10_13.db    3,142,774,784         2.93 GiB            3.14 GB            429,876,465
2026-10-14 ^   bus_movements_2026_10_14.db    4,447,977,472         4.14 GiB            4.45 GB            564,170,327
2026-10-15 ^   bus_movements_2026_10_15.db    4,512,301,056         4.20 GiB            4.51 GB            576,538,937
2026-10-16 ^   bus_movements_2026_10_16.db    4,480,024,576         4.17 GiB            4.48 GB            570,892,721
2026-10-17 ^   bus_movements_2026_10_17.db    4,636,160,000         4.32 GiB            4.64 GB            592,212,324
2026-10-18 ^   bus_movements_2026_10_18.db    4,450,844,672         4.14 GiB            4.45 GB            573,393,267
2026-10-19 ^   bus_movements_2026_10_19.db    4,513,939,456         4.20 GiB            4.51 GB            577,351,465
2026-10-20 ^   bus_movements_2026_10_20.db    4,222,730,240         3.93 GiB            4.22 GB            543,161,475
2026-10-21 ^   bus_movements_2026_10_21.db    4,661,882,880         4.34 GiB            4.66 GB            592,840,188
2026-10-22 ^   bus_movements_2026_10_22.db    4,780,064,768         4.45 GiB            4.78 GB            602,007,035
2026-10-23 ^   bus_movements_2026_10_23.db    4,846,338,048         4.51 GiB            4.85 GB            610,248,907
2026-10-24 ^   bus_movements_2026_10_24.db    4,831,023,104         4.50 GiB            4.83 GB            604,422,225
2026-10-25 ^   bus_movements_2026_10_25.db    4,531,556,352         4.22 GiB            4.53 GB            579,840,712
2026-10-26 ^   bus_movements_2026_10_26.db    4,624,805,888         4.31 GiB            4.62 GB            579,164,799
2026-10-27 ^   bus_movements_2026_10_27.db    4,779,094,016         4.45 GiB            4.78 GB            584,684,737
2026-10-28 ^   bus_movements_2026_10_28.db    4,831,346,688         4.50 GiB            4.83 GB            592,678,662
2026-10-29 ^   bus_movements_2026_10_29.db    4,348,997,632         4.05 GiB            4.35 GB            539,941,202
2026-10-30 ^   bus_movements_2026_10_30.db    4,408,160,256         4.11 GiB            4.41 GB            542,579,668
2026-10-31 ^   bus_movements_2026_10_31.db    4,775,137,280         4.45 GiB            4.78 GB            596,188,158
─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Total (31 Days)                               124,016,046,080       115.50 GiB          124.02 GB          16,077,235,732
```
*\* Denotes 5 processed pilot dates (Oct 1–4, 7). ^ Denotes days following the Oct 14 cluster bus expansion.*

---

## 3. Storage Reconciliation: Why Discovery & M10.1 Reports Differ

1. **Gate 0 Discovery Report (`reports/data_discovery.md`):**  
   Reported **115.50 GiB uncompressed**.  
   *Exact math:* $124,016,046,080 / 1024^3 = 115.4989\text{ GiB} \approx \mathbf{115.50\text{ GiB}}$. This measured all 31 days using binary GiB.
2. **Milestone 10.1 Report (`reports/milestone10_1_historical_gps_audit.md`):**  
   Estimated **88.0 GB temporary space**.  
   *Reconciliation:* This figure represented an approximate decimal calculation for the 26 remaining days ($26 \times \sim 3.4\text{ GB} \approx 88.4\text{ GB}$).  
   *Exact measured sum for remaining 26 days:* **107,838,222,336 bytes** = **100.43 GiB** = **107.84 GB**. The jump in daily size from Oct 14 onwards (~4.5 GB/day) accounts for the higher true total.

---

## 4. Host Storage Capacity & Deficit Analysis

### 4.1 Live Filesystem Measurement
```
Total Space:      245,107,195,904 bytes  (228.27 GiB / 245.11 GB)
Used Space:       232,988,778,496 bytes  (216.99 GiB / 232.99 GB)  [95.06% capacity]
Free Space:        12,118,417,408 bytes  ( 11.29 GiB /  12.12 GB)
```

### 4.2 Storage Requirements vs Available Disk

```
┌───────────────────────────────────────────────┬───────────────────┬───────────────────┬─────────────────┐
│ Requirement Category                          │ Binary Value      │ Decimal Value     │ Host Deficit    │
├───────────────────────────────────────────────┼───────────────────┼───────────────────┼─────────────────┤
│ Available Free Disk Space                     │ 11.29 GiB         │ 12.12 GB          │ —               │
│ Naive Full Extraction (26 SQLite files)       │ 100.43 GiB        │ 107.84 GB         │ -89.14 GiB      │
│ Peak Single-Day Transient Space (Pipelined)   │ 4.51 GiB (Day 23) │ 4.85 GB (Day 23)  │ +6.78 GiB (1 d) │
│ Permanent Parquet for 26 Remaining Days       │ 15.29 GiB         │ 16.42 GB          │ -4.00 GiB       │
│ Peak Combined Working Space (Day 23 + Parquet)│ 19.80 GiB         │ 21.27 GB          │ -8.51 GiB       │
└───────────────────────────────────────────────┴───────────────────┴───────────────────┴─────────────────┘
```

### 4.3 Why Even Pipelined Streaming Cannot Finish:
In a pipelined streaming strategy:
1. Extract Day $N$ SQLite database (~4.5 GB).
2. Clean and convert to Parquet (~630 MB).
3. Extract stop crossings and segments (~5 MB).
4. Delete Day $N$ SQLite database.
5. Repeat for Day $N+1$.

While step 1 fits in the free space for the first few days, the permanent Parquet files accumulate on disk. At ~630 MB per day, 18 days of Parquet consume $18 \times 630\text{ MB} = 11.34\text{ GB}$, **completely exhausting the host free space (11.29 GiB)** around day 18, causing subsequent SQLite extractions to crash with `ENOSPC`.

---

## 5. Safe Extraction Strategy & Recommendation

1. **Current Host Action:** Gating processing to the 5 validated dates (Oct 1–4, 7) is **physically mandatory**.
2. **Safe Future Execution Plan:**
   - Attach an external APFS volume or secondary disk with at least **35 GB of free space**.
   - Direct extraction and intermediate staging to the external volume (`/Volumes/External/staging_gps/`).
   - Stream Parquet partitions incrementally with verification checkpoints.
3. **Preserved Baseline:** The 136 segment traversals across Routes 1598 (124), 1445 (11), and 1657 (1) remain mathematically verified, reproducible, and intact.

