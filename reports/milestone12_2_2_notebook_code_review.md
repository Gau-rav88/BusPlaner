# Milestone 12.2.2 — Colab Notebook Source Code Review

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Milestone:** 12.2.2 — Colab Notebook Pre-Execution Safety Review  
**Subject Files:** 
- Original: `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb`
- Corrected: `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb`  
**Governing Operational Status:** `DEGRADE`  
**Review Verdict:** `REVIEW_COMPLETED_CORRECTIONS_REQUIRED`

---

## 1. Executive Summary & Review Scope

Following the Milestone 12.2.1 truth-in-data audit—which established that the Milestone 12.2 historical GPS pilot was never executed in Google Colab—this review conducted a comprehensive, line-by-line inspection of the 11 notebook cells in `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb` prior to authorizing any live cloud execution.

The review verified the source archive URL, selective 7z decompression parameters, DuckDB data cleaning operations, output Parquet schemas, Google Drive FUSE interaction patterns, two-phase manifest commit sequencing, restart recovery logic, and scratch space purging boundaries.

Two critical fatal execution blockers and several structural deficiencies were discovered in the original notebook:
1. **Fatal DuckDB Pragma Error:** Cell 8 attempted to execute `SELECT * FROM pragma_integrity_check();` against an attached SQLite database inside DuckDB, which fails with `Catalog Error: Table Function with name pragma_integrity_check does not exist!`.
2. **Fatal Recovery Assertion Failure:** Cell 10's recovery test iterated over all 31 October days starting at `2026-10-01`. Because the Google Drive manifest only records Colab-processed dates (`2026-10-05`), `unprocessed[0]` resolved to `2026-10-01`, causing `assert unprocessed[0] == '2026-10-06'` to immediately crash with an `AssertionError`.
3. **Premature Archive Backup:** Cell 6 backed up the 14.97 GiB archive to Google Drive prior to verifying byte size or 7z headers.
4. **Network-Bound SHA-256 Hashing:** Cell 8 computed the SHA-256 checksum by streaming 500 MB over Google Drive FUSE rather than locally on scratch disk.
5. **Premature Scratch Purge:** Cell 8 purged scratch files before committing the manifest.
6. **Incomplete Quarantine Schema:** Cell 8 omitted `quarantine_reason` and `service_date` from the E02 conflicts Parquet export.

All defects have been remediated in `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb` while preserving the original notebook untouched.

---

## 2. Cell-by-Cell Source Code Inspection

### Cell 0 (Markdown) — Header & Overview
- **Original Content:** Outlined project metadata, Free-Tier environment parameters, and declared `Verdict: PILOT_SUCCESSFUL_WITH_LIMITATIONS`.
- **Review Finding:** Prematurely declared a successful execution verdict in an unexecuted artifact.
- **Corrective Action (v2):** Updated header to reflect `Operating Status: DEGRADE` and `Execution Status: READY_FOR_EXECUTION (Pending Human Approval)`, explicitly cataloging all safety enhancements.

---

### Cell 1 (Markdown) & Cell 2 (Code) — Phase 3: Colab Preflight Hardware Benchmarking
- **Source Logic:**
  ```python
  !pip install -q duckdb pyarrow psutil tqdm
  !apt-get install -q -y p7zip-full
  import os, sys, shutil, psutil, subprocess, time, json, hashlib
  import duckdb
  import pyarrow.parquet as pq
  # CPU, RAM, Disk, 7z checks
  assert disk.free / (1024**3) >= 50.0, f'Insufficient disk space: {disk.free / (1024**3):.2f} GiB'
  assert ram.total / (1024**3) >= 11.0, f'Insufficient RAM: {ram.total / (1024**3):.2f} GiB'
  ```
- **Review Finding:** Dependency installation and hardware inspection logic are structurally sound. Colab CPU runtimes provide 2 vCPUs, ~12.7 GiB RAM, and ~80–100 GiB root disk on `/content`. Preflight threshold assertions (>= 50 GiB disk, >= 11 GiB RAM) provide ample headroom for single-day ingestion (~22.15 GiB transient peak).
- **Corrective Action (v2):** Added `sqlite3` to imported standard modules and clarified error messaging on threshold assertions.

---

