# Function 19: Create Thumbnails from Representations

## Overview

**Function 19** creates thumbnail images from existing digital representation files in Alma-D. This allows you to:

1. **Review** all representation images as thumbnails
2. **Compare** multiple representations for each record visually
3. **Select** the best thumbnail for each record
4. **Attach** chosen thumbnails to records using Function 14a workflow

Unlike Function 14a (which uploads existing thumbnails), Function 19 **generates** thumbnails from representation files already in Alma.

**Supported File Types**:
- **Image files**: TIFF, JPEG, PNG, and other formats supported by Pillow
- **PDF files**: Extracts first page as thumbnail (requires poppler)
  - **PDF Conversion**: First page rendered at 200 DPI for high quality
  - **Automatic Detection**: Recognizes both `application/pdf` MIME type and `.pdf` extensions
  - **Common Use Case**: Historical documents, oral history transcripts, scanned materials

**Key Feature**: Function 19 can search for files by filename in a specified directory when exact paths from Alma don't exist locally.

## How File Location Works

Function 19 uses a **two-step approach** to find representation files:

### Step 1: Exact Path Match
First checks if the exact path returned by Alma exists on your filesystem:
```
Alma returns: /Volumes/DGIngest/storage/grinnell_12205_OBJ.tif
Check: Does this exact path exist? → Yes: Use it
```

### Step 2: Filename Search (NEW!)
If exact path doesn't exist, searches for the file by name in a configured directory:
```
Alma returns: 01GCL_INST/storage/alma/fe/8e/3c/grinnell_12205_OBJ.tif
Extract filename: grinnell_12205_OBJ.tif
Search in: /Volumes/Acasis1TB/** (recursively)
Find: /Volumes/Acasis1TB/TIFF-Masters/grinnell_12205_OBJ.tif → Use it
```

### Configuration

**Option 1: Environment Variable (Recommended)**
Set `REP_FILES_SEARCH_PATH` in your `.env` file:
```bash
REP_FILES_SEARCH_PATH=/Volumes/Acasis1TB
```

**Option 2: Current Working Directory**
If not configured, defaults to the directory where you run CABB.

**Option 3: Programmatic Override**
Pass `search_directory` parameter when calling the function (advanced usage).

### Search Behavior

- **Recursive**: Searches all subdirectories under the search path
- **First Match**: Uses the first matching file found (if multiple exist)
- **Filename Only**: Matches on filename, ignoring directory structure
- **Fast**: Uses Python's efficient `rglob()` for searching

## Use Cases

### When to Use Function 19

- **Visual Review**: You want to see what each representation looks like before choosing a thumbnail
- **Multiple Representations**: Records have multiple representations (TIFF master + JPG derivative) and you need to choose which one to use as the thumbnail
- **No Existing Thumbnails**: You don't have `.clientThumb` files but want to create thumbnails from existing representations
- **Quality Comparison**: You need to visually compare representation quality before selecting thumbnails

### When NOT to Use Function 19

- **Thumbnails Already Exist**: If you already have `.clientThumb` or thumbnail files, use Function 14a directly
- **Files Not Accessible**: If representation files are only in Alma S3 storage (not locally accessible), Function 19 cannot download them
- **Simple Upload**: If you just want to upload pre-existing thumbnails without review, use Function 14a

## What It Does

For each MMS ID, Function 19:

1. **Fetches** all digital representations from Alma via API
2. **Accesses** representation files (if available locally or on mounted drives)
3. **Creates** thumbnail images (200x200 pixels by default)
4. **Saves** thumbnails to a timestamped output directory
5. **Generates** a README with instructions for selecting and attaching thumbnails

### Thumbnail Naming Convention

Thumbnails are named using this pattern:
```
{MMS_ID}_rep{NUM}_{USAGE_TYPE}_thumbnail.jpg
```

**Examples:**
```
991234567890104641_rep1_MASTER_thumbnail.jpg
991234567890104641_rep2_DERIVATIVE_COPY_thumbnail.jpg
992345678901104641_rep1_VIEW_thumbnail.jpg
```

**Where:**
- `MMS_ID`: The bibliographic record identifier
- `rep{NUM}`: Representation number (1, 2, 3, etc.) based on Alma order
- `USAGE_TYPE`: Alma representation usage type (MASTER, DERIVATIVE_COPY, VIEW, etc.)
- `_thumbnail.jpg`: Fixed suffix

