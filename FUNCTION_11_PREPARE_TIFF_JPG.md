# Function 11: TIFF/JPG Representations — Full API Method

**Last Updated:** March 23, 2026  
**Branch:** `Function-11-API`  
**Function Status:** Active — Full API approach (no Digital Uploader required)  
**Based on:** Harvard/Corinna LibraryTechServices spec + Alma Representations REST API  
**Archive of previous approach:** `FUNCTION_11_PREPARE_TIFF_JPG_CSV-Method-Archive.md`

---

## Overview

**Function 11** creates DERIVATIVE_COPY JPEG representations on Alma bib records and populates them with JPG derivatives converted from local TIFF files — **entirely via the Alma API and ExLibris S3 bucket**. No manual Digital Uploader steps, no local output directory, no `values.csv`.

### What it does, end-to-end

For each MMS ID in the loaded set:

1. Look up the local TIFF file path from `all_single_tiffs_with_local_paths.csv`
2. Convert the TIFF to a JPG (in a temporary directory, auto-cleaned)
3. Upload the JPG to the ExLibris-managed AWS S3 bucket under `{institution_code}/upload/`
4. Check the Alma bib record for an existing DERIVATIVE_COPY / JPG representation:
   - **Rep has a file already** → **SKIP** the record. Log the state, make no changes.
   - **Rep exists but is empty** → POST the new JPG file into it
   - **No matching rep exists** → POST to create a new DERIVATIVE_COPY rep, then POST the JPG file
5. Temporary JPG files are automatically deleted when the batch finishes

---

## Prerequisites

### Required `.env` variables

Add these to the `.env` file in the CABB workspace (see `.env.example` for the full template):

```
ALMA_API_KEY=your_alma_api_key
ALMA_API_REGION=America
ALMA_INSTITUTION_CODE=01GCL_INST            # Your institution code
ALMA_S3_BUCKET=na-st01.ext.exlibrisgroup.com        # Production
# ALMA_S3_BUCKET=na-test-st01.ext.exlibrisgroup.com  # Sandbox

AWS_ACCESS_KEY_ID=your_exl_s3_access_key
AWS_SECRET_ACCESS_KEY=your_exl_s3_secret_key
AWS_DEFAULT_REGION=us-east-1
```

> **Getting S3 credentials:** The ExLibris S3 credentials are separate from any personal AWS credentials. Request them from your Alma/ExLibris administrator. They are scoped to the institution's upload bucket only.

### Required Python libraries

```bash
source .venv/bin/activate
pip install Pillow boto3
```

Both are verified at runtime; the function will stop immediately with a clear error message if either is missing.

### Required CSV file

**`all_single_tiffs_with_local_paths.csv`** — must exist in the CABB workspace root.

| Column | Description |
|--------|-------------|
| `MMS ID` | Alma bibliographic record ID |
| `Local Path` | Absolute path to the TIFF file on disk |

```csv
MMS ID,Local Path
991234567890104641,/Volumes/DGIngest/Photos/photo_001.tif
991234567890204641,/Volumes/DGIngest/Photos/photo_002.tiff
```

- Lines starting with `#` are treated as comments and skipped
- Both `.tif` and `.tiff` extensions are supported
- Network volume paths are fine (volumes must be mounted before running)

---

## Processing Logic

### Decision tree per record

```
MMS ID received
  |
  |-- Not in TIFF CSV                   --> record as "no_path" (no_path_count++)
  |-- TIFF file not found on disk       --> record as "no_file" (no_file_count++)
  |
  |-- Convert TIFF --> JPG              <-- fails? --> FAIL (failed_count++)
  |-- Upload JPG to ExL S3              <-- fails? --> FAIL
  |
  |-- GET existing representations from Alma API
        |
        |-- DERIVATIVE_COPY/JPG rep found WITH file
        |       --> SKIP (skipped_has_file_count++)
        |         log: "SKIPPED -- existing rep already has file (pid: ...)"
        |
        |-- DERIVATIVE_COPY/JPG rep found, EMPTY
        |       --> POST file to existing rep --> SUCCESS (success_count++)
        |
        +-- No matching rep found
                --> POST create new DERIVATIVE_COPY rep
                --> POST file to new rep --> SUCCESS (success_count++)
```

