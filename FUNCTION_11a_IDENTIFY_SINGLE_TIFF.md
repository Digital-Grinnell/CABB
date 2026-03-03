# Function 11a: Prepare TIFF/JPG Representations (Part 1 of 2)

## Overview

**Function 11a** prepares JPG derivative files from TIFF source files for upload to Alma-D:

1. Creates DERIVATIVE_COPY representations in Alma with proper metadata
2. Processes TIFF files (TIFF→JPEG conversion, 16-bit handling)
3. Saves processed JPG files to a timestamped output directory in `~/Downloads/CABB_tiff_jpg_prep_YYYYMMDD_HHMMSS/`
4. Generates a CSV file mapping MMS IDs to representation IDs

**Note**: This function creates representations and prepares files but does **not** upload the actual files (due to Alma API limitations). Function 11b handles the file upload step.

## What It Does

This function processes bibliographic records that have corresponding TIFF files and:
1. Finds TIFF files from the CSV mapping (`all_single_tiffs_with_local_paths.csv`)
2. Creates JPG representations in Alma
3. Processes files (converts TIFF to JPEG, handles 16-bit images)
4. Saves everything to a timestamped directory for Function 11b

### TIFF-to-Filename Mapping

**CSV Structure:**
The function reads `all_single_tiffs_with_local_paths.csv` which contains:
- `MMS ID`: Alma bibliographic record ID
- `Local Path`: Full path to the TIFF file on the local system

**Examples:**
```csv
MMS ID,Local Path
991234567890104641,/Volumes/DGIngest/Photos/photo_001.tif
991234567890204641,/Volumes/DGIngest/Photos/photo_002.tiff
```

### Smart Processing Logic

The function implements intelligent record filtering to avoid unnecessary processing:

#### Records That Get Processed
✅ Records with a local TIFF file path in the CSV AND file exists on disk

**Example:**
- Has: MMS ID in CSV with valid Local Path
- Found: File exists at that path
- **Action**: Creates representation, converts TIFF to JPG, saves to output directory

#### Records That Get Skipped
⊘ **No path in CSV**: MMS ID not found in `all_single_tiffs_with_local_paths.csv`
- **Message**: "No local path found in CSV"
- **Reason**: Cannot locate the TIFF file

⊘ **File not found**: Path exists in CSV but file doesn't exist on disk
- **Message**: "File not found: [path]"
- **Reason**: TIFF file may have been moved or deleted
- **Note**: Check that network volumes are mounted

## Processing Flow

### Step-by-Step Process

1. **Read CSV**: Loads `all_single_tiffs_with_local_paths.csv` to build MMS ID → TIFF path mapping
2. **For Each MMS ID**:
   - Look up TIFF path from CSV
   - Verify TIFF file exists
   - Check for existing JPG representation in Alma (reuses if found empty)
   - Create JPG representation in Alma (if needed)
   - Convert TIFF to JPG with special handling for:
     - 16-bit images (scales to 8-bit properly)
     - RGBA/LA/P modes (converts with white background)
     - Grayscale images (converts to RGB)
   - Save JPG to output directory
   - Record entry in CSV for Function 11b

3. **Generate Output CSV**: Creates CSV with columns:
   - `mms_id`: Alma bibliographic record ID
   - `rep_id`: Representation ID (created by this function)
   - `jpg_filename`: Full path to processed JPG file
   - `tiff_filename`: Full path to original TIFF file (for reference)

## Requirements

### Prerequisites
- **Pillow library**: Required for image processing
  ```bash
  pip install Pillow
  ```
- **TIFF CSV file**: `all_single_tiffs_with_local_paths.csv` must exist in workspace
- **Network volumes**: Any network volumes containing TIFF files must be mounted
- **Alma API key**: Must be configured in CABB

### TIFF File Access
- TIFF files must be accessible at the paths specified in the CSV
- Network volume disconnections may cause failures
- Large TIFF files (100+ MB) will take longer to process

## Output

### Directory Structure
```
~/Downloads/CABB_tiff_jpg_prep_20260303_143052/
├── tiff_jpg_representations_20260303_143052.csv
├── photo_001.jpg
├── photo_002.jpg
└── photo_003.jpg
```

### CSV File Format
```csv
mms_id,rep_id,jpg_filename,tiff_filename
991234567890104641,23156789012345678,/Users/you/Downloads/CABB_tiff_jpg_prep_20260303_143052/photo_001.jpg,/Volumes/DGIngest/Photos/photo_001.tif
```