This naming allows you to:
- Identify which record each thumbnail belongs to
- See which representation number it came from
- Understand the representation type
- Compare multiple thumbnails for the same record

## Processing Flow

### Step-by-Step Process

1. **Fetch Representations**
   - Queries Alma API for all representations of each record
   - Retrieves representation metadata (ID, usage type, label)
   - Gets file list for each representation

2. **Access Representation Files**
   - First checks if exact path from Alma exists locally
   - If not found, searches by filename in configured search directory
   - Uses first matching file found

3. **Create Thumbnails**
   - Opens each accessible image file using Pillow (PIL)
   - Converts to RGB color space if needed (handles RGBA, grayscale, palette)
   - Creates thumbnail maintaining aspect ratio (max 200x200 pixels)
   - Saves as JPEG with 85% quality

4. **Organize Output**
   - Saves all thumbnails to: `~/Downloads/CABB_rep_thumbnails_YYYYMMDD_HHMMSS/`
   - Creates README.txt with detailed instructions
   - Logs summary of results

### File Type Support

Function 19 supports these image formats:
- **TIFF** (.tif, .tiff) - Converted to JPEG thumbnail
- **JPEG** (.jpg, .jpeg) - Resized to thumbnail
- **PNG** (.png) - Converted to JPEG thumbnail (removes transparency)
- **Other formats** supported by Pillow/PIL

Non-image files (MP3, PDF, etc.) are automatically skipped.

## Prerequisites

### Required

1. **API Key**: Alma API key with read access to bibliographic records and representations
2. **Pillow Library**: Python Imaging Library for image processing
   ```bash
   pip install Pillow
   ```

3. **pdf2image Library**: For PDF thumbnail generation
   ```bash
   pip install pdf2image
   ```

4. **Poppler**: System dependency required for pdf2image (PDF rendering)
   ```bash
   # macOS
   brew install poppler
   
   # Ubuntu/Debian
   sudo apt-get install poppler-utils
   
   # Windows: Download from https://github.com/oschwartz10612/poppler-windows
   ```

5. **File Access**: Representation files must be accessible on:
   - Local file system
   - Mounted network drives
   - External drives

### Recommended

1. **Search Directory Configuration**: Set `REP_FILES_SEARCH_PATH` in `.env`:
   ```bash
   REP_FILES_SEARCH_PATH=/Volumes/Acasis1TB
   ```
   This enables filename search when exact paths from Alma don't exist locally.

### Optional

- **Large Storage**: If processing many records with large TIFF files, ensure adequate disk space

## Usage

### Single Record Mode

1. Enter an MMS ID in the input field
2. Click **"19: Create Thumbnails from Representations"**
3. Wait for processing to complete
4. Review output directory path in status bar

### Batch Mode

1. Load a set using **"Load DCAP01 Set"**
2. Click **"19: Create Thumbnails from Representations"**
3. Monitor progress bar
4. Review summary in log

## Enhanced Logging & Output

Function 19 provides **detailed, real-time logging** with visual indicators to help you understand exactly what's happening during processing.

### Startup Information

When Function 19 begins, you'll see:

```
======================================================================
FUNCTION 19: CREATE THUMBNAILS FROM REPRESENTATIONS - STARTING
======================================================================
🔍 Checking REP_FILES_SEARCH_PATH environment variable...
   Environment value: /Users/mcfatem/Downloads/
   Will use directory: /Users/mcfatem/Downloads/
✅ Search directory verified and ready for recursive search
   Path: /Users/mcfatem/Downloads/

📊 Processing 5 MMS ID(s)
📐 Thumbnail size: 200x200 pixels
📂 Output directory: /Users/mcfatem/Downloads/CABB_rep_thumbnails_20260424_120530
======================================================================
```

This tells you:
- ✅ Whether search directory is configured and accessible
- 📊 How many records will be processed
- 📂 Where thumbnails will be saved

### Per-Record Processing

For each record, detailed logging shows every step:

