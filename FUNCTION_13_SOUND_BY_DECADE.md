# Function 13: Analyze Sound Records by Decade

## Overview

Function 13 is a specialized analytical tool that identifies sound recordings within a bibliographic set and organizes them chronologically by decade. This read-only function extracts date information from Dublin Core metadata, calculates decade groupings, and exports the results to a timestamped CSV file. It's particularly useful for creating decade-based sub-collections, conducting collection analysis, or preparing sound archives for cataloging projects.

## What It Does

This function filters all loaded records to find those with `dc:type` of "sound", extracts temporal metadata from date fields, calculates the decade for each recording, and exports comprehensive results to a CSV file for further analysis or collection development.

### Key Features

- **Intelligent date extraction**: Prioritizes `dc:date` over `dcterms:created` for year information
- **Batch API processing**: Uses efficient batch API calls (100 records per request)
- **Flexible date parsing**: Handles various date formats and extracts 4-digit years using regex
- **Decade calculation**: Automatically computes decade groupings (1960s, 1970s, etc.)
- **Progress tracking**: Real-time progress updates during batch processing
- **Kill switch support**: Can be stopped mid-process if needed
- **Comprehensive output**: Exports both original date fields and computed values
- **Error resilient**: Continues processing even if individual records have issues

## Input Requirements

### Prerequisites
1. **Loaded Set Required**: You must first load a set of MMS IDs using:
   - Load Set by ID (fetches members from an Alma set)
   - Load MMS IDs from CSV (imports MMS IDs from a file)

2. **API Permissions**: Requires Bibliographic Records API read access

3. **Verify Records**: Check the status area confirms records are loaded before running

### What Makes a Record "Sound"?
Records are included in the analysis if:
- The `dc:type` field contains exactly "sound" (case-insensitive)
- The record has Dublin Core metadata in the `anies` field
- Examples of sound types: oral histories, interviews, music recordings, lectures, podcasts

## CSV Output Structure

### File Name Format
`sound_records_by_decade_YYYYMMDD_HHMMSS.csv`

Example: `sound_records_by_decade_20260224_152304.csv`

### Column Descriptions

| Column | Description | Example |
|--------|-------------|---------|
| **MMS ID** | Alma record identifier | `991011589514904641` |
| **Title** | Record title from `dc:title` | `Wally Walker Interview` |
| **dc:type** | Resource type (always "sound" for included records) | `sound` |
| **dc:date** | Original date value from `dc:date` field | `2010` or `1978-05-15` |
| **dcterms:created** | Date value from `dcterms:created` field | `2010` |
| **Year** | Extracted 4-digit year | `2010` |
| **Decade** | Calculated decade grouping | `2010s` |

### Sample CSV Output
```csv
MMS ID,Title,dc:type,dc:date,dcterms:created,Year,Decade
991011589514904641,Wally Walker Interview,sound,,2010,2010,2010s
991011591714204641,Andreas Vassilos '78,sound,,1978,1978,1970s
991011591714404641,Alison Williams Presley '03,sound,,2003,2003,2000s
```

## How It Works

### Step-by-Step Process

#### 1. Initialization
- Generates timestamped filename
- Opens CSV file for writing
- Writes column headers
- Initializes counters for statistics

#### 2. Batch Processing Setup
- Divides loaded MMS IDs into batches of 100
- Calculates total number of API calls needed
- Logs API efficiency comparison (batch vs individual calls)

#### 3. For Each Batch (100 records at a time)
- Checks kill switch (user can stop process)
- Makes single batch API call to fetch all 100 records
- Logs batch progress: "Processing batch 3/15: records 201-300"

#### 4. For Each Record in Batch
- **Check dc:type**: Extract `dc:type` field value
- **Filter for sound**: If `dc:type` ≠ "sound", skip and increment non-sound counter
- **Extract metadata** (for sound records):
  - Title from `dc:title`
  - Date from `dc:date`
  - Created date from `dcterms:created`
