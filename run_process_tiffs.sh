#!/bin/bash
# Wrapper script to run process_tiffs_for_import.py using the project's virtual environment

# Navigate to the script directory
cd "$(dirname "$0")"

# Run the script with the virtual environment's Python
.venv/bin/python process_tiffs_for_import.py
