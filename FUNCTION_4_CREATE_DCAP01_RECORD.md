# Function 4: Create New DCAP01 Dublin Core Record

## Overview

Function 4 creates a new bibliographic record in Alma from scratch using a simplified Dublin Core metadata template. This function is designed for rapid creation of digital object records that follow the DCAP01 (Dublin Core Application Profile 01) format used by Grinnell College for digital collections.

## What It Does

This function generates a complete Alma bibliographic record with:
- Minimal required MARC21 fields for system compatibility
- Full Dublin Core metadata in the `<anies>` section
- Pre-configured settings for digital objects
- Automatic assignment to appropriate item sets
- Proper namespace declarations
- Instant availability in Alma for further editing

### Key Features

- **Template-based creation**: Uses standardized DCAP01 format
- **Dublin Core focus**: Metadata entered as DC elements
- **No MARC knowledge required**: Automatically handles MARC wrapper
- **Fast record creation**: Single-click submission after data entry
- **Batch-friendly**: Can create multiple records in succession
- **Returns MMS ID**: Get new record identifier immediately
- **Pre-configured**: Includes all necessary XML structure

## The Need for This Function

### Rapid Digital Object Cataloging

Traditional cataloging in Alma requires:
- Extensive MARC21 knowledge
- Navigation through complex Alma metadata editor
- Many clicks and form fields
- Separate step to add Dublin Core
- Manual namespace configuration

**Function 4 streamlines this to:**
- Simple form with Dublin Core fields
- One-click submission
- Automatic MARC wrapper generation
- Immediate record creation
- Ready for enhancement or use

### DCAP01 Consistency

Grinnell College uses DCAP01 for digital collections:
- Standardized Dublin Core fields
- Consistent namespace usage
- Predictable record structure
- Compatible with Digital Collections workflow
- Easy to manage in sets

Function 4 ensures every new record follows this standard automatically.

## How It Works

### Step-by-Step Process

1. **User Input**:
   - Fill in Dublin Core metadata form
   - Enter title, creator, date, identifier, etc.
   - Provide URL for digital object
   
2. **Template Population**:
   - Function loads DCAP01 XML template
   - Inserts user-provided values into placeholders
   - Validates required fields
   
3. **MARC Generation**:
   - Creates minimal MARC21 leader and fields
   - Sets record format to "marc21"
   - Adds system-required fields (001, 008, 245)
   
4. **Dublin Core Section**:
   - Populates `<anies><record>` with DC fields
   - Adds proper namespace declarations
   - Includes all user-provided metadata
   
5. **Record Creation**:
   - Sends POST request to Alma Bibs API
   - Alma assigns new MMS ID
   - Returns created record XML
   
6. **Response**:
   - Displays new MMS ID to user
   - Logs complete record details
   - Record immediately available in Alma

### XML Template Structure

**Top Level:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<bib>
  <record_format>marc21</record_format>
  <suppress_from_publishing>false</suppress_from_publishing>
  <suppress_from_external_search>false</suppress_from_external_search>
  <originating_system>01GCL_INST</originating_system>
  <originating_system_id>{identifier}</originating_system_id>
  
  <!-- MARC21 minimal record -->
  <record>...</record>
  
  <!-- Dublin Core metadata -->
  <anies>...</anies>
</bib>
```

**MARC21 Section:**
```xml
<record>
  <leader>00000nam a2200000 a 4500</leader>
  <controlfield tag="001">{identifier}</controlfield>
  <controlfield tag="008">210101s{year}    xxu|||||||||||||||eng|d</controlfield>
  <datafield ind1="1" ind2="0" tag="245">
    <subfield code="a">{title}</subfield>
  </datafield>
</record>
```

**Dublin Core Section:**
```xml
<anies>
  <record xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"
          xmlns:dc="http://purl.org/dc/elements/1.1/"
          xmlns:dcterms="http://purl.org/dc/terms/">
    <dc:title>{title}</dc:title>
    <dc:creator>{creator}</dc:creator>
    <dc:date>{date}</dc:date>
    <dc:identifier>{identifier}</dc:identifier>
    <dc:identifier>{url}</dc:identifier>
    <dc:type>{type}</dc:type>
    <dc:format>{format}</dc:format>
    <dc:rights>{rights}</dc:rights>
    <!-- Additional fields as provided -->
  </record>