- **Parse year**:
  - Try to find 4-digit year (1000-2099) in `dc:date` first
  - If not found, try `dcterms:created`
  - Uses regex pattern: `\b(1[0-9]{3}|20[0-9]{2})\b`
- **Calculate decade**:
  - Formula: `(year // 10) * 10`
  - Append "s": `1985 → 1980 → "1980s"`
- **Write CSV row** with all extracted and calculated values
- **Update progress**: Callback every record, log every 50 records

#### 5. Completion
- Closes CSV file
- Reports final statistics
- Logs API efficiency metrics
- Returns success message with filename

### Date Extraction Logic

**Priority Order:**
1. Look for year in `dc:date` field first
2. If no year found, look in `dcterms:created`
3. If no year found in either, record has empty Year and Decade

**Year Matching Rules:**
- Must be 4 digits
- Must start with 1 (1000-1999) or 20 (2000-2099)
- Uses first matching year if multiple years appear in field
- Examples of what matches:
  - `1985` → matches
  - `2010-05-15` → matches 2010
  - `circa 1960s` → matches 1960
  - `May 15, 1978` → matches 1978

**Examples:**
- `dc:date = "1985"` → Year: 1985, Decade: 1980s
- `dc:date = ""`, `dcterms:created = "2003"` → Year: 2003, Decade: 2000s
- `dc:date = "circa 1960"` → Year: 1960, Decade: 1960s
- `dc:date = "unknown"`, `dcterms:created = ""` → Year: (empty), Decade: (empty)

### Decade Calculation

**Formula:**
```python
decade_start = (year // 10) * 10
decade = f"{decade_start}s"
```

**Examples:**
- 1960 → 1960s
- 1969 → 1960s
- 1970 → 1970s
- 1985 → 1980s
- 2003 → 2000s
- 2010 → 2010s

## How to Use

### Basic Operation

1. **Load Records**
   - Enter Set ID or load MMS IDs from CSV
   - Click "Load Set Members" or "Load from CSV"
   - Verify record count in status area

2. **Run Function**
   - Select "Analyze Sound Records by Decade" from function dropdown
   - Click "Run Function on Set"
   - No confirmation dialog (read-only operation)

3. **Monitor Progress**
   - Watch progress bar update
   - Check log messages for batch progress
   - Can click Kill Switch to stop if needed

4. **Review Results**
   - Open the generated CSV file
   - Check statistics in log output
   - Verify sound recordings are captured correctly

### Post-Export Analysis

#### Sorting by Decade
After export, open CSV in Excel/Google Sheets and sort:
1. Primary sort: Decade column (A-Z for alphabetical)
2. Secondary sort: Year column (ascending for chronological)

This groups all recordings by decade, then chronologically within each decade.

#### Filtering for Specific Decades
Use spreadsheet filters to focus on specific time periods:
- Filter Decade = "1960s" → Show only 1960s recordings
- Filter Decade = "1970s" OR "1980s" → Show 1970s and 1980s
- Filter Year ≥ 1990 → Show 1990s onward

#### Identifying Issues
Look for records that need attention:
- **Empty Year/Decade**: Sort by Year to find blanks at top
- **Future dates**: Filter Year > current year
- **Ancient dates**: Filter Year < 1900 (likely errors)
- **Wrong type**: All dc:type should be "sound"

## Technical Details

### API Endpoint

**Batch Bibliographic Records:**
```
GET /almaws/v1/bibs?mms_id={comma_separated_ids}&view=full&expand=None
```

**Parameters:**
- `mms_id`: Comma-separated list of up to 100 MMS IDs
- `view=full`: Returns complete record data with Dublin Core
- `expand=None`: No expansion of linked data
- `apikey`: API authentication key

**Example Request:**
```
GET /almaws/v1/bibs?mms_id=991011589514904641,991011591714204641,991011591714404641&view=full&expand=None
```

### XML Parsing

