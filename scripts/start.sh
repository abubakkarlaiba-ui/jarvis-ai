#!/usr/bin/env bash
# JARVIS AI Assistant — Startup Script (Linux/macOS)
# ====================================================
# Usage:
#   ./start.sh              Start in default mode (terminal + API)
#   ./start.sh --mode api   Start API server only
#   ./start.sh --mode terminal   Start terminal UI only
#   ./start.sh --debug      Start with debug logging

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env with your API keys before running."
    exit 1
fi

# Ensure data directories exist
mkdir -p data/logs data/vector_store data/models data/knowledge plugins

# Activate virtual environment if present
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo "Starting JARVIS..."
python -m jarvis "$@"
