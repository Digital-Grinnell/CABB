# Function 10: Export for Review with Clickable Handles

## Purpose
Exports a specialized CSV file designed for manual review of digital objects. The CSV includes clickable Handle links and empty columns for reviewers to fill in during their assessment.

## What It Does

1. **Extracts Key Metadata** - For each record in the loaded set:
   - Handle URL (dc:identifier starting with `http://hdl.handle.net/`)
   - MMS ID
   - dc:title
   - dc:type (all type values, semicolon-separated if multiple)

2. **Creates Clickable Links** - The Handle column uses Excel/Google Sheets HYPERLINK formula format, making the URLs clickable when opened in spreadsheet applications

3. **Adds Review Columns** - Three empty columns for manual review:
   - **Thumbnail?** - To verify thumbnail images display correctly
   - **File Opens?** - To verify the digital file opens/plays properly
   - **Needs Attention?** - To flag any issues requiring follow-up

## Output

### File Name
- `Exported_for_Review.csv` (fixed filename, overwrites if exists)

### CSV Structure
```csv
Handle,MMS ID,Title,dc:type,Thumbnail?,File Opens?,Needs Attention?
=HYPERLINK("http://hdl.handle.net/11084/123","http://hdl.handle.net/11084/123"),991012345678904641,Example Document Title,Text; Still Image,,,
```

### Column Descriptions

| Column | Content | Purpose |
|--------|---------|---------|
| **Handle** | Clickable HYPERLINK formula | Click to open the item in browser |
| **MMS ID** | Alma MMS ID | Reference for record lookup |
| **Title** | dc:title value | Identify the item being reviewed |
| **dc:type** | All dc:type values | Know what type of object to expect |
| **Thumbnail?** | Empty | Reviewer marks Y/N/Issues |
| **File Opens?** | Empty | Reviewer marks Y/N/Issues |
| **Needs Attention?** | Empty | Reviewer notes any problems |

## How to Use

### Step 1: Load Your Set
1. Enter a Set ID in the "Set ID" field
2. Click "Load Set Members"
3. Verify the correct records are loaded (preview shows first 20)

### Step 2: Run the Function
1. Select **"Export for Review with Clickable Handles"** from the function dropdown
2. Click **"Run Function on Set"**
3. Wait for processing to complete
4. Check log output for confirmation

### Step 3: Review the Export
1. Open `Exported_for_Review.csv` in Excel, Google Sheets, or LibreOffice Calc
2. The Handle column should be clickable (blue, underlined links)
3. Click each Handle to verify the digital object
4. Fill in the review columns:
   - Enter "Y" (yes), "N" (no), or describe issues
   - Use the "Needs Attention?" column for detailed notes

### Step 4: Process Review Results
1. Filter or sort by review columns to find problems
2. Records with "N" or notes in "Needs Attention?" require follow-up
3. Use the MMS ID to locate records in Alma for corrections

## Review Tips

### Efficient Review Workflow
1. **Sort by dc:type** - Review similar objects together (all images, all PDFs, etc.)
2. **Use filters** - After first pass, filter to show only flagged items
3. **Batch similar issues** - Group records with same problem for efficient fixing
4. **Document patterns** - Note if certain collections/types have recurring issues

### What to Check
- **Thumbnail?**
  - Does a thumbnail image appear in the viewer?
  - Is it the correct thumbnail for this item?
  - Is the image quality acceptable?

- **File Opens?**
  - Does clicking the file link work?
  - Does the file display/play correctly?
  - Are there multiple files? Do all work?

- **Needs Attention?**
  - Wrong thumbnail or file
  - Broken links (404 errors)
  - Poor quality images/files
  - Missing metadata
  - Copyright/permissions issues
  - Anything unusual or incorrect

### Spreadsheet Tips
- **Freeze top row and first columns** - Keep headers and Handle visible while scrolling
- **Use data validation** - Set dropdown lists for Y/N responses
- **Conditional formatting** - Highlight rows with "N" responses in red
- **Add timestamp column** - Track when each record was reviewed

## Technical Details

### API Efficiency
- Uses Alma batch API calls (100 records per call)
- Logs efficiency stats: batch calls vs individual calls
- Progress updates every 50 records

### Handle Link Format
The Handle column uses Excel HYPERLINK formula:
```
=HYPERLINK("url","display_text")
```

This format works in:
- ✅ Microsoft Excel (Windows/Mac)
- ✅ Google Sheets
- ✅ LibreOffice Calc
- ✅ Apple Numbers
- ⚠️ Plain text editors will show the formula, not a clickable link

### Records Without Handles
- Records without Handle URLs are still exported
- Handle column will be empty for these records
- Count is logged: "X with handles, Y without handles"

### Error Handling
- Failed records are logged with error details
- Processing continues for remaining records
- Final summary shows success/failure counts

## Common Issues & Solutions

### Links Not Clickable
**Problem**: Handle column shows formula text instead of clickable links

**Solution**: 
- Open in Excel/Google Sheets/LibreOffice (not plain text editor)
- If formula still visible, the file may have opened in "text mode"
- In Excel: Select the Handle column → Data → Text to Columns → Finish

### Empty Handle Column
**Problem**: Some or all Handle cells are empty

**Cause**: Record doesn't have a dc:identifier field containing a Handle URL

**Solution**:
- Check record in Alma to verify Handle exists
- If missing, use other functions to add/fix identifiers
- Records without Handles cannot be directly accessed via Handle system

### Special Characters in Title
**Problem**: Title displays incorrectly or breaks CSV format

**Cause**: Special characters, quotes, or commas in title field

**Solution**: CSV format handles this automatically with proper escaping. If viewing looks wrong:
- Open in Excel/Sheets (they handle CSV escaping properly)
- Don't edit in plain text editor
- If re-saving, use "CSV UTF-8" format

## Best Practices

### Before Starting
1. **Use appropriate sets** - Create focused sets for review (by collection, date, type, etc.)
2. **Test with small set first** - Verify format works for your workflow
3. **Prepare review guidelines** - Define criteria for "acceptable" thumbnails/files

### During Review
1. **Work systematically** - Don't skip around randomly
2. **Take notes** - Document patterns or unusual issues
3. **Regular saves** - Save your review progress frequently
4. **Batch similar items** - Review all images together, all PDFs together, etc.

### After Review
1. **Share results** - Distribute to team for follow-up actions
2. **Track corrections** - Create issues/tickets for items needing fixes
3. **Re-review** - After fixes, re-run export to verify corrections
4. **Archive** - Keep review CSVs as quality assurance documentation

## Related Functions

- **Function 3**: Export Set to DCAP01 CSV - Full metadata export
- **Function 8**: Export dc:identifier CSV - Focus on identifier fields
- **Function 9**: Validate Handle URLs - Automated HTTP status checking

## Example Workflow

1. Load a set of recently ingested digital objects
2. Run Function 10 to create review CSV
3. Team reviews using the spreadsheet
4. Filter for records marked "Needs Attention?"
5. Catalogers fix identified issues in Alma
6. Re-run Function 10 to verify fixes
7. Run Function 9 to validate all Handles return 200 OK