**Dublin Core Namespaces:**
```python
namespaces = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/'
}
```

**Field Extraction:**
- Parses the `anies` field which contains Dublin Core XML
- Uses namespace-aware XPath queries
- Handles multiple values (takes first occurrence)

**Example XML:**
```xml
<anies>
  <record>
    <dc:title>Wally Walker Interview</dc:title>
    <dc:type>sound</dc:type>
    <dcterms:created>2010</dcterms:created>
  </record>
</anies>
```

### Performance Optimization

**Batch Processing Efficiency:**
- **Without batching**: 1,000 records = 1,000 API calls
- **With batching**: 1,000 records = 10 API calls (100 per batch)
- **Savings**: 99% reduction in API calls
- **Speed improvement**: ~10x faster processing
- **API quota impact**: Minimal (uses only 1% of calls)

**Progress Logging:**
- Every batch: "Processing batch X/Y: records A-B"
- Every 50 records: "Analyzed X/Y records - Found N sound recordings"
- Final summary: Counts for all categories

## Example Use Cases

### Use Case 1: Create Decade-Based Sub-Collections

**Scenario:** You have 500 oral history interviews in one large collection and want to organize them into decade-based sub-collections for easier browsing.

**Steps:**
1. Load set ID: `ORAL_HISTORY_COLLECTION`
2. Run Function 13
3. Open resulting CSV: `sound_records_by_decade_20260224_152304.csv`
4. Sort by Decade column
5. Create sub-collection sets in Alma:
   - `ORAL_HISTORY_1960s`
   - `ORAL_HISTORY_1970s`
   - `ORAL_HISTORY_1980s`
   - etc.
6. Use MMS IDs from CSV to add records to appropriate sub-collection sets
7. Configure digital collection hierarchy in Alma

**Result:** Users can browse interviews by decade, improving discoverability.

---

### Use Case 2: Collection Analysis & Gap Identification

**Scenario:** You're writing a grant application and need to document your sound collection's chronological coverage and identify gaps.

**Steps:**
1. Load all sound recordings set: `ALL_DIGITAL_SOUND`
2. Run Function 13
3. Open CSV and create pivot table:
   - Rows: Decade
   - Values: Count of MMS ID
4. Visualize decade distribution

**Example Results:**
```
1940s: 12 items
1950s: 23 items
1960s: 45 items
1970s: 78 items
1980s: 134 items
1990s: 89 items
2000s: 156 items
2010s: 98 items
```

**Insights:**
- Strong coverage of 1980s-2000s
- Gap in pre-1960s recordings
- Grant proposal: "We seek funding to digitize and preserve our under-represented 1940s-1950s sound recordings"

---

### Use Case 3: Metadata Quality Control

**Scenario:** After a migration, verify that all sound recordings have proper date metadata.

**Steps:**
1. Load migrated sound recordings set
2. Run Function 13
3. Filter CSV for empty Year values
4. Review records with missing dates:
   - Check original metadata
   - Research date information
   - Update `dc:date` or `dcterms:created` fields
5. Re-run Function 13 to verify improvements

**Quality Metrics:**
- Before: 234/500 records (47%) with dates
- After cleanup: 487/500 records (97%) with dates
- Remaining 13 records documented as "date unknown"

---

### Use Case 4: Prepare for Chronological Digital Exhibit

**Scenario:** Creating a digital exhibit showcasing the evolution of campus culture through oral histories, organized by decade.

**Steps:**
1. Load interviews set: `CAMPUS_CULTURE_INTERVIEWS`
2. Run Function 13
3. Open CSV and sort by Decade, then Year
4. For each decade section of exhibit:
   - Select 5-10 representative interviews
   - Use MMS IDs to locate records
   - Extract thumbnails and metadata
   - Write decade overview text
5. Build exhibit with chronological narrative

**Exhibit Structure:**
- 1960s: Civil Rights & Vietnam Era (8 interviews)
- 1970s: Second Wave Feminism (12 interviews)
- 1980s: Technology & Globalization (15 interviews)
- etc.