```
======================================================================
📋 Processing record 1/5: MMS ID 991014062989704641
======================================================================
  🌐 Fetching representations from Alma API...
  ✅ Found 2 representation(s)
  
  📑 Representation 1/2: Oral History PDF (Type: VIEW)
     Fetching file list from Alma...
     Found 1 file(s) in representation
  
  📄 Processing PDF file: alumni_oral_history_12205.pdf
     🔍 Exact path not found, searching by filename...
        Filename to find: 'alumni_oral_history_12205.pdf'
        Searching in: /Users/mcfatem/Downloads/
        Search type: RECURSIVE (all subdirectories)
     ✅ FOUND by recursive search!
        Location: /Users/mcfatem/Downloads/OralHistories/alumni_oral_history_12205.pdf
     📑 Converting first page of PDF to image...
     ✓ Created thumbnail: 991014062989704641_rep1_VIEW_thumbnail.jpg (42.3 KB)

  📑 Representation 2/2: Master TIFF (Type: MASTER)
     Fetching file list from Alma...
     Found 1 file(s) in representation
  
  📄 Processing image file: grinnell_12205_OBJ.tif
     ✅ Found at exact path from Alma
     ✓ Created thumbnail: 991014062989704641_rep2_MASTER_thumbnail.jpg (38.7 KB)

  ✅ Successfully created 2 thumbnail(s) for this record
```

### Visual Indicators

The logging uses emoji indicators for quick scanning:
- 🔍 **Search operations** - Looking for files
- ✅ **Success** - File found, thumbnail created
- ❌ **Error** - Operation failed
- ⚠️ **Warning** - Issue but continuing
- 📄 **File processing** - Working on a file
- 📑 **PDF conversion** - Converting PDF to image
- 🌐 **API calls** - Fetching from Alma
- 📊 **Statistics** - Counts and summaries
- 📂 **Paths** - Directory locations

### File Not Found Example

When a file can't be located, you'll see detailed information:

```
  📄 Processing image file: missing_file.tif
     🔍 Exact path not found, searching by filename...
        Filename to find: 'missing_file.tif'
        Searching in: /Users/mcfatem/Downloads/
        Search type: RECURSIVE (all subdirectories)
     ❌ NOT FOUND - file does not exist in search directory tree

     ⚠️  File not accessible - cannot create thumbnail
        Alma reported path: 01GCL_INST/storage/alma/fe/8e/missing_file.tif
        Searched for 'missing_file.tif' recursively in: /Users/mcfatem/Downloads/
        File not found in search directory tree
```

This shows exactly:
- What file was being searched for
- Where the search was conducted
- That the search was recursive (checked all subdirectories)
- The original path Alma reported

### Final Summary

At completion, you get a comprehensive summary:

```
======================================================================
📊 FUNCTION 19 COMPLETE - SUMMARY
======================================================================
✅ 4 records processed successfully
🖼️  8 thumbnails created
⚠️  1 records had no representations
⚠️  2 representations had no accessible files
❌ 0 failed

📂 Output directory: /Users/mcfatem/Downloads/CABB_rep_thumbnails_20260424_120530
📄 See README.txt for instructions on selecting and attaching thumbnails
======================================================================
```

### Log File

All log output is also saved to:
```
logfiles/cabb_YYYYMMDD_HHMMSS.log
```

This permanent log includes even more detail (DEBUG level) than what's displayed in the UI, useful for troubleshooting.

### Output Structure

After running Function 19:

```
~/Downloads/CABB_rep_thumbnails_20260424_143052/
├── README.txt                                          # Instructions
├── 991234567890104641_rep1_MASTER_thumbnail.jpg        # Record 1, Rep 1
├── 991234567890104641_rep2_DERIVATIVE_COPY_thumbnail.jpg  # Record 1, Rep 2
├── 992345678901104641_rep1_VIEW_thumbnail.jpg          # Record 2, Rep 1
└── 993456789012104641_rep1_MASTER_thumbnail.jpg        # Record 3, Rep 1
```

**Key Features:**
- **Flat Directory**: All thumbnails in one folder (no subdirectories)
- **Clear Naming**: Easy to identify which record and representation
- **README Included**: Complete instructions for next steps
- **Timestamped**: Unique directory name prevents overwriting

## Reviewing Thumbnails

### Visual Review Process

