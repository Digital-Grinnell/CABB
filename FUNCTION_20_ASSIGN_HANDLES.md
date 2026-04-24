# Function 20: Prepare Handles for Assignment

## Purpose

Validates that bibliographic records are properly formatted for Handle assignment and provides step-by-step instructions for running the Alma Handle workflow. This function ensures records are ready before attempting Handle assignment, reducing errors and failed assignments.

## What Function 20 Does

1. **Validates Handle Identifiers** - Checks that each record has properly formatted Handle dc:identifier fields
2. **Detects Format Issues** - Identifies common problems (missing Handles, incorrect formats, known bugs)
3. **Generates Reports** - Creates detailed CSV with validation status for each record
4. **Provides Workflow Instructions** - Generates comprehensive guide for running Alma Handle jobs

## Prerequisites

- Valid Alma API key in .env file
- Records should have Handle identifiers in dc:identifier fields
- Handle format: `http://hdl.handle.net/11084/YOUR_ID`
- Access to Alma UI for running Handle jobs (not automated via API)

## How to Use

### Single Record Mode

1. Enter MMS ID in the input field
2. Click **"20: Prepare Handles for Assignment"**
3. Review validation results in log
4. Check generated CSV for status

### Batch Mode

1. Load a set of MMS IDs (using Set ID or CSV)
2. Click **"20: Prepare Handles for Assignment"**
3. Progress bar shows validation progress
4. Review detailed CSV report when complete

## Validation Status Codes

### READY ✅
- Record has properly formatted Handle dc:identifier
- No known issues detected
- Safe to include in Handle assignment workflow

### NO_HANDLE ⚠️
- Record does not have a Handle dc:identifier
- Must add Handle identifier before running workflow
- Format: `http://hdl.handle.net/11084/YOUR_ID`

### NEEDS_FIX ⚠️
- Record has a Handle but there are formatting issues
- Fix issues before running workflow
- See "issue" column in CSV for specific problems

### ERROR / FAILED ❌
- Could not validate record (API error, XML parsing error, etc.)
- Investigate the specific error message
- Verify MMS ID is correct

## Output Files

### Validation CSV: `handle_preparation_YYYYMMDD_HHMMSS.csv`

Contains:
- **mms_id** - Record identifier
- **status** - Validation status (READY, NO_HANDLE, NEEDS_FIX, ERROR)
- **handle_url** - The Handle URL found in the record
- **issue** - Description of any problems detected
- **fix_needed** - Recommended action to fix issues

### Instructions File: `handle_workflow_instructions_YYYYMMDD_HHMMSS.txt`

Contains:
- Step-by-step Alma Handle workflow (from Ex Libris Support)
- Critical requirements and warnings
- Known issues and troubleshooting
- Next steps based on validation results

## The Proper Handle Workflow

**IMPORTANT:** This workflow is from Ex Libris Support (Feb 2, 2026) and must be followed exactly.

### Step 1: Create a Set in Alma

- Go to Admin → Manage Sets
- Create an ITEMIZED SET with your READY MMS IDs
- Name it descriptively (e.g., "Handle Assignment 2026-04-24")
- Keep sets under 100 records to avoid processing issues

### Step 2: Run the "Handle Migration" Job

- Go to Admin → Run a Job → Handle Migration
- Select your set from Step 1
- Use the control number sequence with your Handle prefix
- This job is **REQUIRED** even if records already have Handles
- It copies Handles from metadata to Alma's background system
- You may see "already has a handle identifier" messages - **this is expected**

### Step 3: Run the Handle Integration Profile

- Go to Configuration → General → External Systems / Integration Profiles
- Find "Persistent Handle Identifiers for Digital Resource"
- Click on the profile name (not the ...)
- Click "Actions" tab
- Enter your set name
- Action: **"Create and Update"**
- Scroll DOWN to "DC METADATA Upon Create"
- Select: **"Do not add metadata"**
- Leave "DC Identifier Prefix Field" blank
- Scroll back UP and click **"Run"** (NOT "Save"!)

### Step 4: Validate Results

- Wait 10-15 minutes for Handle server propagation
- Use CABB **Function 9** (Validate Handle URLs) to test
- Verify Handles resolve correctly to Primo records

## Critical Requirements

### ⚠️ ORDER MATTERS!

Step 2 (Handle Migration job) **MUST** run **BEFORE** Step 3 (Integration Profile).

If you run them out of order, Handles will not resolve correctly.

### ⚠️ DC METADATA SETTING!

When running the integration profile, you **MUST** select:
- **"Do not add metadata"**

If you select "Add new Handles to metadata", this can cause issues with existing Handle assignments.

### ⚠️ SET SIZE LIMIT!

Do not process more than 100 records at once. Large batches can cause the workflow to fail or behave unpredictably.

### ⚠️ COLLECTIONS NOT SUPPORTED!

Handles can only be assigned to **BIBLIOGRAPHIC RECORDS**. Collection records cannot receive Handles via this workflow.

## Known Issues and Troubleshooting

### Issue: Alma assigns sequential numeric Handles

**Symptom:** Alma assigns `11084/1742400039` instead of meaningful `11084/99`

**Cause:** Record may already have a Handle from Alma's automatic numbering

**Solution:** Contact Ex Libris support (reference Case 07949018)

### Issue: Handles don't resolve after workflow

**Possible causes:**
- Steps run out of order (Migration job must run first)
- Wrong DC METADATA setting ("Do not add metadata" required)
- dc:identifier has dcterms:URI attribute (remove this)
- Handle server needs more time (wait 30 minutes)

**Solution:** Re-run workflow in correct order with correct settings

