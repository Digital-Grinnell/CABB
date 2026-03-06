# Function 16: Add MMS ID as dc:identifier

## Overview

Function 16 automatically ensures that each bibliographic record has its bare MMS ID as a `dc:identifier` field. This function analyzes records to check if the MMS ID exists as an identifier, adds it if missing, and intelligently handles duplicate identifiers by replacing one of them with the MMS ID when appropriate.

## What It Does

This function processes bibliographic records and ensures each record has the MMS ID value in a `dc:identifier` field. It performs intelligent updates based on the existing identifier configuration:

### Processing Logic

The function examines each record and takes action based on what it finds:

#### Records That Get Reported (No Changes)
✅ **MMS ID already present**: Record already has a `dc:identifier` matching the MMS ID
- **Result**: Added to `mms_id_already_present_*.csv`
- **Action**: None needed - record is already correct

#### Records That Get Updated
📝 **No MMS ID identifier found**:
  - **If duplicates exist**: Replace one duplicate `dc:identifier` with the MMS ID
  - **If no duplicates**: Add MMS ID as a new `dc:identifier` field
- **Result**: Added to `mms_id_added_*.csv`
- **Action**: Record updated in Alma

### Duplicate Handling

A key feature of this function is its intelligent handling of duplicate identifiers:

**Example - Record with Duplicates:**
```xml
<!-- Before -->
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>dg_12345</dc:identifier>

<!-- After (if MMS ID is 991234567890104641) -->
<dc:identifier>991234567890104641</dc:identifier>  <!-- Replaced one duplicate -->
<dc:identifier>grinnell:12345</dc:identifier>        <!-- Kept one copy -->
<dc:identifier>dg_12345</dc:identifier>
```

**Example - Record without Duplicates:**
```xml
<!-- Before -->
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>dg_12345</dc:identifier>

<!-- After (if MMS ID is 991234567890104641) -->
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>dg_12345</dc:identifier>
<dc:identifier>991234567890104641</dc:identifier>  <!-- Added as new -->
```

## Processing Flow

### Step-by-Step Process

1. **Fetch Records**: Retrieves bibliographic records from Alma in batches (up to 100 per API call)
2. **Parse XML**: Parses each record and locates all `dc:identifier` elements
3. **Check for MMS ID**: Determines if the MMS ID already exists as an identifier
4. **Analyze Identifiers**: If MMS ID not found:
   - Counts occurrences of each identifier value
   - Identifies duplicates (identifiers appearing 2+ times)
5. **Take Action**:
   - **MMS ID already present** → Skip update, add to report CSV
   - **MMS ID missing + duplicates found** → Replace one duplicate with MMS ID
   - **MMS ID missing + no duplicates** → Add MMS ID as new identifier
6. **Update Alma**: For records needing updates, sends modified XML back to Alma
7. **Generate Reports**: Creates CSV files categorizing all processed records

### XML Manipulation Details

**Namespace Handling:**
The function properly handles Dublin Core namespaces:
- `dc`: http://purl.org/dc/elements/1.1/

**Duplicate Replacement:**
- Locates all `dc:identifier` elements
- Finds first occurrence of duplicate value
- Replaces its text content with MMS ID
- Preserves all other identifiers

**New Identifier Addition:**
- Locates parent element containing existing identifiers
- Creates new `dc:identifier` element
- Appends to parent alongside existing identifiers

## Output Files

The function creates a timestamped directory in your Downloads folder:
```
~/Downloads/CABB_mms_id_identifier_YYYYMMDD_HHMMSS/
```

Within this directory, up to three CSV files are created:

### 1. mms_id_already_present_YYYYMMDD_HHMMSS.csv

Records that already have the MMS ID as a dc:identifier.

**Columns:**
- `MMS ID`: The bibliographic record MMS ID
- `dc:identifier`: The matching identifier value (same as MMS ID)

**Example:**
```csv
MMS ID,dc:identifier
991234567890104641,991234567890104641
991234567890204641,991234567890204641
```

### 2. mms_id_added_YYYYMMDD_HHMMSS.csv

