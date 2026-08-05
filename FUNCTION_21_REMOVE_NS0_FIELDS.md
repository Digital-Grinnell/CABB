# Function 21: Remove ns0: Namespaced Fields

---
## ⚠️ **WARNING: THIS FUNCTION DOES NOT WORK**

**DO NOT USE THIS FUNCTION.** It has been disabled and moved to the inactive functions list.

**Known Issues:**
- Does not properly detect ns0: namespaced fields in records
- Cannot identify records that are corrupted beyond API access
- Does not work as intended for cleanup operations

**Status:** Non-functional - Kept for reference only

---

## Overview

**Function 21** identifies and removes erroneous `ns0:` namespaced fields from Alma bibliographic records. These fields are typically the result of XML namespace handling errors during previous processing and should not exist in properly formatted Alma records.

## Purpose

During XML processing, Python's ElementTree library sometimes generates temporary namespace prefixes like `ns0:` when it encounters namespaces that aren't properly registered. While the CABB application includes code to strip these prefixes before sending XML to Alma, Function 6 (Replace dc:rights) appears to have inadvertently added some `ns0:` prefixed fields back into records.

This function provides a cleanup mechanism to:
- **Detect** records containing `ns0:` namespaced fields
- **Identify** which specific fields have the erroneous prefix
- **Remove** those fields entirely from the record
- **Restore** proper XML structure without the corrupted fields

## What It Does

Function 21 scans bibliographic record XML for any elements with the `ns0:` namespace prefix and removes them completely. The function:

1. **Fetches** the bibliographic record as XML
2. **Scans** for any elements with `ns0:` in their tag names
3. **Logs** each field identified for removal
4. **Removes** all `ns0:` namespaced elements from the XML tree
5. **Updates** the record in Alma with the cleaned XML

## When to Use

Use Function 21 when:
- Records display `ns0:` prefixes in XML output (visible via Function 1)
- Function 6 (or other functions) have inadvertently corrupted records
- Alma validation errors mention "Field ns0:xyz is invalid"
- You need to clean up namespace errors in bulk

**Common Scenarios:**
- After running Function 6 on a large batch, some records show `ns0:dginfo` or similar fields
- XML exports show unexpected `ns0:` prefixed elements
- Records fail validation due to unrecognized namespaced fields

## Safety Features

### Confirmation Dialog

Before processing, Function 21 displays a warning dialog with:
- Number of records that will be processed
- Clear warning that ALL `ns0:` fields will be removed entirely
- Option to cancel before making any changes

**Single Record:**
```
⚠️ This will scan and remove ALL ns0: namespaced fields from record 991234567890104641.

These fields are typically erroneous and should not exist in Alma records.

Fields with the 'ns0:' prefix will be removed entirely from the XML.

Do you want to proceed?
```

**Batch Processing:**
```
⚠️ This will scan and remove ALL ns0: namespaced fields from 2,847 record(s).

These fields are typically erroneous and should not exist in Alma records.

Fields with the 'ns0:' prefix will be removed entirely from the XML.

Do you want to proceed?
```

### Detailed Logging

Every action is logged with specifics:
- Which records are being processed
- Which `ns0:` fields are found
- Which fields are removed
- Success or failure of each operation

## How to Use

### Single Record Mode

1. **Enter MMS ID** in the MMS ID field
2. **Select Function 21** from the function dropdown
3. **Click** the function button
4. **Review** the confirmation dialog
5. **Click "Proceed"** to remove ns0: fields
6. **Check** the log for details about which fields were removed

### Batch Mode

1. **Load a set** using "Load Set by ID" or "Load MMS IDs from CSV"
2. **(Optional)** Set a limit to process only the first N records
3. **Select Function 21** from the function dropdown
4. **Click** the function button
5. **Review** the warning dialog showing the number of records
6. **Click "Proceed"** to start batch processing
7. **Monitor** progress via the progress bar
8. **Review** the summary when complete

## Processing Results

### Outcome Categories

**✓ Cleaned Records:**
- Found and removed one or more `ns0:` namespaced fields
- Record successfully updated in Alma
- Example: `✓ 991234567890104641: Removed 2 ns0: namespaced field(s)`

**⊘ No ns0: Fields:**
- No `ns0:` namespaced fields found
- Record left unchanged
- Example: `⊘ 991234567890104641: No ns0: namespaced fields found`

**✗ Errors:**
- Failed to fetch record, parse XML, or update Alma
- Record not modified
- Example: `✗ 991234567890104641: Failed to fetch record: 400`

### Summary Report

After batch processing, you'll see a detailed summary:

```
Batch complete (2,847 records): 
  42 cleaned (removed 67 total fields), 
  2,800 no ns0: fields, 
  5 errors
```

## What Fields Get Removed

Any XML element whose tag includes the `ns0:` namespace prefix will be removed entirely, including:

- `ns0:dginfo`
- `ns0:rights`
- `ns0:identifier`
- `ns0:record`
- Any other `ns0:` prefixed element

**Important:** The entire element is removed, not just the prefix. This is intentional because these fields are typically duplicates or corruptions of properly namespaced fields that exist elsewhere in the record.

## Example Scenario

### Before Function 21

Record XML contains:
```xml
<bib>
  <mms_id>991234567890104641</mms_id>
  <record xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"
          xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dginfo>Proper field</dginfo>
    <ns0:dginfo>Corrupted duplicate</ns0:dginfo>
    <dc:rights>Proper field</dc:rights>
    <ns0:rights>Corrupted duplicate</ns0:rights>
  </record>
</bib>
```

### After Function 21

Record XML cleaned:
```xml
<bib>
  <mms_id>991234567890104641</mms_id>
  <record xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"
          xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dginfo>Proper field</dginfo>
    <dc:rights>Proper field</dc:rights>
  </record>
</bib>
```

