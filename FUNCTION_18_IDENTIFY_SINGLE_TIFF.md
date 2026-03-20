# Function 18: Identify Single TIFF Objects

## Overview

**Identifies bibliographic records that have only a single TIFF representation with no corresponding JPG derivative.**

This function analyzes digital objects in your Alma repository and creates a CSV report listing all records where:
- The record has exactly **one** digital representation
- That representation contains exactly **one** file
- That file is a TIFF image (`.tif` or `.tiff`)

This is useful for identifying records that may need JPG derivatives added for better web display and access.

---

## When to Use This Function

Use Function 18 when you need to:

1. **Audit your digital repository** - Identify which objects only have TIFF files
2. **Plan JPG creation workflows** - Generate a list of records needing web-friendly derivatives
3. **Quality control** - Find records that may be incomplete or missing expected files
4. **Migration planning** - Understand your repository composition before bulk operations

### Typical Workflow

```
1. Load a set of records (e.g., all images from a collection)
2. Run Function 18 to identify single-TIFF objects
3. Review the CSV output
4. Use Function 11 (Prepare TIFF/JPG) to create JPG derivatives for these records
```

---

## How It Works

### Process Flow

```
┌─────────────────────────────────────────────┐
│ Load Set (Batch Mode Required)             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ For Each Record in Set:                    │
│  1. Fetch representation list from Alma    │
│  2. Check: Exactly 1 representation?       │
│  3. Check: Exactly 1 file in rep?          │
│  4. Check: File extension is .tif/.tiff?   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Generate CSV Report                         │
│ - MMS ID                                    │
│ - Title                                     │
│ - Representation ID                         │
│ - TIFF Filename                             │
│ - S3 Path                                   │
│ - File Size (MB)                            │
│ - Recommended Action                        │
│ - Status                                    │
└─────────────────────────────────────────────┘
```

### What Gets Excluded

The function **does not** include records with:
- No digital representations
- Multiple representations (e.g., TIFF + JPG already exists)
- Multiple files in a single representation
- Non-TIFF files (e.g., PDF, MP3, JPG-only)

---

## Step-by-Step Instructions

### Prerequisites

✅ **Required:**
- Active Alma API connection
- Itemized set loaded with MMS IDs
- Batch mode (single record mode not supported for this function)

### Steps

1. **Load Your Set**
   - Enter a Set ID in the main interface
   - Click "Generate Set"
   - Verify the set loaded successfully (check status bar)

2. **Run Function 18**
   - Click the function button: **"18: Identify Single TIFF Objects"** 🔍
   - Progress bar will appear showing analysis progress
   - Process includes multiple API calls per record (representation + file details)

3. **Monitor Progress**
   - Watch the progress bar and status messages
   - Typical processing speed: ~10 records/second
   - For large sets (1000+ records), this may take several minutes

4. **Review Results**
   - Output CSV file created with timestamp: `single_tiff_objects_YYYYMMDD_HHMMSS.csv`
   - File path automatically copied to "Set ID" field for easy access
   - Check log messages for summary statistics

---

## Output Format

### CSV Columns

| Column                  | Description                                                      |
|-------------------------|------------------------------------------------------------------|
| **MMS ID**              | Alma MMS ID of the bibliographic record                          |
| **Title**               | Primary title from dc:title field                                |
| **Representation ID**   | Internal Alma representation identifier                          |
| **TIFF Filename**       | Name of the TIFF file (usually ends in `_OBJ.tiff`)            |
| **S3 Path**             | Full S3 storage path in Alma                                     |
| **File Size (MB)**      | Size of the TIFF file in megabytes                              |
| **Recommended Action**  | Suggested next step (typically "Create JPG derivative...")      |
| **Status**              | Processing status or notes                                       |

### Example Output