Records that were updated with the MMS ID as a dc:identifier.

**Columns:**
- `MMS ID`: The bibliographic record MMS ID
- `Action`: Type of action taken ("Added new identifier" or "Replaced duplicate")
- `Old Value`: The duplicate value that was replaced (empty if adding new)
- `New Value`: The MMS ID that was added

**Example:**
```csv
MMS ID,Action,Old Value,New Value
991234567890104641,Replaced duplicate,grinnell:12345,991234567890104641
991234567890204641,Added new identifier,,991234567890204641
```

### 3. mms_id_failed_YYYYMMDD_HHMMSS.csv

Records that encountered errors during processing (created only if failures occur).

**Columns:**
- `MMS ID`: The bibliographic record MMS ID
- `Error`: Error message describing what went wrong

**Example:**
```csv
MMS ID,Error
991234567890304641,Failed to fetch record: 404
991234567890404641,Failed to update record: 400 - Invalid XML
```

## Operation Modes

### Single Record Mode

Process a single bibliographic record by MMS ID:

1. Enter an MMS ID in the input field
2. Select "Add MMS ID as dc:identifier" from the function dropdown
3. Click the function button
4. **Confirm the warning dialog** before proceeding
5. View result in the status area and log

**Possible Outcomes:**
- ✓ **Already Present**: "MMS ID already in dc:identifier"
- ✓ **Added**: "Added MMS ID as new dc:identifier"
- ✓ **Replaced**: "Replaced duplicate 'value' with MMS ID"
- ✗ **Error**: Error message with details

### Batch Mode

Process multiple records from a loaded set:

1. Load a set using the Set ID field
2. (Optional) Set a processing limit
3. Select "Add MMS ID as dc:identifier" from the function dropdown
4. Click the function button
5. **Confirm the warning dialog** showing the number of records to be processed
6. Monitor progress via the progress bar
7. Review completion message and CSV reports

**Progress Indicators:**
- Progress bar shows percentage complete
- Status text displays current record being processed
- Log messages show detailed information for each record

**Completion Summary:**
- Number of records already having MMS ID
- Number of records updated
- Number of failed records
- Output directory location

## Safety Features

### Confirmation Dialog

Before processing, a warning dialog appears:

**Single Record:**
```
⚠️ WARNING: This will modify the bibliographic record in Alma.

MMS ID: 991234567890104641
Function: Add MMS ID as dc:identifier

This action will add the MMS ID as a dc:identifier field if not already present.

Do you want to continue?
```

**Batch Processing:**
```
⚠️ WARNING: This will modify up to N bibliographic record(s) in Alma.

Function: Add MMS ID as dc:identifier

This action will:
• Add the bare MMS ID as a dc:identifier field if not already present
• Replace one duplicate dc:identifier with the MMS ID if duplicates exist
• Create CSV files with results in a temporary directory

Do you want to continue?
```

### Kill Switch

During batch processing, you can stop the process:
- Click the "Stop Processing" button (if visible)
- The function will complete the current record and stop
- Already processed records remain updated in Alma
- CSV files will contain records processed up to that point

## Best Practices

### When to Use This Function

✅ **Recommended situations:**
- After bulk imports where MMS IDs weren't added as identifiers
- When normalizing identifier formats across records
- After discovering missing self-referential identifiers
- When cleaning up duplicate identifiers

⊘ **Not necessary when:**
- Records already have MMS ID as dc:identifier (function will skip them)
- You need to preserve all existing duplicates exactly as they are

### Pre-Processing Checklist

Before running this function:

1. ✓ **Backup Strategy**: Ensure you have a backup or can reverse changes if needed
2. ✓ **Test First**: Run on a single record to verify behavior
3. ✓ **Review Set**: Confirm your loaded set contains the intended records
4. ✓ **Set Limit**: For large sets, consider processing in smaller batches first

### Post-Processing Review

After running this function:

1. ✓ **Check CSV Files**: Review the categorization of records
2. ✓ **Verify Updates**: Spot-check updated records in Alma
3. ✓ **Review Failures**: Investigate any records in the failed CSV
4. ✓ **Document Changes**: Keep the CSV files for your records

