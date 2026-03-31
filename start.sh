#!/usr/bin/env bash
# Start the Container Mapping Tool web app.
# Usage: ./start.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check for .env
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your API keys."
    exit 1
fi

# Create virtualenv if it doesn't exist
if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtualenv
source .venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Starting Container Mapper on http://localhost:8501"
streamlit run app.py --browser.gatherUsageStats false
