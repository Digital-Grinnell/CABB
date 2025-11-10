#!/bin/bash

# Alma-D Bulk Bib Records Editor - Quick Launch Script
# This script sets up the virtual environment and launches the Flet app

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Alma-D Bulk Bib Records Editor ==="
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
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
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
echo "Launching Alma-D Bulk Bib Records Editor..."
echo
python app.py
