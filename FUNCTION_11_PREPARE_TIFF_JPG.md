# Function 11: Prepare TIFF/JPG Representations for Digital Uploader

## Overview

**Function 11** prepares JPG derivative files from TIFF source files for upload to Alma Digital using XML metadata files:

1. Creates empty DERIVATIVE_COPY representations in Alma with proper metadata
2. Processes TIFF files (TIFF→JPEG conversion with intelligent format handling)
3. Creates subdirectories for each MMS ID
4. Saves processed JPG files named as `{mms_id}.jpg` in subdirectories
5. Generates individual `metadata.xml` files for each record

**Important Note**: This function creates representations and prepares files but does **not** upload the actual files. File upload is completed using Alma's built-in **Digital Uploader** tool with the prepared directory structure and XML metadata files.

**New in:** March 2026 - Switched from CSV overlay approach to XML-based approach to prevent data corruption.

## Why XML Instead of CSV?

**Problem with CSV Overlay:**
The previous CSV-based approach used Alma's Digital Uploader with `values.csv` files. However, this method overlays entire records, destroying valuable existing metadata. When the CSV doesn't include all fields, Alma interprets missing values as deletions, causing data loss.

**XML-Based Solution:**
The new approach creates individual `metadata.xml` files for each record with explicit representation IDs. This:
- **Targets specific representations** without affecting other metadata
- **Preserves existing data** in the bibliographic record
- **Prevents accidental deletions** of fields not in the upload
- **Provides clear audit trail** (one XML per record)
- **Allows granular error handling** (failed uploads don't affect other records)

**Reference:** Harvard Wiki - [Alma Digital Uploader XML spec](https://harvardwiki.atlassian.net/wiki/spaces/LibraryStaffDoc/pages/43394499/Alma+Digital+Uploader+XML+spec+and+manual+process+via+Alma+UI)

## What It Does

This function processes bibliographic records that have corresponding TIFF files and:

1. **Reads TIFF paths** from `all_single_tiffs_with_local_paths.csv`
2. **Verifies files exist** on the local filesystem
3. **Creates JPG representations** in Alma (or reuses existing empty ones)
4. **Creates subdirectories** for each MMS ID
5. **Converts TIFF to JPG** with intelligent handling for various image formats
6. **Saves JPG files** to subdirectories as `{mms_id}.jpg`
7. **Creates metadata.xml** for each record with MMS ID, representation ID, and filename

### CSV Input Structure

**Required CSV File:** `all_single_tiffs_with_local_paths.csv`

**Columns:**
- `MMS ID`: Alma bibliographic record ID
- `Local Path`: Full path to the TIFF file on the local system

**Example:**
```csv
MMS ID,Local Path
991234567890104641,/Volumes/DGIngest/Photos/photo_001.tif
991234567890204641,/Volumes/DGIngest/Photos/photo_002.tiff
991234567890304641,/Volumes/DGIngest/Historical/scan_123.tiff
```

**Notes:**
- Lines starting with `#` are treated as comments and skipped
- Network volume paths are supported (must be mounted)
- Both `.tif` and `.tiff` extensions are supported

### Smart Processing Logic

The function implements intelligent record filtering to avoid unnecessary processing:

#### Records That Get Processed ✅
- MMS ID exists in CSV with valid Local Path
- TIFF file exists at that path
- File is readable by the system

**Action:** Creates representation, converts TIFF to JPG, saves to output directory

#### Records That Get Skipped ⊘

**No path in CSV**
- **Message**: "No local path found in {csv_file}"
- **Reason**: Cannot locate the TIFF file
- **Solution**: Add MMS ID and path to CSV, or generate new CSV

**File not found**
- **Message**: "File not found: {path}"
- **Reason**: TIFF file doesn't exist at the specified path
- **Solution**: 
  - Check that network volumes are mounted
  - Verify file hasn't been moved or deleted
  - Update CSV with correct path

## Processing Flow

### Step-by-Step Process

1. **Read TIFF CSV**
   - Loads `all_single_tiffs_with_local_paths.csv`
   - Builds MMS ID → TIFF path mapping
   - Skips comment lines (starting with #)

2. **For Each MMS ID:**
   - Look up TIFF path from CSV
   - Verify TIFF file exists and is accessible
   - Create subdirectory for MMS ID
   - Check for existing empty JPG representation in Alma
   - Create JPG representation in Alma (if needed) or reuse existing
   - Convert TIFF to JPG with special handling for:
     - **16-bit images**: Properly scales to 8-bit (divides by 256, not simple truncation)
     - **RGBA/LA/P modes**: Converts with white background to prevent transparency issues
     - **Grayscale images**: Converts to RGB for consistent display
     - **Uncommon formats**: Normalizes to standard RGB format
   - Save JPG to subdirectory as `{mms_id}.jpg`
   - Create `metadata.xml` in subdirectory with:
     - MMS ID (dc_identifier)
     - Representation ID (representation_id)
     - JPG filename (file_name)

3. **Generate README.txt**
   - Creates upload instructions file in root directory
   - Includes troubleshooting tips and documentation links

## Requirements

### Prerequisites

1. **Pillow library** - Required for image processing
   ```bash
   pip install Pillow
   ```

2. **TIFF CSV file** - `all_single_tiffs_with_local_paths.csv` must exist in workspace
   - Must contain columns: `MMS ID` and `Local Path`
   - Can be generated by other functions or created manually

3. **Network volumes** - Any network volumes containing TIFF files must be mounted
   - macOS: Check Finder sidebar for mounted volumes
   - Disconnections during processing will cause failures

4. **Alma API key** - Must be configured in CABB
   - Required for creating representations

### File Access Considerations

- TIFF files must be accessible at the paths specified in the CSV
- Network volume disconnections will cause individual record failures
- Large TIFF files (100+ MB) will take longer to process
- Sufficient disk space needed in `~/Downloads/` for processed JPGs

## Output

### Directory Structure

Function 11 creates a timestamped directory in `~/Downloads/` with subdirectories for each MMS ID:

```
~/Downloads/CABB_digital_upload_20260313_143052/
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

### metadata.xml Format

Each subdirectory contains a `metadata.xml` file with this structure:

```xml
<?xml version="1.0" encoding="utf-8"?>
<row>
  <dc_identifier>991234567890104641</dc_identifier>
  <representation_id>12345678910001_REP</representation_id>
  <file_name>991234567890104641.jpg</file_name>
</row>
```

**Key Elements:**
- `dc_identifier`: MMS ID (tells Alma which bibliographic record)
- `representation_id`: The representation ID created by this function
- `file_name`: JPG filename (relative to subdirectory)

### README.txt

The output directory includes a `README.txt` file with:
- Upload instructions
- Directory structure explanation
- Troubleshooting tips
- Links to Alma documentation

### Image Processing Details

**JPG Output Specifications:**
- **Format**: JPEG
- **Quality**: 95% (high quality, near-lossless for photographs)
- **Color Mode**: RGB (standardized for web display)
- **Bit Depth**: 8-bit (converted from 16-bit or other formats)
- **Optimization**: JPEG optimize flag enabled for smaller file sizes

**Special Handling:**
- **16-bit TIFFs**: Properly scaled to 8-bit (pixels divided by 256, not truncated)
- **Transparency**: RGBA/LA images converted with white background
- **Monochrome**: Grayscale (L mode) converted to RGB
- **Indexed**: Palette (P mode) images expanded to full RGB

## Creating the Alma Digital Import Profile

**PREREQUISITE:** Before using Function 11, you must create a compatible Digital Import Profile in Alma. Follow these steps:

### Profile Creation - Screen 1 of 5: Profile Details

Navigate to: **Alma → Admin → Manage Import Profiles → Create Profile**

**Profile Details Section:**
- **Remote:** Unchecked
- **Profile name:** `CABB Function 11 - Add Files to Existing Representations`
- **Profile description:** `Adds file(s) -- generally a JPG -- to existing digital representations without modifying bibliographic metadata.`
- **Cross walk:** No

**Format Settings:**
- **Physical source format:** XML
- **Source format:** Dublin Core
- **Metadata Filename:** `metadata.xml` ⚠️ **CRITICAL** - Must be exactly this
- **Target format:** DigitalGrinnell Qualified DC (or your institution's DC format)
- **Status:** Active

**Scheduling Section:**
- **Files to import:** New
- **Scheduler status:** Inactive
- **Scheduling:** Not scheduled

✅ **Validation:** Ensure "Metadata Filename" is `metadata.xml` - this must match what Function 11 creates.

Click **Next** to continue to Screen 2.

---

### Profile Creation - Screen 2 of 5: Filter and Normalization

**Profile Type:** Digital ✅ (auto-populated)

**Filter Section:**
- **Filter out the data using:** Leave empty/blank
  - We're not filtering records - all records in the upload should be processed

**Normalization Section:**
- **Correct the data for matching and cataloging using:** **`DCAP01 Bib Resequence And Clear em`** (empty fields)
  - ⚠️ **IMPORTANT:** Alma requires a normalization rule selection
  - Choose the LEAST invasive option: "DCAP01 Bib Resequence And Clear em[pty fields]"
  - This rule only resequences fields and removes empty fields - it does NOT modify field values
  - **Avoid** "normalize on save/SRU/search" options - those could alter data values
  - Since this profile adds digital files (not bib records), normalization impact should be minimal
  
**Validation Excel Section:**
- **Handle invalid data using:** (Keep default or most permissive option)

✅ **Validation:** Normalization set to "DCAP01 Bib Resequence And Clear em" - the safest available option.

Click **Next** to continue to Screen 3.

---

### Profile Creation - Screen 3 of 5: Match Profile and Actions

**Match Profile Section:**
- **Match Method:** `dc:identifier`
  - This matches records using the dc_identifier field from metadata.xml (the MMS ID)
- **Identifier Prefix:** Leave empty/blank

**Match Actions Section:**
- **Handling method:** Automatic ✅
- **Upon match:** Overlay ✅
  - This allows adding digital files to existing bibliographic records
- **Allow bibliographic record deletion:** Unchecked ✅
  - Never allow deletions through this profile

**OVERLAY Settings:**
- ✅ **CRITICAL:** Check **"Do not override Originating System"**
  - This prevents the profile from modifying existing bibliographic metadata
  - Only digital representation data will be modified (files added)

**No Match Section:**
- **Upon no match:** Do Not Import ✅
  - If dc:identifier doesn't match an existing record, skip it
  - This ensures we only modify records that exist in Alma

✅ **Validation:** Match on dc:identifier with Overlay mode, "Do not override Originating System" checked, and "Do Not Import" on no match.

Click **Next** to continue to Screen 4.

---

### Profile Creation - Screen 4 of 5: Management Tags

**Set management tags for all the records imported using this profile**

- **Suppress record/s from publish/delivery:** Unchecked ✅
  - Condition: "Only for new re[cords]" (default)
  
- **Suppress record/s from external search:** Unchecked ✅
  - Condition: "Only for new re[cords]" (default)
  
- **Synchronize with OCLC:** Don't publish ✅
  - Condition: "Only for new re[cords]" (default)
  
- **Synchronize with Libraries Australia:** Don't publish ✅
  - Condition: "Only for new re[cords]" (default)

**Note:** These default settings are appropriate for this profile. Since we're adding digital files to **existing** bibliographic records (not creating new ones), these management tags will not affect the import process. All conditions are set to "Only for new re[cords]" which doesn't apply to overlay operations.

✅ **Validation:** Leave all settings at their defaults - no changes needed.

Click **Next** to continue to Screen 5.

---

### Profile Creation - Screen 5 of 5: Bibliographic Record Level and Representation Details

**Bibliographic Record Level Section:**
- **Default Collection:** `DG-OVERLAY` (or your institution's appropriate collection code)
  - This should match your Digital Grinnell collection identifier

**Representation Details Section:**
- **Status:** Active ✅
- **Usage Type:** `Derivative` ✅
  - Standard usage type for access copies (JPGs derived from TIFFs)
- **Library:** `Burling Library` (or your institution's library)
- **Default access rights policy:** `Burling Library` (or your appropriate policy)
- **Extract access rights from property:** Leave empty
- **Extract note from property:** Leave empty
- **Extract public note from property:** Leave empty
- **Group files by regular expression:** Leave empty
- **Extract label from property:** Leave empty

**IMPORTANT: Click "Add Representation" Button**

✅ **You MUST click "Add Representation"** to save/register the representation configuration.

After filling out all the representation details (Usage Type: Derivative, Library, etc.), click the **"Add Representation"** button. This registers your representation configuration with the profile. The button acts like a "Submit" button for the representation definition.

**After clicking "Add Representation", you should see:**
- A table appears at the bottom of the screen showing your registered representation
- The table should display:
  - **Usage Type:** Derivative
  - **Library:** Burling Library
  - **Group files by:** (.*) 
  - Active status indicator
- The form fields reset to defaults (this is normal)

**Note:** You only need to click it ONCE to add one representation type. If you later needed multiple representation types (e.g., both "Derivative" AND "Preservation"), you would fill out the form again with different settings and click "Add Representation" again. For Function 11, one representation is correct.

✅ **Validation:** Verify your "Derivative" representation appears in the table at the bottom of the screen with "Burling Library" selected.

Click **Save** to create the profile.

---

### Profile Successfully Created ✅

**Profile Name:** CABB Function 11 - Add Files to Existing Representations  
**Profile ID:** 7848175270004641  
**Profile Type:** Digital Import Profile  
**Status:** Active

This profile is now ready to use with the Digital Uploader in Alma. When uploading directories prepared by Function 11, select this profile to add JPG files to existing representations without modifying bibliographic metadata.

---

## How to Use

### Step 1: Prepare Environment

1. **Verify TIFF CSV exists**
   ```bash
   ls -lh all_single_tiffs_with_local_paths.csv
   ```

2. **Check network volumes are mounted** (if applicable)
   - Open Finder → Check sidebar for required volumes
   - Reconnect if necessary

3. **Verify Pillow is installed**
   ```bash
   python -c "from PIL import Image; print('Pillow OK')"
   ```

### Step 2: Load Your Set in CABB

1. Enter a Set ID in the **"Set ID"** field
2. Click **"Load Set Members"**
3. Verify the correct records are loaded (preview shows first 20)

**Alternative:** Enter a single MMS ID for single-record processing

### Step 3: Run Function 11

1. Select **"11 - Prepare TIFF/JPG Representations"** from the function dropdown
2. Click **"Run Function on Set"** (or click the function button directly)
3. **Review the warning dialog:**
   - Confirms records to process
   - Notes that this creates representations in Alma (permanent)
4. Click **"Proceed"** to start processing
5. Monitor progress in the log window
   - Progress bar shows completion percentage
   - Log shows detailed status for each record

### Step 4: Review Results

After processing completes:

1. **Check the log output** for:
   - Success count
   - Failed count
   - Breakdown of failures (no path, file not found, etc.)

2. **Note the output directory path:**
   - Automatically shown in CABB status
   - Also auto-populated in the Set ID field
   - Example: `~/Downloads/CABB_digital_upload_20260313_143052`

3. **Verify output structure:**
   ```bash
   ls -lh ~/Downloads/CABB_digital_upload_*/
   ```
   - Check that subdirectories were created (one per MMS ID)
   - Verify each contains metadata.xml and a JPG file

4. **Inspect a sample subdirectory:**
   ```bash
   ls -lh ~/Downloads/CABB_digital_upload_*/991234567890104641/
   cat ~/Downloads/CABB_digital_upload_*/991234567890104641/metadata.xml
   ```
   - Verify XML structure is correct
   - Check that MMS ID and representation ID are present

5. **Review README.txt:**
   - Read upload instructions
   - Note any special considerations

### Step 5: Upload to Alma (Manual Step)

Function 11 prepares files but does **not** upload them. Complete the upload using Alma's Digital Uploader:

1. **Log into Alma**
   - Navigate to: **Resources → Manage Digital Files → Digital Uploader**

2. **Select Upload Profile**
   - **REQUIRED:** You need a Digital Import Profile that supports:
     - XML-based metadata files (not CSV)
     - Subdirectory structure with `metadata.xml` in each folder
     - Targeting by `representation_id` field
     - Adding files to existing representations WITHOUT overlaying bibliographic metadata
   
   - **If you don't have this profile:** Contact your Alma administrator or Ex Libris support to create one
   - Profile must read: `dc_identifier` (MMS ID), `representation_id` (target rep), and `file_name` (file to upload)
   - **WARNING:** Do NOT use CSV-based overlay profiles - they will destroy your metadata!

3. **Upload Directory**
   - Click **"Browse"** or **"Choose Files"**
   - Select the **entire directory** created by Function 11
   - Example: `CABB_digital_upload_20260313_143052`
   - Alma will process each subdirectory and read its metadata.xml file

4. **Start Upload**
   - Review the preview/validation screen
   - Alma will show detected records and files
   - Click **"Submit"** to begin upload
   - Monitor upload progress in Alma

5. **Verify Upload**
   - Check a few records in Alma to confirm JPGs are attached
   - Verify JPG displays correctly in Digital Viewer
   - Review Alma's upload log for any errors
   - Test in public interface (Primo/Discovery)

### Step 6: Cleanup (Optional)

After successful upload to Alma:

```bash
# Verify upload succeeded first!
rm -rf ~/Downloads/CABB_digital_upload_20260308_143052
```

**Warning:** Only delete after confirming all files uploaded successfully to Alma.

## Representation Positioning

**Critical Information about Representation Order:**

Alma uses the **first representation** as the primary display in the digital viewer. This affects user experience significantly.

### Function 11 Behavior

**Reuses existing empty representations:**
- If a DERIVATIVE_COPY representation with "JPG" in the label exists and has no files
- Logs: "Reusing existing representation ID: {rep_id}"

**Creates new representations:**
- If no suitable empty representation exists
- Logs: "Creating new JPG representation for {mms_id}"

### Position Warnings

Function 11 logs warnings if representations are not in optimal position:

**✓ Optimal (First Position):**
```
✓ JPG representation created as first (and only) representation
✓ JPG representation is in first position
```

**⚠️ Suboptimal (Not First):**
```
⚠️ WARNING: JPG representation is at position 3, not first!
⚠️ Alma may not use this as the primary display.
```

**⚠️ Creating When Others Exist:**
```
⚠️ NOTE: Creating new JPG representation, but 2 representation(s) already exist
⚠️ The new JPG will be placed at the end (position 3)
⚠️ Alma may not use this as the primary display.
```

### Fixing Representation Order

If JPG is not in first position, you have two options:

**Option 1: Manual Reordering in Alma (Recommended)**
1. Open the record in Alma's Metadata Editor
2. Navigate to Digital Representations
3. Drag representations to reorder (JPG should be first)
4. Save changes

**Option 2: Delete and Recreate**
1. Delete non-JPG representations (if they're not needed)
2. Re-run Function 11 to create JPG as first representation
3. Re-upload files

## Error Handling

### Common Errors and Solutions

#### "TIFF CSV not found"
**Full Error:** `TIFF CSV not found: all_single_tiffs_with_local_paths.csv`

**Cause:** The required CSV file doesn't exist in the workspace

**Solution:**
- Verify file exists: `ls -lh all_single_tiffs_with_local_paths.csv`
- Generate the CSV using other CABB functions
- Create manually with columns: `MMS ID`, `Local Path`

---

#### "Pillow library not installed"
**Full Error:** `Pillow library not installed. Run: pip install Pillow`

**Cause:** PIL/Pillow image processing library is not available

**Solution:**
```bash
pip install Pillow
# Or for virtual environment:
source .venv/bin/activate
pip install Pillow
```

---

#### "No local path found in {csv}"
**Log Message:** `✗ No local path found in all_single_tiffs_with_local_paths.csv`

**Cause:** MMS ID is not in the CSV file

**Solution:**
- Add the MMS ID and path to the CSV
- Remove the MMS ID from your set if it shouldn't be processed
- Regenerate the CSV with updated data

---

#### "File not found: {path}"
**Log Message:** `✗ File not found: /Volumes/DGIngest/Photos/photo_001.tif`

**Cause:** TIFF file doesn't exist at the specified path

**Solution:**
- **Check network volumes:** Ensure `/Volumes/DGIngest/` (or similar) is mounted
- **Verify file exists:** `ls -lh {path}`
- **Update CSV:** If file moved, update path in CSV
- **Check file extension:** Verify `.tif` vs `.tiff` spelling

---

#### "Failed to create representation: HTTP 400"
**Full Error:** `Failed to create representation: HTTP 400`

**Cause:** Invalid representation data or API issue

**Solution:**
- Verify API key is correct and active
- Check that MMS ID exists in Alma
- Verify MMS ID has digital inventory (not all records can have digital representations)
- Check Alma API status

---

#### "Failed to create representation: HTTP 401"
**Full Error:** `Failed to create representation: HTTP 401`

**Cause:** API authentication failed

**Solution:**
- Verify API key is configured in CABB
- Check that API key hasn't expired
- Ensure API key has Write permissions for Bibs

---

#### "Error creating JPG: {error}"
**Example:** `Error creating JPG: cannot identify image file`

**Cause:** Source TIFF file is corrupted or invalid format

**Solution:**
- Open TIFF in image viewer to verify it's valid
- Try converting manually: `convert source.tif test.jpg`
- Re-scan or re-generate the TIFF if corrupted
- Check file isn't partially downloaded/transferred

---

### Progress Tracking

Function 11 provides detailed progress information:

**Progress Bar:**
- Visual indicator of completion percentage
- Updates after each record processed

**Status Messages:**
- Current record number and total
- Example: `Processing: 15/50 records (30.0%)`

**Log Output:**
- Detailed status for each record
- Success/failure indicators (✓/✗)
- Specific error messages for failures
- Summary statistics at completion

**Summary Statistics:**
```
TIFF/JPG preparation complete: 
  45 prepared
  3 failed
  1 no path
  1 file not found
```

## Technical Details

### API Calls

Function 11 makes the following API calls per record:

1. **GET** `/almaws/v1/bibs/{mms_id}/representations`
   - Check for existing representations
   - Identify if JPG representation already exists

2. **POST** `/almaws/v1/bibs/{mms_id}/representations` (if needed)
   - Create new DERIVATIVE_COPY representation
   - Only if suitable empty representation doesn't exist

**API Efficiency:**
- Minimal API calls (only representation-related)
- No file upload via API (uses Digital Uploader instead)
- Reuses existing empty representations when possible

### Image Conversion Process

The TIFF→JPG conversion uses PIL/Pillow with intelligent format handling:

```python
# Pseudocode for conversion logic:
if image.mode in ('I', 'I;16', 'I;16B'):
    # 16-bit: Scale to 8-bit properly
    image = image.point(lambda x: x / 256).convert('L').convert('RGB')
elif image.mode in ('RGBA', 'LA', 'P'):
    # Transparency: Add white background
    rgb_img = new_image(size, white_background)
    rgb_img.paste(image, mask=alpha_channel)
elif image.mode == 'L':
    # Grayscale: Convert to RGB
    image = image.convert('RGB')
else:
    # Ensure RGB
    image = image.convert('RGB')

# Save with high quality
image.save(output_file, 'JPEG', quality=95, optimize=True)
```

### File Naming Convention

JPG files are named using the MMS ID:
- Pattern: `{mms_id}.jpg`
- Example: `991234567890104641.jpg`

**Why MMS ID?**
- Guarantees unique filenames
- Easy to trace back to source record
- Matches the `dc_identifier` in metadata.xml
- No dependency on original TIFF filename

### XML Metadata Logic

The Digital Uploader uses `metadata.xml` files to control file placement:

1. Reads each subdirectory
2. Parses the `metadata.xml` file
3. Reads `dc_identifier` to identify the bibliographic record
4. Reads `representation_id` to identify the specific representation
5. Uploads `file_name` to that representation

**Structure Benefits:**
- One subdirectory per record keeps files organized
- XML format prevents data corruption (unlike CSV overlay)
- Representation ID explicitly specifies target (no ambiguity)
- Alma processes each subdirectory independently (better error handling)

**Important:** The MMS ID in `dc_identifier` must match the actual MMS ID in Alma, and the `representation_id` must be a valid representation created by Function 11.

## Performance Considerations

### Processing Speed

Factors affecting processing time:

**Fast (< 1 second/record):**
- Small TIFF files (< 10 MB)
- Local storage (internal drive)
- Simple image formats (8-bit RGB)
- Existing representations (reuse)

**Slow (> 5 seconds/record):**
- Large TIFF files (> 50 MB)
- Network storage (mounted volumes)
- Complex formats (16-bit, multi-layer)
- API delays or throttling

**Estimated Times:**
- **10 records, 20MB TIFFs, local**: ~1-2 minutes
- **100 records, 50MB TIFFs, network**: ~15-30 minutes
- **1000 records, mixed sizes**: ~2-5 hours

### Optimization Tips

**Batch Processing:**
- Process in batches of 50-100 records
- Allows for error review and corrections
- Reduces risk of long-session failures

**Network Performance:**
- Mount network volumes via fastest connection (Ethernet > WiFi)
- Process during off-peak hours
- Consider copying TIFFs to local storage first

**Disk Space:**
- JPG files are typically 10-30% of TIFF size
- Ensure sufficient space in `~/Downloads/`
- Clean up old output directories regularly

## Troubleshooting

### All Records Failing

**Check:**
1. API key is configured and valid
2. CSV file path and format are correct
3. At least some TIFF files exist and are accessible
4. Network is stable (if using API)

### Intermittent Failures

**Check:**
1. Network stability (WiFi vs Ethernet)
2. Volume mount stability (network drives)
3. Disk space availability
4. RAM availability for large images

### Image Quality Issues

**Check:**
1. Source TIFF quality (garbage in, garbage out)
2. JPG quality setting (currently 95%)
3. Color profile issues in source files
4. Bit depth conversion (16-bit to 8-bit)

### Upload Issues (After Function 11)

**Check:**
1. metadata.xml files are present in each subdirectory
2. XML format is correct (proper tags and structure)
3. Correct Digital Uploader profile selected
4. MMS IDs in XML match Alma records
5. Representation IDs are valid
6. JPG files are readable and in correct locations

## Related Functions

### Function 14a: Prepare Thumbnails
- Similar workflow for thumbnail images
- Uses PNG→JPEG conversion
- Different representation type (THUMBNAIL vs DERIVATIVE_COPY)
- Uses Handle.net identifier matching

### Function 12 (Old Function 11b)
- **DISABLED/ABANDONED**
- Was a Selenium-based upload automation
- Replaced by manual Digital Uploader workflow
- Code archived in `inactive_functions.py`

## FAQ

### Q: What Digital Uploader profile do I need?

**A:** You need a Digital Import Profile configured for:
- **XML metadata files** (not CSV)
- **Subdirectory structure** (each MMS ID in its own folder)
- **Field mapping:** `dc_identifier` → MMS ID, `representation_id` → target representation, `file_name` → file to upload
- **Behavior:** Add files to representations WITHOUT overlaying bibliographic metadata

If you don't have this profile, contact your Alma administrator or Ex Libris support. Reference the Harvard Wiki documentation on XML-based Digital Uploader profiles.

### Q: Why was the CSV approach replaced with XML?

**A:** The CSV overlay approach was destroying valuable metadata by overlaying entire records. The XML-based approach explicitly targets specific representations using representation IDs, preventing data loss.

### Q: Why doesn't Function 11 upload files directly via API?

**A:** Alma's API has limitations with binary file uploads. The Digital Uploader tool is Alma's recommended method for uploading files to representations and is more reliable than API-based approaches.

### Q: Can I process records without loading a set?

**A:** Yes, you can enter a single MMS ID in the MMS ID field instead of loading a set. Function 11 works in both single-record and batch modes.

### Q: What happens if I run Function 11 twice on the same records?

**A:** Function 11 will reuse existing empty DERIVATIVE_COPY representations if found. If representations now have files (from previous upload), it will create new representations. This can lead to duplicate representations, so verify before re-running.

### Q: Can I edit the metadata.xml files?

**A:** Yes, but be careful. Maintain the XML structure and ensure:
- MMS IDs match actual Alma records
- Representation IDs are valid
- Filenames match actual files in the directory

### Q: What if my TIFF files are in multiple directories?

**A:** The CSV supports any valid file path. Each MMS ID can have a TIFF in a different location. Just ensure all paths are absolute and accessible.

### Q: Can I delete the output directory immediately after processing?

**A:** No! Keep the directory until you've successfully uploaded files to Alma using the Digital Uploader. After upload is verified, you can safely delete it.

### Q: Why use MMS ID instead of Handle URL in dc_identifier?

**A:** The MMS ID is Alma's primary identifier for bibliographic records and is what the Digital Uploader expects in the XML to match files to the correct records. Handle URLs are for external/public access.

### Q: What's the structure of metadata.xml?

**A:**
```xml
<row>
  <dc_identifier>MMS_ID</dc_identifier>
  <representation_id>REP_ID</representation_id>
  <file_name>FILENAME.jpg</file_name>
</row>
```

- `dc_identifier`: Tells Alma which bibliographic record
- `representation_id`: Tells Alma which specific representation
- `file_name`: Tells Alma which file to attach

### Q: Can I change the JPG quality setting?

**A:** Yes, but it requires editing the code. Look for `quality=95` in the `_prepare_jpg_from_tiff_representation` method. Range is 1-95 (95 is near-lossless).

### Q: What if I have both .tif and .tiff files?

**A:** Both extensions are supported. The CSV just needs the correct full path including the correct extension for each file.

---

## Summary Workflow

1. ✅ **PREREQUISITE:** Ensure you have an XML-based Digital Import Profile (see FAQ above)
2. ✅ Prepare `all_single_tiffs_with_local_paths.csv` with MMS IDs and TIFF paths
3. ✅ Load set (or enter single MMS ID) in CABB
4. ✅ Run Function 11
5. ✅ Review output directory structure (subdirectories with metadata.xml and JPG files)
6. ✅ Read README.txt for instructions
7. ✅ Log into Alma → Digital Uploader
8. ✅ Select your XML-based Digital Import Profile
9. ✅ Upload the output directory
10. ✅ Verify upload succeeded in Alma
11. ✅ Clean up output directory after verification

---

**Last Updated:** March 13, 2026  
**Function Status:** Active and Maintained - XML-based approach  
**Related Functions:** Function 14a (Thumbnails)  
**Breaking Change:** Replaced CSV overlay with XML metadata (March 2026)