</anies>
```

## Usage

### Basic Record Creation

**Step 1: Access Function 4**

1. Select "Create New DCAP01 Dublin Core Record" from function dropdown
2. Input form appears with Dublin Core fields

**Step 2: Enter Required Metadata**

**Essential Fields:**
- **Title** (`dc:title`): Primary title of digital object
  - Example: "Grinnell College Yearbook, 1925"
  
- **Identifier** (`dc:identifier`): Unique identifier
  - Example: "grinnell:12345"
  - Format: institution:number
  
- **Date** (`dc:date`): Date of creation or publication
  - Example: "1925" or "1925-06-15"
  
- **Type** (`dc:type`): Resource type
  - Example: "Image", "Text", "Collection"
  
- **Format** (`dc:format`): File format
  - Example: "image/jpeg", "application/pdf"
  
- **Rights** (`dc:rights`): Rights statement
  - Example: "Public Domain in the United States"

**Optional Fields:**
- **Creator** (`dc:creator`): Primary creator/author
  - Example: "Smith, John"
  
- **Subject** (`dc:subject`): Topic or keywords
  - Example: "Yearbooks", "Student life"
  - Can add multiple by separating with semicolons
  
- **Description** (`dc:description`): Abstract or summary
  - Example: "Annual yearbook of Grinnell College featuring student photos and activities"
  
- **Publisher** (`dc:publisher`): Publisher name
  - Example: "Grinnell College"
  
- **Contributor** (`dc:contributor`): Secondary creators
  - Example: "Jones, Mary (editor)"
  
- **Coverage** (`dc:coverage`): Geographic or temporal coverage
  - Example: "Grinnell, Iowa"
  
- **Language** (`dc:language`): Language code
  - Example: "eng" (English)
  
- **Relation** (`dc:relation`): Related resources
  - Example: "Part of Grinnell College Yearbook Collection"
  
- **Source** (`dc:source`): Source of derivation
  - Example: "Original print yearbook"

**Step 3: Add Digital Object URL**

- **URL Field**: Link to digital object
  - Example: "https://digital.grinnell.edu/digital/collection/yearbooks/id/12345"
  - This becomes second `dc:identifier`

**Step 4: Submit**

1. Review all entered metadata
2. Click "Create Record" button
3. Wait for confirmation (2-5 seconds)
4. Note the returned MMS ID

**Step 5: Verify**

1. Copy returned MMS ID
2. Use Function 1 to view created record
3. Verify all metadata populated correctly
4. Add to appropriate set if needed

### Example: Creating a Photograph Record

**Scenario**: Creating record for historical photograph

**Input Data:**
```
Title: Main Hall in Winter, 1920
Creator: Johnson, Robert (photographer)
Date: 1920-02-15
Type: Image
Format: image/tiff
Identifier: grinnell:photos:001234
URL: https://digitalcollections.grinnell.edu/photos/001234
Rights: Public Domain in the United States
Subject: Campus buildings; Winter; Main Hall
Description: Photograph of Grinnell College Main Hall covered in snow during winter 1920
Publisher: Grinnell College
Coverage: Grinnell, Iowa
Language: eng
```

**Generated Record:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<bib>
  <record_format>marc21</record_format>
  <suppress_from_publishing>false</suppress_from_publishing>
  <suppress_from_external_search>false</suppress_from_external_search>
  <originating_system>01GCL_INST</originating_system>
  <originating_system_id>grinnell:photos:001234</originating_system_id>
  
  <record>
    <leader>00000nam a2200000 a 4500</leader>
    <controlfield tag="001">grinnell:photos:001234</controlfield>
    <controlfield tag="008">210101s1920    xxu|||||||||||||||eng|d</controlfield>
    <datafield ind1="1" ind2="0" tag="245">
      <subfield code="a">Main Hall in Winter, 1920</subfield>
    </datafield>
  </record>
  
  <anies>
    <record xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"
            xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:dcterms="http://purl.org/dc/terms/">
      <dc:title>Main Hall in Winter, 1920</dc:title>
      <dc:creator>Johnson, Robert (photographer)</dc:creator>
      <dc:date>1920-02-15</dc:date>
      <dc:type>Image</dc:type>
      <dc:format>image/tiff</dc:format>
      <dc:identifier>grinnell:photos:001234</dc:identifier>
      <dc:identifier>https://digitalcollections.grinnell.edu/photos/001234</dc:identifier>
      <dc:rights>Public Domain in the United States</dc:rights>
      <dc:subject>Campus buildings</dc:subject>
      <dc:subject>Winter</dc:subject>
      <dc:subject>Main Hall</dc:subject>
      <dc:description>Photograph of Grinnell College Main Hall covered in snow during winter 1920</dc:description>
      <dc:publisher>Grinnell College</dc:publisher>
      <dc:coverage>Grinnell, Iowa</dc:coverage>
      <dc:language>eng</dc:language>
    </record>
  </anies>
</bib>
```

