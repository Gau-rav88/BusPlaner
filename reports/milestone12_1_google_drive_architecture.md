# Milestone 12.1 — Google Drive & Google Colab Cloud Ingestion Architecture

**Governing Specification:** PRD v3.0  
**Audit Timestamp:** 2026-11-22T13:30:00Z  
**Governing Status:** `DEGRADE`  
**Milestone Scope:** Architecture Transition to Google Drive + Google Colab (Planning Only)  
**Evaluated Verdict:** `GOOGLE_CLOUD_READY_WITH_LIMITATIONS`

---

## 1. Executive Summary & Strategic Shift

Following confirmation of the user's **Google Drive enterprise capacity** (5.00 TB total capacity, 23.89 GB used, **4.98 TB available free space**), the project architecture is revised to transition historical data storage and compute entirely to the **Google Cloud ecosystem**:

1. **Permanent Data Lake Storage:** **Google Drive** replaces external NVMe hardware and cloud object storage (Cloudflare R2 / AWS S3) for all raw archives, partitioned Parquet datasets, quarantine files, and validation manifests.
2. **Ephemeral Processing & Ingestion Engine:** **Google Colab (Free-Tier CPU Runtime)** provides ephemeral high-performance compute, high-speed network connectivity to Google Drive, and vectorized processing via **DuckDB** and **PyArrow**.
3. **Local Mac Runtime Isolation:** The active local serving stack (FastAPI on port 8000, DLM1 database `/tmp/delhi_dlm1.db` at 346.04 MiB, legacy reference `/tmp/delhi_mdb.db` at 268.41 MiB, and 136 historical observations) remains **completely untouched and isolated**. Local Mac disk space remains protected at 8.27 GiB.

```mermaid
flowchart TD
    subgraph RemoteSource["Upstream Cloudflare R2 (Static Source Archive)"]
        R2["delhi-dtc-bus-gtfs-rt-2026-10.7z<br/>(14.97 GiB Compressed / 31 Days)<br/>Anonymous Public GET"]
    end

    subgraph GoogleDrive["Google Drive Permanent Data Lake (4.98 TB Available)"]
        GD_Source["Delhi_Bus_Historical_Data/source/<br/>Archive Copy (14.97 GiB)"]
        GD_Manifest["Delhi_Bus_Historical_Data/raw_manifests/<br/>ingestion_manifest.json"]
        GD_Parquet["Delhi_Bus_Historical_Data/parquet/<br/>service_date=YYYY-MM-DD/data.parquet<br/>(~15.29 GiB Clean Parquet)"]
        GD_Quarantine["Delhi_Bus_Historical_Data/quarantine/<br/>service_date=YYYY-MM-DD/<br/>conflicts & out_of_bounds (~4.8 GiB)"]
        GD_Reports["Delhi_Bus_Historical_Data/validation_reports/<br/>service_date=YYYY-MM-DD/summary.json"]
    end

    subgraph ColabVM["Google Colab Ephemeral Container (/content)"]
        Local7z["Staged Archive Copy<br/>/content/source.7z (14.97 GiB)"]
        Extract["Selective Single-Day Extract<br/>bus_movements_YYYY_MM_DD.db<br/>(/content/scratch, 3.2 - 4.5 GiB)"]
        DuckDB["DuckDB Vectorized Engine<br/>RAM Buffer: 3.0 GiB<br/>Deduplication, BBOX & Conflict Filter"]
        ValCheck["10-Point Accounting & Quality Gate<br/>Δ_accounting == 0.0000"]
        Purge["Immediate Local Purge<br/>os.remove(raw_sqlite_path)"]
    end

    subgraph LocalMac["Local Developer Machine (macOS - 8.27 GiB Free)"]
        ServingDB[("/tmp/delhi_dlm1.db<br/>346 MB Primary DLM1")]
        LegacyDB[("/tmp/delhi_mdb.db<br/>268 MB Legacy Ref")]
        PilotObs["136 Pilot Obs Intact<br/>(29 DLM1 / 107 Quarantined)"]
        SummarySync["Sync Aggregated Profiles Only<br/>historical_time_profiles.json (~2 MB)"]
    end

    R2 -->|Fast Cloud Backbone (80 MB/s)| GD_Source
    GD_Source -->|Copy / Stream| Local7z
    Local7z -->|Non-Solid 7z Extract| Extract
    Extract --> DuckDB
    DuckDB --> ValCheck
    ValCheck -->|Promote & Upload| GD_Parquet
    ValCheck -->|Promote & Upload| GD_Quarantine
    ValCheck -->|Update State| GD_Manifest
    ValCheck -->|Write Audit| GD_Reports
    ValCheck -->|Trigger| Purge
    GD_Parquet -.->|Post-Ingestion Aggregation| SummarySync
```

