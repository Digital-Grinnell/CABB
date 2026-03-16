# Function 17: Restore Metadata from Previous Version

## Overview

Function 17 attempts to restore Alma bibliographic metadata for one or more records by calling Alma API version-history endpoints.

For each MMS ID, CABB will:
1. Fetch the record's version history
2. Select the most recent non-current version
3. Attempt a metadata restore to that version
4. Write a detailed CSV report

## Why This Function Exists

Function 11 CSV overlay workflows can overwrite or remove metadata unexpectedly. This function is intended as a bulk recovery path when records need to be rolled back to earlier metadata versions.

## Important Safety Notes

- This function modifies bibliographic metadata in Alma.
- Always test with a small sample first.
- Use the generated report CSV to verify outcomes.
- If API restore is unavailable for your Alma environment, use manual fallback in MDE:
  - View Related Data
  - View Versions
  - Restore Metadata

## Input Modes

### Single Record

- Enter one MMS ID in the MMS ID field
- Run Function 17

### Batch Mode

- Load a Set or CSV of MMS IDs
- Run Function 17 to process all loaded IDs

## Output

A timestamped report is created in:

`~/Downloads/CABB_restore_metadata_YYYYMMDD_HHMMSS/`

Report file:

`metadata_restore_report_YYYYMMDD_HHMMSS.csv`

### Report Columns

- `MMS ID`
- `Status` (`Success` or `Failed`)
- `Restored Version ID`
- `Message`
- `Manual Restore Hint`

## Typical Failure Scenarios

- API key lacks permissions for versions/restore operations
- Versions endpoint not enabled in your Alma environment
- Record has no usable prior version
- Restore endpoint shape differs from your Alma tenant

When failures occur, use the report CSV as your manual worklist.

## Recommended Workflow

1. Run Function 17 on 3-5 known affected records
2. Inspect report CSV and verify records in Alma
3. If successful, run on full set
4. Manually restore any failures using MDE version history
