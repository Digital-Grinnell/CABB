"""
Inactive Functions Module for CABB
Contains less frequently used functions that have been moved out of app.py
to reduce file size and improve maintainability.
"""

import logging
import xml.etree.ElementTree as ET
import requests
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# INACTIVE CLASS METHODS - These are called as editor.method_name()
# ============================================================================

def clear_dc_relation_collections(editor, mms_id: str) -> tuple[bool, str]:
    """
    Function 2: Clear all dc:relation fields having a value that begins with 
    "alma:01GCL_INST/bibs/collections/"
    
    Uses the proven approach from change-bib-by-request.py:
    1. GET the bib record as XML
    2. Parse and modify the XML tree
    3. PUT the entire XML tree back
    
    Args:
        editor: The AlmaBibEditor instance
        mms_id: The MMS ID of the bibliographic record
        
    Returns:
        tuple: (success: bool, message: str)
    """
    editor.log(f"Starting clear_dc_relation_collections for MMS ID: {mms_id}")
    if not editor.api_key:
        editor.log("API Key not configured", logging.ERROR)
        return False, "API Key not configured"
    
    try:
        # Get the Alma API base URL
        api_url = editor._get_alma_api_url()
        
        # Step 1: GET the bib record as XML
        editor.log(f"Fetching bibliographic record {mms_id} as XML")
        headers = {'Accept': 'application/xml'}
        response = requests.get(
            f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={editor.api_key}",
            headers=headers
        )
        
        if response.status_code != 200:
            editor.log(f"Failed to fetch record: {response.status_code}", logging.ERROR)
            editor.log(f"Response: {response.text}", logging.ERROR)
            return False, f"Failed to fetch record: {response.status_code}"
        
        # Step 2: Parse the XML response
        editor.log("Parsing XML response")
        root = ET.fromstring(response.text)
        
        # Register namespaces (but NOT the default namespace - we'll handle that in tostring)
        # This prevents xmlns attribute on <bib> root element which Alma rejects
        namespaces_to_register = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        for prefix, uri in namespaces_to_register.items():
            ET.register_namespace(prefix, uri)
        
        editor.log("Registered namespaces: dc, dcterms, xsi (default namespace handled in tostring)")
        
        # Step 3: Find and remove matching dc:relation elements
        # Use namespaces dict for finding
        search_namespaces = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/'
        }
        pattern = 'alma:01GCL_INST/bibs/collections/'
        relations = root.findall('.//dc:relation', search_namespaces)
        editor.log(f"Found {len(relations)} dc:relation elements")
        
        removed_count = 0
        for relation in relations:
            if relation.text and relation.text.startswith(pattern):
                editor.log(f"MATCH FOUND - Removing: {relation.text}")
                # Find parent and remove the element
                for parent in root.iter():
                    if relation in list(parent):
                        parent.remove(relation)
                        removed_count += 1
                        break
        
        if removed_count == 0:
            editor.log("No matching dc:relation fields found")
            return True, "No matching dc:relation fields found"
        
        # Step 4: Convert the modified tree back to XML bytes
        editor.log(f"Removed {removed_count} dc:relation field(s), preparing to update")
        xml_bytes = ET.tostring(root, encoding='utf-8')
        
        # Convert to string and fix namespace prefixes
        xml_str = xml_bytes.decode('utf-8')
        # Remove ns0: prefix from element names (e.g., <ns0:record> -> <record>)
        xml_str = xml_str.replace('ns0:', '').replace(':ns0', '')
        # Remove the xmlns declaration for the Alma namespace (Alma rejects it on <bib>)
        xml_str = xml_str.replace(' xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"', '')
        xml_bytes = xml_str.encode('utf-8')
        
        # Log a sample of the XML being sent (first 500 chars)
        editor.log("=" * 60)
        editor.log("XML being sent to Alma (first 500 chars):")
        editor.log(xml_str[:500])
        editor.log("=" * 60)
        
        # Step 5: PUT the modified XML back to Alma
        editor.log(f"Updating record {mms_id} in Alma")
        headers = {
            'Accept': 'application/xml',
            'Content-Type': 'application/xml; charset=utf-8'
        }
        response = requests.put(
            f"{api_url}/almaws/v1/bibs/{mms_id}?validate=true&override_warning=true&override_lock=true&stale_version_check=false&check_match=false&apikey={editor.api_key}",
            headers=headers,
            data=xml_bytes
        )
        
        if response.status_code != 200:
            editor.log(f"Failed to update record: {response.status_code}", logging.ERROR)
            editor.log(f"Response: {response.text}", logging.ERROR)
            editor.log("=" * 60)
            editor.log("Full XML that was sent:")
            editor.log(xml_str)
            editor.log("=" * 60)
            return False, f"Failed to update record: {response.status_code}"
        
        editor.log(f"Successfully updated record {mms_id}")
        return True, f"Successfully removed {removed_count} dc:relation field(s) from record {mms_id}"
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        editor.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
        editor.log(f"Full traceback:\n{error_details}", logging.DEBUG)
        return False, f"Error processing record {mms_id}: {str(e)}"


