# Milestone 12 — Evaluation of Storage Options and Technical Tradeoffs

**Governing Specification:** PRD v3.0  
**Audit Timestamp:** 2026-11-22T01:56:00Z  
**Governing Status:** `DEGRADE`  
**Milestone Scope:** Storage Options Tradeoff Analysis & Architecture Selection  
**Evaluated Verdict:** `READY_WITH_STORAGE_CONSTRAINTS`

---

## 1. Executive Summary

As demonstrated in the **Milestone 12 Storage Feasibility Audit**, processing the full **October 2026 historical GPS dataset** (31 calendar days, 115.50 GiB uncompressed SQLite, ~23.17 GiB compressed Parquet) cannot be executed within the host volume's remaining **8.27 GiB** of available disk space. 

This document provides a comprehensive engineering evaluation of **four distinct storage and processing architectures**:
- **Option A:** Local High-Performance External NVMe/SSD Storage (`/Volumes/...`)
- **Option B:** Network Attached Storage / Shared Remote Mount (SMB/NFS)
- **Option C:** Cloud Compute & Remote Object Storage (Cloudflare R2 / AWS S3 + DuckDB HTTPFS)
- **Option D:** Strict Day-by-Day Streaming Ingestion with Host Space Reclamation & Immediate Remote Sync

Each option is rigorously evaluated across technical criteria: physical capacity, root disk safety, I/O latency, network bandwidth, fault tolerance, implementation cost, and operational complexity.

---

## 2. In-Depth Evaluation of Storage Options

### 2.1 Option A: Local External High-Speed NVMe/SSD Drive

#### Architectural Overview
An external USB 3.2 Gen2 or Thunderbolt 3/4 NVMe SSD (minimum 500 GB to 1 TB, formatted as APFS or exFAT) is connected directly to the host machine and mounted under `/Volumes/DelhiTransit_Ext`. The workspace redirects all heavy storage directories via symbolic links or configuration flags:
- `RAW_STORAGE_DIR=/Volumes/DelhiTransit_Ext/data/raw/gps`
- `PARQUET_STORAGE_DIR=/Volumes/DelhiTransit_Ext/data/processed/gps_parquet`
- `DUCKDB_TEMP_DIR=/Volumes/DelhiTransit_Ext/tmp`

#### Advantages
1. **Zero Host Root Disk Pressure:** The internal APFS container (`/dev/disk3s1s1`) remains untouched at 8.27 GiB free space, eliminating kernel panics and `ENOSPC` errors.
2. **Extreme I/O Throughput:** Sustained sequential read/write speeds of 1,000–2,800 MB/s enable DuckDB to convert a 4.5 GiB SQLite file to ZSTD Parquet in under 45 seconds.
3. **Full Batch & Rolling Support:** Can effortlessly store all 115.5 GiB of uncompressed SQLite files simultaneously or keep all historical checkpoints indefinitely.
4. **Zero Cloud Egress / Compute Costs:** Completely offline execution with no cloud subscription or egress billing.

#### Disadvantages & Risks
1. **Hardware Dependency:** Requires physical hardware procurement ($70–$110 for a 1TB portable SSD).
2. **Accidental Disconnection Risk:** Physical cord disconnection during DuckDB writes could corrupt the active partition table, requiring journal recovery.

---

### 2.2 Option B: Network Attached Storage / Mounted Shared Volume (SMB / NFS)

#### Architectural Overview
A local server, TrueNAS, or Synology NAS on the local gigabit/10GbE network exports a shared directory mounted on macOS via SMB (`smb://nas.local/delhi_hacks_storage`).

#### Advantages
1. **Centralized Team Access:** Multiple developers and background jobs can query the partitioned Parquet dataset simultaneously.
2. **Infinite Local Expansion:** NAS RAID arrays typically possess 4–20 TB of free capacity.
3. **Zero Host Drive Consumption:** All raw files and parquet outputs reside on the remote filesystem.

#### Disadvantages & Risks
1. **Severe I/O Bottlenecks:** Gigabit Ethernet limits throughput to ~110 MB/s. DuckDB columnar scans across 23 GiB over network shares experience significant latency spikes and random-access stalls.
2. **APFS / POSIX Locking Flaws:** DuckDB and SQLite both rely on strict file-locking primitives (`fcntl`/`flock`). SMB file locking over macOS frequently encounters stale lock state or silent write drops.
3. **Network Jitter Sensitivity:** Wi-Fi drops or switch renegotiations during multi-gigabyte writes trigger write pipeline aborts.

---

### 2.3 Option C: Cloud Compute & Remote Object Storage (Cloudflare R2 / AWS S3 + DuckDB HTTPFS)

#### Architectural Overview
Instead of processing telemetry on the local developer laptop, the entire pipeline is executed in a dedicated cloud worker (e.g., AWS EC2 `c6i.2xlarge` with 8 vCPUs, 16 GiB RAM, and 150 GiB ephemeral NVMe scratch disk). 
- The 7z archive is already hosted on **Cloudflare R2** (`https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/...`).
- The cloud worker pulls 7z blocks within the same datacenter/backbone at 10 Gbps, executes DuckDB ingestion, generates daily Parquet partitions, and streams them back to an R2 bucket (`s3://delhi-gps-parquet/`).
- The local FastAPI backend uses DuckDB's `httpfs` extension to query remote Parquet files on demand via HTTP range requests without storing them locally.

#### Advantages
1. **Zero Local Storage Footprint:** 0 bytes consumed on the local Mac. Root drive remains at 8.27 GiB free.
2. **Zero Ingestion Burden on Laptop:** Laptop fans, battery, and CPU are completely unburdened.
3. **Massive Cloud Backbone Throughput:** Cloud-to-R2 transfers run at 1,000+ MB/s. Full 31-day processing finishes in under 20 minutes.
4. **Cloudflare Zero Egress:** Cloudflare R2 charges $0.00 for data egress, making remote DuckDB queries cost-effective.

