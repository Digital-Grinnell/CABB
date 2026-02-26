# Function 14a: Prepare .clientThumb Thumbnails

## Overview

**Function 14a** prepares `.clientThumb` thumbnail image files from the Digital Grinnell migration for upload to Alma-D:

1. Creates DERIVATIVE_COPY representations in Alma with proper metadata
2. Processes thumbnail files (PNG→JPEG conversion, size optimization)
3. Saves processed files to a timestamped output directory in `~/Downloads/CABB_thumbnail_prep_YYYYMMDD_HHMMSS/`
4. Generates a CSV file mapping MMS IDs to representation IDs

**Note**: This function creates representations and prepares files but does **not** upload the actual files (due to Alma API limitations). Function 14b (to be implemented) will handle the file upload step.

## What It Does

This function processes bibliographic records that have `grinnell:` or `dg_` identifiers and:
1. Finds corresponding `.clientThumb` thumbnail files
2. Creates thumbnail representations in Alma
3. Processes files (converts PNG to JPEG, optimizes size)
4. Saves everything to a timestamped directory for Function 14b

### Identifier-to-Filename Transformation

**Pattern Recognition:**
The function supports flexible filename matching based on identifier patterns:

- **Record identifier**: `grinnell:12205` → searches for files containing `grinnell_12205`
- **Record identifier**: `dg_12205` → searches for files containing `dg_12205`
- **File patterns**: Any file containing the identifier pattern AND ending with `.clientThumb` or `.jpg`

**Examples:**
```xml
<!-- Bib record has: -->
<dc:identifier>grinnell:12205</dc:identifier>

<!-- Function searches for files matching: -->
*grinnell_12205*.clientThumb
*grinnell_12205*.clientThumb.jpg
*grinnell_12205*.jpg

<!-- Examples of matching files: -->
grinnell_12205_OBJ.mp3.clientThumb
grinnell_12205_OBJ.mp3.clientThumb.jpg
grinnell_12205_thumbnail.jpg
```

**dg_ identifier support:**
```xml
<!-- Bib record has: -->
<dc:identifier>dg_12205</dc:identifier>

<!-- Function searches for files matching: -->
*dg_12205*.clientThumb
*dg_12205*.clientThumb.jpg
*dg_12205*.jpg
```

### Smart Processing Logic

The function implements intelligent record filtering to avoid unnecessary processing:

#### Records That Get Processed
✅ Records with a `grinnell:` or `dg_` identifier AND matching `.clientThumb` or `.jpg` file in the directory

**Example:**
- Has: `dc:identifier` = `grinnell:12205` OR `dg_12205`
- Found: File matching pattern `*grinnell_12205*.clientThumb*` or `*grinnell_12205*.jpg`
- **Action**: Processes thumbnail, creates representation, saves to output directory

#### Records That Get Skipped
⊘ **No grinnell: or dg_ identifier**: Record has no `dc:identifier` starting with `grinnell:` or `dg_`
- **Message**: "No grinnell: or dg_ identifier found"
- **Reason**: Cannot determine which thumbnail file to use

⊘ **Thumbnail file not found**: No matching .clientThumb file exists in the directory
- **Message**: "No thumbnail file found - skipping (this is normal for some records)"
- **Reason**: File doesn't exist in the migration directory
- **Note**: This is an expected condition - not all records may have thumbnail files

## Processing Flow

### Step-by-Step Process

1. **Fetch Record**: Retrieves the bibliographic record from Alma as XML
2. **Parse XML**: Locates all `dc:identifier` elements
3. **Extract ID Patterns**: Scans for identifiers starting with `grinnell:` or `dg_`
4. **Generate Search Patterns**: 
   - `grinnell:12205` → searches for `*grinnell_12205*.clientThumb*`, `*grinnell_12205*.jpg`
   - `dg_12205` → searches for `*dg_12205*.clientThumb*`, `*dg_12205*.jpg`
5. **Locate File**: Uses glob patterns to find matching files in the thumbnail directory
6. **Create Clean Filename**: Generates a simple filename for Alma upload
   - Example: `grinnell_12205` → `grinnell_12205_thumbnail.jpg`
   - Removes complex extensions like `.mp3.clientThumb.jpg` that may confuse Alma
7. **Detect File Type**: Reads file header (magic bytes) to determine PNG vs JPEG
8. **Convert if Needed**: Automatically converts PNG to JPEG (Alma requirement)
   - Opens PNG with Pillow
   - Converts RGBA/LA/P to RGB with white background
   - Saves as JPEG (95% quality, optimized)
   - Creates temporary file for upload
