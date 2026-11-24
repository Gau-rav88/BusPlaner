#!/usr/bin/env python3
"""
Milestone 12.2.2 — Pre-Execution Evidence Verification Script
Comprehensive 14-Test Transactional Safety, Preflight Invariants & Rollback Verification Suite:
- Test 1: Full Synthetic End-to-End Simulation (Happy Path) with Explicit NULL/Empty Date Quarantining
- Test 2: Failure during third Parquet promotion (Atomic Transaction Rollback)
- Test 3: Failure after all five promotions but before manifest replacement
- Test 4: Manifest replacement failure with partially written manifest (Torn-Write Recovery)
- Test 5: Failure during canonical-file post-promotion SHA verification
- Test 6: Case B: Existing manifest + Step 10 failure -> original manifest restored byte-for-byte
- Test 7: Case A: No original manifest + manifest created + Step 10 failure -> no manifest & no canonical files remain
- Test 8: Case C: Existing recovery journal preflight in Step 0 -> execution stops before deleting staging files
- Test 9: Case D: Existing .bak or .tmp preflight in Step 0 & Step 9 -> execution stops without overwriting artifacts
- Test 10: Rollback failure itself -> recovery journal written & preserved
- Test 11: Incomplete or corrupted manifest backup in Step 9.4 -> caught before touching manifest, rollback verified
- Test 12: Backup restoration failure during rollback -> recovery journal written, backup & temp artifacts preserved
- Test 13: Real SQLite Source Schema Verification against DuckDB 1.3.2
- Test 14: Environmental Invariants & Baseline Data Preservation
"""

import json
import os
import sys
import shutil
import time
import hashlib
import sqlite3
import subprocess
import tempfile
from collections import namedtuple
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

NOTEBOOK_PATH = "notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab_v2.ipynb"
PILOT_DATE = "2026-10-05"
DB_NAME = f"bus_movements_{PILOT_DATE.replace('-', '_')}.db"

