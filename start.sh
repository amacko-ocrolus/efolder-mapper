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

# Check for dependencies
if ! python3 -c "import streamlit" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo "Starting Container Mapper on http://0.0.0.0:8501"
streamlit run app.py --browser.gatherUsageStats false