**Result:**
```
Record created successfully!
MMS ID: 991234567890104641
```

## Dublin Core Field Guidelines

### dc:title

**Purpose**: Primary name of the resource

**Best Practices:**
- Use sentence case or title case consistently
- Include subtitles with colon separation
- Keep concise but descriptive
- Avoid ending punctuation unless part of title

**Examples:**
- ✓ "Grinnell College Yearbook, 1925"
- ✓ "Portrait of Professor Smith"
- ✓ "Annual Report: Academic Year 1950-1951"
- ✗ "UNTITLED" (too vague)
- ✗ "photo.jpg" (not descriptive)

### dc:creator

**Purpose**: Primary person or organization responsible for creation

**Best Practices:**
- Use "Last, First" format for personal names
- Include role in parentheses if helpful
- Use controlled vocabulary when possible
- List multiple creators in separate dc:creator elements

**Examples:**
- ✓ "Smith, John"
- ✓ "Johnson, Mary (photographer)"
- ✓ "Grinnell College"
- ✓ "Unknown photographer"

### dc:date

**Purpose**: Date of creation, publication, or coverage

**Best Practices:**
- Use ISO 8601 format: YYYY-MM-DD or YYYY
- For ranges: use "YYYY/YYYY"
- For approximates: use "circa YYYY"
- For unknown: use "undated" or omit

**Examples:**
- ✓ "1925"
- ✓ "1925-06-15"
- ✓ "1920/1929"
- ✓ "circa 1950"

### dc:type

**Purpose**: General category of resource

**Use DCMI Type Vocabulary:**
- Collection
- Dataset
- Event
- Image
- Interactive Resource
- Moving Image
- Physical Object
- Service
- Software
- Sound
- Still Image
- Text

**Examples:**
- ✓ "Image" (for photographs)
- ✓ "Text" (for documents)
- ✓ "Collection" (for grouped items)

### dc:format

**Purpose**: File format or physical medium

**Best Practices:**
- Use MIME types for digital files
- Use controlled terms for physical formats
- Be specific (image/jpeg not just image)

**Examples:**
- ✓ "image/jpeg"
- ✓ "image/tiff"
- ✓ "application/pdf"
- ✓ "text/html"
- ✓ "Photograph, black and white"

### dc:identifier

**Purpose**: Unique identifier for the resource

**Best Practices:**
- Use institutional prefix
- Follow local identifier scheme
- Include multiple identifiers as separate elements
- One for internal ID, one for URL

**Examples:**
- ✓ "grinnell:12345"
- ✓ "grinnell:photos:001234"
- ✓ "https://digitalcollections.grinnell.edu/item/12345"

### dc:rights

**Purpose**: Rights statement or copyright information

**Best Practices:**
- Use RightsStatements.org URIs when possible
- Or use standardized statements
- Be specific and accurate
- Consider using Function 6 to standardize later

**Examples:**
- ✓ "Public Domain in the United States"
- ✓ "https://rightsstatements.org/page/NoC-US/1.0/"
- ✓ "In Copyright - Educational Use Permitted"
- ✓ "Copyright Grinnell College. All rights reserved."

### dc:subject

**Purpose**: Topic or keywords

**Best Practices:**
- Use controlled vocabularies (LCSH, local thesaurus)
- Separate multiple subjects with semicolons (function will split)
- Use consistent capitalization
- Be specific

**Examples:**
- ✓ "College life; Student activities; Sports"
- ✓ "Architecture; Historic buildings"
- ✓ "Portraits; Faculty; 1920s"

### dc:description

**Purpose**: Abstract, summary, or full description

