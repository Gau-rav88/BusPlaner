# Milestone 12.2.2 — Colab Notebook Safety & Guardrails Assessment

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Milestone:** 12.2.2 — Colab Notebook Pre-Execution Safety Review  
**Evaluated Notebooks:** 
- `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb` (Original v1)
- `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb` (Hardened v2)  
**Governing Operational Status:** `DEGRADE`  
**Safety Assessment Verdict:** `HARDENED_SAFETY_STANDARDS_VERIFIED_IN_V2`

---

## 1. Executive Summary

This assessment audits the operational safety guardrails of the proposed Google Colab historical GPS ingestion pipeline prior to human operator execution. Under PRD v3.0 governing status `DEGRADE`, zero-risk protocols must be maintained to shield existing pilot assets, ensure non-destructive recovery, prevent data corruption over cloud filesystems, and guarantee credential isolation.

The evaluation audited the implementation against the **10 Mandatory Safety Requirements** defined in the milestone charter. While the original `v1` notebook exhibited several safety vulnerabilities and two fatal execution defects, the hardened `v2` notebook (`notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb`) incorporates comprehensive pre-checks, post-checks, two-phase commits, and fail-safe boundaries.

---

## 2. Audit Against the 10 Mandatory Safety Requirements

| # | Mandatory Safety Requirement | Status in Original (v1) | Status in Hardened (v2) | Verification & Evidence |
|:---:|---|:---:|:---:|---|
| **1** | **Never delete the source archive** | **PASS** | **PASS** | Archive paths (`LOCAL_ARCHIVE` in `/content` and `DRIVE_ARCHIVE` in `source/`) are strictly excluded from scratch purge operations. Scratch purge explicitly enumerates temporary working files (`LOCAL_DB`, `staged_clean`, `staged_conf`, `staged_oob`). |
| **2** | **Never delete or overwrite existing pilot partitions** | **PASS** | **PASS** | Existing 5-date pilot partitions (`2026-10-01`, `02`, `03`, `04`, `07`) reside on the host Mac filesystem and are never referenced or mounted in Colab. In Colab, the pilot strictly targets `service_date=2026-10-05`. In `v2`, the recovery check explicitly shields these 5 baseline dates. |
| **3** | **Never modify DLM1 or legacy databases** | **PASS** | **PASS** | Primary DLM1 (`/tmp/delhi_dlm1.db`) and legacy reference (`/tmp/delhi_mdb.db`) exist exclusively on the local Mac host. Zero database connections or paths in the Colab notebook reference either file. |
| **4** | **Never process more than October 5** | **PASS** | **PASS** | `PILOT_DATE = '2026-10-05'` is hardcoded as a single-target scalar. Zero loop iterations or batch extractions exist. `unprocessed[0]` is evaluated for next-date validation only, with zero extraction logic attached. |
| **5** | **Never commit manifest before upload & checksum verification** | **DEFECTIVE** | **PASS** | In `v1`, scratch was purged before manifest writing, and upload verification was limited to reading back over Drive FUSE. In `v2`, a strict **Two-Phase Commit** is enforced: upload $\rightarrow$ independent verification (file sizes, PyArrow metadata row counts) $\rightarrow$ manifest commit $\rightarrow$ scratch purge. |
| **6** | **Stop on insufficient disk space** | **PASS_WITH_LIMITATIONS** | **PASS** | `v1` checked `/content` free space $\ge 50$ GiB in Preflight. `v2` adds an explicit mid-flight scratch pre-check ($\ge 15$ GiB) immediately before extracting the 3.43 GB SQLite database. |
| **7** | **Do not print OAuth tokens or credentials** | **PASS** | **PASS** | Authentication is handled exclusively by Google Colab's native `drive.mount('/content/drive')` modal. No tokens, cookies, service keys, or secrets are handled, logged, or stored in code or environment variables. |
| **8** | **Use `/content` for temporary processing, not Drive FUSE** | **PASS** | **PASS** | All heavy I/O operations (7z decompression, DuckDB in-memory engine, temporary staging) execute on local NVMe `/content/scratch`. Only finalized immutable Parquet files are copied to Google Drive. |
| **9** | **Add explicit preflight checks and clear failure messages** | **DEFECTIVE** | **PASS** | `v1` suffered from silent failure masking (`> /dev/null` on 7z extraction) and unhandled Drive mount status. `v2` asserts `/content/drive/MyDrive` existence, uses `subprocess.run(..., check=True)`, and provides descriptive assertion diagnostics. |
| **10** | **Do not use theoretical or invented row counts** | **PASS** | **PASS** | All row counts ($N_{\text{raw}}, N_{\text{clean}}, N_{\text{dedup}}, N_{\text{conflicts}}, N_{\text{oob}}$) are computed at runtime directly via SQL aggregates against the extracted SQLite table. Zero hardcoded row counts are committed. |

