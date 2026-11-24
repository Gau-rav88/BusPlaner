#!/usr/bin/env bash
# ==============================================================================
# Setup Script - Delhi Real-Time Bus Traffic Model & Journey Planner
# Sets up Python virtual environment, dependencies, GTFS database, and frontend.
# ==============================================================================

set -e

echo "=== Delhi Bus Journey Planner: Setup Starting ==="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# 1. Environment & Prerequisites Check
echo "--> Checking environment prerequisites..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 could not be found. Python 3.10+ is required."
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "ERROR: node could not be found. Node.js 18+ is required."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python: $PYTHON_VERSION"
echo "Detected Node.js: $(node --version)"

# 2. Python Virtual Environment Setup
if [ ! -d "venv" ]; then
    echo "--> Creating Python virtual environment in ./venv..."
    python3 -m venv venv
else
    echo "--> Using existing Python virtual environment in ./venv..."
fi

source venv/bin/activate
echo "--> Upgrading pip and installing backend dependencies..."
pip install --upgrade pip -q
pip install -r backend/requirements.txt -q

# 3. Environment File Configuration
if [ ! -f ".env" ]; then
    echo "--> Creating .env from .env.example..."
    cp .env.example .env
    echo "    Created .env. Add your DELHI_TRANSPORTSTACK_API_KEY in .env if desired."
else
    echo "--> Found existing .env file."
fi

# 4. Serving Database Setup (DLM1 Static GTFS SQLite)
DB_TARGET="/tmp/delhi_dlm1.db"
if [ ! -f "$DB_TARGET" ]; then
    echo "--> DLM1 database not found at $DB_TARGET. Building from static GTFS archive..."
    if [ -f "data/external/delhi_buses_static_gtfs_v1.zip" ]; then
        python3 scripts/build_staged_dlm1.py
    elif [ -f "data/external/delhi_buses_static_gtfs_v1 (1).zip" ]; then
        cp "data/external/delhi_buses_static_gtfs_v1 (1).zip" "data/external/delhi_buses_static_gtfs_v1.zip"
        python3 scripts/build_staged_dlm1.py
    else
        echo "WARNING: Static GTFS zip archive not found in data/external/. Please place delhi_buses_static_gtfs_v1.zip in data/external/"
    fi
else
    echo "--> Found active DLM1 SQLite database at $DB_TARGET ($(du -h $DB_TARGET | cut -f1))."
fi

# 5. Frontend Dependencies & Build
echo "--> Installing frontend dependencies..."
cd frontend
npm install --silent
echo "--> Building frontend production bundle..."
npm run build
cd "$ROOT_DIR"

echo ""
echo "=== Setup Completed Successfully ==="
echo "To start the application:"
echo "  1. Backend (FastAPI, Port 8000):"
echo "     source venv/bin/activate && export DB_PATH=/tmp/delhi_dlm1.db && uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
echo "  2. Frontend (Vite, Port 3000):"
echo "     cd frontend && npm run dev"
echo "  Or run the automated demo:"
echo "     bash scripts/run_demo.sh"
echo "======================================"