## Statistics Reported

### Counters Tracked

| Statistic | Description | Logged At |
|-----------|-------------|-----------|
| **Sound recordings found** | Records where `dc:type` = "sound" | End of process |
| **Non-sound records** | Records skipped (different `dc:type`) | End of process |
| **Missing/invalid dates** | Sound records without parseable year | End of process |
| **Failed records** | Records that encountered processing errors | End of process |

### Example Log Output

```
Starting sound records decade analysis for 500 records to sound_records_by_decade_20260224_152304.csv
Using batch API calls: 5 calls for 500 records
Processing batch 1/5: records 1-100
Processing batch 2/5: records 101-200
Analyzed 50/500 records - Found 38 sound recordings
Analyzed 100/500 records - Found 73 sound recordings
Processing batch 3/5: records 201-300
Analyzed 150/500 records - Found 109 sound recordings
Processing batch 4/5: records 301-400
Analyzed 200/500 records - Found 147 sound recordings
Processing batch 5/5: records 401-500
Analyzed 250/500 records - Found 178 sound recordings
Sound records analysis complete: 178 sound recordings found, 322 non-sound, 12 missing/invalid dates, 0 failed. File: sound_records_by_decade_20260224_152304.csv
API efficiency: 5 batch calls vs 500 individual calls (saved 495 calls)
```

## Common Issues & Solutions

### Issue: No Sound Recordings Found

**Problem:** CSV is created but shows 0 sound recordings, all records counted as "non-sound"

**Possible Causes:**
1. Records don't have `dc:type` field
2. Records have different type value (e.g., "audio", "Sound Recording")
3. Wrong set loaded (contains images/text, not sound)

**Solution:**
- Run Function 3 (Export to CSV) to check actual `dc:type` values
- Check if type uses different terminology
- Verify you loaded the correct set
- If type is "audio" or other variant, may need custom processing

---

### Issue: Many Records Show Missing/Invalid Dates

**Problem:** High count of sound records with empty Year/Decade

**Possible Causes:**
1. Records missing `dc:date` and `dcterms:created` fields
2. Date fields contain text that doesn't include 4-digit year
3. Dates use non-standard format

**Examples of Unparseable Dates:**
- "circa mid-twentieth century" (no specific year)
- "196?" (incomplete year)
- "Undated" (no year information)

**Solution:**
1. Open CSV and review records with empty Year
2. Look up records in Alma to check date fields
3. Update metadata with proper dates where possible
4. Document records with legitimately unknown dates
5. Consider adding estimated dates in brackets: "[1965]"

---

### Issue: Wrong Decade Calculated

**Problem:** A 1969 recording shows Decade = "1960s" but you expected "1970s"

**Explanation:** This is correct! Decade calculation uses mathematical floor division:
- 1960-1969 → 1960s
- 1970-1979 → 1970s
- 1980-1989 → 1980s

The decade is based on the first year, not rounding. 1969 is indeed part of the 1960s.

**If this doesn't match your needs:**
- You can post-process the CSV to use different decade groupings
- Or group by 5-year periods instead (1965-1969, 1970-1974, etc.)

---

### Issue: Future Dates in Output

**Problem:** Some records show Year = 2025 or later (future dates)

**Causes:**
1. Data entry error during cataloging
2. Planned/scheduled recordings not yet created
3. Date field contains project end date instead of recording date

**Solution:**
1. Filter CSV for Year > current year
2. Review these records in Alma
3. Correct date metadata as appropriate
4. Verify date represents actual recording date, not publication/digitization date

---

### Issue: CSV Doesn't Open Correctly

**Problem:** CSV file shows garbled text or formatting issues

**Solutions:**
- **Encoding**: File uses UTF-8. Open in Excel using "Get Data" → "From Text/CSV" → select UTF-8
- **Special characters**: Some titles contain quotes, commas, or non-English characters. Use proper CSV application that handles escaping
- **Double-click opens wrong app**: Right-click → Open With → Excel/Google Sheets