```csv
MMS ID,Title,Representation ID,TIFF Filename,S3 Path,File Size (MB),Recommended Action,Status
991011532695504641,"College Building Photo",12345678,grinnell_5175_OBJ.tiff,01GCL_INST/storage/alma/73/48/56/...,45.3,"Create JPG derivative and set as primary","Manual JPG creation needed"
991011532695604641,"Historic Postcard",12345679,grinnell_5171_OBJ.tiff,01GCL_INST/storage/alma/80/6B/20/...,32.1,"Create JPG derivative and set as primary","Manual JPG creation needed"
```

---

## Understanding the Results

### Summary Statistics

After completion, check the log messages for statistics like:

```
Single TIFF analysis complete: Found 47 objects with single TIFF files.
(3 no reps, 125 multi-file, 18 other formats, 2 failed)
File: single_tiff_objects_20260320_143022.csv
```

**What this means:**
- **47 objects** → Have exactly one TIFF, no JPG (your target records)
- **3 no reps** → Records with no digital representations at all
- **125 multi-file** → Already have multiple files (likely TIFF + JPG)
- **18 other formats** → Have single files but not TIFF (PDF, MP3, etc.)
- **2 failed** → API errors or network issues during processing

---

## What to Do Next

### If You Want to Create JPG Derivatives

1. **Review the CSV** - Verify these are the records you expect
2. **Prepare local TIFF files** - Download or locate the original TIFF files
3. **Create a mapping CSV** - Map MMS IDs to local file paths
4. **Use Function 11** - Run "Prepare TIFF/JPG Representations" to create JPGs

### If Records Should Have JPG Already

If you find records listed that you expected to have JPG files:
- Check Alma directly to verify the representation status
- There may have been a previous upload failure
- Consider re-uploading the JPG representations

---

## Performance Considerations

### Processing Speed

- **API calls per record:** 2-3 (metadata + representations + files)
- **Typical speed:** ~10 records/second (with API rate limiting)
- **Large sets:** 1000 records ≈ 2-3 minutes

### Rate Limiting

The function includes built-in rate limiting (0.1s delay between records) to respect Alma API limits.

### Network Considerations

- Requires stable internet connection
- Includes retry logic for timeouts (3 attempts per API call)
- Failed records are logged and counted separately

---

## Troubleshooting

### Common Issues

#### ⚠️ "This function requires a set (batch mode only)"

**Cause:** No set loaded, or attempting to use single MMS ID mode

**Solution:** Load an itemized set before running this function

---

#### ⚠️ API Timeout Errors

**Cause:** Network issues or Alma API slowness

**Solution:**
- Check your internet connection
- Check Alma API status
- The function will retry automatically (up to 3 times)
- Failed records are logged and you can retry later

---

#### ⚠️ No Records Found (0 single TIFF objects)

**Possible causes:**
- All records already have JPG derivatives ✅ (Good!)
- Records have multiple files per representation
- Records are not image objects (check resource type)
- Records have no digital representations

**Solution:** Review the summary statistics to understand your set composition

---

#### ⚠️ Large Number of "Multi-file" Records

**Meaning:** These records already have multiple files (likely TIFF + JPG)

**Action:** This is usually correct - these records don't need attention

---

## Technical Details

### Function Method

Calls: `AlmaBibEditor.identify_single_tiff_objects()`