### Cell 3 (Markdown) & Cell 4 (Code) — Phase 2: Google Drive Native Mounting
- **Source Logic:**
  ```python
  from google.colab import drive
  drive.mount('/content/drive')
  DRIVE_ROOT = '/content/drive/MyDrive/Delhi_Bus_Historical_Data'
  SCRATCH_DIR = '/content/scratch'
  # Subdirectories: source, raw_manifests, parquet, quarantine, metadata, validation_reports
  ```
- **Review Finding:** Employs Colab's native interactive OAuth2 browser modal. Zero API tokens, passwords, or service account keys are stored or printed. Creates directories with `exist_ok=True`.
- **Review Risk:** Did not assert whether `/content/drive/MyDrive` is accessible after mounting. If the user cancels the OAuth popup, subsequent operations fail ambiguously.
- **Corrective Action (v2):** Added `assert os.path.exists('/content/drive/MyDrive')` immediately following mount.

---

### Cell 5 (Markdown) & Cell 6 (Code) — Phase 4: Archive Download & Verification
- **Source Logic:**
  - Target URL: `https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z`
  - Expected size: `16,077,236,568` bytes (14.97 GiB).
  - Listing check: `7z l "{LOCAL_ARCHIVE}" | head -n 25`, asserting `'Solid = -'`.
- **Review Finding:** The archive URL, expected size, and non-solid validation (`Solid = -`) are empirically correct. Non-solid compression ensures 31 independent blocks that permit single-day extraction without decompressing previous days.
- **Fatal Risk in Original:** The download block invoked `shutil.copy2(LOCAL_ARCHIVE, DRIVE_ARCHIVE)` *before* verifying `actual_size == EXPECTED_BYTES` or testing 7z headers. If `curl` was interrupted or errored, a corrupt or truncated file would be uploaded to Google Drive.
- **Corrective Action (v2):** Re-sequenced operations: local archive size and 7z header assertions must pass 100% *before* any backup to Google Drive occurs.

---

### Cell 7 (Markdown) & Cell 8 (Code) — Phase 5: Controlled One-Day Pilot Ingestion (`2026-10-05`)
This is the core pipeline cell. Analysis across its 10 operational steps revealed critical defects:

1. **Selective Decompression:**
   - Extraction command: `7z e -y -o'{SCRATCH_DIR}' '{LOCAL_ARCHIVE}' '{DB_NAME}'`
   - Target database: `bus_movements_2026_10_05.db` (uncompressed: `3,428,802,560` bytes).
   - In v1, stdout was redirected to `> /dev/null`, suppressing failure diagnostics. In v2, executed cleanly via `subprocess.run(..., check=True)` with exact size validation.
2. **SQLite Integrity Check (FATAL DEFECT):**
   - Original code:
     ```python
     con_test = duckdb.connect()
     con_test.execute(f'ATTACH "{LOCAL_DB}" AS raw_sqlite (TYPE SQLITE);')
     integ_res = con_test.execute('SELECT * FROM pragma_integrity_check();').fetchall()
     ```
   - Empirical Failure: DuckDB does not support SQLite's `PRAGMA integrity_check` via table function syntax. Running this query raises:
     `Catalog Error: Table Function with name pragma_integrity_check does not exist!`
   - Corrective Action (v2): Replaced with Python's built-in `sqlite3` module:
     ```python
     con_sql = sqlite3.connect(LOCAL_DB)
     integ_res = con_sql.execute('PRAGMA integrity_check;').fetchall()
     con_sql.close()
     assert integ_res[0][0] == 'ok'
     ```
3. **DuckDB Cleaning Pipeline:**
   - Rules E01, E02, E03 and time projection SQL queries were analyzed. The mathematical accounting equation:
     $$\Delta = N_{\text{raw}} - (N_{\text{clean}} + N_{\text{dedup}} + N_{\text{conflicts}} + N_{\text{oob}}) \equiv 0$$
     is an exact algebraic identity across partitioned stages.
4. **Quarantine Schema Inconsistency:**
   - In v1, `stage_ranked WHERE conflict_rank > 1` was exported directly without `quarantine_reason` or `service_date`.
   - Corrective Action (v2): Harmonized with `scripts/ingest_gps.py`, explicitly projecting `'E02_CONFLICTING_TIMESTAMP_POSITION' as quarantine_reason` and `'{PILOT_DATE}' as service_date`.
