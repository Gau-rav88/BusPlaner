with open('scripts/generate_colab_notebook_v2.py', 'r') as f:
    content = f.read()

# 1. Update Cell 8 top to include imports, path defaults, schema specs, and verify_arrow_schema
old_cell8_top = """cell_8_code = \"\"\"# Phase 5: One-Day Ingestion Pilot for 2026-10-05 (Hardened Production Pipeline)
PILOT_DATE = '2026-10-05'
DB_NAME = f'bus_movements_{PILOT_DATE.replace("-", "_")}.db'
LOCAL_DB = os.path.join(SCRATCH_DIR, DB_NAME)
EXPECTED_UNCOMPRESSED_BYTES = 3428802560
EXPECTED_ARCHIVE_BYTES = 16077236568"""

new_cell8_top = """cell_8_code = \"\"\"# Phase 5: One-Day Ingestion Pilot for 2026-10-05 (Hardened Production Pipeline)
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

# System Paths & Defaults (Ensures Cell 8 runs from a fresh runtime without relying on earlier variables)
if 'DRIVE_ROOT' not in globals() or not DRIVE_ROOT:
    DRIVE_ROOT = '/content/drive/MyDrive/Delhi_Bus_Historical_Data'
if 'SCRATCH_DIR' not in globals() or not SCRATCH_DIR:
    SCRATCH_DIR = '/content/scratch'
if 'LOCAL_ARCHIVE' not in globals() or not LOCAL_ARCHIVE:
    LOCAL_ARCHIVE = '/content/delhi-dtc-bus-gtfs-rt-2026-10.7z'
    if not os.path.exists(LOCAL_ARCHIVE):
        candidate_scratch = os.path.join(SCRATCH_DIR, 'delhi-dtc-bus-gtfs-rt-2026-10.7z')
        candidate_drive = os.path.join(DRIVE_ROOT, 'source', 'delhi-dtc-bus-gtfs-rt-2026-10.7z')
        if os.path.exists(candidate_scratch):
            LOCAL_ARCHIVE = candidate_scratch
        elif os.path.exists(candidate_drive):
            LOCAL_ARCHIVE = candidate_drive

os.makedirs(SCRATCH_DIR, exist_ok=True)

PILOT_DATE = '2026-10-05'
DB_NAME = f'bus_movements_{PILOT_DATE.replace("-", "_")}.db'
LOCAL_DB = os.path.join(SCRATCH_DIR, DB_NAME)
EXPECTED_UNCOMPRESSED_BYTES = 3428802560
EXPECTED_ARCHIVE_BYTES = 16077236568

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
            assert act_type_str == exp_type, f"{schema_name} col {field.name}: {act_type_str} != {exp_type}" """

assert old_cell8_top in content, "old_cell8_top not found!"
content = content.replace(old_cell8_top, new_cell8_top, 1)

# 2. Update Substep 3.2.2 and 3.2.3 in Step 3
old_substep_32 = """# Substep 3.2.2: Quarantine Invalid/Implausible Timestamps & Mismatched Dates (Stage E01.5)
con.execute(f'''
    CREATE TEMP TABLE invalid_timestamps AS
    SELECT *,
        CASE 
            WHEN TRY_CAST(timestamp AS BIGINT) IS NULL OR TRY_CAST(timestamp AS BIGINT) <= 0
                THEN 'E00_INVALID_OR_NULL_TIMESTAMP'
            WHEN TRY_CAST(timestamp AS BIGINT) < {MIN_PLAUSIBLE_EPOCH} OR TRY_CAST(timestamp AS BIGINT) > {MAX_PLAUSIBLE_EPOCH}
                THEN 'E00_IMPLAUSIBLE_TIMESTAMP_OUT_OF_BOUNDS'
            WHEN TRY_CAST(date AS DATE) IS NULL OR TRY_CAST(date AS DATE) != TRY_CAST('{PILOT_DATE}' AS DATE)
                THEN 'E00_MISMATCHED_OR_INVALID_SERVICE_DATE'
            ELSE 'E00_TEMPORAL_ANOMALY'
        END as quarantine_reason,
        '{PILOT_DATE}' as service_date
    FROM stage_e01
    WHERE (vehicle_id IS NOT NULL AND TRIM(vehicle_id) != '')
      AND (
          TRY_CAST(timestamp AS BIGINT) IS NULL 
          OR TRY_CAST(timestamp AS BIGINT) <= 0
          OR TRY_CAST(timestamp AS BIGINT) < {MIN_PLAUSIBLE_EPOCH}
          OR TRY_CAST(timestamp AS BIGINT) > {MAX_PLAUSIBLE_EPOCH}
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
      AND (TRY_CAST(timestamp AS BIGINT) IS NOT NULL AND TRY_CAST(timestamp AS BIGINT) > 0)
      AND (TRY_CAST(timestamp AS BIGINT) >= {MIN_PLAUSIBLE_EPOCH} AND TRY_CAST(timestamp AS BIGINT) <= {MAX_PLAUSIBLE_EPOCH})
      AND (TRY_CAST(date AS DATE) IS NOT NULL AND TRY_CAST(date AS DATE) = TRY_CAST('{PILOT_DATE}' AS DATE));
''')"""