### File Processing Details
- **Format**: All output files are JPEG format
- **Quality**: 95% quality (high quality)
- **Color Mode**: RGB (converted from source if needed)
- **Bit Depth**: 8-bit (16-bit sources scaled properly)
- **Optimization**: JPEG optimize flag enabled

## How to Use

### Step 1: Prepare TIFF CSV
1. Ensure `all_single_tiffs_with_local_paths.csv` exists with correct paths
2. Verify network volumes are mounted if needed
3. Check that TIFF files are accessible

### Step 2: Load Your Set
1. Enter a Set ID in the "Set ID" field
2. Click "Load Set Members"
3. Verify the correct records are loaded (preview shows first 20)

### Step 3: Run Function 11a
1. Select **"11a: Prepare TIFF/JPG Representations (Part 1 of 2)"** from the function dropdown
2. Click **"Run Function on Set"**
3. Review the warning dialog and click "Proceed"
4. Wait for processing to complete (may take time for large sets or large files)
5. Check log output for summary statistics
6. **Note the CSV path** - it will be auto-populated in the Set ID field for Function 11b

### Step 4: Review Results
1. Check the output directory in `~/Downloads/CABB_tiff_jpg_prep_*/`
2. Verify JPG files were created correctly
3. Review the CSV file for any failures
4. Proceed to Function 11b to upload the JPG files

## Representation Positioning

**Important**: Alma uses the **first representation** as the primary display. This function:
- Reuses existing empty DERIVATIVE_COPY representations if found
- Creates new representations if none exist
- Warns if the representation is not in first position

**If representation is not first:**
- Alma may not use it for primary display
- You may need to manually reorder representations in Alma UI after upload

## Error Handling

### Common Errors

**"TIFF CSV not found"**
- **Cause**: `all_single_tiffs_with_local_paths.csv` doesn't exist
- **Solution**: Generate the CSV using Function 11 (old) or create it manually

**"No local path found in CSV"**
- **Cause**: MMS ID not in the CSV file
- **Solution**: Add the MMS ID and path to the CSV, or remove from set

**"File not found"**
- **Cause**: TIFF file doesn't exist at the specified path
- **Solution**: Verify path in CSV, check network volumes are mounted

**"Pillow library not installed"**
- **Cause**: PIL/Pillow not available
- **Solution**: Run `pip install Pillow`

**"Failed to create representation: HTTP 400"**
- **Cause**: Invalid representation data or API issue
- **Solution**: Check API key, verify MMS ID exists in Alma

### Progress Tracking
The function shows:
- Progress bar with percentage complete
- Current/total record count
- Status messages for each operation
- Summary of successful and failed operations

## Next Steps

After Function 11a completes successfully:
1. **Review the output** in `~/Downloads/CABB_tiff_jpg_prep_*/`
2. **Verify JPG files** look correct
3. **Note the CSV path** (auto-populated in Set ID field)
4. **Run Function 11b** to upload the JPG files to Alma

## Notes

- JPG quality is set to 95 for high-quality derivatives
- Original TIFF files are not modified
- 16-bit TIFF images are properly scaled to 8-bit
- Network volume disconnections will cause failures
- Progress is saved incrementally to the CSV file
- The output directory can be deleted after successful upload (Function 11b will offer this option)

## Relationship to Function 14a

Function 11a follows the same pattern as Function 14a:
- Both create representations via API
- Both process image files
- Both generate CSV files for their respective "b" functions
- Both save processed files to timestamped directories

The main differences:
- 11a: TIFF → JPG conversion, uses CSV path mapping
- 14a: PNG → JPEG conversion, uses identifier matching


## Purpose
Identifies digital objects in Alma that have only a single TIFF file as their representation. These objects typically need a JPG derivative created from the TIFF and added as the primary representation for better web display performance.

**Note:** This function identifies objects that need JPG derivatives but does not automatically create them. The Alma API does not provide direct file download access for programmatic TIFF retrieval, so JPG creation must be done manually or through Alma's built-in derivative tools.

## What It Does

1. **Analyzes Each Record** - For each record in the loaded set:
   - Retrieves the digital representation information from Alma
   - Counts the number of files in the representation
   - Identifies the file format(s) present

2. **Identifies TIFF-Only Objects** - Flags records that meet these criteria:
   - Has exactly **one representation**
   - That representation contains exactly **one file**
   - That file is a **TIFF** format (.tif or .tiff)

3. **Exports Results** - Creates a CSV file with:
   - MMS ID for reference
   - Title of the object
   - Representation ID
   - File name of the TIFF
   - File size
   - Recommended action