1. **Open Output Directory**
   - Navigate to `~/Downloads/CABB_rep_thumbnails_YYYYMMDD_HHMMSS/`
   - Switch to Icon View or Gallery View in your file browser
   - Enable "Show Preview" to see image contents

2. **Group by Record**
   - Thumbnails with the same MMS ID prefix belong to the same record
   - Compare `rep1`, `rep2`, etc. for each record
   - Identify which representation best shows the content

3. **Check Quality**
   - Look for clarity, legibility, appropriate cropping
   - Compare MASTER vs DERIVATIVE_COPY thumbnails
   - Note any issues (blank images, poor quality, wrong content)

4. **Select Best Thumbnails**
   - For each record, decide which representation to use as the primary thumbnail
   - Usually DERIVATIVE_COPY or VIEW representations are best for thumbnails
   - MASTER TIFF representations may be large but show best quality

### Selection Methods

#### Method 1: Manual Selection (Recommended)

1. Create a subfolder: `selected/`
2. Copy your chosen thumbnails into `selected/`
3. Rename to remove rep number and usage type:
   ```
   From: 991234567890104641_rep2_DERIVATIVE_COPY_thumbnail.jpg
   To:   991234567890104641_thumbnail.jpg
   ```
4. Now you have one thumbnail per record, ready for Function 14a

#### Method 2: Keep All Thumbnails

If you want to upload all thumbnails (all representations):
- Skip selection
- Use the full directory as-is
- Function 14a will match by identifier pattern

#### Method 3: Scripted Selection

For large batches, create a script to:
- Parse thumbnail filenames
- Select based on criteria (prefer rep1, prefer DERIVATIVE_COPY, etc.)
- Copy/rename automatically

## Attaching Thumbnails to Records

### Using Function 14a

After selecting your thumbnails, use **Function 14a: Prepare Thumbnails** to attach them:

1. **Prepare Thumbnails for Function 14a:**
   - Ensure thumbnails are named to match identifiers
   - For `grinnell:12205` → filename should contain `grinnell_12205`
   - For `dg_12205` → filename should contain `dg_12205`

2. **Run Function 14a:**
   - Load your MMS IDs in CABB
   - Specify thumbnail folder (your `selected/` folder or output directory)
   - Function 14a creates representations and prepares files
   - Follow Function 14a output for upload instructions

3. **Upload via Digital Uploader:**
   - Use Alma's Digital Uploader tool
   - Follow the XML or CSV method instructions
   - Verify thumbnails appear in Alma records

### Identifier Matching

Function 14a searches for thumbnails using these patterns:
- `*grinnell_12205*.clientThumb*`
- `*grinnell_12205*.jpg`
- `*dg_12205*.clientThumb*`
- `*dg_12205*.jpg`

So your Function 19 thumbnails must be renamed to match:
```
Original:  991234567890104641_rep1_MASTER_thumbnail.jpg
Check bib record for identifier: grinnell:12205
Rename to: grinnell_12205_thumbnail.jpg
```

## Output and Results

### Success Metrics

The function reports:
- **Records processed**: Number of MMS IDs that had representations
- **Thumbnails created**: Total number of thumbnail files generated
- **No representations**: Records without any digital representations
- **No accessible files**: Representations whose files couldn't be accessed locally
- **Failed**: Records that encountered errors

### Example Output

```
Thumbnail creation complete:
  • 45 records processed
  • 89 thumbnails created
  • 3 records had no representations
  • 12 representations had no accessible files
  • 0 failed

Output: /Users/username/Downloads/CABB_rep_thumbnails_20260424_143052
See README.txt for instructions on selecting and attaching thumbnails
```

### CSV File

Function 19 does **not** create a CSV file (unlike many other functions).
- Thumbnails are self-documenting via filename
- README provides all necessary instructions
- Visual review is the primary workflow

## Important Notes

### File Accessibility

**File Location Strategy**: Function 19 uses a two-step approach:

1. **Exact Path Match**: Checks if the path returned by Alma exists locally
2. **Filename Search**: If not found, searches for the file by name in the configured search directory

**Files Must Be Accessible:**
- On your local file system
- On mounted network drives
- On connected external drives
- In the configured `REP_FILES_SEARCH_PATH` directory (or subdirectories)

