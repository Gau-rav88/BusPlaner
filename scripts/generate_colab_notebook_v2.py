#!/usr/bin/env python3
"""
Generate hardened Google Colab Notebook for M12.2.2:
notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb

Preserves original notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb untouched.
Implements all mandatory safety & hardening requirements:
1. Direct UTC-to-Asia/Kolkata timestamp conversion (no chaining).
2. Never silently reset manifest on JSON error; stops with explicit error.
3. Pre-extraction inspection of existing manifest and Drive partitions (never overwrite committed partition).
4. Hard stop before extraction if LOCAL_DB already exists; verifies source archive; removes -y flag.
5. Quintuple Parquet SHA-256 verification: computes and verifies digests for clean, conflicts, out-of-bounds, invalid-timestamps, and invalid-vehicle-ids files post-upload.
6. Independent PyArrow schema, exact Arrow data types, column order, and row counts validation across all 5 partitions.
7. Stage E01.4 invalid vehicle ID quarantine and Stage E01.5 invalid timestamp quarantine before Rule E02 ranking.
8. Manifest re-read and verification of COMMITTED entry before scratch deletion.
9. Strict preservation of existing dates, baseline data, databases, and archive.
10. Single-date extraction boundary (October 5 only).
11. Strict mathematical accounting conservation (delta = 0).
12. Single-quoted ATTACH path for 100% DuckDB 1.3.2 compatibility.
"""

import json
import os

NOTEBOOK_PATH = "notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb"

def to_source(text: str) -> list[str]:
    lines = text.strip("\n").split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1] + "\n"]

cell_0_md = r"""# Delhi DTC Bus Historical GPS Ingestion — Google Colab Pilot (M12.2.2 Hardened v2)

**Project:** Delhi Real-Time Bus Traffic Prediction & Journey Planner  
**Governing Specification:** PRD v3.0  
**Milestone:** 12.2.2 — Colab Notebook Pre-Execution Safety Review  
**Operating Status:** `DEGRADE`  
**Execution Status:** `READY_FOR_EXECUTION (Pending Human Approval)`  

---

### Overview & Hardened Production Guardrails
This notebook executes the **One-Day Controlled Historical GPS Ingestion Pilot** targeting service date **`2026-10-05`** on Google Colab Free-Tier.

- **Mandatory Hardened Guardrails (v2):**
  1. Direct UTC-to-Asia/Kolkata timestamp projection via `to_timestamp(ts) AT TIME ZONE 'Asia/Kolkata'` (no chained timezones).
  2. Strict manifest protection: halts with explicit `RuntimeError` on parse error without resetting or modifying existing manifests.
  3. Pre-execution safety stops: inspects existing manifest and Drive partitions before extracting; refuses to overwrite committed dates.
  4. Hard stop if `LOCAL_DB` already exists; verifies source archive existence and exact size; eliminates `-y` from extraction.
  5. Quintuple Parquet SHA-256 verification: computes and verifies digests for clean, conflicts, out-of-bounds, invalid-timestamps, and invalid-vehicle-ids files post-upload.
  6. Independent PyArrow schema, column order, & metadata validation across all 5 partitions with exact Arrow data type assertions.
  7. Pre-E02 multi-stage quarantine: isolates invalid vehicle IDs (Stage E01.4) and invalid timestamps (Stage E01.5) before ranking to prevent NULL partition clustering.
  8. Reopens and validates saved manifest on Drive before deleting any temporary scratch files.
  9. Strict date fencing: selectively extracts only `bus_movements_2026_10_05.db`.
  10. Exact closed mathematical conservation identity ($N_{\text{raw}} = N_{\text{clean}} + N_{\text{dedup}} + N_{\text{conflicts}} + N_{\text{oob}} + N_{\text{inv\_ts}} + N_{\text{inv\_vid}}$, $\Delta_{\text{accounting}} \equiv 0.0000$).
  11. 100% DuckDB 1.3.2 syntax compatibility using single-quoted path literals in `ATTACH`.
  12. Baseline-aware session restart recovery and idempotency test.

> **Operating Instructions:** Execute each cell sequentially from top to bottom. Do not extract all 31 days at once."""

cell_1_md = """## Phase 3 — Colab Preflight Hardware Benchmarking
Measures physical CPU, RAM, disk, OS, 7z, and DuckDB versions. Enforces >= 50 GiB disk and >= 11 GiB RAM."""

cell_2_code = """# Phase 3: Colab Preflight & Dependency Setup
!pip install -q duckdb pyarrow psutil tqdm
!apt-get install -q -y p7zip-full

import os, sys, shutil, psutil, subprocess, time, json, hashlib, sqlite3
import duckdb
import pyarrow.parquet as pq

print('=== COLAB PREFLIGHT SYSTEM BENCHMARK ===')
print(f'Python Version: {sys.version.split()[0]}')
print(f'DuckDB Version: {duckdb.__version__}')

# CPU Specs
cpu_info = subprocess.check_output("lscpu | grep 'Model name\\\\|CPU(s):'", shell=True).decode()
print(f'CPU Configuration:\\n{cpu_info.strip()}')

# RAM Specs
ram = psutil.virtual_memory()
ram_total_gib = ram.total / (1024**3)
ram_avail_gib = ram.available / (1024**3)
print(f'System RAM: Total={ram_total_gib:.2f} GiB | Available={ram_avail_gib:.2f} GiB')

# Disk Specs on /content
disk = shutil.disk_usage('/content')
disk_total_gib = disk.total / (1024**3)
disk_free_gib = disk.free / (1024**3)
print(f'Root Disk (/content): Total={disk_total_gib:.2f} GiB | Free={disk_free_gib:.2f} GiB')

# 7z Check
p7z_ver = subprocess.check_output('7z | head -n 2', shell=True).decode()
print(f'7-Zip Binary:\\n{p7z_ver.strip()}')

# Preflight Assertions
assert disk_free_gib >= 50.0, f'Insufficient disk space on /content: {disk_free_gib:.2f} GiB available, 50.0 GiB required'
assert ram_total_gib >= 11.0, f'Insufficient RAM: {ram_total_gib:.2f} GiB available, 11.0 GiB required'
print('\\nPREFLIGHT STATUS: PASS (Hardware & Libraries Verified)')"""

cell_3_md = """## Phase 2 — Google Drive Native Authentication & Folder Setup
Authenticates via native browser OAuth popup (zero credentials stored in notebook) and initializes directory structure."""

cell_4_code = """# Phase 2: Google Drive Native Mounting
from google.colab import drive
drive.mount('/content/drive')

assert os.path.exists('/content/drive/MyDrive'), 'Google Drive mount failed: /content/drive/MyDrive inaccessible!'

DRIVE_ROOT = '/content/drive/MyDrive/Delhi_Bus_Historical_Data'
SCRATCH_DIR = '/content/scratch'

SUBDIRS = [
    'source',
    'raw_manifests',
    'parquet',
    'quarantine',
    'metadata',
    'validation_reports'
]

for sub in SUBDIRS:
    os.makedirs(os.path.join(DRIVE_ROOT, sub), exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

print('Google Drive mounted and verified.')
print(f'Repository Base: {DRIVE_ROOT}')
print('Directories:', os.listdir(DRIVE_ROOT))"""

cell_5_md = """## Phase 4 — Archive Verification & Staging
Stages archive into Colab temporary storage (`/content`), verifies size (16,077,236,568 bytes), verifies non-solid block architecture (`Solid = -`), and backs up to Drive only after successful validation."""

