# Function 22: Diagnose Record Accessibility

---
## ⚠️ **WARNING: THIS FUNCTION DOES NOT WORK**

**DO NOT USE THIS FUNCTION.** It has been disabled and moved to the inactive functions list.

**Known Issues:**
- Cannot properly diagnose records with ns0: corruption
- Alma API returns "clean" XML even when stored records are corrupted
- Reports all records as clean when they may contain hidden corruption
- Cannot detect corruption that only manifests during UPDATE operations

**Status:** Non-functional - Kept for reference only

---

## Overview

**Function 22** tests whether records in a set can be successfully fetched via the Alma API, identifying which records are corrupted beyond API repair. This diagnostic tool helps you understand the scope of corruption issues before attempting fixes.

## Purpose

When records become corrupted (e.g., from namespace handling errors), they may reach a state where:
- The Alma API refuses to serve them (GET returns 400 error)
- API-based tools like Function 21 cannot process them
- Manual intervention in Alma UI is required

Function 22 categorizes each record as:
- **Clean** - Fetchable with no ns0: fields
- **Fixable** - Fetchable with ns0: fields (can be repaired by Function 21)
- **Corrupted** - Unfetchable via API (needs manual intervention)

## What It Does

For each record in your set, Function 22:

1. **Attempts to fetch** the record via Alma API
2. **Categorizes the result**:
   - ✓ Fetchable and clean (no issues)
   - ✓ Fetchable with ns0: fields (repairable)
   - ✗ Unfetchable (critically corrupted)
3. **Counts ns0: references** in fetchable records
4. **Captures error codes** for unfetchable records
5. **Exports detailed CSV** with all findings

## When to Use

Use Function 22:
- **Before running Function 21** - to identify which records can/cannot be fixed
- **After Function 6 corruption** - to assess damage scope
- **When errors occur** - to diagnose which records are causing problems
- **For documentation** - to create a snapshot of record health

## How to Use

### Step 1: Load Your Set
1. Use "Load Set by ID" or "Load MMS IDs from CSV"
2. Verify set is loaded: "Set loaded: N records"

### Step 2: Run Diagnosis
1. Select "22: Diagnose Record Accessibility" from function dropdown
2. Click the function button
3. Monitor progress bar
4. Wait for completion

### Step 3: Review Results
1. Open the generated CSV: `record_diagnosis_YYYYMMDD_HHMMSS.csv`
2. Sort/filter by status column
3. Identify corrupted records for manual intervention
4. Note fixable records for Function 21

## Output File Format

### Filename Convention
**Pattern**: `record_diagnosis_YYYYMMDD_HHMMSS.csv`

**Example**: `record_diagnosis_20260804_151500.csv`

### CSV Columns

| Column | Description | Example Values |
|--------|-------------|----------------|
| mms_id | The MMS ID of the record | 991234567890104641 |
| status | Diagnosis result | Clean, Fetchable with ns0: fields, Unfetchable |
| ns0_count | Number of ns0: references found | 0, 2, 15, ? |
| error_code | API error code (if unfetchable) | 402203, TIMEOUT, blank |
| notes | Detailed explanation | "Contains 2 ns0: reference(s)..." |

### Status Categories

**"Fetchable - Clean"**
- Record fetched successfully
- No ns0: fields detected
- No action needed
- Example: `991234567890104641,Fetchable - Clean,0,,No ns0: fields found - record is clean`

**"Fetchable with ns0: fields"**
- Record fetched successfully
- Contains ns0: namespace corruption
- Can be fixed with Function 21
- Example: `991011687640104641,Fetchable with ns0: fields,2,,Contains 2 ns0: reference(s) - can be fixed by Function 21`

**"Unfetchable - Corrupted"**
- API refuses to return the record
- HTTP 400 error (usually error code 402203)
- Needs manual intervention in Alma UI
- Example: `991011547181804641,Unfetchable - Corrupted,?,402203,API error 400: Input parameters mmsId ... is not valid - Needs manual fix in Alma UI`

**"Timeout"**
- Request timed out (30 second limit)
- Could be network issue or record problem
- Example: `991234567890104641,Timeout,?,TIMEOUT,Request timed out - network issue or record problem`

**"Error"**
- Unexpected exception occurred
- Example: `991234567890104641,Error,?,EXCEPTION,Exception: Connection reset by peer`

## Example Workflow

### Scenario: Function 6 Corrupted Some Records

1. **Run Function 22** on the affected set
   ```
   Set loaded: 2,847 records
   Select: 22: Diagnose Record Accessibility
   Click function button
   ```

2. **Review CSV Results**
   ```
   Clean: 2,800 records (98.4%)
   Fetchable with ns0: 42 records (1.5%)
   Unfetchable: 5 records (0.2%)
   ```

3. **Take Action**:
   - **For 42 fixable**: Create CSV with those MMS IDs, run Function 21
   - **For 5 unfetchable**: Manual intervention required (see below)

## Dealing with Unfetchable Records

If diagnosis finds unfetchable records, you have three options:

### Option 1: Restore from Version History (Recommended)
1. Open record in Alma Metadata Editor
2. Go to Edit → View Versions
3. Find version before corruption
4. Click "Restore"
5. Save the record