**Cannot Access:**
- Files only in Alma S3 storage (no direct download URLs via API)
- Files on unmounted network shares
- Files in cloud storage not mounted locally
- Files outside the search directory if exact path doesn't match

**Example Scenarios:**

✅ **Exact Path Works:**
```
Alma path: /Volumes/DGIngest/storage/grinnell_12205_OBJ.tif
Volume mounted: Yes
Result: ✓ Found at exact path
```

✅ **Filename Search Works:**
```
Alma path: 01GCL_INST/storage/alma/.../grinnell_12205_OBJ.tif
Search path: /Volumes/Acasis1TB
File exists: /Volumes/Acasis1TB/TIFF-Masters/grinnell_12205_OBJ.tif
Result: ✓ Found by filename search
```

✗ **File Not Accessible:**
```
Alma path: 01GCL_INST/storage/alma/.../grinnell_12205_OBJ.tif
Search path: Not configured or doesn't contain file
Result: ✗ File not accessible
Tip: Set REP_FILES_SEARCH_PATH env var
```

### Representation Order

- Thumbnails are numbered based on Alma's representation order
- `rep1` is typically the first/primary representation
- Order may vary by record depending on when representations were added
- No assumption should be made about which rep number is "best"

### Thumbnail Size

- Default: 200x200 pixels maximum (preserves aspect ratio)
- Can be modified by editing function parameter in code
- Larger sizes = better quality but larger files
- Smaller sizes = faster processing but less detail

### Color Modes

Function 19 handles various image modes:
- **RGBA** (transparent PNG): Converted to RGB with white background
- **Grayscale**: Converted to RGB
- **Palette**: Converted to RGB
- **CMYK**: Converted to RGB (if source is CMYK TIFF)

All output thumbnails are RGB JPEG files.

## Troubleshooting

### Understanding the Logs

**First Step**: Always check the detailed log output. Function 19 now provides extensive logging with emoji indicators to help you quickly identify issues.

**Key Log Sections to Check**:
1. **Startup** - Confirms search directory is configured and accessible
2. **Per-Record** - Shows exactly what happens for each MMS ID
3. **File Search** - Details whether files were found and where
4. **Summary** - Reports overall success/failure statistics

**Log Indicators**:
- ✅ = Success
- ❌ = Error
- ⚠️ = Warning
- 🔍 = Searching

### No Thumbnails Created

**Problem**: Function completes but creates 0 thumbnails

**Diagnosis**: Check the log output for these messages:
```
⚠️  No search directory configured
```
or
```
❌ NOT FOUND - file does not exist in search directory tree
```

**Causes:**
1. Representation files not accessible locally
2. Search directory not configured or doesn't contain files
3. Files only in Alma S3 storage (and not copied locally)
4. Representations exist but have no files attached
5. Wrong file paths in Alma representation metadata

**Solutions:**
- **Set search directory**: Add `REP_FILES_SEARCH_PATH=/path/to/files` to `.env`
- **Verify in logs**: Look for `✅ Search directory verified` message
- **Check paths**: Log shows exactly where it searched and what filename it looked for
- **Mount network drives** where files are stored
- **Copy files locally** from S3 or network storage

**Enhanced Troubleshooting**:
The logs now show:
```
🔍 Checking REP_FILES_SEARCH_PATH environment variable...
   Environment value: /Users/mcfatem/Downloads/
```
If this shows `(not set)`, add it to your `.env` file.

### PDF Conversion Failures

**Problem**: PDFs are found but thumbnails not created

**Diagnosis**: Check log for:
```
❌ pdf2image library not installed
```
or
```
❌ Failed to convert PDF: ...
```

**Causes:**
1. `pdf2image` Python library not installed
2. `poppler` system dependency not installed
3. Corrupt PDF file
4. Password-protected PDF
5. Unsupported PDF version

**Solutions:**
- **Install pdf2image**: Run `pip install pdf2image` in your venv
- **Install poppler**: 
  - macOS: `brew install poppler`
  - Ubuntu: `sudo apt-get install poppler-utils`
  - Windows: Download from https://github.com/oschwartz10612/poppler-windows
- **Verify installation**: Run `which pdfinfo` (should return a path)
- **Test PDF**: Try opening the PDF file manually to verify it's not corrupt
- **Check file permissions**: Ensure you have read access to the PDF