---

## 2. Google Drive Folder Taxonomy & Data Lake Structure

The permanent data lake on Google Drive is rooted at `Delhi_Bus_Historical_Data/` in the user's Drive. It adopts a strict hierarchical taxonomy aligned with Apache Hive/Parquet partitioning and data governance standards:

```
Delhi_Bus_Historical_Data/
├── source/
│   └── delhi-dtc-bus-gtfs-rt-2026-10.7z        [ 14.97 GiB ] (Permanent pristine raw archive)
├── raw_manifests/
│   ├── ingestion_manifest.json                 [ ~50 KiB ]   (Master state machine & partition ledger)
│   └── ingestion_manifest.json.bak             [ ~50 KiB ]   (Atomic write backup)
├── parquet/
│   ├── service_date=2026-10-01/
│   │   └── data.parquet                        [ ~507 MiB ]  (ZSTD compressed clean telemetry)
│   ├── service_date=2026-10-02/
│   │   └── data.parquet                        [ ~495 MiB ]
│   └── ... (31 Daily Hive Partitions)          [ Total ~15.29 GiB Clean Parquet ]
├── quarantine/
│   ├── service_date=2026-10-01/
│   │   ├── conflicts.parquet                   [ ~166 MiB ]  (Temporal coordinate discrepancies)
│   │   └── out_of_bounds.parquet               [ ~80 KiB ]   (Telemetry outside Delhi NCR BBOX)
│   └── ... (31 Daily Quarantine Partitions)    [ Total ~4.86 GiB Quarantined Data ]
├── metadata/
│   ├── dlm1_gtfs_schema.sql                    [ ~12 KiB ]   (Static DLM1 table schemas)
│   ├── legacy_stop_crosswalk.parquet           [ ~439 KiB ]  (Stop mapping matrix)
│   └── route_corridor_definitions.json         [ ~150 KiB ]  (Key monitoring corridors)
└── validation_reports/
    ├── service_date=2026-10-01/
    │   └── validation_summary.json             [ ~5 KiB ]    (10-point accounting audit record)
    └── ... (31 Daily Audit Summaries)
```

### Table 1: Google Drive Data Lake Capacity Allocation

| Directory Layer | Purpose | Format | Estimated Size | % of 5 TB Drive |
|---|---|---|:---:|:---:|
| `source/` | Pristine 7z raw archive | 7-Zip (`LZMA2:24`) | 14.97 GiB | 0.30% |
| `parquet/` | Clean 31-day telemetry partitions | Apache Parquet (`ZSTD`) | 15.29 GiB | 0.31% |
| `quarantine/` | Conflicting & OOB observations | Apache Parquet (`ZSTD`) | 4.86 GiB | 0.10% |
| `raw_manifests/` | State machine & partition checksums | JSON / SHA-256 | 0.01 GiB | < 0.001% |
| `metadata/` | Crosswalks & GTFS schemas | Parquet / JSON | 0.01 GiB | < 0.001% |
| `validation_reports/`| 10-point accounting proof logs | JSON | 0.01 GiB | < 0.001% |
| **Total Footprint** | **Complete Historical Repository** | **Hybrid Lake** | **~35.15 GiB** | **0.71%** |
| **Remaining Free** | **Available for Future Ingestion** | — | **~4,945 GiB** | **99.29%** |

