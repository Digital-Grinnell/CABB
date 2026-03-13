# Alma Digital Import Profile Requirements for Function 11

## Document Purpose

This document specifies the requirements for an Alma Digital Import Profile that works with CABB Function 11's XML-based output. Share this with your Alma administrator or Ex Libris support when requesting profile creation.

## Profile Overview

**Profile Name:** (Suggested) "CABB Function 11 - Add Files to Existing Representations"

**Profile Type:** Digital Import Profile

**Purpose:** Add JPG files to existing digital representations without modifying bibliographic metadata

## Critical Requirements

### 1. File Format
- **Format:** XML-based metadata files
- **NOT:** CSV-based (CSV profiles overlay entire records and destroy metadata)
- **Structure:** One `metadata.xml` file per record

### 2. Directory Structure
- **Input:** Directory with subdirectories
- **Pattern:** Each subdirectory named with MMS ID
- **Contents:** Each subdirectory contains:
  - `metadata.xml` - Metadata file
  - `{mms_id}.jpg` - Image file

**Example:**
```
CABB_digital_upload_20260313_143052/
├── README.txt
├── 991234567890104641/
│   ├── metadata.xml
│   └── 991234567890104641.jpg
├── 991234567890204641/
│   ├── metadata.xml
│   └── 991234567890204641.jpg
└── 991234567890304641/
    ├── metadata.xml
    └── 991234567890304641.jpg
```

### 3. XML Metadata Format

Each `metadata.xml` file has this structure:

```xml
<?xml version="1.0" encoding="utf-8"?>
<row>
  <dc_identifier>991234567890104641</dc_identifier>
  <representation_id>12345678910001_REP</representation_id>
  <file_name>991234567890104641.jpg</file_name>
</row>
```

### 4. Field Mapping

The profile must map these XML elements:

| XML Element | Maps To | Purpose |
|-------------|---------|---------|
| `dc_identifier` | MMS ID | Identifies the bibliographic record |
| `representation_id` | Representation ID | Identifies which specific representation to add file to |
| `file_name` | File Name | Name of the file to upload (relative to subdirectory) |

### 5. Processing Behavior

**CRITICAL:** The profile must:
- ✅ Add files to existing representations (specified by `representation_id`)
- ✅ Process subdirectories recursively
- ✅ Read `metadata.xml` from each subdirectory
- ✅ Upload file specified in `file_name` element
- ❌ **DO NOT** overlay or update bibliographic metadata
- ❌ **DO NOT** create new representations
- ❌ **DO NOT** modify existing Dublin Core fields

### 6. Error Handling

Profile should:
- Process each subdirectory independently
- Continue processing if one subdirectory fails
- Log errors with specific MMS ID and reason
- Provide detailed upload report

## Technical Specifications

### Representation Targeting

**Method:** By Representation ID
- Profile must support targeting by explicit representation ID
- Must NOT create new representations
- Must NOT replace files in other representations

### File Upload Behavior

- **Action:** Add file to existing representation
- **Overwrite:** Yes (if file already exists in that representation)
- **Create New Rep:** No
- **Modify Bib Record:** No

### Supported File Types

- JPEG/JPG images
- File size: Variable (typically 1-50 MB per file)
- Color: RGB, 8-bit
- Quality: High (95%)

## Why XML Instead of CSV?

**Problem with CSV Profiles:**
CSV-based profiles (like "DG - Overlay Digital Content File as New Rep") interpret CSV uploads as complete record metadata. Any fields NOT in the CSV are treated as deletions, causing:
- Loss of existing dc:title, dc:creator, dc:subject, etc.
- Destruction of dc:identifier fields (Handle URLs, Grinnell identifiers)
- Removal of dc:rights statements
- Complete metadata wipeout

**XML Solution:**
XML-based profiles with explicit `representation_id` targeting:
- Target ONLY the specified representation
- Add ONLY the file to that representation
- Leave ALL bibliographic metadata untouched
- Prevent accidental data loss

## Profile Configuration Steps

Work with your Alma administrator or Ex Libris support to:

1. **Create new Digital Import Profile**
   - Type: Digital Import Profile
   - Purpose: Add files to existing representations

2. **Configure XML parsing**
   - Root element: `<row>`
   - Required elements: `dc_identifier`, `representation_id`, `file_name`

3. **Set field mappings**
   - `dc_identifier` → MMS ID lookup
   - `representation_id` → Target representation
   - `file_name` → File to upload

4. **Configure processing behavior**
   - Enable subdirectory processing
   - Process each subdirectory independently
   - Add files to representations (do not create new ones)
   - Do not modify bibliographic records

5. **Test with sample data**
   - Create test set with 2-3 records
   - Run Function 11 to generate test package
   - Upload via new profile
   - Verify:
     - Files added to correct representations
     - No bibliographic metadata changed
     - No other representations affected

## Reference Documentation

**Harvard Wiki - XML Spec:**
https://harvardwiki.atlassian.net/wiki/spaces/LibraryStaffDoc/pages/43394499/Alma+Digital+Uploader+XML+spec+and+manual+process+via+Alma+UI

**Ex Libris Knowledge Center:**
Search for: "Digital Uploader XML profiles"

**Contact:**
- Your institution's Alma administrator
- Ex Libris support (if needed)

## Testing Checklist

Before using new profile in production:

- [ ] Profile accepts directory with subdirectories
- [ ] Profile reads `metadata.xml` from each subdirectory
- [ ] Files upload to correct representations
- [ ] Representation ID targeting works correctly
- [ ] No bibliographic metadata is modified
- [ ] No unintended representations are affected
- [ ] Error logging is detailed and helpful
- [ ] Failed uploads don't affect other records
- [ ] Upload report shows success/failure per record

## Profile Configuration Template

Provide this to your Alma administrator:

```
Profile Name: CABB Function 11 - Add Files to Existing Representations
Profile Type: Digital Import Profile
Input Format: XML
Directory Structure: Subdirectories (one per record)

XML Structure:
  Root Element: row
  Required Fields:
    - dc_identifier (MMS ID)
    - representation_id (Target Representation)
    - file_name (File to Upload)

Processing:
  - Target Method: By Representation ID
  - Create New Reps: NO
  - Modify Bib Records: NO
  - Add Files to Existing Reps: YES
  - Process Subdirectories: YES
  
File Handling:
  - File Location: Relative to subdirectory
  - Overwrite Existing: YES
  - Supported Types: JPEG/JPG
```

---

**Last Updated:** March 13, 2026  
**For Use With:** CABB Function 11 (XML-based version)  
**Status:** New profile required - CSV profiles destroy metadata
