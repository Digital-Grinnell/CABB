# Function 17: Restore Metadata from Previous Version

## Status

ACTIVE IN BRANCH: Chrome-Selenium

Function 17 is enabled in this branch and now launches Chrome via Selenium.

## Purpose

Restore bibliographic metadata from a previous version in Alma by automating the MDE flow:

1. Search record by MMS number
2. Open record in Metadata Editor (MDE)
3. Open Record Actions > View Related Data > View Versions
4. Restore the most recent prior (non-current) version
5. Write per-record results to a CSV report

## Prerequisites

- Chrome installed
- ChromeDriver installed on macOS:
	- brew install --cask chromedriver
- Valid Alma SSO access
- DUO device available

Optional environment variables for SSO prefill:

- SSO_USERNAME
- SSO_PASSWORD

## Expected Runtime Behavior

- CABB opens a new Chrome window for Selenium.
- You complete SSO/DUO if needed.
- Before processing, set Alma search bar to:
	- Search type: All titles
	- Search field: MMS number
- Function processes one or many records and writes a CSV report to Downloads.

## Current Notes

- The Alma REST API endpoint /bibs/{mms_id}/versions is still unavailable (404 in this environment), so Function 17 uses UI automation.
- Function 17 is configured to run direct Selenium automation in Chrome without a manual recorder handoff.

## Output

Report directory pattern:

- ~/Downloads/CABB_restore_metadata_YYYYMMDD_HHMMSS/

Report file pattern:

- metadata_restore_report_YYYYMMDD_HHMMSS.csv

CSV columns:

- MMS ID
- Status
- Message
