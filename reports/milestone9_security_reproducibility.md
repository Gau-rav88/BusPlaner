# Milestone 9 — Security and Reproducibility Audit Report

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Current Operational Status:** **`DEGRADE`** *(Strictly Maintained)*  
**Audit Milestone:** Milestone 9: Final Validation, Demo Readiness & Submission Package  
**Date:** November 21, 2026  

---

## 1. Executive Summary & Security Audit

This report verifies that the Delhi Bus Traffic Prediction & Journey Planner repository adheres to strict cybersecurity, information-hygiene, and operational reproducibility standards.

No credentials, API tokens, passwords, or private local user directory paths are exposed in repository tracking, configuration templates, or user-facing documentation. The system is designed for deterministic reproducibility on any Unix/macOS developer workstation.

---

## 2. Security Audit Matrix

| Security Area | Verified Implementation & Protection Mechanism | Audit Finding |
|---|---|:---:|
| **Secret & Token Hygiene** | Checked git status and `.env.example`. `DELHI_TRANSPORTSTACK_API_KEY` is completely blank. No API keys or tokens are committed. | **PASS** |
| **API Response Leakage** | `GET /api/v1/live/status` returns `"auth_configured": false`, exposing only a boolean status without echoing keys. | **PASS** |
| **Error Sanitization** | `RequestValidationError` and `HTTPException` handlers sanitize internal stack traces into clean RFC-compliant JSON envelopes. | **PASS** |
| **CORS Configuration** | `CORSMiddleware` in `backend/app/main.py` restricts origin access to configured local endpoints (`localhost:3000`, `127.0.0.1:3000`, `localhost:5173`, `127.0.0.1:5173`). Wildcard `*` origins are rejected. | **PASS** |
| **Input Coordinate Sanitization** | Pydantic schemas enforce strict bounding checks (lat: $-90$ to $90$, lon: $-180$ to $180$). Out-of-bounds coordinates return clean HTTP 422 errors. | **PASS** |
| **Path Traversal Protection** | File loading in SQLite and Parquet streaming is pinned to explicit project-relative directories (`data/processed/`, `/tmp/delhi_mdb.db`). | **PASS** |
| **Dependency Pinning** | `backend/requirements.txt` and `frontend/package.json` lock major/minor dependency versions. No untrusted packages are invoked. | **PASS** |

---

## 3. Fresh Developer Setup Guide (10-Step Reproducibility)

Follow these exact steps to clone, configure, build, and run the complete stack on a clean machine:

### 1. Required Software
- **Operating System:** macOS (Apple Silicon or Intel) or Linux (Ubuntu 22.04+ / Debian 12+)
- **Python:** Python 3.11, 3.12, or 3.13 (Python 3.13.5 verified)
- **Node.js:** Node.js 18 LTS or Node.js 20/22 (Node.js 22.22.0 verified)
- **NPM:** 10+
- **SQLite:** SQLite 3.35+

### 2. Python Virtual Environment Setup
```bash
cd delhi_hacks
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

### 5. Data Files & Prerequisites
The project requires the following data assets:
- **Processed Parquet Ground Truth:** Pre-bundled in `data/processed/stop_crossings/service_date=*/observed_segments.parquet` (136 verified segment traversals).
- **Historical Time Profiles:** Pre-computed in `data/processed/historical_time_profiles.json` (720 hourly bins).
- **Delhi GTFS SQLite Database:** The pre-populated GTFS SQLite database is located at `/tmp/delhi_mdb.db` (268 MB). If running on a fresh host without `/tmp/delhi_mdb.db`, ingest the static GTFS feed:
  ```bash
  python3 scripts/build_gtfs_sqlite.py --gtfs-dir data/raw/gtfs --output-db /tmp/delhi_mdb.db
  ```

### 6. Environment Configuration
Copy the configuration template:
```bash
cp .env.example .env
```
Leave `DELHI_TRANSPORTSTACK_API_KEY=` blank. The system safely operates under `AUTH_REQUIRED` mode.

### 7. Database & Serving Layer Check
Verify SQLite database accessibility:
```bash
sqlite3 /tmp/delhi_mdb.db "SELECT count(*) FROM stops;"
# Expected output: 3266
```

### 8. Start the FastAPI Backend Server
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
- Interactive Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health Endpoint: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

### 9. Start the Vite Frontend Development Server
In a separate terminal:
```bash
cd frontend
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your web browser.

### 10. Run Full Verification Test Suite
Execute tests across both backend and frontend:
```bash
# 1. Backend Pytest Suite (132 tests)
pytest -q backend/tests/

# 2. Frontend Vitest Suite (26 tests)
cd frontend && npm test

# 3. Frontend Production Bundle Build
npm run build
```

---

## 4. Operational Lifecycle & Graceful Shutdown

- **Startup:** The FastAPI `lifespan` context manager in `backend/app/main.py` automatically initializes the RAPTOR routing graph, builds the $k\text{-d}$ tree spatial index, pre-warms the M0 baseline historical cache, and runs an internal warm-up query. Cold-start latency for the first end-user request is completely eliminated.
- **Shutdown:** SIGINT / SIGTERM signals trigger graceful closing of database connection pools and background tasks without resource leaks or corrupted SQLite journals.