def filter_csv_by_pre1930_dates(editor, input_file: str = None, output_file: str = None) -> tuple[bool, str]:
    """
    Function 4: Filter CSV export to only records 95 years old or older
    
    Reads the most recent alma_export_*.csv file and filters records that have
    non-empty date values 95 years or older (rounded down to year) in any of these fields:
    - dc:date
    - dcterms:created
    - dcterms:issued
    - dcterms:dateSubmitted
    - dcterms:dateAccepted
    
    The cutoff year is calculated dynamically as: current_year - 95
    Dates are rounded down to the year only when applying the age requirement.
    
    Args:
        editor: The AlmaBibEditor instance
        input_file: Optional path to input CSV (if None, uses most recent alma_export_*.csv)
        output_file: Optional path to output CSV (if None, generates timestamped filename)
        
    Returns:
        tuple: (success: bool, message: str)
    """
    import csv
    import glob
    import re
    from datetime import datetime
    
    # Calculate cutoff year (95 years ago)
    current_year = datetime.now().year
    cutoff_year = current_year - 95
    
    editor.log(f"Starting CSV filter for records 95+ years old (cutoff year: {cutoff_year})")
    
    try:
        # Find most recent alma_export_*.csv if not specified
        if input_file is None:
            csv_files = glob.glob("alma_export_*.csv")
            if not csv_files:
                return False, "No alma_export_*.csv files found"
            input_file = max(csv_files, key=lambda f: f)
            editor.log(f"Using input file: {input_file}")
        
        # Generate output filename if not specified
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"historical_export_{timestamp}.csv"
        
        # Date fields to check
        date_fields = [
            "dc:date",
            "dcterms:created",
            "dcterms:issued",
            "dcterms:dateSubmitted",
            "dcterms:dateAccepted"
        ]
        
        def extract_year(date_str: str) -> Optional[int]:
            """Extract 4-digit year from date string"""
            if not date_str or not date_str.strip():
                return None
            
            # Look for 4-digit year
            match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', date_str)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    return None
            return None
        
        def has_old_date(row: dict) -> bool:
            """Check if any date field contains a year 95+ years old (year <= cutoff_year)"""
            for field in date_fields:
                date_value = row.get(field, "")
                year = extract_year(date_value)
                if year is not None and year <= cutoff_year:
                    return True
            return False
        
        # Read input CSV and filter
        filtered_rows = []
        total_rows = 0
        
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            
            for row in reader:
                total_rows += 1
                if has_old_date(row):
                    filtered_rows.append(row)
        
        # Write filtered results
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_rows)
        
        message = f"Filtered {len(filtered_rows)} of {total_rows} records (95+ years old, ≤{cutoff_year}) → {output_file}"
        editor.log(message)
        return True, message
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        editor.log(f"Error filtering CSV: {str(e)}", logging.ERROR)
        editor.log(f"Full traceback:\n{error_details}", logging.DEBUG)
        return False, f"Error filtering CSV: {str(e)}"


