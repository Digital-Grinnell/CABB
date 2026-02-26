#!/bin/bash
#
# Start Firefox for Selenium (Function 14b)
#
# This script starts Firefox with the --marionette flag enabled,
# which allows Selenium to connect to your existing Firefox session.
#
# Usage:
#   ./start_firefox_for_selenium.sh
#
# After Firefox opens:
#   1. Log into Alma
#   2. Navigate to the Alma home page
#   3. Run Function 14b in CABB
#

echo "🦊 Starting Firefox with Marionette enabled for Selenium..."
echo ""
echo "After Firefox opens:"
echo "  1. Log into Alma"
echo "  2. Navigate to: https://grinnell.alma.exlibrisgroup.com/ng;u=%2Fmng%2Faction%2Fhome.do%3FngHome%3Dtrue"
echo "  3. Run Function 14b in CABB"
echo ""

# Detect operating system and start Firefox appropriately
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "Starting Firefox on macOS..."
    open -a Firefox --args --marionette
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "Starting Firefox on Linux..."
    firefox --marionette &
else
    echo "❌ Unsupported operating system: $OSTYPE"
    echo "Please start Firefox manually with: firefox --marionette"
    exit 1
fi

echo ""
echo "✅ Firefox started with Marionette enabled"
echo "   Selenium can now connect to your Firefox session"
echo ""