### Option 2: Use Function 17 (Automated Restore)
1. Create CSV with corrupted MMS IDs
2. Load as set in CABB
3. Run Function 17 (Restore Metadata from Previous Version)
4. Function 17 will automate the restore workflow via Selenium

### Option 3: Contact Ex Libris Support
If records won't open in UI:
1. Document the error code (usually 402203)
2. List affected MMS IDs
3. Open support case with Ex Libris
4. Request database-level repair

## Summary Report

After diagnosis completes, you'll see:

```
Diagnosis complete: 2,847 records analyzed
  • 2,800 clean (no issues)
  • 42 fetchable with ns0: fields (can be fixed by Function 21)
  • 5 unfetchable/corrupted (need manual intervention)
Results saved to: record_diagnosis_20260804_151500.csv
```

The log will also list each unfetchable record:
```
⚠️  UNFETCHABLE RECORDS DETECTED
These records cannot be fixed via API - manual intervention required:
  • 991011547181804641: API error 400: Input parameters mmsId ... is not valid - Needs manual fix in Alma UI
  • 991011687640104641: API error 400: Input parameters mmsId ... is not valid - Needs manual fix in Alma UI
```

## Technical Details

### API Operations

**For each record:**
```
GET /almaws/v1/bibs/{mms_id}?view=full&expand=None
Accept: application/xml
Timeout: 30 seconds
```

### Error Detection

Function 22 captures:
- HTTP status codes (200, 400, 404, 500, etc.)
- Alma error codes (402203, etc.) from error XML
- Timeout exceptions
- Network/connection exceptions

### ns0: Detection

For fetchable records, counts all instances of "ns0:" in the XML:
- Opening tags: `<ns0:tagname>`
- Closing tags: `</ns0:tagname>`
- Self-closing tags: `<ns0:tagname/>`
- Namespace declarations: `xmlns:ns0="..."`

## Performance

- **Speed**: ~1-2 seconds per record (network dependent)
- **Large sets**: 1,000 records ≈ 20-30 minutes
- **Progress tracking**: Real-time progress bar
- **Interruptible**: Can use kill switch to stop early

## Best Practices

### Before Diagnosis

1. **Ensure good network connection** - timeouts will skew results
2. **Run on representative sample first** - test with 10-20 records
3. **Note when corruption occurred** - helps identify affected records
4. **Have API key ready** - function requires read access

### During Diagnosis

1. **Monitor the log** - watch for patterns in errors
2. **Note timeout records** - may need re-testing
3. **Don't interrupt** - let it complete for accurate count
4. **Check network** - if many timeouts, network may be issue

### After Diagnosis

1. **Sort CSV by status** - group issues together
2. **Count each category** - understand scope
3. **Document findings** - for institutional records
4. **Plan remediation** - Function 21 vs. manual fixes
5. **Re-run after fixes** - verify repairs worked

## Integration with Other Functions

### With Function 21 (Remove ns0: Fields)

**Workflow**:
1. Run Function 22 to diagnose
2. Filter CSV for "Fetchable with ns0: fields"
3. Extract those MMS IDs to new CSV
4. Load that CSV as a set
5. Run Function 21 to fix them
6. Re-run Function 22 to verify fixes

### With Function 17 (Restore Metadata)

**Workflow**:
1. Run Function 22 to find unfetchable records
2. Filter CSV for "Unfetchable - Corrupted"
3. Extract those MMS IDs to new CSV
4. Load that CSV as a set
5. Run Function 17 to restore from version history
6. Re-run Function 22 to verify restoration

### With Function 1 (Fetch XML)

For individual investigation:
1. Run Function 22 on set
2. Note specific MMS IDs with issues
3. Use Function 1 to examine XML of fetchable records
4. Identify specific ns0: fields causing problems

## Limitations

- **Cannot fix records** - diagnostic only, no modifications made
- **Network dependent** - slow/unreliable networks cause timeouts
- **Snapshot in time** - records may change between diagnosis and repair
- **API limits** - Very large sets may hit rate limits

## Troubleshooting

### Many Timeout Results

**Cause**: Slow network or API performance issues

**Solution**:
- Check internet connection
- Try during off-peak hours
- Run diagnosis on smaller batches
- Increase timeout in code if needed

### "Please load a set first"

**Cause**: No records loaded

**Solution**:
- Load set via "Load Set by ID"
- Or load MMS IDs from CSV
- Verify "Set loaded" message appears

### All Records Show "Clean" but ns0: Known to Exist

**Cause**: ns0: fields might be in specific locations not caught by string search

**Solution**:
- Use Function 1 to manually inspect sample record XML
- Check if ns0: appears in comments or CDATA (not in actual elements)

## Related Documentation

- **FUNCTION_21_REMOVE_NS0_FIELDS.md** - Fix fetchable records with ns0: corruption
- **FUNCTION_17_RESTORE_METADATA.md** - Restore unfetchable records from version history
- **FUNCTION_1_FETCH_DISPLAY_XML.md** - Manually inspect individual record XML

## Version History

- **2026-08-04** - Initial implementation
  - Diagnoses record fetchability via API
  - Categorizes clean, fixable, and corrupted records
  - Exports detailed CSV with findings
  - Created to identify scope of Function 6 corruption

---

*Function 22 is a diagnostic tool - it identifies problems but does not fix them. Use Function 21 for fixable records and Function 17 or manual intervention for unfetchable records.*
