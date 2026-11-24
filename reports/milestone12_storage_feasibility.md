# Milestone 12 — Storage Feasibility and Capacity Audit

**Governing Specification:** PRD v3.0  
**Audit Timestamp:** 2026-11-22T01:55:00Z  
**Governing Status:** `DEGRADE`  
**Milestone Scope:** Planning and Feasibility Assessment Only (No Extraction of Remaining 26 Days)  
**Evaluated Verdict:** `READY_WITH_STORAGE_CONSTRAINTS`

---

## 1. Executive Summary & Objective

The objective of **Milestone 12** is to establish a verified, storage-safe technical architecture and feasibility plan to extract, validate, and process the complete **October 2026 historical GPS dataset** (31 calendar days) from the Delhi Transport Corporation (DTC) bus fleet. 

Under the governing requirements of PRD v3.0, existing work must be protected:
1. All 5 pilot dates (`2026-10-01`, `2026-10-02`, `2026-10-03`, `2026-10-04`, `2026-10-07`) in `data/processed/gps_parquet/` (2.29 GiB clean, 0.73 GiB quarantine) remain intact.
2. All 136 ground-truth historical stop-crossing observations (29 mapped to DLM1 identifiers, 107 preserved under legacy quarantine) remain versioned and untouched.
3. The active primary database (`/tmp/delhi_dlm1.db`, 346.04 MiB) and legacy reference database (`/tmp/delhi_mdb.db`, 268.41 MiB) remain preserved.
4. **No extraction of the remaining 26 days is permitted during this milestone.** This milestone produces exclusively verified specifications, architectural designs, capacity calculations, and execution plans.

Physical measurements demonstrate that **simultaneous local extraction of the uncompressed 31-day dataset is an absolute physical impossibility**, exceeding local disk capacity by **107.23 GiB (13.9x available space)**. Furthermore, even storing the permanent compressed Parquet files for all 31 days locally incurs an immediate deficit of **-7.02 GiB to -11.88 GiB** against current free space. Consequently, this audit issues an unequivocal verdict of **`READY_WITH_STORAGE_CONSTRAINTS`**, mandating external storage provisioning or aggressive host space reclamation before physical extraction can proceed.

---

## 2. Fresh Host Storage Physical Audit

An empirical physical audit of the host APFS container (`/dev/disk3s1s1` mounted at `/`) was conducted using low-level VFS system calls (`statvfs`) and OS block introspection.

### Table 1: Host Volume Physical Storage Inventory

| Parameter | Bytes | Binary (GiB) | Decimal (GB) | Percentage | Notes |
|---|---|---|---|---|---|
| **Total Volume Capacity** | `245,107,195,904` | 228.27 GiB | 245.11 GB | 100.00% | Apple APFS Container |
| **Used Space** | `236,227,846,144` | 220.00 GiB | 236.23 GB | 96.38% | Operating System & Workspace |
| **Free Physical Space** | `8,879,349,760` | 8.27 GiB | 8.88 GB | 3.62% | Physical unallocated APFS blocks |
| **Available Unprivileged Space** | `8,879,349,760` | 8.27 GiB | 8.88 GB | 3.62% | User space available for writes |
| **Critical Safety Floor (OS buffer)** | `1,610,612,736` | 1.50 GiB | 1.61 GB | 0.66% | Minimum required to prevent macOS freeze |
| **Effective Usable Buffer** | `7,268,737,024` | 6.77 GiB | 7.27 GB | 2.96% | $S_{\text{avail}} - S_{\text{floor}}$ |

> [!CAUTION]
> The host operating system volume is operating at **96.38% capacity** with only **8.27 GiB (8.88 GB)** of available space remaining. Writing more than 7.27 GiB without concurrent space reclamation risks immediate kernel `ENOSPC` panics, application crashes, and APFS metadata corruption.

---

## 3. Remote Archive & Local Data Inventory

### 3.1 Remote October 2026 7-Zip Archive Specification
- **Remote Location:** `https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z`
- **Archive Format:** 7-Zip (`7z`), Non-Solid mode (`Solid = -`, `Method = LZMA2:24`)
- **Block Layout:** 31 independent compressed streams (one stream per calendar day)
- **Compressed Archive Size:** `16,077,235,732` bytes (14.97 GiB / 16.08 GB)
- **Uncompressed Total Size (31 days):** `124,016,046,080` bytes (115.50 GiB / 124.02 GB)
- **Uncompressed Pilot Size (5 days):** `16,177,823,744` bytes (15.07 GiB / 16.18 GB)
- **Uncompressed Remaining Size (26 days):** `107,838,222,336` bytes (100.43 GiB / 107.84 GB)

