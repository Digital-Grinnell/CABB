# Function 11 Migration: CSV to XML

## Date: March 13, 2026

## Summary

Function 11 has been completely redesigned to use XML-based metadata files instead of CSV overlay. This change prevents data corruption and loss that occurred with the CSV approach.

## Problem with CSV Approach

The CSV overlay method (`values.csv` with `dc:identifier` and `file_name_1` columns) had a critical flaw:

**Data Destruction Issue:**
- Alma's Digital Uploader interprets CSV uploads as complete record metadata
- Any fields NOT present in the CSV are treated as deletions
- This caused existing valuable metadata to be overwritten/destroyed
- No way to target specific representations without affecting the entire record

**Example of Data Loss:**
```csv
dc:identifier,file_name_1
991234567890104641,991234567890104641.jpg
```

When uploaded, Alma would:
1. Read the MMS ID from `dc:identifier`
2. Find the bibliographic record
3. **Overlay the entire record** with just these two values
4. **Delete all other metadata** not present in the CSV

## New XML-Based Approach

### Directory Structure
```
CABB_digital_upload_20260313_143052/
├── README.txt
├── 991234567890104641/
│   ├── metadata.xml
│   └── 991234567890104641.jpg
└── 991234567890204641/
    ├── metadata.xml
    └── 991234567890204641.jpg
```

### metadata.xml Format
```xml
<?xml version="1.0" encoding="utf-8"?>
<row>
  <dc_identifier>991234567890104641</dc_identifier>
  <representation_id>12345678910001_REP</representation_id>
  <file_name>991234567890104641.jpg</file_name>
</row>
```

### Key Improvements

1. **Explicit Targeting:**
   - `representation_id` explicitly identifies the target representation
   - No ambiguity about which representation gets the file
   - No risk of affecting other representations or metadata

2. **Data Preservation:**
   - Only adds file to specified representation
   - Does not overlay or modify bibliographic metadata
   - Existing fields remain untouched

3. **Better Organization:**
   - One subdirectory per record
   - Clear one-to-one relationship between XML and files
   - Easy to troubleshoot individual records

4. **Error Isolation:**
   - If one record fails, others are unaffected
   - Alma processes each subdirectory independently
   - Clear error messages reference specific MMS IDs

## Code Changes

### Modified Function

**Method:** `prepare_tiff_jpg_representations()`

**Key Changes:**
1. Creates subdirectories for each MMS ID
2. Calls `_prepare_jpg_from_tiff_representation_xml()` instead of CSV-based method
3. Creates `metadata.xml` files instead of `values.csv`
4. Generates `README.txt` with detailed instructions

### New Helper Methods

1. **`_prepare_jpg_from_tiff_representation_xml()`**
   - Similar to original but saves to subdirectory
   - Returns representation ID for XML creation

2. **`_create_metadata_xml()`**
   - Generates properly formatted XML metadata files
   - Includes MMS ID, representation ID, and filename

3. **`_create_uploader_readme()`**
   - Creates detailed instructions file
   - Includes troubleshooting tips and documentation links

## Migration Impact

### For Users

**Action Required:** You need an XML-based Digital Import Profile in Alma.

**What to Do:**
1. Review [ALMA_DIGITAL_PROFILE_REQUIREMENTS.md](ALMA_DIGITAL_PROFILE_REQUIREMENTS.md)
2. Share that document with your Alma administrator or Ex Libris support
3. Request creation of the new profile
4. Test with a small set before production use

**What Changes:**
- Output directory structure (subdirectories instead of flat)
- Need for new Alma profile (XML-based, not CSV)
- Upload process uses new profile
- Better success rate (no more data corruption)

### For Documentation

**Updated Files:**
- `FUNCTION_11_PREPARE_TIFF_JPG.md` - Complete rewrite for XML approach
- `app.py` - Modified `prepare_tiff_jpg_representations()` and helpers
- This file (`FUNCTION_11_MIGRATION_NOTES.md`) - Migration documentation

**References Added:**
- Harvard Wiki: Alma Digital Uploader XML spec
- Ex Libris Knowledge Center: Digital Uploader guides

## Testing Checklist

Before deploying, verify:

- [ ] Function 11 creates subdirectories correctly
- [ ] Each subdirectory contains metadata.xml and JPG
- [ ] XML files are properly formatted (valid XML)
- [ ] MMS IDs in XML match actual records
- [ ] Representation IDs are correct
- [ ] JPG files are created successfully
- [ ] README.txt is generated with instructions
- [ ] Digital Uploader can read the directory structure
- [ ] Upload to Alma succeeds without errors
- [ ] No metadata is lost or overwritten
- [ ] Files appear in correct representations
- [ ] Single-record mode still works
- [ ] Error handling works correctly

## Rollback Plan

If issues arise, the original CSV-based approach can be restored by:

1. Reverting `app.py` to previous version
2. Restoring original `FUNCTION_11_PREPARE_TIFF_JPG.md`
3. However, note that CSV approach has known data corruption issues

**Recommendation:** Do not rollback. Fix forward instead.

## References

- **Harvard Wiki:** [Alma Digital Uploader XML spec](https://harvardwiki.atlassian.net/wiki/spaces/LibraryStaffDoc/pages/43394499/Alma+Digital+Uploader+XML+spec+and+manual+process+via+Alma+UI)
- **Ex Libris:** Digital Uploader documentation in Knowledge Center
- **PDF:** `CSV-Overlay-Does-NOT-Work.pdf` - Original problem documentation

## Questions or Issues

Contact the development team or refer to:
- `FUNCTION_11_PREPARE_TIFF_JPG.md` for usage instructions
- `README.txt` in output directory for upload instructions
- Ex Libris support for Alma Digital Uploader questions