5. **SHA-256 Hashing Location:**
   - In v1, SHA-256 was computed by opening the uploaded file over Google Drive FUSE (`drive_clean_path`).
   - Corrective Action (v2): Computes SHA-256 locally on `/content/scratch` prior to upload.
6. **Upload Verification & Manifest Commit Sequencing:**
   - In v1, scratch files were deleted in Step 9 *before* writing the manifest in Step 10.
   - Corrective Action (v2): Enforces Two-Phase Commit:
     - Phase A: Upload clean Parquet and quarantine files.
     - Phase B: Verify existence, byte sizes, and read Parquet metadata row count ($N_{\text{clean}}$).
     - Phase C: Atomically commit manifest with `os.replace` (and `OSError` FUSE fallback).
     - Phase D: Purge scratch files only after manifest write succeeds.

---

### Cell 9 (Markdown) & Cell 10 (Code) — Phase 6: Recovery & Re-entrancy Test
- **Original Code:**
  ```python
  all_dates = [f'2026-10-{d:02d}' for d in range(1, 32)]
  unprocessed = []
  for d in all_dates:
      state = saved_manifest['partitions'].get(d, {}).get('status')
      if state != 'COMMITTED':
          unprocessed.append(d)
  assert unprocessed[0] == '2026-10-06'
  ```
- **Fatal Flaw:** The 5 baseline pilot dates (`2026-10-01`, `02`, `03`, `04`, `07`) were processed locally on Mac in M1/M2 and do not reside in Google Drive's `ingestion_manifest.json`. When the loop begins at `d = '2026-10-01'`, `state` is `None`! Consequently, `unprocessed[0]` is `'2026-10-01'`, causing `assert unprocessed[0] == '2026-10-06'` to fail with `AssertionError: Expected 2026-10-06 as next pending, got 2026-10-01`.
- **Corrective Action (v2):** Explicitly defines `BASELINE_LOCAL_DATES = {'2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-07'}` and skips them during Colab pending date calculation. `unprocessed[0]` correctly resolves to `'2026-10-06'`.

---

## 3. Summary of Remediated Defects

| # | Component | Original Defect (v1) | Remediated Behavior (v2) | Severity |
|:---:|---|---|---|:---:|
| 1 | Cell 8 (Integrity) | DuckDB `pragma_integrity_check()` catalog error | Uses standard `sqlite3.connect` for `PRAGMA integrity_check;` | **FATAL** |
| 2 | Cell 10 (Recovery) | Asserts `unprocessed[0] == '2026-10-06'` but gets `'2026-10-01'` | Excludes `BASELINE_LOCAL_DATES` from pending queue | **FATAL** |
| 3 | Cell 6 (Archive) | Copies unverified archive to Drive before size check | Validates size and 7z headers before Drive backup | **HIGH** |
| 4 | Cell 8 (Hashing) | Reads 500 MB back over Drive FUSE to compute hash | Computes SHA-256 locally on `/content/scratch` | **MEDIUM** |
| 5 | Cell 8 (Commit) | Purges scratch before writing manifest | Two-phase commit: purges only after manifest verified | **HIGH** |
| 6 | Cell 8 (Quarantine) | E02 conflicts missing `quarantine_reason` & `service_date` | Harmonized schema with `scripts/ingest_gps.py` | **MEDIUM** |
| 7 | Cell 8 (FUSE atomic) | `os.replace` on Drive FUSE risks `[Errno 95]` | Adds try-except fallback to copy + remove | **MEDIUM** |
| 8 | Cell 0 (Header) | Hardcoded unexecuted `PILOT_SUCCESSFUL` verdict | States `DEGRADE` / `READY_FOR_EXECUTION` | **LOW** |

---

## 4. Verification Conclusion

Both notebooks are preserved in the repository:
- Original: [Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb](file:///Users/gauravchauhan/Downloads/delhi_hacks/notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb) (preserved untouched for audit history).
- Hardened: [Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb](file:///Users/gauravchauhan/Downloads/delhi_hacks/notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb) (recommended for operator execution).

The review confirms that `v2` is syntactically sound, verified against local Python 3.13 and DuckDB engines, and ready for human operator execution in Google Colab.

