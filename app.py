"""
Crunch Alma Bibs in Bulk (CABB)
A Flet UI app designed to perform various Alma-Digital bib record editing functions.
"""

import flet as ft
import os
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
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
    
    def filter_csv_by_pre1931_dates(self, input_file: str = None, output_file: str = None) -> tuple[bool, str]:
        """
        Function 4: Filter CSV export to only records with dates before 1931
        
        Reads the most recent alma_export_*.csv file and filters records that have
        non-empty date values before 1931 in any of these fields:
        - dc:date
        - dcterms:created
        - dcterms:issued
        - dcterms:dateSubmitted
        - dcterms:dateAccepted
        
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
        
        self.log("Starting CSV filter for pre-1931 dates")
        
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
                output_file = f"pre1931_export_{timestamp}.csv"
            
            # Date fields to check
            date_fields = [
                "dc:date",
                "dcterms:created",
                "dcterms:issued",
                "dcterms:dateSubmitted",
                "dcterms:dateAccepted"
            ]
            
            def extract_year(date_str: str) -> int | None:
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
            
            def has_pre1931_date(row: dict) -> bool:
                """Check if any date field contains a year before 1931"""
                for field in date_fields:
                    date_value = row.get(field, "")
                    year = extract_year(date_value)
                    if year is not None and year < 1931:
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
                    if has_pre1931_date(row):
                        filtered_rows.append(row)
            
            # Write filtered results
            with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(filtered_rows)
            
            message = f"Filtered {len(filtered_rows)} of {total_rows} records (pre-1931 dates) → {output_file}"
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
    
    def replace_author_copyright_rights(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 6: Replace dc:rights fields starting with "Copyright to this work is held by the author(s)"
        with a rights statement URL and xml:lang attribute.
        
        Finds dc:rights fields with value starting "Copyright to this work is held by the author(s)"
        and replaces with dc:rights xml:lang="eng" value="https://rightsstatements.org/page/NoC-US/1.0/?language=en"
        Ensures no duplicate values are created.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        self.log(f"Starting replace_author_copyright_rights for MMS ID: {mms_id}")
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
            new_value = '<a href="https://rightsstatements.org/page/NoC-US/1.0/?language=en" target="_blank">Public Domain in the United States</a>'
            url_pattern = "https://rightsstatements.org/page/NoC-US/1.0/?language=en"
            
            # Check if new value already exists
            url_exists = False
            url_element = None
            author_copyright_elements = []
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
                    elif url_pattern in rights_elem.text and 'target="_blank"' not in rights_elem.text:
                        # Found old link without target attribute
                        old_link_elements.append(rights_elem)
                        self.log(f"Found old link without target: {rights_elem.text[:80]}...")
            
            # If URL with target already exists, remove any author copyright fields and old links
            if url_exists:
                elements_to_remove = author_copyright_elements + old_link_elements
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
                else:
                    self.log("URL exists and no old fields to remove")
                    return True, "Rights statement URL already exists, no changes needed"
            else:
                # URL doesn't exist, replace author copyright fields or old links
                elements_to_replace = author_copyright_elements + old_link_elements
                if not elements_to_replace:
                    self.log("No matching dc:rights fields found")
                    return True, "No matching dc:rights fields found"
                
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
                return False, f"Failed to update record: {response.status_code}"
            
            self.log(f"Successfully updated record {mms_id}")
            
            # Build appropriate success message
            if url_exists:
                message = f"Removed {changes_made} author copyright field(s) (rights URL already present) in record {mms_id}"
            else:
                message = f"Replaced {changes_made} author copyright field(s) with rights URL in record {mms_id}"
            
            return True, message
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error processing record {mms_id}: {str(e)}", logging.ERROR)
            self.log(f"Full traceback:\n{error_details}", logging.DEBUG)
            return False, f"Error processing record {mms_id}: {str(e)}"
    
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
    page.window.width = 750
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
        tooltip="Enter 0 for no limit, or a number to process only first N records",
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
                if limit < 0:
                    limit = 0
            except ValueError:
                update_status("Invalid limit value - using 0 (no limit)", True)
                limit = 0
            
            # Apply limit if set
            if limit > 0 and len(members) > limit:
                editor.set_members = members[:limit]
                set_info_text.controls = [ft.Text(f"CSV: {input_value.split('/')[-1]} ({limit} of {len(members)} IDs loaded - limited)", size=12, color=ft.Colors.GREY_700)]
            else:
                set_info_text.controls = [ft.Text(f"CSV: {input_value.split('/')[-1]} ({len(members)} IDs)", size=12, color=ft.Colors.GREY_700)]
            
            page.update()
            update_status(f"Loaded {len(editor.set_members)} MMS IDs from CSV", False)
            
        else:
            # Load from Alma Set
            # Get limit value
            try:
                limit = int(limit_input.value) if limit_input.value else 0
                if limit < 0:
                    limit = 0
            except ValueError:
                update_status("Invalid limit value - using 0 (no limit)", True)
                limit = 0
            
            add_log_message(f"Loading set: {input_value} (limit: {limit if limit > 0 else 'none'})")
            
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
                set_info_text.controls = [ft.Text(f"Set: {set_name} ({member_count} of {limit} members loaded - limited)", size=12, color=ft.Colors.GREY_700)]
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
        """Handle Function 4 click - Filter CSV by pre-1931 dates"""
        logger.info("Function 4 button clicked - Filter CSV")
        storage.record_function_usage("function_4_filter_pre1931")
        
        add_log_message("Filtering latest CSV export for pre-1931 dates")
        success, message = editor.filter_csv_by_pre1931_dates()
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
                
                success_count = 0
                error_count = 0
                
                for i, mms_id in enumerate(editor.set_members[:process_count], 1):
                    if editor.kill_switch:
                        add_log_message("Batch processing stopped by user")
                        break
                    
                    # Update progress
                    set_progress_bar.value = i / process_count
                    set_progress_text.value = f"Processing {i}/{process_count}: {mms_id}"
                    page.update()
                    
                    success, message = editor.replace_author_copyright_rights(mms_id)
                    if success:
                        success_count += 1
                        add_log_message(f"✓ {mms_id}: {message}")
                    else:
                        error_count += 1
                        add_log_message(f"✗ {mms_id}: {message}")
                
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
                
                add_log_message(f"Starting replace_author_copyright_rights for MMS ID: {mms_id_input.value}")
                success, message = editor.replace_author_copyright_rights(mms_id_input.value)
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
    
    # Function definitions with metadata
    functions = {
        "function_1_fetch_xml": {
            "label": "Fetch and Display Single XML",
            "icon": "🔍",
            "handler": on_function_1_click,
            "help_file": "FUNCTION_1_FETCH_DISPLAY_XML.md"
        },
        "function_2_clear_dc_relation": {
            "label": "Clear dc:relation Collections Fields",
            "icon": "🧹",
            "handler": on_function_2_click,
            "help_file": "FUNCTION_2_CLEAR_DC_RELATION.md"
        },
        "function_3_export_csv": {
            "label": "Export Set to DCAP01 CSV",
            "icon": "📥",
            "handler": on_function_3_click,
            "help_file": "FUNCTION_3_EXPORT_TO_CSV.md"
        },
        "function_4_filter_pre1931": {
            "label": "Filter CSV for Pre-1931 Dates",
            "icon": "🔎",
            "handler": on_function_4_click,
            "help_file": "FUNCTION_4_CREATE_DCAP01_RECORD.md"
        },
        "function_5_iiif": {
            "label": "Get IIIF Manifest and Canvas",
            "icon": "🖼️",
            "handler": on_function_5_click,
            "help_file": "FUNCTION_5_BATCH_FETCH_JSON.md"
        },
        "function_6_replace_rights": {
            "label": "Replace old dc:rights with Public Domain link",
            "icon": "©️",
            "handler": on_function_6_click,
            "help_file": "FUNCTION_6_DC_RIGHTS_REPLACEMENT.md"
        },
        "function_7_add_grinnell_id": {
            "label": "Add Grinnell: dc:identifier Field As Needed",
            "icon": "🏷️",
            "handler": on_function_7_click,
            "help_file": "FUNCTION_7_ADD_GRINNELL_IDENTIFIER.md"
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
                function_dropdown.value = None
                page.update()
            else:
                # Execute the function normally
                # Call the function handler with a mock event
                class MockEvent:
                    pass
                functions[function_key]["handler"](MockEvent())
                
                # Refresh dropdown order after execution
                function_dropdown.options = get_sorted_function_options()
                function_dropdown.value = None  # Clear selection
                page.update()
    
    def get_sorted_function_options():
        """Get function dropdown options sorted by last use date"""
        from datetime import datetime
        
        usage_data = storage.get_all_function_usage()
        
        # Create list of (function_key, last_used_timestamp)
        function_usage = []
        for func_key in functions.keys():
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
                    ft.Text("Active Functions", size=18, weight=ft.FontWeight.BOLD),
                    
                    # Function selector dropdown (will be updated after page.add)
                    function_dropdown := ft.Dropdown(
                        label="Select Function to Execute",
                        hint_text="Functions ordered by most recently used",
                        width=400,
                        options=[],
                        on_change=lambda e: execute_selected_function(e.control.value)
                    ),
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
    
    # Populate function dropdown with sorted options
    function_dropdown.options = get_sorted_function_options()
    page.update()
    
    logger.info("UI initialized successfully")


if __name__ == "__main__":
    logger.info("Application starting...")
    ft.app(
        target=main,
        assets_dir="assets",
        web_renderer=ft.WebRenderer.HTML
    )
