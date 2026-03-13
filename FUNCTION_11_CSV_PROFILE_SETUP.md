# CABB Function 11 - CSV Profile Setup (Harvard Method)

**Profile Type:** Digital Import Profile  
**Approach:** CSV with minimal 2-column format (mms_id + file_name_1 only)  
**Based on:** [Harvard Wiki - Alma-D batch uploader](https://harvardwiki.atlassian.net/wiki/spaces/LibraryStaffDoc/pages/43394499/Alma-D+batch+uploader+--+for+bibs+that+already+exist+in+Alma)

## Key Difference from Previous CSV Approach

**THIS IS SAFE** because:
- ✅ Only 2 columns: `mms_id` and `file_name_1`
- ✅ NO bibliographic metadata columns (no dc:title, dc:creator, dc:rights, etc.)
- ✅ Uses Digital Uploader's "Add Files" interface with drag/drop
- ✅ Profile configured to add files only, not modify bib records
- ✅ Harvard explicitly states: "will update timestamp but will not actually change the content of the bib"

**Previous Destructive Approach** (NEVER USE):
- ❌ Multiple Dublin Core columns
- ❌ Overlay profile that overwrote ALL fields
- ❌ Missing values triggered deletions
- ❌ **"ALL of my correct metadata was obliterated"** (user quote)

---

## Creating the Profile

### Screen 1 of 5: Profile Details

**Profile Details Section:**
- **Remote:** Unchecked
- **Profile name:** `CABB Function 11 - Add ONE File to Existing Representation`
- **Profile description:** `Used in conjunction with CABB Function 11, this profile should be used to attach a single digital file to an existing representation (also created by Function 11) on the target bib record.`
- **Cross walk:** Yes ✅

**Format Settings:**
- **Physical source format:** CSV
- **Source format:** Comma Separated Values
- **Metadata Filename:** `values.csv` ⚠️ **CRITICAL** - Must be exactly this
- **Target format:** DigitalGrinnell Qualified DC (or your institution's DC format)
- **Status:** Active
- **Download Template:** Available (can download template to see expected format)

**Scheduling Section:**
- **Files to import:** New
- **Scheduler status:** Inactive
- **Scheduling:** Not scheduled

✅ **Validation:** CSV format with values.csv filename, Cross walk enabled.

Click **Next** to continue to Screen 2.

---

### Screen 2 of 5: Filter and Normalization

**Profile Type:** Digital ✅ (auto-populated)

**Filter Section:**
- **Filter out the data using:** Leave empty/blank
  - We're not filtering records - all records in the CSV should be processed

**Normalization Section:**
- **Correct the data for matching and cataloging using:** **`DCAP01 Bib Resequence And Clear empty fields`** ✅
  - Same safe normalization rule as the XML profile
  - Only resequences fields and removes empty fields - does NOT modify field values
  - This is critical for preventing metadata destruction

**Validation Exception Profile:**
- **Handle invalid data using:** `DC Application Profile 1 Metadata Editing On Save`
- ✅ **Skip records with validation issues** - CHECKED
  - This ensures problematic records are skipped rather than causing batch failures

✅ **Validation:** Filter empty, normalization set to "DCAP01 Bib Resequence And Clear empty fields", validation issues will be skipped.

Click **Next** to continue to Screen 3.

---

### Screen 3 of 5: Match Profile and Actions

**Match Profile Section:**
- **Match Method:** `dc:identifier`
  - This matches records using the mms_id column from values.csv
- **Identifier Prefix:** Leave empty/blank

**Match Actions Section:**
- **Handling method:** Automatic ✅
- **Upon match:** Overlay ✅
  - This allows adding digital files to existing bibliographic records
- **Allow bibliographic record deletion:** Unchecked ✅
  - Never allow deletions through this profile

**OVERLAY Settings:**
- ✅ **CRITICAL:** Check **"Do not override Originating System"** ✅
  - **This is the key protection** that prevents the profile from modifying existing bibliographic metadata
  - Only digital representation data will be modified (files added)
  - Without this checkbox, the CSV overlay would destroy your metadata!

**No Match Section:**
- **Upon no match:** Do Not Import ✅
  - If mms_id doesn't match an existing record, skip it
  - This ensures we only modify records that exist in Alma

✅ **Validation:** Match on dc:identifier with Overlay mode, **"Do not override Originating System" CHECKED**, and "Do Not Import" on no match.

Click **Next** to continue to Screen 4.

---

### Screen 4 of 5: Management Tags

**Set management tags for all the records imported using this profile**

- **Suppress record/s from publish/delivery:** Unchecked ✅
  - Condition: "Only for new records" (default)
  
- **Suppress record/s from external search:** Unchecked ✅
  - Condition: "Only for new records" (default)
  
- **Synchronize with OCLC:** Don't publish ✅
  - Condition: "Only for new records" (default)
  
- **Synchronize with Libraries Australia:** Don't publish ✅
  - Condition: "Only for new records" (default)

**Note:** These default settings are appropriate for this profile. Since we're adding digital files to **existing** bibliographic records (not creating new ones), these management tags will not affect the import process. All conditions are set to "Only for new records" which doesn't apply to overlay operations.

✅ **Validation:** Leave all settings at their defaults - no changes needed.

Click **Next** to continue to Screen 5.

---

### Screen 5 of 5: Bibliographic Record Level and Representation Details

**Bibliographic Record Level Section:**
- **Default Collection:** `DG-OVERLAY` (or your institution's appropriate collection code)
  - This should match your Digital Grinnell collection identifier

**Representation Details Section:**
- **Status:** Active ✅
- **Default Usage Type:** `Derivative` ✅
  - Standard usage type for access copies (JPGs derived from TIFFs)
- **Default library:** `Burling Library` (or your institution's library)
- **Default access rights policy:** (Select your appropriate policy, or leave empty to use collection defaults)

**IMPORTANT: No "Add Representation" Button for CSV Profiles**

⚠️ **For CSV-based profiles, there is NO "Add Representation" button on this screen.**

This is different from XML-based profiles. With CSV profiles:
- The representation configuration is applied automatically based on the settings above
- No additional button click is required to register the representation
- The CSV format with mms_id + file_name_1 columns ensures each file is added to the appropriate existing representation created by Function 11

Simply verify your settings are correct and proceed to save the profile.

✅ **Validation:** Collection and library set appropriately, Usage Type "Derivative", status "Active". No additional button clicks needed.

Click **Save** to create the profile.

---

### Profile Successfully Created ✅

**Profile Name:** CABB Function 11 - Add ONE File to Existing Representation  
**Profile ID:** 7848184990004641  
**Profile Type:** Digital Import Profile  
**Status:** Active  
**Format:** CSV (values.csv)

This CSV-based profile is now ready to use with the Digital Uploader in Alma following Harvard's minimal 2-column approach. When uploading files prepared by Function 11, use this profile with the drag-and-drop method in Digital Uploader.

**Key Safety Features:**
- ✅ Only 2 CSV columns (mms_id, file_name_1) - NO bibliographic metadata columns
- ✅ "Do not override Originating System" enabled
- ✅ "DCAP01 Bib Resequence And Clear empty fields" normalization (safest option)
- ✅ Match on dc:identifier with overlay mode
- ✅ Skip records with validation issues

This profile adds digital files to existing representations WITHOUT modifying bibliographic metadata, following the proven Harvard University approach.

---