## Why This Matters

### Performance Issues
- **TIFF files are large** - Often 10-100+ MB per file
- **Slow web display** - TIFFs take longer to load in browsers
- **Poor user experience** - Users wait longer to view images

### Best Practice Solution
- **Create JPG derivative** - Smaller file size (typically 1-5 MB)
- **Set JPG as primary** - Fast loading for web display
- **Keep TIFF as preservation** - Original quality maintained
- **Better accessibility** - JPGs display in more browsers/devices

## Output

### File Name
- `single_tiff_objects_YYYYMMDD_HHMMSS.csv`
- Timestamped to prevent overwriting previous exports

### CSV Structure
```csv
MMS ID,Title,Representation ID,TIFF Filename,File Size (MB),Recommended Action
991012345678904641,"Historical Photograph, 1920",23156789012345678,photo_001.tif,45.3,Create JPG derivative and set as primary
```

### Column Descriptions

| Column | Content | Purpose |
|--------|---------|---------|
| **MMS ID** | Alma bibliographic record ID | Locate the record in Alma |
| **Title** | dc:title value | Identify what the object is |
| **Representation ID** | Digital representation ID | Reference for API operations |
| **TIFF Filename** | Name of the TIFF file | Identify the source file |
| **File Size (MB)** | Size in megabytes | Assess storage/processing impact |
| **Recommended Action** | Standard recommendation | Next steps for remediation |

## How to Use

### Step 1: Load Your Set
1. Enter a Set ID in the "Set ID" field
2. Click "Load Set Members"
3. Verify the correct records are loaded (preview shows first 20)

### Step 2: Run the Function
1. Select **"Identify Single TIFF Representations"** from the function dropdown
2. Click **"Run Function on Set"**
3. Wait for processing to complete (may take time for large sets)
4. Check log output for summary statistics

### Step 3: Review the Results
1. Open the generated CSV file
2. Review the list of TIFF-only objects
3. Prioritize based on:
   - File size (larger files = higher priority)
   - Collection importance
   - ExpecteCreate JPG Derivatives

**Important:** Automatic JPG creation is not available through this function due to Alma API limitations. Use one of these manual workflows:

#### Option A: Alma's Built-in Tools
1. In Alma, navigate to the digital representation
2. Use Alma's derivative generation tools
3. Create JPG derivative (recommended: 2000px longest edge)
4. Set JPG as primary display file

###Limitations

### Why Automatic JPG Creation Isn't Available

The Alma API does not provide direct programmatic access to download digital file content. While the API can:
- ✅ List files in representations
- ✅ Retrieve file metadata (name, size, format)
- ✅ Upload new files to representations

It cannot:
- ❌ Download file content directly via API endpoints
- ❌ Provide authenticated delivery URLs for programmatic access
- ❌ Stream file content for automated processing

This means TIFF files cannot be automatically downloaded, converted to JPG, and re-uploaded through this function. The workflow requires manual intervention or institutional-specific solutions with direct repository access.

## # Option B: Manual Download and Conversion
1. Download TIFFs from Alma manually
2. Use ImageMagick, Photoshop, or similar tools to create JPGs
3. Upload JPG derivatives to Alma
4. Set JPGs as primary display files

**ImageMagick Batch Conversion Example:**
```bash
# Convert all TIFFs in current directory
for file in *.tif; do
    convert "$file" -resize 2000x2000\> -quality 85 -colorspace sRGB "${file%.tif}.jpg"
done
```

#### Option C: Scripted Workflow (Advanced)
For large batches, consider creating a custom script that:
1. Uses Alma's delivery URLs (requires institutional access)
2. Downloads TIFFs from your institution's digital repository
3. Batch converts to JPG
4. Uploads via Alma API's file upload endpointn the same representation
4. Set JPG as the primary/display file
5. Keep TIFF as preservation master

## Processing Details

### API Calls Required
- **Batch bibs call** - Retrieve metadata for 100 records at once
- **Individual representations call** - Get digital files for each record
  - Note: This is the performance bottleneck for large sets

### Progress Tracking
- Updates logged every 50 records
- Shows counts: Total processed, TIFF-only found, multi-file, other formats

### Performance Expectations
- **Small sets (< 100)**: 2-5 minutes
- **Medium sets (100-500)**: 10-30 minutes
- **Large sets (500+)**: 30+ minutes

The function must make individual API calls to check representations, which is slower than batch operations.

## Filtering Criteria

### Included (Exported)
✅ Records with exactly 1 representation containing exactly 1 TIFF file