9. **Optimize File Size**: Ensures file is under 100KB (Alma limit)
   - First tries reducing JPEG quality (85%, 75%, 65%, 55%)
   - If still too large, resizes image dimensions (90%, 80%, 70%, 60%, 50% of original)
   - Logs all optimization attempts
10. **Create Representation**: POSTs to Alma API to create DERIVATIVE_COPY representation
11. **Upload File**: Uploads the optimized JPEG file to the representation
12. **Cleanup**: Removes temporary conversion files (if created)
13. **Save to Output Directory**: Copies processed file to timestamped directory
14. **Record to CSV**: Adds MMS ID, Rep ID, and filename to CSV data
15. **Log Result**: Reports success or failure

### Final Step: Generate CSV

After processing all records, Function 14a creates a CSV file in the output directory:
- **Columns**: `mms_id`, `rep_id`, `filename`, `original_file`
- **Purpose**: Maps representations to processed files for Function 14b
- **Location**: `~/Downloads/CABB_thumbnail_prep_YYYYMMDD_HHMMSS/thumbnail_representations_YYYYMMDD_HHMMSS.csv`

### API Endpoints Used

**Function 14a (This Function):**
- `POST /almaws/v1/bibs/{mms_id}/representations`
  - Creates representation with metadata
  - Payload includes `usage_type: DERIVATIVE_COPY`

**Function 14b (To Be Implemented):**
- `POST /almaws/v1/bibs/{mms_id}/representations/{rep_id}/files`
  - File upload endpoint (alternative method to be determined)

### Representation Details

The function creates representations with these properties:
- **Label**: "Thumbnail - [filename]"
- **Usage Type**: DERIVATIVE_COPY (derived/processed versions of content)
- **Library**: MAIN (configurable)
- **Public Note**: "Thumbnail image from Digital Grinnell migration (prepared for upload)"

### Representation Positioning

**Important**: Alma uses the **first representation** in the list as the primary thumbnail for display.

Function 14a monitors and reports on representation positioning:

#### Existing Empty Thumbnail Representation
When an empty thumbnail representation already exists:
- ✅ **Position 1**: "✓ Thumbnail representation is in first position" - Ideal state
- ⚠️ **Position 2+**: "WARNING: Thumbnail representation is at position X, not first!" - Requires manual reordering

#### Creating New Thumbnail Representation
When creating a new thumbnail representation:
- ✅ **No existing reps**: "✓ Thumbnail representation created as first (and only) representation" - Ideal state
- ⚠️ **Existing reps present**: "NOTE: Creating new thumbnail representation, but X representation(s) already exist. The new thumbnail will be placed at the end (position Y)" - May require manual reordering

**Manual Reordering:**
If the thumbnail representation is not in first position, you must manually reorder it in the Alma UI:
1. Open the bibliographic record in Alma
2. Navigate to the Digital Inventory
3. Drag the thumbnail representation to the first position
4. Save changes

**Note**: The Alma API does not provide an automated way to reorder representations. Manual intervention is required if the thumbnail is not automatically placed first.

## Operation Modes

### Single Record Mode (Testing)

Process a single bibliographic record by MMS ID - especially useful for testing:

1. Enter an MMS ID in the input field
2. Select "14a: Prepare .clientThumb Thumbnails" from the function dropdown
3. Click the function button
4. **Confirm the warning dialog** before proceeding
5. View result in the status area and log
6. Check the `~/Downloads/CABB_thumbnail_prep_YYYYMMDD_HHMMSS` directory for output

**Possible Outcomes:**
- ✓ **Success**: "Representation created and file prepared (Rep ID: 12345678)"
- ⊘ **Skipped**: "No grinnell: or dg_ identifier found" or "No thumbnail file found"
- ✗ **Error**: "Failed to create representation: 404" or other error message

### Batch Mode (Primary Use Case)

Process multiple records from a loaded set:

1. Load a set using "Load Set by ID" or "Load MMS IDs from CSV"
2. (Optional) Set a limit in the "Limit" field to process only the first N records
3. Select "14a: Prepare .clientThumb Thumbnails" from the function dropdown
4. Click the function button
5. **Confirm the warning dialog** showing the number of records to be modified
6. Monitor progress via the progress bar
7. View summary results when complete
8. Find output in `~/Downloads/CABB_thumbnail_prep_YYYYMMDD_HHMMSS` directory