def replace_author_copyright_rights(editor, mms_id: str) -> tuple[bool, str, str]:
    """
    Function 6: Replace dc:rights fields starting with "Copyright to this work is held by the author(s)"
    or "Grinnell College Libraries does not own the copyright in these images..."
    with a rights statement URL and xml:lang attribute. Also adds new dc:rights for records with none.
    
    Finds dc:rights fields with value starting "Copyright to this work is held by the author(s)"
    or "Grinnell College Libraries does not own the copyright in these images..."
    and replaces with dc:rights xml:lang="eng" value="https://rightsstatements.org/page/NoC-US/1.0/?language=en"
    For records with NO dc:rights elements, adds the new Public Domain rights element.
    Ensures no duplicate values are created.
    
    Args:
        editor: The AlmaBibEditor instance
        mms_id: The MMS ID of the bibliographic record
        
    Returns:
        tuple: (success: bool, message: str, outcome: str)
            outcome can be: 'replaced', 'added', 'removed_duplicates', 'no_change', 'error'
    """
    editor.log(f"Starting replace_author_copyright_rights for MMS ID: {mms_id}")
    if not editor.api_key:
        editor.log("API Key not configured", logging.ERROR)
        return False, "API Key not configured", "error"
    
    try:
        # Get the Alma API base URL
        api_url = editor._get_alma_api_url()
        
        # Step 1: GET the bib record as XML
        editor.log(f"Fetching bibliographic record {mms_id} as XML")
        headers = {'Accept': 'application/xml'}
        response = requests.get(
            f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={editor.api_key}",
            headers=headers
        )
        
        if response.status_code != 200:
            editor.log(f"Failed to fetch record: {response.status_code}", logging.ERROR)
            editor.log(f"Response: {response.text}", logging.ERROR)
            return False, f"Failed to fetch record: {response.status_code}", "error"
        
        # Step 2: Parse the XML response
        editor.log("Parsing XML response")
        root = ET.fromstring(response.text)
        
        # Register namespaces (but NOT the default namespace)
        namespaces_to_register = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xml': 'http://www.w3.org/XML/1998/namespace'
        }
        for prefix, uri in namespaces_to_register.items():
            ET.register_namespace(prefix, uri)
        
        editor.log("Registered namespaces: dc, dcterms, xsi, xml")
        
        # Step 3: Find dc:rights elements
        search_namespaces = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/'
        }
        rights_elements = root.findall('.//dc:rights', search_namespaces)
        editor.log(f"Found {len(rights_elements)} dc:rights elements")
        
        # Constants
        pattern_start = "Copyright to this work is held by the author(s)"
        grinnell_pattern_start = "Grinnell College Libraries does not own the copyright in these images"
        new_value = '<a href="https://rightsstatements.org/page/NoC-US/1.0/?language=en" target="_blank">Public Domain in the United States</a>'
        url_pattern = "https://rightsstatements.org/page/NoC-US/1.0/?language=en"
        
        # Check if new value already exists
        url_exists = False
        url_element = None
        author_copyright_elements = []
        grinnell_copyright_elements = []
        old_link_elements = []  # Links without target attribute
        
        for rights_elem in rights_elements:
            if rights_elem.text:
                if rights_elem.text == new_value:
                    url_exists = True
                    url_element = rights_elem
                    editor.log(f"Rights statement URL with target already exists")
                elif rights_elem.text.startswith(pattern_start):
                    author_copyright_elements.append(rights_elem)
                    editor.log(f"Found author copyright field: {rights_elem.text[:80]}...")
                elif rights_elem.text.startswith(grinnell_pattern_start):
                    grinnell_copyright_elements.append(rights_elem)
                    editor.log(f"Found Grinnell copyright field: {rights_elem.text[:80]}...")
                elif url_pattern in rights_elem.text and 'target="_blank"' not in rights_elem.text:
                    # Found old link without target attribute
                    old_link_elements.append(rights_elem)
                    editor.log(f"Found old link without target: {rights_elem.text[:80]}...")
        
        # If URL with target already exists, remove any author copyright fields, grinnell copyright fields, and old links
        if url_exists:
            elements_to_remove = author_copyright_elements + grinnell_copyright_elements + old_link_elements
            if elements_to_remove:
                editor.log(f"URL exists, removing {len(elements_to_remove)} old field(s)")
                for rights_elem in elements_to_remove:
                    # Find parent and remove the element
                    for parent in root.iter():
                        if rights_elem in list(parent):
                            parent.remove(rights_elem)
                            editor.log(f"Removed: {rights_elem.text[:80]}...")
                            break
                
                changes_made = len(elements_to_remove)
                outcome = "removed_duplicates"
            else:
                editor.log("URL exists and no old fields to remove")
                return True, "Rights statement URL already exists, no changes needed", "no_change"
        else:
            # URL doesn't exist, replace author copyright fields, grinnell copyright fields, or old links OR add new element
            elements_to_replace = author_copyright_elements + grinnell_copyright_elements + old_link_elements
            if not elements_to_replace:
                # No dc:rights elements exist, add a new one
                if len(rights_elements) == 0:
                    warning_msg = f"WARNING: Record {mms_id} has NO dc:rights element - adding Public Domain rights statement"
                    editor.log(warning_msg, logging.WARNING)
                    editor.log("No dc:rights elements found, adding new Public Domain rights element")
                    # Find where to add dc:rights
                    # In Alma XML, Dublin Core elements are inside anies/any, not inside a "metadata" element
                    # Look for any existing DC element to find the parent
                    dc_parent = None
                    
                    # Try to find parent by looking for other dc: elements
                    dc_test_tags = ['title', 'creator', 'subject', 'description', 'publisher', 'contributor', 'date', 'type', 'format', 'identifier', 'source', 'language', 'relation', 'coverage']
                    for tag in dc_test_tags:
                        test_elem = root.find(f'.//{{http://purl.org/dc/elements/1.1/}}{tag}', search_namespaces)
                        if test_elem is not None:
                            # Find this element's parent
                            for parent in root.iter():
                                if test_elem in list(parent):
                                    dc_parent = parent
                                    editor.log(f"Found DC parent element via dc:{tag}")
                                    break
                            if dc_parent is not None:
                                break
                    
                    # If no DC elements found, try to find anies/any element
                    if dc_parent is None:
                        anies_elem = root.find('.//{http://com/exlibris/urm/general/xmlbeans}anies')
                        if anies_elem is not None:
                            any_elems = list(anies_elem)
                            if any_elems:
                                dc_parent = any_elems[0]
                                editor.log("Found DC parent element via anies/any")
                    
                    if dc_parent is not None:
                        # Create new dc:rights element
                        new_rights_elem = ET.Element('{http://purl.org/dc/elements/1.1/}rights')
                        new_rights_elem.text = new_value
                        dc_parent.append(new_rights_elem)
                        editor.log(f"Added new dc:rights element: {new_value}")
                        changes_made = 1
                        outcome = "added"
                    else:
                        editor.log("Could not find parent element to add dc:rights", logging.ERROR)
                        return False, "Could not find parent element to add dc:rights", "error"
                else:
                    editor.log("No matching dc:rights fields found")
                    return True, "No matching dc:rights fields found", "no_change"
            
            else:
                # Replace first matching element with new value
                first_elem = elements_to_replace[0]
                first_elem.text = new_value
                editor.log(f"Replaced first old field with new URL")
                
                # Remove any additional fields (duplicates)
                for rights_elem in elements_to_replace[1:]:
                    for parent in root.iter():
                        if rights_elem in list(parent):
                            parent.remove(rights_elem)
                            editor.log(f"Removed duplicate: {rights_elem.text[:80]}...")
                            break
                
                changes_made = len(elements_to_replace)
                outcome = "replaced"
        
        # Step 4: Convert the modified tree back to XML bytes
        editor.log(f"Modified {changes_made} dc:rights field(s), preparing to update")
        xml_bytes = ET.tostring(root, encoding='utf-8')
        
        # Convert to string and fix namespace prefixes
        xml_str = xml_bytes.decode('utf-8')
        # Remove ns0: prefix from element names
        xml_str = xml_str.replace('ns0:', '').replace(':ns0', '')
        # Remove the xmlns declaration for the Alma namespace
        xml_str = xml_str.replace(' xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"', '')
        xml_bytes = xml_str.encode('utf-8')
        
        # Log a sample of the XML being sent
        editor.log("=" * 60)
        editor.log("XML being sent to Alma (first 500 chars):")
        editor.log(xml_str[:500])
        editor.log("=" * 60)
        
        # Step 5: PUT the modified XML back to Alma
        editor.log(f"Updating record {mms_id} in Alma")
        headers = {
            'Accept': 'application/xml',
            'Content-Type': 'application/xml; charset=utf-8'
        }
        response = requests.put(
            f"{api_url}/almaws/v1/bibs/{mms_id}?validate=true&override_warning=true&override_lock=true&stale_version_check=false&check_match=false&apikey={editor.api_key}",
            headers=headers,
            data=xml_bytes
        )
        
        if response.status_code != 200:
            editor.log(f"Failed to update record: {response.status_code}", logging.ERROR)
            editor.log(f"Response: {response.text}", logging.ERROR)
            editor.log("=" * 60)
            editor.log("Full XML that was sent:")
            editor.log(xml_str)
            editor.log("=" * 60)
            return False, f"Failed to update record: {response.status_code}", "error"
        
        editor.log(f"Successfully updated record {mms_id}")
        
        # Build appropriate success message based on outcome
        if outcome == "removed_duplicates":
            message = f"Removed {changes_made} duplicate field(s) (rights URL already present) in record {mms_id}"
        elif outcome == "replaced":
            message = f"Replaced {changes_made} old dc:rights field(s) with Public Domain link in record {mms_id}"
        elif outcome == "added":
            message = f"Added new Public Domain dc:rights element to record {mms_id}"
        else:
            message = f"Updated record {mms_id}"
        
        return True, message, outcome
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        editor.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
        editor.log(f"Full traceback:\n{error_details}", logging.DEBUG)
        return False, f"Error: {str(e)}", "error"