### Excluded (Not Exported)
❌ Records with no digital representations
❌ Records with multiple representations
❌ Records with multiple files in representation (even if all TIFFs)
❌ Records where the single file is NOT a TIFF (JPG, PDF, etc.)
❌ Records that already have both TIFF and JPG files

## Common Scenarios

### Scenario 1: Single Page Document
- **Issue**: Historical document scanned as one TIFF
- **Detection**: Function identifies it
- **Solution**: Create JPG derivative for web display

### Scenario 2: Single Photograph
- **Issue**: Photo digitized as high-res TIFF only
- **Detection**: Function identifies it
- **Solution**: Create JPG derivative, set as primary

### Scenario 3: Multi-Page Document
- **Issue**: 20-page document with 20 TIFF files
- **Detection**: NOT flagged (multiple files)
- **Note**: Different workflow needed (possibly create PDF)

### Scenario 4: Already Has Derivatives
- **Issue**: Object has both TIFF and JPG
- **Detection**: NOT flagged (multiple files)
- **Note**: No action needed, already has web-friendly format

## Best Practices

### Before Processing
1. **Start with small test set** - Verify function works as expected
2. **Check disk space** - Ensure adequate space for downloading TIFFs
3. **Prepare image processing workflow** - Have tools ready (Photoshop, ImageMagick, etc.)

### During Review
1. **Prioritize large files** - Sort CSV by file size, handle biggest first
2. **Batch similar items** - Process photos together, documents together
3. **Document standards** - Define JPG quality settings for consistency

### Creating JPG Derivatives
**Recommended Settings:**
- **Dimensions**: 2000px longest edge (maintains quality for zoom)
- **Quality**: 85% (good balance of quality vs file size)
- **Color space**: sRGB (web standard)
- **Format**: Progressive JPG (better web loading)

**ImageMagick Command Example:**
```bash
convert input.tif -resize 2000x2000\> -quality 85 -colorspace sRGB output.jpg
```

### After Creating Derivatives
1. **Upload to Alma** - Add JPG to the same representation
2. **Set as primary** - Make JPG the default display file
3. **Verify in viewer** - Check that JPG displays correctly
4. **Keep TIFF** - Retain as preservation master
5. **Update documentation** - Note when derivatives were created

## Error Handling

### Records Without Representations
- Logged as INFO level
- Not included in export
- Count shown in final summary

### API Errors
- Individual failures logged with MMS ID
- Processing continues for remaining records
- Failed records noted in summary

### Unexpected File Formats
- If representation analysis fails, logged as WARNING
- Record skipped, processing continues

## Related Functions

- **Function 3**: Export Set to DCAP01 CSV - See full metadata for these objects
- **Function 10**: Export for Review - Manually verify TIFF objects in viewer

## Example Workflow

1. **Identify candidates**: Run Function 11 on a collection set
2. **Export results**: CSV shows 47 objects with single TIFFs
3. **Download TIFFs**: Use Alma interface or API to download files
4. **Batch convert**: Use ImageMagick to create JPG derivatives
5. **Upload JPGs**: Add to Alma representations
6. **Set primaries**: Configure JPGs as display files
7. **Verify**: Run Function 10 to manually check in viewer
8. **Document**: Archive the CSV as record of batch processing

## Technical Notes

### File Format Detection
The function checks file extensions to identify TIFF files:
- `.tif`
- `.tiff`
- Case-insensitive matching

### API Endpoints Used
- Bibs API (batch): `/almaws/v1/bibs`
- Representations API: `/almaws/v1/bibs/{mms_id}/representations`

### Rate Limiting
- Alma API has rate limits (typically 25 requests/second)
- Function includes delays to respect limits
- Large sets may take considerable time

## Troubleshooting

### "No representations found"
**Cause**: Records don't have digital objects attached

**Solution**: 
- Verify you're running on correct set
- Check records in Alma to confirm digital representations exist

### "All records have multiple files"
**Cause**: Objects already have derivatives or are multi-page

**Solution**: 
- This is good! Means derivatives already exist
- No action needed for this set

### "Function running very slowly"
**Cause**: Must make individual API calls for each record's representations

**Solution**: 
- This is expected behavior
- Consider splitting very large sets into smaller batches
- Run during off-hours if processing thousands of records

### "TIFF file won't convert"
**Cause**: TIFF may be corrupted or use unusual compression

**Solution**: 
- Try opening in different software (Photoshop, GIMP, etc.)
- Check TIFF properties for unusual settings
- May need specialized conversion tools