**Best Practices:**
- Write complete sentences
- Focus on content, not format
- Include context not obvious from other fields
- Keep concise but informative

**Examples:**
- ✓ "Photograph of students gathered on central campus during Homecoming celebration, October 1925"
- ✓ "Annual report documenting academic programs, enrollment statistics, and financial summary for the 1950-1951 academic year"

## Use Cases

### 1. Bulk Digitization Project

**Scenario**: Digitizing 500 historical photographs, need records quickly

**Workflow:**
1. Create spreadsheet with metadata for all 500 photos
2. Use Function 4 to create first record (test template)
3. Verify record structure with Function 1
4. For remaining 499:
   - Copy metadata from spreadsheet
   - Paste into Function 4 form
   - Submit
   - Record MMS ID in spreadsheet
5. Batch add all MMS IDs to digital collections set

**Benefits:**
- Fast record creation (30-60 seconds each)
- Consistent structure across all records
- Can enhance records later as needed
- Immediate availability in Alma

### 2. Born-Digital Collection

**Scenario**: Adding new digital scholarship to repository

**Workflow:**
1. Gather metadata from submission form
2. Generate unique identifier (grinnell:scholarship:NNNNN)
3. Create record with Function 4
4. Add record to "Digital Scholarship" set
5. Link to digital files in Alma Digital
6. Publish to Primo

**Benefits:**
- Simple metadata entry
- Standardized format
- Quick turnaround from submission to availability

### 3. Retrospective Conversion

**Scenario**: Converting legacy finding aids to individual item records

**Workflow:**
1. Extract metadata from finding aid spreadsheet
2. For each item:
   - Map finding aid fields to Dublin Core
   - Create record with Function 4
   - Note MMS ID in conversion tracking
3. Add all records to "Converted from Finding Aids" set
4. Enhance records as resources allow

**Benefits:**
- Rapid conversion of legacy metadata
- Consistent application of DCAP01 standard
- Trackable conversion process

### 4. Test Record Creation

**Scenario**: Need test records for training or system testing

**Workflow:**
1. Use Function 4 with sample metadata
2. Create 5-10 test records
3. Test various Alma workflows
4. Delete test records when done

**Benefits:**
- Quick test record creation
- Realistic record structure
- Safe to delete after testing

## Technical Details

### API Endpoint

**Create Bib Record:**
```
POST /almaws/v1/bibs
Content-Type: application/xml
Accept: application/xml
Body: <bib>...</bib>
```

**Response:**
- Returns complete created record XML
- Includes assigned MMS ID
- Status code 200 on success

### Required MARC Fields

**Leader (fixed length):**
```
00000nam a2200000 a 4500
```

**Control Fields:**
- **001**: Record identifier (uses dc:identifier value)
- **008**: Fixed-length data elements (includes year from dc:date)

**Data Fields:**
- **245**: Title statement (uses dc:title value)

### Namespace Declarations

**Alma Institution Namespace:**
```xml
xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"
```

**Dublin Core Elements:**
```xml
xmlns:dc="http://purl.org/dc/elements/1.1/"
```

**Dublin Core Terms:**
```xml
xmlns:dcterms="http://purl.org/dc/terms/"
```

### Field Mapping

| Form Field | Dublin Core | MARC | Required |
|------------|-------------|------|----------|
| Title | dc:title | 245$a | Yes |
| Creator | dc:creator | - | No |
| Date | dc:date | 008 (year) | Yes |
| Type | dc:type | - | Yes |
| Format | dc:format | - | Yes |
| Identifier | dc:identifier (1st) | 001 | Yes |
| URL | dc:identifier (2nd) | - | No |
| Rights | dc:rights | - | No |
| Subject | dc:subject (multiple) | - | No |
| Description | dc:description | - | No |
| Publisher | dc:publisher | - | No |
| Contributor | dc:contributor | - | No |
| Language | dc:language | 008 (lang) | No |
| Relation | dc:relation | - | No |
| Coverage | dc:coverage | - | No |
| Source | dc:source | - | No |

### Validation

**Pre-Submission Checks:**
- Title not empty
- Identifier not empty
- Date not empty
- Type not empty
- Format not empty

**API-Level Validation:**
- Valid XML structure
- Required MARC fields present
- Namespace declarations correct
- Character encoding (UTF-8)

### Error Handling