**Parameters:**
- `mms_ids`: List of MMS IDs to analyze
- `output_file`: Output CSV filename
- `progress_callback`: Function for progress updates
- `create_jpg`: False (this function only identifies, doesn't create)

### API Endpoints Used

1. **Batch Metadata Fetch**
   - `/almaws/v1/bibs` (batch endpoint)
   - Gets title and basic metadata

2. **Representations List**
   - `/almaws/v1/bibs/{mms_id}/representations`
   - With `expand=p_files` parameter

3. **Files List**
   - `/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files`
   - Gets detailed file information

---

## Related Functions

### Complementary Workflows

- **Function 11**: Prepare TIFF/JPG Representations - Creates JPG derivatives from TIFFs
- **Function 3**: Export Set to CSV - Get full metadata for analysis
- **Function 10**: Export for Review - Create review sheets with Handle links

### Before Function 18

- **Function 3**: Export metadata to understand your set
- **Function 4**: Filter for specific date ranges or criteria

### After Function 18

- **Function 11**: Prepare JPG derivatives for the identified records
- **Manual review**: Verify which records truly need JPG files

---

## Best Practices

### 1. Start with Small Test Sets

If you have a large collection:
1. Create a small test set (10-20 records)
2. Run Function 18 to verify expected results
3. Scale up to full set

### 2. Regular Audits

Run this function periodically to:
- Find newly ingested TIFFs without JPGs
- Identify incomplete upload workflows
- Maintain repository quality

### 3. Document Your Findings

The output CSV serves as a snapshot of your repository state:
- Keep dated copies for comparison
- Track progress over time
- Plan resource allocation for JPG creation

### 4. Coordinate with Function 11

This function pairs naturally with Function 11:
```
Function 18 (Identify) → Review → Function 11 (Prepare) → Upload to Alma
```

---

## Examples

### Example 1: Audit a Postcard Collection

**Scenario:** You want to know which postcards only have TIFF files

```
1. Create itemized set: "Postcards_Collection" (500 records)
2. Load set in CABB
3. Run Function 18
4. Result: 47 postcards with single TIFF files identified
5. Next: Prepare to create JPG derivatives for web display
```

### Example 2: Quality Control After Migration

**Scenario:** After migrating from another system, verify all records have JPGs

```
1. Create set of migrated records (2,000 records)
2. Run Function 18
3. Result: 15 records still missing JPGs
4. Investigate: Were these supposed to have JPGs?
5. Action: Re-upload missing JPG files
```

### Example 3: Collection Assessment

**Scenario:** Understand file formats across a large photograph collection

```
1. Load set: "Historical_Photographs" (5,000 records)
2. Run Function 18
3. Summary: 234 single TIFF, 4,500 multi-file, 200 no rep, 66 other formats
4. Analysis: 90% already have TIFF+JPG, 4.7% need JPG creation
5. Plan: Budget time to create ~234 JPG derivatives
```

---

## FAQ

**Q: Can I use this with a single MMS ID?**

A: No, this function requires batch mode (a loaded set). For single records, use Function 1 to view the record's representations directly.

**Q: What if a record has both TIFF and JPG?**

A: It will not appear in the output - this function only lists records with a *single* TIFF file and no other files.

**Q: Why are some records showing as "failed"?**

A: Common causes include:
- Network timeouts (retries exhausted)
- API errors (500 errors from Alma)
- Malformed data in Alma record
- Check the detailed logs for specific error messages

**Q: Can I filter the results after running?**

A: Yes! The CSV output can be:
- Opened in Excel/Google Sheets for filtering
- Filtered by file size, title, or other columns
- Used as input for Function 11 (Prepare TIFF/JPG)

**Q: How is this different from Function 11?**

A: 
- **Function 18** (this): Identifies and reports records with single TIFFs
- **Function 11**: Actually creates JPG derivatives and prepares for upload
- Use Function 18 first to understand scope, then Function 11 to take action

**Q: What if the S3 path is wrong or file is missing?**

A: This function only reports what Alma's API returns. If paths are incorrect, that's an Alma data issue requiring separate investigation.

---

## Notes

- This is the **original Function 11 behavior** restored as Function 18
- Function 11 was repurposed for TIFF/JPG preparation workflows
- This separation allows clear distinction between "identify" and "prepare" operations
- Simple, focused functionality: just identifies, doesn't modify anything

---

## Version History

- **March 2026**: Function 18 created - restored original "identify single TIFF" functionality
- Separated from Function 11 which was repurposed for TIFF/JPG preparation

---

## Support

For issues or questions:
1. Check the log messages for detailed error information
2. Verify your API connection is working (test with Function 1)
3. Ensure your set loaded correctly
4. Review this help file for common issues

**Remember:** This function is read-only - it analyzes and reports but does not modify any records.
