# Function 11: Identify Single TIFF Representations

## Purpose
Identifies digital objects in Alma that have only a single TIFF file as their representation. These objects typically need a JPG derivative created from the TIFF and added as the primary representation for better web display performance.

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
   - Expected usage frequency

### Step 4: Remediate
For each identified object:
1. Download the TIFF from Alma
2. Create a JPG derivative (recommended: 2000px longest dimension, 80-90% quality)
3. Upload JPG to Alma as new file in the same representation
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
