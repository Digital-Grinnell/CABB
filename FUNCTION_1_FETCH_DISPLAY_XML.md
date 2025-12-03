# Function 1: Fetch and Display Single XML

## Overview

Function 1 provides a quick way to view the complete XML structure of any bibliographic record in Alma. This read-only function retrieves the full record data and displays it in a formatted, user-friendly dialog window, making it easy to inspect metadata, troubleshoot issues, or understand record structure before making changes.

## What It Does

This function fetches a single bibliographic record from Alma using its MMS ID and displays the complete XML in a popup dialog with syntax formatting and copy functionality.

### Key Features

- **Read-only operation**: No modifications to Alma data
- **Full record retrieval**: Gets complete bibliographic record with all fields
- **Pretty-printed XML**: Automatic formatting with proper indentation
- **Copy to clipboard**: One-click copying of entire XML content
- **Large file handling**: Can display records of any size
- **Character count**: Shows total XML size in the dialog

## How It Works

### Step-by-Step Process

1. **User Input**: Enter an MMS ID in the input field
2. **API Request**: Sends GET request to Alma Bibs API
3. **Receive XML**: Gets raw XML response from Alma
4. **Format XML**: Pretty-prints with indentation and line breaks
5. **Display Dialog**: Opens popup window with formatted XML
6. **User Actions**: View, scroll, and optionally copy the XML

### API Endpoint

```
GET /almaws/v1/bibs/{mms_id}?view=full&expand=None
Accept: application/xml
```

**Parameters:**
- `mms_id`: The bibliographic record identifier
- `view=full`: Returns complete record data
- `expand=None`: No additional expansion of linked data
- `apikey`: API authentication key

## Usage

### Basic Operation

1. **Enter MMS ID**: Type or paste the MMS ID in the "MMS ID" input field
   - Example: `991234567890104641`
2. **Select Function**: Choose "Fetch and Display Single XML" from the function dropdown
3. **Execute**: Click the function button
4. **View XML**: Dialog window opens with formatted XML
5. **Copy (Optional)**: Click "Copy to Clipboard" to copy the entire XML
6. **Close**: Click "Close" button to dismiss the dialog

### Dialog Features

**Title Bar:**
- Shows the MMS ID: "XML for MMS ID: 991234567890104641"

**Content Area:**
- File size display: "Size: 45,823 characters"
- Scrollable text field with formatted XML
- Fixed-width font for readability
- 25 visible lines with scroll capability
- Read-only (cannot be edited)

**Action Buttons:**
- **Copy to Clipboard**: Copies entire XML to system clipboard
  - Button changes to "Copied!" for 2 seconds after clicking
  - Then resets back to "Copy to Clipboard"
- **Close**: Closes the dialog window

## XML Structure

### Record Components

The displayed XML includes all standard Alma bibliographic record elements:

**Root Element:**
```xml
<bib>
  <!-- Record metadata -->
</bib>
```

**Key Sections:**
- `mms_id`: Alma record identifier
- `record_format`: MARC21 or other format
- `linked_record_id`: Links to other records
- `title`: Brief title for display
- `author`: Primary author/creator
- `issn`: Serial number (if applicable)
- `isbn`: Book number (if applicable)
- `network_number`: Network-level identifiers
- `publisher_const`: Publisher information
- `originating_system`: Source system code
- `originating_system_id`: Original identifier
- `cataloging_level`: Cataloging completeness level
- `record`: Full MARC21 record with all fields
- `anies`: Dublin Core metadata (if present)

### Dublin Core in anies

The `<anies>` section contains Dublin Core metadata:

```xml
<anies>
  <record xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"
          xmlns:dc="http://purl.org/dc/elements/1.1/"
          xmlns:dcterms="http://purl.org/dc/terms/">
    <dc:title>Title of Item</dc:title>
    <dc:creator>Author Name</dc:creator>
    <dc:identifier>dg_12345</dc:identifier>
    <dc:rights>Rights Statement</dc:rights>
    <!-- Additional Dublin Core fields -->
  </record>
</anies>
```

## Use Cases

### 1. Record Structure Inspection

**Scenario:** Need to understand how metadata is structured in a record

**Workflow:**
1. Enter MMS ID
2. Run Function 1
3. Examine XML structure
4. Identify field locations and namespace usage

**Benefits:**
- See exact field names and namespaces
- Understand parent-child relationships
- Identify repeated fields
- Locate specific metadata elements

### 2. Pre-Edit Verification