**Batch Processing Features:**
- Progress bar shows current record being processed
- Kill switch available to stop processing mid-batch
- Four-category summary: prepared, failed, no identifier, no thumbnail
- Individual record results logged with status symbols:
  - ✓ = Successfully prepared thumbnail and created representation
  - ⊘ = Skipped (no identifier or no thumbnail - normal condition)
  - ✗ = Failed with error

**Example Summary:**
```
Thumbnail preparation complete: 45 prepared, 2 failed, 3 no identifier, 8 no thumbnail (normal)
Output directory: /Users/username/Downloads/CABB_thumbnail_prep_20260226_105623
Note: 8 record(s) had no matching thumbnail files - this is expected for some records
```

## Safety Features

### Confirmation Dialog

Before any modification occurs, a warning dialog appears with:

- ⚠️ Clear warning that Alma data will be PERMANENTLY modified (representations created)
- Function name and description
- Number of records affected
- Red "Proceed" button to continue
- "Cancel" button to abort

**Warning Dialog:**
```
⚠️ WARNING: Alma Data Modification

This will create thumbnail representations in Alma and prepare files for upload.

MMS ID: 991234567890104641  (or: Records to process: 58)
Function: 14a: Prepare .clientThumb Thumbnails

This action will PERMANENTLY create thumbnail representations in Alma.
Processed files will be saved to a local directory for later upload (Function 14b).
Representations are created from .clientThumb files found in the specified directory 
based on each record's grinnell: or dg_ identifier.

Do you want to continue?
```

### Two-Step Workflow

**Function 14a (This Function):**
- ✅ Creates DERIVATIVE_COPY representations in Alma
- ✅ Processes thumbnail files (PNG→JPEG, optimization)
- ✅ Saves processed files to timestamped directory
- ✅ Generates CSV mapping MMS IDs to representation IDs
- ❌ Does NOT upload files to Alma (due to API limitation)

**Function 14b (To Be Implemented):**
- Will read the CSV from Function 14a
- Will upload processed files to their corresponding representations
- Will use an alternative upload method

### Non-Destructive Operation

- Does NOT modify existing thumbnails or representations
- Only ADDS new thumbnail representations (empty, pending file upload)
- Original thumbnail files are not modified or deleted
- Processed files are saved locally in timestamped directory

## File Format Support

The function automatically detects the actual file format by reading the file header (magic bytes), not just the file extension:

- **PNG Detection**: Checks for PNG signature (0x89 0x50 0x4E 0x47)
- **JPEG Detection**: Checks for JPEG signature (0xFF 0xD8 0xFF)
- **Automatic Conversion**: PNG files are automatically converted to JPEG before upload

**Important**: Many `.clientThumb.jpg` files are actually PNG format despite the `.jpg` extension. The function:
1. Correctly detects PNG files by reading the file signature
2. Automatically converts PNG to JPEG (Alma requires JPEG for thumbnails)
3. Handles transparency by converting RGBA/LA/P modes to RGB with white background
4. Saves converted JPEG with 95% quality, optimized
5. Cleans up temporary conversion files after upload

**Requirements**: PNG-to-JPEG conversion requires the Pillow library (included in requirements.txt)

## File Size Optimization

Alma has a **100KB size limit** for thumbnail files. The function automatically optimizes files that exceed this limit:

### Optimization Strategy

1. **Quality Reduction** (first attempt):
   - Tries JPEG quality levels: 85%, 75%, 65%, 55%
   - Stops when file size drops below 100KB
   - Uses `optimize=True` for additional compression

2. **Image Resizing** (if quality reduction insufficient):
   - Reduces dimensions by 10% increments: 90%, 80%, 70%, 60%, 50%
   - Uses high-quality LANCZOS resampling
   - Applies quality=65 to resized images
   - Stops when file size drops below 100KB

3. **Fallback**:
   - If file cannot be optimized below 100KB, uploads as-is with warning
   - Logs all optimization attempts for troubleshooting

### Example Log Output