**Example Log Output**:
```
📄 Processing PDF file: document.pdf
   📑 Converting first page of PDF to image...
   ✓ Created thumbnail: 991234567890104641_rep1_VIEW_thumbnail.jpg (42.3 KB)
```

### Thumbnails Are Blank or Corrupted

**Problem**: Thumbnails created but appear blank, black, or corrupted

**Causes:**
1. Source files are corrupted
2. Source files are multi-page TIFFs (only first page extracted)
3. Color space issues
4. Very large source files causing memory issues

**Solutions:**
- Check source files in their original format
- Verify files open correctly in image viewer
- For multi-page TIFFs, only first page is used
- Ensure adequate system memory

### Wrong Thumbnails Selected

**Problem**: Attached wrong representation as thumbnail

**Causes:**
1. Didn't compare all representations visually
2. Assumed rep1 is always best
3. Misread filenames during selection

**Solutions:**
- Always review thumbnails visually before selecting
- Compare all `rep{NUM}` variants for each record
- Use descriptive file naming during selection process
- Create a selection spreadsheet for large batches

### Function 14a Can't Find Thumbnails

**Problem**: Function 14a reports "No thumbnail file found"

**Causes:**
1. Thumbnail filenames don't match identifier pattern
2. Thumbnails in wrong directory
3. Missing required identifier in bib record

**Solutions:**
- Verify bib records have `grinnell:` or `dg_` identifiers
- Rename thumbnails to match identifier format
- Check Function 14a is looking in correct directory
- Review Function 14a thumbnail search patterns

## Best Practices

### Planning

1. **Start Small**: Test with 5-10 records first
2. **Verify File Access**: Ensure representation files are locally accessible
3. **Check Disk Space**: Thumbnails are small but source files may be large
4. **Review Identifier Patterns**: Confirm records have identifiers that match Function 14a patterns

### Processing

1. **Batch Wisely**: Process 50-100 records at a time for easier review
2. **Name Directories**: Use descriptive timestamps or batch names
3. **Log Results**: Save log output to track what was processed
4. **Backup Source Files**: Don't modify original representation files

### Review Process

1. **Systematic Review**: Review one record's thumbnails at a time
2. **Document Decisions**: Note why you chose specific representations
3. **Quality Check**: Verify selected thumbnails are clear and representative
4. **Spot Check After Upload**: Verify attachments in Alma after upload

### Selection Strategy

1. **Prefer Derivatives**: DERIVATIVE_COPY usually best for thumbnails (already optimized)
2. **Avoid Masters**: MASTER TIFFs may be unnecessarily large
3. **Check First Page**: For multi-page documents, ensure first page is representative
4. **Consider Context**: Match thumbnail to what users will see in public interface

## Related Functions

### Function 14a: Prepare Thumbnails
- **Purpose**: Upload thumbnails to Alma (final step after Function 19)
- **Input**: Directory of thumbnail files
- **Output**: Representations created, files prepared for upload
- **Use After**: Function 19 selection process

### Function 18: Identify Single TIFF Objects
- **Purpose**: Find records with single TIFF representations (no derivatives)
- **Input**: Set of MMS IDs
- **Output**: CSV of records needing derivatives
- **Use Before**: Function 19 (to identify which records might benefit from new thumbnails)

### Function 11: Prepare TIFF/JPG Representations
- **Purpose**: Create JPG derivatives from TIFF masters
- **Input**: TIFF files and CSV mapping
- **Output**: JPG files and representations
- **Use Before**: Function 19 (creates derivatives that can be used for thumbnails)

## Workflow Example

### Complete Thumbnail Creation Workflow

**Scenario**: You have 100 records with TIFF master files and want to add thumbnails to each.

**Steps:**

1. **Run Function 18**: Identify records with single TIFF (no JPG derivative)
   ```
   Output: single_tiff_objects_20260424_140000.csv
   ```

2. **Run Function 11**: Create JPG derivatives from TIFFs
   ```
   Input: TIFF CSV from Function 18
   Output: JPG files and representations created
   ```

3. **Run Function 19**: Create thumbnails from representations
   ```
   Input: MMS IDs from Function 18
   Output: ~/Downloads/CABB_rep_thumbnails_20260424_143052/
   Contains: Thumbnails from both TIFF masters and JPG derivatives
   ```

