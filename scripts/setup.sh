#!/usr/bin/env bash
# JARVIS AI Assistant — Development Setup Script
# =================================================
# Sets up the development environment from scratch.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== JARVIS Development Setup ==="

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create .env
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ">>> Edit .env to add your API keys <<<"
fi

# Create data directories
echo "Creating data directories..."
mkdir -p data/logs data/vector_store data/models data/knowledge plugins

echo ""
echo "=== Setup complete! ==="
echo "Run: ./scripts/start.sh"