```
Starting Function 14a: Prepare .clientThumb Thumbnails
Processing 3 MMS ID(s)
Thumbnail folder: /Volumes/DGIngest/Migration-to-Alma/exports/alumni-oral-histories/OBJ
Output directory: /Users/username/Downloads/CABB_thumbnail_prep_20260226_105623

Processing 1/3: MMS 991011591726204641
  ✓ Found thumbnail: grinnell_12205_OBJ.mp3.clientThumb.jpg (46.97 KB)
  PNG detected - converting to JPEG
  ✓ Converted to JPEG: 9.07 KB
  Creating thumbnail representation for 991011591726204641
  Created representation ID: 12349493060004641
  Saved processed file to: /Users/username/Downloads/CABB_thumbnail_prep_20260226_105623/grinnell_12205_thumbnail.jpg
  ✓ Representation created and file prepared (Rep ID: 124349493060004641)
    Rep ID: 12349493060004641
    Processed file: grinnell_12205_thumbnail.jpg

✓ Created CSV file: /Users/username/Downloads/CABB_thumbnail_prep_20260226_105623/thumbnail_representations_20260226_105623.csv
  Contains 3 entries

Thumbnail preparation complete: 3 prepared, 0 failed, 0 no identifier, 0 no thumbnail (normal)
Output directory: /Users/username/Downloads/CABB_thumbnail_prep_20260226_105623
```

```
File size (156.45 KB) exceeds 100KB limit - optimizing
  Trying quality=85: 142.31 KB
  Trying quality=75: 98.67 KB
✓ Optimized to 98.67 KB (quality=75)
```

Or for larger files requiring resize:

```
File size (245.89 KB) exceeds 100KB limit - optimizing
  Trying quality=85: 223.12 KB
  Trying quality=75: 201.45 KB
  Trying quality=65: 178.34 KB
  Trying quality=55: 156.89 KB
  Quality reduction insufficient - resizing image
  Trying 720x480 (scale=0.9): 125.67 KB
  Trying 640x427 (scale=0.8): 95.34 KB
✓ Resized to 640x427: 95.34 KB
```

## Output Directory and Files

### Timestamped Directory

Function 14a creates a new directory in your Downloads folder for each run:
```
~/Downloads/CABB_thumbnail_prep_20260226_105623/
  ├── grinnell_12205_thumbnail.jpg
  ├── grinnell_12346_thumbnail.jpg
  ├── dg_45678_thumbnail.jpg
  └── thumbnail_representations_20260226_105623.csv
```

**Directory Name Format**: `~/Downloads/CABB_thumbnail_prep_YYYYMMDD_HHMMSS`
**Absolute Path**: The full absolute path is displayed in the log output

### CSV File Structure

The CSV file contains:
```csv
mms_id,rep_id,filename,original_file
991011591726204641,12349493060004641,grinnell_12205_thumbnail.jpg,grinnell_12205_OBJ.mp3.clientThumb.jpg
991011592834504641,12349505120004641,grinnell_12346_thumbnail.jpg,grinnell_12346_OBJ.mp3.clientThumb.jpg
```

**Columns**:
- `mms_id`: Bibliographic record MMS ID
- `rep_id`: Created representation ID in Alma
- `filename`: Processed thumbnail filename (in output directory)
- `original_file`: Original thumbnail filename (before processing)

**Purpose**: This CSV will be used by Function 14b to upload the processed files to their corresponding representations.

## Usage Type: DERIVATIVE_COPY

The function creates representations with `usage_type = DERIVATIVE_COPY` because:
- **THUMBNAIL**: Not supported as a usage_type by Alma API (returns HTTP 400)
- **AUXILIARY**: Representations are created successfully, but file uploads fail with UTF-8 parsing errors
- **DERIVATIVE_COPY**: Standard usage type for derived versions of content, supports file uploads ✅

The representation is labeled as \"Thumbnail - [filename]\" with a public note indicating it's from the Digital Grinnell migration.

## Directory Configuration

### Environment Variable Configuration

The thumbnail directory is configured via the `.env` file:

```dotenv
# Thumbnail Upload Configuration (Function 14)
THUMBNAIL_FOLDER_PATH=/Volumes/DGIngest/Migration-to-Alma/exports/alumni-oral-histories/OBJ
```

**To change the thumbnail directory:**
1. Edit the `.env` file in the CABB root directory
2. Update the `THUMBNAIL_FOLDER_PATH` value
3. Restart the CABB application

### Default Directory

If `THUMBNAIL_FOLDER_PATH` is not set, the default is:
```
/Volumes/DGIngest/Migration-to-Alma/exports/alumni-oral-histories/OBJ
```

### Programmatic Override

You can also override the directory when calling the function directly:

```python
success, message = editor.upload_clientthumb_thumbnails(
    editor.set_members,
    thumbnail_folder="/path/to/your/thumbnails",  # Override .env setting
    progress_callback=progress_update
)
```

