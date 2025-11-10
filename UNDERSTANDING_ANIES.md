# Understanding ANIES in Alma Bibliographic Records

## What is ANIES?

**ANIES** stands for **Analytics Information Export Schema**. It's a specific XML format used by Ex Libris Alma to store and exchange bibliographic metadata in a standardized way.

## Why is it significant in this code?

### 1. Where metadata lives
When you fetch a bibliographic record from Alma's API, the detailed descriptive metadata (like Dublin Core fields) is stored in the `anies` field, not in the top-level record structure.

### 2. Dublin Core fields
The `dc:relation` field you're trying to clear is part of Dublin Core metadata, which is embedded within the ANIES XML structure.

### 3. The structure you're seeing

```
Bibliographic Record (JSON/dict)
├── mms_id
├── title
├── created_date
└── anies (list or string)
    └── XML containing Dublin Core metadata
        ├── dc:title
        ├── dc:creator
        ├── dc:relation  ← This is what we're removing
        └── ... other DC fields
```

### 4. Why it's a list
In your case, `anies` is a **list** because a single bibliographic record can have multiple metadata representations (different schemas, different versions, etc.). Each item in the list contains XML metadata.

## In your specific use case

The workflow is:

1. **Fetch the bib record** → Get JSON with an `anies` field
2. **Parse the ANIES XML** → Find Dublin Core elements
3. **Remove `dc:relation` fields** matching your pattern
4. **Update the ANIES XML** → Reconstruct the XML with changes
5. **Send the modified record back to Alma** → Save changes

The "collections" pattern you're removing (`alma:01GCL_INST/bibs/collections/...`) appears to be Alma's way of linking bibliographic records to digital collections, and you're removing those links from the descriptive metadata.

## Technical Details

### ANIES Data Types
- **String**: Single XML document containing metadata
- **List**: Multiple XML documents (most common in practice)
- **Dict**: Dictionary containing XML or other structured data

### Dublin Core Namespace
The Dublin Core elements use the namespace `http://purl.org/dc/elements/1.1/`, which is why the code references:
```python
namespaces = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'dcterms': 'http://purl.org/dc/terms/'
}
```

### Processing Flow in the Code

```python
# 1. Fetch record
bib_response = alma_cnxn.bibs.catalog.get(mms_id)

# 2. Extract anies
anies_data = bib_response['anies']

# 3. Process each anies item (if it's a list)
for anies_item in anies_data:
    # Parse XML
    root = ET.fromstring(anies_item)
    
    # Find dc:relation elements
    relations = root.findall('.//dc:relation', namespaces)
    
    # Remove matching ones
    for relation in relations:
        if relation.text.startswith('alma:01GCL_INST/bibs/collections/'):
            parent.remove(relation)

# 4. Update record with modified anies
bib_response['anies'] = modified_anies
alma_cnxn.bibs.catalog.post(mms_id, bib_response)
```

## References

- [Ex Libris Alma API Documentation](https://developers.exlibrisgroup.com/alma/apis/)
- [Dublin Core Metadata Initiative](https://www.dublincore.org/)
- [Analytics Information Export Schema (ANIES) - Ex Libris Documentation](https://developers.exlibrisgroup.com/alma/apis/docs/xsd/rest_bib.xsd/)

## Related Files

- `app.py` - Main application containing ANIES processing logic
- `README.md` - Project documentation