## Performance Optimization

### Batch API Calls

The function uses efficient batch API calls:
- Fetches up to 100 records per API call
- Dramatically reduces API load for large sets
- Example: 1,000 records = ~10 API calls instead of 1,000

**Efficiency Log Example:**
```
Using batch API calls: 25 calls for 2,434 records
API efficiency: 25 batch calls vs 2,434 individual calls (saved 2,409 calls)
```

### Processing Speed

Typical processing rates:
- Single record: 1-2 seconds
- Batch processing: ~50-100 records per minute
- Large sets (1000+ records): Plan for 10-20 minutes

Factors affecting speed:
- Network latency to Alma API
- XML complexity of records
- Number of identifiers per record
- API rate limits

## Technical Details

### API Endpoints Used

**Retrieve Record:**
```
GET /almaws/v1/bibs/{mms_id}?view=full&expand=None
```

**Update Record:**
```
PUT /almaws/v1/bibs/{mms_id}
```

### Error Handling

The function handles various error scenarios:

**Network Errors:**
- API connection failures
- Timeout errors
- Rate limit responses

**Data Errors:**
- Invalid XML structure
- Missing record elements
- Update conflicts

**All errors are:**
- Logged with details
- Added to failed CSV with error message
- Counted in summary statistics

### Logging Levels

The function logs at multiple levels:
- `INFO`: General progress and statistics
- `DEBUG`: Detailed per-record actions
- `WARNING`: Recoverable issues
- `ERROR`: Failures requiring attention

View detailed logs in the application log window and log file.

## Troubleshooting

### Common Issues

**Issue: "Failed to fetch record: 404"**
- **Cause**: MMS ID doesn't exist or is incorrect
- **Solution**: Verify MMS ID is valid in Alma

**Issue: "Failed to update record: 400"**
- **Cause**: Invalid XML structure or namespace issues
- **Solution**: Check log for XML validation errors; may require manual review

**Issue: "Record not returned in batch API call"**
- **Cause**: Batch API call succeeded but specific record missing
- **Solution**: Retry individual record; check Alma for record status

**Issue: Progress appears stuck**
- **Cause**: Large records or slow API responses
- **Solution**: Wait; check log for activity; use kill switch if needed

### Getting Help

If you encounter persistent issues:

1. Check the CSV files in the output directory
2. Review the application log for detailed error messages
3. Note the MMS IDs of problematic records
4. Test with a single problematic record to isolate the issue
5. Verify API key has necessary permissions

## Examples

### Example 1: Clean Set of Mixed Records

**Input Set:** 500 records, mix of states

**Process:**
1. Load set of 500 records
2. Click Function 16
3. Confirm warning dialog
4. Wait for completion (~5-10 minutes)

**Results:**
- `mms_id_already_present_*.csv`: 125 records (25%)
- `mms_id_added_*.csv`: 370 records (74%)
  - 50 replaced duplicates
  - 320 added new identifiers
- `mms_id_failed_*.csv`: 5 records (1%)

**Next Steps:** Review failures and retry if needed

### Example 2: Single Record with Duplicates

**Record:** MMS ID = 991234567890104641

**Before:**
```xml
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>grinnell:12345</dc:identifier>
```

**After:**
```xml
<dc:identifier>991234567890104641</dc:identifier>
<dc:identifier>grinnell:12345</dc:identifier>
<dc:identifier>grinnell:12345</dc:identifier>
```

**Result:** One duplicate replaced with MMS ID; other duplicates remain

### Example 3: Record Already Correct

**Record:** MMS ID = 991234567890104641

**Identifiers:**
```xml
<dc:identifier>991234567890104641</dc:identifier>
<dc:identifier>grinnell:12345</dc:identifier>
```

**Result:** No change; added to `mms_id_already_present_*.csv`

## Version History

- **v1.0** (March 2026): Initial release
  - Add MMS ID as dc:identifier
  - Intelligent duplicate replacement
  - Batch processing with efficiency
  - CSV report generation
