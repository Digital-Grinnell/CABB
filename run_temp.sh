#!/bin/bash

# Temporary workaround for SSL issues
# This script uses pip without SSL verification

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Crunch Alma Bibs in Bulk (CABB) - Temporary SSL Workaround ==="
echo

# Try to use system Python 3.9 which should have SSL
if [ -f "/usr/bin/python3" ]; then
    PYTHON_CMD="/usr/bin/python3"
    echo "Using system Python: $PYTHON_CMD"
else
    echo "Error: System Python not found"
    exit 1
fi

# Check if .venv exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
    echo "✓ Virtual environment created"
    echo
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✓ Virtual environment activated"
echo

# Install/upgrade dependencies with SSL workaround
echo "Installing dependencies (bypassing SSL - TEMPORARY FIX)..."
python -m pip install --upgrade pip --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
python -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
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
python app.py