**Result:** Removed 2 ns0: namespaced fields

## Technical Details

### XML Processing

Function 21 uses Python's `xml.etree.ElementTree` to:

1. Parse the record XML into an element tree
2. Iterate through all elements looking for those that would serialize with `ns0:` prefixes
3. Remove matching elements from their parent nodes
4. Serialize the modified tree back to XML

### Namespace Handling

The function properly handles XML namespaces by:
- Registering known namespaces (dc, dcterms, xsi, xml)
- NOT registering the Alma default namespace (which would cause `ns0:` prefixes)
- Stripping any remaining `ns0:` references before sending to Alma
- Removing the rejected default xmlns declaration

### API Operations

**Read Record:**
```
GET /almaws/v1/bibs/{mms_id}?view=full&expand=None
Accept: application/xml
```

**Update Record:**
```
PUT /almaws/v1/bibs/{mms_id}?validate=true&override_warning=true&...
Content-Type: application/xml; charset=utf-8
Body: <bib>...</bib>
```

### Error Handling

Common errors and handling:

- **API Key not configured:** Returns error immediately
- **Record fetch failure:** Logs HTTP status code and response
- **XML parsing error:** Logs error with traceback
- **No ns0: fields found:** Returns success with zero count
- **Update failure:** Logs full error response from Alma

## Best Practices

### Before Running Function 21

1. **Use Function 1** to inspect a sample record and confirm `ns0:` fields exist
2. **Check logs** from Function 6 to identify potentially affected records
3. **Test on a single record** before batch processing
4. **Backup your data** (Alma's version history provides this automatically)

### During Processing

1. **Monitor the log** for which fields are being removed
2. **Watch for errors** and note any failed records
3. **Use the kill switch** if you see unexpected behavior
4. **Note the summary** statistics for documentation

### After Processing

1. **Use Function 1** to verify records are cleaned
2. **Re-run Function 21** on the same set to confirm no `ns0:` fields remain
3. **Check affected records** in Alma to ensure they display properly
4. **Document which sets** were processed for institutional records

## Limitations

- **Cannot restore removed fields:** If a `ns0:` field contained unique data (unlikely), it's permanently removed
- **No field-level control:** All `ns0:` fields are removed; you cannot selectively keep some
- **Requires API access:** Must have Bibs read/write API permissions
- **No undo:** Changes are immediate; rely on Alma's version history to revert if needed

## Troubleshooting

### "No ns0: namespaced fields found" but XML shows ns0:

**Cause:** The `ns0:` might be in comments or CDATA sections, not actual element tags

**Solution:** Use Function 1 to view the raw XML and verify the `ns0:` prefix is in element tags

### Function 21 removes fields but they reappear

**Cause:** Another process (like Function 6) is still adding `ns0:` fields

**Solution:** 
1. Fix the source function that's creating the `ns0:` fields
2. Re-run Function 21 after the source is fixed

### Errors during batch processing

**Cause:** Network issues, API rate limits, or individual record problems

**Solution:**
1. Note the failed MMS IDs from the log
2. Try processing those records individually
3. Check Alma API status
4. Verify API key permissions

### Record validation errors after cleanup

**Cause:** Removed `ns0:` field was actually required (very rare)

**Solution:**
1. Use Alma's version history to view the previous version
2. Determine what the `ns0:` field was a duplicate of
3. If needed, manually re-add the proper version of the field in Alma

## Integration with Other Functions

### After Function 6

If Function 6 has corrupted records:
1. Identify affected records (check logs or use a test set)
2. Run Function 21 to clean up the `ns0:` fields
3. Re-run Function 6 if needed (once the bug is fixed)

### With Function 1

Use Function 1 to:
- **Before:** Confirm `ns0:` fields exist in sample records
- **After:** Verify `ns0:` fields have been removed

### With Function 3

1. **Before Function 21:** Export to CSV for documentation
2. **Run Function 21:** Clean the records
3. **After Function 21:** Export again to document changes

## Related Documentation

- **README.md** - "Alma API Namespace Handling" section explains the `ns0:` issue
- **FUNCTION_6_DC_RIGHTS_REPLACEMENT.md** - Function that may have created the problem
- **FUNCTION_1_FETCH_DISPLAY_XML.md** - How to inspect record XML for `ns0:` fields
- **Alma Bibs API:** https://developers.exlibrisgroup.com/alma/apis/bibs/

## Frequently Asked Questions

**Q: Will this delete important data?**
A: No. The `ns0:` prefixed fields are errors/duplicates. Proper versions of the data exist elsewhere in the record with correct namespaces.

**Q: Can I preview which fields will be removed?**
A: Yes. Process a single record first and check the log to see exactly which fields are removed. Then decide whether to proceed with batch processing.

**Q: What if I remove fields by mistake?**
A: Alma keeps version history. Contact your Alma administrator to restore a previous version if needed.

**Q: How do I know if I have affected records?**
A: Use Function 1 to fetch and display XML for sample records. Look for elements with `ns0:` prefixes in the XML output.

**Q: Will this fix the root cause?**
A: No. Function 21 cleans up the symptoms. The root cause is in the function that created the `ns0:` fields (likely Function 6), which needs to be debugged and fixed separately.

## Version History

- **2026-08-04** - Initial implementation
  - Scans for and removes all `ns0:` namespaced fields
  - Supports single record and batch processing
  - Provides detailed logging and summary reports
  - Created in response to Function 6 corruption issue

## Support

For questions or issues with Function 21:
- Check the log file for detailed error messages
- Use Function 1 to inspect record XML before and after
- Review Alma API documentation for validation errors
- Contact your Alma administrator for version history access

---

*Function 21 is a data cleanup utility. Use responsibly and always test on sample records first.*