## Troubleshooting

### "No grinnell: or dg_ identifier found"

**Cause**: Record doesn't have a `dc:identifier` starting with `grinnell:` or `dg_`

**Solution**: 
- Verify you're running on the correct set
- Check if records need `grinnell:` identifiers added first (see Function 7)
- Review record in Alma to confirm identifier format
- Check if records use a different identifier pattern

### "Thumbnail file not found"

**Cause**: No matching .clientThumb file exists in the specified directory
Note**: This is a **normal condition** for some records. Not all migrated records may have associated thumbnail files.

**Possible Reasons:**
- File naming doesn't match the expected patterns
- Files are in a different directory
- Files weren't migrated for this collection
- Identifier pattern in record doesn't match filename pattern
- Record legitimately has no thumbnail in the source system
- Identifier pattern in record doesn't match filename pattern

**Solution**:
- Check the thumbnail directory path is correct (verify `THUMBNAIL_FOLDER_PATH` in `.env`)
- List files to verify naming patterns: `ls /Volumes/DGIngest/.../OBJ/*grinnell*`
- Check for dg_ pattern files: `ls /Volumes/DGIngest/.../OBJ/*dg_*`
- Confirm files exist with expected extensions (`.clientThumb`, `.clientThumb.jpg`, `.jpg`)
- Review log output to see which identifier patterns were searched

### "Failed to create representation: HTTP 400"

**Cause**: Using an unsupported `usage_type` value.

**Solution**: Function now uses `usage_type = "DERIVATIVE_COPY"`. 

**History of usage_type attempts**:
1. **THUMBNAIL**: Not recognized by Alma API (HTTP 400)
2. **AUXILIARY**: Representation created successfully, but file upload fails with UTF-8 error
3. **DERIVATIVE_COPY**: ✅ Works correctly for both representation creation and file upload

Valid usage_type values in Alma:
- PRIMARY
- MODIFIED_PRIMARY  
- DERIVATIVE_COPY ✅ (current)
- AUXILIARY

### "Failed to upload file: HTTP 400 - Invalid UTF-8"

**Status**: ⚠️ **KNOWN LIMITATION** - Alma API file upload endpoint issue

**Error Message**: `"Invalid UTF-8 start byte 0xff (at char #282, byte #-1)"`