cell_6_code = """# Phase 4: Download & Verify Pristine 7z Archive
ARCHIVE_URL = 'https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z'
LOCAL_ARCHIVE = '/content/delhi-dtc-bus-gtfs-rt-2026-10.7z'
DRIVE_ARCHIVE = os.path.join(DRIVE_ROOT, 'source', 'delhi-dtc-bus-gtfs-rt-2026-10.7z')
EXPECTED_BYTES = 16077236568

# 1. Acquire archive into local /content scratch
if os.path.exists(DRIVE_ARCHIVE) and os.path.getsize(DRIVE_ARCHIVE) == EXPECTED_BYTES:
    print('Found existing verified archive on Google Drive! Copying to Colab local scratch...')
    shutil.copy2(DRIVE_ARCHIVE, LOCAL_ARCHIVE)
elif not os.path.exists(LOCAL_ARCHIVE) or os.path.getsize(LOCAL_ARCHIVE) != EXPECTED_BYTES:
    print(f'Downloading 14.97 GiB archive from remote R2 (estimated duration: ~3.5 min)...')
    !curl -L -C - -o '{LOCAL_ARCHIVE}' '{ARCHIVE_URL}'
else:
    print('Archive already present in Colab local storage.')

# 2. Strict Size & Header Verification BEFORE Google Drive Backup
actual_size = os.path.getsize(LOCAL_ARCHIVE)
print(f'Verified Local Archive Size: {actual_size:,} bytes ({actual_size / (1024**3):.3f} GiB)')
assert actual_size == EXPECTED_BYTES, f'Archive size mismatch: got {actual_size}, expected {EXPECTED_BYTES}'

# Check 7z Listing & Non-Solid Mode
header_info = subprocess.check_output(f'7z l "{LOCAL_ARCHIVE}" | head -n 25', shell=True).decode()
print('\\n7z Archive Header:')
print(header_info)
assert 'Solid = -' in header_info, 'Archive must be non-solid for selective extraction!'
print('NON-SOLID COMPRESSION CONFIRMED: Selective extraction is safe and feasible.')

# 3. Backup to Google Drive only after local validation passes
if not os.path.exists(DRIVE_ARCHIVE) or os.path.getsize(DRIVE_ARCHIVE) != EXPECTED_BYTES:
    print('Backing up verified archive to Google Drive source folder (one-time step)...')
    shutil.copy2(LOCAL_ARCHIVE, DRIVE_ARCHIVE)
    assert os.path.getsize(DRIVE_ARCHIVE) == EXPECTED_BYTES, 'Drive backup incomplete!'
    print('Archive backup to Google Drive confirmed.')
else:
    print('Verified archive already exists on Google Drive.')"""

cell_7_md = r"""## Phase 5 — Controlled One-Day Pilot Ingestion (`2026-10-05`)
Selects the next unprocessed date (`2026-10-05`), inspects existing manifest and Drive partitions (halts if already COMMITTED or files exist), validates source archive, enforces hard stop if `LOCAL_DB` already exists, extracts only that single day without `-y`, validates SQLite B-Tree integrity via `sqlite3`, executes DuckDB cleaning pipeline:
1. Rule E01: Deduplicates exact duplicate records.
2. Stage E01.4: Isolates invalid/NULL/empty vehicle IDs into `invalid_vehicle_ids` quarantine before ranking, preventing NULL vehicle IDs from clustering as false conflicts or leaking to clean output.
3. Stage E01.5: Validates timestamps against acceptable October 2026 epoch boundaries ([1791133200, 1791246600], spanning 2026-10-04 17:00:00 UTC / 22:30 IST to 2026-10-06 00:30:00 UTC / 06:00 IST), and validates source `date` matches `2026-10-05`; quarantines invalid, implausible, or mismatched records into `invalid_timestamps.parquet`.
4. Rule E02: Deterministically ranks conflicting duplicate records on `(vehicle_id, timestamp)` strictly for valid records; quarantines rank > 1 to `conflicts.parquet`.
5. Rule E03: Quarantines out-of-bounds coordinates outside Delhi BBOX ([28.0, 29.2] lat, [76.5, 77.8] lng) to `out_of_bounds.parquet`.
6. Projects UTC Unix epoch to Asia/Kolkata (`timestamp_ist`) via direct `to_timestamp(ts) AT TIME ZONE 'Asia/Kolkata'`, derives calendar columns, extracts canonical trip ID prefix via safe pattern `^([0-9]+_[0-9]+_[0-9]+)`, and normalizes route IDs.
7. Verifies exact mathematical conservation ($N_{\text{raw}} = N_{\text{clean}} + N_{\text{dedup}} + N_{\text{conflicts}} + N_{\text{oob}} + N_{\text{inv\_ts}} + N_{\text{inv\_vid}}$, $\Delta = 0.0000$).
8. Exports 5 Parquet files locally, computes SHA-256 checksums and byte sizes.
9. Pre-Promotion Verification: Stages uploads to temporary `.uploading` files; independently verifies byte sizes, SHA-256 digests, PyArrow row counts, and exact Arrow data types on staged files before entering the atomic transaction scope.
10. Unified Transaction & Verified Rollback: Enters atomic transaction covering Parquet promotion and manifest commit. Promotes staging files to canonical partition paths and independently re-verifies all 5 canonical files directly on Drive (checksums, sizes, rows, and Arrow types). Stages and commits manifest with `.bak` snapshot backup. On ANY failure during promotion, canonical verification, manifest replacement, or post-commit readback, automatically rolls back all promoted files, restores manifest from `.bak`, verifies rollback state (or logs a recovery journal), and preserves scratch data. Scratch is purged ONLY after post-commit verification completely passes."""

