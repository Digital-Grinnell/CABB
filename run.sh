#!/bin/bash

# Clean Alma Bibs in Bulk (CABB) - Quick Launch Script
# This script sets up the virtual environment and launches the Flet app

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Clean Alma Bibs in Bulk (CABB) ==="
echo

# Check if .venv exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
    echo
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo

# Install/upgrade dependencies
echo "Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet
echo "✓ Dependencies installed"
echo

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠ Warning: .env file not found!"
    echo "Creating .env template..."
    cat > .env << 'EOF'
# Alma API Configuration
ALMA_API_KEY=your_api_key_here
ALMA_API_URL=https://api-na.hosted.exlibrisgroup.com
EOF
    echo "✓ .env template created"
    echo "  Please edit .env file and add your Alma API key"
    echo
fi

# Launch the app
echo "Launching CABB..."
echo
.venv/bin/python app.py