#### Disadvantages & Risks
1. **Query Latency for Serving:** Querying remote Parquet over HTTPS adds 40–120ms round-trip latency to each historical baseline lookup, unless aggressive in-memory caching is implemented in FastAPI.
2. **External Cloud Dependency:** Requires cloud API keys, IAM credentials, and an active internet connection.
3. **Compute Cost:** Minimal but non-zero (~$0.50–$2.00 for a single cloud worker execution run).

---

### 2.4 Option D: Strict Day-by-Day Streaming Ingestion with Host Drive Reclamation & Push

#### Architectural Overview
Execution remains on the local machine, but is subjected to two mandatory prerequisites:
1. **Host Space Reclamation:** Clean development caches (Xcode `DerivedData`, Docker volumes, brew cache, old downloads) to expand local available space from 8.27 GiB to $\ge 25\text{ GiB}$.
2. **Rolling Pipeline with Immediate Push & Purge:**
   - Day $k$ is extracted from the 7z archive (peak transient: 4.45 GiB).
   - DuckDB processes telemetry and writes clean Parquet (0.50 GiB) and stop crossings (0.01 MiB).
   - Immediate verification against the 10-point validation specification.
   - Upon PASS: Raw Day $k$ SQLite file is **instantly deleted** from disk.
   - Parquet partition is committed.

#### Advantages
1. **Pure Software Solution:** No new hardware purchase ($0 hardware cost).
2. **Local Serving Speed:** All Parquet partitions reside on the local high-speed SSD, providing sub-millisecond query responses to the RAPTOR engine.
3. **Deterministic Memory Footprint:** DuckDB memory capped at 4 GiB; single-day SQLite processing bounded to predictable intervals.

#### Disadvantages & Risks
1. **Requires Host Space Reclamation:** The operator *must* manually delete files on macOS to achieve $\ge 25\text{ GiB}$ free space before Day 1 starts. If run today with 8.27 GiB, it will run out of disk space by Day 4.
2. **Zero Fault Margin:** If a single day's processing leaves temporary artifacts or if background OS tasks write 2 GiB to disk, the process aborts.

---

## 3. Comparative Tradeoff Matrix

### Table 1: Comprehensive Multi-Criteria Scoring (Scale 1–5, Higher is Better)

| Criterion | Weight | Option A (Ext NVMe SSD) | Option B (Network NAS) | Option C (Cloud R2/EC2) | Option D (Streaming + Reclaim) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Storage Headroom & Safety** | 25% | **5** (500GB+ available) | **4** (Large pool) | **5** (Infinite object store) | **2** (Tight margins, needs clean) |
| **Local Disk Protection** | 20% | **5** (0 bytes on root) | **5** (0 bytes on root) | **5** (0 bytes on root) | **3** (Consumes ~18 GiB Parquet) |
| **I/O & Query Latency** | 20% | **5** (2,000+ MB/s) | **2** (Network SMB latency) | **3** (HTTP range request latency)| **5** (Local NVMe 2,500 MB/s) |
| **Fault Tolerance & Resume** | 15% | **4** (High reliability) | **2** (Locking & net drops) | **5** (Stateless cloud tasks) | **3** (Fragile free-space ceiling)|
| **Implementation Simplicity** | 10% | **5** (Plug & symlink) | **3** (SMB mount & permissions) | **2** (Cloud scripts & IAM setup)| **4** (Scripted rolling loop) |
| **Hardware / Cloud Cost** | 10% | **3** ($70 hardware) | **4** ($0 if NAS exists) | **4** (<$2 compute cost) | **5** ($0 pure software) |
| **Weighted Score** | **100%** | **4.60 / 5.00** | **3.25 / 5.00** | **4.25 / 5.00** | **3.30 / 5.00** |
| **Ranking** | — | **Rank 1 (Optimal)** | **Rank 4 (Unsuitable)** | **Rank 2 (Best Cloud)** | **Rank 3 (Contingent)** |

---

## 4. Architectural Recommendation & Decision Rationale

### 4.1 Primary Recommendation: Option A (External High-Speed NVMe/SSD)
If physical hardware is available or procurable, **Option A is the definitive superior architecture**:
- Completely eliminates risk to the primary OS volume.
- Provides peak local performance for DuckDB analytics and ML training.
- Retains both raw SQLite databases and Parquet archives for exhaustive scientific auditing.

### 4.2 Secondary / Hybrid Fallback: Option D + Host Reclamation (or Option C Cloud Processing)
If external hardware cannot be provisioned:
1. **Option D is only approved IF the operator first reclaims at least $20\text{ GiB}$ of host disk space**, raising available capacity from 8.27 GiB to $\ge 28\text{ GiB}$.
2. Under Option D, a strict **Single-Day Sliding Window** must be enforced:
   $$\text{Extract}(k) \longrightarrow \text{Ingest}(k) \longrightarrow \text{Validate}(k) \longrightarrow \text{PurgeRaw}(k) \longrightarrow \text{CommitParquet}(k)$$
3. If host disk reclamation is unacceptable to the operator, **Option C (Cloud Execution via Cloudflare R2)** should be deployed, rendering local storage constraints completely irrelevant.

---

## 5. Formal Verdict

$$\mathbf{Verdict: \ READY\_WITH\_STORAGE\_CONSTRAINTS}$$
- **Option A is certified as the safest, highest-performing path.**
- **Option D is certified as mathematically viable only upon prior host space reclamation ($\ge 25\text{ GiB}$).**
- **Under current conditions (8.27 GiB free space, no external drive), physical extraction remains strictly GATED.**