cell_8_code = """# Phase 5: One-Day Ingestion Pilot for 2026-10-05 (Hardened Production Pipeline)
import os
import sys
import json
import time
import shutil
import hashlib
import sqlite3
import subprocess
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

# System Paths & Defaults (Established production paths on Google Colab)
if 'DRIVE_ROOT' not in globals() or not DRIVE_ROOT:
    DRIVE_ROOT = '/content/drive/MyDrive/Delhi_Bus_Historical_Data'
if 'SCRATCH_DIR' not in globals() or not SCRATCH_DIR:
    SCRATCH_DIR = '/content/scratch'
if 'LOCAL_ARCHIVE' not in globals() or not LOCAL_ARCHIVE:
    LOCAL_ARCHIVE = '/content/delhi-dtc-bus-gtfs-rt-2026-10.7z'

# Verify Google Drive Mounting (Colab Native Workflow)
# If targeting Colab Drive, verify mount exists; attempt mount if in Colab; halt clearly if absent.
if DRIVE_ROOT.startswith('/content/drive'):
    if not os.path.exists('/content/drive/MyDrive'):
        try:
            from google.colab import drive
            print("Google Drive not yet mounted. Attempting Colab native mount at /content/drive...")
            drive.mount('/content/drive')
        except (ImportError, Exception):
            pass
    assert os.path.exists('/content/drive/MyDrive'), (
        "CRITICAL PREFLIGHT HALT: Google Drive is not mounted! '/content/drive/MyDrive' does not exist.\\n"
        "Please execute Phase 2 (drive.mount('/content/drive')) or authorize Google Drive access before running Phase 5.\\n"
        "Cell 8 will NEVER silently write to a local substitute directory."
    )

assert os.path.exists(DRIVE_ROOT), (
    f"CRITICAL PREFLIGHT HALT: Established project directory {DRIVE_ROOT} does not exist on Google Drive!\\n"
    "Ensure '/content/drive/MyDrive/Delhi_Bus_Historical_Data' exists with required subdirectories."
)

# Verify & safely create established directories
ESTABLISHED_DRIVE_SUBDIRS = [
    'source',
    'raw_manifests',
    'parquet',
    'quarantine',
    'metadata',
    'validation_reports'
]
for sub in ESTABLISHED_DRIVE_SUBDIRS:
    os.makedirs(os.path.join(DRIVE_ROOT, sub), exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

PILOT_DATE = '2026-10-05'
DB_NAME = f'bus_movements_{PILOT_DATE.replace("-", "_")}.db'
LOCAL_DB = os.path.join(SCRATCH_DIR, DB_NAME)
EXPECTED_UNCOMPRESSED_BYTES = 3428802560
EXPECTED_ARCHIVE_BYTES = 16077236568
DRIVE_ARCHIVE = os.path.join(DRIVE_ROOT, 'source', 'delhi-dtc-bus-gtfs-rt-2026-10.7z')

# Archive Resolution: Verify local archive or Drive archive without re-downloading
if not os.path.exists(LOCAL_ARCHIVE) or os.path.getsize(LOCAL_ARCHIVE) != EXPECTED_ARCHIVE_BYTES:
    if os.path.exists(DRIVE_ARCHIVE) and os.path.getsize(DRIVE_ARCHIVE) == EXPECTED_ARCHIVE_BYTES:
        print(f"Local archive missing or partial at {LOCAL_ARCHIVE}. Copying verified archive from Google Drive...")
        shutil.copy2(DRIVE_ARCHIVE, LOCAL_ARCHIVE)
    else:
        candidate_scratch = os.path.join(SCRATCH_DIR, 'delhi-dtc-bus-gtfs-rt-2026-10.7z')
        if os.path.exists(candidate_scratch) and os.path.getsize(candidate_scratch) == EXPECTED_ARCHIVE_BYTES:
            LOCAL_ARCHIVE = candidate_scratch

# Parquet Schema Specifications & Schema Verifier
# (Defined at top-level so available unconditionally across every execution path)
schema_clean_spec = {
    'vehicle_id': 'string', 'lat': 'double', 'lng': 'double', 'speed_kmh': 'double',
    'route_id': 'string', 'trip_id_raw': 'string', 'trip_id_canonical': 'string',
    'timestamp_utc': 'int64', 'timestamp_ist': 'timestamp[us', 'service_date': 'date32[day]',
    'hour_ist': 'int64', 'minute_ist': 'int64', 'day_of_week': 'int64', 'is_weekend': 'bool'
}
schema_conf_spec = {
    'vehicle_id': 'string', 'timestamp': 'string', 'lat': 'string', 'lng': 'string',
    'speed': 'double', 'route_id': 'double', 'trip_id': 'string',
    'conflict_rank': 'int64', 'conflict_group_size': 'int64',
    'quarantine_reason': 'string', 'service_date': 'string'
}
schema_quar_spec = {
    'vehicle_id': 'string', 'lat': 'string', 'lng': 'string',
    'speed': 'double', 'route_id': 'double', 'trip_id': 'string', 'timestamp': 'string',
    'date': ('date32[day]', 'string'), 'time': 'string',
    'quarantine_reason': 'string', 'service_date': 'string'
}

def verify_arrow_schema(schema, expected_dict, schema_name):
    actual_cols = schema.names
    expected_cols = list(expected_dict.keys())
    assert actual_cols == expected_cols, f"{schema_name} column/order mismatch: got {actual_cols}, expected {expected_cols}"
    for field in schema:
        exp_type = expected_dict[field.name]
        act_type_str = str(field.type)
        if isinstance(exp_type, (list, tuple)):
            assert act_type_str in exp_type, f"{schema_name} col {field.name}: {act_type_str} not in {exp_type}"
        elif exp_type == 'timestamp[us':
            assert act_type_str.startswith('timestamp[us'), f"{schema_name} col {field.name}: {act_type_str} != {exp_type}"
        else:
            assert act_type_str == exp_type, f"{schema_name} col {field.name}: {act_type_str} != {exp_type}" 

# Acceptable Timestamp Boundaries for October 5, 2026 Service Day:
# As demonstrated across all five October 2026 baseline dates:
# The collection feed begins at ~23:30 IST on the prior calendar day (18:00 UTC).
# Transit service extends through 23:59:59 IST (18:30 UTC), with late-night service
# extending into early morning of the following day (up to 04:00-06:00 IST / 00:30 UTC).
# Bounded operational epoch window for 2026-10-05:
# MIN: 2026-10-04 17:00:00 UTC (22:30 IST on Oct 4) -> 1791133200
# MAX: 2026-10-06 00:30:00 UTC (06:00 IST on Oct 6) -> 1791246600
MIN_PLAUSIBLE_EPOCH = 1791133200
MAX_PLAUSIBLE_EPOCH = 1791246600

print(f'=== COMMENCING ONE-DAY PILOT: {PILOT_DATE} ===')
t_start = time.time()

# -------------------------------------------------------------------------
# Step 0: Pre-execution Safety Invariants & Manifest Inspection
# -------------------------------------------------------------------------
print('0. Inspecting existing manifest and Google Drive partitions...')
manifest_file = os.path.join(DRIVE_ROOT, 'raw_manifests', 'ingestion_manifest.json')
manifest_bak = manifest_file + '.bak'
manifest_tmp = manifest_file + '.tmp'
recovery_journal_path = os.path.join(DRIVE_ROOT, 'raw_manifests', f'recovery_journal_{PILOT_DATE}.json')

# 0.1 Check for Existing Recovery Journal (Hard Stop Before Any File Modification)
if os.path.exists(recovery_journal_path):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Existing recovery journal found at {recovery_journal_path}!\\n"
        "A prior attempt failed and left an unresolved recovery journal. Explicit manual inspection\\n"
        "and recovery are required before re-attempting ingestion. Halting without modifying any files."
    )

# 0.2 Check for Existing Backup or Temp Manifest Artifacts (Never Overwrite Recovery Artifacts)
if os.path.exists(manifest_bak):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Existing manifest backup found at {manifest_bak}!\\n"
        "An uncommitted or unrecovered manifest backup is present on Google Drive.\\n"
        "Manual inspection is required before proceeding. Halting without modifying any files."
    )
if os.path.exists(manifest_tmp):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Existing temporary manifest found at {manifest_tmp}!\\n"
        "A lingering temporary manifest from an aborted session is present on Google Drive.\\n"
        "Manual inspection is required before proceeding. Halting without modifying any files."
    )

drive_pq_dir = os.path.join(DRIVE_ROOT, 'parquet', f'service_date={PILOT_DATE}')
drive_quar_dir = os.path.join(DRIVE_ROOT, 'quarantine', f'service_date={PILOT_DATE}')
drive_clean_path = os.path.join(drive_pq_dir, 'data.parquet')
drive_conf_path = os.path.join(drive_quar_dir, 'conflicts.parquet')
drive_oob_path = os.path.join(drive_quar_dir, 'out_of_bounds.parquet')
drive_inv_ts_path = os.path.join(drive_quar_dir, 'invalid_timestamps.parquet')
drive_inv_vid_path = os.path.join(drive_quar_dir, 'invalid_vehicle_ids.parquet')

# Staging upload paths (with .uploading suffix)
drive_clean_staging = drive_clean_path + '.uploading'
drive_conf_staging = drive_conf_path + '.uploading'
drive_oob_staging = drive_oob_path + '.uploading'
drive_inv_ts_staging = drive_inv_ts_path + '.uploading'
drive_inv_vid_staging = drive_inv_vid_path + '.uploading'

# If any stale .uploading files remain from an uncommitted crashed session, clean them up safely:
for st_path in [drive_clean_staging, drive_conf_staging, drive_oob_staging, drive_inv_ts_staging, drive_inv_vid_staging]:
    if os.path.exists(st_path):
        try: os.remove(st_path)
        except OSError: pass

manifest = {}
pre_existing_partitions = {}
if os.path.exists(manifest_file):
    try:
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)
        pre_existing_partitions = json.loads(json.dumps(manifest.get('partitions', {})))
    except Exception as exc:
        raise RuntimeError(
            f"CRITICAL SAFETY STOP: Failed to parse existing manifest at {manifest_file}!\\n"
            f"Preserving original file untouched to prevent data corruption. Error: {exc}"
        )
    
    p_info = manifest.get('partitions', {}).get(PILOT_DATE)
    if p_info and p_info.get('status') == 'COMMITTED':
        raise RuntimeError(
            f"CRITICAL SAFETY STOP: Partition for {PILOT_DATE} is already marked COMMITTED in manifest!\\n"
            f"Committed at: {p_info.get('committed_at')}, SHA-256: {p_info.get('sha256_clean', p_info.get('sha256'))}\\n"
            "Refusing to overwrite an already committed partition without an explicit approved recovery procedure."
        )

for p_desc, p_path in [
    ('Clean Parquet', drive_clean_path),
    ('Conflicts Parquet', drive_conf_path),
    ('Out-of-Bounds Parquet', drive_oob_path),
    ('Invalid Timestamps Parquet', drive_inv_ts_path),
    ('Invalid Vehicle IDs Parquet', drive_inv_vid_path)
]:
    if os.path.exists(p_path):
        raise RuntimeError(
            f"CRITICAL SAFETY STOP: {p_desc} already exists on Drive at {p_path}!\\n"
            "Refusing to overwrite without an explicit approved recovery procedure."
        )

# Pre-extraction Disk Check
free_scratch_gib = shutil.disk_usage(SCRATCH_DIR).free / (1024**3)
print(f'   Scratch disk space: {free_scratch_gib:.2f} GiB available')
assert free_scratch_gib >= 15.0, f'Insufficient scratch disk space: {free_scratch_gib:.2f} GiB available, 15.0 GiB required'

# -------------------------------------------------------------------------
# Step 1: Selective Decompression with Strict Overwrite and Archive Protections
# -------------------------------------------------------------------------
print(f'1. Selectively extracting {DB_NAME} from 7z archive...')

# 1.1 Verify Source Archive Exists & Exact Size (Never Re-download)
if not os.path.exists(LOCAL_ARCHIVE):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Source archive missing at {LOCAL_ARCHIVE}!\\n"
        f"Also checked Drive source folder at {DRIVE_ARCHIVE}.\\n"
        "Run Phase 4 or ensure archive is staged before proceeding. Will NOT re-download."
    )
actual_archive_bytes = os.path.getsize(LOCAL_ARCHIVE)
if actual_archive_bytes != EXPECTED_ARCHIVE_BYTES:
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Source archive size mismatch at {LOCAL_ARCHIVE}!\\n"
        f"Got {actual_archive_bytes:,} bytes, expected {EXPECTED_ARCHIVE_BYTES:,} bytes."
    )

# 1.2 Hard Stop If Local SQLite Database Already Exists (No Overwrite Allowed)
if os.path.exists(LOCAL_DB):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Local SQLite database already exists at {LOCAL_DB}!\\n"
        "Refusing to overwrite an existing extraction without an explicit approved recovery procedure."
    )

# 1.3 Selective Extraction Without -y Flag (Safe Extraction)
subprocess.run(['7z', 'e', f'-o{SCRATCH_DIR}', LOCAL_ARCHIVE, DB_NAME], check=True)
assert os.path.exists(LOCAL_DB), f'Extraction failed: {LOCAL_DB} not found!'
db_size = os.path.getsize(LOCAL_DB)
print(f'   Extracted SQLite size: {db_size:,} bytes ({db_size / (1024**3):.3f} GiB)')
assert db_size == EXPECTED_UNCOMPRESSED_BYTES, f'Extracted size mismatch: got {db_size}, expected {EXPECTED_UNCOMPRESSED_BYTES}'

# -------------------------------------------------------------------------
# Step 2: SQLite B-Tree Integrity Check via python sqlite3
# -------------------------------------------------------------------------
print('2. Validating SQLite file integrity via sqlite3 PRAGMA integrity_check...')
con_sql = sqlite3.connect(LOCAL_DB)
integ_res = con_sql.execute('PRAGMA integrity_check;').fetchall()
con_sql.close()
print(f'   SQLite integrity: {integ_res[0][0]}')
assert integ_res[0][0] == 'ok', f'SQLite integrity check failed: {integ_res}'

# -------------------------------------------------------------------------
# Step 3: Vectorized DuckDB Ingestion & Cleaning Pipeline (Rules E01-E03)
# -------------------------------------------------------------------------
print('3. Running DuckDB cleaning pipeline with Rules E01-E03...')
con = duckdb.connect(database=':memory:')
con.execute("PRAGMA max_memory = '3.0GB';")
con.execute("PRAGMA threads = 2;")
con.execute("LOAD sqlite;")
# Single quotes around path for 100% DuckDB 1.3.2 parser compatibility
con.execute(f"ATTACH '{LOCAL_DB}' AS raw_db (TYPE SQLITE);")

# Substep 3.1: Raw Observations
n_raw = con.execute('SELECT COUNT(*) FROM raw_db.vehicle_feed').fetchone()[0]
print(f'   Raw Observations: {n_raw:,}')

# Substep 3.2: Exact Duplicate Deduplication (Rule E01)
con.execute('''
    CREATE TEMP TABLE stage_e01 AS
    SELECT DISTINCT vehicle_id, lat, lng, speed, route_id, trip_id, timestamp, date, time
    FROM raw_db.vehicle_feed;
''')
n_distinct = con.execute('SELECT COUNT(*) FROM stage_e01').fetchone()[0]
n_dedup = n_raw - n_distinct
print(f'   Rule E01 Deduplication: Dropped {n_dedup:,} exact duplicates ({n_distinct:,} distinct)')

# Substep 3.2.1: Quarantine Invalid/NULL Vehicle IDs (Stage E01.4)
con.execute(f'''
    CREATE TEMP TABLE invalid_vehicle_ids AS
    SELECT *, 'E00_INVALID_OR_NULL_VEHICLE_ID' as quarantine_reason, '{PILOT_DATE}' as service_date
    FROM stage_e01
    WHERE vehicle_id IS NULL OR TRIM(vehicle_id) = '';
''')
n_inv_vid = con.execute('SELECT COUNT(*) FROM invalid_vehicle_ids').fetchone()[0]
print(f'   Stage E01.4 Invalid Vehicle IDs: Quarantining {n_inv_vid:,} records (NULL or empty string)')

# Substep 3.2.2: Quarantine Invalid/Implausible Timestamps & Missing/Mismatched Dates (Stage E01.5)
con.execute(f'''
    CREATE TEMP TABLE invalid_timestamps AS
    SELECT *,
        CASE 
            WHEN timestamp IS NULL OR TRY_CAST(timestamp AS BIGINT) IS NULL OR TRY_CAST(timestamp AS BIGINT) <= 0
                THEN 'E00_INVALID_OR_NULL_TIMESTAMP'
            WHEN TRY_CAST(timestamp AS BIGINT) < {MIN_PLAUSIBLE_EPOCH} OR TRY_CAST(timestamp AS BIGINT) > {MAX_PLAUSIBLE_EPOCH}
                THEN 'E00_IMPLAUSIBLE_TIMESTAMP_OUT_OF_BOUNDS'
            WHEN date IS NULL OR TRIM(CAST(date AS VARCHAR)) = '' OR TRY_CAST(date AS DATE) IS NULL
                THEN 'E00_MISSING_OR_NULL_SERVICE_DATE'
            WHEN TRY_CAST(date AS DATE) != TRY_CAST('{PILOT_DATE}' AS DATE)
                THEN 'E00_MISMATCHED_SERVICE_DATE'
            ELSE 'E00_TEMPORAL_ANOMALY'
        END as quarantine_reason,
        '{PILOT_DATE}' as service_date
    FROM stage_e01
    WHERE (vehicle_id IS NOT NULL AND TRIM(vehicle_id) != '')
      AND (
          timestamp IS NULL
          OR TRY_CAST(timestamp AS BIGINT) IS NULL 
          OR TRY_CAST(timestamp AS BIGINT) <= 0
          OR TRY_CAST(timestamp AS BIGINT) < {MIN_PLAUSIBLE_EPOCH}
          OR TRY_CAST(timestamp AS BIGINT) > {MAX_PLAUSIBLE_EPOCH}
          OR date IS NULL
          OR TRIM(CAST(date AS VARCHAR)) = ''
          OR TRY_CAST(date AS DATE) IS NULL
          OR TRY_CAST(date AS DATE) != TRY_CAST('{PILOT_DATE}' AS DATE)
      );
''')
n_inv_ts = con.execute('SELECT COUNT(*) FROM invalid_timestamps').fetchone()[0]
print(f'   Stage E01.5 Invalid Timestamps & Mismatched Dates: Quarantining {n_inv_ts:,} records')

# Substep 3.2.3: Valid Records for E02 Ranking
con.execute(f'''
    CREATE TEMP TABLE stage_e01_valid AS
    SELECT *
    FROM stage_e01
    WHERE (vehicle_id IS NOT NULL AND TRIM(vehicle_id) != '')
      AND (timestamp IS NOT NULL AND TRY_CAST(timestamp AS BIGINT) IS NOT NULL AND TRY_CAST(timestamp AS BIGINT) > 0)
      AND (TRY_CAST(timestamp AS BIGINT) >= {MIN_PLAUSIBLE_EPOCH} AND TRY_CAST(timestamp AS BIGINT) <= {MAX_PLAUSIBLE_EPOCH})
      AND (date IS NOT NULL AND TRIM(CAST(date AS VARCHAR)) != '' AND TRY_CAST(date AS DATE) IS NOT NULL AND TRY_CAST(date AS DATE) = TRY_CAST('{PILOT_DATE}' AS DATE));
''')

# Substep 3.3: Conflicting Duplicate Quarantine (Rule E02)
con.execute('''
    CREATE TEMP TABLE stage_ranked AS
    SELECT vehicle_id, lat, lng, speed, route_id, trip_id, timestamp, date, time,
           ROW_NUMBER() OVER (PARTITION BY vehicle_id, timestamp ORDER BY speed DESC, lat, lng) as conflict_rank,
           COUNT(*) OVER (PARTITION BY vehicle_id, timestamp) as conflict_group_size
    FROM stage_e01_valid;
''')

con.execute(f'''
    CREATE TEMP TABLE stage_conflicts AS
    SELECT 
        vehicle_id,
        timestamp,
        lat,
        lng,
        speed,
        route_id,
        trip_id,
        conflict_rank,
        conflict_group_size,
        'E02_CONFLICTING_TIMESTAMP_POSITION' as quarantine_reason,
        '{PILOT_DATE}' as service_date
    FROM stage_ranked
    WHERE conflict_rank > 1;
''')
n_conflicts = con.execute('SELECT COUNT(*) FROM stage_conflicts').fetchone()[0]
print(f'   Rule E02 Conflict Isolation: Quarantining {n_conflicts:,} conflicting observations')
con.execute('CREATE TEMP TABLE stage_e02 AS SELECT * EXCLUDE (conflict_rank, conflict_group_size) FROM stage_ranked WHERE conflict_rank = 1;')

# Substep 3.4: Spatial Bounding Box Filter (Rule E03: Lat [28.0, 29.2], Lng [76.5, 77.8])
con.execute(f'''
    CREATE TEMP TABLE out_of_bounds AS
    SELECT *, 'E03_OUT_OF_BOUNDS_COORDINATE' as quarantine_reason, '{PILOT_DATE}' as service_date
    FROM stage_e02
    WHERE TRY_CAST(lat AS DOUBLE) < 28.0 OR TRY_CAST(lat AS DOUBLE) > 29.2
       OR TRY_CAST(lng AS DOUBLE) < 76.5 OR TRY_CAST(lng AS DOUBLE) > 77.8
       OR TRY_CAST(lat AS DOUBLE) IS NULL OR TRY_CAST(lng AS DOUBLE) IS NULL;
''')
n_oob = con.execute('SELECT COUNT(*) FROM out_of_bounds').fetchone()[0]
print(f'   Rule E03 Spatial BBOX Filter: Quarantining {n_oob:,} out-of-bounds observations')

# Substep 3.5: Clean Output with CTE-based Direct Asia/Kolkata Projection & Safe Regex
con.execute('''
    CREATE TEMP TABLE clean_final AS
    WITH projected AS (
        SELECT
            vehicle_id,
            TRY_CAST(lat AS DOUBLE) AS lat,
            TRY_CAST(lng AS DOUBLE) AS lng,
            TRY_CAST(speed AS DOUBLE) AS speed_kmh,
            CASE 
                WHEN TRY_CAST(route_id AS DOUBLE) IS NOT NULL 
                THEN CAST(CAST(TRY_CAST(route_id AS DOUBLE) AS BIGINT) AS VARCHAR)
                ELSE CAST(route_id AS VARCHAR)
            END AS route_id,
            trip_id AS trip_id_raw,
            REGEXP_EXTRACT(trip_id, '^([0-9]+_[0-9]+_[0-9]+)') AS trip_id_canonical,
            TRY_CAST(timestamp AS BIGINT) AS timestamp_utc,
            to_timestamp(TRY_CAST(timestamp AS BIGINT)) AT TIME ZONE 'Asia/Kolkata' AS timestamp_ist,
            TRY_CAST(date AS DATE) AS service_date
        FROM stage_e02
        WHERE TRY_CAST(lat AS DOUBLE) >= 28.0 AND TRY_CAST(lat AS DOUBLE) <= 29.2
          AND TRY_CAST(lng AS DOUBLE) >= 76.5 AND TRY_CAST(lng AS DOUBLE) <= 77.8
    )
    SELECT
        vehicle_id,
        lat,
        lng,
        speed_kmh,
        route_id,
        trip_id_raw,
        trip_id_canonical,
        timestamp_utc,
        timestamp_ist,
        service_date,
        EXTRACT(hour FROM timestamp_ist)::BIGINT AS hour_ist,
        EXTRACT(minute FROM timestamp_ist)::BIGINT AS minute_ist,
        DAYOFWEEK(timestamp_ist)::BIGINT AS day_of_week,
        CASE WHEN DAYOFWEEK(timestamp_ist) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
    FROM projected;
''')
n_clean = con.execute('SELECT COUNT(*) FROM clean_final').fetchone()[0]
print(f'   Clean Retained Observations: {n_clean:,}')

# -------------------------------------------------------------------------
# Step 4: Strict Mathematical Conservation Verification
# -------------------------------------------------------------------------
delta = n_raw - (n_clean + n_dedup + n_conflicts + n_oob + n_inv_ts + n_inv_vid)
print('\\n4. Mathematical Balance Check:')
print(f'   N_raw ({n_raw:,}) = N_clean ({n_clean:,}) + N_dedup ({n_dedup:,}) + N_conf ({n_conflicts:,}) + N_oob ({n_oob:,}) + N_inv_ts ({n_inv_ts:,}) + N_inv_vid ({n_inv_vid:,})')
print(f'   Accounting Delta: {delta} (Strict Zero Tolerance)')
assert delta == 0, f'Conservation violation on {PILOT_DATE}! Delta={delta}'

# -------------------------------------------------------------------------
# Step 5: Export Staged Parquet in Local Scratch Space
# -------------------------------------------------------------------------
print('\\n5. Exporting staged Parquet partitions in local scratch space...')
staged_clean = os.path.join(SCRATCH_DIR, f'clean_{PILOT_DATE}.parquet')
staged_conf = os.path.join(SCRATCH_DIR, f'conflicts_{PILOT_DATE}.parquet')
staged_oob = os.path.join(SCRATCH_DIR, f'oob_{PILOT_DATE}.parquet')
staged_inv_ts = os.path.join(SCRATCH_DIR, f'inv_ts_{PILOT_DATE}.parquet')
staged_inv_vid = os.path.join(SCRATCH_DIR, f'inv_vid_{PILOT_DATE}.parquet')

con.execute(f"COPY clean_final TO '{staged_clean}' (FORMAT PARQUET, COMPRESSION ZSTD);")
con.execute(f"COPY stage_conflicts TO '{staged_conf}' (FORMAT PARQUET, COMPRESSION ZSTD);")
con.execute(f"COPY out_of_bounds TO '{staged_oob}' (FORMAT PARQUET, COMPRESSION ZSTD);")
con.execute(f"COPY invalid_timestamps TO '{staged_inv_ts}' (FORMAT PARQUET, COMPRESSION ZSTD);")
con.execute(f"COPY invalid_vehicle_ids TO '{staged_inv_vid}' (FORMAT PARQUET, COMPRESSION ZSTD);")
con.close()

# -------------------------------------------------------------------------
# Step 6: Compute SHA-256 Checksums Locally on Scratch Files
# -------------------------------------------------------------------------
def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192 * 1024):
            h.update(chunk)
    return h.hexdigest()

sha_clean_local = compute_sha256(staged_clean)
sha_conf_local = compute_sha256(staged_conf)
sha_oob_local = compute_sha256(staged_oob)
sha_inv_ts_local = compute_sha256(staged_inv_ts)
sha_inv_vid_local = compute_sha256(staged_inv_vid)

size_clean_local = os.path.getsize(staged_clean)
size_conf_local = os.path.getsize(staged_conf)
size_oob_local = os.path.getsize(staged_oob)
size_inv_ts_local = os.path.getsize(staged_inv_ts)
size_inv_vid_local = os.path.getsize(staged_inv_vid)

print(f'   Local Clean Parquet:       {size_clean_local:,} bytes | SHA-256: {sha_clean_local}')
print(f'   Local Conflicts:           {size_conf_local:,} bytes | SHA-256: {sha_conf_local}')
print(f'   Local Out-of-Bounds:       {size_oob_local:,} bytes | SHA-256: {sha_oob_local}')
print(f'   Local Invalid Timestamps:  {size_inv_ts_local:,} bytes | SHA-256: {sha_inv_ts_local}')
print(f'   Local Invalid Vehicle IDs: {size_inv_vid_local:,} bytes | SHA-256: {sha_inv_vid_local}')

# -------------------------------------------------------------------------
# Step 7: Recoverable Upload to Google Drive via Staging Files (.uploading)
# -------------------------------------------------------------------------
print('\\n7. Uploading partitions to Google Drive staging paths (.uploading)...')
os.makedirs(drive_pq_dir, exist_ok=True)
os.makedirs(drive_quar_dir, exist_ok=True)

upload_items = [
    ('Clean Parquet', staged_clean, drive_clean_staging, drive_clean_path, size_clean_local, sha_clean_local, n_clean),
    ('Conflicts Parquet', staged_conf, drive_conf_staging, drive_conf_path, size_conf_local, sha_conf_local, n_conflicts),
    ('Out-of-Bounds Parquet', staged_oob, drive_oob_staging, drive_oob_path, size_oob_local, sha_oob_local, n_oob),
    ('Invalid Timestamps Parquet', staged_inv_ts, drive_inv_ts_staging, drive_inv_ts_path, size_inv_ts_local, sha_inv_ts_local, n_inv_ts),
    ('Invalid Vehicle IDs Parquet', staged_inv_vid, drive_inv_vid_staging, drive_inv_vid_path, size_inv_vid_local, sha_inv_vid_local, n_inv_vid)
]

try:
    for p_name, local_p, staging_p, final_p, exp_size, exp_sha, exp_rows in upload_items:
        shutil.copy2(local_p, staging_p)
except Exception as exc:
    print(f'   Upload interrupted: {exc}. Cleaning up partial staging files on Drive...')
    for _, _, staging_p, _, _, _, _ in upload_items:
        if os.path.exists(staging_p):
            try: os.remove(staging_p)
            except OSError: pass
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Parquet upload to Drive failed: {exc}!\\n"
        "Partial staging files cleaned up. Canonical partitions were untouched. Scratch files preserved."
    )

# -------------------------------------------------------------------------
# Step 8: Independent Post-Upload Verification on Staged Files BEFORE Promotion
# -------------------------------------------------------------------------
print('8. Running independent post-upload verification on staged files (.uploading)...')
try:
    # 8.1 Existence & Byte Size Checks
    for p_name, local_p, staging_p, final_p, exp_size, exp_sha, exp_rows in upload_items:
        assert os.path.exists(staging_p), f"Staged upload missing: {staging_p}"
        act_size = os.path.getsize(staging_p)
        assert act_size == exp_size, f"{p_name} size mismatch: got {act_size}, expected {exp_size}"

    # 8.2 SHA-256 Checksum Verification for ALL FIVE Files
    for p_name, local_p, staging_p, final_p, exp_size, exp_sha, exp_rows in upload_items:
        act_sha = compute_sha256(staging_p)
        assert act_sha == exp_sha, f"{p_name} SHA-256 mismatch!\\nExpected: {exp_sha}\\nGot: {act_sha}"
    print('   SHA-256 checksums verified for all 5 staged Parquet files.')

    # 8.3 PyArrow Row Counts Verification
    for p_name, local_p, staging_p, final_p, exp_size, exp_sha, exp_rows in upload_items:
        meta = pq.read_metadata(staging_p)
        assert meta.num_rows == exp_rows, f"{p_name} row count mismatch: got {meta.num_rows}, expected {exp_rows}"
    print(f'   PyArrow row counts verified: clean={n_clean:,}, conflicts={n_conflicts:,}, oob={n_oob:,}, inv_ts={n_inv_ts:,}, inv_vid={n_inv_vid:,}')

    # 8.4 PyArrow Exact Schema, Column Order & Data Type Verification for ALL FIVE Files
    verify_arrow_schema(pq.read_schema(drive_clean_staging), schema_clean_spec, 'Staged Clean Parquet')
    clean_table_staged = pq.read_table(drive_clean_staging)
    assert clean_table_staged['service_date'].null_count == 0, "NULL service_date detected in staged clean Parquet!"
    verify_arrow_schema(pq.read_schema(drive_conf_staging), schema_conf_spec, 'Staged Conflicts Parquet')
    for q_name, q_staging in [
        ('Staged Out-of-Bounds Parquet', drive_oob_staging),
        ('Staged Invalid Timestamps Parquet', drive_inv_ts_staging),
        ('Staged Invalid Vehicle IDs Parquet', drive_inv_vid_staging)
    ]:
        verify_arrow_schema(pq.read_schema(q_staging), schema_quar_spec, q_name)
    print('   Pre-promotion staged verification PASSED: all 5 staging files validated.')

except Exception as exc:
    print(f'   Post-upload verification on staging files failed: {exc}. Cleaning up staging files on Drive...')
    for _, _, staging_p, _, _, _, _ in upload_items:
        if os.path.exists(staging_p):
            try: os.remove(staging_p)
            except OSError: pass
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Post-upload verification on staging files failed: {exc}!\\n"
        "Staging files cleaned up. Canonical partitions were untouched. Manifest was NOT updated. Scratch files preserved."
    )

# -------------------------------------------------------------------------
# Step 9: Unified Atomic Transaction: Promotion, Canonical Verification & Safe Manifest Commit
# -------------------------------------------------------------------------
print('\\n=== COMMENCING UNIFIED TRANSACTION: PROMOTION & MANIFEST COMMIT ===')
manifest_existed_initially = os.path.exists(manifest_file)
if os.path.exists(manifest_bak):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Pre-transaction check failed! Existing backup manifest found at {manifest_bak}!\\n"
        "Never overwrite recovery artifacts. Halting."
    )
if os.path.exists(manifest_tmp):
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Pre-transaction check failed! Existing temporary manifest found at {manifest_tmp}!\\n"
        "Never overwrite recovery artifacts. Halting."
    )

promoted_canonical_files = []
manifest_bak_created = False
manifest_tmp_created = False
manifest_replaced = False
sha_orig = compute_sha256(manifest_file) if (manifest_existed_initially and os.path.exists(manifest_file)) else None
sha_bak = None

def execute_transaction_rollback(failure_reason, original_exc):
    print(f"\\n   >>> INITIATING TRANSACTION ROLLBACK (Trigger: {failure_reason}) <<<")
    rollback_errors = []

    # 1. Remove only the canonical files created by this attempt
    for f_path in promoted_canonical_files:
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
                assert not os.path.exists(f_path), f"Canonical file still exists after removal: {f_path}"
                print(f"       [ROLLBACK] Removed uncommitted canonical file: {f_path}")
            except Exception as e:
                rollback_errors.append(f"Failed removing canonical file {f_path}: {e}")

    # 2. Clean up any remaining .uploading staging files
    for _, _, staging_p, _, _, _, _ in upload_items:
        if os.path.exists(staging_p):
            try:
                os.remove(staging_p)
                print(f"       [ROLLBACK] Cleaned up staging file: {staging_p}")
            except Exception as e:
                rollback_errors.append(f"Failed removing staging file {staging_p}: {e}")

    # 3. Strengthened Manifest Rollback:
    # Handle both initial existence cases safely
    if manifest_existed_initially:
        # If manifest was replaced in this transaction (or damaged), it must be restored from backup
        if manifest_replaced:
            if manifest_bak_created and os.path.exists(manifest_bak):
                try:
                    shutil.copy2(manifest_bak, manifest_file)
                    assert os.path.exists(manifest_file), "Restored manifest missing!"
                    restored_sha = compute_sha256(manifest_file)
                    assert restored_sha == sha_bak, f"Restored manifest SHA-256 mismatch! Got {restored_sha}, expected {sha_bak}"
                    assert sha_orig is None or restored_sha == sha_orig, f"Restored manifest differs from original! {restored_sha} vs {sha_orig}"
                    print(f"       [ROLLBACK] Restored and verified original manifest from backup: {manifest_file}")
                except Exception as e:
                    rollback_errors.append(f"Failed restoring/verifying manifest from backup: {e}")
            else:
                rollback_errors.append(f"Manifest was replaced but backup {manifest_bak} is missing to restore original!")
        else:
            # Manifest was NOT replaced. Verify original manifest still matches sha_orig
            if sha_orig and os.path.exists(manifest_file):
                current_sha = compute_sha256(manifest_file)
                if current_sha != sha_orig:
                    # Original manifest was damaged despite manifest_replaced=False (e.g. torn write on replace)
                    if manifest_bak_created and os.path.exists(manifest_bak):
                        try:
                            shutil.copy2(manifest_bak, manifest_file)
                            restored_sha = compute_sha256(manifest_file)
                            assert restored_sha == sha_orig, f"Restored manifest mismatch: {restored_sha} vs {sha_orig}"
                            print(f"       [ROLLBACK] Restored damaged manifest from backup: {manifest_file}")
                        except Exception as e:
                            rollback_errors.append(f"Failed restoring damaged manifest from backup: {e}")
                    else:
                        rollback_errors.append(f"Manifest damaged and backup {manifest_bak} missing or invalid!")
                else:
                    print(f"       [ROLLBACK] Original manifest untouched and verified intact (SHA-256: {current_sha[:16]}...).")
    else:
        # Manifest did NOT exist initially, but was created/replaced in this transaction.
        # Rollback must remove the newly created manifest and verify it no longer exists!
        if os.path.exists(manifest_file):
            try:
                os.remove(manifest_file)
                assert not os.path.exists(manifest_file), f"Manifest file still exists after removal: {manifest_file}"
                print(f"       [ROLLBACK] Removed newly created manifest (did not exist before transaction): {manifest_file}")
            except Exception as e:
                rollback_errors.append(f"Failed removing newly created manifest {manifest_file}: {e}")

    # 4. Clean up temporary manifest created by current attempt, if created and not already replaced
    if manifest_tmp_created and os.path.exists(manifest_tmp):
        try:
            os.remove(manifest_tmp)
            print(f"       [ROLLBACK] Cleaned up temporary manifest created by current attempt: {manifest_tmp}")
        except Exception as e:
            rollback_errors.append(f"Failed removing temporary manifest {manifest_tmp}: {e}")

    # 5. Rollback Verification Check: verify no uncommitted canonical files exist
    for f_path in [drive_clean_path, drive_conf_path, drive_oob_path, drive_inv_ts_path, drive_inv_vid_path]:
        if os.path.exists(f_path):
            rollback_errors.append(f"Canonical file {f_path} still exists on Drive after rollback!")

    # Verify manifest state matches initial existence
    if not manifest_existed_initially and os.path.exists(manifest_file):
        rollback_errors.append(f"Manifest file {manifest_file} still exists after rollback when it did not exist initially!")
    if manifest_existed_initially and not os.path.exists(manifest_file):
        rollback_errors.append(f"Original manifest {manifest_file} missing after rollback!")

    # 6. If rollback encountered errors, write recovery journal and preserve .bak and .tmp
    if rollback_errors:
        journal_data = {
            "pilot_date": PILOT_DATE,
            "failure_reason": str(failure_reason),
            "original_exception": str(original_exc),
            "promoted_canonical_files": promoted_canonical_files,
            "manifest_replaced": manifest_replaced,
            "manifest_existed_initially": manifest_existed_initially,
            "manifest_bak_created": manifest_bak_created,
            "manifest_tmp_created": manifest_tmp_created,
            "rollback_errors": rollback_errors,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        try:
            with open(recovery_journal_path, 'w') as jf:
                json.dump(journal_data, jf, indent=2)
            print(f"       [CRITICAL] Preserved recovery journal at {recovery_journal_path}")
        except Exception as je:
            print(f"       [CRITICAL] Failed writing recovery journal: {je}")
        raise RuntimeError(
            f"CRITICAL SAFETY STOP: Transaction failed AND rollback encountered errors!\\n"
            f"Rollback errors: {rollback_errors}\\n"
            f"Recovery journal: {recovery_journal_path}. Backup and temp files preserved. Scratch preserved."
        )
    else:
        # On clean rollback, if manifest was restored from .bak, clean up .bak
        if manifest_bak_created and os.path.exists(manifest_bak):
            try: os.remove(manifest_bak)
            except OSError: pass
        print("       [OK] Transaction rollback clean and verified: uncommitted files removed, manifest state restored, scratch preserved.")

try:
    # 9.1 Promote verified staging files to canonical target paths
    print('   Promoting verified staging files to final partition paths...')
    for p_name, local_p, staging_p, final_p, exp_size, exp_sha, exp_rows in upload_items:
        os.replace(staging_p, final_p)
        promoted_canonical_files.append(final_p)
        assert os.path.exists(final_p) and os.path.getsize(final_p) == exp_size, f"Promotion failed for {p_name}"
    print('   All 5 partitions promoted to canonical Drive paths.')

    # 9.2 Independent Verification on CANONICAL Drive Files (Recalculate SHA-256, sizes, rows, Arrow types)
    print('   Running independent post-promotion verification on canonical Drive files...')
    for p_name, local_p, staging_p, final_p, exp_size, exp_sha, exp_rows in upload_items:
        assert os.path.exists(final_p), f"Canonical file missing: {final_p}"
        act_size = os.path.getsize(final_p)
        assert act_size == exp_size, f"Canonical {p_name} size mismatch: got {act_size}, expected {exp_size}"
        act_sha = compute_sha256(final_p)
        assert act_sha == exp_sha, f"Canonical {p_name} SHA-256 mismatch!\\nExpected: {exp_sha}\\nGot: {act_sha}"
        meta = pq.read_metadata(final_p)
        assert meta.num_rows == exp_rows, f"Canonical {p_name} row count mismatch: got {meta.num_rows}, expected {exp_rows}"

    verify_arrow_schema(pq.read_schema(drive_clean_path), schema_clean_spec, 'Canonical Clean Parquet')
    clean_table_canon = pq.read_table(drive_clean_path)
    assert clean_table_canon['service_date'].null_count == 0, "NULL service_date detected in canonical clean Parquet!"
    verify_arrow_schema(pq.read_schema(drive_conf_path), schema_conf_spec, 'Canonical Conflicts Parquet')
    for q_name, q_final in [
        ('Canonical Out-of-Bounds Parquet', drive_oob_path),
        ('Canonical Invalid Timestamps Parquet', drive_inv_ts_path),
        ('Canonical Invalid Vehicle IDs Parquet', drive_inv_vid_path)
    ]:
        verify_arrow_schema(pq.read_schema(q_final), schema_quar_spec, q_name)
    print('   Independent canonical verification PASSED: checksums, sizes, rows, and Arrow types verified on permanent files.')

    # 9.3 Prepare and Validate Staged Manifest Locally
    print('   Staging and validating manifest update locally...')
    pre_existing_partitions = json.loads(json.dumps(manifest.get('partitions', {})))

    if 'partitions' not in manifest: manifest['partitions'] = {}
    if 'metadata' not in manifest:
        manifest['metadata'] = {
            'dataset': 'Delhi DTC Bus GTFS-RT Historical GPS (October 2026)',
            'source_archive': 'delhi-dtc-bus-gtfs-rt-2026-10.7z',
            'governing_status': 'DEGRADE',
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }

    duration = round(time.time() - t_start, 2)
    manifest['partitions'][PILOT_DATE] = {
        'status': 'COMMITTED',
        'service_date': PILOT_DATE,
        'raw_records': n_raw,
        'clean_records': n_clean,
        'dedup_records': n_dedup,
        'conflict_records': n_conflicts,
        'out_of_bounds_records': n_oob,
        'invalid_timestamp_records': n_inv_ts,
        'invalid_vehicle_id_records': n_inv_vid,
        'accounting_delta': delta,
        'sha256': sha_clean_local,
        'sha256_clean': sha_clean_local,
        'sha256_conflicts': sha_conf_local,
        'sha256_out_of_bounds': sha_oob_local,
        'sha256_invalid_timestamps': sha_inv_ts_local,
        'sha256_invalid_vehicle_ids': sha_inv_vid_local,
        'clean_parquet_bytes': size_clean_local,
        'conflicts_parquet_bytes': size_conf_local,
        'out_of_bounds_parquet_bytes': size_oob_local,
        'invalid_timestamps_parquet_bytes': size_inv_ts_local,
        'invalid_vehicle_ids_parquet_bytes': size_inv_vid_local,
        'raw_sqlite_bytes': db_size,
        'duration_seconds': duration,
        'committed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }

    local_manifest_staged = os.path.join(SCRATCH_DIR, 'ingestion_manifest_staged.json')
    with open(local_manifest_staged, 'w') as f:
        json.dump(manifest, f, indent=2)

    with open(local_manifest_staged, 'r') as f:
        local_val = json.load(f)
    p_pilot = local_val['partitions'].get(PILOT_DATE)
    assert p_pilot is not None, f"Local manifest validation failed: {PILOT_DATE} partition missing!"
    assert p_pilot['status'] == 'COMMITTED', f"Local status mismatch: {p_pilot['status']}"
    assert p_pilot['raw_records'] == n_raw
    assert p_pilot['clean_records'] == n_clean
    assert p_pilot['dedup_records'] == n_dedup
    assert p_pilot['conflict_records'] == n_conflicts
    assert p_pilot['out_of_bounds_records'] == n_oob
    assert p_pilot['invalid_timestamp_records'] == n_inv_ts
    assert p_pilot['invalid_vehicle_id_records'] == n_inv_vid
    assert p_pilot['accounting_delta'] == 0
    assert p_pilot['sha256_clean'] == sha_clean_local
    assert p_pilot['sha256_conflicts'] == sha_conf_local
    assert p_pilot['sha256_out_of_bounds'] == sha_oob_local
    assert p_pilot['sha256_invalid_timestamps'] == sha_inv_ts_local
    assert p_pilot['sha256_invalid_vehicle_ids'] == sha_inv_vid_local
    assert p_pilot['clean_parquet_bytes'] == size_clean_local
    assert p_pilot['conflicts_parquet_bytes'] == size_conf_local
    assert p_pilot['out_of_bounds_parquet_bytes'] == size_oob_local
    assert p_pilot['invalid_timestamps_parquet_bytes'] == size_inv_ts_local
    assert p_pilot['invalid_vehicle_ids_parquet_bytes'] == size_inv_vid_local
    for p_date, p_data in pre_existing_partitions.items():
        assert p_date in local_val['partitions'], f"Pre-existing partition {p_date} missing in local staged manifest!"
        assert local_val['partitions'][p_date] == p_data, f"Pre-existing partition {p_date} modified in local staged manifest!"
    print('   Local staged manifest created and validated successfully.')

    # 9.4 Create snapshot backup of existing Drive manifest before touching it
    if manifest_existed_initially and os.path.exists(manifest_file):
        sha_orig = compute_sha256(manifest_file)
        shutil.copy2(manifest_file, manifest_bak)
        manifest_bak_created = True
        sha_bak = compute_sha256(manifest_bak)
        assert sha_bak == sha_orig, f"CRITICAL SAFETY STOP: Manifest backup integrity check failed! Original {sha_orig} != Backup {sha_bak}"
        print(f'   Created and verified backup of existing Drive manifest at {manifest_bak} (SHA-256: {sha_bak[:16]}...).')

    # 9.5 Stage to Google Drive temporary manifest alongside target
    shutil.copy2(local_manifest_staged, manifest_tmp)
    manifest_tmp_created = True

    # 9.6 Atomically replace manifest
    try:
        os.replace(manifest_tmp, manifest_file)
        manifest_replaced = True
    except OSError as exc:
        raise exc

    print(f'   Manifest successfully replaced at {manifest_file}.')

    # -------------------------------------------------------------------------
    # Step 10: Reopen Saved Manifest and Verify COMMITTED Entry BEFORE Scratch Purge
    # -------------------------------------------------------------------------
    print('10. Reopening saved manifest to verify COMMITTED state...')
    assert os.path.exists(manifest_file), f"Manifest file missing at {manifest_file}"
    with open(manifest_file, 'r') as f:
        verified_manifest = json.load(f)

    entry = verified_manifest['partitions'].get(PILOT_DATE)
    assert entry is not None, f"Manifest verification failed: entry for {PILOT_DATE} missing!"
    assert entry['status'] == 'COMMITTED', f"Manifest status mismatch: {entry['status']}"
    assert entry['raw_records'] == n_raw, f"Raw count mismatch in manifest: {entry['raw_records']} vs {n_raw}"
    assert entry['clean_records'] == n_clean, f"Clean count mismatch: {entry['clean_records']} vs {n_clean}"
    assert entry['dedup_records'] == n_dedup, f"Dedup count mismatch: {entry['dedup_records']} vs {n_dedup}"
    assert entry['conflict_records'] == n_conflicts, f"Conflict count mismatch: {entry['conflict_records']} vs {n_conflicts}"
    assert entry['out_of_bounds_records'] == n_oob, f"OOB count mismatch: {entry['out_of_bounds_records']} vs {n_oob}"
    assert entry['invalid_timestamp_records'] == n_inv_ts, f"Invalid TS count mismatch: {entry['invalid_timestamp_records']} vs {n_inv_ts}"
    assert entry['invalid_vehicle_id_records'] == n_inv_vid, f"Invalid VID count mismatch: {entry['invalid_vehicle_id_records']} vs {n_inv_vid}"
    assert entry['accounting_delta'] == 0, f"Non-zero accounting delta in manifest: {entry['accounting_delta']}"
    assert entry['sha256_clean'] == sha_clean_local, "Clean SHA-256 mismatch in manifest!"
    assert entry['sha256_conflicts'] == sha_conf_local, "Conflicts SHA-256 mismatch in manifest!"
    assert entry['sha256_out_of_bounds'] == sha_oob_local, "OOB SHA-256 mismatch in manifest!"
    assert entry['sha256_invalid_timestamps'] == sha_inv_ts_local, "Invalid TS SHA-256 mismatch in manifest!"
    assert entry['sha256_invalid_vehicle_ids'] == sha_inv_vid_local, "Invalid VID SHA-256 mismatch in manifest!"
    assert entry['clean_parquet_bytes'] == size_clean_local, "Clean bytes mismatch in manifest!"
    assert entry['conflicts_parquet_bytes'] == size_conf_local, "Conflicts bytes mismatch in manifest!"
    assert entry['out_of_bounds_parquet_bytes'] == size_oob_local, "OOB bytes mismatch in manifest!"
    assert entry['invalid_timestamps_parquet_bytes'] == size_inv_ts_local, "Invalid TS bytes mismatch in manifest!"
    assert entry['invalid_vehicle_ids_parquet_bytes'] == size_inv_vid_local, "Invalid VID bytes mismatch in manifest!"

    # Verify all pre-existing entries remain unchanged
    for p_date, p_data in pre_existing_partitions.items():
        assert p_date in verified_manifest['partitions'], f"Pre-existing partition {p_date} missing from committed manifest!"
        assert verified_manifest['partitions'][p_date] == p_data, f"Pre-existing partition {p_date} modified during commit!"

    print(f'    Manifest verification PASSED: {PILOT_DATE} is COMMITTED with exact counts, checksums, and pre-existing entries preserved.')

    # Clean up backup file ONLY now that post-commit verification has passed
    if os.path.exists(manifest_bak):
        try: os.remove(manifest_bak)
        except OSError: pass

except Exception as exc:
    execute_transaction_rollback("Transaction Failure", exc)
    raise RuntimeError(
        f"CRITICAL SAFETY STOP: Transaction failed: {exc}!\\n"
        "Rollback executed: uncommitted canonical files removed, manifest preserved/restored. Scratch files preserved."
    )

# -------------------------------------------------------------------------
# Step 11: Local Scratch Purge (ONLY Executed After Step 10 Verification Passes)
# -------------------------------------------------------------------------
print('\\n11. Purging temporary scratch files...')
for p_file in [LOCAL_DB, staged_clean, staged_conf, staged_oob, staged_inv_ts, staged_inv_vid, local_manifest_staged]:
    if os.path.exists(p_file):
        os.remove(p_file)
print('    Scratch SQLite and temporary parquet safely purged.')
print(f'\\nONE-DAY PILOT FOR {PILOT_DATE} COMPLETED AND COMMITTED TO DRIVE IN {duration}s!')
"""