new_substep_32 = """# Substep 3.2.2: Quarantine Invalid/Implausible Timestamps & Missing/Mismatched Dates (Stage E01.5)
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
''')"""

assert old_substep_32 in content, "old_substep_32 not found!"
content = content.replace(old_substep_32, new_substep_32, 1)

# 3. Update Step 8: remove duplicate schema definitions and add service_date non-null assertion
old_step8_schemas = """    # 8.4 PyArrow Exact Schema, Column Order & Data Type Verification for ALL FIVE Files
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

    verify_arrow_schema(pq.read_schema(drive_clean_staging), schema_clean_spec, 'Staged Clean Parquet')"""

new_step8_schemas = """    # 8.4 PyArrow Exact Schema, Column Order & Data Type Verification for ALL FIVE Files
    verify_arrow_schema(pq.read_schema(drive_clean_staging), schema_clean_spec, 'Staged Clean Parquet')
    clean_table_staged = pq.read_table(drive_clean_staging)
    assert clean_table_staged['service_date'].null_count == 0, "NULL service_date detected in staged clean Parquet!"""""

assert old_step8_schemas in content, "old_step8_schemas not found!"
content = content.replace(old_step8_schemas, new_step8_schemas, 1)

# 4. Update Step 9 variables and execute_transaction_rollback
old_step9_vars = """promoted_canonical_files = []
manifest_bak_created = False
manifest_tmp_created = False
manifest_replaced = False
sha_bak = None

def execute_transaction_rollback(failure_reason, original_exc):
    print(f"\\\\n   >>> INITIATING TRANSACTION ROLLBACK (Trigger: {failure_reason}) <<<")
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
        # If manifest existed initially and backup was created, restore from .bak regardless of replace state
        if manifest_bak_created and os.path.exists(manifest_bak):
            try:
                shutil.copy2(manifest_bak, manifest_file)
                assert os.path.exists(manifest_file), "Restored manifest missing!"
                restored_sha = compute_sha256(manifest_file)
                assert restored_sha == sha_bak, f"Restored manifest SHA-256 mismatch! Got {restored_sha}, expected {sha_bak}"
                print(f"       [ROLLBACK] Restored and verified original manifest from backup: {manifest_file}")
            except Exception as e:
                rollback_errors.append(f"Failed restoring/verifying manifest from backup: {e}")
        elif manifest_replaced:
            rollback_errors.append(f"Manifest was replaced but backup {manifest_bak} is missing to restore original!")
    else:"""

new_step9_vars = """promoted_canonical_files = []
manifest_bak_created = False
manifest_tmp_created = False
manifest_replaced = False
sha_orig = compute_sha256(manifest_file) if (manifest_existed_initially and os.path.exists(manifest_file)) else None
sha_bak = None

def execute_transaction_rollback(failure_reason, original_exc):
    print(f"\\\\n   >>> INITIATING TRANSACTION ROLLBACK (Trigger: {failure_reason}) <<<")
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
    else:"""

assert old_step9_vars in content, "old_step9_vars not found!"
content = content.replace(old_step9_vars, new_step9_vars, 1)

# 5. Update Step 9.2: add canonical service_date non-null assertion
old_step92 = """    verify_arrow_schema(pq.read_schema(drive_clean_path), schema_clean_spec, 'Canonical Clean Parquet')"""
new_step92 = """    verify_arrow_schema(pq.read_schema(drive_clean_path), schema_clean_spec, 'Canonical Clean Parquet')
    clean_table_canon = pq.read_table(drive_clean_path)
    assert clean_table_canon['service_date'].null_count == 0, "NULL service_date detected in canonical clean Parquet!\""""

assert old_step92 in content, "old_step92 not found!"
content = content.replace(old_step92, new_step92, 1)

# 6. Update Step 9.4: verify backup SHA matches original before continuing
old_step94 = """    # 9.4 Create snapshot backup of existing Drive manifest before touching it
    if manifest_existed_initially and os.path.exists(manifest_file):
        shutil.copy2(manifest_file, manifest_bak)
        manifest_bak_created = True
        sha_bak = compute_sha256(manifest_bak)
        print(f'   Created backup of existing Drive manifest at {manifest_bak} (SHA-256: {sha_bak[:16]}...).')"""

new_step94 = """    # 9.4 Create snapshot backup of existing Drive manifest before touching it
    if manifest_existed_initially and os.path.exists(manifest_file):
        sha_orig = compute_sha256(manifest_file)
        shutil.copy2(manifest_file, manifest_bak)
        manifest_bak_created = True
        sha_bak = compute_sha256(manifest_bak)
        assert sha_bak == sha_orig, (
            f"CRITICAL SAFETY STOP: Manifest backup integrity check failed!\\n"
            f"Original SHA-256: {sha_orig}\\n"
            f"Backup SHA-256:   {sha_bak}\\n"
            "Backup copy was corrupted or incomplete. Aborting before touching manifest."
        )
        print(f'   Created and verified backup of existing Drive manifest at {manifest_bak} (SHA-256: {sha_bak[:16]}...).')"""

assert old_step94 in content, "old_step94 not found!"
content = content.replace(old_step94, new_step94, 1)

with open('scripts/generate_colab_notebook_v2.py', 'w') as f:
    f.write(content)

print("Patch applied to scripts/generate_colab_notebook_v2.py successfully!")