**Scenario:** Planning to run Functions 2, 6, or 7 and want to verify data first

**Workflow:**
1. Fetch XML for sample record
2. Search for target fields (dc:relation, dc:rights, dc:identifier)
3. Verify field values and structure
4. Confirm records will be affected by planned function

**Benefits:**
- Avoid unexpected changes
- Verify target fields exist
- Check current values before modification
- Ensure function will work as expected

### 3. Troubleshooting Metadata Issues

**Scenario:** Record not displaying correctly or has data quality issues

**Workflow:**
1. Get MMS ID of problematic record
2. Fetch and display XML
3. Search for specific fields or values
4. Identify malformed data, encoding issues, or missing fields

**Benefits:**
- See raw data as stored in Alma
- Identify encoding problems (special characters)
- Find empty or malformed fields
- Diagnose namespace issues

### 4. Copy Record XML for External Processing

**Scenario:** Need to analyze record outside of CABB

**Workflow:**
1. Fetch XML for record
2. Click "Copy to Clipboard"
3. Paste into text editor, XML validator, or other tool
4. Perform external analysis or transformation

**Benefits:**
- Work with XML in preferred tools
- Share record data with colleagues
- Validate against schemas
- Transform using XSLT or other processors

### 5. Documentation and Training

**Scenario:** Creating documentation or training materials about Alma records

**Workflow:**
1. Fetch XML for example records
2. Copy XML for documentation
3. Use in training materials or technical specifications

**Benefits:**
- Real examples from production system
- Accurate field representations
- Complete metadata context
- Version-specific format documentation

### 6. Comparison Before and After Edits

**Scenario:** Verify changes made by other functions

**Workflow:**
1. **Before**: Fetch and copy XML before running editing function
2. **Edit**: Run Functions 2, 6, or 7
3. **After**: Fetch XML again for same record
4. **Compare**: Use diff tool to see exact changes

**Benefits:**
- Confirm only intended fields changed
- Verify no data loss
- Document transformation results
- Quality assurance for batch operations

## Output Format

### Pretty-Printed XML

The function formats XML with:
- **Consistent indentation**: 2 spaces per level
- **Line breaks**: Each element on separate line
- **Attribute formatting**: Attributes on same line as opening tag
- **Namespace declarations**: Preserved with prefixes
- **Text content**: Preserved exactly as stored

### Example Display

```xml
<?xml version="1.0" ?>
<bib>
  <mms_id>991234567890104641</mms_id>
  <record_format>marc21</record_format>
  <linked_record_id></linked_record_id>
  <title>Sample Digital Object</title>
  <author>Smith, John</author>
  <originating_system>01GCL_INST</originating_system>
  <originating_system_id>grinnell:12345</originating_system_id>
  <anies>
    <record xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST" 
            xmlns:dc="http://purl.org/dc/elements/1.1/" 
            xmlns:dcterms="http://purl.org/dc/terms/">
      <dc:title>Sample Digital Object</dc:title>
      <dc:creator>Smith, John</dc:creator>
      <dc:identifier>dg_12345</dc:identifier>
      <dc:identifier>Grinnell:12345</dc:identifier>
      <dc:date>1925</dc:date>
      <dc:rights>Public Domain</dc:rights>
    </record>
  </anies>
</bib>
```

## Technical Details

### Character Limit

- **Maximum display**: Unlimited characters
- **Dialog scrollable**: Can handle very large records
- **Copy functionality**: Copies complete XML regardless of size
- **Truncation**: Log messages truncate to first 500 chars (full XML still displayed)

### Response Time

- **Typical**: 1-2 seconds for standard records
- **Large records**: 2-5 seconds for records with extensive holdings
- **Network dependent**: Speed varies with connection quality

### Error Handling

**Common Errors:**

| Error | Status Code | Cause | Solution |
|-------|-------------|-------|----------|
| Record not found | 404 | Invalid MMS ID | Verify MMS ID is correct |
| Unauthorized | 401 | Invalid API key | Check .env configuration |
| Access denied | 403 | API key lacks permissions | Add "Bibs" read permission |
| Server error | 500 | Alma internal error | Retry or contact support |

**Error Messages:**

```
Failed to fetch record: 404
```
```
API Key not configured
```

### Logging

The function logs:
- Start of fetch operation with MMS ID
- Raw XML length
- Pretty-printed XML length
- Success or failure status
- Any errors with full traceback

