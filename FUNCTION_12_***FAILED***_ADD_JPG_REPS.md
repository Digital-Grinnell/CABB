# Function 12: Add JPG Representations from For-Import

## Overview
Uploads JPG derivative files from the `For-Import` directory as new representations in Alma for digital objects listed in a CSV file.

## Purpose
This function automates the process of adding JPG derivatives to Alma digital objects that currently only have TIFF representations, improving access and reducing bandwidth requirements.

## Use Case
After using `process_tiffs_for_import.py` to:
1. Copy TIFF files from various locations to `For-Import/`
2. Create JPG derivatives of those TIFFs
3. Update the alma_export CSV with file names

Function 12 completes the workflow by uploading those JPG files as new representations in Alma.

## Requirements

### Input
- **CSV File**: An alma_export CSV file (e.g., `alma_export_20260127_161511.csv`) containing:
  - `mms_id`: The bibliographic record MMS ID
  - `file_name_1`: JPG filename (e.g., `grinnell_3482_OBJ.jpg`)
  - `file_name_2`: TIFF filename (for reference)

- **For-Import Folder**: Directory containing the JPG files referenced in the CSV

### Permissions
- Alma API key with write permissions for representations
- API permissions for `/almaws/v1/bibs/{mms_id}/representations` POST endpoint

## How to Use

### Step 1: Prepare the CSV
Run `process_tiffs_for_import.py` to create JPGs and update the alma_export CSV:
```bash
./run_process_tiffs.sh
```

### Step 2: Load CSV Path
In the CABB UI:
1. Enter the path to your alma_export CSV file in the **Set ID or CSV Path** field
   - Example: `alma_export_20260127_161511.csv`

### Step 3: Run Function 12
1. Select **"Add JPG Representations from For-Import"** from the Active Functions dropdown
2. Click the **Execute** button
3. Monitor progress in the status bar and log output

## What It Does

For each record in the CSV:

1. **Read Record**: Extracts `mms_id` and `file_name_1` (JPG filename)
2. **Locate JPG**: Checks if `For-Import/{file_name_1}` exists
3. **Create Representation**: POSTs to Alma API to create new representation with:
   - Label: "JPG derivative - {filename}"
   - Usage Type: DERIVATIVE_COPY
   - Library: MAIN (configurable)
   - Public Note: "JPG derivative created from TIFF"
4. **Upload File**: POSTs the JPG file to the new representation
5. **Log Results**: Reports success or failure for each upload

## Output

### Console/Log Output
- Progress updates for each record processed
- Success confirmations with representation IDs
- Error messages for failed uploads

### Alma Changes
- New representations created for each successful upload
- JPG files available in Alma's digital repository
- Derivatives accessible through IIIF or download

## Example Workflow

```
1. Start with: all_single_tiffs_with_local_paths.csv
   - Contains MMS IDs and paths to TIFF files

2. Run: ./run_process_tiffs.sh
   - Copies TIFFs to For-Import/
   - Creates JPGs in For-Import/
   - Updates: alma_export_20260127_161511.csv

3. Use Function 12:
   - Reads: alma_export_20260127_161511.csv
   - Uploads JPGs from: For-Import/
   - Creates representations in Alma

Result: All objects now have both TIFF and JPG representations
```

## Error Handling

The function handles:
- **Missing Files**: Skips records where JPG file doesn't exist
- **API Errors**: Logs HTTP errors from Alma API
- **Network Issues**: Reports connection failures
- **Invalid MMS IDs**: Catches records not found in Alma

Errors are logged but don't stop processing - all remaining records continue.

## API Endpoints Used

### Create Representation
- **Endpoint**: `POST /almaws/v1/bibs/{mms_id}/representations`
- **Payload**: JSON with representation metadata
- **Response**: Representation object with ID

### Upload File
- **Endpoint**: `POST /almaws/v1/bibs/{mms_id}/representations/{rep_id}/files`
- **Content-Type**: `multipart/form-data`
- **Payload**: Binary JPG file
- **Response**: File object with upload confirmation

## Configuration

### Representation Settings
Edit `_upload_jpg_representation()` in `app.py` to customize:
- **Usage Type**: Default is `DERIVATIVE_COPY`, could be `MASTER`, `VIEW_REPRESENTATION`, etc.
- **Library**: Default is `MAIN`, change to your institutional library code
- **Public Note**: Customize the description shown to users
- **Label**: Modify the representation label format

### Folder Location
Default is `For-Import/`, but can be changed:
```python
editor.add_jpg_representations_from_folder(
    csv_file,
    jpg_folder="My-Custom-Folder"  # Change here
)
```

## Limitations

- **File Size**: Large JPGs may timeout; Alma has file size limits
- **Batch Processing**: Uploads happen one at a time (not batched)
- **Existing Reps**: Does not check if JPG representation already exists
- **Manual Cleanup**: `For-Import/` folder is not automatically cleaned

## Best Practices

1. **Test First**: Run on a small batch (5-10 records) to verify settings
2. **Backup**: Keep original TIFFs until JPGs are confirmed in Alma
3. **Verify**: Use Alma UI to spot-check uploaded representations
4. **Monitor Quota**: Large batches consume API rate limits
5. **Clean Up**: Delete `For-Import/` contents after successful upload

## Troubleshooting

### "CSV file not found"
- Check the path in Set ID field is correct
- Use absolute path if relative path fails

### "No matching JPG files found"
- Verify `For-Import/` folder exists
- Check that JPG filenames in CSV match actual files
- Ensure `process_tiffs_for_import.py` completed successfully

### "Failed to create representation"
- Check API key has write permissions
- Verify MMS ID exists in Alma
- Check Alma API error message in logs

### "Failed to upload file"
- File may be corrupted
- File may be too large (check Alma limits)
- Network connection issues

## Related Functions

- **Function 3**: Export Set to DCAP01 CSV - Creates initial CSV export
- **Function 11**: Identify Single TIFF Representations - Identifies objects needing JPG derivatives

## Related Scripts

- **process_tiffs_for_import.py**: Prepares JPGs and updates CSV
- **run_process_tiffs.sh**: Wrapper script to run with virtual environment

## Technical Notes

### Multipart Upload
The Alma API requires `multipart/form-data` for file uploads. The implementation uses the Python `requests` library's `files` parameter to handle this automatically.

### Rate Limiting
- Alma API has rate limits (typically 25 requests/second)
- Function processes records sequentially to avoid rate limit issues
- Large sets may take considerable time (2 API calls per record)

### Error Recovery
If the function is interrupted:
1. Check logs to identify last successfully processed MMS ID
2. Filter CSV to remove already-processed records
3. Re-run function on remaining records

## Version History

- **v1.0** (2026-01-28): Initial implementation
  - Basic representation creation
  - Multipart file upload
  - Progress tracking and error handling