### 3.2 Existing Local Storage Consumption

```
/Users/gauravchauhan/Downloads/delhi_hacks/
├── data/
│   ├── raw/
│   │   └── gps/
│   │       └── bus_movements_2026_10_01.db     [ 3.185 GiB /  3.420 GB ] (Extracted Pilot Day 1)
│   └── processed/                              [ 3.024 GiB /  3.247 GB ]
│       ├── gps_parquet/                        [ 2.294 GiB /  2.464 GB ] (5 Pilot Dates)
│       │   ├── service_date=2026-10-01/        [ 483.98 MiB ]
│       │   ├── service_date=2026-10-02/        [ 472.13 MiB ]
│       │   ├── service_date=2026-10-03/        [ 501.86 MiB ]
│       │   ├── service_date=2026-10-04/        [ 492.51 MiB ]
│       │   └── service_date=2026-10-07/        [ 398.57 MiB ]
│       ├── quarantine/                         [ 0.728 GiB /  0.781 GB ] (Conflicts & OOB)
│       └── stop_crossings/                     [ 0.055 MiB ] (136 Observed Segments)
├── /tmp/
│   ├── delhi_dlm1.db                           [ 346.04 MiB / 362.85 MB ] (Active Primary DB)
│   └── delhi_mdb.db                            [ 268.41 MiB / 281.45 MB ] (Legacy Reference DB)
```

---

## 4. Empirical Compression Ratios & Projection Modeling

Using the completed 5-day pilot dataset as an empirical baseline, compression and yield ratios were calculated to project the storage requirements of the full month.

### Table 2: Empirical Pilot Storage and Compression Yield

| Service Date | Raw SQLite Size (Bytes) | Clean Parquet (Bytes) | Quarantine Parquet (Bytes) | Total Parquet (Bytes) | Clean Ratio | Total Ratio |
|---|---|---|---|---|---|---|
| **2026-10-01** | `3,420,090,368` (3.19 GiB) | `507,495,221` | `166,690,446` | `674,185,667` | 14.84% | 19.71% |
| **2026-10-02** | `3,267,821,568` (3.04 GiB) | `495,068,797` | `152,040,101` | `647,108,898` | 15.15% | 19.80% |
| **2026-10-03** | `3,398,729,728` (3.17 GiB) | `526,241,292` | `166,166,249` | `692,407,541` | 15.48% | 20.37% |
| **2026-10-04** | `3,294,683,136` (3.07 GiB) | `516,432,084` | `158,118,729` | `674,550,813` | 15.67% | 20.47% |
| **2026-10-07** | `2,796,498,944` (2.60 GiB) | `417,934,972` | `138,577,200` | `556,512,172` | 14.95% | 19.90% |
| **Pilot Total**| `16,177,823,744` (15.07 GiB)| `2,463,672,815` (2.29 GiB)| `781,257,322` (0.73 GiB)| `3,244,930,137` (3.02 GiB)| **15.23%** | **20.06%** |

### Mathematical Projection Formulas
1. **Clean Parquet Compression Ratio:**
   $$R_{\text{clean}} = \frac{\sum \text{Size}(\text{Clean Parquet})}{\sum \text{Size}(\text{Raw SQLite})} = \frac{2,463,672,815}{16,177,823,744} \approx 0.152287 \approx \mathbf{15.23\%}$$

2. **Total Parquet (Clean + Quarantine) Ratio:**
   $$R_{\text{total}} = \frac{\sum \text{Size}(\text{Total Parquet})}{\sum \text{Size}(\text{Raw SQLite})} = \frac{3,244,930,137}{16,177,823,744} \approx 0.200579 \approx \mathbf{20.06\%}$$

3. **Remaining 26-Day Projection:**
   $$S_{\text{parquet, clean}}^{26\text{d}} = 107,838,222,336 \times 0.152287 \approx 16,422,360,000\text{ bytes} \approx \mathbf{15.29\text{ GiB}} \ (16.42\text{ GB})$$
   $$S_{\text{parquet, total}}^{26\text{d}} = 107,838,222,336 \times 0.200579 \approx 21,630,100,000\text{ bytes} \approx \mathbf{20.15\text{ GiB}} \ (21.63\text{ GB})$$