def add_grinnell_identifier(editor, mms_id: str) -> tuple[bool, str]:
    """
    Function 7: Add Grinnell: dc:identifier field as needed
    
    Finds records with dc:identifier starting with "dg_" and adds a corresponding
    "Grinnell:<number>" dc:identifier if one doesn't already exist.
    
    Args:
        editor: The AlmaBibEditor instance
        mms_id: The MMS ID of the bibliographic record
        
    Returns:
        tuple: (success: bool, message: str)
    """
    editor.log(f"Starting add_grinnell_identifier for MMS ID: {mms_id}")
    if not editor.api_key:
        editor.log("API Key not configured", logging.ERROR)
        return False, "API Key not configured"
    
    try:
        # Get the Alma API base URL
        api_url = editor._get_alma_api_url()
        
        # Step 1: GET the bib record as XML
        editor.log(f"Fetching bibliographic record {mms_id} as XML")
        headers = {'Accept': 'application/xml'}
        response = requests.get(
            f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={editor.api_key}",
            headers=headers
        )
        
        if response.status_code != 200:
            editor.log(f"Failed to fetch record: {response.status_code}", logging.ERROR)
            editor.log(f"Response: {response.text}", logging.ERROR)
            return False, f"Failed to fetch record: {response.status_code}"
        
        # Step 2: Parse the XML response
        editor.log("Parsing XML response")
        root = ET.fromstring(response.text)
        
        # Register namespaces
        namespaces_to_register = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        for prefix, uri in namespaces_to_register.items():
            ET.register_namespace(prefix, uri)
        
        editor.log("Registered namespaces: dc, dcterms, xsi")
        
        # Step 3: Find dc:identifier elements
        search_namespaces = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/'
        }
        identifier_elements = root.findall('.//dc:identifier', search_namespaces)
        editor.log(f"Found {len(identifier_elements)} dc:identifier elements")
        
        # Step 4: Check for existing identifiers
        dg_identifier = None
        grinnell_identifier_exists = False
        
        for identifier_elem in identifier_elements:
            if identifier_elem.text:
                if identifier_elem.text.startswith("dg_"):
                    dg_identifier = identifier_elem.text
                    editor.log(f"Found dg_ identifier: {dg_identifier}")
                elif identifier_elem.text.startswith("Grinnell:"):
                    grinnell_identifier_exists = True
                    editor.log(f"Found existing Grinnell: identifier: {identifier_elem.text}")
        
        # Step 5: Determine if we need to add Grinnell: identifier
        if not dg_identifier:
            editor.log("No dg_ identifier found - nothing to do")
            return True, "No dg_ identifier found"
        
        if grinnell_identifier_exists:
            editor.log("Grinnell: identifier already exists - nothing to do")
            return True, "Grinnell: identifier already exists"
        
        # Step 6: Extract number from dg_ identifier and create Grinnell: identifier
        # Extract number from "dg_<number>"
        dg_number = dg_identifier.replace("dg_", "")
        new_grinnell_id = f"Grinnell:{dg_number}"
        editor.log(f"Creating new identifier: {new_grinnell_id}")
        
        # Step 7: Add new dc:identifier element
        # Find the parent element that contains dc:identifier elements
        # Typically this is the record element in the anies section
        parent_element = None
        for identifier_elem in identifier_elements:
            for parent in root.iter():
                if identifier_elem in list(parent):
                    parent_element = parent
                    break
            if parent_element:
                break
        
        if not parent_element:
            editor.log("Could not find parent element for dc:identifier", logging.ERROR)
            return False, "Could not find parent element for dc:identifier"
        
        # Create new dc:identifier element
        new_identifier = ET.Element('{http://purl.org/dc/elements/1.1/}identifier')
        new_identifier.text = new_grinnell_id
        parent_element.append(new_identifier)
        editor.log(f"Added new dc:identifier: {new_grinnell_id}")
        
        # Step 8: Convert the modified tree back to XML bytes
        xml_bytes = ET.tostring(root, encoding='utf-8')
        
        # Convert to string and fix namespace prefixes
        xml_str = xml_bytes.decode('utf-8')
        # Remove ns0: prefix from element names
        xml_str = xml_str.replace('ns0:', '').replace(':ns0', '')
        # Remove the xmlns declaration for the Alma namespace
        xml_str = xml_str.replace(' xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"', '')
        xml_bytes = xml_str.encode('utf-8')
        
        # Log a sample of the XML being sent
        editor.log("=" * 60)
        editor.log("XML being sent to Alma (first 500 chars):")
        editor.log(xml_str[:500])
        editor.log("=" * 60)
        
        # Step 9: PUT the modified XML back to Alma
        editor.log(f"Updating record {mms_id} in Alma")
        headers = {
            'Accept': 'application/xml',
            'Content-Type': 'application/xml; charset=utf-8'
        }
        response = requests.put(
            f"{api_url}/almaws/v1/bibs/{mms_id}?validate=true&override_warning=true&override_lock=true&stale_version_check=false&check_match=false&apikey={editor.api_key}",
            headers=headers,
            data=xml_bytes
        )
        
        if response.status_code != 200:
            editor.log(f"Failed to update record: {response.status_code}", logging.ERROR)
            editor.log(f"Response: {response.text}", logging.ERROR)
            editor.log("=" * 60)
            editor.log("Full XML that was sent:")
            editor.log(xml_str)
            editor.log("=" * 60)
            return False, f"Failed to update record: {response.status_code}"
        
        editor.log(f"Successfully updated record {mms_id}")
        return True, f"Added {new_grinnell_id} to record {mms_id}"
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        editor.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
        editor.log(f"Full traceback:\n{error_details}", logging.DEBUG)
        return False, f"Error processing record {mms_id}: {str(e)}"
