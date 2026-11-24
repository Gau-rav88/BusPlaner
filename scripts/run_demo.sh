#!/usr/bin/env bash
# ==============================================================================
# Run Demo Script - Delhi Real-Time Bus Traffic Model & Journey Planner
# Demonstrates API endpoints, live bus tracking, and provides access links.
# ==============================================================================

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "======================================================================"
echo "DELHI BUS JOURNEY PLANNER — AUTOMATED DEMONSTRATION"
echo "======================================================================"

source venv/bin/activate
export DB_PATH=/tmp/delhi_dlm1.db

# 1. Verify Backend Health
echo ""
echo "[Step 1/4] Checking Backend API Health on Port 8000..."
HEALTH_STATUS=$(curl -s http://127.0.0.1:8000/api/v1/health | grep -o '"overall_operational_status":"[^"]*"' || echo "offline")
echo "  Backend Health Response: $HEALTH_STATUS"

if [[ "$HEALTH_STATUS" == "offline" || -z "$HEALTH_STATUS" ]]; then
    echo "  Backend is not running. Starting uvicorn backend on port 8000..."
    uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 > /tmp/uvicorn_demo.log 2>&1 &
    BACKEND_PID=$!
    echo "  Waiting for backend startup (PID $BACKEND_PID)..."
    sleep 3
fi

# 2. Check Live Feed Status
echo ""
echo "[Step 2/4] Checking Real-Time Delhi Transport Stack GTFS-RT Telemetry..."
LIVE_STATUS=$(curl -s http://127.0.0.1:8000/api/v1/live/status)
ACTIVE_COUNT=$(python3 -c "import json; d = json.loads('''$LIVE_STATUS'''); print(d.get('active_vehicles_count', 0))")
FEED_STATUS=$(python3 -c "import json; d = json.loads('''$LIVE_STATUS'''); print(d.get('feed_availability_status', 'UNKNOWN'))")
echo "  Feed Status: $FEED_STATUS"
echo "  Active GPS Vehicles: $ACTIVE_COUNT buses currently reporting"

# 3. Demonstrate Journey Planning on Route 641 (High-Frequency Live Corridor)
echo ""
echo "[Step 3/4] Demonstrating Journey Planning & Suitable Bus Matching (Route 641)..."
PLAN_PAYLOAD='{
  "origin_stop_id": "3572",
  "dest_stop_id": "3640",
  "departure_date": "2026-10-01",
  "departure_time": "08:00:00",
  "allow_assumed_recurring": true,
  "max_transfers": 2
}'

PLAN_RES=$(curl -s -X POST http://127.0.0.1:8000/api/v1/journeys/plan \
  -H "Content-Type: application/json" \
  -d "$PLAN_PAYLOAD")

JOURNEYS_COUNT=$(python3 -c "import json; d = json.loads('''$PLAN_RES'''); print(len(d.get('journeys', [])))")
echo "  Returned Journeys: $JOURNEYS_COUNT direct/transfer route options"

SUITABLE_RES=$(curl -s "http://127.0.0.1:8000/api/v1/live/suitable-vehicles?route_id=641&board_stop_id=3572&alight_stop_id=3640")
SUITABLE_COUNT=$(python3 -c "import json; d = json.loads('''$SUITABLE_RES'''); print(d.get('suitable_count', len(d.get('vehicles', []))))")
echo "  Verified Approaching Pickup Buses on Corridor: $SUITABLE_COUNT buses"

# 4. Demonstrate Historic Route 1598
echo ""
echo "[Step 4/4] Demonstrating Historic North GT Road Corridor (Route 1598)..."
SUITABLE_1598=$(curl -s "http://127.0.0.1:8000/api/v1/live/suitable-vehicles?route_id=1598&board_stop_id=7572&alight_stop_id=1010")
SUITABLE_1598_COUNT=$(python3 -c "import json; d = json.loads('''$SUITABLE_1598'''); print(d.get('suitable_count', len(d.get('vehicles', []))))")
DIAGNOSTIC_1598=$(python3 -c "import json; d = json.loads('''$SUITABLE_1598'''); print(d.get('diagnostic_detail') or d.get('fallback_message') or 'All current vehicles on route have already passed boarding stop or are off-corridor.')")
echo "  Route 1598 Suitable Approaching Buses: $SUITABLE_1598_COUNT"
echo "  Diagnostic Explanation: $DIAGNOSTIC_1598"

echo ""
echo "======================================================================"
echo "DEMO APPLICATION ACCESS LINKS"
echo "======================================================================"
echo "  Web Interface:   http://localhost:3000/"
echo "  FastAPI Docs:    http://localhost:8000/docs"
echo "  Health Status:   http://localhost:8000/api/v1/health"
echo "  Live Telemetry:  http://localhost:8000/api/v1/live/status"
echo "======================================================================"