---

## 3. Deep-Dive Risk Analysis & Failure Mitigation

### 3.1 Google Drive FUSE Operational Limits & Atomic Renames
- **Risk:** Google Drive mounted via `google.colab.drive` is a user-space virtual filesystem (FUSE). Operations like `os.replace` (POSIX atomic rename) can fail with `[Errno 95] Operation not supported`.
- **v1 Vulnerability:** Cell 8 used `os.replace(manifest_file + '.tmp', manifest_file)` without exception handling. If FUSE rejected the rename, the manifest update would fail after scratch files were already purged.
- **v2 Mitigation:** Implemented resilient atomic writing:
  ```python
  try:
      os.replace(manifest_tmp, manifest_file)
  except OSError:
      shutil.copy2(manifest_tmp, manifest_file)
      os.remove(manifest_tmp)
  ```

### 3.2 Network-Bound Hashing Latency & Timeouts
- **Risk:** Reading a ~500 MB Parquet file back through Google Drive FUSE to calculate a SHA-256 hash incurs network latency, potential throttling, and FUSE cache inconsistencies.
- **v1 Vulnerability:** Cell 8 opened `drive_clean_path` directly to compute `clean_sha256`.
- **v2 Mitigation:** Cell 8 in `v2` computes the SHA-256 checksum and measures byte size locally on `/content/scratch/clean_2026-10-05.parquet` before initiating the upload. Post-upload verification confirms byte size and verifies row counts using PyArrow metadata without re-reading the entire payload over the network.

### 3.3 Colab Session Disconnect & Non-Destructive Idempotency
- **Scenario A (Disconnect during 7z download):**
  - In `v2`, the partial file in `/content` will fail `EXPECTED_BYTES == 16077236568`. The pre-check cleanly re-downloads or copies from Drive if previously backed up.
- **Scenario B (Disconnect during DuckDB cleaning):**
  - Scratch files in `/content/scratch` are discarded on kernel restart. Google Drive remains untouched because the upload and manifest commit have not occurred.
- **Scenario C (Disconnect during Drive upload):**
  - Partial files on Drive will fail the post-upload size check (`os.path.getsize(drive_clean_path) == clean_bytes`). The manifest remains uncommitted (`status != 'COMMITTED'`). Re-running the pilot safely overwrites incomplete outputs.
- **Scenario D (Colab session restart after successful commit):**
  - The manifest records `status: "COMMITTED"`. Cell 10's recovery check verifies that `2026-10-05` is skipped and `2026-10-06` is designated as the next pending date.

### 3.4 Scratch Purge Containment
- **Risk:** Recursive deletion commands (`rm -rf` or `shutil.rmtree`) can accidentally purge unintended parent directories if path variables are misconfigured or empty.
- **Mitigation:** In both `v1` and `v2`, scratch cleanup avoids recursive directory deletion. It targets an explicit, enumerated list of exact temporary file paths:
  ```python
  for p_file in [LOCAL_DB, staged_clean, staged_conf, staged_oob]:
      if os.path.exists(p_file):
          os.remove(p_file)
  ```
  Neither `/content/delhi-dtc-bus-gtfs-rt-2026-10.7z` nor any directory under `DRIVE_ROOT` can be deleted by this cleanup routine.

---

## 4. Safety Audit Verdict

The pre-execution safety review concludes that `notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb` satisfies all 10 mandatory safety requirements, eliminates the 2 fatal runtime execution defects discovered in `v1`, and establishes a zero-risk environment for human operator execution in Google Colab.