### What "matching representation" means

The code searches the GET response for a representation where:
- `usage_type.value == "DERIVATIVE_COPY"`, AND
- `label` contains `"JPG"`, `"jpg"`, or `"derivative"` (case-insensitive)

If the inline file list in the GET response is ambiguous, a second `GET /representations/{rep_id}/files` call is made to confirm whether a file exists before deciding to skip.

---

## How to Use

### Step 1: Configure `.env`

Ensure all required variables are set. The function stops immediately with a clear error message if `ALMA_S3_BUCKET` or the AWS credentials are missing.

### Step 2: Verify prerequisites

```bash
# Check CSV exists
ls -lh all_single_tiffs_with_local_paths.csv

# Check libraries
source .venv/bin/activate
python -c "from PIL import Image; import boto3; print('OK')"

# Check volumes are mounted (if using network paths)
ls /Volumes/DGIngest/
```

### Step 3: Load a set in CABB

- Enter a **Set ID** and click **"Load Set Members"**, OR
- Enter a single **MMS ID** in the MMS ID field for single-record mode

### Step 4: Run Function 11

1. Select **"11 - Prepare TIFF/JPG Representations"** from the function dropdown
2. Click **"Run Function on Set"**
3. Review the confirmation dialog — it confirms the API+S3 approach and credential requirements
4. Click **"Proceed"**
5. Monitor the log window (progress bar updates after each record)

### Step 5: Review log output

The log shows a detail line for every record processed. At the end, the summary line reads:

```
Function 11 (API method) complete:
  N succeeded,
  N skipped (rep already has file),
  N failed,
  N missing path,
  N file not found
```

If `success_count > 0`, the files are already live in Alma — **no further upload steps needed**.

### Step 6: Verify in Alma

- Open a processed record in Alma
- Navigate to **Resources > Manage Inventory > Manage Digital Files**
- Confirm the DERIVATIVE_COPY representation has a JPG file attached
- (Optional) Check the Primo/Discovery view after ~15 minutes for the thumbnail

---

## Output

There is **no local output directory**. All JPG conversion files are written to a `tempfile.TemporaryDirectory` that is automatically cleaned up when the batch finishes. Nothing is written to `~/Downloads/` or any persistent path.

The only permanent output is the file attached to the Alma digital representation.

---

## Summary of API Calls Per Record

| # | Method | Endpoint | Purpose |
|---|--------|----------|---------|
| 1 | `GET` | `/almaws/v1/bibs/{mms_id}/representations` | Check for existing DERIVATIVE_COPY rep |
| 2 | `GET` | `/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files` | Confirm file presence (conditionally) |
| 3 | `POST` | `/almaws/v1/bibs/{mms_id}/representations` | Create new rep (only if none found) |
| 4 | `POST` | `/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files` | Attach JPG via S3 path reference |

The S3 upload precedes call #4: a boto3 `put_object` writes the JPG to:

```
s3://{ALMA_S3_BUCKET}/{ALMA_INSTITUTION_CODE}/upload/{mms_id}.jpg
```

The file POST body that references the S3 path:

```json
{
  "label": "991234567890104641.jpg",
  "path": "01GCL_INST/upload/991234567890104641.jpg"
}
```

Alma moves the file from the `/upload` staging area to `/storage` automatically.

---

## Image Conversion Details

**JPG output specifications:**
- Format: JPEG, quality=95, optimize=True
- Color mode: RGB (all source modes normalized)
- Bit depth: 8-bit output

**Mode handling in `_convert_tiff_to_jpg()`:**

