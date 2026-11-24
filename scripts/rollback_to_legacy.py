#!/usr/bin/env python3
"""Milestone 11.2: Reproducible Rollback Script to Legacy Database.

This script restores the legacy GTFS database (/tmp/delhi_mdb.db)
as the primary runtime database if cutover rollback is required.

Rules & Constraints:
- By default runs in --dry-run mode (does not alter running config unless --execute is passed).
- Never deletes or modifies /tmp/delhi_dlm1.db.
- Verifies database integrity and scale before switching back.
"""

import argparse
import os
import sqlite3
import sys

PRIMARY_DLM1_PATH = "/tmp/delhi_dlm1.db"
LEGACY_MDB_PATH = "/tmp/delhi_mdb.db"
ENV_PATH = ".env"


def verify_rollback_preconditions():
    """Verify that legacy database is available and valid."""
    print("1. Verifying legacy database availability for rollback...")
    if not os.path.exists(LEGACY_MDB_PATH):
        raise FileNotFoundError(f"Legacy database not found at {LEGACY_MDB_PATH}")

    size_mb = os.path.getsize(LEGACY_MDB_PATH) / (1024 * 1024)
    print(f"   Legacy database size: {size_mb:.2f} MB")

    conn = sqlite3.connect(LEGACY_MDB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM stops;")
    stops = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM routes;")
    routes = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM trips;")
    trips = cur.fetchone()[0]

    conn.close()

    print(f"   Stops: {stops}, Routes: {routes}, Trips: {trips}")
    assert stops == 6342, "Legacy stops count mismatch"
    assert routes == 2964, "Legacy routes count mismatch"
    assert trips == 78515, "Legacy trips count mismatch"
    print("   Rollback preconditions: PASSED")


def execute_rollback(dry_run: bool = True):
    """Execute or simulate database rollback."""
    print("\n=== Milestone 11.2 Database Rollback Execution ===")
    verify_rollback_preconditions()

    if dry_run:
        print("\n[DRY RUN MODE]: Rollback preconditions verified. No configuration changes applied.")
        print("To execute rollback when needed, pass: python3 scripts/rollback_to_legacy.py --execute")
        return True

    print("\n2. Restoring environment configuration to legacy database...")
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("DB_PATH="):
            new_lines.append(f"DB_PATH={LEGACY_MDB_PATH}\n")
        elif line.startswith("HISTORICAL_LEGACY_DB_PATH="):
            continue  # Remove auxiliary setting
        else:
            new_lines.append(line)

    with open(ENV_PATH, "w") as f:
        f.writelines(new_lines)

    print(f"   Updated {ENV_PATH}: DB_PATH={LEGACY_MDB_PATH}")
    print("3. Restart backend server to apply rollback.")
    print("   Rollback completed successfully.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Legacy Database Rollback Script")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute actual rollback. If omitted, runs in safe dry-run mode.",
    )
    args = parser.parse_args()

    try:
        execute_rollback(dry_run=not args.execute)
    except Exception as e:
        print(f"Rollback failed: {e}", file=sys.stderr)
        sys.exit(1)