4. **Full 31-Day Complete Month Projection:**
   $$S_{\text{parquet, clean}}^{31\text{d}} = 124,016,046,080 \times 0.152287 \approx 18,886,000,000\text{ bytes} \approx \mathbf{17.59\text{ GiB}} \ (18.89\text{ GB})$$
   $$S_{\text{parquet, total}}^{31\text{d}} = 124,016,046,080 \times 0.200579 \approx 24,875,000,000\text{ bytes} \approx \mathbf{23.17\text{ GiB}} \ (24.88\text{ GB})$$

---

## 5. Storage Deficit and Ingestion Feasibility Matrix

A rigorous cross-comparison between available host storage and ingestion demands reveals insurmountable deficits under naive or batch workflows.

### Table 3: Host Storage Deficit Accounting

| Execution Scenario | Space Required | Available Space | Net Deficit | Feasibility Verdict |
|---|---|---|---|:---:|
| **Full 31-Day Uncompressed SQLite** | 115.50 GiB | 8.27 GiB | **-107.23 GiB** | **FATAL DISK EXHAUSTION** |
| **Remaining 26-Day Uncompressed SQLite**| 100.43 GiB | 8.27 GiB | **-92.16 GiB** | **FATAL DISK EXHAUSTION** |
| **Full 31-Day Compressed 7z Archive** | 14.97 GiB | 8.27 GiB | **-6.70 GiB** | **FATAL DISK EXHAUSTION** |
| **Full 31-Day Clean Parquet (Retained)** | 17.59 GiB | 8.27 GiB | **-9.32 GiB** | **EXCEEDS CAPACITY** |
| **Remaining 26-Day Clean Parquet (Only)**| 15.29 GiB | 8.27 GiB | **-7.02 GiB** | **EXCEEDS CAPACITY** |
| **Remaining 26-Day Clean + Quarantine** | 20.15 GiB | 8.27 GiB | **-11.88 GiB** | **EXCEEDS CAPACITY** |
| **Single-Day Peak Workspace (Day 31)** | 6.50 GiB | 8.27 GiB | **+1.77 GiB** | **BORDERLINE / TRANSIENT ONLY** |

### 5.1 The Single-Day Workspace Peak Trap
Even if an operator attempts a strictly pipelined rolling extraction (extract 1 day $\to$ convert to Parquet $\to$ delete SQLite):
- Peak Day 31 SQLite: `4.45 GiB`
- Intermediate DuckDB sort buffers and temporary WAL: `~1.50 GiB`
- Output Parquet (clean + quarantine): `~0.55 GiB`
- **Total transient disk footprint during Day 31 processing: ~6.50 GiB**.
- At Day 1, available space is 8.27 GiB. After processing Day 1, Parquet accumulates (+0.55 GiB). Available space drops to 7.72 GiB.
- By Day 4, accumulated Parquet reaches $4 \times 0.55 = 2.20\text{ GiB}$. Available space drops to $8.27 - 2.20 = 6.07\text{ GiB}$.
- When Day 5 attempts to extract a 4.14 GiB database, the peak requirement (6.50 GiB) exceeds the remaining 6.07 GiB, triggering a terminal OS out-of-disk failure.

---

## 6. Audit Conclusion & Final Verdict

1. **Physical Impossibility of Local Batch Ingestion:** Local disk space is completely insufficient to host the remaining 26 days of raw SQLite (`-92.16 GiB` deficit) or the permanent Parquet output (`-7.02 GiB` clean deficit; `-11.88 GiB` total deficit).
2. **Pipelining Limitation:** A single-day streaming pipeline will fail within 4 days due to local Parquet accumulation on the root disk.
3. **Mandatory Storage Gating:** Full extraction of the remaining 26 days cannot proceed until either:
   - An external high-speed NVMe/SSD drive ($\ge 128\text{ GB}$) is mounted, OR
   - Cloud object storage (Cloudflare R2 / AWS S3) is leveraged for direct remote Parquet output, OR
   - Host disk space is reclaimed by freeing at least $25\text{ GiB}$ of unallocated space.
4. **Governing Verdict:**
   $$\mathbf{Verdict: \ READY\_WITH\_STORAGE\_CONSTRAINTS}$$
   **Current Operating Status:** Strictly maintained at **`DEGRADE`**.