**Common Errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| Missing required field | Form incomplete | Fill all required fields |
| Invalid XML | Template corruption | Contact support |
| Duplicate identifier | Identifier already exists | Use different identifier |
| API key invalid | Expired or wrong key | Update .env file |
| Permission denied | API key lacks write access | Add "Bibs" write permission |

## Performance

**Record Creation Time:**
- Form fill: 1-3 minutes
- API call: 2-3 seconds
- Total: ~2-4 minutes per record

**Batch Creation:**
- 10 records: 20-40 minutes
- 50 records: 1.5-3 hours
- 100 records: 3-6 hours

**Optimization Tips:**
- Prepare metadata in spreadsheet first
- Use copy-paste for repeated values
- Create records in batches (rest between batches)
- Consider scripting for very large batches

## Limitations

- **Form-based only**: No CSV import or batch upload
- **Manual entry**: Must type or paste each field
- **No templates**: Cannot save field combinations for reuse
- **No validation preview**: Can't see XML before submission
- **Single record**: Must repeat for each new record
- **No editing**: Must create new record or edit in Alma afterward
- **Basic DC only**: Cannot add custom namespaces or extensions

## Best Practices

### Before Creating Records

1. **Plan identifier scheme**: Establish consistent format
2. **Prepare metadata**: Gather all information first
3. **Test with one record**: Verify template works correctly
4. **Use Function 1 to inspect**: Understand resulting XML structure
5. **Document conventions**: Record decisions about field usage

### During Creation

1. **Copy-paste carefully**: Avoid typos in identifiers
2. **Check required fields**: Ensure all completed before submit
3. **Use consistent formats**: Maintain standards across records
4. **Record MMS IDs**: Save to spreadsheet immediately
5. **Verify each record**: Quick check with Function 1 periodically

### After Creation

1. **Add to sets**: Group related records immediately
2. **Enhance as needed**: Add additional MARC or DC fields in Alma
3. **Link digital files**: Connect to Alma Digital objects
4. **Test discovery**: Verify records appear in Primo
5. **Document creation**: Log batch details for audit trail

## Integration with Other Functions

### Function 1: Verify Created Records

After creating with Function 4:
- Use Function 1 to view complete XML
- Verify all fields populated correctly
- Check namespace declarations
- Confirm MARC fields generated properly

### Function 3: Export Created Records

For documentation:
- Load set of newly created records
- Export to CSV with Function 3
- Review metadata consistency
- Share with stakeholders

### Function 7: Add Grinnell Identifiers

If created with dg_ identifiers:
- Use Function 7 to add Grinnell: identifiers
- Standardizes identifier format
- Makes records consistent with migrated content

### Alma Metadata Editor

For enhancements:
- Open created record in Alma
- Add additional MARC fields
- Enhance Dublin Core
- Add links to digital files
- Configure access permissions

## Troubleshooting

### Record Creation Fails

**Check:**
- All required fields completed
- Identifier is unique (not already used)
- API key valid and has write permission
- Network connection stable

**Try:**
- Copy form data to notepad
- Refresh CABB application
- Re-enter data and retry
- Check Alma service status

### Wrong Data in Created Record

**Issue**: Field values not where expected

**Cause**: Template mapping issue

**Solution**:
- Use Function 1 to view XML
- Verify which field went where
- May need code adjustment
- Contact support if persistent

### MMS ID Not Returned

**Issue**: Record created but no MMS ID shown

**Cause**: API response parsing issue

**Solution**:
- Check Alma for recently created records
- Search by identifier
- Check logs for MMS ID
- Manual lookup in Alma

### Character Encoding Problems

**Issue**: Special characters appear incorrectly

**Cause**: UTF-8 encoding not preserved

**Solution**:
- Ensure form input is UTF-8
- Check browser encoding settings
- May need to edit in Alma afterward
- Report issue for investigation

## Related Documentation

- **Dublin Core Metadata Initiative**: https://www.dublincore.org/
- **MARC21 Format**: https://www.loc.gov/marc/bibliographic/
- **Alma Bibs API**: https://developers.exlibrisgroup.com/alma/apis/bibs/
- **RightsStatements.org**: https://rightsstatements.org/

## Version History

- **Initial Implementation**: DCAP01 template creation
- **Purpose**: Rapid digital object record creation
- **Status**: Active, production-ready