---

## 3. Storage & Compute Separation: The FUSE Mount Constraint

> [!CAUTION]
> **Operating System Invariant:** Never attach a SQLite database or execute iterative DuckDB sort/group-by operations directly over Google Drive's FUSE mount (`/content/drive/MyDrive/...`).

### Why Direct FUSE Processing is Prohibited:
1. **Userspace I/O Latency:** Google Drive FUSE (`google-drive-ocamlfuse` or Google's internal FUSE daemon) introduces a 15–50ms round-trip latency per read/write syscall. SQLite's B-Tree operations require hundreds of thousands of random 4KB page lookups, causing pipeline runtimes to balloon from 2 minutes to over 4 hours per day.
2. **POSIX Lock Failures (`fcntl`/`flock`):** SQLite's write-ahead log (`WAL`) and shared memory (`shm`) mechanisms require robust POSIX file-locking primitives. Google Drive FUSE does not implement true atomic POSIX byte-range locking, frequently resulting in `sqlite3.OperationalError: database is locked` or silent corruption.
3. **Colab Kernel Panics:** High-frequency random I/O over FUSE triggers Colab kernel hangs and uncatchable I/O errors (`EIO: Input/output error`).

### The Scratch Staging Protocol:
To satisfy these constraints, the architecture enforces a strict **Local Staging Buffer** inside the Colab container's high-speed NVMe root filesystem (`/content/scratch/`):
- **Step 1:** The target date's single SQLite file (`bus_movements_YYYY_MM_DD.db`) is extracted from the 7z archive directly into `/content/scratch/`.
- **Step 2:** DuckDB attaches to `/content/scratch/bus_movements_YYYY_MM_DD.db` as a local, bare-metal SQLite database.
- **Step 3:** Deduplication, spatial bounding-box filtering, and conflict identification execute entirely in Colab RAM and local NVMe scratch storage.
- **Step 4:** Validated clean and quarantine datasets are written locally to `/content/scratch/*.parquet`.
- **Step 5:** The 10-point validation suite validates the locally generated Parquet files.
- **Step 6:** Monolithic, finalized Parquet files are copied via high-throughput sequential write to `/content/drive/MyDrive/Delhi_Bus_Historical_Data/...`.
- **Step 7:** The local SQLite file and local Parquet buffers in `/content/scratch/` are **immediately purged** with `os.remove()`.

---

## 4. Preservation of Local Mac Serving Environment

The local Mac development environment is entirely shielded from the ingestion workload:
- **No Large File Downloads to Mac:** Zero raw `.db` or compressed `.7z` files are downloaded to the host Mac.
- **Root Disk Consumption Unchanged:** The host APFS volume (`/dev/disk3s1s1`) remains at **8.27 GiB free space**.
- **Active Serving DB Protected:** `/tmp/delhi_dlm1.db` (346.04 MiB, 6,862 stops, 2,574 routes, 80,357 trips) continues serving the live FastAPI application on `http://127.0.0.1:8000` without downtime or modification.
- **Legacy DB Preserved:** `/tmp/delhi_mdb.db` (268.41 MiB) remains intact for rollback verification on port 8001.
- **Downstream Synchronization:** Once all 31 days are processed and aggregated on Colab, only the lightweight aggregated artifacts (`historical_time_profiles.json`, ~2.1 MiB; and updated stop-crossing medians, ~450 KiB) will be synchronized to the Mac, consuming less than 3 MiB of local disk space.

---

## 5. Architectural Verdict

$$\mathbf{Verdict: \ GOOGLE\_CLOUD\_READY\_WITH\_LIMITATIONS}$$

The Google Drive + Google Colab architecture resolves all local storage barriers while incurring zero infrastructure costs. However, operational execution must be governed by the Colab free-tier runtime constraints, FUSE staging boundaries, and stateful manifest recovery protocols detailed in the accompanying reports.

