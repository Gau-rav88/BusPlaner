"""
Unit and Integration Tests for GTFS Ingestion and Validation
Milestone 1 Deliverable
"""

import os
import sqlite3
import pytest
import pandas as pd
from scripts.ingest_gtfs import parse_time_to_seconds, ingest_gtfs

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEST_GTFS_DIR = os.path.join(ROOT_DIR, "data", "raw", "gtfs")
TEST_DB_PATH = os.path.join(ROOT_DIR, "data", "serving", "delhi_bus.db")


def test_time_conversion():
    assert parse_time_to_seconds("00:00:00") == 0
    assert parse_time_to_seconds("01:00:00") == 3600
    assert parse_time_to_seconds("06:05:00") == 21900
    # Test post-midnight GTFS time
    assert parse_time_to_seconds("24:15:30") == 87330
    assert parse_time_to_seconds("25:30:00") == 91800
    # Invalid
    assert parse_time_to_seconds("invalid") == -1


def test_gtfs_serving_database():
    assert os.path.exists(TEST_DB_PATH), "Serving database must exist"
    conn = sqlite3.connect(TEST_DB_PATH)
    cur = conn.cursor()

    # Verify tables exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {r[0] for r in cur.fetchall()}
    assert "routes" in tables
    assert "stops" in tables
    assert "trips" in tables
    assert "stop_times" in tables
    assert "calendar" in tables

    # Verify indexes exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = {r[0] for r in cur.fetchall()}
    assert "idx_routes_id" in indexes
    assert "idx_stops_id" in indexes
    assert "idx_trips_id" in indexes
    assert "idx_stop_times_trip" in indexes

    # Verify UTM coordinates populated on stops
    cur.execute("SELECT stop_id, stop_lat, stop_lon, utm_x, utm_y FROM stops LIMIT 5;")
    rows = cur.fetchall()
    assert len(rows) > 0
    for r in rows:
        assert r[3] > 0, "UTM X must be positive"
        assert r[4] > 0, "UTM Y must be positive"

    # Verify route_id normalization
    cur.execute("SELECT route_id FROM routes LIMIT 10;")
    route_ids = [r[0] for r in cur.fetchall()]
    for rid in route_ids:
        assert not str(rid).endswith(".0"), f"route_id {rid} must be normalized without .0"

    conn.close()


def test_full_mdb_referential_integrity():
    """Validates the complete MobilityData open transit dataset if present."""
    mdb_db = "/tmp/delhi_mdb.db"
    if not os.path.exists(mdb_db):
        pytest.skip("/tmp/delhi_mdb.db not generated yet")

    conn = sqlite3.connect(mdb_db)
    cur = conn.cursor()

    # Zero orphan trips
    cur.execute("""
        SELECT COUNT(*)
        FROM trips t
        LEFT JOIN routes r ON t.route_id = r.route_id
        WHERE r.route_id IS NULL;
    """)
    assert cur.fetchone()[0] == 0, "No trips should exist without a route"

    # Zero orphan stop_times
    cur.execute("""
        SELECT COUNT(*)
        FROM stop_times st
        LEFT JOIN trips t ON st.trip_id = t.trip_id
        WHERE t.trip_id IS NULL;
    """)
    assert cur.fetchone()[0] == 0, "No stop_times should exist without a trip"

    conn.close()