**Log Example:**
```
Fetching XML for MMS ID: 991234567890104641
Requesting bibliographic record 991234567890104641 from Alma API
Raw XML length: 42,156 chars
Pretty-printed XML length: 45,823 chars
Successfully fetched XML for MMS ID: 991234567890104641
Displaying XML dialog...
```

## Comparison with Other Methods

### CABB Function 1 vs. Alma UI

**CABB Function 1 Advantages:**
- Faster access (single field, one click)
- Copy functionality built-in
- Formatted for readability
- Can be scripted/automated
- Works offline from saved MMS IDs

**Alma UI Advantages:**
- Shows related data (holdings, items)
- Editing capabilities
- Authority file integration
- Full system context

### CABB Function 1 vs. API Direct Call

**CABB Function 1 Advantages:**
- No curl/postman setup needed
- Automatic formatting
- User-friendly dialog
- Copy button convenience
- Error handling built-in

**API Direct Call Advantages:**
- Scriptable for automation
- Can process many records
- Integration with other tools
- Returns JSON option

## Best Practices

1. **Keep MMS IDs handy**: Maintain a list of common record IDs for quick testing
2. **Copy before major changes**: Snapshot XML before running modification functions
3. **Use for training**: Show new staff what Alma records look like internally
4. **Validate structure**: Check that records follow expected patterns
5. **Document anomalies**: Copy XML for records with unusual structures
6. **Share examples**: Use copied XML in documentation and communications
7. **Verify namespaces**: Check that Dublin Core and custom namespaces are correct

## Limitations

- **Single record only**: Cannot display multiple records at once
- **Read-only**: Cannot edit XML directly (must use other functions)
- **No syntax highlighting**: Plain text display (not color-coded)
- **No XPath search**: Cannot query specific elements in the dialog
- **No save option**: Cannot save XML to file directly (must copy and paste)
- **Network required**: Cannot work offline (needs API access)

## Integration with Other Functions

### Before Running Function 2 (Clear dc:relation)
- Verify which dc:relation fields exist
- Check which ones match the deletion pattern
- Confirm the record should be modified

### Before Running Function 6 (Replace dc:rights)
- Check current dc:rights values
- Verify author copyright statement is present
- Confirm need for replacement

### Before Running Function 7 (Add Grinnell Identifier)
- Check for existing dg_ identifiers
- Verify Grinnell: identifier doesn't already exist
- Confirm identifier format

### After Running Any Editing Function
- Fetch XML to verify changes
- Compare with before state
- Document the modifications

### With Function 3 (Export to CSV)
- Export records first
- Use Function 1 to examine individual records
- Understand XML structure for CSV field mapping

## Keyboard Shortcuts

**Within Dialog:**
- **Ctrl/Cmd + A**: Select all XML text
- **Ctrl/Cmd + C**: Copy selected text (alternative to button)
- **Scroll wheel**: Navigate through long XML
- **Esc**: Close dialog (if supported by browser)

## Privacy and Security

- **API key required**: Must have valid Alma API key configured
- **Read permission**: API key must have "Bibs" read access
- **No data sent out**: XML only displayed locally, not transmitted elsewhere
- **Clipboard security**: Copied XML persists in clipboard (clear if sensitive)
- **No logging of content**: Only metadata logged (size, MMS ID), not actual content

## Troubleshooting

### Dialog Doesn't Appear

**Cause**: JavaScript error or page update issue
**Solution**: 
- Check browser console for errors
- Refresh the application
- Verify MMS ID was entered

### XML Shows Encoding Issues

**Cause**: Special characters not properly encoded
**Solution**:
- This reflects actual data in Alma
- May need manual correction in Alma
- Report to cataloging team for cleanup

### Copy Button Doesn't Work

**Cause**: Browser clipboard permissions
**Solution**:
- Grant clipboard access when prompted
- Try manual select-all and copy
- Check browser compatibility

### Very Slow Loading

**Cause**: Large record or slow network
**Solution**:
- Wait for completion (may take 10-15 seconds)
- Check network connection
- Try again during off-peak hours

## Related Documentation

- **Alma Bibs API**: https://developers.exlibrisgroup.com/alma/apis/bibs/
- **MARC21 Format**: https://www.loc.gov/marc/bibliographic/
- **Dublin Core Metadata**: https://www.dublincore.org/specifications/dublin-core/

## Version History

- **Initial Implementation**: Original function in CABB v1.0
- **Purpose**: Provide quick XML inspection capability
- **Status**: Active, stable, production-ready