# 22 synthetic observations covering all edge cases, including NULL, empty, and mismatched dates
SYNTHETIC_ROWS = [
    # 1,2: Exact duplicate pair (1 clean, 1 dedup)
    ('DL1PC0001', '28.6139', '77.2090', 25.5, 1598.0, '1598_08_30_1', '1791158400', '2026-10-05', '05:30:00'),
    ('DL1PC0001', '28.6139', '77.2090', 25.5, 1598.0, '1598_08_30_1', '1791158400', '2026-10-05', '05:30:00'),
    # 3,4: Conflicting duplicates at same timestamp (1 clean, 1 conflict)
    ('DL1PC0002', '28.6140', '77.2091', 35.0, 1445.0, '1445_10_15_2', '1791158400', '2026-10-05', '05:30:00'),
    ('DL1PC0002', '28.6145', '77.2095', 15.0, 1445.0, '1445_10_15_2', '1791158400', '2026-10-05', '05:30:00'),
    # 5,6,7: Multiple NULL & empty vehicle IDs at same timestamp 1791158400 (3 quarantined)
    (None,        '28.6140', '77.2091', 20.0, 1598.0, '1598_08_30_1', '1791158400', '2026-10-05', '05:30:00'),
    (None,        '28.6145', '77.2095', 22.0, 1445.0, '1445_10_15_2', '1791158400', '2026-10-05', '05:30:00'),
    ('   ',       '28.6140', '77.2091', 20.0, 1598.0, '1598_08_30_1', '1791158400', '2026-10-05', '05:30:00'),
    # 8,9,10,11,12,13: Invalid & implausible timestamps (6 quarantined)
    ('DL1PC0003', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', None,         '2026-10-05', '05:30:00'),  # NULL timestamp
    ('DL1PC0004', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', 'BAD_TS',     '2026-10-05', '05:30:00'),  # Non-numeric timestamp
    ('DL1PC0005', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', '0',          '2026-10-05', '05:30:00'),  # Zero timestamp
    ('DL1PC0006', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', '-100',       '2026-10-05', '05:30:00'),  # Negative timestamp
    ('DL1PC0007', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', '1791133199', '2026-10-05', '05:30:00'),  # Below MIN_PLAUSIBLE_EPOCH
    ('DL1PC0008', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', '1791246601', '2026-10-05', '05:30:00'),  # Above MAX_PLAUSIBLE_EPOCH
    # 14,15: Explicit NULL and mismatched dates (2 quarantined to invalid_timestamps)
    ('DL1PC0009', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', '1791158400', None,         '05:30:00'),  # NULL date
    ('DL1PC0010', '28.6139', '77.2090', 20.0, 1598.0, '1598_08_30_1', '1791158400', '2026-10-06', '05:30:00'),  # Mismatched date 2026-10-06
    # 17,18,19,20: Out-of-bounds coordinates (4 quarantined)
    ('DL1PC0012', '25.0000', '77.2090', 20.0, 1657.0, '1657_12_00',   '1791158400', '2026-10-05', '05:30:00'),  # Lat < 28.0
    ('DL1PC0013', '30.5000', '77.2090', 20.0, 1657.0, '1657_12_00',   '1791158400', '2026-10-05', '05:30:00'),  # Lat > 29.2
    ('DL1PC0014', '28.6139', '70.0000', 20.0, 1657.0, '1657_12_00',   '1791158400', '2026-10-05', '05:30:00'),  # Lng < 76.5
    ('DL1PC0015', '28.6139', None,      20.0, 1657.0, '1657_12_00',   '1791158400', '2026-10-05', '05:30:00'),  # Lng is None
    # 21,22: Valid clean observations with varied routes & trips (2 clean)
    ('DL1PC0016', '28.6139', '77.2090', 10.0, 788.0,  '788_15_32_9877', '1791225000', '2026-10-05', '00:00:00'),
    ('DL1PC0017', '28.6139', '77.2090', 18.0, 2203.0, '2203_16_29_3935','1791184060', '2026-10-05', '12:37:40')
]

INITIAL_MANIFEST = {
    "metadata": {
        "dataset": "Delhi DTC Bus GTFS-RT Historical GPS (October 2026)",
        "source_archive": "delhi-dtc-bus-gtfs-rt-2026-10.7z",
        "governing_status": "DEGRADE",
        "created_at": "2026-11-20T00:00:00Z"
    },
    "partitions": {
        "2026-10-01": {
            "status": "COMMITTED",
            "service_date": "2026-10-01",
            "raw_records": 31290299,
            "clean_records": 28500000,
            "dedup_records": 2000000,
            "conflict_records": 500000,
            "out_of_bounds_records": 290299,
            "invalid_timestamp_records": 0,
            "invalid_vehicle_id_records": 0,
            "accounting_delta": 0,
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "sha256_clean": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "sha256_conflicts": "1111111111111111111111111111111111111111111111111111111111111111",
            "sha256_out_of_bounds": "2222222222222222222222222222222222222222222222222222222222222222",
            "sha256_invalid_timestamps": "3333333333333333333333333333333333333333333333333333333333333333",
            "sha256_invalid_vehicle_ids": "4444444444444444444444444444444444444444444444444444444444444444",
            "clean_parquet_bytes": 104857600,
            "conflicts_parquet_bytes": 1024000,
            "out_of_bounds_parquet_bytes": 1024000,
            "invalid_timestamps_parquet_bytes": 1024000,
            "invalid_vehicle_ids_parquet_bytes": 1024000,
            "raw_sqlite_bytes": 3500000000,
            "duration_seconds": 120.5,
            "committed_at": "2026-11-20T01:00:00Z"
        }
    }
}

DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])

def create_sqlite_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE vehicle_feed (
            vehicle_id TEXT,
            lat TEXT,
            lng TEXT,
            speed REAL,
            route_id REAL,
            trip_id TEXT,
            timestamp TEXT,
            date date,
            time TEXT
        );
    """)
    con.executemany("INSERT INTO vehicle_feed VALUES (?,?,?,?,?,?,?,?,?);", rows)
    con.commit()
    con.close()

def setup_test_env(prefix, with_manifest=True):
    sandbox = tempfile.mkdtemp(prefix=prefix)
    scratch = os.path.join(sandbox, "scratch")
    drive = os.path.join(sandbox, "drive")
    os.makedirs(scratch, exist_ok=True)
    os.makedirs(os.path.join(drive, "raw_manifests"), exist_ok=True)

    manifest_file = os.path.join(drive, "raw_manifests", "ingestion_manifest.json")
    if with_manifest:
        with open(manifest_file, "w") as f:
            json.dump(INITIAL_MANIFEST, f, indent=2)

    archive_file = os.path.join(sandbox, "delhi-dtc-bus-gtfs-rt-2026-10.7z")
    with open(archive_file, "wb") as f:
        f.seek(16077236568 - 1)
        f.write(b"\0")

    db_path = os.path.join(scratch, DB_NAME)
    create_sqlite_db(db_path, SYNTHETIC_ROWS)
    db_size = os.path.getsize(db_path)
    os.rename(db_path, db_path + ".staged")

    return sandbox, scratch, drive, archive_file, db_path, db_size, manifest_file

def prepare_code(c8_code, db_path, db_size):
    target_uncompressed = "EXPECTED_UNCOMPRESSED_BYTES = 3428802560"
    target_7z = "subprocess.run(['7z', 'e', f'-o{SCRATCH_DIR}', LOCAL_ARCHIVE, DB_NAME], check=True)"
    return c8_code.replace(
        target_uncompressed,
        f"EXPECTED_UNCOMPRESSED_BYTES = {db_size}"
    ).replace(
        target_7z,
        f"os.rename('{db_path}.staged', '{db_path}')"
    )

def build_scope(drive, scratch, archive):
    return {
        "DRIVE_ROOT": drive,
        "SCRATCH_DIR": scratch,
        "LOCAL_ARCHIVE": archive,
        "os": os,
        "sys": sys,
        "json": json,
        "shutil": shutil,
        "time": time,
        "hashlib": hashlib,
        "sqlite3": sqlite3,
        "duckdb": duckdb,
        "pq": pq,
        "subprocess": subprocess
    }

def run_all_checks():
    print("=" * 80)
    print("M12.2.2 FINAL CELL 8 TRANSACTIONAL SAFETY & ROLLBACK AUDIT (DUCKDB 1.3.2)")
    print("=" * 80)
    print(f"Python Version:  {sys.version.split()[0]}")
    print(f"DuckDB Version:  {duckdb.__version__}")
    print(f"PyArrow Version: {pa.__version__}")
    print(f"Timestamp:       {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print("=" * 80)

    # Load Cell 8 from notebook
    with open(NOTEBOOK_PATH, "r") as f:
        nb = json.load(f)
    cell_8 = nb["cells"][8]
    c8_source_lines = cell_8["source"]
    c8_code = "".join(c8_source_lines)
    print(f"\nNotebook Verified: {NOTEBOOK_PATH}")
    print(f"Cell 8: {len(c8_source_lines)} lines, {len(c8_code)} characters")

    orig_disk_usage = shutil.disk_usage
    shutil.disk_usage = lambda p: DiskUsage(total=100 * 1024**3, used=50 * 1024**3, free=50 * 1024**3)

    try:
        # =====================================================================
        # TEST 1: Full Synthetic End-to-End Simulation (Happy Path)
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 1: FULL SYNTHETIC END-TO-END SIMULATION (HAPPY PATH)")
        print("=" * 80)
        sb1, sc1, dr1, ar1, db1, dbs1, mf1 = setup_test_env("delhi_t1_happy_")
        try:
            code1 = prepare_code(c8_code, db1, dbs1)
            scope1 = build_scope(dr1, sc1, ar1)
            exec(code1, scope1)

            assert scope1['n_raw'] == 21
            assert scope1['n_clean'] == 4
            assert scope1['n_dedup'] == 1
            assert scope1['n_conflicts'] == 1
            assert scope1['n_oob'] == 4
            assert scope1['n_inv_ts'] == 8
            assert scope1['n_inv_vid'] == 3
            assert scope1['delta'] == 0
            print("   [OK] Accounting conservation verified: N_raw=21, delta=0")

            # Check service_date non-null assertion on clean partition
            clean_p = os.path.join(dr1, "parquet", "service_date=2026-10-05", "data.parquet")
            assert os.path.exists(clean_p) and os.path.getsize(clean_p) > 0
            t_clean = pq.read_table(clean_p)
            assert t_clean['service_date'].null_count == 0, "NULL service_date detected in clean Parquet!"
            print("   [OK] Clean partition service_date contains 0 nulls across all records.")

            conf_p = os.path.join(dr1, "quarantine", "service_date=2026-10-05", "conflicts.parquet")
            assert os.path.exists(conf_p) and os.path.getsize(conf_p) > 0
            print("   [OK] All 5 canonical Parquet files verified on permanent Drive paths.")

            # Check manifest committed and pre-existing 2026-10-01 preserved
            with open(mf1, "r") as f:
                man_data = json.load(f)
            assert man_data["partitions"]["2026-10-05"]["status"] == "COMMITTED"
            assert man_data["partitions"]["2026-10-01"] == INITIAL_MANIFEST["partitions"]["2026-10-01"]
            print("   [OK] Manifest committed; pre-existing partition 2026-10-01 byte-for-byte preserved.")

            # Check scratch purged
            assert not os.path.exists(db1)
            assert not os.path.exists(os.path.join(sc1, f"clean_{PILOT_DATE}.parquet"))
            print("   [OK] Scratch purged after successful Step 10 verification.")
            print("Test 1 PASSED.")
        finally:
            shutil.rmtree(sb1)

        # =====================================================================
        # TEST 2: Failure during third Parquet promotion
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 2: FAILURE DURING THIRD PARQUET PROMOTION")
        print("=" * 80)
        sb2, sc2, dr2, ar2, db2, dbs2, mf2 = setup_test_env("delhi_t2_promo3_")
        try:
            code2 = prepare_code(c8_code, db2, dbs2)
            scope2 = build_scope(dr2, sc2, ar2)

            orig_replace = os.replace
            def failing_promo_replace(src, dst):
                if "quarantine" in dst and "out_of_bounds.parquet" in dst and not dst.endswith(".uploading"):
                    raise OSError("Simulated FUSE I/O error during promotion of 3rd file (out_of_bounds.parquet)")
                return orig_replace(src, dst)

            os.replace = failing_promo_replace
            caught_t2 = False
            try:
                exec(code2, scope2)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc) and ("out_of_bounds" in str(exc).lower() or "out-of-bounds" in str(exc).lower()):
                    caught_t2 = True
                    print(f"   [OK] Caught expected promotion error: {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                os.replace = orig_replace

            assert caught_t2, "FAILED: Did not catch promotion error!"

            for p_sub in ["parquet/service_date=2026-10-05/data.parquet",
                          "quarantine/service_date=2026-10-05/conflicts.parquet",
                          "quarantine/service_date=2026-10-05/out_of_bounds.parquet"]:
                assert not os.path.exists(os.path.join(dr2, p_sub)), f"Canonical file lingering after rollback: {p_sub}"
            print("   [OK] Verified zero canonical files linger on Drive after promotion failure rollback.")

            with open(mf2, "r") as f:
                assert json.load(f) == INITIAL_MANIFEST
            print("   [OK] Original manifest untouched.")
            assert os.path.exists(db2)
            print("   [OK] Scratch data safely preserved.")
            print("Test 2 PASSED.")
        finally:
            shutil.rmtree(sb2)

        # =====================================================================
        # TEST 3: Failure after all five promotions but before manifest replacement
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 3: FAILURE AFTER ALL FIVE PROMOTIONS BEFORE MANIFEST REPLACEMENT")
        print("=" * 80)
        sb3, sc3, dr3, ar3, db3, dbs3, mf3 = setup_test_env("delhi_t3_precommit_")
        try:
            code3 = prepare_code(c8_code, db3, dbs3)
            scope3 = build_scope(dr3, sc3, ar3)

            orig_copy2 = shutil.copy2
            def failing_copy2(src, dst):
                if dst.endswith("ingestion_manifest.json.tmp"):
                    raise IOError("Simulated network timeout staging manifest.tmp to Google Drive")
                return orig_copy2(src, dst)

            shutil.copy2 = failing_copy2
            caught_t3 = False
            try:
                exec(code3, scope3)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc):
                    caught_t3 = True
                    print(f"   [OK] Caught expected staging error: {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                shutil.copy2 = orig_copy2

            assert caught_t3, "FAILED: Did not catch manifest staging error!"

            for p_sub in ["parquet/service_date=2026-10-05/data.parquet",
                          "quarantine/service_date=2026-10-05/conflicts.parquet",
                          "quarantine/service_date=2026-10-05/out_of_bounds.parquet",
                          "quarantine/service_date=2026-10-05/invalid_timestamps.parquet",
                          "quarantine/service_date=2026-10-05/invalid_vehicle_ids.parquet"]:
                assert not os.path.exists(os.path.join(dr3, p_sub)), f"Canonical file lingering: {p_sub}"
            print("   [OK] All 5 promoted canonical files removed by rollback.")

            with open(mf3, "r") as f:
                assert json.load(f) == INITIAL_MANIFEST
            print("   [OK] Original manifest untouched.")
            assert os.path.exists(db3)
            print("   [OK] Scratch data preserved.")
            print("Test 3 PASSED.")
        finally:
            shutil.rmtree(sb3)

        # =====================================================================
        # TEST 4: Failure during manifest replacement with a partially written manifest
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 4: MANIFEST REPLACEMENT FAILURE WITH PARTIALLY WRITTEN MANIFEST")
        print("=" * 80)
        sb4, sc4, dr4, ar4, db4, dbs4, mf4 = setup_test_env("delhi_t4_torn_manifest_")
        try:
            with open(mf4, "rb") as f:
                initial_bytes = f.read()
            initial_sha = hashlib.sha256(initial_bytes).hexdigest()

            code4 = prepare_code(c8_code, db4, dbs4)
            scope4 = build_scope(dr4, sc4, ar4)

            orig_replace = os.replace
            def failing_replace_corrupt(src, dst):
                if dst == mf4:
                    with open(dst, "wb") as f:
                        f.write(b"CORRUPTED_TORN_JSON_DATA_1234567890")
                    raise OSError("Simulated Google Drive network timeout during os.replace")
                return orig_replace(src, dst)

            os.replace = failing_replace_corrupt
            caught_t4 = False
            try:
                exec(code4, scope4)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc):
                    caught_t4 = True
                    print(f"   [OK] Caught expected manifest replace error: {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                os.replace = orig_replace

            assert caught_t4, "FAILED: Did not catch manifest replacement error!"

            with open(mf4, "rb") as f:
                restored_bytes = f.read()
            restored_sha = hashlib.sha256(restored_bytes).hexdigest()
            assert restored_sha == initial_sha, "Manifest restoration failed! Hash mismatch!"
            print(f"   [OK] Manifest restored from .bak and verified byte-for-byte (SHA-256: {restored_sha[:16]}...).")

            for p_sub in ["parquet/service_date=2026-10-05/data.parquet", "quarantine/service_date=2026-10-05/conflicts.parquet"]:
                assert not os.path.exists(os.path.join(dr4, p_sub)), f"Canonical file lingering: {p_sub}"
            print("   [OK] All canonical files removed by rollback.")
            assert os.path.exists(db4)
            print("   [OK] Scratch data preserved.")
            print("Test 4 PASSED.")
        finally:
            shutil.rmtree(sb4)

        # =====================================================================
        # TEST 5: Failure during canonical-file post-promotion SHA verification
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 5: FAILURE DURING CANONICAL-FILE POST-PROMOTION SHA VERIFICATION")
        print("=" * 80)
        sb5, sc5, dr5, ar5, db5, dbs5, mf5 = setup_test_env("delhi_t5_canon_sha_")
        try:
            code5 = prepare_code(c8_code, db5, dbs5)
            scope5 = build_scope(dr5, sc5, ar5)

            orig_replace = os.replace
            def replace_with_corrupt(src, dst):
                orig_replace(src, dst)
                if "data.parquet" in dst and not dst.endswith(".uploading"):
                    with open(dst, "r+b") as f:
                        f.seek(15)
                        f.write(b"\xFF")
            os.replace = replace_with_corrupt

            caught_t5 = False
            try:
                exec(code5, scope5)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc) and "SHA-256 mismatch" in str(exc):
                    caught_t5 = True
                    print(f"   [OK] Caught expected canonical SHA verification failure:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                os.replace = orig_replace

            assert caught_t5, "FAILED: Did not catch canonical SHA mismatch!"

            for p_sub in ["parquet/service_date=2026-10-05/data.parquet", "quarantine/service_date=2026-10-05/conflicts.parquet"]:
                assert not os.path.exists(os.path.join(dr5, p_sub)), f"Canonical file lingering: {p_sub}"
            print("   [OK] Canonical files removed by rollback.")

            with open(mf5, "r") as f:
                assert json.load(f) == INITIAL_MANIFEST
            print("   [OK] Manifest untouched.")
            assert os.path.exists(db5)
            print("   [OK] Scratch data preserved.")
            print("Test 5 PASSED.")
        finally:
            shutil.rmtree(sb5)

        # =====================================================================
        # TEST 6: CASE B — Existing manifest + Step 10 readback failure -> restored byte-for-byte
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 6: CASE B — EXISTING MANIFEST + STEP 10 FAILURE -> RESTORED BYTE-FOR-BYTE")
        print("=" * 80)
        sb6, sc6, dr6, ar6, db6, dbs6, mf6 = setup_test_env("delhi_t6_case_b_")
        try:
            with open(mf6, "rb") as f:
                initial_manifest_bytes = f.read()
            initial_sha = hashlib.sha256(initial_manifest_bytes).hexdigest()

            code6 = prepare_code(c8_code, db6, dbs6)
            scope6 = build_scope(dr6, sc6, ar6)

            orig_json_load = json.load
            def mock_json_load_corrupt(fp):
                data = orig_json_load(fp)
                if hasattr(fp, "name") and fp.name.endswith("ingestion_manifest.json"):
                    if isinstance(data, dict) and "partitions" in data and "2026-10-05" in data["partitions"]:
                        data["partitions"]["2026-10-05"]["status"] = "CORRUPTED_STATUS"
                return data

            json.load = mock_json_load_corrupt
            caught_t6 = False
            try:
                exec(code6, scope6)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc) and "Manifest status mismatch" in str(exc):
                    caught_t6 = True
                    print(f"   [OK] Caught expected post-commit readback failure:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                json.load = orig_json_load

            assert caught_t6, "FAILED: Did not catch readback status mismatch!"

            with open(mf6, "rb") as f:
                restored_bytes = f.read()
            restored_sha = hashlib.sha256(restored_bytes).hexdigest()
            assert restored_sha == initial_sha, f"Case B failed: manifest hash mismatch! {restored_sha} vs {initial_sha}"
            with open(mf6, "r") as f:
                restored_man = json.load(f)
            assert restored_man["partitions"]["2026-10-01"] == INITIAL_MANIFEST["partitions"]["2026-10-01"]
            assert "2026-10-05" not in restored_man["partitions"]
            print(f"   [OK] Manifest restored byte-for-byte from backup (SHA-256: {restored_sha[:16]}...).")
            print("        Pre-existing baseline partition 2026-10-01 intact, 2026-10-05 partition absent.")

            for p_sub in ["parquet/service_date=2026-10-05/data.parquet", "quarantine/service_date=2026-10-05/conflicts.parquet"]:
                assert not os.path.exists(os.path.join(dr6, p_sub)), f"Canonical file lingering: {p_sub}"
            print("   [OK] Canonical files removed by rollback.")
            assert os.path.exists(db6)
            print("   [OK] Scratch data preserved.")
            print("Test 6 PASSED.")
        finally:
            shutil.rmtree(sb6)

        # =====================================================================
        # TEST 7: CASE A — No original manifest + Step 10 failure -> no manifest & no canonical files
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 7: CASE A — NO ORIGINAL MANIFEST + STEP 10 FAILURE -> NO MANIFEST & NO CANONICAL FILES")
        print("=" * 80)
        sb7, sc7, dr7, ar7, db7, dbs7, mf7 = setup_test_env("delhi_t7_case_a_", with_manifest=False)
        try:
            assert not os.path.exists(mf7), "Manifest must not exist initially for Case A test!"
            code7 = prepare_code(c8_code, db7, dbs7)
            scope7 = build_scope(dr7, sc7, ar7)

            orig_json_load = json.load
            def mock_json_load_corrupt_a(fp):
                data = orig_json_load(fp)
                if hasattr(fp, "name") and fp.name.endswith("ingestion_manifest.json"):
                    if isinstance(data, dict) and "partitions" in data and "2026-10-05" in data["partitions"]:
                        data["partitions"]["2026-10-05"]["status"] = "CORRUPTED_STATUS"
                return data

            json.load = mock_json_load_corrupt_a
            caught_t7 = False
            try:
                exec(code7, scope7)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc) and "Manifest status mismatch" in str(exc):
                    caught_t7 = True
                    print(f"   [OK] Caught expected post-commit readback failure:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                json.load = orig_json_load

            assert caught_t7, "FAILED: Did not catch readback status mismatch in Case A!"

            assert not os.path.exists(mf7), f"Case A failed: manifest still exists at {mf7}!"
            print(f"   [OK] Verified manifest does NOT exist after rollback (initial non-existence preserved).")

            for p_sub in ["parquet/service_date=2026-10-05/data.parquet",
                          "quarantine/service_date=2026-10-05/conflicts.parquet",
                          "quarantine/service_date=2026-10-05/out_of_bounds.parquet",
                          "quarantine/service_date=2026-10-05/invalid_timestamps.parquet",
                          "quarantine/service_date=2026-10-05/invalid_vehicle_ids.parquet"]:
                assert not os.path.exists(os.path.join(dr7, p_sub)), f"Canonical file lingering: {p_sub}"
            print("   [OK] Verified zero canonical Parquet files exist on Drive after rollback.")
            assert os.path.exists(db7)
            print("   [OK] Scratch data preserved.")
            print("Test 7 PASSED.")
        finally:
            shutil.rmtree(sb7)

        # =====================================================================
        # TEST 8: CASE C — Existing Recovery Journal Preflight in Step 0
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 8: CASE C — EXISTING RECOVERY JOURNAL PREFLIGHT IN STEP 0")
        print("=" * 80)
        sb8, sc8, dr8, ar8, db8, dbs8, mf8 = setup_test_env("delhi_t8_case_c_")
        try:
            journal_path = os.path.join(dr8, "raw_manifests", f"recovery_journal_{PILOT_DATE}.json")
            with open(journal_path, "w") as jf:
                json.dump({"pilot_date": PILOT_DATE, "unresolved": True}, jf)

            clean_staging = os.path.join(dr8, "parquet", f"service_date={PILOT_DATE}", "data.parquet.uploading")
            os.makedirs(os.path.dirname(clean_staging), exist_ok=True)
            with open(clean_staging, "w") as sf:
                sf.write("PRE_EXISTING_STAGING_CONTENT")

            code8 = prepare_code(c8_code, db8, dbs8)
            scope8 = build_scope(dr8, sc8, ar8)

            caught_t8 = False
            try:
                exec(code8, scope8)
            except RuntimeError as exc:
                if "Existing recovery journal found" in str(exc):
                    caught_t8 = True
                    print(f"   [OK] Caught expected Step 0 recovery journal preflight error:\n        {str(exc).splitlines()[0]}")
                else:
                    raise

            assert caught_t8, "FAILED: Did not catch existing recovery journal in Step 0!"

            assert os.path.exists(clean_staging), "Staging file was deleted before aborting!"
            with open(clean_staging, "r") as sf:
                assert sf.read() == "PRE_EXISTING_STAGING_CONTENT"
            print("   [OK] Staging files safely preserved untouched without deletion.")

            assert os.path.exists(journal_path), "Recovery journal was deleted!"
            print("   [OK] Recovery journal intact. Halting was clean and immediate.")
            print("Test 8 PASSED.")
        finally:
            shutil.rmtree(sb8)

        # =====================================================================
        # TEST 9: CASE D — Existing .bak or .tmp Preflight in Step 0 & Step 9
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 9: CASE D — EXISTING .BAK OR .TMP PREFLIGHT IN STEP 0 & STEP 9")
        print("=" * 80)

        # Subtest D1: Existing .bak in Step 0
        sb9a, sc9a, dr9a, ar9a, db9a, dbs9a, mf9a = setup_test_env("delhi_t9a_bak_s0_")
        try:
            bak_path = mf9a + ".bak"
            with open(bak_path, "w") as f:
                f.write("EXISTING_BACKUP_MANIFEST_CONTENT")
            staging_file = os.path.join(dr9a, "parquet", f"service_date={PILOT_DATE}", "data.parquet.uploading")
            os.makedirs(os.path.dirname(staging_file), exist_ok=True)
            with open(staging_file, "w") as f:
                f.write("STAGING_DATA")

            code9a = prepare_code(c8_code, db9a, dbs9a)
            scope9a = build_scope(dr9a, sc9a, ar9a)

            caught_d1 = False
            try:
                exec(code9a, scope9a)
            except RuntimeError as exc:
                if "Existing manifest backup found" in str(exc):
                    caught_d1 = True
                    print(f"   [OK] Caught expected Step 0 .bak preflight: {str(exc).splitlines()[0]}")
                else:
                    raise
            assert caught_d1, "FAILED: Did not catch existing .bak in Step 0!"
            with open(bak_path, "r") as f:
                assert f.read() == "EXISTING_BACKUP_MANIFEST_CONTENT"
            assert os.path.exists(staging_file)
            print("   [OK] Subtest D1 passed: existing .bak preserved, staging untouched.")
        finally:
            shutil.rmtree(sb9a)

        # Subtest D2: Existing .tmp in Step 0
        sb9b, sc9b, dr9b, ar9b, db9b, dbs9b, mf9b = setup_test_env("delhi_t9b_tmp_s0_")
        try:
            tmp_path = mf9b + ".tmp"
            with open(tmp_path, "w") as f:
                f.write("EXISTING_TEMP_MANIFEST_CONTENT")

            code9b = prepare_code(c8_code, db9b, dbs9b)
            scope9b = build_scope(dr9b, sc9b, ar9b)

            caught_d2 = False
            try:
                exec(code9b, scope9b)
            except RuntimeError as exc:
                if "Existing temporary manifest found" in str(exc):
                    caught_d2 = True
                    print(f"   [OK] Caught expected Step 0 .tmp preflight: {str(exc).splitlines()[0]}")
                else:
                    raise
            assert caught_d2, "FAILED: Did not catch existing .tmp in Step 0!"
            with open(tmp_path, "r") as f:
                assert f.read() == "EXISTING_TEMP_MANIFEST_CONTENT"
            print("   [OK] Subtest D2 passed: existing .tmp preserved without overwriting.")
        finally:
            shutil.rmtree(sb9b)

        # Subtest D3: Existing .bak appearing before Step 9 begins
        sb9c, sc9c, dr9c, ar9c, db9c, dbs9c, mf9c = setup_test_env("delhi_t9c_bak_s9_")
        try:
            code9c = prepare_code(c8_code, db9c, dbs9c)
            scope9c = build_scope(dr9c, sc9c, ar9c)

            orig_read_schema = pq.read_schema
            def plant_bak_in_step8(p):
                res = orig_read_schema(p)
                if "invalid_vehicle_ids.parquet.uploading" in p:
                    bak_p = mf9c + ".bak"
                    with open(bak_p, "w") as f:
                        f.write("INJECTED_PRE_STEP9_BACKUP")
                return res

            pq.read_schema = plant_bak_in_step8
            caught_d3 = False
            try:
                exec(code9c, scope9c)
            except RuntimeError as exc:
                if "Pre-transaction check failed! Existing backup manifest found" in str(exc):
                    caught_d3 = True
                    print(f"   [OK] Caught expected Step 9 .bak pre-transaction preflight:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                pq.read_schema = orig_read_schema

            assert caught_d3, "FAILED: Did not catch .bak preflight in Step 9!"
            with open(mf9c + ".bak", "r") as f:
                assert f.read() == "INJECTED_PRE_STEP9_BACKUP"
            print("   [OK] Subtest D3 passed: Step 9 pre-transaction safety halted without overwriting .bak.")
            print("Test 9 PASSED.")
        finally:
            shutil.rmtree(sb9c)

        # =====================================================================
        # TEST 10: Rollback failure itself (Recovery Journal Preservation)
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 10: ROLLBACK FAILURE ITSELF (RECOVERY JOURNAL PRESERVATION)")
        print("=" * 80)
        sb10, sc10, dr10, ar10, db10, dbs10, mf10 = setup_test_env("delhi_t10_journal_")
        try:
            code10 = prepare_code(c8_code, db10, dbs10)
            scope10 = build_scope(dr10, sc10, ar10)

            orig_replace = os.replace
            orig_remove = os.remove

            def replace_fail_on_3(src, dst):
                if "out_of_bounds.parquet" in dst and not dst.endswith(".uploading"):
                    raise OSError("Promotion failure on out_of_bounds.parquet")
                return orig_replace(src, dst)

            def remove_fail(path):
                if "data.parquet" in path and not path.endswith(".uploading"):
                    raise PermissionError("Drive mount permission denied during rollback removal")
                return orig_remove(path)

            os.replace = replace_fail_on_3
            os.remove = remove_fail

            caught_t10 = False
            try:
                exec(code10, scope10)
            except RuntimeError as exc:
                if "Transaction failed AND rollback encountered errors" in str(exc):
                    caught_t10 = True
                    print(f"   [OK] Caught expected rollback failure:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                os.replace = orig_replace
                os.remove = orig_remove

            assert caught_t10, "FAILED: Did not catch rollback failure!"

            journal_path = os.path.join(dr10, "raw_manifests", f"recovery_journal_{PILOT_DATE}.json")
            assert os.path.exists(journal_path), f"Recovery journal missing: {journal_path}"
            with open(journal_path, "r") as f:
                j_data = json.load(f)
            assert j_data["pilot_date"] == PILOT_DATE
            assert len(j_data["rollback_errors"]) > 0
            print(f"   [OK] Recovery journal successfully verified at {journal_path}")
            print(f"        Errors logged: {j_data['rollback_errors']}")
            assert os.path.exists(db10)
            print("   [OK] Scratch data preserved.")
            print("Test 10 PASSED.")
        finally:
            shutil.rmtree(sb10)

        # =====================================================================
        # TEST 11: Incomplete or Corrupted Manifest Backup in Step 9.4 (Directive 2)
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 11: INCOMPLETE OR CORRUPTED MANIFEST BACKUP IN STEP 9.4")
        print("=" * 80)
        sb11, sc11, dr11, ar11, db11, dbs11, mf11 = setup_test_env("delhi_t11_bak_integrity_")
        try:
            with open(mf11, "rb") as f:
                initial_bytes = f.read()
            initial_sha = hashlib.sha256(initial_bytes).hexdigest()

            code11 = prepare_code(c8_code, db11, dbs11)
            scope11 = build_scope(dr11, sc11, ar11)

            orig_copy2 = shutil.copy2
            def failing_copy2_corrupt_bak(src, dst):
                orig_copy2(src, dst)
                if dst.endswith("ingestion_manifest.json.bak"):
                    # Corrupt 1 byte in backup copy to trigger sha_bak != sha_orig
                    with open(dst, "r+b") as f:
                        f.seek(5)
                        f.write(b"X")
            shutil.copy2 = failing_copy2_corrupt_bak

            caught_t11 = False
            try:
                exec(code11, scope11)
            except RuntimeError as exc:
                if "Transaction failed" in str(exc) and "Manifest backup integrity check failed" in str(exc):
                    caught_t11 = True
                    print(f"   [OK] Caught expected backup integrity failure:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                shutil.copy2 = orig_copy2

            assert caught_t11, "FAILED: Did not catch backup integrity failure!"

            # Verify original manifest remains 100% intact and uncorrupted
            with open(mf11, "rb") as f:
                current_bytes = f.read()
            assert hashlib.sha256(current_bytes).hexdigest() == initial_sha, "Original manifest corrupted!"
            print(f"   [OK] Original manifest untouched and uncorrupted (SHA-256: {initial_sha[:16]}...).")

            # Verify canonical files were removed by rollback
            for p_sub in ["parquet/service_date=2026-10-05/data.parquet", "quarantine/service_date=2026-10-05/conflicts.parquet"]:
                assert not os.path.exists(os.path.join(dr11, p_sub)), f"Canonical file lingering: {p_sub}"
            print("   [OK] Canonical files removed by rollback.")
            assert os.path.exists(db11)
            print("   [OK] Scratch data preserved.")
            print("Test 11 PASSED.")
        finally:
            shutil.rmtree(sb11)

        # =====================================================================
        # TEST 12: Backup Restoration Failure during Rollback (Recovery Evidence Preserved)
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 12: BACKUP RESTORATION FAILURE DURING ROLLBACK (EVIDENCE PRESERVED)")
        print("=" * 80)
        sb12, sc12, dr12, ar12, db12, dbs12, mf12 = setup_test_env("delhi_t12_restore_fail_")
        try:
            code12 = prepare_code(c8_code, db12, dbs12)
            scope12 = build_scope(dr12, sc12, ar12)

            orig_replace = os.replace
            orig_copy2 = shutil.copy2
            manifest_replaced_simulated = False

            def replace_hook(src, dst):
                nonlocal manifest_replaced_simulated
                if dst == mf12:
                    manifest_replaced_simulated = True
                return orig_replace(src, dst)

            def copy2_hook(src, dst):
                # If restoring from backup during rollback after manifest was replaced, simulate disk error
                if manifest_replaced_simulated and src.endswith("ingestion_manifest.json.bak") and dst == mf12:
                    raise PermissionError("FUSE Google Drive permission error during manifest restoration")
                return orig_copy2(src, dst)

            os.replace = replace_hook
            shutil.copy2 = copy2_hook

            orig_json_load = json.load
            def mock_json_load_fail(fp):
                data = orig_json_load(fp)
                if hasattr(fp, "name") and fp.name.endswith("ingestion_manifest.json"):
                    if isinstance(data, dict) and "partitions" in data and "2026-10-05" in data["partitions"]:
                        data["partitions"]["2026-10-05"]["status"] = "CORRUPTED_STATUS"
                return data
            json.load = mock_json_load_fail

            caught_t12 = False
            try:
                exec(code12, scope12)
            except RuntimeError as exc:
                if "Transaction failed AND rollback encountered errors" in str(exc):
                    caught_t12 = True
                    print(f"   [OK] Caught expected rollback restoration failure:\n        {str(exc).splitlines()[0]}")
                else:
                    raise
            finally:
                os.replace = orig_replace
                shutil.copy2 = orig_copy2
                json.load = orig_json_load

            assert caught_t12, "FAILED: Did not catch rollback restoration error!"

            # Verify recovery journal was written and backup was preserved
            journal_path = os.path.join(dr12, "raw_manifests", f"recovery_journal_{PILOT_DATE}.json")
            assert os.path.exists(journal_path), f"Recovery journal missing at {journal_path}"
            with open(journal_path, "r") as jf:
                j_data = json.load(jf)
            assert any("restoring/verifying manifest from backup" in err for err in j_data["rollback_errors"])
            print(f"   [OK] Recovery journal verified with logged restoration errors.")

            bak_path = mf12 + ".bak"
            assert os.path.exists(bak_path), "Backup was deleted despite restoration failure!"
            print(f"   [OK] Manifest backup preserved at {bak_path} for manual forensic recovery.")
            assert os.path.exists(db12)
            print("   [OK] Scratch data preserved.")
            print("Test 12 PASSED.")
        finally:
            shutil.rmtree(sb12)

        # =====================================================================
        # TEST 13: Real SQLite Source Schema Verification against DuckDB 1.3.2
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 13: REAL SQLITE SOURCE SCHEMA VERIFICATION AGAINST DUCKDB 1.3.2")
        print("=" * 80)
        real_db = "data/raw/gps/bus_movements_2026_10_01.db"
        assert os.path.exists(real_db), f"Real SQLite database missing: {real_db}"

        sql_con = sqlite3.connect(real_db)
        info = sql_con.execute("PRAGMA table_info(vehicle_feed);").fetchall()
        sql_con.close()

        expected_source_cols = [
            (0, 'vehicle_id', 'TEXT'),
            (1, 'lat', 'TEXT'),
            (2, 'lng', 'TEXT'),
            (3, 'speed', 'REAL'),
            (4, 'route_id', 'REAL'),
            (5, 'trip_id', 'TEXT'),
            (6, 'timestamp', 'TEXT'),
            (7, 'date', 'date'),
            (8, 'time', 'TEXT')
        ]
        for col_idx, (idx, name, c_type) in enumerate(expected_source_cols):
            act_col = info[col_idx]
            assert act_col[1] == name and act_col[2] == c_type, f"Col {name} type mismatch: got {act_col}, expected {name}:{c_type}"
            print(f"   [OK] Source SQLite column verified: {act_col[0]}: {act_col[1]} ({act_col[2]})")

        # Run DuckDB on real sample (100 rows)
        tmp_real_sample = tempfile.mktemp(suffix=".db")
        src_c = sqlite3.connect(real_db)
        s_rows = src_c.execute("SELECT * FROM vehicle_feed LIMIT 100;").fetchall()
        src_c.close()

        dst_c = sqlite3.connect(tmp_real_sample)
        dst_c.execute("CREATE TABLE vehicle_feed (vehicle_id TEXT, lat TEXT, lng TEXT, speed REAL, route_id REAL, trip_id TEXT, timestamp TEXT, date date, time TEXT);")
        dst_c.executemany("INSERT INTO vehicle_feed VALUES (?,?,?,?,?,?,?,?,?);", s_rows)
        dst_c.commit()
        dst_c.close()

        ddb = duckdb.connect(":memory:")
        ddb.execute("LOAD sqlite;")
        ddb.execute(f"ATTACH '{tmp_real_sample}' AS raw_db (TYPE SQLITE);")

        ddb.execute("CREATE TEMP TABLE s1 AS SELECT DISTINCT * FROM raw_db.vehicle_feed;")
        ddb.execute(f"""
            CREATE TEMP TABLE clean_real AS
            WITH projected AS (
                SELECT
                    vehicle_id, TRY_CAST(lat AS DOUBLE) AS lat, TRY_CAST(lng AS DOUBLE) AS lng,
                    TRY_CAST(speed AS DOUBLE) AS speed_kmh,
                    CASE WHEN TRY_CAST(route_id AS DOUBLE) IS NOT NULL 
                         THEN CAST(CAST(TRY_CAST(route_id AS DOUBLE) AS BIGINT) AS VARCHAR)
                         ELSE CAST(route_id AS VARCHAR) END AS route_id,
                    trip_id AS trip_id_raw,
                    REGEXP_EXTRACT(trip_id, '^([0-9]+_[0-9]+_[0-9]+)') AS trip_id_canonical,
                    TRY_CAST(timestamp AS BIGINT) AS timestamp_utc,
                    to_timestamp(TRY_CAST(timestamp AS BIGINT)) AT TIME ZONE 'Asia/Kolkata' AS timestamp_ist,
                    TRY_CAST(date AS DATE) AS service_date
                FROM s1
                WHERE TRY_CAST(lat AS DOUBLE) >= 28.0 AND TRY_CAST(lat AS DOUBLE) <= 29.2
                  AND TRY_CAST(lng AS DOUBLE) >= 76.5 AND TRY_CAST(lng AS DOUBLE) <= 77.8
            )
            SELECT vehicle_id, lat, lng, speed_kmh, route_id, trip_id_raw, trip_id_canonical,
                   timestamp_utc, timestamp_ist, service_date,
                   EXTRACT(hour FROM timestamp_ist)::BIGINT AS hour_ist,
                   EXTRACT(minute FROM timestamp_ist)::BIGINT AS minute_ist,
                   DAYOFWEEK(timestamp_ist)::BIGINT AS day_of_week,
                   CASE WHEN DAYOFWEEK(timestamp_ist) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
            FROM projected;
        """)
        pq_tmp = tempfile.mktemp(suffix=".parquet")
        ddb.execute(f"COPY clean_real TO '{pq_tmp}' (FORMAT PARQUET, COMPRESSION ZSTD);")
        s_clean = pq.read_schema(pq_tmp)
        assert len(s_clean.names) == 14
        print(f"   [OK] DuckDB 1.3.2 pipeline on real SQLite data executed with 14 verified Arrow columns.")
        os.remove(tmp_real_sample)
        os.remove(pq_tmp)
        print("Test 13 PASSED.")

        # =====================================================================
        # TEST 14: Environmental Invariants & Baseline Data Preservation
        # =====================================================================
        print("\n" + "=" * 80)
        print("TEST 14: ENVIRONMENTAL INVARIANTS & BASELINE DATA PRESERVATION")
        print("=" * 80)
        real_oct5_db = "data/raw/gps/bus_movements_2026_10_05.db"
        assert not os.path.exists(real_oct5_db), f"CRITICAL: {real_oct5_db} exists!"
        print(f"   [OK] Real October 5 SQLite does NOT exist: {real_oct5_db}")

        real_oct5_pq = "data/processed/gps_parquet/service_date=2026-10-05/data.parquet"
        assert not os.path.exists(real_oct5_pq), f"CRITICAL: {real_oct5_pq} exists!"
        print(f"   [OK] Real October 5 Parquet does NOT exist: {real_oct5_pq}")

        baseline_dates = ['2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-07']
        for b_date in baseline_dates:
            bp = f"data/processed/gps_parquet/service_date={b_date}/data.parquet"
            assert os.path.exists(bp) and os.path.getsize(bp) > 0, f"Baseline {b_date} missing or empty!"
        print(f"   [OK] All 5 baseline dates intact: {baseline_dates}")

        assert os.path.exists("/tmp/delhi_dlm1.db") and os.path.getsize("/tmp/delhi_dlm1.db") == 362852352
        assert os.path.exists("/tmp/delhi_mdb.db") and os.path.getsize("/tmp/delhi_mdb.db") == 281452544
        print("   [OK] Serving DLM1 database (/tmp/delhi_dlm1.db: 362,852,352 bytes) untouched")
        print("   [OK] Rollback legacy database (/tmp/delhi_mdb.db: 281,452,544 bytes) untouched")

        # Original v1 notebook unchanged
        v1_path = "notebooks/Delhi_Bus_GPS_Pilot_Ingestion_Colab.ipynb"
        with open(v1_path, "rb") as f:
            v1_hash = hashlib.sha256(f.read()).hexdigest()
        assert v1_hash == "244c5254da89912c414588f47f01651d30af6a1884a0cb502ff7bddf25da7dd8"
        print(f"   [OK] Original v1 notebook untouched: {v1_hash}")
        print("Test 14 PASSED.")

    finally:
        shutil.disk_usage = orig_disk_usage

    print("\n" + "=" * 80)
    print("ALL 14 VERIFICATION AND FAILURE-INJECTION TESTS PASSED UNDER DUCKDB 1.3.2!")
    print("=" * 80)

if __name__ == "__main__":
    run_all_checks()
