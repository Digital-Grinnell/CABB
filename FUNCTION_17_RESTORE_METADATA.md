# Function 17: Restore Metadata from Previous Version

## Status

ACTIVE IN BRANCH: Chrome-Selenium

**MILESTONE ACHIEVED (2026-03-17):** Successfully completes end-to-end metadata restore with batch processing.

Function 17 is enabled in this branch and launches Chrome via Selenium. The automation successfully:
- Searches for records by MMS ID
- Opens records in Metadata Editor (MDE)
- Navigates the Angular Material menu: View Related Data → View Versions
- Intelligently selects the correct version to restore (validates Subjects field)
- Clicks "Restore Metadata" button to restore and save the selected metadata version
- Navigates back to Alma home page ready for next record (batch processing enabled)

## Purpose

Restore bibliographic metadata from a previous version in Alma by automating the MDE flow:

1. Search record by MMS ID
2. Click into the bib record from search results
3. Open record in Metadata Editor (MDE)
4. Navigate: View Related Data → View Versions
5. Select the most recent version with valid metadata (has title and subjects)
6. Restore the selected version (saves automatically in Alma)
7. Navigate back to Alma home page for next record
8. Write per-record results to a CSV report

**Batch Processing:**
- Processes multiple MMS IDs from CSV in a single browser session
- Browser stays open throughout the batch
- Each record is restored sequentially with progress updates

**Version Selection Logic:**
- The automation examines versions from newest to oldest
- Selects the first version containing "Subjects:" field (plural with colon)
- Versions without "Subjects:" are skipped as they lack complete bibliographic metadata

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
	- Search field: MMS ID
- Function processes one or many records and writes a CSV report to Downloads.

## Current Notes

- The Alma REST API endpoint /bibs/{mms_id}/versions is still unavailable (404 in this environment), so Function 17 uses UI automation.
- Function 17 is configured to run direct Selenium automation in Chrome without a manual recorder handoff.
- Progress messages displayed in terminal for each step of the automation process.

## Technical Details

**Key implementation notes from development:**

1. **Angular Material Menu Navigation:**
   - The "View Related Data" and "View Versions" menus use Angular Material components
   - Direct ID-based element selection: `SubMenuItem_menu_records_viewRelatedData_viewVersions`
   - Menu items contain `span.menu-label` elements with the visible text

2. **Frame Context Management:**
   - The MDE content itself loads in `yards_iframe`
   - The dropdown menus render in the PARENT frame context (not inside yards_iframe)
   - Critical: Must stay in parent context when clicking menu items
   - Only switch to yards_iframe when interacting with the versions panel content

3. **ChromeDriver Setup (macOS):**
   - After installing via Homebrew, remove quarantine attribute:
     ```bash
     xattr -d com.apple.quarantine /opt/homebrew/bin/chromedriver
     ```
   - ChromeDriver version must match installed Chrome browser version

4. **Restore and Save:**
   - Searches for actual `<button>` elements with text "Restore Metadata" (not just any element containing "Restore")
   - Clicking "Restore Metadata" automatically saves the changes in Alma
   - No manual Save or Save and Release Record step required
   - May show confirmation dialog that requires clicking "Confirm" or "OK"
   - After restore, navigates back to Alma home page to prepare for next record in batch

5. **Version Selection:**
   - Examines each version container's text to validate metadata quality
   - Requires "Subjects:" field (plural with colon) to confirm valid bibliographic record
   - Selects the most recent (topmost) version containing "Subjects:"
   - Falls back to first version if no version passes validation

## Output

Report directory pattern:

- ~/Downloads/CABB_restore_metadata_YYYYMMDD_HHMMSS/

Report file pattern:

- metadata_restore_report_YYYYMMDD_HHMMSS.csv

CSV columns:

- MMS ID
- Status
- Message