**Root Cause**: The Alma API endpoint `POST /almaws/v1/bibs/{mms_id}/representations/{rep_id}/files` appears to not support direct binary file uploads via multipart/form-data. The error occurs at the exact same byte position (#282) regardless of:
- File content (PNG vs JPEG)
- File size (9KB to 100KB)
- Filename format (simple vs complex)
- usage_type (AUXILIARY vs DERIVATIVE_COPY)
- Upload method (file handle vs bytes in memory)

**Workarounds**:

1. **Manual Upload** (Current Recommended Approachfor small batches):
   - Function successfully creates representations with correct metadata
   - Files must be uploaded manually through Alma UI
   - Check Alma logs for representation IDs
   - Navigate to representation in Alma and upload file manually

2. **Remote URL Import** (Potential Future Solution):
   - Host thumbnail files on an accessible web server
   - Use Alma's remote file import feature (if supported)
   - Provide URLs instead of uploading binary data

3. **Contact Ex Libris Support**:
   - Report UTF-8 parsing error at char #282
   - Request clarification on correct file upload method
   - Ask if alternative API endpoints exist for representation file uploads

**Related Issues**:
- Function 12 (Add JPG Representations) has the same issue - marked as ***FAILED***
- This appears to be a consistent limitation of the Alma API

**What Still Works**:
✅ Representation creation with usage_type DERIVATIVE_COPY
✅ Automatic PNG to JPEG conversion
✅ File size optimization (under 100KB)
✅ Clean filename generation
✅ Batch processing of records

**What Doesn't Work**:
❌ Actual file upload to created representations via API

**If error persists**: 
- This is expected behavior based on current Alma API limitations
- Use manual upload workaround via Alma UI
- Contact Ex Libris for API guidance

### Thumbnails don't appear in viewer

**Cause**: Representation uploaded but may need configuration in Alma

**Solution**:
- AUXILIARY representations are uploaded successfully but may require Alma configuration to display as thumbnails
- Check representation settings in Alma UI
- Verify representation was created successfully (check logs for Rep ID)
- Consult Alma documentation on configuring thumbnail display for AUXILIARY representations

## Expected File Patterns

### File Naming Examples

**Pattern 1: .clientThumb.jpg extension**
```
grinnell_12205_OBJ.mp3.clientThumb.jpg  ← PNG format (despite .jpg extension)
grinnell_17924_AUDIO.clientThumb.jpg    ← JPEG format
dg_98765_OBJ.clientThumb.jpg           ← Using dg_ identifier
```

**Pattern 2: .clientThumb (no extension)**
```
grinnell_17924_OBJ.mp3.clientThumb      ← JPEG format (no extension)
grinnell_18499_OBJ.mp3.clientThumb      ← JPEG format (no extension)
dg_54321_MEDIA.clientThumb             ← Using dg_ identifier
```

**Pattern 3: .jpg extension only**
```
grinnell_12205_thumbnail.jpg            ← Alternative naming
dg_12205_thumb.jpg                     ← Using dg_ identifier
```

**The function will match any file that:**
- Contains the identifier pattern (`grinnell_12205` or `dg_12205`)
- AND ends with `.clientThumb`, `.clientThumb.jpg`, or `.jpg`

### Typical File Sizes
- Most thumbnails: 10-50 KB
- Range: ~5-200 KB
- Typical dimensions: 135px width (varies)

## Best Practices

1. **Test First**: Run on a **single MMS ID** to verify settings and file patterns
2. **Verify Directory**: Confirm thumbnail files are accessible before processing
3. **Check Identifiers**: Ensure records have `grinnell:` or `dg_` identifiers (use Function 7 if needed)
4. **Monitor Progress**: Watch the log output for patterns in failures
5. **Review Results**: Spot-check uploaded thumbnails in Alma viewer
6. **Document**: Save the log file for records of successful uploads

## Workflow Integration

### Typical Migration Workflow

1. **Ensure Identifiers** (Function 7):
   - Run "Add Grinnell: dc:identifier Field As Needed"
   - Ensures all records have standardized `grinnell:` identifiers
   - Note: Records may already have `dg_` identifiers from migration

2. **Upload Thumbnails** (Function 14):
   - Configure `THUMBNAIL_FOLDER_PATH` in `.env` file
   - Run "Upload .clientThumb Thumbnails"
   - Creates thumbnail representations from migration files

3. **Review Results** (Function 10):
   - Run "Export for Review with Clickable Handles"
   - Manually verify thumbnails display correctly

## Performance Considerations

### API Calls Per Record
- 1 GET call (fetch bib record)
- 1 POST call (create representation)
- 1 POST call (upload file)
- **Total**: 3 API calls per successful upload

### Rate Limiting
- Alma API typically allows 25 requests/second
- Function processes sequentially to respect limits
- Large batches may take considerable time

### Estimated Processing Time
- Small set (50 records): ~5 minutes
- Medium set (200 records): ~20 minutes
- Large set (1000 records): ~1.5 hours

## Technical Notes

### Multipart File Upload

Alma requires `multipart/form-data` for file uploads:

```python
files_data = {
    'file': (filename, file_content, mime_type)
}

data = {
    'path': f"{institution_code}/upload/{filename}"
}
```

### MIME Type Detection

Automatically detects image format:
- Checks file extension first
- Falls back to PNG for .png files
- Defaults to JPEG otherwise
- Uses Python's `mimetypes.guess_type()`

### Error Recovery

If the function is interrupted:
1. Check logs to identify last successfully processed MMS ID
2. Create a filtered set excluding already-processed records
3. Re-run function on remaining records
4. Alma safely prevents duplicate uploads (different rep IDs)

## What's Next: Function 14b

Function 14b (to be implemented) will:
1. Read the CSV file from the output directory
2. For each row, upload the processed file to its representation
3. Use an alternative upload method (to be determined) that avoids the Alma API file upload limitation

Possible approaches for 14b:
- Direct file system access (if available)
- Alternative API endpoint discovery
- Batch import process via Alma UI
- Remote URL import (if Alma supports it)

## Related Functions

- **Function 7**: Add Grinnell: dc:identifier Field As Needed - Ensures records have required identifiers
- **Function 10**: Export for Review with Clickable Handles - Verify thumbnails display correctly
- **Function 1**: Fetch and Display Single XML - Inspect identifier values in records

## Version History

- **v1.0** (2026-02-26): Initial implementation
  - Automatic identifier-to-filename mapping
  - THUMBNAIL usage_type representation creation
  - PNG and JPEG format support
  - Batch processing with progress tracking