### Issue: 20-30% of Handles don't resolve

This was a known issue in 2025-2026. Possible causes:
- Mixed migration batches
- Timing issues during Handle server setup
- Metadata differences affecting assignment logic

**Solution:** Open Ex Libris support case (reference Case 07949018)

## Integration with Other Functions

### Function 9: Validate Handle URLs
- **Use AFTER** Handle assignment to verify success
- Tests actual Handle resolution
- Reports HTTP status codes
- Identifies non-resolving Handles

### Function 8: Export dc:identifier CSV
- **Use BEFORE** Function 20 to review existing identifiers
- Shows all dc:identifier fields across records
- Helps identify missing or malformed Handles

### Function 16: Add MMS ID as dc:identifier
- Can be used to add MMS ID identifiers
- Does not add Handle identifiers (use Alma workflow for that)

## Example Workflow

1. **Prepare** - Use Function 20 to validate records
   ```
   Records ready: 85/100
   Need fixes: 12/100
   Failed: 3/100
   ```

2. **Fix Issues** - Address problems in records that need fixes
   - Add missing Handle identifiers
   - Fix malformed URLs
   - Remove dcterms:URI attributes

3. **Create Set** - In Alma, create itemized set with 85 READY MMS IDs

4. **Run Jobs** - Execute Handle Migration job, then Integration Profile

5. **Validate** - After 15 minutes, use Function 9 to verify success
   ```
   Handles tested: 85
   200 OK: 83
   404 Not Found: 2
   ```

6. **Troubleshoot** - Investigate the 2 failed Handles
   - Re-run workflow if needed
   - Contact support for persistent issues

## Technical Details

### Handle Format Detection

Function 20 looks for Handles in MARC fields:

**024 Field** (Other Standard Identifier):
- ind1='7' (Source specified in $2)
- $2='hdl' (Handle identifier)
- $a contains Handle value

**856 Field** (Electronic Location):
- $u contains Handle URL
- Must include 'hdl.handle.net' domain

### Validation Logic

1. Fetch bib record XML via Alma API
2. Parse MARC XML
3. Search 024 and 856 fields for Handle identifiers
4. Validate URL format: `http://hdl.handle.net/11084/*`
5. Report any format issues or missing Handles

### Known Limitations

- Cannot check for dcterms:URI attribute (requires DC XML representation)
- Cannot automatically fix issues (requires manual editing in Alma)
- Cannot run Alma jobs via API (must use Alma UI)
- Does not validate whether Handle actually resolves (use Function 9 for that)

## Best Practices

1. **Start Small** - Test with 5-10 records before large batches
2. **Validate First** - Always run Function 20 before attempting Handle assignment
3. **Follow Order** - Never skip steps or run out of sequence
4. **Check Results** - Use Function 9 after assignment to verify success
5. **Keep Records** - Save validation CSVs for troubleshooting
6. **Limit Batches** - Stay under 100 records per workflow run
7. **Wait Between Runs** - Allow 15-30 minutes between attempts

## References

### Documentation

- [Alma Knowledge Center: Persistent Identifiers](https://knowledge.exlibrisgroup.com/)
- Ex Libris Case 07949018 - Handle workflow guidance
- FUNCTION_9_VALIDATE_HANDLES.md - Handle validation tool
- FUNCTION_8_EXPORT_IDENTIFIERS.md - Identifier export tool

### Related Documentation in all-things-alma Directory

- `PROPER_HANDLE_WORKFLOW.md` - Ex Libris workflow from Feb 2, 2026
- `Assigning-Existing-Handles.md` - Detailed workflow with screenshots
- `Handle-Discussion-from-June-2025.md` - Collection limitations
- `Many-Handles-Still-Not-Working.md` - Troubleshooting failed assignments
- `HANDLE_VALIDATION_FEB_2_2026/` - Validation results and outcomes

## Frequently Asked Questions

### Q: Why can't Function 20 assign Handles automatically?

**A:** Handle assignment requires running Alma-specific jobs that are not available via the Alma API. The workflow must be performed in the Alma UI.

### Q: How long does Handle assignment take?

**A:** The Alma jobs typically complete in 1-5 minutes for small sets. Allow 10-15 additional minutes for Handle server propagation before validation.

### Q: Can I assign Handles to collection records?

**A:** No. Alma's Handle system only supports bibliographic records. Collections cannot receive Handles via the standard workflow.

### Q: What if some Handles resolve and others don't?

**A:** This suggests timing or metadata inconsistencies. Re-run the workflow for failed records. If problems persist, contact Ex Libris support with specific MMS IDs.

### Q: Can I use custom Handle prefixes (not 11084)?

**A:** Your institution's Handle prefix is configured in Alma. Function 20 validates any format but assumes `11084/` for Grinnell. Adjust validation logic if needed for different prefixes.

### Q: What if Function 20 says "NEEDS_FIX" but I can't find the issue?

**A:** Check the "issue" column in the CSV for specific problems. Common issues: missing "http://" prefix, wrong domain, trailing spaces, or special characters in Handle ID.

## Support

For additional help:
- Review generated instructions file for detailed guidance
- Check validation CSV for specific error messages
- Consult Alma Knowledge Center documentation
- Open Ex Libris support case if issues persist (reference Case 07949018)
- Review parallel documentation in `../all-things-alma/` directory

## Version History

- **2026-04-24** - Initial implementation
  - Validates Handle identifiers in bib records
  - Generates CSV reports and workflow instructions
  - Based on Ex Libris guidance from Feb 2, 2026
  - Integrates with Function 9 (Handle validation)