## Best Practices

### Before Running

1. **Verify your set** - Preview first 20 records to confirm you loaded correct set
2. **Check record count** - Ensure count matches expectations
3. **Review set composition** - If set includes non-sound records, that's fine (they'll be filtered out)
4. **Estimate runtime** - Approximately 1 second per record (500 records ≈ 8 minutes)

### During Processing

1. **Monitor progress** - Watch log messages for batch progress
2. **Don't close app** - Let process complete (or use Kill Switch to stop gracefully)
3. **Check for errors** - Watch for warning/error messages in log
4. **Note statistics** - Progress messages show how many sound recordings found so far

### After Export

1. **Validate output** - Open CSV and spot-check a few records
2. **Review statistics** - Check if counts make sense (expected ratio of sound to non-sound)
3. **Sort by Decade** - Primary analysis should group by decade
4. **Check for blanks** - Filter or sort to find records missing dates
5. **Back up file** - Save copy before making edits for future reference
6. **Document findings** - Note patterns, issues, or insights for collection management

### Metadata Improvement Workflow

1. **First run** - Baseline analysis, identify problems
2. **Fix dates** - Update records with missing/incorrect dates
3. **Second run** - Verify improvements
4. **Compare results** - Track progress (e.g., 60% → 95% with dates)
5. **Iterate** - Continue improving until acceptable quality

## Related Functions

### Complementary Functions

- **Function 3: Export Set to DCAP01 CSV** - Get complete Dublin Core metadata for detailed analysis
- **Function 1: Fetch and Display Single XML** - Inspect individual records to troubleshoot date issues
- **Function 11: Identify Single-TIFF Objects** - Similar filtering function for different resource type

### Workflow Integration

**Collection Development Workflow:**
1. Function 13: Analyze sound records by decade (this function)
2. Create decade-based sets in Alma
3. Function 3: Export each decade set for detailed metadata review
4. Update/enhance metadata as needed
5. Function 13: Re-run to verify improvements

**Quality Control Workflow:**
1. Load migrated records set
2. Function 13: Identify records without dates
3. Function 1: Review individual records
4. Fix metadata in Alma
5. Function 13: Re-run to confirm 100% coverage

## Notes

- **Read-only function**: No modifications to Alma data
- **Case-insensitive type matching**: "sound", "Sound", "SOUND" all match
- **First year wins**: If date field contains multiple years, first 4-digit match is used
- **Decade ties to year**: 1960 and 1969 are both 1960s (not rounded)
- **Empty values allowed**: Records without dates still exported (Year and Decade blank)
- **Kill switch supported**: Can stop processing mid-run; partial CSV is saved
- **Timestamped files**: Each run creates new file; old files preserved
- **UTF-8 encoding**: Proper handling of international characters and special symbols

## File Management

**Output Location:** Same directory as the application (workspace root)

**File Naming:** `sound_records_by_decade_YYYYMMDD_HHMMSS.csv`
- YYYY = 4-digit year
- MM = 2-digit month
- DD = 2-digit day
- HH = hour (24-hour format)
- MM = minute
- SS = second

**Example:** `sound_records_by_decade_20260224_152304.csv`
- Created: February 24, 2026 at 3:23:04 PM

**Retention:** Files are not automatically deleted. Manually remove old exports when no longer needed.

## API Efficiency

**Batch Processing Benefits:**
- **1,000 records**: 10 API calls (vs 1,000 individual calls)
- **Savings**: 99% reduction in API calls
- **Speed**: ~10x faster processing
- **API quota**: Minimal impact
- **Network**: Fewer connections, less overhead

**Logged Efficiency Stats:**
```
API efficiency: 5 batch calls vs 500 individual calls (saved 495 calls)
```

This demonstrates the function used only 5 API calls instead of 500, saving 99% of API quota and processing time.
