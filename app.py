"""
Clean Alma Bibs in Bulk (CABB)
A Flet UI app designed to perform various Alma-Digital bib record editing functions.
"""

import flet as ft
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import requests

# Load environment variables
load_dotenv()

# Configure logging
log_filename = f"cabb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce Flet's logging verbosity
logging.getLogger('flet').setLevel(logging.WARNING)
logging.getLogger('flet_core').setLevel(logging.WARNING)
logging.getLogger('flet_desktop').setLevel(logging.WARNING)


class AlmaBibEditor:
    """Main application class for Alma Bib Records Editor"""
    
    def __init__(self, log_callback=None):
        logger.info("Initializing AlmaBibEditor")
        self.api_key = os.getenv('ALMA_API_KEY', '')
        # Region should be: 'America', 'Europe', 'Asia Pacific', 'Canada', or 'China'
        self.api_region = os.getenv('ALMA_API_REGION', 'America')
        self.status_text = None
        self.log_callback = log_callback
        self.set_members = []  # Store MMS IDs from loaded set
        self.set_info = None   # Store set metadata
        self.current_record = None  # Store currently fetched bib record
        self.kill_switch = False  # Emergency stop for batch operations
        logger.debug(f"API Region: {self.api_region}")
        logger.debug(f"API Key configured: {'Yes' if self.api_key else 'No'}")
        
    def log(self, message, level=logging.INFO):
        """Log a message and send to UI callback"""
        logger.log(level, message)
        if self.log_callback:
            self.log_callback(message)
    
    def _get_alma_api_url(self):
        """Get the correct Alma API URL based on region"""
        region_urls = {
            'America': 'https://api-na.hosted.exlibrisgroup.com',
            'Europe': 'https://api-eu.hosted.exlibrisgroup.com',
            'Asia Pacific': 'https://api-ap.hosted.exlibrisgroup.com',
            'Canada': 'https://api-ca.hosted.exlibrisgroup.com',
            'China': 'https://api-cn.hosted.exlibrisgroup.com'
        }
        return region_urls.get(self.api_region, region_urls['America'])
    
    def initialize_alma_connection(self):
        """Verify API Key is configured"""
        self.log("Verifying Alma API configuration...")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured. Please set ALMA_API_KEY in .env file"
        
        self.log(f"API Key configured for region: {self.api_region}")
        self.log("Ready to process records", logging.INFO)
        return True, f"Ready to process records (Region: {self.api_region})"
    
    def fetch_set_details(self, set_id: str) -> tuple[bool, str, dict]:
        """
        Fetch details about a set from Alma
        
        Args:
            set_id: The ID of the set to retrieve
            
        Returns:
            tuple: (success: bool, message: str, set_data: dict)
        """
        self.log(f"Fetching set details for Set ID: {set_id}")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured", {}
        
        try:
            api_url = self._get_alma_api_url()
            
            self.log(f"Requesting set {set_id} from Alma API")
            response = requests.get(
                f"{api_url}/almaws/v1/conf/sets/{set_id}?apikey={self.api_key}",
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 401 or response.status_code == 400:
                # Check if it's an authorization issue
                if 'UNAUTHORIZED' in response.text or 'API-key not defined' in response.text:
                    error_msg = "API Key not authorized for Sets API. Please add 'Configuration' permissions in Alma API key settings."
                    self.log(error_msg, logging.ERROR)
                    self.log(f"Response: {response.text}", logging.ERROR)
                    return False, error_msg, {}
            
            if response.status_code != 200:
                self.log(f"Failed to fetch set: {response.status_code}", logging.ERROR)
                self.log(f"Response: {response.text}", logging.ERROR)
                return False, f"Failed to fetch set: {response.status_code}", {}
            
            set_data = response.json()
            set_name = set_data.get('name', 'Unknown')
            set_type = set_data.get('type', {}).get('desc', 'Unknown')
            member_count = set_data.get('number_of_members', {}).get('value', 0)
            
            self.set_info = set_data
            self.log(f"Successfully fetched set: {set_name}")
            self.log(f"Set type: {set_type}, Members: {member_count}")
            
            return True, f"Set: {set_name} ({member_count} members)", set_data
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error fetching set {set_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error fetching set {set_id}: {str(e)}", {}
    
    def fetch_set_members(self, set_id: str, progress_callback=None, max_members=0) -> tuple[bool, str, list]:
        """
        Fetch all member MMS IDs from a set
        
        Args:
            set_id: The ID of the set
            progress_callback: Optional callback function(current, total) for progress updates
            max_members: Maximum number of members to fetch (0 = no limit)
            
        Returns:
            tuple: (success: bool, message: str, members: list of MMS IDs)
        """
        self.log(f"Fetching members for Set ID: {set_id} (max: {max_members if max_members > 0 else 'unlimited'})")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured", []
        
        try:
            api_url = self._get_alma_api_url()
            all_members = []
            offset = 0
            limit = 100  # API default page size
            total_records = 0
            
            while True:
                self.log(f"Fetching members (offset: {offset}, limit: {limit})")
                response = requests.get(
                    f"{api_url}/almaws/v1/conf/sets/{set_id}/members?limit={limit}&offset={offset}&apikey={self.api_key}",
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code != 200:
                    self.log(f"Failed to fetch set members: {response.status_code}", logging.ERROR)
                    self.log(f"Response: {response.text}", logging.ERROR)
                    return False, f"Failed to fetch set members: {response.status_code}", []
                
                data = response.json()
                members = data.get('member', [])
                
                # Get total record count from first response
                if offset == 0:
                    total_records = data.get('total_record_count', 0)
                    # Adjust total if max_members is set
                    if max_members > 0 and max_members < total_records:
                        total_records = max_members
                
                if not members:
                    break
                
                # Extract MMS IDs from member objects
                for member in members:
                    mms_id = member.get('id')
                    if mms_id:
                        all_members.append(mms_id)
                        # Stop if we've reached the limit
                        if max_members > 0 and len(all_members) >= max_members:
                            break
                
                self.log(f"Retrieved {len(members)} members (total so far: {len(all_members)})")
                
                # Update progress
                if progress_callback and total_records > 0:
                    progress_callback(len(all_members), total_records)
                
                # Check if we've reached the limit
                if max_members > 0 and len(all_members) >= max_members:
                    break
                
                # Check if there are more results
                if offset + limit >= total_records:
                    break
                
                offset += limit
            
            self.set_members = all_members
            self.log(f"Successfully fetched {len(all_members)} members from set {set_id}")
            
            return True, f"Fetched {len(all_members)} member records", all_members
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error fetching set members {set_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error fetching set members {set_id}: {str(e)}", []
    
    def fetch_bib_records_batch(self, mms_ids: list) -> dict:
        """
        Fetch multiple bibliographic records in a single batch API call (up to 100 IDs).
        
        Args:
            mms_ids: List of MMS IDs to retrieve (max 100)
            
        Returns:
            dict: Dictionary mapping mms_id -> record dict, only contains successfully fetched records
        """
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return {}
        
        if not mms_ids:
            return {}
        
        # Limit to 100 IDs per Alma API restrictions
        if len(mms_ids) > 100:
            self.log(f"Warning: Batch size {len(mms_ids)} exceeds limit, truncating to 100", logging.WARNING)
            mms_ids = mms_ids[:100]
        
        try:
            api_url = self._get_alma_api_url()
            
            # Join MMS IDs with comma for batch request
            mms_ids_param = ','.join([str(mms_id).strip() for mms_id in mms_ids])
            
            self.log(f"Batch API call: Fetching {len(mms_ids)} records")
            headers = {'Accept': 'application/json'}
            response = requests.get(
                f"{api_url}/almaws/v1/bibs?mms_id={mms_ids_param}&view=full&expand=None&apikey={self.api_key}",
                headers=headers
            )
            
            if response.status_code != 200:
                self.log(f"Batch API call failed: {response.status_code}", logging.ERROR)
                self.log(f"Response: {response.text}", logging.ERROR)
                return {}
            
            # Parse JSON response
            data = response.json()
            records = {}
            
            # Extract bibs from response
            bibs = data.get('bib', [])
            if not isinstance(bibs, list):
                bibs = [bibs] if bibs else []
            
            self.log(f"Batch API returned {len(bibs)} records")
            
            # Process each bib record
            for bib in bibs:
                mms_id = bib.get('mms_id')
                if not mms_id:
                    continue
                
                # Extract anies field (contains Dublin Core XML)
                anies = bib.get('anies', [])
                if not isinstance(anies, list):
                    anies = [anies] if anies else []
                
                # Store record in same format as fetch_bib_record
                records[mms_id] = {
                    'mms_id': mms_id,
                    'originating_system_id': bib.get('originating_system_id', ''),
                    'title': bib.get('title', ''),
                    'date_of_publication': '',
                    'author': '',
                    'originating_system': bib.get('originating_system_id', '')[:9] if bib.get('originating_system_id') else '01GCL_INST',
                    'anies': anies
                }
            
            return records
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error in batch fetch: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return {}
    
    def fetch_bib_record(self, mms_id: str) -> tuple[bool, str]:
        """
        Fetch a bibliographic record and store it in current_record
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Fetching bib record: {mms_id}")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured"
        
        try:
            api_url = self._get_alma_api_url()
            
            # GET the bib record as JSON (easier to parse than XML for this use case)
            self.log(f"Requesting bibliographic record {mms_id} from Alma API")
            headers = {'Accept': 'application/json'}
            response = requests.get(
                f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={self.api_key}",
                headers=headers
            )
            
            if response.status_code != 200:
                self.log(f"Failed to fetch record: {response.status_code}", logging.ERROR)
                self.log(f"Response: {response.text}", logging.ERROR)
                return False, f"Failed to fetch record: {response.status_code}"
            
            # Parse JSON response
            bib = response.json()
            
            # Extract anies field (contains Dublin Core XML)
            anies = bib.get('anies', [])
            if not isinstance(anies, list):
                anies = [anies] if anies else []
            
            # Store record
            self.current_record = {
                'mms_id': mms_id,
                'originating_system_id': bib.get('originating_system_id', ''),
                'title': bib.get('title', ''),
                'date_of_publication': '',
                'author': '',
                'originating_system': bib.get('originating_system_id', '')[:9] if bib.get('originating_system_id') else '01GCL_INST',
                'anies': anies
            }
            
            self.log(f"Successfully fetched record {mms_id}")
            return True, f"Successfully fetched record {mms_id}"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error fetching record {mms_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error fetching record {mms_id}: {str(e)}"
    
    def fetch_and_display_xml(self, mms_id: str, page=None) -> tuple[bool, str]:
        """
        Function 1: Fetch and display the XML for a bibliographic record
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            page: The Flet page object (for displaying dialog)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Fetching XML for MMS ID: {mms_id}")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured"
        
        try:
            # Get the Alma API base URL
            api_url = self._get_alma_api_url()
            
            # GET the bib record as XML
            self.log(f"Requesting bibliographic record {mms_id} from Alma API")
            headers = {'Accept': 'application/xml'}
            response = requests.get(
                f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={self.api_key}",
                headers=headers
            )
            
            if response.status_code != 200:
                self.log(f"Failed to fetch record: {response.status_code}", logging.ERROR)
                self.log(f"Response: {response.text}", logging.ERROR)
                return False, f"Failed to fetch record: {response.status_code}"
            
            # Pretty print the XML
            xml_text = response.text
            self.log(f"Raw XML length: {len(xml_text)} chars")
            
            try:
                # Parse and pretty print
                dom = minidom.parseString(xml_text)
                pretty_xml = dom.toprettyxml(indent="  ")
                # Remove extra blank lines
                pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
                self.log(f"Pretty-printed XML length: {len(pretty_xml)} chars")
            except Exception as e:
                self.log(f"Could not pretty-print XML: {str(e)}", logging.WARNING)
                pretty_xml = xml_text
            
            self.log(f"Successfully fetched XML for MMS ID: {mms_id}")
            
            # Display in popup if page is provided
            if page:
                self.log("Displaying XML dialog...")
                self._show_xml_dialog(page, mms_id, pretty_xml)
            else:
                self.log("WARNING: No page object provided, cannot show dialog", logging.WARNING)
            
            return True, f"Successfully fetched and displayed XML for record {mms_id} ({len(xml_text)} chars)"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error fetching record {mms_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error fetching record {mms_id}: {str(e)}"
    
    def _show_xml_dialog(self, page, mms_id: str, xml_content: str):
        """Show XML content in a dialog with copy functionality"""
        self.log(f"Creating dialog for {len(xml_content)} chars of XML...")
        
        def close_dialog(e):
            self.log("Closing XML dialog")
            xml_dialog.open = False
            page.update()
        
        def copy_xml(e):
            self.log("Copying XML to clipboard")
            page.set_clipboard(xml_content)
            copy_button.text = "Copied!"
            page.update()
            # Reset button text after 2 seconds
            import threading
            def reset_text():
                import time
                time.sleep(2)
                copy_button.text = "Copy to Clipboard"
                page.update()
            threading.Thread(target=reset_text, daemon=True).start()
        
        copy_button = ft.TextButton("Copy to Clipboard", on_click=copy_xml)
        
        xml_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"XML for MMS ID: {mms_id}"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(f"Size: {len(xml_content)} characters", size=12, color=ft.Colors.GREY_700),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.TextField(
                            value=xml_content,
                            multiline=True,
                            read_only=True,
                            min_lines=25,
                            max_lines=25,
                            text_size=11,
                            border_color=ft.Colors.GREY_400,
                        ),
                        width=800,
                        height=600,
                    ),
                ], scroll=ft.ScrollMode.AUTO),
                padding=10,
            ),
            actions=[
                copy_button,
                ft.TextButton("Close", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        self.log("Opening dialog using page.open()...")
        page.open(xml_dialog)
        self.log("Dialog should now be visible")
    
    def clear_dc_relation_collections(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 2: Clear all dc:relation fields having a value that begins with 
        "alma:01GCL_INST/bibs/collections/"
        
        Uses the proven approach from change-bib-by-request.py:
        1. GET the bib record as XML
        2. Parse and modify the XML tree
        3. PUT the entire XML tree back
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Starting clear_dc_relation_collections for MMS ID: {mms_id}")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured"
        
        try:
            # Get the Alma API base URL
            api_url = self._get_alma_api_url()
            
            # Step 1: GET the bib record as XML
            self.log(f"Fetching bibliographic record {mms_id} as XML")
            headers = {'Accept': 'application/xml'}
            response = requests.get(
                f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={self.api_key}",
                headers=headers
            )
            
            if response.status_code != 200:
                self.log(f"Failed to fetch record: {response.status_code}", logging.ERROR)
                self.log(f"Response: {response.text}", logging.ERROR)
                return False, f"Failed to fetch record: {response.status_code}"
            
            # Step 2: Parse the XML response
            self.log("Parsing XML response")
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
            
            self.log("Registered namespaces: dc, dcterms, xsi (default namespace handled in tostring)")
            
            # Step 3: Find and remove matching dc:relation elements
            # Use namespaces dict for finding
            search_namespaces = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/'
            }
            pattern = 'alma:01GCL_INST/bibs/collections/'
            relations = root.findall('.//dc:relation', search_namespaces)
            self.log(f"Found {len(relations)} dc:relation elements")
            
            removed_count = 0
            for relation in relations:
                if relation.text and relation.text.startswith(pattern):
                    self.log(f"MATCH FOUND - Removing: {relation.text}")
                    # Find parent and remove the element
                    for parent in root.iter():
                        if relation in list(parent):
                            parent.remove(relation)
                            removed_count += 1
                            break
            
            if removed_count == 0:
                self.log("No matching dc:relation fields found")
                return True, "No matching dc:relation fields found"
            
            # Step 4: Convert the modified tree back to XML bytes
            self.log(f"Removed {removed_count} dc:relation field(s), preparing to update")
            xml_bytes = ET.tostring(root, encoding='utf-8')
            
            # Convert to string and fix namespace prefixes
            xml_str = xml_bytes.decode('utf-8')
            # Remove ns0: prefix from element names (e.g., <ns0:record> -> <record>)
            xml_str = xml_str.replace('ns0:', '').replace(':ns0', '')
            # Remove the xmlns declaration for the Alma namespace (Alma rejects it on <bib>)
            xml_str = xml_str.replace(' xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"', '')
            xml_bytes = xml_str.encode('utf-8')
            
            # Log a sample of the XML being sent (first 500 chars)
            self.log("=" * 60)
            self.log("XML being sent to Alma (first 500 chars):")
            self.log(xml_str[:500])
            self.log("=" * 60)
            
            # Step 5: PUT the modified XML back to Alma
            self.log(f"Updating record {mms_id} in Alma")
            headers = {
                'Accept': 'application/xml',
                'Content-Type': 'application/xml; charset=utf-8'
            }
            response = requests.put(
                f"{api_url}/almaws/v1/bibs/{mms_id}?validate=true&override_warning=true&override_lock=true&stale_version_check=false&check_match=false&apikey={self.api_key}",
                headers=headers,
                data=xml_bytes
            )
            
            if response.status_code != 200:
                self.log(f"Failed to update record: {response.status_code}", logging.ERROR)
                self.log(f"Response: {response.text}", logging.ERROR)
                self.log("=" * 60)
                self.log("Full XML that was sent:")
                self.log(xml_str)
                self.log("=" * 60)
                return False, f"Failed to update record: {response.status_code}"
            
            self.log(f"Successfully updated record {mms_id}")
            return True, f"Successfully removed {removed_count} dc:relation field(s) from record {mms_id}"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error processing record {mms_id}: {str(e)}"
    
    def export_to_csv(self, mms_ids: list, output_file: str, progress_callback=None) -> tuple[bool, str]:
        """
        Function 3: Export bibliographic records to CSV with Dublin Core fields
        Uses batch API calls (100 records per call) for efficiency.
        
        Args:
            mms_ids: List of MMS IDs to export
            output_file: Path to output CSV file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        
        self.log(f"Starting CSV export for {len(mms_ids)} records to {output_file}")
        
        # Define CSV column headings
        column_headings = [
            "group_id", "collection_id", "mms_id", "originating_system_id", "compoundrelationship",
            "dc:title", "dcterms:alternative", "oldalttitle", "dc:identifier",
            "dcterms:identifier.dcterms:URI", "dcterms:tableOfContents", "dc:creator",
            "dc:contributor", "dc:subject", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dc:description", "dcterms:provenance",
            "dcterms:bibliographicCitation", "dcterms:abstract", "dcterms:publisher",
            "dcterms:publisher", "dc:date", "dcterms:created", "dcterms:issued",
            "dcterms:dateSubmitted", "dcterms:dateAccepted", "dc:type", "dc:format",
            "dcterms:extent", "dcterms:extent", "dcterms:medium",
            "dcterms:format.dcterms:IMT", "dcterms:type.dcterms:DCMIType", "dc:language",
            "dc:relation", "dcterms:isPartOf", "dcterms:isPartOf", "dcterms:isPartOf",
            "dc:coverage", "dcterms:spatial", "dcterms:spatial.dcterms:Point",
            "dcterms:temporal", "dc:rights", "dc:source", "bib custom field",
            "rep_label", "rep_public_note", "rep_access_rights", "rep_usage_type",
            "rep_library", "rep_note", "rep_custom field", "file_name_1", "file_label_1",
            "file_name_2", "file_label_2", "googlesheetsource", "dginfo"
        ]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=column_headings)
                writer.writeheader()
                
                success_count = 0
                failed_count = 0
                total = len(mms_ids)
                batch_size = 100  # Alma API supports up to 100 MMS IDs per batch call
                
                # Calculate total number of API calls
                total_batches = (total + batch_size - 1) // batch_size
                self.log(f"Using batch API calls: {total_batches} calls for {total} records (vs {total} individual calls)")
                
                # Process in batches
                for batch_start in range(0, total, batch_size):
                    batch_end = min(batch_start + batch_size, total)
                    batch_ids = mms_ids[batch_start:batch_end]
                    batch_num = (batch_start // batch_size) + 1
                    
                    self.log(f"Processing batch {batch_num}/{total_batches}: records {batch_start+1}-{batch_end}")
                    
                    # Fetch batch of records
                    batch_records = self.fetch_bib_records_batch(batch_ids)
                    
                    # Process each record in the batch
                    for i in range(len(batch_ids)):
                        record_index = batch_start + i + 1
                        mms_id = batch_ids[i]
                        
                        try:
                            # Check if record was successfully fetched
                            if mms_id in batch_records:
                                # Set as current record for field extraction
                                self.current_record = batch_records[mms_id]
                                
                                # Map record to CSV row
                                row = self._map_bib_to_csv_row(self.current_record)
                                writer.writerow(row)
                                success_count += 1
                            else:
                                self.log(f"Record not returned in batch: {mms_id}", logging.WARNING)
                                failed_count += 1
                            
                            # Update progress
                            if progress_callback:
                                progress_callback(record_index, total)
                            
                            if record_index % 50 == 0:
                                self.log(f"Exported {record_index}/{total} records")
                                
                        except Exception as e:
                            self.log(f"Error exporting {mms_id}: {str(e)}", logging.ERROR)
                            failed_count += 1
                
                message = f"CSV export complete: {success_count} succeeded, {failed_count} failed. File: {output_file}"
                self.log(message)
                self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
                return True, message
                
        except Exception as e:
            error_msg = f"Error creating CSV file: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg
    
    def _extract_dc_field(self, element: str, namespace: str = "dc") -> list:
        """Extract data from Dublin Core XML in the anies field"""
        try:
            anies = self.current_record.get("anies", [])
            if not anies:
                return []
            
            dc_xml = anies[0] if isinstance(anies, list) else anies
            root = ET.fromstring(dc_xml)
            
            namespaces = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/'
            }
            
            values = []
            tag = f"{{{namespaces[namespace]}}}{element}"
            for elem in root.findall(f".//{tag}"):
                if elem.text and elem.text.strip():
                    values.append(elem.text.strip())
            
            return values
        except Exception as e:
            self.log(f"Error extracting DC field {namespace}:{element}: {str(e)}", logging.WARNING)
            return []
    
    def _extract_custom_field(self, element: str, namespace_uri: str) -> list:
        """Extract data from custom namespace fields"""
        try:
            anies = self.current_record.get("anies", [])
            if not anies:
                return []
            
            dc_xml = anies[0] if isinstance(anies, list) else anies
            root = ET.fromstring(dc_xml)
            
            values = []
            tag = f"{{{namespace_uri}}}{element}"
            for elem in root.findall(f".//{tag}"):
                if elem.text and elem.text.strip():
                    values.append(elem.text.strip())
            
            return values
        except Exception as e:
            self.log(f"Error extracting custom field {element}: {str(e)}", logging.WARNING)
            return []
    
    def _map_bib_to_csv_row(self, bib: dict) -> dict:
        """Map a bibliographic record to a CSV row using Dublin Core fields"""
        column_headings = [
            "group_id", "collection_id", "mms_id", "originating_system_id", "compoundrelationship",
            "dc:title", "dcterms:alternative", "oldalttitle", "dc:identifier",
            "dcterms:identifier.dcterms:URI", "dcterms:tableOfContents", "dc:creator",
            "dc:contributor", "dc:subject", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dcterms:subject.dcterms:LCSH",
            "dcterms:subject.dcterms:LCSH", "dc:description", "dcterms:provenance",
            "dcterms:bibliographicCitation", "dcterms:abstract", "dcterms:publisher",
            "dcterms:publisher", "dc:date", "dcterms:created", "dcterms:issued",
            "dcterms:dateSubmitted", "dcterms:dateAccepted", "dc:type", "dc:format",
            "dcterms:extent", "dcterms:extent", "dcterms:medium",
            "dcterms:format.dcterms:IMT", "dcterms:type.dcterms:DCMIType", "dc:language",
            "dc:relation", "dcterms:isPartOf", "dcterms:isPartOf", "dcterms:isPartOf",
            "dc:coverage", "dcterms:spatial", "dcterms:spatial.dcterms:Point",
            "dcterms:temporal", "dc:rights", "dc:source", "bib custom field",
            "rep_label", "rep_public_note", "rep_access_rights", "rep_usage_type",
            "rep_library", "rep_note", "rep_custom field", "file_name_1", "file_label_1",
            "file_name_2", "file_label_2", "googlesheetsource", "dginfo"
        ]
        
        row = {heading: "" for heading in column_headings}
        
        # Custom namespace URI
        grinnell_ns = f"http://alma.exlibrisgroup.com/dc/{bib.get('originating_system', '01GCL_INST')}"
        
        # Basic metadata
        row["mms_id"] = bib.get("mms_id", "")
        row["originating_system_id"] = bib.get("originating_system_id", "")
        
        # Extract Dublin Core fields
        titles = self._extract_dc_field("title", "dc")
        row["dc:title"] = titles[0] if titles else bib.get("title", "")
        
        alt_titles = self._extract_dc_field("alternative", "dcterms")
        row["dcterms:alternative"] = "; ".join(alt_titles) if alt_titles else ""
        
        identifiers = self._extract_dc_field("identifier", "dc")
        row["dc:identifier"] = "; ".join(identifiers) if identifiers else ""
        
        for identifier in identifiers:
            if identifier.startswith("http://") or identifier.startswith("https://"):
                row["dcterms:identifier.dcterms:URI"] = identifier
                break
        
        toc = self._extract_dc_field("tableOfContents", "dcterms")
        row["dcterms:tableOfContents"] = "; ".join(toc) if toc else ""
        
        creators = self._extract_dc_field("creator", "dc")
        row["dc:creator"] = "; ".join(creators) if creators else bib.get("author", "")
        
        contributors = self._extract_dc_field("contributor", "dc")
        row["dc:contributor"] = "; ".join(contributors) if contributors else ""
        
        subjects = self._extract_dc_field("subject", "dc") + self._extract_dc_field("subject", "dcterms")
        if subjects:
            row["dc:subject"] = subjects[0]
        
        descriptions = self._extract_dc_field("description", "dc")
        row["dc:description"] = "; ".join(descriptions) if descriptions else ""
        
        provenance = self._extract_dc_field("provenance", "dcterms")
        row["dcterms:provenance"] = "; ".join(provenance) if provenance else ""
        
        citation = self._extract_dc_field("bibliographicCitation", "dcterms")
        row["dcterms:bibliographicCitation"] = "; ".join(citation) if citation else ""
        
        abstract = self._extract_dc_field("abstract", "dcterms")
        row["dcterms:abstract"] = "; ".join(abstract) if abstract else ""
        
        publishers = self._extract_dc_field("publisher", "dcterms")
        if publishers:
            row["dcterms:publisher"] = publishers[0]
        
        dates = self._extract_dc_field("date", "dc")
        row["dc:date"] = dates[0] if dates else bib.get("date_of_publication", "")
        
        created = self._extract_dc_field("created", "dcterms")
        row["dcterms:created"] = created[0] if created else ""
        
        issued = self._extract_dc_field("issued", "dcterms")
        row["dcterms:issued"] = issued[0] if issued else ""
        
        submitted = self._extract_dc_field("dateSubmitted", "dcterms")
        row["dcterms:dateSubmitted"] = submitted[0] if submitted else ""
        
        accepted = self._extract_dc_field("dateAccepted", "dcterms")
        row["dcterms:dateAccepted"] = accepted[0] if accepted else ""
        
        types = self._extract_dc_field("type", "dc")
        row["dc:type"] = types[0] if types else ""
        
        formats = self._extract_dc_field("format", "dc")
        row["dc:format"] = formats[0] if formats else ""
        
        extents = self._extract_dc_field("extent", "dcterms")
        if extents:
            row["dcterms:extent"] = extents[0]
        
        medium = self._extract_dc_field("medium", "dcterms")
        row["dcterms:medium"] = medium[0] if medium else ""
        
        languages = self._extract_dc_field("language", "dc")
        row["dc:language"] = "; ".join(languages) if languages else ""
        
        relations = self._extract_dc_field("relation", "dc")
        row["dc:relation"] = "; ".join(relations) if relations else ""
        
        ispartof = self._extract_dc_field("isPartOf", "dcterms")
        if ispartof:
            row["dcterms:isPartOf"] = ispartof[0]
        
        coverage = self._extract_dc_field("coverage", "dc")
        row["dc:coverage"] = "; ".join(coverage) if coverage else ""
        
        spatial = self._extract_dc_field("spatial", "dcterms")
        row["dcterms:spatial"] = "; ".join(spatial) if spatial else ""
        
        temporal = self._extract_dc_field("temporal", "dcterms")
        row["dcterms:temporal"] = "; ".join(temporal) if temporal else ""
        
        rights = self._extract_dc_field("rights", "dc")
        row["dc:rights"] = "; ".join(rights) if rights else ""
        
        sources = self._extract_dc_field("source", "dc")
        row["dc:source"] = "; ".join(sources) if sources else ""
        
        # Custom fields
        compound = self._extract_custom_field("compoundrelationship", grinnell_ns)
        row["compoundrelationship"] = compound[0] if compound else ""
        
        sheets = self._extract_custom_field("googlesheetsource", grinnell_ns)
        row["googlesheetsource"] = sheets[0] if sheets else ""
        
        dginfo = self._extract_custom_field("dginfo", grinnell_ns)
        row["dginfo"] = dginfo[0] if dginfo else ""
        
        return row
    
    def placeholder_function_4(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 4: Placeholder for future Alma-Digital record editing function
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Executing placeholder_function_4 for MMS ID: {mms_id}")
        return True, f"Placeholder Function 4 executed for record {mms_id}"
    
    def placeholder_function_5(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 5: Placeholder for future Alma-Digital record editing function
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Executing placeholder_function_5 for MMS ID: {mms_id}")
        return True, f"Placeholder Function 5 executed for record {mms_id}"


def main(page: ft.Page):
    """Main Flet application"""
    logger.info("Starting Flet application")
    page.title = "🚕 CABB - Clean Alma Bibs in Bulk"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    
    # Set window size - try both properties
    page.window.height = 1000
    page.window.width = 750
    page.window.resizable = True
    
    page.scroll = ft.ScrollMode.AUTO  # Enable vertical scrolling if needed
    
    # Log display list
    log_messages = []
    
    # UI Components
    status_text = ft.Text("", color=ft.Colors.BLUE)
    
    # Log output window - scrollable ListView with 5 lines visible
    log_output = ft.ListView(
        spacing=2,
        padding=10,
        auto_scroll=True,
        height=120,  # Approximately 5 lines
    )
    
    def add_log_message(message: str):
        """Add a message to the log output window"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        log_messages.append(log_msg)
        log_output.controls.append(
            ft.Text(log_msg, size=11, color=ft.Colors.GREY_800)
        )
        # Keep only last 100 messages to prevent memory issues
        if len(log_messages) > 100:
            log_messages.pop(0)
            log_output.controls.pop(0)
        page.update()
    
    # Initialize editor with log callback
    editor = AlmaBibEditor(log_callback=add_log_message)
    
    add_log_message("Application started")
    add_log_message(f"Log file: {log_filename}")
    
    # Input fields
    mms_id_input = ft.TextField(
        label="MMS ID",
        hint_text="Enter bibliographic record MMS ID",
        width=400
    )
    
    set_id_input = ft.TextField(
        label="Set ID",
        hint_text="Enter Alma Set ID",
        width=300
    )
    
    limit_input = ft.TextField(
        label="Limit",
        hint_text="Max records to process",
        value="0",
        width=100,
        keyboard_type=ft.KeyboardType.NUMBER,
        tooltip="Enter 0 for no limit, or a number to process only first N records"
    )
    
    # Set members display
    set_info_text = ft.Text("No set loaded", size=12, color=ft.Colors.GREY_700)
    set_progress_text = ft.Text("", size=12, color=ft.Colors.BLUE_700, visible=False)
    set_progress_bar = ft.ProgressBar(
        width=400,
        visible=False,
        color=ft.Colors.BLUE,
        bgcolor=ft.Colors.GREY_300,
    )
    
    def update_status(message: str, is_error: bool = False):
        """Update status message"""
        status_text.value = message
        status_text.color = ft.Colors.RED if is_error else ft.Colors.GREEN
        add_log_message(f"Status: {message}")
        page.update()
    
    def copy_status_to_clipboard(e):
        """Copy status text to clipboard"""
        if status_text.value:
            page.set_clipboard(status_text.value)
            logger.info("Status copied to clipboard")
            add_log_message("Status copied to clipboard")
        else:
            add_log_message("No status to copy")
    
    def on_connect_click(e):
        """Handle connect button click"""
        logger.info("Connect button clicked")
        add_log_message("Attempting to connect to Alma API...")
        success, message = editor.initialize_alma_connection()
        update_status(message, not success)
    
    def on_load_set_click(e):
        """Handle Load Set button click"""
        logger.info("Load Set button clicked")
        if not set_id_input.value:
            update_status("Please enter a Set ID", True)
            return
        
        # Get limit value
        try:
            limit = int(limit_input.value) if limit_input.value else 0
            if limit < 0:
                limit = 0
        except ValueError:
            update_status("Invalid limit value - using 0 (no limit)", True)
            limit = 0
        
        add_log_message(f"Loading set: {set_id_input.value} (limit: {limit if limit > 0 else 'none'})")
        
        # Show indeterminate progress bar while fetching set details
        set_progress_bar.visible = True
        set_progress_text.visible = True
        set_progress_bar.value = None  # Indeterminate progress
        set_progress_text.value = "Fetching set details..."
        page.update()
        
        # Fetch set details
        success, message, set_data = editor.fetch_set_details(set_id_input.value)
        if not success:
            set_progress_bar.visible = False
            set_progress_text.visible = False
            update_status(message, True)
            return
        
        # Define progress callback to update the progress bar and text
        def update_progress(current, total):
            set_progress_bar.value = current / total
            set_progress_text.value = f"Loading members: {current} of {total}"
            page.update()
        
        # Fetch set members with progress updates
        success, member_msg, members = editor.fetch_set_members(
            set_id_input.value, 
            progress_callback=update_progress,
            max_members=limit
        )
        if not success:
            set_progress_bar.visible = False
            set_progress_text.visible = False
            update_status(member_msg, True)
            return
        
        # Update set info display
        set_name = set_data.get('name', 'Unknown')
        member_count = len(members)
        if limit > 0 and member_count >= limit:
            set_info_text.value = f"Set: {set_name} ({member_count} of {limit} members loaded - limited)"
        else:
            set_info_text.value = f"Set: {set_name} ({member_count} members)"
        
        # Hide progress bar after loading
        set_progress_bar.visible = False
        set_progress_text.visible = False
        
        page.update()
        update_status(f"Loaded set with {member_count} members", False)
    
    def on_clear_set_click(e):
        """Handle Clear Set button click"""
        logger.info("Clear Set button clicked")
        editor.set_members = []
        editor.set_info = None
        set_info_text.value = "No set loaded"
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        add_log_message("Set cleared")
        update_status("Set cleared", False)
    
    def on_kill_switch_click(e):
        """Handle Kill Switch button click - emergency stop for batch operations"""
        logger.warning("KILL SWITCH ACTIVATED")
        editor.kill_switch = True
        add_log_message("⚠️ KILL SWITCH ACTIVATED - Stopping batch operation")
        update_status("⚠️ Kill switch activated - stopping after current record", True)
    
    def on_function_1_click(e):
        """Handle Function 1: Fetch and display XML"""
        logger.info("Function 1 button clicked")
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        add_log_message(f"Fetching XML for MMS ID: {mms_id_input.value}")
        success, message = editor.fetch_and_display_xml(mms_id_input.value, page)
        update_status(message, not success)
        update_status(message, not success)
    
    def on_function_2_click(e):
        """Handle Function 2: Clear dc:relation collections"""
        logger.info("Function 2 button clicked")
        
        # Determine if processing single record or batch
        if editor.set_members:
            # Batch processing
            member_count = len(editor.set_members)
            
            # Get limit value
            try:
                limit = int(limit_input.value) if limit_input.value else 0
            except ValueError:
                update_status("Invalid limit value - must be a whole number", True)
                return
            
            # Apply limit if set
            members_to_process = editor.set_members
            if limit > 0 and limit < member_count:
                members_to_process = editor.set_members[:limit]
                add_log_message(f"Limiting batch to first {limit} of {member_count} records")
            
            process_count = len(members_to_process)
            add_log_message(f"Starting batch clear_dc_relation for {process_count} records from set")
            
            # Show progress bar
            set_progress_bar.visible = True
            set_progress_text.visible = True
            set_progress_bar.value = 0
            set_progress_text.value = f"Processing: 0 of {process_count}"
            page.update()
            
            # Reset kill switch before starting
            editor.kill_switch = False
            
            success_count = 0
            error_count = 0
            
            for idx, mms_id in enumerate(members_to_process, 1):
                # Check kill switch
                if editor.kill_switch:
                    add_log_message(f"⚠️ Batch operation stopped by kill switch at record {idx}/{process_count}")
                    set_progress_bar.visible = False
                    set_progress_text.visible = False
                    update_status(f"⚠️ STOPPED by kill switch: {success_count} succeeded, {error_count} failed, {process_count - idx + 1} skipped", True)
                    editor.kill_switch = False  # Reset for next operation
                    return
                
                add_log_message(f"Processing {idx}/{process_count}: {mms_id}")
                
                # Update progress bar and text
                set_progress_bar.value = idx / process_count
                set_progress_text.value = f"Processing: {idx} of {process_count}"
                update_status(f"Processing {idx}/{process_count}: {mms_id}", False)
                
                success, message = editor.clear_dc_relation_collections(mms_id)
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    add_log_message(f"ERROR on {mms_id}: {message}")
            
            # Hide progress bar
            set_progress_bar.visible = False
            set_progress_text.visible = False
            
            summary = f"Batch complete: {success_count} succeeded, {error_count} failed out of {process_count} records"
            if limit > 0 and limit < member_count:
                summary += f" (limited from {member_count} total)"
            update_status(summary, error_count > 0)
        else:
            # Single record processing
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            
            add_log_message(f"Starting clear_dc_relation for MMS ID: {mms_id_input.value}")
            success, message = editor.clear_dc_relation_collections(mms_id_input.value)
            update_status(message, not success)
    
    def on_function_3_click(e):
        """Handle Function 3 click - Export set to CSV"""
        logger.info("Function 3 button clicked - Export to CSV")
        
        # Check if set is loaded
        if not editor.set_members:
            update_status("Please load a set first", True)
            return
        
        # Generate output filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"alma_export_{timestamp}.csv"
        
        add_log_message(f"Exporting {len(editor.set_members)} records to CSV: {output_file}")
        
        # Show progress bar
        set_progress_bar.visible = True
        set_progress_bar.value = None  # Indeterminate mode
        set_progress_text.value = "Preparing export..."
        set_progress_text.visible = True
        page.update()
        
        def progress_callback(current, total):
            """Update progress during export"""
            set_progress_bar.value = current / total if total > 0 else None
            set_progress_text.value = f"Exported {current} of {total} records"
            page.update()
        
        # Export to CSV
        success, message = editor.export_to_csv(
            editor.set_members,
            output_file,
            progress_callback=progress_callback
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message(f"CSV export complete: {output_file}")
    
    def on_function_4_click(e):
        """Handle Function 4 click"""
        logger.info("Function 4 button clicked")
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        add_log_message(f"Executing Function 4 for MMS ID: {mms_id_input.value}")
        success, message = editor.placeholder_function_4(mms_id_input.value)
        update_status(message, not success)
    
    def on_function_5_click(e):
        """Handle Function 5 click"""
        logger.info("Function 5 button clicked")
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        add_log_message(f"Executing Function 5 for MMS ID: {mms_id_input.value}")
        success, message = editor.placeholder_function_5(mms_id_input.value)
        update_status(message, not success)
    
    # Build UI
    page.add(
        ft.Column([
            ft.Text("🚕 CABB - Clean Alma Bibs in Bulk", 
                   size=24, 
                   weight=ft.FontWeight.BOLD),
            ft.Divider(height=5),
            
            # Connection section
            ft.Container(
                content=ft.Column([
                    ft.Text("Connection", size=18, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton(
                        "Connect to Alma API",
                        on_click=on_connect_click,
                        icon=ft.Icons.CONNECT_WITHOUT_CONTACT
                    ),
                ], spacing=5),
                padding=5,
            ),
            
            ft.Divider(height=5),
            
            # Input section
            ft.Container(
                content=ft.Column([
                    ft.Text("Record Input", size=18, weight=ft.FontWeight.BOLD),
                    
                    # Single record input
                    ft.Text("Single Record:", size=14, weight=ft.FontWeight.W_500),
                    mms_id_input,
                    
                    ft.Divider(height=10),
                    
                    # Set input
                    ft.Text("Batch Processing (Set):", size=14, weight=ft.FontWeight.W_500),
                    ft.Row([
                        set_id_input,
                        limit_input,
                    ], spacing=10),
                    ft.Row([
                        ft.ElevatedButton(
                            "Load Set Members",
                            on_click=on_load_set_click,
                            icon=ft.Icons.DOWNLOAD
                        ),
                        ft.ElevatedButton(
                            "Clear Set",
                            on_click=on_clear_set_click,
                            icon=ft.Icons.CLEAR
                        ),
                        ft.ElevatedButton(
                            "🛑 Kill Switch",
                            on_click=on_kill_switch_click,
                            icon=ft.Icons.CANCEL,
                            color=ft.Colors.WHITE,
                            bgcolor=ft.Colors.RED_700,
                            tooltip="Emergency stop - halts batch processing immediately"
                        ),
                    ], spacing=10),
                    set_info_text,
                ], spacing=5),
                padding=5,
            ),
            
            ft.Divider(height=5),
            
            # Functions section
            ft.Container(
                content=ft.Column([
                    ft.Text("Editing Functions", size=18, weight=ft.FontWeight.BOLD),
                    
                    ft.ElevatedButton(
                        "1. Fetch and Display Single XML",
                        on_click=on_function_1_click,
                        icon=ft.Icons.PREVIEW,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "2. Clear dc:relation Collections Fields",
                        on_click=on_function_2_click,
                        icon=ft.Icons.CLEAR_ALL,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "3. Export Set to DCAP01 CSV",
                        on_click=on_function_3_click,
                        icon=ft.Icons.DOWNLOAD,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "4. Placeholder Function 4",
                        on_click=on_function_4_click,
                        icon=ft.Icons.EDIT,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "5. Placeholder Function 5",
                        on_click=on_function_5_click,
                        icon=ft.Icons.EDIT,
                        width=400
                    ),
                ], spacing=5),
                padding=5,
            ),
            
            ft.Divider(height=5),
            
            # Status section
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text("Status", size=18, weight=ft.FontWeight.BOLD),
                        ft.IconButton(
                            icon=ft.Icons.COPY,
                            tooltip="Copy status to clipboard",
                            on_click=copy_status_to_clipboard,
                            icon_size=20,
                        ),
                    ]),
                    status_text,
                    set_progress_text,
                    set_progress_bar,
                ], spacing=5),
                padding=5,
            ),
            
            ft.Divider(height=5),
            
            # Log output section
            ft.Container(
                content=ft.Column([
                    ft.Text("Log Output", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=log_output,
                        border=ft.border.all(1, ft.Colors.GREY_400),
                        border_radius=5,
                        bgcolor=ft.Colors.GREY_100,
                    ),
                ], spacing=5),
                padding=5,
            ),
        ])
    )
    
    logger.info("UI initialized successfully")


if __name__ == "__main__":
    logger.info("Application starting...")
    ft.app(
        target=main,
        assets_dir="assets",
        web_renderer=ft.WebRenderer.HTML
    )
