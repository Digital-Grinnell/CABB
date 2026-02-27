"""
Crunch Alma Bibs in Bulk (CABB)
A Flet UI app designed to perform various Alma-Digital bib record editing functions.
"""

import flet as ft
import os
import logging
import json
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import requests

# Load environment variables
load_dotenv()

# Configure logging
# Create logfiles directory if it doesn't exist
os.makedirs('logfiles', exist_ok=True)
log_filename = f"logfiles/cabb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

# Persistent storage file
PERSISTENCE_FILE = "persistent.json"


class PersistentStorage:
    """Handle persistent storage of UI state and function usage"""
    
    def __init__(self):
        self.data = self.load()
    
    def load(self) -> dict:
        """Load persistent data from file"""
        try:
            if os.path.exists(PERSISTENCE_FILE):
                with open(PERSISTENCE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"Loaded persistent data from {PERSISTENCE_FILE}")
                return data
        except Exception as e:
            logger.warning(f"Could not load persistent data: {str(e)}")
        
        # Return default structure
        return {
            "ui_state": {
                "mms_id": "",
                "set_id": "",
                "limit": "0"
            },
            "function_usage": {
                # Format: "function_name": {"last_used": "ISO timestamp", "count": N}
            }
        }
    
    def save(self):
        """Save persistent data to file"""
        try:
            with open(PERSISTENCE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved persistent data to {PERSISTENCE_FILE}")
        except Exception as e:
            logger.error(f"Could not save persistent data: {str(e)}")
    
    def set_ui_state(self, field: str, value: str):
        """Update UI state field"""
        self.data["ui_state"][field] = value
        self.save()
    
    def get_ui_state(self, field: str, default: str = "") -> str:
        """Get UI state field"""
        return self.data["ui_state"].get(field, default)
    
    def record_function_usage(self, function_name: str):
        """Record that a function was used"""
        if function_name not in self.data["function_usage"]:
            self.data["function_usage"][function_name] = {"count": 0}
        
        self.data["function_usage"][function_name]["last_used"] = datetime.now().isoformat()
        self.data["function_usage"][function_name]["count"] = self.data["function_usage"][function_name].get("count", 0) + 1
        self.save()
    
    def get_function_usage(self, function_name: str) -> dict:
        """Get usage stats for a function"""
        return self.data["function_usage"].get(function_name, {"last_used": None, "count": 0})
    
    def get_all_function_usage(self) -> dict:
        """Get all function usage stats"""
        return self.data["function_usage"]


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
        self.last_manifest = None  # Store last retrieved IIIF manifest
        self.last_manifest_url = None  # Store last manifest URL
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
    
    def load_mms_ids_from_csv(self, csv_file_path: str) -> tuple[bool, str, list]:
        """
        Load MMS IDs from a CSV file.
        
        The CSV file should have a column named 'mms_id' (case-insensitive).
        If no such column is found, assumes the first column contains MMS IDs.
        
        Args:
            csv_file_path: Path to the CSV file
            
        Returns:
            tuple: (success: bool, message: str, mms_ids: list)
        """
        import csv
        
        self.log(f"Loading MMS IDs from CSV: {csv_file_path}")
        
        try:
            mms_ids = []
            
            with open(csv_file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Find the mms_id column (case-insensitive)
                mms_id_column = None
                for fieldname in reader.fieldnames:
                    if fieldname.lower() == 'mms_id':
                        mms_id_column = fieldname
                        break
                
                if mms_id_column is None:
                    # Use first column if no mms_id column found
                    mms_id_column = reader.fieldnames[0]
                    self.log(f"No 'mms_id' column found, using first column: {mms_id_column}", logging.WARNING)
                
                # Read MMS IDs
                for row in reader:
                    mms_id = row.get(mms_id_column, '').strip()
                    if mms_id:
                        mms_ids.append(mms_id)
            
            self.set_members = mms_ids
            self.set_info = {'name': csv_file_path.split('/')[-1], 'source': 'CSV'}
            
            self.log(f"Loaded {len(mms_ids)} MMS IDs from CSV")
            return True, f"Loaded {len(mms_ids)} MMS IDs from CSV", mms_ids
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error loading CSV {csv_file_path}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error loading CSV: {str(e)}", []
    
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
        
        # Define CSV column headings (no duplicates)
        column_headings = [
            "group_id", "collection_id", "mms_id", "originating_system_id", "compoundrelationship",
            "dc:title", "dcterms:alternative", "oldalttitle", "dc:identifier",
            "dcterms:identifier.dcterms:URI", "dcterms:tableOfContents", "dc:creator",
            "dc:contributor", "dc:subject", "dcterms:subject.dcterms:LCSH",
            "dc:description", "dcterms:provenance",
            "dcterms:bibliographicCitation", "dcterms:abstract", "dcterms:publisher",
            "dc:date", "dcterms:created", "dcterms:issued",
            "dcterms:dateSubmitted", "dcterms:dateAccepted", "dc:type", "dc:format",
            "dcterms:extent", "dcterms:medium",
            "dcterms:format.dcterms:IMT", "dcterms:type.dcterms:DCMIType", "dc:language",
            "dc:relation", "dcterms:isPartOf",
            "dc:coverage", "dcterms:spatial", "dcterms:spatial.dcterms:Point",
            "dcterms:temporal", "dc:rights", "dc:source", "bib custom field",
            "rep_label", "rep_public_note", "rep_access_rights", "rep_usage_type",
            "rep_library", "rep_note", "rep_custom field", "file_name_1", "file_label_1",
            "file_name_2", "file_label_2", "googlesheetsource", "dginfo"
        ]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(column_headings)  # Write header
                
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
                                
                                # Map record to CSV row (returns list)
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
    
    def _extract_lcsh_subjects(self) -> list:
        """Extract LCSH subjects (dcterms:subject with xsi:type='dcterms:LCSH')"""
        try:
            anies = self.current_record.get("anies", [])
            if not anies:
                return []
            
            dc_xml = anies[0] if isinstance(anies, list) else anies
            root = ET.fromstring(dc_xml)
            
            namespaces = {
                'dcterms': 'http://purl.org/dc/terms/',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
            }
            
            values = []
            # Find all dcterms:subject elements
            for elem in root.findall(".//{{{}}}subject".format(namespaces['dcterms'])):
                # Check if it has xsi:type="dcterms:LCSH" attribute
                xsi_type = elem.get("{{{0}}}type".format(namespaces['xsi']))
                if xsi_type == "dcterms:LCSH" and elem.text and elem.text.strip():
                    values.append(elem.text.strip())
            
            return values
        except Exception as e:
            self.log(f"Error extracting LCSH subjects: {str(e)}", logging.WARNING)
            return []
    
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
        """Extract data from custom namespace fields (tries both namespaced and unprefixed)"""
        try:
            anies = self.current_record.get("anies", [])
            if not anies:
                return []
            
            dc_xml = anies[0] if isinstance(anies, list) else anies
            root = ET.fromstring(dc_xml)
            
            values = []
            # Try namespaced version first
            tag = f"{{{namespace_uri}}}{element}"
            for elem in root.findall(f".//{tag}"):
                if elem.text and elem.text.strip():
                    values.append(elem.text.strip())
            
            # If no namespaced elements found, try unprefixed (for dginfo, compoundrelationship, etc.)
            if not values:
                for elem in root.findall(f".//{element}"):
                    if elem.text and elem.text.strip():
                        values.append(elem.text.strip())
            
            return values
        except Exception as e:
            self.log(f"Error extracting custom field {element}: {str(e)}", logging.WARNING)
            return []
    
    def _deduplicate_values(self, values: list) -> list:
        """Remove duplicate values from a list while preserving order"""
        seen = set()
        result = []
        for value in values:
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result
    
    def _map_bib_to_csv_row(self, bib: dict) -> list:
        """Map a bibliographic record to a CSV row using Dublin Core fields
        Returns a list of values in the same order as column_headings
        Multi-valued fields are joined with ' | ' separator"""
        
        # Extract the actual namespace from the XML record
        grinnell_ns = "http://alma.exlibrisgroup.com/dc/01GCL_INST"  # Default
        try:
            anies = bib.get("anies", [])
            if anies:
                dc_xml = anies[0] if isinstance(anies, list) else anies
                # Extract namespace from root element
                import re
                ns_match = re.search(r'xmlns="([^"]+)"', dc_xml)
                if ns_match:
                    grinnell_ns = ns_match.group(1)
        except Exception as e:
            self.log(f"Could not extract namespace from XML: {str(e)}", logging.DEBUG)
        
        # Build row as list - must match column_headings order exactly
        row = []
        
        # Basic metadata
        row.append("")  # group_id
        row.append("")  # collection_id
        row.append(bib.get("mms_id", ""))  # mms_id
        row.append(bib.get("originating_system_id", ""))  # originating_system_id
        
        # compoundrelationship (custom field)
        compound = self._extract_custom_field("compoundrelationship", grinnell_ns)
        row.append(compound[0] if compound else "")
        
        # Extract Dublin Core fields
        titles = self._extract_dc_field("title", "dc")
        row.append(titles[0] if titles else bib.get("title", ""))  # dc:title
        
        alt_titles = self._extract_dc_field("alternative", "dcterms")
        row.append(" | ".join(self._deduplicate_values(alt_titles)) if alt_titles else "")  # dcterms:alternative
        
        row.append("")  # oldalttitle
        
        identifiers = self._extract_dc_field("identifier", "dc")
        row.append(" | ".join(self._deduplicate_values(identifiers)) if identifiers else "")  # dc:identifier
        
        # dcterms:identifier.dcterms:URI - extract URI from identifiers
        uri = ""
        for identifier in identifiers:
            if identifier.startswith("http://") or identifier.startswith("https://"):
                uri = identifier
                break
        row.append(uri)
        
        toc = self._extract_dc_field("tableOfContents", "dcterms")
        row.append(" | ".join(self._deduplicate_values(toc)) if toc else "")  # dcterms:tableOfContents
        
        creators = self._extract_dc_field("creator", "dc")
        row.append(" | ".join(self._deduplicate_values(creators)) if creators else bib.get("author", ""))  # dc:creator
        
        contributors = self._extract_dc_field("contributor", "dc")
        row.append(" | ".join(self._deduplicate_values(contributors)) if contributors else "")  # dc:contributor
        
        # dc:subject - all dc:subject values joined with pipe separator
        dc_subjects = self._extract_dc_field("subject", "dc")
        row.append(" | ".join(self._deduplicate_values(dc_subjects)) if dc_subjects else "")
        
        # Extract LCSH subjects - all joined in single column
        lcsh_subjects = self._extract_lcsh_subjects()
        row.append(" | ".join(self._deduplicate_values(lcsh_subjects)) if lcsh_subjects else "")
        
        descriptions = self._extract_dc_field("description", "dc")
        row.append(" | ".join(self._deduplicate_values(descriptions)) if descriptions else "")  # dc:description
        
        provenance = self._extract_dc_field("provenance", "dcterms")
        row.append(" | ".join(self._deduplicate_values(provenance)) if provenance else "")  # dcterms:provenance
        
        citation = self._extract_dc_field("bibliographicCitation", "dcterms")
        row.append(" | ".join(self._deduplicate_values(citation)) if citation else "")  # dcterms:bibliographicCitation
        
        abstract = self._extract_dc_field("abstract", "dcterms")
        row.append(" | ".join(self._deduplicate_values(abstract)) if abstract else "")  # dcterms:abstract
        
        # dcterms:publisher - all values joined
        publishers = self._extract_dc_field("publisher", "dcterms")
        row.append(" | ".join(self._deduplicate_values(publishers)) if publishers else "")
        
        dates = self._extract_dc_field("date", "dc")
        row.append(dates[0] if dates else bib.get("date_of_publication", ""))  # dc:date
        
        created = self._extract_dc_field("created", "dcterms")
        row.append(created[0] if created else "")  # dcterms:created
        
        issued = self._extract_dc_field("issued", "dcterms")
        row.append(issued[0] if issued else "")  # dcterms:issued
        
        submitted = self._extract_dc_field("dateSubmitted", "dcterms")
        row.append(submitted[0] if submitted else "")  # dcterms:dateSubmitted
        
        accepted = self._extract_dc_field("dateAccepted", "dcterms")
        row.append(accepted[0] if accepted else "")  # dcterms:dateAccepted
        
        types = self._extract_dc_field("type", "dc")
        row.append(types[0] if types else "")  # dc:type
        
        formats = self._extract_dc_field("format", "dc")
        row.append(formats[0] if formats else "")  # dc:format
        
        # dcterms:extent - all values joined
        extents = self._extract_dc_field("extent", "dcterms")
        row.append(" | ".join(self._deduplicate_values(extents)) if extents else "")
        
        medium = self._extract_dc_field("medium", "dcterms")
        row.append(medium[0] if medium else "")  # dcterms:medium
        
        # dcterms:format.dcterms:IMT
        imt_formats = self._extract_dc_field("format", "dcterms")
        row.append(imt_formats[0] if imt_formats else "")
        
        # dcterms:type.dcterms:DCMIType  
        dcmi_types = self._extract_dc_field("type", "dcterms")
        row.append(dcmi_types[0] if dcmi_types else "")
        
        languages = self._extract_dc_field("language", "dc")
        row.append(" | ".join(self._deduplicate_values(languages)) if languages else "")  # dc:language
        
        relations = self._extract_dc_field("relation", "dc")
        row.append(" | ".join(self._deduplicate_values(relations)) if relations else "")  # dc:relation
        
        # dcterms:isPartOf - all values joined
        ispartof = self._extract_dc_field("isPartOf", "dcterms")
        row.append(" | ".join(self._deduplicate_values(ispartof)) if ispartof else "")
        
        coverage = self._extract_dc_field("coverage", "dc")
        row.append(" | ".join(self._deduplicate_values(coverage)) if coverage else "")  # dc:coverage
        
        spatial = self._extract_dc_field("spatial", "dcterms")
        row.append(" | ".join(self._deduplicate_values(spatial)) if spatial else "")  # dcterms:spatial
        
        row.append("")  # dcterms:spatial.dcterms:Point
        
        temporal = self._extract_dc_field("temporal", "dcterms")
        row.append(" | ".join(self._deduplicate_values(temporal)) if temporal else "")  # dcterms:temporal
        
        rights = self._extract_dc_field("rights", "dc")
        row.append(" | ".join(self._deduplicate_values(rights)) if rights else "")  # dc:rights
        
        sources = self._extract_dc_field("source", "dc")
        row.append(" | ".join(self._deduplicate_values(sources)) if sources else "")  # dc:source
        
        row.append("")  # bib custom field
        
        # Representation fields (placeholders)
        row.append("")  # rep_label
        row.append("")  # rep_public_note
        row.append("")  # rep_access_rights
        row.append("")  # rep_usage_type
        row.append("")  # rep_library
        row.append("")  # rep_note
        row.append("")  # rep_custom field
        
        # File fields (placeholders)
        row.append("")  # file_name_1
        row.append("")  # file_label_1
        row.append("")  # file_name_2
        row.append("")  # file_label_2
        
        # Custom fields
        sheets = self._extract_custom_field("googlesheetsource", grinnell_ns)
        row.append(sheets[0] if sheets else "")  # googlesheetsource
        
        dginfo = self._extract_custom_field("dginfo", grinnell_ns)
        row.append(dginfo[0] if dginfo else "")  # dginfo
        
        return row
    
    def filter_csv_by_pre1930_dates(self, input_file: str = None, output_file: str = None) -> tuple[bool, str]:
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
        
        self.log(f"Starting CSV filter for records 95+ years old (cutoff year: {cutoff_year})")
        
        try:
            # Find most recent alma_export_*.csv if not specified
            if input_file is None:
                csv_files = glob.glob("alma_export_*.csv")
                if not csv_files:
                    return False, "No alma_export_*.csv files found"
                input_file = max(csv_files, key=lambda f: f)
                self.log(f"Using input file: {input_file}")
            
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
            self.log(message)
            return True, message
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error filtering CSV: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error filtering CSV: {str(e)}"
    
    def get_iiif_manifest_and_canvas(self, mms_id: str, representation_id: str = None) -> tuple[bool, str]:
        """
        Function 5: Retrieve IIIF manifest and canvas for a digital object
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            representation_id: Optional representation ID. If not provided, uses first available.
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Retrieving IIIF manifest for MMS ID: {mms_id}")
        
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured"
        
        try:
            api_url = self._get_alma_api_url()
            
            # Step 1: Get representations if representation_id not provided
            if not representation_id:
                self.log("Fetching representations list")
                response = requests.get(
                    f"{api_url}/almaws/v1/bibs/{mms_id}/representations?apikey={self.api_key}",
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code != 200:
                    self.log(f"Failed to fetch representations: {response.status_code}", logging.ERROR)
                    return False, f"Failed to fetch representations: {response.status_code}"
                
                reps_data = response.json()
                representations = reps_data.get('representation', [])
                
                if not representations:
                    return False, "No digital representations found for this record"
                
                # Use first representation (lowest ID derivative, or first master, or first remote)
                representation_id = representations[0].get('id')
                self.log(f"Using first representation: {representation_id}")
            
            # Step 2: Get IIIF manifest URL
            # According to Alma documentation, IIIF manifest URLs follow this pattern:
            # - Regional instances: https://{region}.alma.exlibrisgroup.com/view/iiif/presentation/{INST_CODE}/{REP_ID}/manifest
            # - Custom domain: https://{domain}.alma.exlibrisgroup.com/view/iiif/presentation/{REP_ID}/manifest
            # Note: The region domain (na01, eu01, etc.) differs from the API domain
            
            alma_domain = self._get_alma_domain()
            institution_code = self._get_institution_code()
            
            # Construct URL based on whether we have institution code
            if institution_code:
                # Regional/sandbox instance - institution code in path
                manifest_url = f"https://{alma_domain}.alma.exlibrisgroup.com/view/iiif/presentation/{institution_code}/{representation_id}/manifest"
            else:
                # Custom domain instance
                manifest_url = f"https://{alma_domain}.alma.exlibrisgroup.com/view/iiif/presentation/{representation_id}/manifest"
            
            self.log(f"IIIF Manifest URL: {manifest_url}")
            
            # Step 3: Fetch the manifest (no authentication needed for public IIIF)
            manifest_response = requests.get(manifest_url)
            
            if manifest_response.status_code != 200:
                self.log(f"Failed to fetch IIIF manifest: {manifest_response.status_code}", logging.ERROR)
                self.log(f"Response headers: {manifest_response.headers}", logging.DEBUG)
                self.log(f"Response text: {manifest_response.text[:500]}", logging.DEBUG)
                
                # IIIF manifest might not be available - try getting delivery JSON instead
                self.log("Attempting alternative: delivery JSON endpoint", logging.INFO)
                delivery_url = f"https://{alma_domain}.alma.exlibrisgroup.com/view/delivery/{representation_id}.json"
                if institution_code:
                    delivery_url = f"https://{alma_domain}.alma.exlibrisgroup.com/view/delivery/{institution_code}/{representation_id}.json"
                
                delivery_response = requests.get(
                    delivery_url,
                    headers={'Accept': 'application/json'}
                )
                
                if delivery_response.status_code == 200:
                    delivery_data = delivery_response.json()
                    
                    result = f"Retrieved delivery information (IIIF manifest not available):\\n\\n"
                    result += f"Representation ID: {representation_id}\\n"
                    result += f"Delivery URL: {delivery_url}\\n"
                    result += f"Label: {delivery_data.get('label', 'N/A')}\\n"
                    
                    # Extract file/canvas information from delivery JSON
                    files = delivery_data.get('files', [])
                    result += f"Number of files: {len(files)}\\n\\n"
                    
                    if files:
                        result += "Files:\\n"
                        for i, file in enumerate(files[:10], 1):
                            label = file.get('label', f'File {i}')
                            path = file.get('path', 'N/A')
                            result += f"  {i}. {label}\\n     Path: {path}\\n"
                        
                        if len(files) > 10:
                            result += f"  ... and {len(files) - 10} more files\\n"
                    
                    self.log("Retrieved delivery JSON successfully")
                    return True, result
                
                # If delivery JSON also fails, try representation files API
                self.log("Attempting to retrieve representation files for canvas URLs", logging.INFO)
                api_url = self._get_alma_api_url()
                files_response = requests.get(
                    f"{api_url}/almaws/v1/bibs/{mms_id}/representations/{representation_id}/files?apikey={self.api_key}",
                    headers={'Accept': 'application/json'}
                )
                
                if files_response.status_code == 200:
                    files_data = files_response.json()
                    files = files_data.get('representation_file', [])
                    
                    result = f"Retrieved representation file information:\\n\\n"
                    result += f"Representation ID: {representation_id}\\n"
                    result += f"Number of files: {len(files)}\\n"
                    result += f"Note: IIIF manifest and delivery JSON not accessible\\n\\n"
                    
                    if files:
                        result += "Files (with potential canvas URLs):\\n"
                        for i, file in enumerate(files[:10], 1):
                            file_id = file.get('id', 'N/A')
                            label = file.get('label', f'File {i}')
                            path = file.get('path', 'N/A')
                            # Canvas URL format (may not work if IIIF not enabled)
                            canvas_url = f"https://{alma_domain}.alma.exlibrisgroup.com/view/iiif/presentation/{representation_id}/canvas/{file_id}"
                            if institution_code:
                                canvas_url = f"https://{alma_domain}.alma.exlibrisgroup.com/view/iiif/presentation/{institution_code}/{representation_id}/canvas/{file_id}"
                            result += f"  {i}. {label}\\n"
                            result += f"     File ID: {file_id}\\n"
                            result += f"     Path: {path}\\n"
                            result += f"     Canvas URL: {canvas_url}\\n"
                        
                        if len(files) > 10:
                            result += f"  ... and {len(files) - 10} more files\\n"
                    
                    self.log("Retrieved file information successfully")
                    return True, result
                else:
                    return False, f"Failed to fetch IIIF manifest (HTTP {manifest_response.status_code}), delivery JSON, and representation files"
            
            manifest_data = manifest_response.json()
            
            # Step 4: Extract canvas information
            sequences = manifest_data.get('sequences', [])
            canvases = []
            
            if sequences:
                canvases = sequences[0].get('canvases', [])
            
            # Build result message
            result = f"IIIF Manifest retrieved successfully\n\n"
            result += f"Representation ID: {representation_id}\n"
            result += f"Manifest URL: {manifest_url}\n"
            result += f"Label: {manifest_data.get('label', 'N/A')}\n"
            result += f"Number of canvases: {len(canvases)}\n\n"
            
            # List canvas details
            if canvases:
                result += "Canvases:\n"
                for i, canvas in enumerate(canvases[:10], 1):  # Limit to first 10
                    canvas_id = canvas.get('@id', 'N/A')
                    canvas_label = canvas.get('label', f'Canvas {i}')
                    result += f"  {i}. {canvas_label}\n     {canvas_id}\n"
                
                if len(canvases) > 10:
                    result += f"  ... and {len(canvases) - 10} more canvases\n"
            
            # Store manifest data for potential use
            self.last_manifest = manifest_data
            self.last_manifest_url = manifest_url
            
            self.log("IIIF manifest retrieved successfully")
            return True, result
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error retrieving IIIF manifest: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error retrieving IIIF manifest: {str(e)}"
    
    def replace_author_copyright_rights(self, mms_id: str) -> tuple[bool, str, str]:
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
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str, outcome: str)
                outcome can be: 'replaced', 'added', 'removed_duplicates', 'no_change', 'error'
        """
        self.log(f"Starting replace_author_copyright_rights for MMS ID: {mms_id}")
        if not self.api_key:
            self.log("API Key not configured", logging.ERROR)
            return False, "API Key not configured", "error"
        
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
                return False, f"Failed to fetch record: {response.status_code}", "error"
            
            # Step 2: Parse the XML response
            self.log("Parsing XML response")
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
            
            self.log("Registered namespaces: dc, dcterms, xsi, xml")
            
            # Step 3: Find dc:rights elements
            search_namespaces = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/'
            }
            rights_elements = root.findall('.//dc:rights', search_namespaces)
            self.log(f"Found {len(rights_elements)} dc:rights elements")
            
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
                        self.log(f"Rights statement URL with target already exists")
                    elif rights_elem.text.startswith(pattern_start):
                        author_copyright_elements.append(rights_elem)
                        self.log(f"Found author copyright field: {rights_elem.text[:80]}...")
                    elif rights_elem.text.startswith(grinnell_pattern_start):
                        grinnell_copyright_elements.append(rights_elem)
                        self.log(f"Found Grinnell copyright field: {rights_elem.text[:80]}...")
                    elif url_pattern in rights_elem.text and 'target="_blank"' not in rights_elem.text:
                        # Found old link without target attribute
                        old_link_elements.append(rights_elem)
                        self.log(f"Found old link without target: {rights_elem.text[:80]}...")
            
            # If URL with target already exists, remove any author copyright fields, grinnell copyright fields, and old links
            if url_exists:
                elements_to_remove = author_copyright_elements + grinnell_copyright_elements + old_link_elements
                if elements_to_remove:
                    self.log(f"URL exists, removing {len(elements_to_remove)} old field(s)")
                    for rights_elem in elements_to_remove:
                        # Find parent and remove the element
                        for parent in root.iter():
                            if rights_elem in list(parent):
                                parent.remove(rights_elem)
                                self.log(f"Removed: {rights_elem.text[:80]}...")
                                break
                    
                    changes_made = len(elements_to_remove)
                    outcome = "removed_duplicates"
                else:
                    self.log("URL exists and no old fields to remove")
                    return True, "Rights statement URL already exists, no changes needed", "no_change"
            else:
                # URL doesn't exist, replace author copyright fields, grinnell copyright fields, or old links OR add new element
                elements_to_replace = author_copyright_elements + grinnell_copyright_elements + old_link_elements
                if not elements_to_replace:
                    # No dc:rights elements exist, add a new one
                    if len(rights_elements) == 0:
                        warning_msg = f"WARNING: Record {mms_id} has NO dc:rights element - adding Public Domain rights statement"
                        self.log(warning_msg, logging.WARNING)
                        self.log("No dc:rights elements found, adding new Public Domain rights element")
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
                                        self.log(f"Found DC parent element via dc:{tag}")
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
                                    self.log("Found DC parent element via anies/any")
                        
                        if dc_parent is not None:
                            # Create new dc:rights element
                            new_rights_elem = ET.Element('{http://purl.org/dc/elements/1.1/}rights')
                            new_rights_elem.text = new_value
                            dc_parent.append(new_rights_elem)
                            self.log(f"Added new dc:rights element: {new_value}")
                            changes_made = 1
                            outcome = "added"
                        else:
                            self.log("Could not find parent element to add dc:rights", logging.ERROR)
                            return False, "Could not find parent element to add dc:rights", "error"
                    else:
                        self.log("No matching dc:rights fields found")
                        return True, "No matching dc:rights fields found", "no_change"
                
                else:
                    # Replace first matching element with new value
                    first_elem = elements_to_replace[0]
                    first_elem.text = new_value
                    self.log(f"Replaced first old field with new URL")
                    
                    # Remove any additional fields (duplicates)
                    for rights_elem in elements_to_replace[1:]:
                        for parent in root.iter():
                            if rights_elem in list(parent):
                                parent.remove(rights_elem)
                                self.log(f"Removed duplicate: {rights_elem.text[:80]}...")
                                break
                    
                    changes_made = len(elements_to_replace)
                    outcome = "replaced"
            
            # Step 4: Convert the modified tree back to XML bytes
            self.log(f"Modified {changes_made} dc:rights field(s), preparing to update")
            xml_bytes = ET.tostring(root, encoding='utf-8')
            
            # Convert to string and fix namespace prefixes
            xml_str = xml_bytes.decode('utf-8')
            # Remove ns0: prefix from element names
            xml_str = xml_str.replace('ns0:', '').replace(':ns0', '')
            # Remove the xmlns declaration for the Alma namespace
            xml_str = xml_str.replace(' xmlns="http://alma.exlibrisgroup.com/dc/01GCL_INST"', '')
            xml_bytes = xml_str.encode('utf-8')
            
            # Log a sample of the XML being sent
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
                return False, f"Failed to update record: {response.status_code}", "error"
            
            self.log(f"Successfully updated record {mms_id}")
            
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
            self.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error processing record {mms_id}: {str(e)}", "error"
    
    def add_grinnell_identifier(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 7: Add Grinnell: dc:identifier field as needed
        
        Finds records with dc:identifier starting with "dg_" and adds a corresponding
        "Grinnell:<number>" dc:identifier if one doesn't already exist.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Starting add_grinnell_identifier for MMS ID: {mms_id}")
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
            
            # Register namespaces
            namespaces_to_register = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
            }
            for prefix, uri in namespaces_to_register.items():
                ET.register_namespace(prefix, uri)
            
            self.log("Registered namespaces: dc, dcterms, xsi")
            
            # Step 3: Find dc:identifier elements
            search_namespaces = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/'
            }
            identifier_elements = root.findall('.//dc:identifier', search_namespaces)
            self.log(f"Found {len(identifier_elements)} dc:identifier elements")
            
            # Step 4: Check for existing identifiers
            dg_identifier = None
            grinnell_identifier_exists = False
            
            for identifier_elem in identifier_elements:
                if identifier_elem.text:
                    if identifier_elem.text.startswith("dg_"):
                        dg_identifier = identifier_elem.text
                        self.log(f"Found dg_ identifier: {dg_identifier}")
                    elif identifier_elem.text.startswith("Grinnell:"):
                        grinnell_identifier_exists = True
                        self.log(f"Found existing Grinnell: identifier: {identifier_elem.text}")
            
            # Step 5: Determine if we need to add Grinnell: identifier
            if not dg_identifier:
                self.log("No dg_ identifier found - nothing to do")
                return True, "No dg_ identifier found"
            
            if grinnell_identifier_exists:
                self.log("Grinnell: identifier already exists - nothing to do")
                return True, "Grinnell: identifier already exists"
            
            # Step 6: Extract number from dg_ identifier and create Grinnell: identifier
            # Extract number from "dg_<number>"
            dg_number = dg_identifier.replace("dg_", "")
            new_grinnell_id = f"Grinnell:{dg_number}"
            self.log(f"Creating new identifier: {new_grinnell_id}")
            
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
                self.log("Could not find parent element for dc:identifier", logging.ERROR)
                return False, "Could not find parent element for dc:identifier"
            
            # Create new dc:identifier element
            new_identifier = ET.Element('{http://purl.org/dc/elements/1.1/}identifier')
            new_identifier.text = new_grinnell_id
            parent_element.append(new_identifier)
            self.log(f"Added new dc:identifier: {new_grinnell_id}")
            
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
            self.log("=" * 60)
            self.log("XML being sent to Alma (first 500 chars):")
            self.log(xml_str[:500])
            self.log("=" * 60)
            
            # Step 9: PUT the modified XML back to Alma
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
            return True, f"Added {new_grinnell_id} to record {mms_id}"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error processing record {mms_id}: {str(e)}"
    
    def export_identifier_csv(self, mms_ids: list, output_file: str, progress_callback=None) -> tuple[bool, str]:
        """
        Function 8: Export dc:identifier fields to specialized CSV
        Creates a 4-column CSV with MMS ID and three specific identifier types:
        - dg_* identifiers (legacy Digital Grinnell)
        - Grinnell:* identifiers (standardized format)
        - http://hdl.handle.net/* identifiers (Handle System)
        
        Args:
            mms_ids: List of MMS IDs to export
            output_file: Path to output CSV file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        
        self.log(f"Starting identifier CSV export for {len(mms_ids)} records to {output_file}")
        
        # Define CSV column headings
        column_headings = [
            "MMS ID",
            "dg_* identifier",
            "Grinnell:* identifier",
            "Handle identifier"
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
                self.log(f"Using batch API calls: {total_batches} calls for {total} records")
                
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
                                
                                # Extract all dc:identifier values
                                identifiers = self._extract_dc_field("identifier", "dc")
                                
                                # Categorize identifiers
                                dg_identifier = ""
                                grinnell_identifier = ""
                                handle_identifier = ""
                                
                                for identifier in identifiers:
                                    if identifier.startswith("dg_"):
                                        dg_identifier = identifier
                                    elif identifier.startswith("Grinnell:"):
                                        grinnell_identifier = identifier
                                    elif identifier.startswith("http://hdl.handle.net/"):
                                        handle_identifier = identifier
                                
                                # Create CSV row
                                row = {
                                    "MMS ID": mms_id,
                                    "dg_* identifier": dg_identifier,
                                    "Grinnell:* identifier": grinnell_identifier,
                                    "Handle identifier": handle_identifier
                                }
                                
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
                
                message = f"Identifier CSV export complete: {success_count} succeeded, {failed_count} failed. File: {output_file}"
                self.log(message)
                self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
                return True, message
                
        except Exception as e:
            error_msg = f"Error creating identifier CSV file: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg
    
    def validate_handles_to_csv(self, mms_ids: list, output_file: str, progress_callback=None) -> tuple[bool, str]:
        """
        Function 9: Validate Handle URLs and export results to CSV
        Creates a CSV with Handle URL, dc:title, and HTTP status code.
        Useful for finding broken Handle links (404s, redirects, etc.)
        
        Args:
            mms_ids: List of MMS IDs to check
            output_file: Path to output CSV file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        
        self.log(f"Starting Handle validation for {len(mms_ids)} records to {output_file}")
        
        # Define CSV column headings
        column_headings = [
            "MMS ID",
            "Handle URL",
            "dc:title",
            "HTTP Status Code",
            "Status Message",
            "Final Redirect URL",
            "Returned Correct MMS ID",
            "Titles Match!"
        ]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=column_headings)
                writer.writeheader()
                
                success_count = 0
                failed_count = 0
                no_handle_count = 0
                status_200_count = 0
                status_404_count = 0
                status_other_count = 0
                total = len(mms_ids)
                batch_size = 100  # Alma API supports up to 100 MMS IDs per batch call
                
                # Calculate total number of API calls
                total_batches = (total + batch_size - 1) // batch_size
                self.log(f"Using batch API calls: {total_batches} calls for {total} records")
                
                # Process in batches
                for batch_start in range(0, total, batch_size):
                    # Check kill switch
                    if self.kill_switch:
                        self.log("Process stopped by user")
                        break
                    batch_end = min(batch_start + batch_size, total)
                    batch_ids = mms_ids[batch_start:batch_end]
                    batch_num = (batch_start // batch_size) + 1
                    
                    self.log(f"Processing batch {batch_num}/{total_batches}: records {batch_start+1}-{batch_end}")
                    
                    # Fetch batch of records
                    batch_records = self.fetch_bib_records_batch(batch_ids)
                    
                    # Process each record in the batch
                    for i in range(len(batch_ids)):
                        # Check kill switch
                        if self.kill_switch:
                            self.log("Process stopped by user")
                            break
                        
                        record_index = batch_start + i + 1
                        mms_id = batch_ids[i]
                        
                        try:
                            # Check if record was successfully fetched
                            if mms_id in batch_records:
                                # Set as current record for field extraction
                                self.current_record = batch_records[mms_id]
                                
                                # Extract title
                                titles = self._extract_dc_field("title", "dc")
                                title = titles[0] if titles else "No title found"
                                
                                # Extract all dc:identifier values
                                identifiers = self._extract_dc_field("identifier", "dc")
                                
                                # Find Handle identifier
                                handle_url = ""
                                for identifier in identifiers:
                                    if identifier.startswith("http://hdl.handle.net/"):
                                        handle_url = identifier
                                        break
                                
                                if handle_url:
                                    # Test the Handle URL
                                    self.log(f"Testing Handle: {handle_url}")
                                    returned_title = ""
                                    title_matches = ""
                                    primo_title_match = "N/A"
                                    
                                    try:
                                        response = requests.head(handle_url, allow_redirects=True, timeout=10)
                                        status_code = response.status_code
                                        
                                        # Get status message
                                        if status_code == 200:
                                            status_message = "OK"
                                            # Check the final redirect URL to verify it contains the correct MMS ID
                                            try:
                                                full_response = requests.get(handle_url, allow_redirects=True, timeout=10)
                                                if full_response.status_code == 200:
                                                    final_url = full_response.url
                                                    returned_title = final_url
                                                    
                                                    # Check if the final URL contains the MMS ID
                                                    # Handle URLs typically redirect to Primo with pattern: .../alma{MMS_ID}/...
                                                    primo_title_match = "N/A"
                                                    if mms_id in final_url:
                                                        title_matches = "TRUE"
                                                        self.log(f"MMS ID {mms_id} found in redirect URL: {final_url}")
                                                        
                                                        # Query Primo API for title comparison
                                                        try:
                                                            primo_api_url = f"https://grinnell.primo.exlibrisgroup.com/primaws/rest/pub/pnxs/undefined/alma{mms_id}?vid=01GCL_INST:GCL&lang=en&lang=en"
                                                            self.log(f"Querying Primo API: {primo_api_url}", logging.DEBUG)
                                                            primo_response = requests.get(primo_api_url, timeout=10)
                                                            
                                                            if primo_response.status_code == 200:
                                                                primo_data = primo_response.json()
                                                                # Extract title from JSON - typically in pnx.display.title[0]
                                                                if 'pnx' in primo_data and 'display' in primo_data['pnx'] and 'title' in primo_data['pnx']['display']:
                                                                    primo_title = primo_data['pnx']['display']['title'][0] if primo_data['pnx']['display']['title'] else ""
                                                                    # Compare titles (case-insensitive, strip whitespace)
                                                                    if primo_title.strip().lower() == title.strip().lower():
                                                                        primo_title_match = "TRUE"
                                                                        self.log(f"Primo title matches: '{primo_title}'")
                                                                    else:
                                                                        primo_title_match = "FALSE"
                                                                        self.log(f"Primo title mismatch: '{primo_title}' vs '{title}'", logging.WARNING)
                                                                else:
                                                                    self.log("No title field found in Primo JSON response", logging.WARNING)
                                                            else:
                                                                self.log(f"Primo API returned status {primo_response.status_code}", logging.WARNING)
                                                        except Exception as e:
                                                            self.log(f"Error querying Primo API: {str(e)}", logging.DEBUG)
                                                    else:
                                                        title_matches = "FALSE"
                                                        self.log(f"MMS ID {mms_id} NOT found in redirect URL: {final_url}", logging.WARNING)
                                            except Exception as e:
                                                self.log(f"Could not fetch redirect URL: {str(e)}", logging.DEBUG)
                                                returned_title = "Error fetching page"
                                                title_matches = "N/A"
                                        elif status_code == 404:
                                            status_message = "Not Found"
                                        elif status_code == 301:
                                            status_message = "Moved Permanently"
                                        elif status_code == 302:
                                            status_message = "Found (Redirect)"
                                        elif status_code == 403:
                                            status_message = "Forbidden"
                                        elif status_code == 500:
                                            status_message = "Internal Server Error"
                                        else:
                                            status_message = response.reason if hasattr(response, 'reason') else "Unknown"
                                        
                                        self.log(f"Handle {handle_url} returned {status_code}: {status_message}")
                                        
                                    except requests.exceptions.Timeout:
                                        status_code = 0
                                        status_message = "Timeout"
                                        returned_title = ""
                                        title_matches = "N/A"
                                        self.log(f"Handle {handle_url} timed out", logging.WARNING)
                                    except requests.exceptions.ConnectionError:
                                        status_code = 0
                                        status_message = "Connection Error"
                                        returned_title = ""
                                        title_matches = "N/A"
                                        self.log(f"Handle {handle_url} connection error", logging.WARNING)
                                    except Exception as e:
                                        status_code = 0
                                        status_message = f"Error: {str(e)}"
                                        returned_title = ""
                                        title_matches = "N/A"
                                        self.log(f"Handle {handle_url} error: {str(e)}", logging.WARNING)
                                    
                                    # Create CSV row
                                    row = {
                                        "MMS ID": mms_id,
                                        "Handle URL": handle_url,
                                        "dc:title": title,
                                        "HTTP Status Code": status_code,
                                        "Status Message": status_message,
                                        "Final Redirect URL": returned_title,
                                        "Returned Correct MMS ID": title_matches,
                                        "Titles Match!": primo_title_match
                                    }
                                    
                                    writer.writerow(row)
                                    success_count += 1
                                    
                                    # Track status code categories
                                    if status_code == 200:
                                        status_200_count += 1
                                    elif status_code == 404:
                                        status_404_count += 1
                                    else:
                                        status_other_count += 1
                                else:
                                    # No Handle found - skip this record
                                    no_handle_count += 1
                                    self.log(f"No Handle found for MMS ID {mms_id}", logging.DEBUG)
                            else:
                                self.log(f"Record not returned in batch: {mms_id}", logging.WARNING)
                                failed_count += 1
                            
                            # Update progress
                            if progress_callback:
                                progress_callback(record_index, total)
                            
                            if record_index % 50 == 0:
                                self.log(f"Validated {record_index}/{total} records")
                                
                        except Exception as e:
                            self.log(f"Error validating {mms_id}: {str(e)}", logging.ERROR)
                            failed_count += 1
                
                message = f"Handle validation complete: {success_count} handles tested, {no_handle_count} records without handles, {failed_count} failed. Status codes: {status_200_count} OK (200), {status_404_count} Not Found (404), {status_other_count} Other. File: {output_file}"
                self.log(message)
                self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
                return True, message
                
        except Exception as e:
            error_msg = f"Error creating Handle validation CSV file: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg
    
    def export_for_review_csv(self, mms_ids: list, output_file: str, progress_callback=None) -> tuple[bool, str]:
        """
        Function 10: Export records for review with clickable Handle links
        Creates a CSV with Handle (clickable), MMS ID, Title, dc:type, and empty review columns.
        Useful for manual review of digital objects.
        
        Args:
            mms_ids: List of MMS IDs to export
            output_file: Path to output CSV file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        
        self.log(f"Starting review export for {len(mms_ids)} records to {output_file}")
        
        # Define CSV column headings
        column_headings = [
            "MMS ID",
            "Handle",
            "Title",
            "dc:type",
            "dc:format",
            "dcterms:format",
            "Thumbnail?",
            "File Opens?",
            "Needs Attention?"
        ]
        
        try:
            # Collect all rows first before writing
            all_rows = []
            
            success_count = 0
            failed_count = 0
            no_handle_count = 0
            total = len(mms_ids)
            batch_size = 100  # Alma API supports up to 100 MMS IDs per batch call
            
            # Calculate total number of API calls
            total_batches = (total + batch_size - 1) // batch_size
            self.log(f"Using batch API calls: {total_batches} calls for {total} records")
            
            # Process in batches
            for batch_start in range(0, total, batch_size):
                # Check kill switch
                if self.kill_switch:
                    self.log("Process stopped by user")
                    break
                
                batch_end = min(batch_start + batch_size, total)
                batch_ids = mms_ids[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                
                self.log(f"Processing batch {batch_num}/{total_batches}: records {batch_start+1}-{batch_end}")
                
                # Fetch batch of records
                batch_records = self.fetch_bib_records_batch(batch_ids)
                
                # Process each record in the batch
                for i in range(len(batch_ids)):
                    # Check kill switch
                    if self.kill_switch:
                        self.log("Process stopped by user")
                        break
                    
                    record_index = batch_start + i + 1
                    mms_id = batch_ids[i]
                    
                    try:
                        # Check if record was successfully fetched
                        if mms_id in batch_records:
                            # Set as current record for field extraction
                            self.current_record = batch_records[mms_id]
                            
                            # Extract fields
                            titles = self._extract_dc_field("title", "dc")
                            title = titles[0] if titles else ""
                            
                            # Wrap title in quotes if not already quoted
                            if title and not title.startswith('"'):
                                title = f'"{title}"'
                            
                            identifiers = self._extract_dc_field("identifier", "dc")
                            handle_url = ""
                            for identifier in identifiers:
                                if identifier.startswith("http://hdl.handle.net/"):
                                    handle_url = identifier
                                    break
                            
                            types = self._extract_dc_field("type", "dc")
                            dc_type = "; ".join(types) if types else ""
                            
                            formats = self._extract_dc_field("format", "dc")
                            dc_format = "; ".join(formats) if formats else ""
                            
                            dcterms_formats = self._extract_dc_field("format", "dcterms")
                            dcterms_format = "; ".join(dcterms_formats) if dcterms_formats else ""
                            
                            # Create CSV row with empty review columns
                            row = {
                                "MMS ID": mms_id,
                                "Handle": handle_url,
                                "Title": title,
                                "dc:type": dc_type,
                                "dc:format": dc_format,
                                "dcterms:format": dcterms_format,
                                "Thumbnail?": "",
                                "File Opens?": "",
                                "Needs Attention?": ""
                            }
                            
                            all_rows.append(row)
                            
                            if handle_url:
                                success_count += 1
                            else:
                                no_handle_count += 1
                                self.log(f"No Handle URL found for {mms_id}", logging.WARNING)
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
            
            # Sort rows by MMS ID
            self.log("Sorting rows by MMS ID...")
            all_rows.sort(key=lambda x: x["MMS ID"])
            
            # Write sorted rows to CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=column_headings)
                writer.writeheader()
                writer.writerows(all_rows)
            
            message = f"Review export complete: {success_count} with handles, {no_handle_count} without handles, {failed_count} failed. File: {output_file}"
            self.log(message)
            self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
            return True, message
                
        except Exception as e:
            error_msg = f"Error creating review CSV file: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg
    
    def identify_single_tiff_objects(self, mms_ids: list, output_file: str, progress_callback=None, create_jpg=False) -> tuple[bool, str]:
        """
        Function 11: Identify digital objects with single TIFF representations
        Creates a CSV listing objects that have only one TIFF file and likely need JPG derivatives.
        Optionally creates JPG derivatives and uploads them.
        
        Args:
            mms_ids: List of MMS IDs to analyze
            output_file: Path to output CSV file
            progress_callback: Optional callback function(current, total) for progress updates
            create_jpg: If True, generate JPG derivatives and upload them
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        import os
        import tempfile
        
        if create_jpg:
            try:
                from PIL import Image
            except ImportError:
                return False, "Pillow library not installed. Run: pip install Pillow"
        
        self.log(f"Starting single TIFF analysis for {len(mms_ids)} records to {output_file}")
        if create_jpg:
            self.log("JPG derivative creation ENABLED - will download TIFFs, create JPGs, and upload")
        
        # Define CSV column headings
        column_headings = [
            "MMS ID",
            "Title",
            "Representation ID",
            "TIFF Filename",
            "S3 Path",
            "File Size (MB)",
            "JPG Created" if create_jpg else "Recommended Action",
            "Status"
        ]
        
        try:
            success_count = 0
            no_rep_count = 0
            multi_file_count = 0
            other_format_count = 0
            failed_count = 0
            jpg_created_count = 0
            jpg_failed_count = 0
            total = len(mms_ids)
            batch_size = 100
            
            # Calculate total number of API calls
            total_batches = (total + batch_size - 1) // batch_size
            self.log(f"Processing {total} records (batch metadata calls: {total_batches})")
            
            # Open CSV file for writing immediately (write results as we go)
            csvfile = open(output_file, 'w', newline='', encoding='utf-8')
            writer = csv.DictWriter(csvfile, fieldnames=column_headings)
            writer.writeheader()
            csvfile.flush()  # Ensure header is written to disk
            self.log(f"Created output file: {output_file}")
            
            # Process in batches for metadata, but individual calls for representations
            for batch_start in range(0, total, batch_size):
                if self.kill_switch:
                    self.log("Process stopped by user")
                    break
                
                batch_end = min(batch_start + batch_size, total)
                batch_ids = mms_ids[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                
                self.log(f"Processing batch {batch_num}/{total_batches}: records {batch_start+1}-{batch_end}")
                
                # Fetch batch of records for metadata
                batch_records = self.fetch_bib_records_batch(batch_ids)
                
                # Process each record in the batch
                for i in range(len(batch_ids)):
                    if self.kill_switch:
                        self.log("Process stopped by user")
                        break
                    
                    record_index = batch_start + i + 1
                    mms_id = batch_ids[i]
                    
                    try:
                        # Check if record was successfully fetched
                        if mms_id not in batch_records:
                            self.log(f"Record not returned in batch: {mms_id}", logging.WARNING)
                            failed_count += 1
                            continue
                        
                        # Set as current record for field extraction
                        self.current_record = batch_records[mms_id]
                        
                        # Extract title
                        titles = self._extract_dc_field("title", "dc")
                        title = titles[0] if titles else ""
                        if title and not title.startswith('"'):
                            title = f'"{title}"'
                        
                        # Get representations for this record (requires individual API call)
                        api_url = self._get_alma_api_url()
                        rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
                        headers = {
                            'Authorization': f'apikey {self.api_key}',
                            'Accept': 'application/json'
                        }
                        
                        # Add expand parameter to get file details
                        params = {'expand': 'p_files'}
                        
                        # Make API call with timeout and retry logic
                        max_retries = 3
                        retry_delay = 2
                        response = None
                        
                        for attempt in range(max_retries):
                            try:
                                response = requests.get(rep_url, headers=headers, params=params, timeout=30)
                                break  # Success, exit retry loop
                            except requests.exceptions.Timeout:
                                if attempt < max_retries - 1:
                                    self.log(f"Timeout for {mms_id}, retrying ({attempt+1}/{max_retries})...", logging.WARNING)
                                    import time
                                    time.sleep(retry_delay)
                                else:
                                    self.log(f"Timeout for {mms_id} after {max_retries} attempts", logging.ERROR)
                                    failed_count += 1
                                    response = None
                                    break
                            except requests.exceptions.RequestException as req_err:
                                if attempt < max_retries - 1:
                                    self.log(f"Network error for {mms_id}: {req_err}, retrying ({attempt+1}/{max_retries})...", logging.WARNING)
                                    import time
                                    time.sleep(retry_delay)
                                else:
                                    self.log(f"Network error for {mms_id} after {max_retries} attempts: {req_err}", logging.ERROR)
                                    failed_count += 1
                                    response = None
                                    break
                        
                        if response is None:
                            continue
                        
                        if response.status_code == 200:
                            rep_data = response.json()
                            representations = rep_data.get('representation', [])
                            
                            if not representations:
                                no_rep_count += 1
                                continue
                            
                            # Check if exactly ONE representation exists
                            if len(representations) != 1:
                                multi_file_count += 1
                                continue
                            
                            # Check the single representation
                            rep = representations[0]
                            rep_id = rep.get('id', '')
                            
                            files_data = rep.get('files', {})
                            
                            # The files are not included directly, we need to follow the link
                            files = []
                            if isinstance(files_data, dict):
                                files_link = files_data.get('link')
                                if files_link:
                                    # Make another API call to get the files with timeout and retry
                                    files_response = None
                                    for attempt in range(max_retries):
                                        try:
                                            files_response = requests.get(files_link, headers=headers, timeout=30)
                                            break
                                        except requests.exceptions.Timeout:
                                            if attempt < max_retries - 1:
                                                self.log(f"Timeout fetching files for {mms_id}, retrying ({attempt+1}/{max_retries})...", logging.WARNING)
                                                import time
                                                time.sleep(retry_delay)
                                            else:
                                                self.log(f"Timeout fetching files for {mms_id} after {max_retries} attempts", logging.ERROR)
                                                failed_count += 1
                                                files_response = None
                                                break
                                        except requests.exceptions.RequestException as req_err:
                                            if attempt < max_retries - 1:
                                                self.log(f"Network error fetching files for {mms_id}: {req_err}, retrying ({attempt+1}/{max_retries})...", logging.WARNING)
                                                import time
                                                time.sleep(retry_delay)
                                            else:
                                                self.log(f"Network error fetching files for {mms_id} after {max_retries} attempts: {req_err}", logging.ERROR)
                                                failed_count += 1
                                                files_response = None
                                                break
                                    
                                    if files_response and files_response.status_code == 200:
                                        files_json = files_response.json()
                                        files = files_json.get('representation_file', [])
                                        # Ensure files is a list
                                        if not isinstance(files, list):
                                            files = [files] if files else []
                                    # Make another API call to get the files
                                    files_response = requests.get(files_link, headers=headers)
                                    if files_response.status_code == 200:
                                        files_json = files_response.json()
                                        files = files_json.get('representation_file', [])
                                        # Ensure files is a list
                                        if not isinstance(files, list):
                                            files = [files] if files else []
                            
                            # Debug logging
                            self.log(f"MMS {mms_id}: Found {len(files)} file(s) in representation", logging.DEBUG)
                            try:
                                if files:
                                    self.log(f"MMS {mms_id}: Files type: {type(files)}", logging.DEBUG)
                                    if isinstance(files, list) and len(files) > 0:
                                        self.log(f"MMS {mms_id}: First file: {files[0]}", logging.DEBUG)
                                    elif isinstance(files, dict):
                                        self.log(f"MMS {mms_id}: Files is dict with keys: {list(files.keys())}", logging.DEBUG)
                                    else:
                                        self.log(f"MMS {mms_id}: Files content: {files}", logging.DEBUG)
                            except Exception as debug_error:
                                self.log(f"MMS {mms_id}: Debug error: {debug_error}", logging.DEBUG)
                            if files:
                                for f in files:
                                    self.log(f"  File: {f.get('path', 'unknown')}", logging.DEBUG)
                            
                            # Check if exactly ONE file in the representation
                            if len(files) != 1:
                                self.log(f"MMS {mms_id}: Multiple files ({len(files)}), skipping", logging.DEBUG)
                                multi_file_count += 1
                                continue
                            
                            # Check if the file is a TIFF
                            file_info = files[0]
                            filename = file_info.get('label', '') or file_info.get('path', '')
                            s3_path = file_info.get('path', '')
                            file_pid = file_info.get('pid', '')
                            file_size_bytes = int(file_info.get('size', 0))
                            file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
                            
                            # Check file extension
                            if filename.lower().endswith(('.tif', '.tiff')):
                                # Found a single TIFF representation!
                                
                                # Write result to CSV immediately (don't wait till end)
                                row = {
                                    "MMS ID": mms_id,
                                    "Title": title,
                                    "Representation ID": rep_id,
                                    "TIFF Filename": filename,
                                    "S3 Path": s3_path,
                                    "File Size (MB)": file_size_mb,
                                    "JPG Created" if create_jpg else "Recommended Action": "Not Implemented" if create_jpg else "Create JPG derivative and set as primary",
                                    "Status": "File download from Alma API requires special permissions" if create_jpg else "Manual JPG creation needed"
                                }
                                writer.writerow(row)
                                csvfile.flush()  # Ensure row is written to disk immediately
                                success_count += 1
                                
                                if create_jpg:
                                    self.log(f"Note: Automatic JPG creation requires direct file access - add this to your workflow", logging.WARNING)
                            else:
                                other_format_count += 1
                        
                        elif response.status_code == 404:
                            # No representations
                            no_rep_count += 1
                        else:
                            self.log(f"Error fetching representations for {mms_id}: HTTP {response.status_code}", logging.WARNING)
                            failed_count += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_callback(record_index, total)
                        
                        if record_index % 50 == 0:
                            self.log(f"Analyzed {record_index}/{total} records - Found {success_count} single TIFF objects")
                        
                        # Small delay to respect API rate limits (0.1s = max 10 req/sec)
                        import time
                        time.sleep(0.1)
                            
                    except Exception as e:
                        self.log(f"Error analyzing {mms_id}: {str(e)}", logging.ERROR)
                        failed_count += 1
            
            # Close the CSV file
            csvfile.close()
            self.log(f"Closed output file: {output_file}")
            
            message = f"Single TIFF analysis complete: Found {success_count} objects with single TIFF files. "
            if create_jpg:
                message += f"JPG derivatives: {jpg_created_count} created, {jpg_failed_count} failed. "
            message += f"({no_rep_count} no reps, {multi_file_count} multi-file, {other_format_count} other formats, {failed_count} failed). "
            message += f"File: {output_file}"
            self.log(message)
            return True, message
                
        except Exception as e:
            error_msg = f"Error creating single TIFF analysis CSV: {str(e)}"
            self.log(error_msg, logging.ERROR)
            # Try to close the file if it was opened
            try:
                csvfile.close()
            except:
                pass
            return False, error_msg
    
    def analyze_sound_records_by_decade(self, mms_ids: list, output_file: str, progress_callback=None) -> tuple[bool, str]:
        """
        Function 13: Analyze sound recordings by decade
        Examines records where dc:type is "sound", extracts dc:date or dcterms:created (year), 
        determines the decade, and exports to CSV grouped by decade.
        
        Args:
            mms_ids: List of MMS IDs to analyze
            output_file: Path to output CSV file
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        import re
        
        self.log(f"Starting sound records decade analysis for {len(mms_ids)} records to {output_file}")
        
        # Define CSV column headings
        column_headings = [
            "MMS ID",
            "Title",
            "dc:type",
            "dc:date",
            "dcterms:created",
            "Year",
            "Decade"
        ]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(column_headings)
                
                sound_count = 0
                non_sound_count = 0
                no_date_count = 0
                failed_count = 0
                total = len(mms_ids)
                batch_size = 100
                
                # Calculate total number of API calls
                total_batches = (total + batch_size - 1) // batch_size
                self.log(f"Using batch API calls: {total_batches} calls for {total} records")
                
                # Process in batches
                for batch_start in range(0, total, batch_size):
                    # Check kill switch
                    if self.kill_switch:
                        self.log("Process stopped by user")
                        break
                    
                    batch_end = min(batch_start + batch_size, total)
                    batch_ids = mms_ids[batch_start:batch_end]
                    batch_num = (batch_start // batch_size) + 1
                    
                    self.log(f"Processing batch {batch_num}/{total_batches}: records {batch_start+1}-{batch_end}")
                    
                    # Fetch batch of records
                    batch_records = self.fetch_bib_records_batch(batch_ids)
                    
                    # Process each record in the batch
                    for i in range(len(batch_ids)):
                        # Check kill switch
                        if self.kill_switch:
                            self.log("Process stopped by user")
                            break
                        
                        record_index = batch_start + i + 1
                        mms_id = batch_ids[i]
                        
                        try:
                            # Check if record was successfully fetched
                            if mms_id in batch_records:
                                # Set as current record for field extraction
                                self.current_record = batch_records[mms_id]
                                
                                # Extract dc:type field
                                types = self._extract_dc_field("type", "dc")
                                dc_type = types[0] if types else ""
                                
                                # Check if dc:type is "sound"
                                if dc_type.lower() == "sound":
                                    # Extract title
                                    titles = self._extract_dc_field("title", "dc")
                                    title = titles[0] if titles else self.current_record.get("title", "")
                                    
                                    # Extract dc:date
                                    dates = self._extract_dc_field("date", "dc")
                                    dc_date = dates[0] if dates else ""
                                    
                                    # Extract dcterms:created
                                    created = self._extract_dc_field("created", "dcterms")
                                    dcterms_created = created[0] if created else ""
                                    
                                    # Try to extract year from dc:date first, then dcterms:created
                                    year = None
                                    decade = ""
                                    date_source = ""
                                    
                                    # Try dc:date first
                                    if dc_date:
                                        # Try to find a 4-digit year in the date string
                                        year_match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', dc_date)
                                        if year_match:
                                            year = int(year_match.group(1))
                                            date_source = "dc:date"
                                    
                                    # If no year from dc:date, try dcterms:created
                                    if not year and dcterms_created:
                                        year_match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', dcterms_created)
                                        if year_match:
                                            year = int(year_match.group(1))
                                            date_source = "dcterms:created"
                                    
                                    # Calculate decade if we found a year
                                    if year:
                                        decade_start = (year // 10) * 10
                                        decade = f"{decade_start}s"
                                    else:
                                        if not dc_date and not dcterms_created:
                                            self.log(f"No dc:date or dcterms:created found for {mms_id}", logging.WARNING)
                                        else:
                                            self.log(f"Could not extract year from date fields for {mms_id} (dc:date='{dc_date}', dcterms:created='{dcterms_created}')", logging.WARNING)
                                        no_date_count += 1
                                    
                                    # Write row to CSV
                                    row = [
                                        mms_id,
                                        title,
                                        dc_type,
                                        dc_date,
                                        dcterms_created,
                                        year if year else "",
                                        decade
                                    ]
                                    writer.writerow(row)
                                    sound_count += 1
                                else:
                                    non_sound_count += 1
                            else:
                                self.log(f"Record not returned in batch: {mms_id}", logging.WARNING)
                                failed_count += 1
                            
                            # Update progress
                            if progress_callback:
                                progress_callback(record_index, total)
                            
                            if record_index % 50 == 0:
                                self.log(f"Analyzed {record_index}/{total} records - Found {sound_count} sound recordings")
                                
                        except Exception as e:
                            self.log(f"Error analyzing {mms_id}: {str(e)}", logging.ERROR)
                            failed_count += 1
                
                message = f"Sound records analysis complete: {sound_count} sound recordings found, {non_sound_count} non-sound, {no_date_count} missing/invalid dates, {failed_count} failed. File: {output_file}"
                self.log(message)
                self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
                return True, message
                
        except Exception as e:
            error_msg = f"Error creating sound records analysis CSV: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg
    
    def upload_clientthumb_thumbnails(self, mms_ids: list, thumbnail_folder: str = None, progress_callback=None) -> tuple[bool, str]:
        """
        Function 14a: Prepare .clientThumb thumbnails for Alma (Create representations & process files)
        
        For each MMS ID:
        1. Fetch the bib record from Alma
        2. Extract all dc:identifier values
        3. Search for thumbnail files matching pattern: *grinnell_<ID>*.clientThumb* or *grinnell_<ID>*.jpg
           (also supports dg_<ID> patterns)
        4. Create thumbnail representation in Alma
        5. Process file (PNG->JPEG conversion, optimization)
        6. Save processed file to timestamped output directory
        7. Create CSV mapping MMS IDs to representation IDs
        
        Args:
            mms_ids: List of MMS IDs to process
            thumbnail_folder: Folder containing .clientThumb files (default: from THUMBNAIL_FOLDER_PATH env var)
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        from pathlib import Path
        import re
        from datetime import datetime
        import csv
        import shutil
        
        # Get thumbnail folder from environment variable if not provided
        if thumbnail_folder is None:
            thumbnail_folder = os.getenv('THUMBNAIL_FOLDER_PATH', '/Volumes/DGIngest/Migration-to-Alma/exports/alumni-oral-histories/OBJ')
        
        # Create timestamped output directory in Downloads folder (absolute path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        downloads_dir = Path.home() / "Downloads"
        output_dir = downloads_dir / f"CABB_thumbnail_prep_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log(f"Starting Function 14a: Prepare .clientThumb Thumbnails")
        self.log(f"Processing {len(mms_ids)} MMS ID(s)")
        self.log(f"Thumbnail folder: {thumbnail_folder}")
        self.log(f"Output directory: {output_dir.absolute()}")
        
        if not self.api_key:
            return False, "API Key not configured"
        
        # Verify folder exists
        folder_path = Path(thumbnail_folder)
        if not folder_path.exists() or not folder_path.is_dir():
            return False, f"Thumbnail folder not found: {thumbnail_folder}"
        
        try:
            # Initialize CSV data collection
            csv_data = []
            
            # Process each MMS ID
            success_count = 0
            failed_count = 0
            no_identifier_count = 0
            no_thumbnail_count = 0
            total = len(mms_ids)
            
            for idx, mms_id in enumerate(mms_ids, 1):
                if self.kill_switch:
                    self.log("Operation cancelled by user", logging.WARNING)
                    break
                
                if progress_callback:
                    progress_callback(idx, total)
                
                self.log(f"\nProcessing {idx}/{total}: MMS {mms_id}")
                
                # Step 1: Fetch bib record to get dc:identifier
                success, message = self.fetch_bib_record(mms_id)
                if not success:
                    self.log(f"  ✗ Failed to fetch record: {message}", logging.ERROR)
                    failed_count += 1
                    continue
                
                # Step 2: Extract all dc:identifier values
                identifiers = self._extract_dc_field("identifier", "dc")
                
                if not identifiers:
                    self.log(f"  ⊘ No dc:identifier found", logging.WARNING)
                    no_identifier_count += 1
                    continue
                
                # Step 3: Extract ID numbers from identifiers (grinnell:XXXXX or dg_XXXXX)
                # and search for matching thumbnail files
                id_patterns = []
                for identifier in identifiers:
                    # Pattern 1: grinnell:12205 → grinnell_12205
                    if identifier.startswith("grinnell:"):
                        id_num = identifier.replace("grinnell:", "")
                        id_patterns.append(("grinnell_" + id_num, identifier))
                    # Pattern 2: dg_12205 → dg_12205
                    elif identifier.startswith("dg_"):
                        id_patterns.append((identifier, identifier))
                
                if not id_patterns:
                    self.log(f"  ⊘ No grinnell: or dg_ identifier found", logging.WARNING)
                    self.log(f"  Available identifiers: {', '.join(identifiers)}", logging.DEBUG)
                    no_identifier_count += 1
                    continue
                
                # Step 4: Search for thumbnail file using glob patterns
                thumbnail_file = None
                matched_id = None
                
                self.log(f"  Searching for thumbnails matching: {', '.join([p[0] for p in id_patterns])}")
                
                for id_pattern, original_id in id_patterns:
                    # Try various glob patterns:
                    # 1. *grinnell_12205*.clientThumb (files ending in .clientThumb, no extension)
                    # 2. *grinnell_12205*.clientThumb.jpg (files with .clientThumb.jpg extension)
                    # 3. *grinnell_12205*.jpg (files ending in .jpg that contain the ID)
                    
                    search_patterns = [
                        f"*{id_pattern}*.clientThumb",
                        f"*{id_pattern}*.clientThumb.jpg",
                        f"*{id_pattern}*.jpg"
                    ]
                    
                    for pattern in search_patterns:
                        matches = list(folder_path.glob(pattern))
                        if matches:
                            # Take the first match
                            thumbnail_file = matches[0]
                            matched_id = original_id
                            self.log(f"  Pattern '{pattern}' matched: {thumbnail_file.name}")
                            break
                    
                    if thumbnail_file:
                        break
                
                if not thumbnail_file:
                    self.log(f"  ⊘ No thumbnail file found - skipping (this is normal for some records)", logging.INFO)
                    self.log(f"    Searched patterns: {', '.join([f'*{p[0]}*' for p in id_patterns])}", logging.DEBUG)
                    no_thumbnail_count += 1
                    continue
                
                file_size = thumbnail_file.stat().st_size
                self.log(f"  ✓ Found thumbnail: {thumbnail_file.name} ({file_size / 1024:.2f} KB)")
                
                # Step 5: Create representation and prepare thumbnail file
                # Pass the id_pattern to create a clean filename
                prep_success, prep_result = self._prepare_thumbnail_representation(
                    mms_id, 
                    str(thumbnail_file), 
                    thumbnail_file.name,
                    id_pattern,  # Pass the clean identifier for filename
                    output_dir  # Output directory for processed files
                )
                
                if prep_success:
                    # prep_result is a dict with rep_id, processed_file, message
                    rep_id = prep_result['rep_id']
                    processed_file = prep_result['processed_file']
                    
                    self.log(f"  ✓ {prep_result['message']}")
                    self.log(f"    Rep ID: {rep_id}")
                    self.log(f"    Processed file: {processed_file}")
                    
                    # Add to CSV data with full paths
                    csv_data.append({
                        'mms_id': mms_id,
                        'rep_id': rep_id,
                        'filename': str(output_dir / processed_file),  # Full path to processed file
                        'original_file': str(thumbnail_file)  # Full path to original file
                    })
                    
                    success_count += 1
                else:
                    self.log(f"  ✗ {prep_result}", logging.ERROR)
                    failed_count += 1
            
            # Write CSV file with results
            if csv_data:
                csv_file = output_dir / f"thumbnail_representations_{timestamp}.csv"
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['mms_id', 'rep_id', 'filename', 'original_file'])
                    writer.writeheader()
                    writer.writerows(csv_data)
                
                self.log(f"\n✓ Created CSV file: {csv_file}")
                self.log(f"  Contains {len(csv_data)} entries")
            
            # Final summary
            message = f"Thumbnail preparation complete: {success_count} prepared, {failed_count} failed, "
            message += f"{no_identifier_count} no identifier, {no_thumbnail_count} no thumbnail (normal)"
            message += f"\nOutput directory: {output_dir.absolute()}"
            self.log(message)
            if no_thumbnail_count > 0:
                self.log(f"Note: {no_thumbnail_count} record(s) had no matching thumbnail files - this is expected for some records", logging.INFO)
            return True, message
            
        except Exception as e:
            error_msg = f"Error preparing thumbnails: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.DEBUG)
            return False, error_msg
    
    def add_jpg_representations_from_folder(self, mms_ids: list, jpg_folder: str = "For-Import", progress_callback=None) -> tuple[bool, str]:
        """
        Function 12: Add JPG representations to objects from For-Import folder
        
        For each MMS ID:
        1. Fetch existing representation info from Alma
        2. Get TIFF filename from representation
        3. Derive JPG filename from TIFF basename
        4. Check For-Import folder for matching JPG
        5. If found, upload JPG as new representation
        
        Args:
            mms_ids: List of MMS IDs to process
            jpg_folder: Folder containing JPG files (default: "For-Import")
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        from pathlib import Path
        
        self.log(f"Starting Function 12: Add JPG Representations from {jpg_folder}")
        self.log(f"Processing {len(mms_ids)} MMS ID(s)")
        
        if not self.api_key:
            return False, "API Key not configured"
        
        # Verify folder exists
        folder_path = Path(jpg_folder)
        if not folder_path.exists() or not folder_path.is_dir():
            return False, f"Folder not found: {jpg_folder}"
        
        try:
            # Process each MMS ID
            success_count = 0
            failed_count = 0
            no_rep_count = 0
            no_jpg_count = 0
            total = len(mms_ids)
            
            for idx, mms_id in enumerate(mms_ids, 1):
                if self.kill_switch:
                    self.log("Operation cancelled by user", logging.WARNING)
                    break
                
                if progress_callback:
                    progress_callback(idx, total)
                
                self.log(f"\nProcessing {idx}/{total}: MMS {mms_id}")
                
                # Step 1: Get representations from Alma
                api_url = self._get_alma_api_url()
                rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
                headers = {
                    'Authorization': f'apikey {self.api_key}',
                    'Accept': 'application/json'
                }
                
                self.log(f"  Fetching representations from Alma...")
                response = requests.get(rep_url, headers=headers)
                
                if response.status_code != 200:
                    self.log(f"  ✗ Failed to fetch representations: HTTP {response.status_code}", logging.ERROR)
                    failed_count += 1
                    continue
                
                rep_data = response.json()
                representations = rep_data.get('representation', [])
                
                if not representations:
                    self.log(f"  ✗ No representations found", logging.WARNING)
                    no_rep_count += 1
                    continue
                
                # Step 2: Find TIFF file in representations
                tiff_filename = None
                for rep in representations:
                    rep_id = rep.get('id', '')
                    files_data = rep.get('files', {})
                    
                    # Get files link
                    if isinstance(files_data, dict):
                        files_link = files_data.get('link')
                        if files_link:
                            # Fetch files
                            files_response = requests.get(files_link, headers=headers)
                            if files_response.status_code == 200:
                                files_json = files_response.json()
                                files = files_json.get('representation_file', [])
                                if not isinstance(files, list):
                                    files = [files] if files else []
                                
                                # Look for TIFF file
                                for file_info in files:
                                    filename = file_info.get('label', '')
                                    if filename.lower().endswith(('.tif', '.tiff')):
                                        tiff_filename = filename
                                        self.log(f"  Found TIFF in representation: {tiff_filename}")
                                        break
                    
                    if tiff_filename:
                        break
                
                if not tiff_filename:
                    self.log(f"  ✗ No TIFF file found in representations", logging.WARNING)
                    no_rep_count += 1
                    continue
                
                # Step 3: Derive JPG filename from TIFF basename
                tiff_path = Path(tiff_filename)
                jpg_filename = tiff_path.stem + '.jpg'
                jpg_path = folder_path / jpg_filename
                
                self.log(f"  TIFF file: {tiff_filename}")
                self.log(f"  Looking for JPG: {jpg_filename}")
                self.log(f"  JPG path: {jpg_path}")
                
                # Step 4: Check if JPG exists
                if not jpg_path.exists():
                    self.log(f"  ✗ JPG file not found in {jpg_folder}", logging.WARNING)
                    no_jpg_count += 1
                    continue
                
                file_size = jpg_path.stat().st_size
                self.log(f"  ✓ Found JPG: {jpg_filename} ({file_size / 1024 / 1024:.2f} MB)")
                
                # Step 5: Upload JPG as new representation
                upload_success, message = self._upload_jpg_representation(mms_id, str(jpg_path), jpg_filename)
                
                if upload_success:
                    success_count += 1
                    self.log(f"  ✓ Successfully added JPG representation")
                else:
                    failed_count += 1
                    self.log(f"  ✗ Failed: {message}", logging.ERROR)
            
            result_msg = f"Function 12 complete: {success_count} JPG(s) added, {failed_count} failed, {no_rep_count} no TIFF found, {no_jpg_count} no JPG found"
            self.log(result_msg)
            return True, result_msg
            
        except Exception as e:
            error_msg = f"Error in Function 12: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False, error_msg
    
    def _upload_jpg_representation(self, mms_id: str, jpg_path: str, filename: str) -> tuple[bool, str]:
        """
        Upload a JPG file as a new representation for a bib record.
        
        NOTE: The Alma Representations API requires multipart file upload.
        This is a placeholder implementation - actual file upload requires
        proper multipart/form-data handling.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            jpg_path: Full path to the JPG file
            filename: Filename for the uploaded file
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            self.log(f"Starting upload for MMS {mms_id}")
            self.log(f"  File: {filename}")
            self.log(f"  Path: {jpg_path}")
            
            # Verify file exists before attempting upload
            from pathlib import Path
            if not Path(jpg_path).exists():
                return False, f"File not found: {jpg_path}"
            
            file_size = Path(jpg_path).stat().st_size
            self.log(f"  File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            api_url = self._get_alma_api_url()
            self.log(f"  API URL: {api_url}")
            
            # Step 1: Create a new representation
            # POST /almaws/v1/bibs/{mms_id}/representations
            rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
            
            # Representation metadata
            rep_data = {
                "label": f"JPG derivative - {filename}",
                "usage_type": {"value": "DERIVATIVE_COPY"},
                "library": {"value": "MAIN"},  # Adjust as needed
                "public_note": "JPG derivative created from TIFF"
            }
            
            headers = {
                'Authorization': f'apikey {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            self.log(f"Creating representation for {mms_id}")
            self.log(f"  POST to: {rep_url}")
            response = requests.post(rep_url, headers=headers, json=rep_data)
            
            self.log(f"  Response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                self.log(f"  Response body: {response.text}", logging.ERROR)
                return False, f"Failed to create representation: HTTP {response.status_code} - {response.text}"
            
            rep_response = response.json()
            rep_id = rep_response.get('id')
            self.log(f"Created representation ID: {rep_id}")
            
            # Step 2: Upload the JPG file to the representation
            # POST /almaws/v1/bibs/{mms_id}/representations/{rep_id}/files
            # Alma requires files to be uploaded via a specific path format
            files_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files"
            
            self.log(f"Uploading file {filename} to representation {rep_id}")
            self.log(f"  POST to: {files_url}")
            
            # Get institution code from environment
            institution_code = self._get_institution_code()
            if not institution_code:
                # Try to extract from API URL or use default
                institution_code = "01GCL_INST"  # Default for Grinnell
            
            self.log(f"  Institution code: {institution_code}")
            
            # Read the file content
            with open(jpg_path, 'rb') as f:
                file_content = f.read()
            
            file_size_mb = len(file_content) / 1024 / 1024
            self.log(f"  File size: {len(file_content)} bytes ({file_size_mb:.2f} MB)")
            
            # Alma's file upload requires multipart/form-data with specific fields
            # The 'path' field must start with institution_code/upload/
            upload_path = f"{institution_code}/upload/{filename}"
            
            self.log(f"  Upload path: {upload_path}")
            
            # Prepare multipart form data
            files_data = {
                'file': (filename, file_content, 'image/jpeg')
            }
            
            data = {
                'path': upload_path
            }
            
            headers_upload = {
                'Authorization': f'apikey {self.api_key}',
                'Accept': 'application/json'
            }
            
            upload_response = requests.post(files_url, headers=headers_upload, files=files_data, data=data)
            
            self.log(f"  Upload response status: {upload_response.status_code}")
            if upload_response.status_code not in [200, 201]:
                self.log(f"  Upload response body: {upload_response.text}", logging.ERROR)
                return False, f"Failed to upload file: HTTP {upload_response.status_code} - {upload_response.text}"
            
            self.log(f"Successfully uploaded {filename} as representation {rep_id}")
            return True, f"JPG representation added successfully (Rep ID: {rep_id})"
            
        except Exception as e:
            self.log(f"Exception in _upload_jpg_representation: {str(e)}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False, f"Error uploading JPG: {str(e)}"
    
    def _upload_thumbnail_representation(self, mms_id: str, thumbnail_path: str, filename: str, identifier: str = None) -> tuple[bool, str]:
        """
        Upload a thumbnail image file as a new representation for a bib record.
        
        This creates a representation with usage_type AUXILIARY and uploads the clientThumb image file.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            thumbnail_path: Full path to the thumbnail file
            filename: Original filename (for logging only)
            identifier: Clean identifier like 'grinnell_12205' or 'dg_12205' (for creating clean upload filename)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        temp_file_path = None  # Initialize temp file tracking
        
        # Create a clean upload filename from identifier
        # Example: grinnell_12205 -> grinnell_12205_thumbnail.jpg
        if identifier:
            clean_upload_name = f"{identifier}_thumbnail.jpg"
        else:
            # Fallback to sanitized version of original filename
            clean_upload_name = filename.replace('.mp3', '').replace('.clientThumb', '_thumbnail')
            if not clean_upload_name.endswith('.jpg'):
                clean_upload_name += '.jpg'
        
        try:
            self.log(f"Starting thumbnail upload for MMS {mms_id}")
            self.log(f"  File: {filename}")
            self.log(f"  Path: {thumbnail_path}")
            
            # Verify file exists before attempting upload
            from pathlib import Path
            if not Path(thumbnail_path).exists():
                return False, f"File not found: {thumbnail_path}"
            
            file_size = Path(thumbnail_path).stat().st_size
            self.log(f"  File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
            
            # Determine actual MIME type by reading file magic bytes (not extension)
            # Many .jpg files are actually PNG format
            mime_type = 'image/jpeg'  # default
            try:
                with open(thumbnail_path, 'rb') as f:
                    header = f.read(8)
                    # Check for PNG signature: 89 50 4E 47 0D 0A 1A 0A
                    if header[:4] == b'\x89PNG':
                        mime_type = 'image/png'
                    # Check for JPEG signature: FF D8 FF
                    elif header[:3] == b'\xff\xd8\xff':
                        mime_type = 'image/jpeg'
                    else:
                        # Fall back to extension-based detection
                        import mimetypes
                        detected_type, _ = mimetypes.guess_type(thumbnail_path)
                        if detected_type:
                            mime_type = detected_type
            except Exception as e:
                self.log(f"  Warning: Could not detect file type from magic bytes: {e}", logging.WARNING)
                # Fall back to extension
                import mimetypes
                detected_type, _ = mimetypes.guess_type(thumbnail_path)
                if detected_type:
                    mime_type = detected_type
            
            self.log(f"  Detected MIME type: {mime_type}")
            
            # Step 1a: Convert PNG to JPEG if needed (Alma may require JPEG for thumbnails)
            file_to_upload = thumbnail_path
            upload_filename = clean_upload_name  # Use the clean filename from start
            
            if mime_type == 'image/png':
                try:
                    from PIL import Image
                    import tempfile
                    
                    self.log(f"  PNG detected - converting to JPEG for Alma compatibility")
                    
                    # Open PNG and convert to RGB (remove alpha channel if present)
                    img = Image.open(thumbnail_path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        # Convert RGBA/LA/P to RGB by creating white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Create temporary JPEG file
                    temp_fd, temp_file_path = tempfile.mkstemp(suffix='.jpg', prefix='thumb_')
                    os.close(temp_fd)  # Close the file descriptor
                    
                    # Save as JPEG with high quality
                    img.save(temp_file_path, 'JPEG', quality=95, optimize=True)
                    
                    # Update file reference and MIME type
                    file_to_upload = temp_file_path
                    mime_type = 'image/jpeg'
                    # upload_filename already set to clean name above
                    
                    converted_size = Path(temp_file_path).stat().st_size
                    self.log(f"  ✓ Converted to JPEG: {converted_size} bytes ({converted_size / 1024:.2f} KB)")
                    
                except ImportError:
                    self.log(f"  Warning: Pillow library not available - uploading PNG as-is", logging.WARNING)
                    self.log(f"  Install Pillow with: pip install Pillow", logging.INFO)
                except Exception as e:
                    self.log(f"  Warning: PNG to JPEG conversion failed: {e}", logging.WARNING)
                    self.log(f"  Uploading original PNG file", logging.INFO)
                    import traceback
                    self.log(traceback.format_exc(), logging.DEBUG)
            
            # Step 1b: Ensure file size is under 100KB (Alma thumbnail size limit)
            MAX_SIZE = 100 * 1024  # 100KB in bytes
            current_size = Path(file_to_upload).stat().st_size
            
            if current_size > MAX_SIZE:
                try:
                    from PIL import Image
                    import tempfile
                    
                    self.log(f"  File size ({current_size / 1024:.2f} KB) exceeds 100KB limit - optimizing")
                    
                    # Remember which file currently has the image data
                    source_image = file_to_upload
                    
                    # If we haven't already created a temp file, create one now
                    if temp_file_path is None:
                        temp_fd, temp_file_path = tempfile.mkstemp(suffix='.jpg', prefix='thumb_')
                        os.close(temp_fd)
                        file_to_upload = temp_file_path
                    
                    # Open the source image
                    img = Image.open(source_image)
                    
                    # Convert to RGB if needed
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Try reducing quality first
                    quality_attempts = [85, 75, 65, 55]
                    optimized = False
                    
                    for quality in quality_attempts:
                        img.save(temp_file_path, 'JPEG', quality=quality, optimize=True)
                        new_size = Path(temp_file_path).stat().st_size
                        self.log(f"    Trying quality={quality}: {new_size / 1024:.2f} KB")
                        
                        if new_size <= MAX_SIZE:
                            self.log(f"  ✓ Optimized to {new_size / 1024:.2f} KB (quality={quality})")
                            optimized = True
                            mime_type = 'image/jpeg'
                            # upload_filename already set to clean name above
                            break
                    
                    # If quality reduction wasn't enough, try resizing
                    if not optimized:
                        self.log(f"    Quality reduction insufficient - resizing image")
                        original_width, original_height = img.size
                        
                        # Try reducing size by 10% increments
                        for scale in [0.9, 0.8, 0.7, 0.6, 0.5]:
                            new_width = int(original_width * scale)
                            new_height = int(original_height * scale)
                            resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            
                            resized.save(temp_file_path, 'JPEG', quality=65, optimize=True)
                            new_size = Path(temp_file_path).stat().st_size
                            self.log(f"    Trying {new_width}x{new_height} (scale={scale}): {new_size / 1024:.2f} KB")
                            
                            if new_size <= MAX_SIZE:
                                self.log(f"  ✓ Resized to {new_width}x{new_height}: {new_size / 1024:.2f} KB")
                                optimized = True
                                mime_type = 'image/jpeg'
                                # upload_filename already set to clean name above
                                break
                    
                    if not optimized:
                        self.log(f"  Warning: Could not reduce file size below 100KB - uploading as-is", logging.WARNING)
                
                except ImportError:
                    self.log(f"  Warning: Pillow library not available - cannot optimize file size", logging.WARNING)
                    self.log(f"  File will be uploaded as-is ({current_size / 1024:.2f} KB)", logging.INFO)
                except Exception as e:
                    self.log(f"  Warning: File size optimization failed: {e}", logging.WARNING)
                    self.log(f"  Uploading file as-is", logging.INFO)
                    import traceback
                    self.log(traceback.format_exc(), logging.DEBUG)
            
            api_url = self._get_alma_api_url()
            self.log(f"  API URL: {api_url}")
            
            # Step 1: Create a new representation with usage_type DERIVATIVE_COPY (for thumbnail)
            # POST /almaws/v1/bibs/{mms_id}/representations
            # Note: AUXILIARY and THUMBNAIL usage_types have issues with file uploads
            # DERIVATIVE_COPY is the most appropriate for thumbnail images
            rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
            
            # Representation metadata (use upload_filename in case of PNG->JPEG conversion)
            rep_data = {
                "label": f"Thumbnail - {upload_filename}",
                "usage_type": {"value": "DERIVATIVE_COPY"},
                "library": {"value": "MAIN"},  # Adjust as needed
                "public_note": "Thumbnail image from Digital Grinnell migration"
            }
            
            headers = {
                'Authorization': f'apikey {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            self.log(f"Creating thumbnail representation for {mms_id}")
            self.log(f"  POST to: {rep_url}")
            response = requests.post(rep_url, headers=headers, json=rep_data)
            
            self.log(f"  Response status: {response.status_code}")
            if response.status_code not in [200, 201]:
                self.log(f"  Response body: {response.text}", logging.ERROR)
                # Clean up temp file if it exists
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                return False, f"Failed to create representation: HTTP {response.status_code} - {response.text}"
            
            rep_response = response.json()
            rep_id = rep_response.get('id')
            self.log(f"Created thumbnail representation ID: {rep_id}")
            
            # Step 2: Upload the thumbnail file to the representation
            # POST /almaws/v1/bibs/{mms_id}/representations/{rep_id}/files
            files_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations/{rep_id}/files"
            
            self.log(f"Uploading file {upload_filename} to representation {rep_id}")
            self.log(f"  POST to: {files_url}")
            
            # Get institution code from environment
            institution_code = self._get_institution_code()
            if not institution_code:
                # Try to extract from API URL or use default
                institution_code = "01GCL_INST"  # Default for Grinnell
            
            self.log(f"  Institution code: {institution_code}")
            
            # Alma's file upload requires multipart/form-data with specific fields
            # The 'path' field must start with institution_code/upload/
            upload_path = f"{institution_code}/upload/{upload_filename}"
            
            self.log(f"  Upload path: {upload_path}")
            self.log(f"  Using MIME type: {mime_type}")
            
            # Read file content into memory (matches pattern used in _upload_jpg_representation)
            try:
                with open(file_to_upload, 'rb') as f:
                    file_content = f.read()
                
                file_size_kb = len(file_content) / 1024
                self.log(f"  Upload file size: {len(file_content)} bytes ({file_size_kb:.2f} KB)")
                
                # Prepare multipart form data
                files_data = {
                    'file': (upload_filename, file_content, mime_type)
                }
                
                data = {
                    'path': upload_path
                }
                
                headers_upload = {
                    'Authorization': f'apikey {self.api_key}',
                    'Accept': 'application/json'
                }
                
                upload_response = requests.post(files_url, headers=headers_upload, files=files_data, data=data)
                
                self.log(f"  Upload response status: {upload_response.status_code}")
                if upload_response.status_code not in [200, 201]:
                    self.log(f"  Upload response body: {upload_response.text}", logging.ERROR)
                    return False, f"Failed to upload file: HTTP {upload_response.status_code} - {upload_response.text}"
                
                self.log(f"Successfully uploaded {upload_filename} as thumbnail representation {rep_id}")
                return True, f"Thumbnail uploaded successfully (Rep ID: {rep_id})"
            
            finally:
                # Clean up temporary JPEG file if it was created
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                        self.log(f"  Cleaned up temporary file: {temp_file_path}", logging.DEBUG)
                    except Exception as cleanup_error:
                        self.log(f"  Warning: Could not delete temporary file {temp_file_path}: {cleanup_error}", logging.WARNING)
            
        except Exception as e:
            self.log(f"Exception in _upload_thumbnail_representation: {str(e)}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            # Clean up temp file if it exists
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            return False, f"Error uploading thumbnail: {str(e)}"
    
    def _prepare_thumbnail_representation(self, mms_id: str, thumbnail_path: str, filename: str, identifier: str, output_dir) -> tuple[bool, dict]:
        """
        Create a thumbnail representation and prepare the file (without uploading).
        
        This creates a representation with usage_type DERIVATIVE_COPY, processes the thumbnail
        (PNG->JPEG conversion, optimization), and saves it to the output directory.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            thumbnail_path: Full path to the thumbnail file
            filename: Original filename (for logging only)
            identifier: Clean identifier like 'grinnell_12205' or 'dg_12205'
            output_dir: Path object for output directory
            
        Returns:
            tuple: (success: bool, result: dict or error_message: str)
                   result dict contains: {'rep_id': str, 'processed_file': str, 'message': str}
        """
        from pathlib import Path
        temp_file_path = None  # Initialize temp file tracking
        
        # Create a clean upload filename from identifier
        # Example: grinnell_12205 -> grinnell_12205_thumbnail.jpg
        if identifier:
            clean_upload_name = f"{identifier}_thumbnail.jpg"
        else:
            # Fallback to sanitized version of original filename
            clean_upload_name = filename.replace('.mp3', '').replace('.clientThumb', '_thumbnail')
            if not clean_upload_name.endswith('.jpg'):
                clean_upload_name += '.jpg'
        
        try:
            self.log(f"Starting thumbnail preparation for MMS {mms_id}")
            self.log(f"  Source file: {filename}")
            self.log(f"  Path: {thumbnail_path}")
            
            # Verify file exists before attempting processing
            if not Path(thumbnail_path).exists():
                return False, f"File not found: {thumbnail_path}"
            
            file_size = Path(thumbnail_path).stat().st_size
            self.log(f"  File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
            
            # Determine actual MIME type by reading file magic bytes (not extension)
            mime_type = 'image/jpeg'  # default
            try:
                with open(thumbnail_path, 'rb') as f:
                    header = f.read(8)
                    if header[:4] == b'\\x89PNG':
                        mime_type = 'image/png'
                    elif header[:3] == b'\\xff\\xd8\\xff':
                        mime_type = 'image/jpeg'
                    else:
                        import mimetypes
                        detected_type, _ = mimetypes.guess_type(thumbnail_path)
                        if detected_type:
                            mime_type = detected_type
            except Exception as e:
                self.log(f"  Warning: Could not detect file type from magic bytes: {e}", logging.WARNING)
            
            self.log(f"  Detected MIME type: {mime_type}")
            
            # Step 1: Convert PNG to JPEG if needed
            file_to_process = thumbnail_path
            
            if mime_type == 'image/png':
                try:
                    from PIL import Image
                    import tempfile
                    
                    self.log(f"  PNG detected - converting to JPEG")
                    
                    img = Image.open(thumbnail_path)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    temp_fd, temp_file_path = tempfile.mkstemp(suffix='.jpg', prefix='thumb_')
                    os.close(temp_fd)
                    
                    img.save(temp_file_path, 'JPEG', quality=95, optimize=True)
                    file_to_process = temp_file_path
                    mime_type = 'image/jpeg'
                    
                    converted_size = Path(temp_file_path).stat().st_size
                    self.log(f"  ✓ Converted to JPEG: {converted_size} bytes ({converted_size / 1024:.2f} KB)")
                    
                except ImportError:
                    self.log(f"  Warning: Pillow library not available", logging.WARNING)
                except Exception as e:
                    self.log(f"  Warning: PNG to JPEG conversion failed: {e}", logging.WARNING)
            
            # Step 2: Optimize file size (ensure under 100KB)
            MAX_SIZE = 100 * 1024  # 100KB
            current_size = Path(file_to_process).stat().st_size
            
            if current_size > MAX_SIZE:
                try:
                    from PIL import Image
                    import tempfile
                    
                    self.log(f"  File size ({current_size / 1024:.2f} KB) exceeds 100KB limit - optimizing")
                    
                    source_image = file_to_process
                    if temp_file_path is None:
                        temp_fd, temp_file_path = tempfile.mkstemp(suffix='.jpg', prefix='thumb_')
                        os.close(temp_fd)
                        file_to_process = temp_file_path
                    
                    img = Image.open(source_image)
                    
                    if img.mode in ('RGBA', 'LA', 'P'):
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Try quality reduction first
                    quality_attempts = [85, 75, 65, 55]
                    optimized = False
                    
                    for quality in quality_attempts:
                        img.save(temp_file_path, 'JPEG', quality=quality, optimize=True)
                        new_size = Path(temp_file_path).stat().st_size
                        if new_size <= MAX_SIZE:
                            self.log(f"  ✓ Optimized to {new_size / 1024:.2f} KB (quality={quality})")
                            optimized = True
                            break
                    
                    # Try resizing if quality reduction wasn't enough
                    if not optimized:
                        self.log(f"    Quality reduction insufficient - resizing image")
                        original_width, original_height = img.size
                        
                        for scale in [0.9, 0.8, 0.7, 0.6, 0.5]:
                            new_width = int(original_width * scale)
                            new_height = int(original_height * scale)
                            resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                            
                            resized.save(temp_file_path, 'JPEG', quality=65, optimize=True)
                            new_size = Path(temp_file_path).stat().st_size
                            
                            if new_size <= MAX_SIZE:
                                self.log(f"  ✓ Resized to {new_width}x{new_height}: {new_size / 1024:.2f} KB")
                                optimized = True
                                break
                    
                    if not optimized:
                        self.log(f"  Warning: Could not reduce file size below 100KB", logging.WARNING)
                
                except Exception as e:
                    self.log(f"  Warning: File size optimization failed: {e}", logging.WARNING)
            
            # Step 3: Check for existing thumbnail representation
            api_url = self._get_alma_api_url()
            rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
            
            headers = {
                'Authorization': f'apikey {self.api_key}',
                'Accept': 'application/json'
            }
            
            # Fetch existing representations
            self.log(f"Checking for existing thumbnail representation for {mms_id}")
            response = requests.get(rep_url, headers=headers)
            
            existing_rep_id = None
            thumbnail_position = None
            total_reps = 0
            
            if response.status_code == 200:
                reps_data = response.json()
                representations = reps_data.get('representation', [])
                total_reps = len(representations)
                
                # Look for existing DERIVATIVE_COPY representation with "Thumbnail" in label
                for idx, rep in enumerate(representations):
                    label = rep.get('label', '')
                    usage_type = rep.get('usage_type', {}).get('value', '')
                    
                    if usage_type == 'DERIVATIVE_COPY' and 'Thumbnail' in label:
                        # Check if this representation has files
                        files = rep.get('files', {})
                        # If files is empty dict or has no file list, consider it empty
                        has_files = False
                        if isinstance(files, dict):
                            file_list = files.get('representation_file', [])
                            if file_list:
                                has_files = True
                        
                        if not has_files:
                            existing_rep_id = rep.get('id')
                            thumbnail_position = idx  # Track position (0-based)
                            self.log(f"  Found existing empty thumbnail representation: {existing_rep_id}")
                            self.log(f"  Position: {idx + 1} of {total_reps} representations")
                            break
            
            # Step 4: Create representation only if one doesn't already exist
            if existing_rep_id:
                rep_id = existing_rep_id
                self.log(f"Reusing existing representation ID: {rep_id}")
                
                # Check position
                if thumbnail_position is not None:
                    if thumbnail_position == 0:
                        self.log(f"  ✓ Thumbnail representation is in first position", logging.INFO)
                    else:
                        self.log(f"  ⚠️ WARNING: Thumbnail representation is at position {thumbnail_position + 1}, not first!", logging.WARNING)
                        self.log(f"  Alma may not use this as the primary thumbnail.", logging.WARNING)
                        self.log(f"  Consider manually reordering representations in Alma UI.", logging.WARNING)
            else:
                # Warn if creating new representation when others already exist
                if total_reps > 0:
                    self.log(f"  ⚠️ NOTE: Creating new thumbnail representation, but {total_reps} representation(s) already exist", logging.WARNING)
                    self.log(f"  The new thumbnail will be placed at the end (position {total_reps + 1})", logging.WARNING)
                    self.log(f"  Alma may not use this as the primary thumbnail.", logging.WARNING)
                    self.log(f"  Consider manually reordering representations in Alma UI after upload.", logging.WARNING)
                
                rep_data = {
                    "label": f"Thumbnail - {clean_upload_name}",
                    "usage_type": {"value": "DERIVATIVE_COPY"},
                    "library": {"value": "MAIN"},
                    "public_note": "Thumbnail image from Digital Grinnell migration (prepared for upload)"
                }
                
                headers_create = {
                    'Authorization': f'apikey {self.api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                
                self.log(f"Creating new thumbnail representation for {mms_id}")
                response = requests.post(rep_url, headers=headers_create, json=rep_data)
                
                if response.status_code not in [200, 201]:
                    self.log(f"  Response body: {response.text}", logging.ERROR)
                    if temp_file_path and os.path.exists(temp_file_path):
                        try:
                            os.remove(temp_file_path)
                        except:
                            pass
                    return False, f"Failed to create representation: HTTP {response.status_code}"
                
                rep_response = response.json()
                rep_id = rep_response.get('id')
                self.log(f"Created representation ID: {rep_id}")
                
                # Confirm positioning
                if total_reps == 0:
                    self.log(f"  ✓ Thumbnail representation created as first (and only) representation", logging.INFO)
            
            # Step 4: Copy processed file to output directory
            import shutil
            output_file = output_dir / clean_upload_name
            shutil.copy2(file_to_process, output_file)
            self.log(f"Saved processed file to: {output_file}")
            
            # Clean up temp file if it exists
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            
            return True, {
                'rep_id': rep_id,
                'processed_file': clean_upload_name,
                'message': f"{'Reused existing' if existing_rep_id else 'Created'} representation and file prepared (Rep ID: {rep_id})"
            }
            
        except Exception as e:
            self.log(f"Exception in _prepare_thumbnail_representation: {str(e)}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            return False, f"Error preparing thumbnail: {str(e)}"
    
    def upload_thumbnails_selenium(self, csv_file_path: str, progress_callback=None) -> tuple[bool, str, int, int]:
        """
        Function 14b: Upload thumbnail files to Alma representations using Selenium
        
        This function reads a CSV file (from Function 14a) containing:
        - mms_id: The MMS ID
        - rep_id: The representation ID
        - filename: Full path to processed thumbnail file
        - original_file: Full path to original file (for reference)
        
        It then uses Selenium to control Firefox and upload each file via the Alma UI.
        
        Args:
            csv_file_path: Path to CSV file from Function 14a
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str, success_count: int, failed_count: int)
        """
        import csv
        from pathlib import Path
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        import time
        
        try:
            self.log(f"Starting Function 14b: Upload Thumbnails via Selenium")
            self.log(f"Reading CSV file: {csv_file_path}")
            
            # Read CSV file
            csv_path = Path(csv_file_path)
            if not csv_path.exists():
                return False, f"CSV file not found: {csv_file_path}", 0, 0
            
            records = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
            
            if not records:
                return False, "No records found in CSV file", 0, 0
            
            self.log(f"Loaded {len(records)} record(s) from CSV")
            
            # Launch Firefox via GeckoDriver for automation
            self.log("Starting Firefox browser for automation...")
            self.log("Note: Selenium will launch a NEW Firefox window (cannot attach to existing sessions)")
            self.log("")
            
            # Configure Firefox options
            try:
                from selenium.webdriver.firefox.service import Service
                
                options = webdriver.FirefoxOptions()
                # Keep browser open after automation for review
                options.set_preference("browser.sessionstore.resume_from_crash", False)
                # Prevent fullscreen mode issues
                options.set_preference("full-screen-api.enabled", False)
                # Disable "Save password" prompts
                options.set_preference("signon.rememberSignons", False)
                # Disable cookie consent banners where possible
                options.set_preference("cookiebanners.service.mode", 2)
                options.set_preference("cookiebanners.service.mode.privateBrowsing", 2)
                # Start with a normal window size (not maximized/fullscreen)
                options.add_argument("--width=1400")
                options.add_argument("--height=1000")
                
                # Create GeckoDriver service
                service = Service()
                
                # Launch Firefox
                self.log("Launching Firefox via GeckoDriver...")
                driver = webdriver.Firefox(service=service, options=options)
                self.log("✓ Firefox launched successfully")
                
                # Navigate to Alma SAML/SSO login page
                target_url = "https://grinnell.alma.exlibrisgroup.com/SAML"
                self.log("Navigating to Alma SSO login page...")
                driver.get(target_url)
                
                self.log("")
                self.log("=" * 70)
                self.log("⏸️  PLEASE LOG INTO ALMA NOW (via Grinnell SSO)")
                self.log("=" * 70)
                self.log("1. Complete the SSO login process in the Firefox window")
                self.log("2. Complete DUO authentication if prompted")
                self.log("3. Wait for the Alma home page to fully load")
                self.log("4. Automation will begin automatically in 60 seconds...")
                self.log("")
                self.log("(If you need more time, the system will pause for 30 more seconds)")
                self.log("(Or use the Kill Switch and restart Function 14b)")
                self.log("")
                
                # Give user time to log in via SSO + DUO
                time.sleep(60)
                
                # Force window to maximize and get focus
                self.log("\nAttempting to focus Firefox window...")
                try:
                    # First, try to bring Firefox to front using AppleScript
                    try:
                        subprocess.run([
                            'osascript', '-e',
                            'tell application "Firefox" to activate'
                        ], capture_output=True, timeout=5)
                        self.log("✓ Firefox activated via AppleScript")
                        time.sleep(0.5)  # Give it a moment to activate
                    except Exception as e:
                        self.log(f"⚠️  AppleScript activation failed: {e}")
                    
                    # Then maximize and focus the window
                    driver.maximize_window()
                    driver.switch_to.window(driver.current_window_handle)
                    driver.execute_script("window.focus();")
                    self.log("✓ Window maximized and focused")
                except Exception as e:
                    self.log(f"⚠️  Could not maximize/focus window: {e}")
                
                # Try to dismiss common popups
                self.log("Attempting to dismiss common popups...")
                try:
                    # Try to dismiss "Stay signed in" dialogs (common selectors)
                    dismiss_scripts = [
                        # Click "No" or "Not now" on stay signed in prompts
                        """
                        var buttons = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
                        for (var i = 0; i < buttons.length; i++) {
                            var text = buttons[i].textContent || buttons[i].value || '';
                            if (text.toLowerCase().includes('no') || 
                                text.toLowerCase().includes('not now') || 
                                text.toLowerCase().includes('dismiss')) {
                                buttons[i].click();
                                break;
                            }
                        }
                        """,
                        # Dismiss cookie banners
                        """
                        var cookieButtons = document.querySelectorAll('[class*="cookie"] button, [id*="cookie"] button');
                        for (var i = 0; i < cookieButtons.length; i++) {
                            var text = cookieButtons[i].textContent || '';
                            if (text.toLowerCase().includes('accept') || 
                                text.toLowerCase().includes('ok') || 
                                text.toLowerCase().includes('agree')) {
                                cookieButtons[i].click();
                                break;
                            }
                        }
                        """
                    ]
                    
                    for script in dismiss_scripts:
                        driver.execute_script(script)
                        time.sleep(0.5)
                    
                    self.log("✓ Popup dismissal attempted")
                except Exception as e:
                    self.log(f"⚠️  Could not dismiss popups: {e}")
                
                # Debug: Log current page info
                current_url = driver.current_url
                self.log(f"\nCurrent URL: {current_url}")
                
                # Save page source for inspection
                page_source = driver.page_source
                debug_file = Path.home() / "Downloads" / f"alma_page_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                self.log(f"📄 Page HTML saved to: {debug_file}")
                self.log("")
                self.log("=" * 70)
                self.log("⚠️  ELEMENT SELECTORS ARE PLACEHOLDERS - NEED UPDATING")
                self.log("=" * 70)
                self.log("To find the correct selectors:")
                self.log("1. In the Firefox window, press F12 to open DevTools")
                self.log("2. Click the Inspector/Select Element tool (arrow icon)")
                self.log("3. Click on the search bar dropdown (search type)")
                self.log("4. Note the 'id' or 'name' attribute in DevTools")
                self.log("5. Update app.py with the correct selectors")
                self.log("")
                self.log(f"Or use the helper script:")
                self.log(f"  python inspect_alma_page.py {debug_file}")
                self.log("=" * 70)
                self.log("")
                
                self.log("Starting automated uploads...")
            except Exception as e:
                return False, f"Could not start Firefox: {str(e)}. Please ensure GeckoDriver is installed (brew install geckodriver).", 0, 0
            
            success_count = 0
            failed_count = 0
            
            try:
                for idx, record in enumerate(records):
                    if self.kill_switch:
                        self.log("Kill switch activated - stopping processing", logging.WARNING)
                        break
                    
                    current = idx + 1
                    if progress_callback:
                        progress_callback(current, len(records))
                    
                    mms_id = record['mms_id']
                    rep_id = record['rep_id']
                    filename = record['filename']
                    
                    self.log(f"\n[{current}/{len(records)}] Processing MMS ID: {mms_id}")
                    self.log(f"  Rep ID: {rep_id}")
                    self.log(f"  File: {filename}")
                    
                    # Verify file exists
                    file_path = Path(filename)
                    if not file_path.exists():
                        self.log(f"  ✗ File not found: {filename}", logging.ERROR)
                        failed_count += 1
                        continue
                    
                    try:
                        # Step 1: Wait for page to be ready
                        self.log("  Step 1: Waiting for Alma page to load...")
                        
                        # Wait for page to be ready
                        try:
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.TAG_NAME, "body"))
                            )
                        except TimeoutException:
                            # If page not ready, user might still be logging in
                            self.log("    ⏸️  Page not ready yet - waiting 30 more seconds for login...")
                            time.sleep(30)
                            # Try again
                            WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.TAG_NAME, "body"))
                            )
                        
                        # NOTE: Skipping search type and search field dropdown configuration
                        # The search bar retains the last used settings ("Digital titles" and "Representation ID")
                        # so we can go directly to entering the search term
                        
                        # # Find search type dropdown and set to "Digital titles"
                        # # COMMENTED OUT: Search bar retains previous settings
                        # try:
                        #     search_type_select = Select(WebDriverWait(driver, 10).until(
                        #         EC.presence_of_element_located((By.ID, "searchType"))
                        #     ))
                        #     search_type_select.select_by_visible_text("Digital titles")
                        #     self.log("    ✓ Set search type to 'Digital titles'")
                        # except:
                        #     self.log("    ⚠️ Could not find search type dropdown - attempting to continue", logging.WARNING)
                        
                        # # Find search field dropdown and set to "Representation PID"
                        # # COMMENTED OUT: Search bar retains previous settings
                        # try:
                        #     search_field_select = Select(WebDriverWait(driver, 5).until(
                        #         EC.presence_of_element_located((By.ID, "searchField"))
                        #     ))
                        #     search_field_select.select_by_visible_text("Representation PID")
                        #     self.log("    ✓ Set search field to 'Representation PID'")
                        # except:
                        #     self.log("    ⚠️ Could not find search field dropdown - attempting to continue", logging.WARNING)
                        
                        # Step 2: Enter representation ID and search
                        self.log(f"  Step 2: Searching for representation {rep_id}...")
                        self.log("    Note: Using previous search settings (Digital titles / Representation ID)")
                        try:
                            search_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "NEW_ALMA_MENU_TOP_NAV_Search_Text"))
                            )
                            search_input.clear()
                            search_input.send_keys(rep_id)
                            self.log("    ✓ Entered representation ID in search field")
                            
                            # Press ENTER to initiate search (instead of clicking button)
                            search_input.send_keys(Keys.RETURN)
                            self.log("    ✓ Search initiated (pressed ENTER)")
                        except TimeoutException:
                            self.log("    ✗ Could not find search input field with id='NEW_ALMA_MENU_TOP_NAV_Search_Text'", logging.ERROR)
                            self.log("    → You need to inspect the page and update the selector in app.py", logging.ERROR)
                            self.log("    → Check the saved HTML file in ~/Downloads/alma_page_debug_*.html", logging.ERROR)
                            raise
                        
                        # Wait for results
                        time.sleep(2)
                        
                        # Step 3: Click on "Digital Representations (X)" link
                        self.log("  Step 3: Opening Digital Representations...")
                        # Note: Using CSS_SELECTOR for multiple classes (CLASS_NAME only supports single class)
                        digital_reps_link = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, ".hep-smart-link-ex-link-content.sel-smart-link-nggeneralsectiontitleall_titles_details_digital_representations.ng-star-inserted"))
                        )
                        digital_reps_link.click()
                        self.log("    ✓ Opened Digital Representations")
                        
                        # Wait for modal/window to appear
                        time.sleep(1)
                        
                        # Step 4: Click on the specific representation ID link
                        self.log(f"  Step 4: Opening representation {rep_id}...")
                        rep_link = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.LINK_TEXT, rep_id))
                        )
                        rep_link.click()
                        self.log("    ✓ Opened representation")
                        
                        # Wait for representation page to load
                        time.sleep(1)
                        
                        # Step 5: Click "Thumbnail Upload" file selector
                        self.log("  Step 5: Uploading thumbnail file...")
                        file_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "thumbnailUpload"))  # TODO: Adjust this selector
                        )
                        file_input.send_keys(str(file_path.absolute()))
                        self.log(f"    ✓ Selected file: {file_path.name}")
                        
                        # Wait for file to be processed
                        time.sleep(2)
                        
                        # Step 6: Click Save button
                        save_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.ID, "saveButton"))  # TODO: Adjust this selector
                        )
                        save_button.click()
                        self.log("    ✓ Clicked Save")
                        
                        # Wait for save to complete
                        time.sleep(2)
                        
                        self.log(f"  ✓ Successfully uploaded thumbnail for {mms_id}")
                        success_count += 1
                        
                    except TimeoutException as e:
                        self.log(f"  ✗ Timeout waiting for page element: {str(e)}", logging.ERROR)
                        self.log(f"    This may indicate the page structure has changed or the page didn't load in time", logging.ERROR)
                        failed_count += 1
                    except NoSuchElementException as e:
                        self.log(f"  ✗ Could not find required element: {str(e)}", logging.ERROR)
                        failed_count += 1
                    except Exception as e:
                        self.log(f"  ✗ Error uploading thumbnail: {str(e)}", logging.ERROR)
                        import traceback
                        self.log(traceback.format_exc(), logging.DEBUG)
                        failed_count += 1
                
            finally:
                # Note: We don't close the driver since we're using an existing session
                self.log("\n⚠️ NOTE: Firefox browser has been left open for your review")
                self.log("You can manually close Firefox when done reviewing the results")
            
            message = f"Thumbnail upload complete: {success_count} uploaded, {failed_count} failed"
            self.log(message)
            
            if failed_count > 0:
                self.log(f"⚠️ {failed_count} upload(s) failed - check logs for details", logging.WARNING)
            
            return True, message, success_count, failed_count
            
        except Exception as e:
            error_msg = f"Error in selenium upload: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False, error_msg, 0, 0
    
    def process_tiffs_for_import(self, mms_ids: list, tiff_csv: str = "all_single_tiffs_with_local_paths.csv",
                                  alma_export_csv: str = None, for_import_dir: str = "For-Import",
                                  progress_callback=None) -> tuple[bool, str]:
        """
        Function 12: Process TIFF files for import
        
        For each MMS ID:
        1. Look up Local Path in tiff_csv
        2. Copy TIFF to For-Import directory
        3. Create JPG derivative
        4. Update alma_export CSV with filenames
        
        Args:
            mms_ids: List of MMS IDs to process
            tiff_csv: CSV file with MMS ID and Local Path columns (default: "all_single_tiffs_with_local_paths.csv")
            alma_export_csv: CSV to update with file names (if None, generates timestamped filename)
            for_import_dir: Directory for output files (default: "For-Import")
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str)
        """
        import csv
        import shutil
        from pathlib import Path
        from datetime import datetime
        
        self.log(f"Starting Function 12: Process TIFFs for Import")
        self.log(f"Processing {len(mms_ids)} MMS ID(s)")
        
        # Check if Pillow is available
        try:
            from PIL import Image
        except ImportError:
            return False, "Pillow library not installed. Run: pip install Pillow"
        
        # Verify tiff_csv exists
        if not Path(tiff_csv).exists():
            return False, f"TIFF CSV not found: {tiff_csv}"
        
        # Generate alma_export_csv filename if not provided
        if not alma_export_csv:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            alma_export_csv = f"alma_export_{timestamp}.csv"
            self.log(f"Generated output filename: {alma_export_csv}")
        
        # Create For-Import directory
        import_path = Path(for_import_dir)
        import_path.mkdir(exist_ok=True)
        self.log(f"Created/verified directory: {import_path}")
        
        try:
            # Read tiff_csv to get local paths
            self.log(f"Reading TIFF paths from {tiff_csv}")
            tiff_paths = {}
            with open(tiff_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mms_id = row.get('MMS ID', '').strip()
                    local_path = row.get('Local Path', '').strip()
                    if mms_id and local_path:
                        tiff_paths[mms_id] = local_path
            
            self.log(f"Found {len(tiff_paths)} records with local paths")
            
            # Read or create alma_export CSV
            alma_rows = []
            alma_fieldnames = []
            
            if Path(alma_export_csv).exists():
                self.log(f"Reading existing {alma_export_csv}")
                with open(alma_export_csv, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    alma_fieldnames = list(reader.fieldnames)
                    alma_rows = list(reader)
            else:
                # Create new CSV structure
                self.log(f"Creating new {alma_export_csv}")
                # Use column headings from export function
                alma_fieldnames = ['mms_id', 'file_name_1', 'file_name_2']
            
            # Create MMS ID to row index mapping
            mms_to_index = {row.get('mms_id', ''): idx for idx, row in enumerate(alma_rows)}
            
            # Process each MMS ID
            processed_count = 0
            updated_count = 0
            failed_count = 0
            no_path_count = 0
            total = len(mms_ids)
            
            for idx, mms_id in enumerate(mms_ids, 1):
                if self.kill_switch:
                    self.log("Operation cancelled by user", logging.WARNING)
                    break
                
                if progress_callback:
                    progress_callback(idx, total)
                
                self.log(f"\nProcessing {idx}/{total}: MMS {mms_id}")
                
                # Check if we have a local path for this MMS ID
                if mms_id not in tiff_paths:
                    self.log(f"  ✗ No local path found in {tiff_csv}", logging.WARNING)
                    no_path_count += 1
                    continue
                
                local_path = tiff_paths[mms_id]
                source_tiff = Path(local_path)
                
                # Check if source file exists
                if not source_tiff.exists():
                    self.log(f"  ✗ File not found: {local_path}", logging.ERROR)
                    failed_count += 1
                    continue
                
                # Get filenames
                tiff_filename = source_tiff.name
                jpg_filename = tiff_filename.replace('.tiff', '.jpg').replace('.tif', '.jpg')
                
                dest_tiff = import_path / tiff_filename
                dest_jpg = import_path / jpg_filename
                
                # Copy TIFF file
                self.log(f"  Copying TIFF: {tiff_filename}")
                try:
                    shutil.copy2(source_tiff, dest_tiff)
                    self.log(f"    ✓ Copied to {dest_tiff}")
                except (OSError, IOError) as e:
                    self.log(f"    ✗ Copy failed: {str(e)}", logging.ERROR)
                    failed_count += 1
                    continue
                
                # Create JPG derivative
                self.log(f"  Creating JPG: {jpg_filename}")
                try:
                    with Image.open(source_tiff) as img:
                        # Handle 16-bit images (I, I;16, I;16B) - convert to 8-bit first
                        if img.mode in ('I', 'I;16', 'I;16B', 'I;16L', 'I;16N'):
                            # Properly scale 16-bit to 8-bit by dividing by 256
                            img = img.point(lambda x: x / 256).convert('L').convert('RGB')
                        # Convert to RGB if necessary
                        elif img.mode in ('RGBA', 'LA', 'P'):
                            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                            img = rgb_img
                        elif img.mode == 'L':
                            # Grayscale to RGB
                            img = img.convert('RGB')
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # Save as JPG with high quality
                        img.save(dest_jpg, 'JPEG', quality=95, optimize=True)
                        self.log(f"    ✓ Created JPG at {dest_jpg}")
                except Exception as e:
                    self.log(f"    ✗ JPG creation failed: {str(e)}", logging.ERROR)
                    failed_count += 1
                    continue
                
                # Update or create alma_export row
                if mms_id in mms_to_index:
                    # Update existing row
                    row_idx = mms_to_index[mms_id]
                    alma_rows[row_idx]['file_name_1'] = jpg_filename
                    alma_rows[row_idx]['file_name_2'] = tiff_filename
                    self.log(f"  Updated existing CSV row")
                else:
                    # Create new row
                    new_row = {field: '' for field in alma_fieldnames}
                    new_row['mms_id'] = mms_id
                    new_row['file_name_1'] = jpg_filename
                    new_row['file_name_2'] = tiff_filename
                    alma_rows.append(new_row)
                    mms_to_index[mms_id] = len(alma_rows) - 1
                    self.log(f"  Created new CSV row")
                
                updated_count += 1
                processed_count += 1
            
            # Write updated alma_export CSV
            if updated_count > 0:
                self.log(f"Writing updated {alma_export_csv}...")
                with open(alma_export_csv, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=alma_fieldnames)
                    writer.writeheader()
                    writer.writerows(alma_rows)
                self.log(f"✓ Updated {updated_count} records in {alma_export_csv}")
            
            result_msg = f"Function 12 complete: {processed_count} TIFFs processed, {updated_count} CSV rows updated in {alma_export_csv}, {failed_count} failed, {no_path_count} no path"
            self.log(result_msg)
            self.log(f"Files saved to: {import_path.absolute()}")
            
            return True, result_msg
            
        except Exception as e:
            error_msg = f"Error in Function 12: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False, error_msg
    
    def _get_alma_domain(self) -> str:
        """
        Get the Alma domain for the institution.
        Returns the domain part of the Alma URL (e.g., 'grinnell' from grinnell.alma.exlibrisgroup.com)
        """
        # Try to extract from environment or use a default
        # For institutions without custom domains, this would need to be configured
        alma_domain = os.getenv('ALMA_DOMAIN', 'na01')  # Default to North America regional
        return alma_domain
    
    def _get_institution_code(self) -> str:
        """
        Get the institution code (e.g., '01GRINNELL_INST').
        Required for regional/sandbox IIIF URLs.
        """
        institution_code = os.getenv('ALMA_INSTITUTION_CODE', '')
        return institution_code


def main(page: ft.Page):
    """Main Flet application"""
    logger.info("Starting Flet application")
    page.title = "🚕 CABB - Crunch Alma Bibs in Bulk"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    
    # Set window size - try both properties
    page.window.height = 1000
    page.window.width = 1100
    page.window.resizable = True
    
    page.scroll = ft.ScrollMode.AUTO  # Enable vertical scrolling if needed
    
    # Initialize persistent storage
    storage = PersistentStorage()
    logger.info("Persistent storage initialized")
    
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
    
    # Input fields - restore from persistent storage
    mms_id_input = ft.TextField(
        label="MMS ID",
        hint_text="Enter bibliographic record MMS ID",
        width=400,
        value=storage.get_ui_state("mms_id"),
        on_change=lambda e: storage.set_ui_state("mms_id", e.control.value)
    )
    
    set_id_input = ft.TextField(
        label="Set ID or CSV Path",
        hint_text="Enter Alma Set ID or path to CSV file",
        width=300,
        value=storage.get_ui_state("set_id"),
        on_change=lambda e: storage.set_ui_state("set_id", e.control.value)
    )
    
    limit_input = ft.TextField(
        label="Limit",
        hint_text="Max records to process",
        value=storage.get_ui_state("limit", "0"),
        width=100,
        keyboard_type=ft.KeyboardType.NUMBER,
        tooltip="Enter 0 for no limit, positive N for first N records, or negative -N for last N records",
        on_change=lambda e: storage.set_ui_state("limit", e.control.value)
    )
    
    # Set members display
    def load_dcap01_set(e):
        """Load the DCAP01 set ID into the input field"""
        set_id_input.value = "7071087320004641"
        page.update()
        add_log_message("DCAP01 set ID loaded into Set ID field")
    
    set_info_text = ft.Row([
        ft.Text("No set loaded - All Digital Titles in DCAP01 Format set ID is: ", size=12, color=ft.Colors.GREY_700),
        ft.TextButton(
            "7071087320004641",
            on_click=load_dcap01_set,
            style=ft.ButtonStyle(padding=0),
            tooltip="Click to load this Set ID"
        )
    ], spacing=0)
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
        """Handle Load Set button click - supports both Set ID and CSV file"""
        logger.info("Load Set button clicked")
        if not set_id_input.value:
            update_status("Please enter a Set ID or select a CSV file", True)
            return
        
        input_value = set_id_input.value.strip()
        
        # Determine if input is a CSV file path or Set ID
        is_csv = input_value.endswith('.csv') or '/' in input_value or '\\' in input_value
        
        if is_csv:
            # Load from CSV file
            add_log_message(f"Loading MMS IDs from CSV: {input_value}")
            
            # Show progress
            set_progress_bar.visible = True
            set_progress_text.visible = True
            set_progress_bar.value = None
            set_progress_text.value = "Loading CSV..."
            page.update()
            
            success, message, members = editor.load_mms_ids_from_csv(input_value)
            
            # Hide progress
            set_progress_bar.visible = False
            set_progress_text.visible = False
            
            if not success:
                update_status(message, True)
                return
            
            # Get limit value
            try:
                limit = int(limit_input.value) if limit_input.value else 0
            except ValueError:
                update_status("Invalid limit value - using 0 (no limit)", True)
                limit = 0
            
            # Apply limit if set
            if limit > 0 and len(members) > limit:
                # Positive limit: take first N records
                editor.set_members = members[:limit]
                set_info_text.controls = [ft.Text(f"CSV: {input_value.split('/')[-1]} (first {limit} of {len(members)} IDs loaded)", size=12, color=ft.Colors.GREY_700)]
            elif limit < 0 and abs(limit) <= len(members):
                # Negative limit: take last N records
                editor.set_members = members[limit:]
                set_info_text.controls = [ft.Text(f"CSV: {input_value.split('/')[-1]} (last {abs(limit)} of {len(members)} IDs loaded)", size=12, color=ft.Colors.GREY_700)]
            elif limit < 0:
                # Negative limit larger than total: take all records
                set_info_text.controls = [ft.Text(f"CSV: {input_value.split('/')[-1]} ({len(members)} IDs - limit exceeds total)", size=12, color=ft.Colors.GREY_700)]
            else:
                set_info_text.controls = [ft.Text(f"CSV: {input_value.split('/')[-1]} ({len(members)} IDs)", size=12, color=ft.Colors.GREY_700)]
            
            page.update()
            update_status(f"Loaded {len(editor.set_members)} MMS IDs from CSV", False)
            
        else:
            # Load from Alma Set
            # Get limit value
            try:
                limit = int(limit_input.value) if limit_input.value else 0
            except ValueError:
                update_status("Invalid limit value - using 0 (no limit)", True)
                limit = 0
            
            # For negative limits, we need to fetch ALL members then slice
            # For positive limits, we can limit at the API level
            original_limit = limit
            if limit > 0:
                api_limit = limit  # Positive: fetch only first N
            else:
                api_limit = 0  # Zero or negative: fetch all
            
            limit_msg = "none" if limit == 0 else (f"first {limit}" if limit > 0 else f"last {abs(limit)}")
            add_log_message(f"Loading set: {input_value} (limit: {limit_msg})")
            
            # Show indeterminate progress bar while fetching set details
            set_progress_bar.visible = True
            set_progress_text.visible = True
            set_progress_bar.value = None  # Indeterminate progress
            set_progress_text.value = "Fetching set details..."
            page.update()
            
            # Fetch set details
            success, message, set_data = editor.fetch_set_details(input_value)
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
                input_value, 
                progress_callback=update_progress,
                max_members=api_limit
            )
            if not success:
                set_progress_bar.visible = False
                set_progress_text.visible = False
                update_status(member_msg, True)
                return
            
            # Apply negative limit if specified (take last N records)
            if original_limit < 0 and abs(original_limit) <= len(members):
                editor.set_members = members[original_limit:]
                members = editor.set_members
            
            # Update set info display
            set_name = set_data.get('name', 'Unknown')
            member_count = len(members)
            if original_limit > 0 and member_count >= original_limit:
                set_info_text.controls = [ft.Text(f"Set: {set_name} (first {member_count} of {original_limit} members loaded)", size=12, color=ft.Colors.GREY_700)]
            elif original_limit < 0:
                set_info_text.controls = [ft.Text(f"Set: {set_name} (last {member_count} members loaded)", size=12, color=ft.Colors.GREY_700)]
            else:
                set_info_text.controls = [ft.Text(f"Set: {set_name} ({member_count} members)", size=12, color=ft.Colors.GREY_700)]
            
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
        set_info_text.controls = [
            ft.Text("No set loaded - All Digital Titles in DCAP01 Format set ID is: ", size=12, color=ft.Colors.GREY_700),
            ft.TextButton(
                "7071087320004641",
                on_click=load_dcap01_set,
                style=ft.ButtonStyle(padding=0),
                tooltip="Click to load this Set ID"
            )
        ]
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
        storage.record_function_usage("function_1_fetch_xml")
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        add_log_message(f"Fetching XML for MMS ID: {mms_id_input.value}")
        success, message = editor.fetch_and_display_xml(mms_id_input.value, page)
        update_status(message, not success)
    
    def on_function_2_click(e):
        """Handle Function 2: Clear dc:relation collections"""
        logger.info("Function 2 button clicked")
        
        def execute_function_2():
            """Execute Function 2 after confirmation"""
            storage.record_function_usage("function_2_clear_dc_relation")
            
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
        
        # Show confirmation dialog
        def confirm_action(e):
            dialog.open = False
            page.update()
            execute_function_2()
        
        def cancel_action(e):
            dialog.open = False
            page.update()
            update_status("Operation cancelled by user", False)
        
        # Determine warning message based on single or batch
        if editor.set_members:
            member_count = len(editor.set_members)
            try:
                limit = int(limit_input.value) if limit_input.value else 0
            except ValueError:
                limit = 0
            
            process_count = min(limit, member_count) if limit > 0 else member_count
            warning_msg = f"⚠️ WARNING: This will modify {process_count} bibliographic record(s) in Alma.\n\nFunction: Clear dc:relation Collections Fields\n\nThis action will PERMANENTLY remove matching dc:relation fields from the records.\n\nDo you want to continue?"
        else:
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            warning_msg = f"⚠️ WARNING: This will modify the bibliographic record in Alma.\n\nMMS ID: {mms_id_input.value}\nFunction: Clear dc:relation Collections Fields\n\nThis action will PERMANENTLY remove matching dc:relation fields.\n\nDo you want to continue?"
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirm Data Modification", weight=ft.FontWeight.BOLD),
            content=ft.Text(warning_msg, size=14),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_action),
                ft.TextButton("Proceed", on_click=confirm_action, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(dialog)
    
    def on_function_3_click(e):
        """Handle Function 3 click - Export set to CSV"""
        logger.info("Function 3 button clicked - Export to CSV")
        storage.record_function_usage("function_3_export_csv")
        
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
        """Handle Function 4 click - Filter CSV for records 95+ years old"""
        logger.info("Function 4 button clicked - Filter CSV")
        storage.record_function_usage("function_4_filter_pre1930")
        
        from datetime import datetime
        cutoff_year = datetime.now().year - 95
        add_log_message(f"Filtering latest CSV export for records 95+ years old (≤{cutoff_year})")
        success, message = editor.filter_csv_by_pre1930_dates()
        update_status(message, not success)
        if success:
            add_log_message("CSV filtering complete")
    
    def on_function_5_click(e):
        """Handle Function 5 click - Get IIIF Manifest"""
        logger.info("Function 5 button clicked - Get IIIF Manifest")
        storage.record_function_usage("function_5_iiif")
        
        # Get MMS ID from input or use loaded set
        mms_id = mms_id_input.value
        
        if not mms_id:
            update_status("Please enter an MMS ID", True)
            return
        
        add_log_message(f"Retrieving IIIF manifest for MMS ID: {mms_id}")
        success, message = editor.get_iiif_manifest_and_canvas(mms_id)
        update_status(message, not success)
        if success:
            add_log_message("IIIF manifest retrieved successfully")
    
    def on_function_6_click(e):
        """Handle Function 6 click - Replace Author Copyright Rights"""
        logger.info("Function 6 button clicked - Replace Author Copyright Rights")
        
        def execute_function_6():
            """Execute Function 6 after confirmation"""
            storage.record_function_usage("function_6_replace_rights")
            
            # Check if processing a batch or single record
            if editor.set_members and len(editor.set_members) > 0:
                # Batch processing
                add_log_message(f"Starting batch replace_author_copyright_rights for {len(editor.set_members)} records")
                
                # Get limit
                try:
                    limit = int(limit_input.value) if limit_input.value else 0
                    if limit < 0:
                        limit = 0
                except ValueError:
                    limit = 0
                
                # Calculate how many to process
                member_count = len(editor.set_members)
                process_count = min(limit, member_count) if limit > 0 else member_count
                
                # Show progress bar
                set_progress_bar.visible = True
                set_progress_text.visible = True
                set_progress_bar.value = 0
                set_progress_text.value = f"Processing 0/{process_count}"
                page.update()
                
                total_count = 0
                replaced_count = 0
                added_count = 0
                removed_duplicates_count = 0
                no_change_count = 0
                error_count = 0
                
                for i, mms_id in enumerate(editor.set_members[:process_count], 1):
                    if editor.kill_switch:
                        add_log_message("Batch processing stopped by user")
                        break
                    
                    total_count += 1
                    
                    # Update progress
                    set_progress_bar.value = i / process_count
                    set_progress_text.value = f"Processing {i}/{process_count}: {mms_id}"
                    page.update()
                    
                    success, message, outcome = editor.replace_author_copyright_rights(mms_id)
                    if success:
                        if outcome == "replaced":
                            replaced_count += 1
                            add_log_message(f"✓ {mms_id}: {message}")
                        elif outcome == "added":
                            added_count += 1
                            add_log_message(f"+ {mms_id}: {message}")
                        elif outcome == "removed_duplicates":
                            removed_duplicates_count += 1
                            add_log_message(f"◆ {mms_id}: {message}")
                        elif outcome == "no_change":
                            no_change_count += 1
                            add_log_message(f"⊘ {mms_id}: {message}")
                    else:
                        error_count += 1
                        add_log_message(f"✗ {mms_id}: {message}")
                
                # Hide progress bar
                set_progress_bar.visible = False
                set_progress_text.visible = False
                
                # Build detailed summary
                summary = f"Batch complete ({total_count} records): {replaced_count} replaced, {added_count} added, {removed_duplicates_count} duplicates removed, {no_change_count} no change, {error_count} errors"
                if limit > 0 and limit < member_count:
                    summary += f" (limited from {member_count} total)"
                update_status(summary, error_count > 0)
            else:
                # Single record processing
                if not mms_id_input.value:
                    update_status("Please enter an MMS ID or load a set", True)
                    return
                
                add_log_message(f"Starting replace_author_copyright_rights for MMS ID: {mms_id_input.value}")
                success, message, outcome = editor.replace_author_copyright_rights(mms_id_input.value)
                update_status(message, not success)
        
        # Show confirmation dialog
        def confirm_action(e):
            dialog.open = False
            page.update()
            execute_function_6()
        
        def cancel_action(e):
            dialog.open = False
            page.update()
            update_status("Operation cancelled by user", False)
        
        # Determine warning message based on single or batch
        if editor.set_members and len(editor.set_members) > 0:
            member_count = len(editor.set_members)
            try:
                limit = int(limit_input.value) if limit_input.value else 0
                if limit < 0:
                    limit = 0
            except ValueError:
                limit = 0
            
            process_count = min(limit, member_count) if limit > 0 else member_count
            warning_msg = f"⚠️ WARNING: This will modify {process_count} bibliographic record(s) in Alma.\n\nFunction: Replace old dc:rights with Public Domain link\n\nThis action will PERMANENTLY modify dc:rights fields in the records.\n\nDo you want to continue?"
        else:
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            warning_msg = f"⚠️ WARNING: This will modify the bibliographic record in Alma.\n\nMMS ID: {mms_id_input.value}\nFunction: Replace old dc:rights with Public Domain link\n\nThis action will PERMANENTLY modify dc:rights fields.\n\nDo you want to continue?"
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirm Data Modification", weight=ft.FontWeight.BOLD),
            content=ft.Text(warning_msg, size=14),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_action),
                ft.TextButton("Proceed", on_click=confirm_action, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(dialog)
    
    def on_function_7_click(e):
        """Handle Function 7 click - Add Grinnell: dc:identifier"""
        logger.info("Function 7 button clicked - Add Grinnell: dc:identifier")
        
        def execute_function_7():
            """Execute Function 7 after confirmation"""
            storage.record_function_usage("function_7_add_grinnell_id")
            
            # Check if processing a batch or single record
            if editor.set_members and len(editor.set_members) > 0:
                # Batch processing
                add_log_message(f"Starting batch add_grinnell_identifier for {len(editor.set_members)} records")
                
                # Get limit
                try:
                    limit = int(limit_input.value) if limit_input.value else 0
                    if limit < 0:
                        limit = 0
                except ValueError:
                    limit = 0
                
                # Calculate how many to process
                member_count = len(editor.set_members)
                process_count = min(limit, member_count) if limit > 0 else member_count
                
                # Show progress bar
                set_progress_bar.visible = True
                set_progress_text.visible = True
                set_progress_bar.value = 0
                set_progress_text.value = f"Processing 0/{process_count}"
                page.update()
                
                success_count = 0
                error_count = 0
                skipped_count = 0
                
                for i, mms_id in enumerate(editor.set_members[:process_count], 1):
                    if editor.kill_switch:
                        add_log_message("Batch processing stopped by user")
                        break
                    
                    # Update progress
                    set_progress_bar.value = i / process_count
                    set_progress_text.value = f"Processing {i}/{process_count}: {mms_id}"
                    page.update()
                    
                    success, message = editor.add_grinnell_identifier(mms_id)
                    if success:
                        if "already exists" in message or "No dg_" in message:
                            skipped_count += 1
                            add_log_message(f"⊘ {mms_id}: {message}")
                        else:
                            success_count += 1
                            add_log_message(f"✓ {mms_id}: {message}")
                    else:
                        error_count += 1
                        add_log_message(f"✗ {mms_id}: {message}")
                
                # Hide progress bar
                set_progress_bar.visible = False
                set_progress_text.visible = False
                
                summary = f"Batch complete: {success_count} added, {skipped_count} skipped, {error_count} failed out of {process_count} records"
                if limit > 0 and limit < member_count:
                    summary += f" (limited from {member_count} total)"
                update_status(summary, error_count > 0)
            else:
                # Single record processing
                if not mms_id_input.value:
                    update_status("Please enter an MMS ID or load a set", True)
                    return
                
                add_log_message(f"Starting add_grinnell_identifier for MMS ID: {mms_id_input.value}")
                success, message = editor.add_grinnell_identifier(mms_id_input.value)
                update_status(message, not success)
        
        # Show confirmation dialog
        def confirm_action(e):
            dialog.open = False
            page.update()
            execute_function_7()
        
        def cancel_action(e):
            dialog.open = False
            page.update()
            update_status("Operation cancelled by user", False)
        
        # Determine warning message based on single or batch
        if editor.set_members and len(editor.set_members) > 0:
            member_count = len(editor.set_members)
            try:
                limit = int(limit_input.value) if limit_input.value else 0
                if limit < 0:
                    limit = 0
            except ValueError:
                limit = 0
            
            process_count = min(limit, member_count) if limit > 0 else member_count
            warning_msg = f"⚠️ WARNING: This will modify {process_count} bibliographic record(s) in Alma.\n\nFunction: Add Grinnell: dc:identifier Field As Needed\n\nThis action will PERMANENTLY add dc:identifier fields to records with dg_ identifiers.\n\nDo you want to continue?"
        else:
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            warning_msg = f"⚠️ WARNING: This will modify the bibliographic record in Alma.\n\nMMS ID: {mms_id_input.value}\nFunction: Add Grinnell: dc:identifier Field As Needed\n\nThis action will PERMANENTLY add a dc:identifier field if a dg_ identifier exists.\n\nDo you want to continue?"
        
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirm Data Modification", weight=ft.FontWeight.BOLD),
            content=ft.Text(warning_msg, size=14),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_action),
                ft.TextButton("Proceed", on_click=confirm_action, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(dialog)
    
    def on_function_8_click(e):
        """Handle Function 8: Export Identifier CSV"""
        if not editor.set_members or len(editor.set_members) == 0:
            update_status("Please load a set first", True)
            return
        
        # Generate timestamped filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"identifier_export_{timestamp}.csv"
        
        add_log_message(f"Starting identifier export to {output_file}")
        update_status(f"Exporting identifiers for {len(editor.set_members)} records...", False)
        
        def progress_update(current, total):
            progress = current / total
            set_progress_bar.value = progress
            status_text.value = f"Exporting identifiers: {current}/{total} records ({progress*100:.1f}%)"
            page.update()
        
        # Export to CSV
        success, message = editor.export_identifier_csv(
            editor.set_members,
            output_file,
            progress_callback=progress_update
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message(f"Identifier CSV export complete: {output_file}")
    
    def on_function_9_click(e):
        """Handle Function 9: Validate Handle URLs"""
        if not editor.set_members or len(editor.set_members) == 0:
            update_status("Please load a set first", True)
            return
        
        # Generate timestamped filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"handle_validation_{timestamp}.csv"
        
        add_log_message(f"Starting Handle validation to {output_file}")
        update_status(f"⚠️ This will make HTTP requests to each Handle URL. Validating {len(editor.set_members)} records...", False)
        
        def progress_update(current, total):
            progress = current / total
            set_progress_bar.value = progress
            status_text.value = f"Validating Handles: {current}/{total} records ({progress*100:.1f}%)"
            page.update()
        
        # Validate Handles
        success, message = editor.validate_handles_to_csv(
            editor.set_members,
            output_file,
            progress_callback=progress_update
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message("Handle validation complete")
            add_log_message("💡 Tip: Filter the CSV by 'HTTP Status Code' ≠ 200 to find problems")
    
    def on_function_10_click(e):
        """Handle Function 10: Export for Review"""
        if not editor.set_members or len(editor.set_members) == 0:
            update_status("Please load a set first", True)
            return
        
        # Generate timestamped filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"Exported_for_Review_{timestamp}.csv"
        
        add_log_message(f"Starting review export to {output_file}")
        update_status(f"Exporting {len(editor.set_members)} records for review...", False)
        
        # Show progress bar
        set_progress_bar.visible = True
        set_progress_bar.value = 0
        set_progress_text.visible = True
        set_progress_text.value = f"Processing: 0/{len(editor.set_members)} records"
        page.update()
        
        def progress_update(current, total):
            progress = current / total
            set_progress_bar.value = progress
            set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
            status_text.value = f"Exporting for review: {current}/{total} records ({progress*100:.1f}%)"
            page.update()
        
        # Export to CSV
        storage.record_function_usage("function_10_export_review")
        success, message = editor.export_for_review_csv(
            editor.set_members,
            output_file,
            progress_callback=progress_update
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message(f"Review export complete: {output_file}")
            add_log_message("💡 Tip: Open in Excel/Sheets - Handle column will be clickable")
    
    def on_function_11_click(e):
        """Handle Function 11: Identify Single TIFF Representations"""
        # Determine if processing single MMS ID or set
        if not editor.set_members or len(editor.set_members) == 0:
            # Try single MMS ID
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            mms_ids = [mms_id_input.value.strip()]
            add_log_message(f"Analyzing single MMS ID: {mms_ids[0]}")
        else:
            mms_ids = editor.set_members
            add_log_message(f"Analyzing {len(mms_ids)} records from set")
        
        # Generate timestamped filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"single_tiff_objects_{timestamp}.csv"
        
        add_log_message(f"Identifying objects with single TIFF representations...")
        update_status(f"Analyzing {len(mms_ids)} record(s)...", False)
        
        # Show progress bar
        set_progress_bar.visible = True
        set_progress_bar.value = 0
        set_progress_text.visible = True
        set_progress_text.value = f"Processing: 0/{len(editor.set_members)} records"
        page.update()
        
        def progress_update(current, total):
            progress = current / total
            set_progress_bar.value = progress
            set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
            status_text.value = f"Analyzing representations: {current}/{total} records ({progress*100:.1f}%)"
            page.update()
        
        # Identify single TIFF objects
        storage.record_function_usage("function_11_identify_single_tiff")
        success, message = editor.identify_single_tiff_objects(
            mms_ids,
            output_file,
            progress_callback=progress_update,
            create_jpg=False
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message(f"Single TIFF analysis complete: {output_file}")
            add_log_message("💡 Tip: Use Alma's derivative creation tools or download TIFFs manually for JPG conversion")
    
    def on_function_12_click(e):
        """Handle Function 12: Process TIFFs for Import"""
        # Determine if processing single MMS ID or set
        if not editor.set_members or len(editor.set_members) == 0:
            # Try single MMS ID mode
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            mms_ids = [mms_id_input.value.strip()]
            add_log_message(f"Processing single MMS ID: {mms_ids[0]}")
        else:
            mms_ids = editor.set_members
            add_log_message(f"Processing {len(mms_ids)} records from set")
        
        # Get optional CSV path from Set ID field (only if it looks like a file path)
        alma_export_csv = None
        if set_id_input.value:
            value = set_id_input.value.strip()
            # Only use as CSV path if it has .csv extension or contains path separators
            if '.csv' in value.lower() or '/' in value or '\\' in value:
                alma_export_csv = value
        
        add_log_message(f"Function 12: Processing TIFFs for Import...")
        update_status(f"Processing {len(mms_ids)} record(s)...", False)
        
        # Show progress bar
        set_progress_bar.visible = True
        set_progress_bar.value = 0
        set_progress_text.visible = True
        set_progress_text.value = f"Processing: 0/{len(mms_ids)} records"
        page.update()
        
        def progress_update(current, total):
            progress = current / total
            set_progress_bar.value = progress
            set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
            status_text.value = f"Processing TIFFs: {current}/{total} records ({progress*100:.1f}%)"
            page.update()
        
        # Process TIFFs
        storage.record_function_usage("function_12_process_tiffs")
        success, message = editor.process_tiffs_for_import(
            mms_ids,
            tiff_csv="all_single_tiffs_with_local_paths.csv",
            alma_export_csv=alma_export_csv,
            for_import_dir="For-Import",
            progress_callback=progress_update
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message("Function 12 complete: TIFFs processed and JPGs created")
    
    def on_function_13_click(e):
        """Handle Function 13: Analyze Sound Records by Decade"""
        if not editor.set_members or len(editor.set_members) == 0:
            update_status("Please load a set first", True)
            return
        
        # Generate timestamped filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"sound_records_by_decade_{timestamp}.csv"
        
        add_log_message(f"Starting sound records decade analysis to {output_file}")
        update_status(f"Analyzing {len(editor.set_members)} records for sound recordings...", False)
        
        # Show progress bar
        set_progress_bar.visible = True
        set_progress_bar.value = 0
        set_progress_text.visible = True
        set_progress_text.value = f"Processing: 0/{len(editor.set_members)} records"
        page.update()
        
        def progress_update(current, total):
            progress = current / total
            set_progress_bar.value = progress
            set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
            status_text.value = f"Analyzing sound records: {current}/{total} records ({progress*100:.1f}%)"
            page.update()
        
        # Analyze sound records by decade
        storage.record_function_usage("function_13_sound_by_decade")
        success, message = editor.analyze_sound_records_by_decade(
            editor.set_members,
            output_file,
            progress_callback=progress_update
        )
        
        # Hide progress bar
        set_progress_bar.visible = False
        set_progress_text.visible = False
        page.update()
        
        update_status(message, not success)
        if success:
            add_log_message(f"Sound records decade analysis complete: {output_file}")
            add_log_message("💡 Tip: Sort by Decade column to group records for sub-collection distribution")
    
    def on_function_14_click(e):
        """Handle Function 14a: Prepare .clientThumb Thumbnails (Part 1 of 2)"""
        # Determine if batch or single mode
        is_batch = editor.set_members and len(editor.set_members) > 0
        
        if not is_batch:
            # Single record mode
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            mms_ids_to_process = [mms_id_input.value]
            record_info = f"MMS ID: {mms_id_input.value}"
        else:
            # Batch mode
            mms_ids_to_process = editor.set_members
            record_info = f"Records to process: {len(editor.set_members)}"
        
        # Show warning dialog
        def proceed_with_upload(e):
            warning_dialog.open = False
            page.update()
            
            if is_batch:
                add_log_message(f"Starting thumbnail preparation for {len(mms_ids_to_process)} records")
                update_status(f"Preparing thumbnails for {len(mms_ids_to_process)} records...", False)
                
                # Show progress bar
                set_progress_bar.visible = True
                set_progress_bar.value = 0
                set_progress_text.visible = True
                set_progress_text.value = f"Processing: 0/{len(mms_ids_to_process)} records"
                page.update()
                
                def progress_update(current, total):
                    progress = current / total
                    set_progress_bar.value = progress
                    set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
                    status_text.value = f"Preparing thumbnails: {current}/{total} records ({progress*100:.1f}%)"
                    page.update()
            else:
                add_log_message(f"Starting thumbnail preparation for MMS ID: {mms_ids_to_process[0]}")
                update_status(f"Preparing thumbnail for {mms_ids_to_process[0]}...", False)
                progress_update = None
            
            # Prepare thumbnails (Part 1 - create reps and process files)
            storage.record_function_usage("function_14_upload_thumbnails")
            success, message = editor.upload_clientthumb_thumbnails(
                mms_ids_to_process,
                progress_callback=progress_update
            )
            
            # Hide progress bar (if it was shown)
            if is_batch:
                set_progress_bar.visible = False
                set_progress_text.visible = False
                page.update()
            
            update_status(message, not success)
            if success:
                if is_batch:
                    add_log_message(f"Thumbnail preparation complete")
                    add_log_message("💡 Check the logs for details on prepared files and any failures")
                else:
                    add_log_message("Thumbnail preparation complete for single record")
        
        def cancel_upload(e):
            warning_dialog.open = False
            page.update()
            add_log_message("Thumbnail preparation cancelled by user")
        
        warning_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ WARNING: Alma Data Modification", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "This will create thumbnail representations in Alma and prepare files for upload.",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        record_info,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Function: 14a - Prepare Thumbnails (Part 1 of 2)",
                        italic=True,
                        color=ft.Colors.GREY_700
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "This action will PERMANENTLY create thumbnail representations in Alma. "
                        "Files will be processed from .clientThumb files based on each record's grinnell: or dg_ identifier. "
                        "Note: This only creates representations and prepares files. Actual file upload will be done in Function 14b.",
                        size=13
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Do you want to continue?",
                        weight=ft.FontWeight.BOLD
                    ),
                ]),
                padding=10,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_upload),
                ft.TextButton(
                    "Proceed",
                    on_click=proceed_with_upload,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_700,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(warning_dialog)
    
    def on_function_14b_click(e):
        """Handle Function 14b: Upload Thumbnails via Selenium (Part 2 of 2)"""
        # Get CSV file path from Set ID field
        csv_path = set_id_input.value.strip() if set_id_input.value else ""
        
        if not csv_path:
            update_status("Please enter the CSV file path from Function 14a in the Set ID field", True)
            return
        
        if not csv_path.endswith('.csv'):
            update_status("Please provide a valid CSV file path (must end with .csv)", True)
            return
        
        # Show warning dialog
        def proceed_with_upload(e):
            warning_dialog.open = False
            page.update()
            
            add_log_message(f"Starting thumbnail upload via Selenium")
            add_log_message(f"CSV file: {csv_path}")
            update_status(f"Uploading thumbnails via Firefox...", False)
            
            # Show progress bar
            set_progress_bar.visible = True
            set_progress_bar.value = 0
            set_progress_text.visible = True
            set_progress_text.value = f"Initializing..."
            page.update()
            
            def progress_update(current, total):
                progress = current / total
                set_progress_bar.value = progress
                set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
                status_text.value = f"Uploading thumbnails: {current}/{total} records ({progress*100:.1f}%)"
                page.update()
            
            # Upload via Selenium
            storage.record_function_usage("function_14b_upload_thumbnails")
            success, message, success_count, failed_count = editor.upload_thumbnails_selenium(
                csv_path,
                progress_callback=progress_update
            )
            
            # Hide progress bar
            set_progress_bar.visible = False
            set_progress_text.visible = False
            page.update()
            
            update_status(message, not success)
            if success:
                add_log_message(f"Thumbnail upload complete")
                add_log_message("💡 Firefox has been left open for your review")
            else:
                add_log_message(f"Upload failed or incomplete - check logs for details")
            
            # Show completion dialog
            from pathlib import Path as PathLib
            csv_path_obj = PathLib(csv_path)
            temp_dir = csv_path_obj.parent
            
            def close_completion_dialog(e):
                completion_dialog.open = False
                page.update()
            
            def delete_temp_directory(e):
                """Delete the temporary directory after user confirmation"""
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                    add_log_message(f"✓ Deleted temporary directory: {temp_dir}")
                    update_status(f"Temporary directory deleted: {temp_dir}", False)
                except Exception as delete_error:
                    add_log_message(f"✗ Error deleting directory: {str(delete_error)}", logging.ERROR)
                    update_status(f"Error deleting directory: {str(delete_error)}", True)
                finally:
                    completion_dialog.open = False
                    page.update()
            
            # Build completion dialog content
            completion_content = [
                ft.Text(
                    "Upload Process Complete",
                    size=16,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Container(height=10),
                ft.Text(f"✓ Successfully uploaded: {success_count}", color=ft.Colors.GREEN_700),
                ft.Text(f"✗ Failed uploads: {failed_count}", 
                        color=ft.Colors.RED_700 if failed_count > 0 else ft.Colors.GREY_600),
                ft.Container(height=10),
                ft.Text(f"Temporary directory:", weight=ft.FontWeight.BOLD),
                ft.Text(str(temp_dir), size=12, italic=True),
            ]
            
            # Add delete option only if no errors
            completion_actions = [
                ft.TextButton("Close", on_click=close_completion_dialog)
            ]
            
            if failed_count == 0 and success_count > 0:
                completion_content.append(ft.Container(height=10))
                completion_content.append(
                    ft.Text(
                        "Since all uploads were successful, would you like to delete the temporary directory?",
                        size=13,
                        italic=True
                    )
                )
                completion_actions.insert(0, ft.TextButton(
                    "Delete Temp Directory",
                    on_click=delete_temp_directory,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.ORANGE_700
                    )
                ))
            else:
                completion_content.append(ft.Container(height=10))
                completion_content.append(
                    ft.Text(
                        "⚠️ Some uploads failed. The temporary directory has been preserved for review.",
                        size=12,
                        color=ft.Colors.ORANGE_700
                    )
                )
            
            completion_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("🎉 Upload Complete", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Column(completion_content),
                    padding=20
                ),
                actions=completion_actions,
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            page.open(completion_dialog)
        
        def cancel_upload(e):
            warning_dialog.open = False
            page.update()
            add_log_message("Thumbnail upload cancelled by user")
        
        warning_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ WARNING: Browser Automation", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "This will upload thumbnail files to Alma using browser automation (Selenium).",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        f"CSV file: {csv_path}",
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Function: 14b - Upload Thumbnails (Part 2 of 2)",
                        italic=True,
                        color=ft.Colors.GREY_700
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "⚠️ IMPORTANT: Close all Firefox windows before proceeding!",
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED_700,
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "How it works:\n\n"
                        "1. Click Proceed below\n\n"
                        "2. Selenium will launch a NEW Firefox window\n\n"
                        "3. You'll have 60 seconds to log into Alma via Grinnell SSO + DUO\n\n"
                        "4. If you need more time, automation will pause 30 additional seconds\n\n"
                        "5. Automation begins automatically\n\n"
                        "Do not interact with Firefox during uploads.\n\n"
                        "Note: Selenium cannot use your existing Firefox session—\n"
                        "it must launch its own window.",
                        size=13
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Do you want to continue?",
                        weight=ft.FontWeight.BOLD
                    ),
                ]),
                padding=20
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=cancel_upload
                ),
                ft.TextButton(
                    "Proceed",
                    on_click=proceed_with_upload,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_700
                    )
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(warning_dialog)
    
    # Function definitions with metadata
    # Active functions - frequently used
    active_functions = [
        "function_1_fetch_xml",
        "function_3_export_csv",
        "function_5_iiif",
        "function_8_export_identifiers",
        "function_9_validate_handles",
        "function_10_export_review",
        "function_11_identify_single_tiff",
        "function_12_process_tiffs",
        "function_13_sound_by_decade",
        "function_14a_prepare_thumbnails",
        "function_14b_upload_thumbnails"
    ]
    
    # Inactive functions - less frequently used
    inactive_functions = [
        "function_2_clear_dc_relation",
        "function_4_filter_pre1930",
        "function_6_replace_rights",
        "function_7_add_grinnell_id"
    ]
    
    functions = {
        "function_1_fetch_xml": {
            "label": "1: Fetch and Display Single XML",
            "icon": "🔍",
            "handler": on_function_1_click,
            "help_file": "FUNCTION_1_FETCH_DISPLAY_XML.md"
        },
        "function_2_clear_dc_relation": {
            "label": "2: Clear dc:relation Collections Fields",
            "icon": "🧹",
            "handler": on_function_2_click,
            "help_file": "FUNCTION_2_CLEAR_DC_RELATION.md"
        },
        "function_3_export_csv": {
            "label": "3: Export Set to DCAP01 CSV",
            "icon": "📥",
            "handler": on_function_3_click,
            "help_file": "FUNCTION_3_EXPORT_TO_CSV.md"
        },
        "function_4_filter_pre1930": {
            "label": "4: Filter CSV for Records 95+ Years Old",
            "icon": "🔎",
            "handler": on_function_4_click,
            "help_file": "FUNCTION_4_FILTER_HISTORICAL_RECORDS.md"
        },
        "function_5_iiif": {
            "label": "5: Get IIIF Manifest and Canvas",
            "icon": "🖼️",
            "handler": on_function_5_click,
            "help_file": "FUNCTION_5_BATCH_FETCH_JSON.md"
        },
        "function_6_replace_rights": {
            "label": "6: Replace old dc:rights with Public Domain link",
            "icon": "©️",
            "handler": on_function_6_click,
            "help_file": "FUNCTION_6_DC_RIGHTS_REPLACEMENT.md"
        },
        "function_7_add_grinnell_id": {
            "label": "7: Add Grinnell: dc:identifier Field As Needed",
            "icon": "🏷️",
            "handler": on_function_7_click,
            "help_file": "FUNCTION_7_ADD_GRINNELL_IDENTIFIER.md"
        },
        "function_8_export_identifiers": {
            "label": "8: Export dc:identifier CSV",
            "icon": "🔖",
            "handler": on_function_8_click,
            "help_file": "FUNCTION_8_EXPORT_IDENTIFIERS.md"
        },
        "function_9_validate_handles": {
            "label": "9: Validate Handle URLs and Export Results",
            "icon": "🔗",
            "handler": on_function_9_click,
            "help_file": "FUNCTION_9_VALIDATE_HANDLES.md"
        },
        "function_10_export_review": {
            "label": "10: Export for Review with Clickable Handles",
            "icon": "📋",
            "handler": on_function_10_click,
            "help_file": "FUNCTION_10_EXPORT_REVIEW.md"
        },
        "function_11_identify_single_tiff": {
            "label": "11: Identify Single TIFF Representations",
            "icon": "🖼️",
            "handler": on_function_11_click,
            "help_file": "FUNCTION_11_IDENTIFY_SINGLE_TIFF.md"
        },
        "function_12_process_tiffs": {
            "label": "12: Process TIFFs & Create JPG Derivatives",
            "icon": "📸",
            "handler": on_function_12_click,
            "help_file": "FUNCTION_12_PROCESS_TIFFS.md"
        },
        "function_13_sound_by_decade": {
            "label": "13: Analyze Sound Records by Decade",
            "icon": "🎵",
            "handler": on_function_13_click,
            "help_file": "FUNCTION_13_SOUND_BY_DECADE.md"
        },
        "function_14a_prepare_thumbnails": {
            "label": "14a: Prepare Thumbnails (Part 1 of 2)",
            "icon": "🖼️",
            "handler": on_function_14_click,
            "help_file": "FUNCTION_14a_PREPARE_THUMBNAILS.md"
        },
        "function_14b_upload_thumbnails": {
            "label": "14b: Upload Thumbnails (Part 2 of 2)",
            "icon": "⬆️",
            "handler": on_function_14b_click,
            "help_file": "FUNCTION_14b_UPLOAD_THUMBNAILS.md"
        }
    }
    
    # Help checkbox state
    help_mode_enabled = ft.Ref[ft.Checkbox]()
    
    def show_help_dialog(function_key):
        """Display the help markdown file for a function"""
        if function_key not in functions:
            return
        
        func_info = functions[function_key]
        help_file = func_info.get("help_file")
        
        if not help_file:
            add_log_message(f"No help file available for {func_info['label']}")
            return
        
        try:
            # Read the markdown file
            with open(help_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            add_log_message(f"Displaying help for: {func_info['label']}")
            
            def close_help_dialog(e):
                help_dialog.open = False
                page.update()
            
            def copy_help(e):
                page.set_clipboard(markdown_content)
                copy_help_button.text = "Copied!"
                page.update()
                # Reset button text after 2 seconds
                import threading
                def reset_text():
                    import time
                    time.sleep(2)
                    copy_help_button.text = "Copy to Clipboard"
                    page.update()
                threading.Thread(target=reset_text, daemon=True).start()
            
            copy_help_button = ft.TextButton("Copy to Clipboard", on_click=copy_help)
            
            help_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text(f"📖 Help: {func_info['label']}", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(f"File: {help_file}", size=11, color=ft.Colors.GREY_600, italic=True),
                        ft.Container(height=10),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Markdown(
                                        value=markdown_content,
                                        selectable=True,
                                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                                        on_tap_link=lambda e: page.launch_url(e.data),
                                    ),
                                ],
                                scroll=ft.ScrollMode.AUTO,
                            ),
                            width=900,
                            height=700,
                            padding=10,
                            bgcolor=ft.Colors.WHITE,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=5,
                        ),
                    ]),
                    padding=10,
                ),
                actions=[
                    copy_help_button,
                    ft.TextButton("Close", on_click=close_help_dialog),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            page.open(help_dialog)
            
        except FileNotFoundError:
            add_log_message(f"Help file not found: {help_file}")
            update_status(f"Help file not found: {help_file}", True)
        except Exception as e:
            add_log_message(f"Error reading help file: {str(e)}")
            update_status(f"Error reading help file: {str(e)}", True)
    
    def execute_selected_function(function_key):
        """Execute the selected function from dropdown or show help if help mode is enabled"""
        if function_key and function_key in functions:
            # Check if help mode is enabled
            if help_mode_enabled.current and help_mode_enabled.current.value:
                # Show help dialog instead of executing
                show_help_dialog(function_key)
                # Clear selection
                active_function_dropdown.value = None
                inactive_function_dropdown.value = None
                page.update()
            else:
                # Execute the function normally
                # Call the function handler with a mock event
                class MockEvent:
                    pass
                functions[function_key]["handler"](MockEvent())
                
                # Refresh dropdown orders after execution
                active_function_dropdown.options = get_sorted_function_options(active_functions)
                inactive_function_dropdown.options = get_sorted_function_options(inactive_functions)
                active_function_dropdown.value = None  # Clear selection
                inactive_function_dropdown.value = None  # Clear selection
                page.update()
    
    def get_sorted_function_options(function_list):
        """Get function dropdown options sorted by last use date"""
        from datetime import datetime
        
        usage_data = storage.get_all_function_usage()
        
        # Create list of (function_key, last_used_timestamp)
        function_usage = []
        for func_key in function_list:
            usage = usage_data.get(func_key, {})
            last_used = usage.get("last_used")
            # Parse ISO timestamp or use epoch start for never-used functions
            if last_used:
                try:
                    timestamp = datetime.fromisoformat(last_used)
                except:
                    timestamp = datetime.min
            else:
                timestamp = datetime.min
            
            function_usage.append((func_key, timestamp))
        
        # Sort by timestamp (most recent first)
        function_usage.sort(key=lambda x: x[1], reverse=True)
        
        # Create dropdown options
        options = []
        for func_key, timestamp in function_usage:
            func_info = functions[func_key]
            label = f"{func_info['icon']} {func_info['label']}"
            options.append(ft.dropdown.Option(key=func_key, text=label))
        
        return options
    
    # Build UI
    page.add(
        ft.Column([
            ft.Text("🚕 CABB - Crunch Alma Bibs in Bulk", 
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
                    ft.Text("Batch Processing (Set or CSV):", size=14, weight=ft.FontWeight.W_500),
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
                    ft.Row([
                        ft.Column([
                            ft.Text("Active Functions", size=18, weight=ft.FontWeight.BOLD),
                            active_function_dropdown := ft.Dropdown(
                                label="Select Function to Execute",
                                hint_text="Functions ordered by most recently used",
                                width=500,
                                max_menu_height=400,
                                options=[],
                                on_change=lambda e: execute_selected_function(e.control.value)
                            ),
                        ], spacing=5),
                        ft.Container(width=20),  # Spacer
                        ft.Column([
                            ft.Text("Inactive Functions", size=18, weight=ft.FontWeight.BOLD),
                            inactive_function_dropdown := ft.Dropdown(
                                label="Select Inactive Function",
                                hint_text="Less frequently used",
                                width=500,
                                max_menu_height=400,
                                options=[],
                                on_change=lambda e: execute_selected_function(e.control.value)
                            ),
                        ], spacing=5),
                    ]),
                    ft.Checkbox(
                        label="Help Mode",
                        ref=help_mode_enabled,
                        tooltip="Enable to view help documentation for functions instead of executing them"
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
    
    # Populate function dropdowns with sorted options
    active_function_dropdown.options = get_sorted_function_options(active_functions)
    inactive_function_dropdown.options = get_sorted_function_options(inactive_functions)
    page.update()
    
    logger.info("UI initialized successfully")


if __name__ == "__main__":
    logger.info("Application starting...")
    ft.app(
        target=main,
        assets_dir="assets",
        web_renderer=ft.WebRenderer.HTML
    )