cell_9_md = """## Phase 6 — Recovery & Re-entrancy Test
Verifies partition persistence on Google Drive, validates SHA-256 checksums, simulates Colab session restart, properly accounts for baseline local dates (`2026-10-01`, `02`, `03`, `04`, `07`), skips the committed pilot, and identifies `2026-10-06` as the next pending date."""

cell_10_code = """# Phase 6: Recovery & Re-entrancy Test (Corrected Baseline-Aware Logic)
print('=== EXECUTING RECOVERY AND IDEMPOTENCY TEST ===')

# 1. Verify Partition Exists on Drive
manifest_file = os.path.join(DRIVE_ROOT, 'raw_manifests', 'ingestion_manifest.json')
assert os.path.exists(manifest_file), 'Manifest missing from Google Drive!'

with open(manifest_file, 'r') as f:
    saved_manifest = json.load(f)

pilot_record = saved_manifest['partitions'].get('2026-10-05')
assert pilot_record is not None, 'Pilot date 2026-10-05 missing from manifest!'
assert pilot_record['status'] == 'COMMITTED', f"Expected COMMITTED, got {pilot_record['status']}"

drive_clean_pq = os.path.join(DRIVE_ROOT, 'parquet', 'service_date=2026-10-05', 'data.parquet')
assert os.path.exists(drive_clean_pq), 'Committed Parquet missing from Drive!'

# Recompute Checksum
h2 = hashlib.sha256()
with open(drive_clean_pq, 'rb') as f:
    while chunk := f.read(8192 * 1024): h2.update(chunk)
recomputed_sha256 = h2.hexdigest()
assert recomputed_sha256 == pilot_record['sha256_clean'], 'Checksum mismatch on Drive Parquet!'
print('1. Parquet partition and SHA-256 checksum verified on Google Drive.')

# 2. Baseline-Aware Session Restart & Next Date Identification
BASELINE_LOCAL_DATES = {'2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-07'}
all_dates = [f'2026-10-{d:02d}' for d in range(1, 32)]
unprocessed = []
for d in all_dates:
    if d in BASELINE_LOCAL_DATES:
        continue
    state = saved_manifest['partitions'].get(d, {}).get('status')
    if state != 'COMMITTED':
        unprocessed.append(d)

print(f'2. Re-entrancy Check: Skipped 2026-10-05 (already COMMITTED).')
print(f'   Skipped baseline local dates: {sorted(BASELINE_LOCAL_DATES)}')
print(f'   Total remaining unprocessed dates in Colab: {len(unprocessed)} of 26 non-baseline dates')
print(f'   Immediate next pending date: {unprocessed[0]}')
assert unprocessed[0] == '2026-10-06', f"Expected 2026-10-06 as next pending, got {unprocessed[0]}"

print('\\nRECOVERY TEST VERDICT: PASS (Zero duplication, exact state recovery)')"""

cells = [
    {"cell_type": "markdown", "metadata": {}, "source": to_source(cell_0_md)},
    {"cell_type": "markdown", "metadata": {}, "source": to_source(cell_1_md)},
    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source(cell_2_code)},
    {"cell_type": "markdown", "metadata": {}, "source": to_source(cell_3_md)},
    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source(cell_4_code)},
    {"cell_type": "markdown", "metadata": {}, "source": to_source(cell_5_md)},
    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source(cell_6_code)},
    {"cell_type": "markdown", "metadata": {}, "source": to_source(cell_7_md)},
    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source(cell_8_code)},
    {"cell_type": "markdown", "metadata": {}, "source": to_source(cell_9_md)},
    {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source(cell_10_code)}
]

notebook_data = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "colab": {
            "provenance": [],
            "authorship_tag": "Delhi_Bus_Traffic_Planner_Team"
        },
        "kernelspec": {
            "display_name": "Python 3",
            "name": "python3"
        },
        "language_info": {
            "name": "python"
        }
    },
    "cells": cells
}

with open(NOTEBOOK_PATH, "w") as fp:
    json.dump(notebook_data, fp, indent=2)

print(f"Generated fully hardened notebook at {NOTEBOOK_PATH} with {len(cells)} cells.")
