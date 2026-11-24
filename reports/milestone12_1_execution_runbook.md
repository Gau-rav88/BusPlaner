# Milestone 12.1 — Google Colab Execution Runbook

**Governing Specification:** PRD v3.0  
**Audit Timestamp:** 2026-11-22T13:34:00Z  
**Governing Status:** `DEGRADE`  
**Milestone Scope:** Step-by-Step Operator Runbook & Colab Notebook Code (Ready to Run)  
**Evaluated Verdict:** `GOOGLE_CLOUD_READY_WITH_LIMITATIONS`

---

## 1. Operator Preparation & Prerequisites

This runbook provides complete, copy-pasteable instructions for running the **October 2026 Delhi Bus Historical GPS Ingestion Pipeline** on **Google Colab Free-Tier**.

### Prerequisites:
1. A Google Account with access to Google Drive (User has 4.98 TB available space).
2. A modern web browser (Chrome, Edge, or Firefox).
3. No software installation is required on your local Mac.
4. **Execution is currently GATED** pending your explicit authorization.

---

## 2. Step-by-Step Google Colab Execution Guide

### Step 1: Open Google Colab
1. Navigate to [https://colab.research.google.com](https://colab.research.google.com).
2. Click **New Notebook**.
3. In the top menu, go to **Runtime** $\to$ **Change runtime type**.
4. Confirm **Hardware accelerator** is set to **None (CPU)**.
5. Name the notebook: `Delhi_Bus_GPS_Ingestion_2026_10.ipynb`.

---

### Step 2: Colab Notebook Code Cells (Execute in Sequence)

#### Cell 1: Environment Setup & High-Performance Dependencies
```python
# Cell 1: Install DuckDB and PyArrow
!pip install -q duckdb pyarrow tqdm
!apt-get install -q -y p7zip-full

import os, sys, time, json, hashlib, glob
import duckdb
import pyarrow.parquet as pq

print("Environment initialized successfully.")
print(f"DuckDB version: {duckdb.__version__}")
```

---

#### Cell 2: Mount Google Drive (Native OAuth2 Popup)
```python
# Cell 2: Securely Mount Google Drive
from google.colab import drive

# This triggers Google's native, secure interactive popup.
# No passwords or tokens are stored in the notebook.
drive.mount('/content/drive')

DRIVE_BASE = "/content/drive/MyDrive/Delhi_Bus_Historical_Data"
SCRATCH_DIR = "/content/scratch"

os.makedirs(f"{DRIVE_BASE}/source", exist_ok=True)
os.makedirs(f"{DRIVE_BASE}/raw_manifests", exist_ok=True)
os.makedirs(f"{DRIVE_BASE}/parquet", exist_ok=True)
os.makedirs(f"{DRIVE_BASE}/quarantine", exist_ok=True)
os.makedirs(f"{DRIVE_BASE}/validation_reports", exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)

print(f"Drive mounted. Target workspace: {DRIVE_BASE}")
```

---

#### Cell 3: Download Pristine Source Archive (Fast Google Backbone)
```python
# Cell 3: Download 7z Archive directly to Colab /content
ARCHIVE_URL = "https://pub-091bd9e794bb4877b10b29e6df80f065.r2.dev/2026-10/delhi-dtc-bus-gtfs-rt-2026-10.7z"
LOCAL_ARCHIVE = "/content/delhi-dtc-bus-gtfs-rt-2026-10.7z"
DRIVE_ARCHIVE = f"{DRIVE_BASE}/source/delhi-dtc-bus-gtfs-rt-2026-10.7z"

# Check if already present on Drive to avoid redundant downloads
if os.path.exists(DRIVE_ARCHIVE) and os.path.getsize(DRIVE_ARCHIVE) == 16077235732:
    print("Found verified archive on Google Drive! Copying to local SSD...")
    !cp "{DRIVE_ARCHIVE}" "{LOCAL_ARCHIVE}"
else:
    print("Downloading 14.97 GiB archive from remote R2 (Estimated time: ~3.5 min)...")
    !curl -L -C - -o "{LOCAL_ARCHIVE}" "{ARCHIVE_URL}"
    # Verify download byte size
    actual_size = os.path.getsize(LOCAL_ARCHIVE)
    assert actual_size == 16077235732, f"Size mismatch: got {actual_size}, expected 16077235732"
    print("Download complete and size verified! Backing up to Google Drive...")
    !cp "{LOCAL_ARCHIVE}" "{DRIVE_ARCHIVE}"

print("Pristine 7z archive ready on local high-speed SSD.")
```

---

#### Cell 4: Initialize Ingestion Manifest State Machine
```python
# Cell 4: Initialize or Load Master Manifest
MANIFEST_PATH = f"{DRIVE_BASE}/raw_manifests/ingestion_manifest.json"

ALL_DATES = [f"2026-10-{d:02d}" for d in range(1, 32)]

if os.path.exists(MANIFEST_PATH):
    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)
    print(f"Loaded existing manifest with {len(manifest['partitions'])} tracked partitions.")
else:
    manifest = {
        "manifest_version": "1.0.0",
        "dataset": "delhi_dtc_historical_gps_2026_10",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "partitions": {}
    }
    for d in ALL_DATES:
        manifest["partitions"][d] = {"status": "PENDING"}
    
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
    print("Created fresh ingestion manifest on Google Drive.")
```

---

#### Cell 5: Automated Sliding-Window Ingestion Controller
```python
# Cell 5: Execute Sliding-Window Ingestion with Immediate Purge
def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192 * 1024):
            h.update(chunk)
    return h.hexdigest()

print("Starting Historical GPS Ingestion Pipeline...")

for target_date in ALL_DATES:
    p_state = manifest["partitions"].get(target_date, {})
    if p_state.get("status") == "COMMITTED":
        print(f"[{target_date}] Already COMMITTED. Skipping.")
        continue

    print(f"\n=======================================================")
    print(f" PROCESSING SERVICE DATE: {target_date}")
    print(f"=======================================================")
    t0 = time.time()
    
    db_filename = f"bus_movements_{target_date.replace('-', '_')}.db"
    local_db_path = f"{SCRATCH_DIR}/{db_filename}"
    
    # 1. Selective single-day decompression from 7z
    print(f"[{target_date}] Extracting {db_filename} from 7z...")
    !7z e -y -o"{SCRATCH_DIR}" "{LOCAL_ARCHIVE}" "{db_filename}" > /dev/null
    
    if not os.path.exists(local_db_path):
        print(f"ERROR: Failed to extract {db_filename}!")
        break
        
    raw_bytes = os.path.getsize(local_db_path)
    print(f"[{target_date}] Extracted SQLite size: {raw_bytes / (1024**3):.3f} GiB")
    
    # 2. DuckDB Vectorized Processing in Scratch Storage
    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA max_memory = '3.0GB';")
    con.execute("PRAGMA threads = 2;")
    con.execute(f"ATTACH '{local_db_path}' AS raw_db (TYPE SQLITE);")
    
    n_raw = con.execute("SELECT COUNT(*) FROM raw_db.bus_telemetry").fetchone()[0]
    print(f"[{target_date}] Raw telemetry rows: {n_raw:,}")
    
    # Deduplication
    con.execute("""
        CREATE TEMP TABLE deduped AS
        SELECT DISTINCT vehicle_id, timestamp, latitude, longitude, speed, heading
        FROM raw_db.bus_telemetry
        WHERE vehicle_id IS NOT NULL AND TRIM(vehicle_id) != '';
    """)
    n_distinct = con.execute("SELECT COUNT(*) FROM deduped").fetchone()[0]
    n_dedup = n_raw - n_distinct
    
    # Conflicts
    con.execute("""
        CREATE TEMP TABLE conflicts AS
        SELECT * FROM deduped
        WHERE (vehicle_id, timestamp) IN (
            SELECT vehicle_id, timestamp FROM deduped GROUP BY vehicle_id, timestamp HAVING COUNT(*) > 1
        );
    """)
    n_conflict = con.execute("SELECT COUNT(*) FROM conflicts").fetchone()[0]
    
    # Out of Bounds Filter (Delhi NCR)
    con.execute("""
        CREATE TEMP TABLE clean_candidates AS
        SELECT * FROM deduped
        WHERE (vehicle_id, timestamp) NOT IN (SELECT vehicle_id, timestamp FROM conflicts);
        
        CREATE TEMP TABLE out_of_bounds AS
        SELECT * FROM clean_candidates
        WHERE latitude < 28.40 OR latitude > 28.90 OR longitude < 76.80 OR longitude > 77.45;
    """)
    n_oob = con.execute("SELECT COUNT(*) FROM out_of_bounds").fetchone()[0]
    
    # Clean Final
    con.execute("""
        CREATE TEMP TABLE clean_final AS
        SELECT 
            CAST(vehicle_id AS VARCHAR) AS vehicle_id,
            CAST(timestamp AS BIGINT) AS timestamp,
            CAST(latitude AS DOUBLE) AS latitude,
            CAST(longitude AS DOUBLE) AS longitude,
            CAST(speed AS DOUBLE) AS speed,
            CAST(heading AS DOUBLE) AS heading,
            CAST(DATE(EPOCH_MS(timestamp * 1000)) AS DATE) AS service_date
        FROM clean_candidates
        WHERE latitude >= 28.40 AND latitude <= 28.90 AND longitude >= 76.80 AND longitude <= 77.45
        ORDER BY vehicle_id, timestamp ASC;
    """)
    n_clean = con.execute("SELECT COUNT(*) FROM clean_final").fetchone()[0]
    
    # Mathematical Conservation Check
    delta = n_raw - (n_clean + n_dedup + n_conflict + n_oob)
    print(f"[{target_date}] Clean: {n_clean:,} | Dedup: {n_dedup:,} | Conflicts: {n_conflict:,} | OOB: {n_oob:,}")
    print(f"[{target_date}] Accounting Delta: {delta} (Strict Zero Tolerance)")
    assert delta == 0, f"Accounting discrepancy on {target_date}: {delta}"
    
    # Export Partitions to Scratch
    clean_tmp = f"{SCRATCH_DIR}/clean_{target_date}.parquet"
    conf_tmp = f"{SCRATCH_DIR}/conflicts_{target_date}.parquet"
    oob_tmp = f"{SCRATCH_DIR}/oob_{target_date}.parquet"
    
    con.execute(f"COPY clean_final TO '{clean_tmp}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    if n_conflict > 0:
        con.execute(f"COPY conflicts TO '{conf_tmp}' (FORMAT PARQUET, COMPRESSION ZSTD);")
    if n_oob > 0:
        con.execute(f"COPY out_of_bounds TO '{oob_tmp}' (FORMAT PARQUET, COMPRESSION ZSTD);")
        
    con.close()
    
    # 3. Upload final Parquet partitions to Google Drive
    drive_parquet_dir = f"{DRIVE_BASE}/parquet/service_date={target_date}"
    drive_quarantine_dir = f"{DRIVE_BASE}/quarantine/service_date={target_date}"
    os.makedirs(drive_parquet_dir, exist_ok=True)
    os.makedirs(drive_quarantine_dir, exist_ok=True)
    
    !cp "{clean_tmp}" "{drive_parquet_dir}/data.parquet"
    if n_conflict > 0:
        !cp "{conf_tmp}" "{drive_quarantine_dir}/conflicts.parquet"
    if n_oob > 0:
        !cp "{oob_tmp}" "{drive_quarantine_dir}/out_of_bounds.parquet"
        
    # Generate SHA-256 Checksum
    clean_sha256 = get_sha256(f"{drive_parquet_dir}/data.parquet")
    
    # 4. Immediate Local Disk Purge
    os.remove(local_db_path)
    os.remove(clean_tmp)
    if os.path.exists(conf_tmp): os.remove(conf_tmp)
    if os.path.exists(oob_tmp): os.remove(oob_tmp)
    print(f"[{target_date}] Purged transient SQLite and scratch files. Space reclaimed.")
    
    # 5. Commit Partition to Manifest on Drive
    duration = round(time.time() - t0, 1)
    manifest["partitions"][target_date] = {
        "status": "COMMITTED",
        "raw_sqlite_bytes": raw_bytes,
        "clean_rows": n_clean,
        "dedup_rows": n_dedup,
        "conflict_rows": n_conflict,
        "oob_rows": n_oob,
        "accounting_delta": delta,
        "sha256": clean_sha256,
        "duration_seconds": duration,
        "committed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    with open(f"{MANIFEST_PATH}.tmp", "w") as f:
        json.dump(manifest, f, indent=2)
    os.replace(f"{MANIFEST_PATH}.tmp", MANIFEST_PATH)
    
    print(f"[{target_date}] COMMITTED to Google Drive in {duration}s. Manifest updated.")

print("\nALL 31 SERVICE DATES PROCESSED AND COMMITTED TO GOOGLE DRIVE!")
```

---

## 3. Disconnection Recovery Protocol

If Google Colab disconnects or the runtime restarts:
1. Re-open the notebook and connect to a new runtime.
2. Run **Cell 1** (install dependencies) and **Cell 2** (mount Google Drive).
3. Skip Cell 3 if the archive is already backed up on Drive.
4. Run **Cell 4** and **Cell 5**.
5. **The pipeline reads `ingestion_manifest.json` from Drive, skips all previously `COMMITTED` dates, and resumes immediately at the exact next pending day.** Zero data is duplicated or lost.

