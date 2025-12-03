# Function 6: Replace old dc:rights with Public Domain link

## Overview

Function 6 automatically replaces outdated copyright statements in Alma bibliographic records with a standardized Public Domain rights statement. This function ensures consistent rights metadata across the digital collection by converting old text-based copyright notices into a properly formatted HTML link.

## What It Does

This function searches for and replaces `dc:rights` fields in bibliographic records that contain outdated copyright statements, replacing them with a standardized Public Domain rights statement link.

### Targeted Rights Statements

The function identifies and replaces the following types of `dc:rights` fields:

1. **Author copyright statements**: Any `dc:rights` field with text starting with:
   - `"Copyright to this work is held by the author(s)"`

2. **Old URL formats**: Any `dc:rights` field containing the rights statement URL but missing the `target="_blank"` attribute:
   - Contains: `https://rightsstatements.org/page/NoC-US/1.0/?language=en`
   - Missing: `target="_blank"` attribute

### Replacement Value

All matching fields are replaced with:

```html
<a href="https://rightsstatements.org/page/NoC-US/1.0/?language=en" target="_blank">Public Domain in the United States</a>
```

This creates a clickable link that:
- Displays as: "Public Domain in the United States"
- Links to: https://rightsstatements.org/page/NoC-US/1.0/?language=en
- Opens in a new browser tab/window (`target="_blank"`)

## Processing Logic

### Duplicate Prevention

The function implements smart duplicate handling to ensure clean metadata:

1. **If the new link already exists in the record:**
   - Remove all old author copyright fields
   - Remove all old links without the target attribute
   - Keep the new link intact

2. **If the new link doesn't exist:**
   - Replace the first old field (author copyright OR old link) with the new link
   - Remove all remaining duplicate old fields

### Step-by-Step Process

1. **Fetch Record**: Retrieves the bibliographic record from Alma as XML
2. **Parse XML**: Parses the XML and identifies all `dc:rights` elements
3. **Categorize Fields**: Sorts rights elements into three categories:
   - New links (with target attribute) ✓
   - Author copyright statements (to be replaced)
   - Old links (without target attribute, to be replaced)
4. **Apply Changes**: Either removes duplicates or replaces/removes old fields
5. **Update Alma**: Sends the modified XML back to Alma

## Operation Modes

### Single Record Mode

Process a single bibliographic record by MMS ID:

1. Enter an MMS ID in the input field
2. Select "Replace old dc:rights with Public Domain link" from the function dropdown
3. Click the function button
4. **Confirm the warning dialog** before proceeding
5. View results in the status area and log

### Batch Mode

Process multiple records from a loaded set:

1. Load a set using "Load Set by ID" or "Load MMS IDs from CSV"
2. (Optional) Set a limit in the "Limit" field to process only the first N records
3. Select "Replace old dc:rights with Public Domain link" from the function dropdown
4. Click the function button
5. **Confirm the warning dialog** showing the number of records to be modified
6. Monitor progress via the progress bar
7. View summary results when complete

**Batch Processing Features:**
- Progress bar shows current record being processed
- Kill switch available to stop processing mid-batch
- Summary shows success/failure counts
- Individual record results logged

## Safety Features

### Confirmation Dialog

Before any modification occurs, a warning dialog appears with:

- ⚠️ Clear warning that Alma data will be PERMANENTLY modified
- Function name and description
- Number of records affected (batch mode) or MMS ID (single mode)
- Red "Proceed" button to continue
- "Cancel" button to abort

**Example Warnings:**

**Single Record:**
```
⚠️ WARNING: This will modify the bibliographic record in Alma.

MMS ID: 991234567890104641
Function: Replace old dc:rights with Public Domain link

This action will PERMANENTLY modify dc:rights fields.

Do you want to continue?
```

**Batch Mode:**
```
⚠️ WARNING: This will modify 150 bibliographic record(s) in Alma.

Function: Replace old dc:rights with Public Domain link

This action will PERMANENTLY modify dc:rights fields in the records.

Do you want to continue?
```

### Additional Safeguards

- **No changes without confirmation**: Operation cannot proceed without explicit user approval
- **API validation**: Alma validates all XML before accepting changes
- **Detailed logging**: Every change is logged with MMS ID and result
- **Error handling**: Failed updates are caught and reported without stopping batch processing
- **Kill switch**: Emergency stop button available during batch operations

## Technical Details

### XML Namespace Handling

The function properly handles Dublin Core namespaces:

- `dc`: http://purl.org/dc/elements/1.1/
- `dcterms`: http://purl.org/dc/terms/

### API Endpoints Used

- **GET** `/almaws/v1/bibs/{mms_id}` - Fetch bibliographic record as XML
- **PUT** `/almaws/v1/bibs/{mms_id}` - Update bibliographic record with modified XML

### Error Handling

Common errors and handling:

- **API Key not configured**: Returns error message, no processing occurs
- **Record fetch failure**: Logs HTTP status code and error details
- **XML parsing error**: Logs error with traceback, skips to next record
- **Update failure**: Logs full error response from Alma, continues batch if applicable

## Output and Logging

### Success Messages

- **Single record**: `"Successfully replaced N dc:rights field(s)"`
- **Batch mode**: `"Batch complete: X succeeded, Y failed out of Z records"`

### Log Entries

The function logs:
- Start of operation with MMS ID
- Number of `dc:rights` elements found
- Each matching field identified
- Replacement or removal actions taken
- API request/response details (first 500 chars)
- Success or failure for each record
- Final summary statistics

### Status Updates

Real-time status updates show:
- Current operation in progress
- Record being processed (batch mode)
- Progress percentage (batch mode)
- Final result summary

## Use Cases

### Bulk Rights Statement Updates

Apply consistent Public Domain statements to a collection of pre-1931 materials:

1. Export set to CSV
2. Filter for pre-1931 dates
3. Load filtered CSV
4. Run Function 6 on the set
5. All old copyright statements updated to standardized link

### Individual Record Correction

Fix a single record with outdated rights metadata:

1. Enter MMS ID
2. Run Function 6
3. Verify update in Alma

### Link Format Standardization

Update records that have the correct URL but incorrect format:

- Old: `https://rightsstatements.org/page/NoC-US/1.0/?language=en`
- New: `<a href="..." target="_blank">Public Domain in the United States</a>`

## Best Practices

1. **Test first**: Try on a single record before running batch operations
2. **Use limits**: For large sets, start with a small limit to verify behavior
3. **Monitor logs**: Watch for patterns in errors or unexpected results
4. **Keep backups**: Alma maintains record history, but document your changes
5. **Verify results**: Spot-check modified records in Alma to confirm expected changes

## Limitations

- Only processes `dc:rights` fields (not other rights metadata fields)
- Matches exact pattern for author copyright statements
- Does not modify rights statements with different wording
- Requires valid Alma API key with appropriate permissions
- Subject to Alma API rate limits for large batch operations

## Related Functions

- **Function 3**: Export Set to CSV - useful for identifying records needing updates
- **Function 4**: Filter CSV for Pre-1931 Dates - commonly used before applying rights updates
- **Function 1**: Fetch and Display XML - verify record structure before/after changes
