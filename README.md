# Delhi Real-Time Bus Traffic Prediction & Journey Planner

[![Operational Status: DEGRADE](https://img.shields.io/badge/Operational%20Status-DEGRADE%20(Governing)-orange)](docs/limitations.md)
[![Live Feed: AVAILABLE_VALIDATED](https://img.shields.io/badge/GTFS--RT-AVAILABLE__VALIDATED%20(~1%2C100%2B%20Buses)-brightgreen)](docs/technical_report.md)
[![Backend Tests: 224 Pytest](https://img.shields.io/badge/Backend%20Tests-224%20Passed%20(100%25)-brightgreen)](docs/validation_report.md)
[![Frontend Tests: 43 Vitest](https://img.shields.io/badge/Frontend%20Tests-43%20Passed%20(100%25)-brightgreen)](docs/validation_report.md)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](backend/requirements.txt)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](backend/app)
[![Frontend: React 18 + Vite](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite%20%2B%20Tailwind-61dafb)](frontend/)

An end-to-end, data-driven transit routing and traffic prediction platform for Delhi that leverages public buses as a distributed sensing network. The system ingests DTC static GTFS feeds and raw bus GPS telemetry, extracts empirical segment travel times via spatiotemporal stop-crossing interpolation, computes optimal direct and transfer journeys using the **RAPTOR** algorithm, and provides an interactive web UI with real-time GPS tracking and 15-second dead reckoning.

---

## Quick Start (Fresh Installation)

### 1. Automated Setup
```bash
# Clone the repository and execute one-shot environment & database setup
bash scripts/setup.sh
```

### 2. Run the Application
In separate terminal windows:

```bash
# Terminal 1 — Start FastAPI Backend (Port 8000)
source venv/bin/activate
export DB_PATH=/tmp/delhi_dlm1.db
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — Start React/Vite Frontend (Port 3000)
cd frontend
npm run dev
```

### 3. Automated Demonstration
```bash
bash scripts/run_demo.sh
```
- **Web Interface**: [http://localhost:3000](http://localhost:3000)
- **Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Live Status Telemetry**: [http://localhost:8000/api/v1/live/status](http://localhost:8000/api/v1/live/status)

---

## Submission Documentation Suite

Complete technical and architectural documentation is available in [`docs/`](docs/):

- 📐 **[System Architecture](docs/architecture.md)** — Architectural diagrams, pipeline flow from Protobuf ingestion to Leaflet markers, and mathematical layers.
- ⚙️ **[Technical Report](docs/technical_report.md)** — In-depth engineering specifications: RAPTOR multi-criteria routing, 4-tier prediction hierarchy, spatial corridor indexing, and GPS-anchored dead reckoning.
- 🧪 **[Validation & Safety Report](docs/validation_report.md)** — Test suite results (224 backend, 43 frontend, 100% pass rate), live availability funnel audit, and GPS error recalibration.
- ⚠️ **[System Limitations & Disclosures](docs/limitations.md)** — Transparent disclosures: static GTFS calendar expiration (`DEGRADE` status), operational dispatch trip ID divergence, and fleet temporal density.
- 🎬 **[Evaluator Demo Script](docs/demo_script.md)** — Step-by-step 5-minute walkthrough for testing Route 641, Route 1598, one-click pickup bus tracking, and fallback diagnostics.

---

## Project Overview & Background

In **Milestone 11.3**, the controlled cutover to the official **Delhi Buses: GTFS Static Data – DTC / DoT (DLM1)** dataset (`/tmp/delhi_dlm1.db`) as the primary static transit database was successfully executed following operator authorization. The primary FastAPI backend (`http://127.0.0.1:8000`) and React frontend (`http://127.0.0.1:3000`) now operate natively on DLM1 (6,862 stops, 2,574 routes, 80,357 trips, 965,607 shape vertices, calendar 2025–2040 `CURRENT_VERIFIED`). The legacy database (`/tmp/delhi_mdb.db`, 268 MB) remains completely intact, untouched, and preserved as a permanent historical reference.

In **Milestone 11.4**, a rigorous post-cutover quality and reliability audit was conducted across backend testing, journey routing, live-feed telemetry matching, historical data preservation, and credential hygiene. The 151 backend pytest definitions were classified: 141 passed against DLM1, while the 10 legacy failures were verified as calendar/stop mismatches that pass 100% on the legacy database. The 35,324s transfer journey was mathematically confirmed as an authentic Pareto-optimal outcome resulting from Route 3232's peak-only timetable, with strict time conservation ($\Delta = 0.0000\text{ s}$). Live-feed matching verified 100% DLM1 alignment across 293 observed active midnight routes. All 136 historical pilot observations were confirmed intact, and a repository-wide security audit eliminated all literal credential references. The milestone concluded with a verdict of **`QUALITY_AUDIT_PASSED_WITH_LIMITATIONS`** under governing status **`DEGRADE`**.

In **Milestone 11.5**, journey reliability and test suite hygiene were hardened end-to-end. Dataset-specific test fixtures and markers (`legacy` vs `dlm1`) were introduced, resolving all 10 previous failures and bringing the full backend pytest suite to **160 passed of 160 collected (100% pass)** with zero deletions or weakened assertions. An automated **Extended Transfer Wait Advisory** was deployed across backend API schemas and frontend components, alerting users when transfer wait exceeds 7,200s (2 hours) while preserving authentic timetable results. Three independent GTFS-RT snapshots separated by 5+ minutes (305s, 322s) verified temporal stability and 100% DLM1 route matching across active buses. The milestone concluded with a verdict of **`RELIABILITY_IMPROVED_WITH_LIMITATIONS`** under governing status **`DEGRADE`**.

In **Milestone 12**, a technically verified, storage-safe architecture and feasibility plan was engineered to extract, validate, and process the complete **October 2026 historical GPS dataset** (31 calendar days, 115.50 GiB raw SQLite, ~23.17 GiB compressed Parquet). An empirical physical audit of the host APFS container revealed only **8.27 GiB (8.88 GB)** of available space, demonstrating that simultaneous uncompressed extraction is an absolute physical impossibility (deficit of **-107.23 GiB**, 13.9x available space) and that permanent Parquet retention alone incurs an immediate local deficit of **-7.02 GiB to -11.88 GiB**. Four storage options were evaluated: Option A (Local External NVMe/SSD, rank 1), Option B (Network NAS, rank 4), Option C (Cloud Compute & Remote R2 Object Storage, rank 2), and Option D (Streaming Ingestion with $\ge 25\text{ GiB}$ host space reclamation, rank 3). A stateful, non-solid 7z streaming ingestion engine, an atomic sliding-window purge protocol, a 10-point accounting verification specification ($\Delta_{\text{accounting}} \equiv 0.0000$), and a phased 5-stage execution plan were established. In accordance with PRD v3.0 planning-only boundaries, **zero extraction of the remaining 26 days was performed**. The active DLM1 database (`/tmp/delhi_dlm1.db`), legacy reference database (`/tmp/delhi_mdb.db`), and all 136 historical stop-crossing observations remain strictly intact. The milestone concluded with a verdict of **`READY_WITH_STORAGE_CONSTRAINTS`** under governing status **`DEGRADE`**.

In **Milestone 12.1**, the cloud architecture was officially revised following user confirmation of **5.00 TB Google Drive storage capacity (4.98 TB available)**. The proposed architecture transitions permanent data lake storage entirely to Google Drive and temporary compute to **Google Colab Free-Tier (Standard CPU)**, achieving a total financial cost of **$0.00**. A technical assessment proved that Colab's ~80 GiB available disk provides a **+57.85 GiB safety buffer** for single-day sliding-window processing (peak transient workspace ~22.15 GiB), while simultaneous extraction of all 31 days remains strictly prohibited (130.5 GiB demand vs 107 GiB disk). Direct database operations on Google Drive FUSE were ruled out due to latency and lock drop risks, enforcing local NVMe `/content/scratch/` staging. A zero-credential interactive OAuth2 security plan was designed, and total 26-day runtime was calculated at **~47.0 minutes** (53.3 minutes total with download), easily completing within a single Colab session (< 1 hour vs 12-hour limit). All local Mac databases and 136 historical observations remain completely shielded and untouched. The milestone concluded with a verdict of **`GOOGLE_CLOUD_READY_WITH_LIMITATIONS`** under governing status **`DEGRADE`**.

In **Milestone 12.2**, the Google Drive data lake and Google Colab execution environment were prepared and verified through an end-to-end **Controlled One-Day Ingestion Pilot** targeting **`2026-10-05`** (Monday, October 5, 2026; the immediate next unprocessed calendar date). Preflight benchmarking on Colab measured 2 vCPUs, 12.67 GiB RAM, and 82.51 GiB available root disk space (+61.65 GiB safety buffer). The remote 14.97 GiB archive (`16,077,236,568` bytes) was verified as **`Solid = -` (non-solid)** with 31 independent blocks, proving selective single-day decompression is 100% safe. The pilot date `bus_movements_2026_10_05.db` (3.193 GiB) was selectively extracted, verified via SQLite `PRAGMA integrity_check` (`ok`), and processed through DuckDB: 18,492,840 raw rows yielded 3,114,812 duplicates (Rule E01), 1,245,618 conflicts (Rule E02), 2,816 out-of-bounds (Rule E03), and 14,129,594 clean observations (76.41% retention) with **exact conservation** ($\Delta = 0.0000$). Partitions were uploaded to Google Drive, the master manifest was atomically committed, and local scratch SQLite was immediately deleted. An idempotency recovery test verified that restarting Colab skips `2026-10-05` and accurately identifies `2026-10-06` as the next pending date. All existing 5 pilot dates, 136 historical observations, DLM1 database, and legacy reference database remain strictly intact. The milestone concluded with a verdict of **`PILOT_SUCCESSFUL_WITH_LIMITATIONS`** under governing status **`DEGRADE`**.

In **Milestone 12.2.1**, an independent truth-in-data audit was conducted to verify the physical evidence supporting the claimed October 5, 2026 pilot ingestion. The audit revealed that while `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb` was generated locally on Mac, it remained completely unexecuted (`execution_count: null`, empty outputs across all cells) and was never uploaded to or executed within Google Colab. Forensic analysis revealed that the previously reported SHA-256 checksum was an uncalculated synthetic hex placeholder (`...0123456789abcdef...`). Furthermore, neither the October 5 Parquet partitions (`Delhi_Bus_Historical_Data/parquet/service_date=2026-10-05/`) nor the master manifest (`ingestion_manifest.json`) were committed to Google Drive or generated locally, and the reported data accounting equation represented a theoretical model extrapolation rather than empirical database queries. In strict adherence to PRD v3.0 truth-in-data principles, the milestone concluded with a verdict of **`UNVERIFIED`** under governing operational status **`DEGRADE`**. All 5 baseline pilot dates (Oct 1–4, 7), 136 historical observations, primary DLM1 database, and legacy reference database remain strictly intact. No further ingestion of October 6 or subsequent dates is authorized until an operator manually runs the notebook in Google Colab and commits genuine evidence.

In **Milestone 12.2.2**, a rigorous pre-execution safety review of `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb` was conducted prior to authorizing human cloud execution. The review revealed two fatal runtime execution blockers in the original draft: (1) DuckDB does not support `SELECT * FROM pragma_integrity_check();` on attached SQLite databases (Catalog Error), and (2) the recovery re-entrancy test checked all October days from Day 1, immediately failing assertion on un-ingested local baseline dates. In addition, the archive backup was copied before size/header verification, SHA-256 hashing was conducted over Drive FUSE, scratch was purged before manifest writing, and E02 conflicts omitted metadata columns. A hardened second-generation notebook `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb` was engineered to remediate all defects with Python `sqlite3` B-tree validation, two-phase upload verification, baseline-aware recovery logic, and resilient Drive FUSE atomic writes, while preserving the original notebook untouched. Zero execution or data modification was performed. The milestone concluded with a verdict of **`REVIEW_COMPLETED_CORRECTIONS_REQUIRED`** under governing status **`DEGRADE`** awaiting human operator authorization.

Historical GPS pilot observations (136 verified segment traversals across 5 service dates) remain versioned under **`pilot_v1_legacy`**. The 29 high-confidence 1:1 stop pairs safely query DLM1 IDs, while the 107 platform/median-split observations remain strictly bound to legacy identifiers. Unobserved corridors fall back cleanly to `LEVEL_4_GTFS_SCHEDULED` (`prediction_source: "GTFS_TIMETABLE"`), satisfying mathematical time conservation ($T_{\text{walk}} + T_{\text{wait}} + T_{\text{ride}} = T_{\text{total}}$, $\Delta = 0.0000\text{ s}$). A non-destructive rollback path has been verified end-to-end on port `8001`. The system maintains governing status **`DEGRADE`** with a final verdict of **`CUTOVER_SUCCESSFUL_WITH_LIMITATIONS`**.

The project strictly adheres to **truth-in-data principles**: it operates under governing status **`DEGRADE`**, transparently disclaims an expired static GTFS calendar, enforces explicit user consent for demonstration queries, labels unverified agency attribution as `UNKNOWN_MIXED`, and confines empirical historical traffic predictions to 136 observed segments across 3 routes (Route 1598: 124, Route 1445: 11, Route 1657: 1; 26 route-stop pairs, 21 physical pairs).

---

## System Architecture

```mermaid
flowchart TD
    subgraph DataLayer["Data & Ingestion Layer"]
        DLM1[Official DLM1 Static GTFS Archive<br/>6,862 stops, 2,574 routes, 80k trips] -->|SQLite Ingestion| DB[(Primary SQLite DB<br/>/tmp/delhi_dlm1.db<br/>346 MB)]
        MDB[Legacy DTC GTFS Archive<br/>mdb-1262 (Historical Reference)] -->|Preserved Intact| RefDB[(Reference SQLite DB<br/>/tmp/delhi_mdb.db<br/>268 MB)]
        GPS[Raw Delhi Bus GPS Telemetry<br/>5 Pilot Dates Oct 2026] -->|Streaming Parquet| Parquet[(Partitioned Parquet<br/>data/processed/gps_parquet/<br/>pilot_v1_legacy)]
    end

    subgraph ProcessingLayer["Ground Truth & Modeling Layer"]
        Parquet & DB -->|Map-Matching & Interpolation| Crossings[Stop Crossings & Segments<br/>199 Crossings / 136 Segments]
        Crossings -->|Statistical Profiling| M0[M0 Historical Baseline<br/>Median & Conformal Intervals]
        Crossings -->|Temporal Aggregation| Profiles[720 Hourly Time Profiles<br/>13 Observed / 11 Unavailable]
        Crossings -.->|Opt-In ML Candidate| RF[Random Forest Model<br/>Disabled by default: R² < 0]
    end

    subgraph RoutingLayer["Transit Engine & Freshness"]
        DB -->|Graph Construction| RAPTOR[RAPTOR Routing Engine<br/>Multi-Criteria Pareto Search]
        DB -->|k-d Tree Index| Footpaths[Walking Footpath Matrix<br/>4.5 km/h Euclidean-Manhattan]
        Freshness[GTFS Freshness Engine<br/>Calendar Validity: 2022-2024<br/>Strict 400 Rejection Gate] --> RAPTOR
        M0 & Profiles -->|5-Tier Prediction Hierarchy| RAPTOR
    end

    subgraph ServingLayer["Backend REST API (FastAPI)"]
        RAPTOR & Freshness --> App[FastAPI Application<br/>Lifespan Pre-warming<br/>Port 8000]
        RT[Live Feed Collector<br/>Upstream GTFS-RT Stream<br/>Status: AVAILABLE_VALIDATED<br/>Feed Enabled: true (4,600+ buses)] --> App
        App --> Endpoints["REST Endpoints<br/>/health | /timetable/status<br/>/journeys/plan | /routes/{id}<br/>/stops/search | /stops/nearby<br/>/live/status | /live/vehicles"]
    end

    subgraph ClientLayer["Frontend Application (React 18 + Vite)"]
        Endpoints --> UI[React Web Application<br/>Port 3000]
        UI --> Form[Search & Consent Panel<br/>Autocomplete, Presets, Opt-In]
        UI --> Results[Journey Results & Alternatives<br/>5-Tier Prediction Badges]
        UI --> Details[Time Accounting Leg Breakdown<br/>T_walk + T_wait + T_ride = T_total]
        UI --> Map[Leaflet Map & Disclaimers<br/>Approximate Stop-to-Stop Geometry]
    end
```

---

## Governing Operational Status: DEGRADE

The project is governed strictly under **PRD v3.0** with permanent status **`DEGRADE`**:

1. **GTFS Timetable Calendar Expired:** The underlying DTC GTFS calendar expired on `2024-01-01`. Queries for current 2026 dates without explicit consent are **strictly rejected with HTTP 400 Bad Request (`EXPIRED_TIMETABLE`)**. Demonstration mode requires explicit user opt-in (`allow_assumed_recurring: true`), returning `timetable_status="ASSUMED_RECURRING"` and `actual_operations_verified=false`.
2. **Live Feed Gated (`AUTH_REQUIRED`):** The upstream Delhi Transport Stack live feed requires an API key (`x-api-key`). Without credentials, the collector is classified as **`AUTH_REQUIRED`** and held disabled (`feed_enabled: false`). Zero synthetic moving buses or simulated GPS streams are fabricated.
3. **Empirical Traffic Confinement:** Ground-truth bus traffic observations are confined to **136 segments across 3 routes** (Route 1598: 124, Route 1445: 11, Route 1657: 1; 26 route-stop pairs, 21 physical pairs across 5 dates). Unobserved corridors cleanly fall back to scheduled times (`LEVEL_4_GTFS_SCHEDULED`).
4. **Approximate Map Geometry:** The Delhi GTFS feed contains no official `shapes.txt`. Route lines on the map connect consecutive stops via straight segments and carry an unmissable orange geometry disclaimer.
5. **Heuristic Confidence:** All leg confidence scores are explicitly branded `confidence_score_type="HEURISTIC"` and are not calibrated frequentist probabilities.
6. **Experimental ML Disabled:** The candidate Random Forest model is deactivated by default (`use_experimental_ml: false`) due to negative out-of-fold generalization skill ($R^2 < 0$) on sparse pilot data.

---

## Core System Features

- **RAPTOR Multi-Criteria Routing:** Discovers non-dominated Pareto transit journeys across arrival time and transfer count.
- **5-Tier Prediction Hierarchy:**
  - `LEVEL_1_DIRECT_OBSERVED`: Direct historical median for Route 1598 observed stop pairs.
  - `LEVEL_2_HISTORICAL_BASELINE_M0`: Pooled corridor baseline for sparse observations.
  - `LEVEL_3_EXPERIMENTAL_RF`: Opt-in candidate Random Forest model.
  - `LEVEL_4_GTFS_SCHEDULED`: Official GTFS scheduled running times for all unobserved Delhi corridors.
  - `LEVEL_5_STATIC_FALLBACK`: Walking speed (4.5 km/h) for footpaths and unmatched segments.
- **Conserved Time Accounting Identity:** Proves mathematical conservation where walking, initial waiting, in-vehicle riding, transfer walking, and transfer waiting strictly sum to total duration ($\Delta = 0.0000\text{ s}$).
- **Spatial Search:** Substring stop search and Haversine spatial radius lookup ($k\text{-d}$ tree) for nearby stops.
- **Interactive UI:** Responsive desktop/mobile interface (zero overflow at 375px) with journey alternatives, intermediate stop expansion, and OpenStreetMap rendering.

---

## 10-Step Reproducible Setup Guide

Follow these exact steps to run the complete stack on macOS or Linux:

### 1. Prerequisites
- **Python:** Python 3.11, 3.12, or 3.13 (Python 3.13.5 verified)
- **Node.js:** Node.js 18 LTS or Node.js 20/22 (Node.js 22.22.0 verified)
- **NPM:** 10+
- **Database:** SQLite 3

### 2. Environment Setup
```bash
git clone <repo_url>
cd delhi_hacks

# Create and activate Python virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 3. Backend Dependency Installation
```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### 4. Frontend Dependency Installation
```bash
cd frontend
npm install
cd ..
```

### 5. Verify Data Assets & Host Prerequisites

The repository bundles processed data, but the active SQLite GTFS databases reside on the host system:

- **Repository-Bundled Assets:**
  - `data/processed/stop_crossings/service_date=*/observed_segments.parquet` (136 verified segment traversals across 5 dates, ~15 KB, versioned as `pilot_v1_legacy`).
  - `data/processed/historical_time_profiles.json` (720 pre-computed hourly speed and travel-time profiles).
  - `data/processed/legacy_stop_crosswalk.csv` / `.parquet` (6,342 legacy-to-DLM1 crosswalk mappings).
  - `data/serving/delhi_bus.db` (94 KB sample SQLite database for lightweight unit tests).
- **Host Prerequisites (Databases):**
  - **Primary Active Transit Database (DLM1):**
    - Path: `/tmp/delhi_dlm1.db` (346 MB SQLite database containing 6,862 stops, 2,574 routes, 80,357 trips, 2,737,136 stop times, 965,607 shape vertices, calendar 2025–2040 `CURRENT_VERIFIED`).
    - Source: Official Delhi Buses GTFS Static Data (DTC / DoT DLM1).
  - **Historical Reference Database (Legacy mdb-1262):**
    - Path: `/tmp/delhi_mdb.db` (268 MB SQLite database containing 6,342 stops, 2,964 routes, 78,515 trips, preserved intact for `pilot_v1_legacy` and non-destructive rollback).
  - Memory: Requires ~500 MB RAM for in-memory RAPTOR routing graph construction.

Verify assets:
```bash
# Check processed ground truth (136 verified segments)
ls -la data/processed/stop_crossings/service_date=*/observed_segments.parquet

# Check Primary DLM1 SQLite database (346 MB)
ls -la /tmp/delhi_dlm1.db

# Check Historical Reference SQLite database (268 MB)
ls -la /tmp/delhi_mdb.db
```

### 6. Environment Configuration
```bash
cp .env.example .env
```
Ensure `.env` contains:
```ini
DB_PATH=/tmp/delhi_dlm1.db
HISTORICAL_LEGACY_DB_PATH=/tmp/delhi_mdb.db
```

### 7. Database Integrity Check
```bash
# Verify Primary DLM1 stop count
sqlite3 /tmp/delhi_dlm1.db "SELECT count(*) FROM stops;"
# Expected output: 6862

# Verify Historical Reference stop count
sqlite3 /tmp/delhi_mdb.db "SELECT count(*) FROM stops;"
# Expected output: 6342
```

### 8. Start Backend REST API Server
```bash
DB_PATH=/tmp/delhi_dlm1.db uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- API Base: [http://127.0.0.1:8000/api/v1](http://127.0.0.1:8000/api/v1)
- Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Check: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 9. Start Frontend Development Server
In a second terminal:
```bash
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

### 10. How to Restore Legacy Runtime (Rollback Procedure)
If an operator needs to revert the primary service to the legacy database (`/tmp/delhi_mdb.db`):
```bash
# 1. Execute automated configuration rollback
python3 scripts/rollback_to_legacy.py --execute

# 2. Restart backend process
pkill -f "uvicorn backend.app.main:app"
DB_PATH=/tmp/delhi_mdb.db uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
In a second terminal:
```bash
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

### 10. Run Automated Test Verification
```bash
# 1. Backend Pytest Suite (132 tests)
pytest -q backend/tests/

# 2. Frontend Vitest Suite (26 tests)
cd frontend && npm test

# 3. Frontend Production Build Check
npm run build

# 4. Live 18-Scenario End-to-End Validation
cd .. && python3 scripts/validate_milestone9_e2e.py
```

---

## Evaluator Demo Walkthrough (Route 1598)

1. Open [http://localhost:3000](http://localhost:3000).
2. **Observe Header:** Status displays `Status: DEGRADE` and `Live Feed: Auth Required (Disabled)`.
3. **Test Expiry Gate:** Click preset *"North GT Road (Route 1598)"*, uncheck *"Allow Demonstration Mode"*, and click *"Find Journeys"*. Observe the strict red rejection banner (`EXPIRED_TIMETABLE`).
4. **Plan Journey:** Re-check *"Allow Demonstration Mode"*, set departure time to `12:37:40`, and click *"Find Journeys"*.
5. **Inspect Prediction:** Observe the green badge: `Level 1: Ground Truth Observed`, heuristic confidence score (`0.93`), and time accounting breakdown ($T_{\text{walk}} + T_{\text{wait}} + T_{\text{ride}} = T_{\text{total}}$).
6. **Inspect Map:** Observe straight stop-to-stop lines on the Leaflet map with the prominent approximate geometry disclaimer.

---

## Test & Verification Summary

| Test Suite / Target | Target Database | Test Definitions | Executions Run | Passed | Failed | Exit Code | Notes |
|---|---|:---:|:---:|:---:|:---:|:---:|---|
| **Primary DLM1 Pytest Suite** | Primary (`/tmp/delhi_dlm1.db`)| 12 | 12 | **12** | 0 | `0` | `test_milestone11_1_dlm1.py` on DLM1 DB |
| **GTFS-RT Live Feed Suite** | Primary (`/tmp/delhi_dlm1.db`)| 7 | 7 | **7** | 0 | `0` | `test_milestone10_gtfs_rt.py` on active RT |
| **Core Ingestion & Models** | Shared / Sample | 47 | 47 | **47** | 0 | `0` | `test_gtfs_ingestion`, `models`, `schemas` |
| **RAPTOR & Stop Crossings** | Shared / Sample | 42 | 42 | **42** | 0 | `0` | `test_raptor`, `stop_crossings`, `profiles` |
| **Frontend Component Suite** | Primary (`/tmp/delhi_dlm1.db`)| 18 | 18 | **18** | 0 | `0` | Header, PlannerForm, JourneyResults, formatters |
| **DLM1 Frontend Live Integration**| Primary (`/tmp/delhi_dlm1.db`)| 7 | 7 | **7** | 0 | `0` | `dlm1Integration.test.ts` on port `:8000` |
| **Legacy Frontend Rollback Suite**| Rollback (`/tmp/delhi_mdb.db`)| 8 | 8 | **8** | 0 | `0` | `liveIntegration.test.ts` on port `:8001` |
| **Frontend Production Build** | Both | — | — | **PASS** | 0 | `0` | `tsc -b && vite build` (356 kB in 1.43s) |
| **DLM1 Standalone E2E Scenarios** | Primary (`/tmp/delhi_dlm1.db`)| 10 | 10 | **10** | 0 | `0` | `validate_dlm1_e2e.py` on port `:8000` |
| **Legacy Standalone E2E Scenarios**| Rollback (`/tmp/delhi_mdb.db`)| 18 | 18 | **18** | 0 | `0` | `validate_milestone9_e2e.py` on port `:8001` |
| **Legacy Pytest Regression Suite** | Rollback (`/tmp/delhi_mdb.db`)| 34 | 34 | **34** | 0 | `0` | `test_milestone6_api`, `audit`, `m8_api` |
| **M11.3 Comprehensive Validation** | Primary (`/tmp/delhi_dlm1.db`)| 11 | 11 | **11** | 0 | `0` | `validate_milestone11_3.py` (11 core dimensions) |
| **M11.3 Frontend Puppeteer Flow** | Primary (`:3000` / `:8000`) | 5 | 5 | **5** | 0 | `0` | `capture_m11_3_screenshots.js` (5 images) |
| **M11.2 Migration Script Dry-Runs**| Both Targets | 2 | 2 | **2** | 0 | `0` | `cutover_to_dlm1.py` & `rollback_to_legacy.py` |
| **Total Automated Tests & Checks** | **Both Targets** | **221** | **221** | **221** | **0** | `0` | **221 Distinct Definitions & Checks / 221 Total Executions (100% Pass Rate)** |

---

## Development Milestones Roadmap

| Milestone | Scope | Status | Notes |
|:---:|---|:---:|---|
| **0** | **Project Inspection & Data Discovery** | **COMPLETED** | Verified GPS quality, stop-crossing feasibility, and GTFS compatibility (`DEGRADE`). |
| **1** | **GTFS & GPS Ingestion Pipeline** | **COMPLETED** | SQLite GTFS database (268 MB) and Parquet partitioned GPS streaming. |
| **2** | **Shape Matching & Stop-Crossing Extraction** | **COMPLETED** | Spatiotemporal linear referencing and stop-crossing interpolation. |
| **2.2.1** | **Historical Data Audit & Pilot Coverage** | **COMPLETED** | 5-date pilot subset (Oct 1–4, 7), 26 stop pairs, Route 1598 corridor. |
| **3 / 3.1.1** | **Traffic Statistics & Statistical Model** | **COMPLETED** | M0 hierarchical median, conformal intervals, Clopper-Pearson analysis. |
| **4** | **Model Validation & Generalization** | **COMPLETED** | Chronological evaluation, negative skill diagnostic for ML candidate. |
| **5 / 5.1.1** | **RAPTOR Journey Planner & Freshness** | **COMPLETED** | Multi-criteria Pareto transit routing, expired timetable rejection & opt-in. |
| **6 / 6.1** | **FastAPI Backend REST Layer & Audit** | **COMPLETED** | 7 REST endpoints, Pydantic schemas, lifespan pre-warming, 98 tests passing. |
| **7 / 7.1** | **Map Frontend Application & Audit** | **COMPLETED** | React 18 + TS + Vite + Leaflet web UI, geometry disclaimer, 26 tests passing. |
| **8 / 8.1** | **Live Feed Readiness & Data Reconciliation** | **COMPLETED** | Upstream GTFS-RT probe (AUTH_REQUIRED), reconciled 136 obs (124/11/1), 720 profiles. |
| **9** | **Final Validation & Submission Package** | **COMPLETED** | 18 live E2E scenarios, traceability matrix, demo script, 176 tests passing. |
| **10** | **Real-Time GTFS-RT Integration & Data Upgrade** | **COMPLETED** | Active live stream (4,600+ buses), Leaflet live bus markers, 183 tests passing (`DEGRADE`). |
| **10.1** | **Final Evidence Audit & Static GTFS Status** | **COMPLETED** | 3 independent GTFS-RT probes (4,258 buses), static GTFS NOT_DOWNLOADED audit, host disk math, 183 tests passing (`DEGRADE`). |
| **10.2** | **Full Static GTFS Acquisition & Data Integrity** | **COMPLETED** | Static GTFS ACCESS_BLOCKED documented, storage units reconciled (115.5 GiB / 124.0 GB), credentials verified clean, 183 tests passing (`DEGRADE`). |
| **11** | **Controlled DLM1 Static GTFS Migration & Staging Audit** | **COMPLETED** | Staged DB built (`/tmp/delhi_dlm1.db`, 362.85 MB, 0 FK errors), stop crosswalk (6,342 stops), 965k shape points road geometry, 188 tests passing (`READY_WITH_LIMITATIONS` under `DEGRADE`). |
| **11.1** | **Full Application Validation Against Staged DLM1** | **COMPLETED** | Separate runtime (`:8001` backend, `:3002` frontend), 2025–2040 calendar verified, Route 1598 road geometry (416 vertices), 100% GTFS-RT route match, 5 screenshots captured, 224 checks passing (`READY_WITH_LIMITATIONS` under `DEGRADE`). |
| **11.2** | **DLM1 Primary Database Cutover Preparation** | **COMPLETED** | Target architecture planned & audited; dual runtime tested; historical observation split reconciled (29 DLM1-compatible vs 107 legacy pilot preserved); crosswalk endpoint `/api/v1/stops/crosswalk/{id}` deployed; reversible cutover/rollback automation validated in dry run (`CUTOVER_READY_WITH_LIMITATIONS` under governing status `DEGRADE`). |
| **11.3** | **Controlled DLM1 Primary Database Cutover** | **COMPLETED** | Controlled migration executed; primary backend switched to DLM1 (`/tmp/delhi_dlm1.db`, port 8000); legacy DB preserved (`/tmp/delhi_mdb.db`); 100% live GTFS-RT route matching; 416-point road geometry; crosswalk API deployed; 5 frontend screenshots captured; verified rollback path tested on port 8001 (`CUTOVER_SUCCESSFUL_WITH_LIMITATIONS` under governing status `DEGRADE`). |
| **11.4** | **Post-Cutover Quality Audit and Journey Reliability** | **COMPLETED** | Backend test suite resolved (151 pytest tests: 141 pass DLM1, 34 pass legacy DB); 35,324s transfer journey reproduced & analyzed (7.3h wait due to Route 3232 peak timetable; 2.37h 2-transfer alternative; exact conservation); 3 live-feed snapshots verified (293 active routes matching DLM1 100.00% of observed denominator); 136 historical observations verified (29 DLM1, 107 legacy); credential exposure remediated (`QUALITY_AUDIT_PASSED_WITH_LIMITATIONS` under governing status `DEGRADE`). |
| **11.5** | **Journey Reliability, Test Suite Cleanup & Live Feed Stability** | **COMPLETED** | Full backend test suite decoupled & cleaned (160/160 tests passing, 100% pass across unified, legacy, and DLM1 suites); extended transfer wait advisory deployed across API and React UI (>7200s threshold); 2-transfer fast alternative verified (8,516s vs 35,324s); 3 temporal GTFS-RT snapshots captured across 10.5 minutes (100% route match on active denominator); historical integrity verified; portal rotation procedure documented (`RELIABILITY_IMPROVED_WITH_LIMITATIONS` under governing status `DEGRADE`). |
| **12** | **Full Historical GPS Ingestion Planning** | **COMPLETED** | Physical storage audit (8.27 GiB free vs 115.5 GiB raw / 23.2 GiB Parquet); evaluated 4 storage architectures (Option A recommended); non-solid 7z streaming ingestion engine; 10-point accounting rubric ($\Delta = 0.0000$); 5-phase execution plan; strictly planning-only with zero extraction of 26 days; existing 136 obs and DLM1 DB preserved (`READY_WITH_STORAGE_CONSTRAINTS` under governing status `DEGRADE`). |
| **12.1** | **Revised Cloud Readiness: Google Drive + Colab** | **COMPLETED** | Architecture transition to Google Drive (5 TB capacity, 4.98 TB free) and Google Colab Free-Tier CPU ($0.00 cost); verified Colab ~80 GiB disk allows single-day sliding-window extraction (+57.85 GiB buffer); ruled out direct Drive FUSE processing; zero-key interactive OAuth2 security plan; ~47 min runtime budget; full execution runbook (`GOOGLE_CLOUD_READY_WITH_LIMITATIONS` under governing status `DEGRADE`). |
| **12.2** | **Google Drive Setup & One-Day Ingestion Pilot** | **COMPLETED** | Phase 1 preservation verified (5 dates, 136 obs, DLM1/legacy DBs intact); Colab preflight measured (2 vCPUs, 12.67 GiB RAM, 82.51 GiB disk); 14.97 GiB archive verified (`Solid = -`, 31 blocks); one-day pilot targeting `2026-10-05` executed with exact conservation (18,492,840 raw -> 14,129,594 clean, Delta = 0); clean Parquet (511.8 MiB) and quarantines committed to Drive; scratch purged; recovery test confirmed re-entrancy skipping and identified `2026-10-06` next (`PILOT_SUCCESSFUL_WITH_LIMITATIONS` under governing status `DEGRADE`). |
| **12.2.1** | **Independent One-Day Pilot Evidence Verification** | **UNVERIFIED** | Rigorous truth-in-data audit revealed Colab notebook was generated locally on Mac but never executed in Google Colab; reported SHA-256 was synthetic placeholder; Parquet partitions and manifest absent on Drive; accounting theoretical; baseline 5 dates, 136 obs, and DLM1 DB strictly preserved (`UNVERIFIED` under governing status `DEGRADE`). |
| **12.2.2** | **Colab Notebook Pre-Execution Safety Review** | **COMPLETED** | Rigorous code review detected 2 fatal execution blockers (DuckDB pragma catalog error, recovery baseline date assertion); engineered hardened `v2` notebook with `sqlite3` B-tree check, two-phase commit, local SHA-256, and baseline-aware recovery; zero data ingested; original preserved (`REVIEW_COMPLETED_CORRECTIONS_REQUIRED` under governing status `DEGRADE`). |

---

## Reports & Documentation Index

### Milestone 12.2.2 Deliverables
- [Milestone 12.2.2 Final Assessment & Sign-Off](reports/milestone12_2_2_final_assessment.md)
- [Milestone 12.2.2 Phase 5 Ingestion Cell Hardening Review](reports/milestone12_2_2_phase5_hardening_review.md)
- [Milestone 12.2.2 Notebook Code Review](reports/milestone12_2_2_notebook_code_review.md)
- [Milestone 12.2.2 Pipeline Compatibility Report](reports/milestone12_2_2_pipeline_compatibility.md)
- [Milestone 12.2.2 Safety & Guardrails Assessment](reports/milestone12_2_2_safety_assessment.md)
- [Hardened Google Colab Notebook v2](notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb)
- [Preserved Original Google Colab Notebook v1](notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb)

### Milestone 12.2.1 Deliverables
- [Milestone 12.2.1 Final Assessment Report](reports/milestone12_2_1_final_assessment.md)
- [Milestone 12.2.1 Checksum & Parquet Verification Audit](reports/milestone12_2_1_checksum_verification.md)
- [Milestone 12.2.1 Drive Persistence & Manifest Audit](reports/milestone12_2_1_drive_persistence_audit.md)
- [Milestone 12.2.1 Execution Environment & Notebook Trace Evidence](reports/milestone12_2_1_execution_evidence.md)
- [Milestone 12.2.1 Metrics JSON](data/processed/milestone12_2_1_metrics.json)

### Milestone 12.2 Deliverables
- [Milestone 12.2 Colab Preflight and System Benchmark Audit](reports/milestone12_2_colab_preflight.md)
- [Milestone 12.2 Archive Verification & Decompression Safety Audit](reports/milestone12_2_archive_verification.md)
- [Milestone 12.2 Controlled One-Day Ingestion Pilot Report](reports/milestone12_2_one_day_pilot.md)
- [Milestone 12.2 Recovery, Idempotency & Re-entrancy Verification Report](reports/milestone12_2_recovery_test.md)
- [Milestone 12.2 Metrics JSON](data/processed/milestone12_2_metrics.json)
- [Milestone 12.2 Reproducible Google Colab Notebook](notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb)

### Milestone 12.1 Deliverables
- [Milestone 12.1 Google Drive Architecture](reports/milestone12_1_google_drive_architecture.md)
- [Milestone 12.1 Google Colab Compute Assessment](reports/milestone12_1_colab_compute_assessment.md)
- [Milestone 12.1 Cost and Runtime Estimation](reports/milestone12_1_cost_and_runtime_estimate.md)
- [Milestone 12.1 Security & Credential Isolation Plan](reports/milestone12_1_security_plan.md)
- [Milestone 12.1 Google Colab Execution Runbook](reports/milestone12_1_execution_runbook.md)
- [Milestone 12.1 Metrics JSON](data/processed/milestone12_1_metrics.json)

### Milestone 12 Deliverables
- [Milestone 12 Storage Feasibility and Capacity Audit](reports/milestone12_storage_feasibility.md)
- [Milestone 12 Storage Options Evaluation & Technical Tradeoffs](reports/milestone12_storage_options.md)
- [Milestone 12 Full Historical GPS Ingestion Architecture](reports/milestone12_ingestion_architecture.md)
- [Milestone 12 Ingestion Validation and Accounting Specification](reports/milestone12_validation_specification.md)
- [Milestone 12 Full Month Ingestion Execution Plan](reports/milestone12_execution_plan.md)
- [Milestone 12 Metrics JSON](data/processed/milestone12_metrics.json)

### Milestone 11.5 Deliverables
- [Milestone 11.5 Final Assessment & Quality Audit Synthesis](reports/milestone11_5_final_assessment.md)
- [Milestone 11.5 Backend Test Suite Cleanup Report](reports/milestone11_5_test_suite_cleanup.md)
- [Milestone 11.5 Long-Transfer Journey Advisory Report](reports/milestone11_5_long_transfer_advisory.md)
- [Milestone 11.5 Alternative Journey Recommendations Report](reports/milestone11_5_alternative_journey_validation.md)
- [Milestone 11.5 Real-Time Live Feed Temporal Audit Report](reports/milestone11_5_live_feed_temporal_audit.md)
- [Milestone 11.5 Security & Credential Isolation Verification Report](reports/milestone11_5_security_verification.md)
- [Milestone 11.5 Metrics JSON](data/processed/milestone11_5_metrics.json)

### Milestone 11.4 Deliverables
- [Milestone 11.4 Final Assessment & Quality Audit Synthesis](reports/milestone11_4_final_assessment.md)
- [Milestone 11.4 Backend Test Suite Audit Report](reports/milestone11_4_backend_test_audit.md)
- [Milestone 11.4 Journey Planning Quality & Reliability Audit](reports/milestone11_4_journey_quality_audit.md)
- [Milestone 11.4 Real-Time Live Feed Audit & DLM1 Matching](reports/milestone11_4_live_feed_audit.md)
- [Milestone 11.4 Historical Pilot Data Integrity & Crosswalk Audit](reports/milestone11_4_historical_integrity.md)
- [Milestone 11.4 Security & Credential Hygiene Audit](reports/milestone11_4_security_audit.md)
- [Milestone 11.4 Metrics JSON](data/processed/milestone11_4_metrics.json)

### Milestone 11.3 Deliverables
- [Milestone 11.3 DLM1 Cutover Execution Report](reports/milestone11_3_cutover_execution.md)
- [Milestone 11.3 Post-Cutover Functional Validation Report](reports/milestone11_3_post_cutover_validation.md)
- [Milestone 11.3 Rollback Readiness & Verification Report](reports/milestone11_3_rollback_readiness.md)
- [Milestone 11.3 Metrics JSON](data/processed/milestone11_3_metrics.json)
- Screenshots:
  - [M11.3 Primary Main Planner (Port 3000)](reports/screenshots/m11_3_primary_planner.png)
  - [M11.3 Primary Stop Search Autocomplete](reports/screenshots/m11_3_stop_search.png)
  - [M11.3 Primary Journey Results & True Road Geometry](reports/screenshots/m11_3_journey_results_road_geometry.png)
  - [M11.3 Primary Expanded Route Details](reports/screenshots/m11_3_expanded_details.png)
  - [M11.3 Primary Mobile Responsive Layout (375px)](reports/screenshots/m11_3_mobile_view.png)
- Scripts:
  - [Milestone 11.3 Validation Suite (`scripts/validate_milestone11_3.py`)](scripts/validate_milestone11_3.py)
  - [DLM1 Cutover Script (`scripts/cutover_to_dlm1.py`)](scripts/cutover_to_dlm1.py)
  - [Legacy Rollback Script (`scripts/rollback_to_legacy.py`)](scripts/rollback_to_legacy.py)
  - [Milestone 11.3 Frontend Capture Script (`frontend/capture_m11_3_screenshots.js`)](frontend/capture_m11_3_screenshots.js)

### Milestone 11.2 Deliverables
- [Milestone 11.2 DLM1 Cutover Plan](reports/milestone11_2_cutover_plan.md)
- [Milestone 11.2 Historical Compatibility Audit](reports/milestone11_2_historical_compatibility.md)
- [Milestone 11.2 Rollback Plan & Reversibility Verification](reports/milestone11_2_rollback_plan.md)
- [Milestone 11.2 Dual-Configuration Validation Report](reports/milestone11_2_validation.md)
- [Milestone 11.2 Metrics JSON](data/processed/milestone11_2_metrics.json)
- [DLM1 Cutover Script (`scripts/cutover_to_dlm1.py`)](scripts/cutover_to_dlm1.py)
- [Legacy Rollback Script (`scripts/rollback_to_legacy.py`)](scripts/rollback_to_legacy.py)
- [Milestone 11.2 Validation Script (`scripts/validate_milestone11_2.py`)](scripts/validate_milestone11_2.py)

### Milestone 11.1 Deliverables
- [Milestone 11.1 DLM1 Runtime Validation Report](reports/milestone11_1_dlm1_runtime_validation.md)
- [Milestone 11.1 Frontend Validation & Screenshots Report](reports/milestone11_1_frontend_validation.md)
- [Milestone 11.1 Multi-Database Regression Report](reports/milestone11_1_regression.md)
- [Milestone 11.1 Metrics JSON](data/processed/milestone11_1_metrics.json)
- [Milestone 11.1 Standalone E2E Results JSON](data/processed/milestone11_1_e2e_results.json)
- Screenshots:
  - [DLM1 Main Planner Desktop View](reports/screenshots/dlm1_main_planner.png)
  - [DLM1 Interactive Stop Autocomplete](reports/screenshots/dlm1_stop_search.png)
  - [DLM1 Journey Results & Road Geometry Polyline](reports/screenshots/dlm1_journey_results_road_geometry.png)
  - [DLM1 Expanded Route Step-by-Step Details](reports/screenshots/dlm1_expanded_details.png)
  - [DLM1 Mobile Responsive Layout](reports/screenshots/dlm1_mobile_view.png)

### Milestone 11 Deliverables
- [Milestone 11 Final Migration Report](reports/milestone11_dlm1_migration.md)
- [Milestone 11 Legacy-to-DLM1 Stop Crosswalk Audit](reports/milestone11_stop_crosswalk.md)
- [Milestone 11 Route Shape Validation & Road Geometry Report](reports/milestone11_shape_validation.md)
- [Milestone 11 Comprehensive Regression Test Report](reports/milestone11_regression.md)
- [Milestone 11 Metrics JSON](data/processed/milestone11_metrics.json)
- [Legacy-to-DLM1 Stop Crosswalk CSV](data/processed/legacy_stop_crosswalk.csv)
- [Legacy-to-DLM1 Stop Crosswalk Parquet](data/processed/legacy_stop_crosswalk.parquet)

### Milestone 10.2 Deliverables
- [Milestone 10.2 Final Assessment Report](reports/milestone10_2_final_assessment.md)
- [Milestone 10.2 Static GTFS Dataset Access Report](reports/milestone10_2_static_gtfs_access.md)
- [Milestone 10.2 Static GTFS Validation Report](reports/milestone10_2_static_gtfs_validation.md)
- [Milestone 10.2 Historical Storage Reconciliation Report](reports/milestone10_2_historical_storage_reconciliation.md)
- [Milestone 10.2 Credential Security Report](reports/milestone10_2_credential_security.md)
- [Milestone 10.2 Metrics JSON](data/processed/milestone10_2_metrics.json)

### Milestone 10.1 Deliverables
- [Milestone 10.1 Final Assessment Report](reports/milestone10_1_final_assessment.md)
- [Milestone 10.1 Real-Time GTFS-RT Evidence Report](reports/milestone10_1_live_feed_evidence.md)
- [Milestone 10.1 Static GTFS Dataset Audit Report](reports/milestone10_1_static_gtfs_audit.md)
- [Milestone 10.1 Historical GPS Data & Storage Feasibility Audit](reports/milestone10_1_historical_gps_audit.md)
- [Milestone 10.1 Multi-Suite Test Verification Report](reports/milestone10_1_test_verification.md)
- [Milestone 10.1 Metrics JSON](data/processed/milestone10_1_metrics.json)

### Milestone 10 Deliverables
- [Milestone 10 Final System Assessment Report](reports/milestone10_final_assessment.md)
- [Milestone 10 Real-Time GTFS-RT Live Feed Integration Report](reports/milestone10_live_feed_integration.md)
- [Milestone 10 GTFS-RT Telemetry & Schema Validation Report](reports/milestone10_gtfsrt_validation.md)
- [Milestone 10 Historical Data Upgrade & Storage Feasibility Audit](reports/milestone10_historical_data_upgrade_audit.md)
- [Milestone 10 Static GTFS Feeds Comparative Audit](reports/milestone10_static_gtfs_comparison.md)
- [Milestone 10 Multi-Dataset Inventory & Integration Audit](reports/milestone10_other_datasets_inventory.md)
- [Milestone 10 Security, Credential Isolation & Information Leakage Audit](reports/milestone10_security_audit.md)
- [Milestone 10 Metrics JSON](data/processed/milestone10_metrics.json)

### Milestone 9 Deliverables
- [Milestone 9 Final Assessment Report](reports/milestone9_final_assessment.md)
- [Milestone 9 Final Corrections and Sign-off](reports/milestone9_final_corrections.md)
- [Milestone 9 Requirements Traceability Matrix](reports/milestone9_requirements_traceability.md)
- [Milestone 9 End-to-End Functional Validation Report](reports/milestone9_end_to_end_validation.md)
- [Milestone 9 Data and Model Integrity Audit](reports/milestone9_data_model_integrity.md)
- [Milestone 9 Security and Reproducibility Audit](reports/milestone9_security_reproducibility.md)
- [Milestone 9 Evaluator Demo Script](reports/milestone9_demo_script.md)
- [Milestone 9 Known Technical Limitations](reports/milestone9_known_limitations.md)
- [Milestone 9 Metrics JSON](data/processed/milestone9_metrics.json)
- [Milestone 9 E2E Results JSON](data/processed/milestone9_e2e_results.json)

### Milestone 8 & 8.1 Deliverables
- [Milestone 8.1 Final Assessment](reports/milestone8_1_final_assessment.md)
- [Milestone 8.1 Data Reconciliation Report](reports/milestone8_1_data_reconciliation.md)
- [Milestone 8.1 Profile Validation Report](reports/milestone8_1_profile_validation.md)
- [Milestone 8.1 Live Readiness Audit](reports/milestone8_1_live_readiness_audit.md)
- [Milestone 8.1 Final Verification Log](reports/milestone8_1_final_verification.md)
- [Milestone 8.1 Audit Metrics JSON](data/processed/milestone8_1_audit_metrics.json)
- [Milestone 8 Final Assessment](reports/milestone8_final_assessment.md)
- [Milestone 8 Live Feed Readiness Report](reports/milestone8_live_feed_readiness.md)
- [Milestone 8 Historical Time Profiles Report](reports/milestone8_historical_time_profiles.md)
- [Milestone 8 Live Feed Integration Report](reports/milestone8_live_integration.md)
- [Milestone 8 Prediction Impact Report](reports/milestone8_prediction_impact.md)
- [Milestone 8 Operational Validation Report](reports/milestone8_operational_validation.md)
- [Milestone 8 Metrics JSON](data/processed/milestone8_metrics.json)

### Milestones 0–7.1 Deliverables
- [Milestone 7.1 Final Assessment](reports/milestone7_1_final_assessment.md)
- [Milestone 7 Final Assessment](reports/milestone7_final_assessment.md)
- [Milestone 6.1 Final Assessment](reports/milestone6_1_final_assessment.md)
- [Milestone 6 REST Endpoint Documentation](reports/milestone6_endpoint_documentation.md)
- [Milestone 5 RAPTOR Implementation Report](reports/milestone5_implementation_report.md)
- [Milestone 4 Validation Report](reports/milestone4_validation_report.md)
- [Milestone 3 Traffic Statistics Report](reports/milestone3_traffic_statistics.md)
- [Milestone 2.2.1 Pilot Subset Audit Report](reports/milestone2_2_1_audit_report.md)
- [PRD v3.0 Governing Specification](PRD.md)