| Source mode | Action |
|-------------|--------|
| `I`, `I;16`, `I;16B`, `I;16L`, `I;16N` | Scale to 8-bit (pixel / 256), convert L then RGB |
| `RGBA`, `LA` | Composite alpha over white background, convert to RGB |
| `P` (palette) | Convert to RGBA first, then composite over white |
| `L` (grayscale) | Convert to RGB directly |
| `RGB` | Used as-is |
| Other | Force convert to RGB |

Temporary JPG files are named `{mms_id}.jpg` during processing and deleted automatically.

---

## Error Reference

| Message in log | Cause | Fix |
|---|---|---|
| `API Key not configured` | `ALMA_API_KEY` missing from `.env` | Add it |
| `ALMA_S3_BUCKET not configured` | Missing `.env` var | Add `ALMA_S3_BUCKET=...` |
| `AWS credentials not configured` | Missing `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` | Add both to `.env` |
| `TIFF CSV not found` | `all_single_tiffs_with_local_paths.csv` absent | Generate via Function 18 |
| `Pillow library not installed` | Missing dependency | `pip install Pillow` |
| `boto3 library not installed` | Missing dependency | `pip install boto3` |
| `No local path found for ...` | MMS ID not in TIFF CSV | Add row to CSV |
| `File not found: ...` | TIFF path in CSV doesn't exist on disk | Mount volume / fix path |
| `TIFF/JPG conversion failed` | Corrupt or unreadable TIFF | Verify TIFF integrity |
| `S3 upload failed: ...` | Wrong AWS credentials / bucket unreachable | Check `.env` AWS vars |
| `Failed to create representation: HTTP 4xx` | API auth failure or bad MMS ID | Check API key and MMS ID |
| `Failed to post file to representation` | S3 file not visible or wrong path | Check S3 key format |
| `SKIPPED -- existing rep already has file` | Rep already populated | Intentional — no changes made |

---

## FAQ

**Q: Can I re-run Function 11 on records that were already processed?**  
Yes, but those records will be **skipped** automatically. The function detects the representation already has a file and leaves it untouched. Only records with empty or missing representations are processed.

**Q: Can I process a single record without loading a set?**  
Yes. Enter the MMS ID in the MMS ID field instead of loading a set.

**Q: What S3 bucket should I use for testing?**  
Use the sandbox bucket: `na-test-st01.ext.exlibrisgroup.com`. Set `ALMA_S3_BUCKET` to this in `.env` when testing against your Alma sandbox. Ensure you're also using the sandbox API key.

**Q: Do I need the old Alma Digital Import Profile (ID 7848184990004641)?**  
No. That profile was for the previous CSV/Digital-Uploader approach. It is not used by Function 11.

**Q: What if I need to change the JPG quality?**  
Edit `_convert_tiff_to_jpg()` in `app.py` and change `quality=95`. Valid JPEG quality range is 1-95.

**Q: What if my TIFFs are spread across multiple directories?**  
That is fine. Each row in `all_single_tiffs_with_local_paths.csv` is an independent absolute path.

**Q: Will this touch bibliographic metadata?**  
No. Function 11 only reads, creates, and attaches files to digital representations. Bibliographic metadata is never modified.

**Q: What if an S3 upload succeeds but the file POST fails?**  
The orphaned file in `/upload` will be cleaned up by ExLibris automatically. The record is marked as failed in the summary, and you can safely re-run it.

---

## Related Documentation

| File | Contents |
|------|----------|
| `.env.example` | All required environment variables with comments |
| `FUNCTION_11_PREPARE_TIFF_JPG_CSV-Method-Archive.md` | Archived docs for the old CSV/Digital-Uploader approach |
| `FUNCTION_11_MIGRATION_NOTES.md` | History of prior CSV to XML migration (superseded) |
| `FUNCTION_11_CSV_PROFILE_SETUP.md` | Setup guide for old Alma Digital Import Profile (no longer needed) |

## Related Functions

- **Function 18** — Identify single-TIFF records (generates `all_single_tiffs_with_local_paths.csv`)
- **Function 14a** — Prepare Thumbnails (similar API-driven workflow, uses `AUXILIARY` usage type)