4. **Review Thumbnails**: Open output directory, switch to Icon View
   - Compare `rep1` (TIFF master) vs `rep2` (JPG derivative) for each record
   - Usually JPG derivatives (rep2) are better for web thumbnails

5. **Select Thumbnails**: 
   - Create `selected/` subfolder
   - Copy best thumbnail for each record to `selected/`
   - Rename: `991234567890104641_rep2_DERIVATIVE_COPY_thumbnail.jpg` → `grinnell_12205_thumbnail.jpg`

6. **Run Function 14a**: Prepare thumbnails for upload
   ```
   Input: MMS IDs + selected/ folder
   Output: Representations created, files optimized
   ```

7. **Upload**: Use Alma Digital Uploader
   ```
   Upload prepared files from Function 14a output directory
   ```

8. **Verify**: Check records in Alma
   - Confirm thumbnails appear in Digital Viewer
   - Test in public interface (Primo/Discovery)

## References

- **Function 14a Documentation**: `FUNCTION_14a_PREPARE_THUMBNAILS.md`
- **Function 18 Documentation**: `FUNCTION_18_IDENTIFY_SINGLE_TIFF.md`
- **Function 11 Documentation**: `FUNCTION_11_PREPARE_TIFF_JPG.md`
- **Alma API**: Representations API documentation
- **Pillow Documentation**: https://pillow.readthedocs.io/

## Technical Details

### API Endpoints Used

```
GET /almaws/v1/bibs/{mms_id}/representations
  - Fetches list of representations for a record
  - Returns: representation metadata, file links

GET /almaws/v1/bibs/{mms_id}/representations/{rep_id}/files
  - Fetches file list for a representation
  - Returns: file metadata, paths, MIME types
```

### Dependencies

**Python Libraries:**
- **Pillow (PIL)**: Required for image processing
- **pdf2image**: Required for PDF thumbnail generation
- **requests**: For API calls (already required by CABB)
- **pathlib**: For file path handling (Python 3 built-in)

**System Dependencies:**
- **poppler**: Required for pdf2image to convert PDFs
  - Install on macOS: `brew install poppler`
  - Install on Ubuntu: `sudo apt-get install poppler-utils`
  - Install on Windows: Download from https://github.com/oschwartz10612/poppler-windows

**Verification:**
```bash
# Check Python libraries
pip list | grep -E 'Pillow|pdf2image'

# Check poppler installation
which pdfinfo  # Should return: /opt/homebrew/bin/pdfinfo (or similar)
```

### Image Processing Details

**For Image Files (TIFF, JPEG, PNG):**
- Opens image using Pillow
- Converts to RGB color space (handles RGBA, CMYK, Grayscale, Palette)
- Creates thumbnail preserving aspect ratio
- Saves as JPEG with 85% quality

**For PDF Files:**
- Renders first page at 200 DPI (high quality)
- Converts to RGB color space
- Creates thumbnail preserving aspect ratio  
- Saves as JPEG with 85% quality

**Color Conversion:**
- RGBA → RGB with white background
- CMYK → RGB
- Grayscale → RGB
- Palette → RGB

### Performance

- **Speed**: ~2-5 seconds per record (depends on file size and count)
  - Image files: 1-2 seconds per file
  - PDF files: 2-4 seconds per file (rendering takes longer)
- **Memory**: Moderate (images loaded into memory temporarily)
- **Disk**: Output thumbnails typically 10-50 KB each
- **Network**: Only for API calls (minimal data transfer)

### Error Handling

The function handles:
- Missing representations
- Inaccessible files
- Corrupt image files
- Network/API errors
- Disk space issues
- Permission errors

Errors are logged but don't stop batch processing.

---

**Function Status**: ✅ Active - Ready for production use

**Last Updated**: April 24, 2026

**Recent Enhancements**:
- Enhanced logging with emoji indicators for better visibility (April 2026)
- PDF thumbnail support with first-page extraction (April 2026)
- Recursive filename search in configured directories (April 2026)
- Detailed troubleshooting output showing exact search paths (April 2026)

**Related Issues**: File accessibility for Alma S3-only files remains a limitation
