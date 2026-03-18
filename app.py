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

# Import inactive functions module
import inactive_functions

# Load environment variables
load_dotenv()

# Configure logging
# Create logfiles directory if it doesn't exist
os.makedirs('logfiles', exist_ok=True)
log_filename = f"logfiles/cabb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Set up file handler (DEBUG level) and console handler (ERROR/INFO only, no DEBUG)
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)  # Only ERROR and above to console

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[file_handler, console_handler]
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
        self._pinned_debug_driver = None  # Keep failed Selenium session alive for manual inspection
        self.min_log_level = logging.INFO  # Minimum log level for UI display
        logger.debug(f"API Region: {self.api_region}")
        logger.debug(f"API Key configured: {'Yes' if self.api_key else 'No'}")
        
    def log(self, message, level=logging.INFO):
        """Log a message and send to UI callback if level is sufficient"""
        logger.log(level, message)
        # Only send to UI callback if message level is >= minimum level
        if self.log_callback and level >= self.min_log_level:
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
                
                # Read MMS IDs, skipping comment lines (starting with #)
                for row in reader:
                    mms_id = row.get(mms_id_column, '').strip()
                    # Skip empty lines and comment lines (starting with #)
                    if mms_id and not mms_id.startswith('#'):
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
        """Function 2: Delegate to inactive_functions module"""
        return inactive_functions.clear_dc_relation_collections(self, mms_id)
    
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
        """Function 4: Delegate to inactive_functions module"""
        return inactive_functions.filter_csv_by_pre1930_dates(self, input_file, output_file)
    
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
        """Function 6: Delegate to inactive_functions module"""
        return inactive_functions.replace_author_copyright_rights(self, mms_id)
    
    def add_grinnell_identifier(self, mms_id: str) -> tuple[bool, str]:
        """Function 7: Delegate to inactive_functions module"""
        return inactive_functions.add_grinnell_identifier(self, mms_id)
    
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
        Function 12: Analyze sound recordings by decade
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
            csv_file_path = None
            if csv_data:
                csv_file = output_dir / f"thumbnail_representations_{timestamp}.csv"
                csv_file_path = str(csv_file.absolute())
                with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['mms_id', 'rep_id', 'filename', 'original_file'])
                    writer.writeheader()
                    writer.writerows(csv_data)
                
                self.log(f"\n✓ Created CSV file: {csv_file_path}")
                self.log(f"  Contains {len(csv_data)} entries")
            
            # Final summary
            message = f"Thumbnail preparation complete: {success_count} prepared, {failed_count} failed, "
            message += f"{no_identifier_count} no identifier, {no_thumbnail_count} no thumbnail (normal)"
            if csv_file_path:
                message += f"\nCSV file: {csv_file_path}"
            message += f"\nOutput directory: {output_dir.absolute()}"
            self.log(message)
            if no_thumbnail_count > 0:
                self.log(f"Note: {no_thumbnail_count} record(s) had no matching thumbnail files - this is expected for some records", logging.INFO)
            return True, message, csv_file_path
            
        except Exception as e:
            error_msg = f"Error preparing thumbnails: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.DEBUG)
            return False, error_msg, None
    
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
    
    def prepare_tiff_jpg_representations(self, mms_ids: list, tiff_csv: str = "all_single_tiffs_with_local_paths.csv", 
                                         progress_callback=None) -> tuple[bool, str, str | None]:
        """
        Function 11: Prepare TIFF/JPG representations for Alma Digital Uploader (CSV Harvard Method)
        
        For each MMS ID:
        1. Look up TIFF file path from CSV
        2. Create empty JPG representation in Alma (or find existing empty one)
        3. Create JPG derivative from TIFF
        4. Add MMS ID and filename to values.csv
        
        The output is designed for Alma's Digital Uploader using Harvard's minimal CSV approach.
        All JPG files are placed in a single flat directory with one values.csv file.
        
        CSV Format (ONLY 2 columns):
            mms_id,file_name_1
            991234567890104641,991234567890104641.jpg
            992345678901104641,992345678901104641.jpg
        
        Args:
            mms_ids: List of MMS IDs to process
            tiff_csv: CSV file with MMS ID and Local Path columns
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str, output_dir_path: str | None)
        """
        from pathlib import Path
        from datetime import datetime
        import csv
        
        # Create timestamped output directory in Downloads folder
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        downloads_dir = Path.home() / "Downloads"
        output_dir = downloads_dir / f"CABB_digital_upload_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.log(f"Starting Function 11: Prepare TIFF/JPG Representations (CSV Harvard Method)")
        self.log(f"Processing {len(mms_ids)} MMS ID(s)")
        self.log(f"TIFF CSV: {tiff_csv}")
        self.log(f"Output directory: {output_dir.absolute()}")
        self.log(f"Format: Flat directory with values.csv (Harvard approach)")
        
        if not self.api_key:
            return False, "API Key not configured", None
        
        # Verify TIFF CSV exists
        tiff_csv_path = Path(tiff_csv)
        if not tiff_csv_path.exists():
            return False, f"TIFF CSV not found: {tiff_csv}", None
        
        # Check if Pillow is available for JPG creation
        try:
            from PIL import Image
        except ImportError:
            return False, "Pillow library not installed. Run: pip install Pillow", None
        
        try:
            # Read TIFF CSV to get local paths
            self.log(f"Reading TIFF paths from {tiff_csv}")
            tiff_paths = {}
            with open(tiff_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mms_id = (row.get('MMS ID') or '').strip()
                    # Skip comment lines (lines starting with #)
                    if mms_id.startswith('#'):
                        continue
                    local_path = (row.get('Local Path') or '').strip()
                    if mms_id and local_path:
                        tiff_paths[mms_id] = local_path
            
            self.log(f"Found {len(tiff_paths)} records with local paths")
            
            # Initialize CSV data structure for values.csv
            csv_rows = []
            
            # Process each MMS ID
            success_count = 0
            failed_count = 0
            no_path_count = 0
            no_file_count = 0
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
                    no_file_count += 1
                    failed_count += 1
                    continue
                
                file_size = source_tiff.stat().st_size
                self.log(f"  ✓ Found TIFF: {source_tiff.name} ({file_size / 1024 / 1024:.2f} MB)")
                
                # Prepare JPG representation and file (flat in output_dir, no subdirectories)
                jpg_filename = f"{mms_id}.jpg"
                prep_success, prep_result = self._prepare_jpg_from_tiff_representation_csv(
                    mms_id,
                    str(source_tiff),
                    jpg_filename,
                    output_dir  # Flat directory - no subdirectories
                )
                
                if prep_success:
                    # prep_result is a dict with rep_id, processed_file, message
                    rep_id = prep_result['rep_id']
                    processed_file = prep_result['processed_file']
                    
                    self.log(f"  ✓ {prep_result['message']}")
                    self.log(f"    Rep ID: {rep_id}")
                    self.log(f"    JPG file: {processed_file}")
                    
                    # Add to CSV data (ONLY mms_id and file_name_1 columns)
                    csv_rows.append({
                        'mms_id': mms_id,
                        'file_name_1': jpg_filename
                    })
                    
                    success_count += 1
                else:
                    self.log(f"  ✗ {prep_result}", logging.ERROR)
                    failed_count += 1
            
            # Create values.csv file
            output_dir_path = None
            if csv_rows:
                values_csv = output_dir / "values.csv"
                with open(values_csv, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['mms_id', 'file_name_1'])
                    writer.writeheader()
                    writer.writerows(csv_rows)
                
                self.log(f"\n✓ Created values.csv with {len(csv_rows)} records")
                
                # Create master README file with instructions
                readme_content = self._create_uploader_readme_csv(len(csv_rows), timestamp)
                readme_file = output_dir / "README.txt"
                with open(readme_file, 'w', encoding='utf-8') as f:
                    f.write(readme_content)
                
                self.log(f"✓ Created README.txt with upload instructions")
                output_dir_path = str(output_dir.absolute())
            
            # Final summary
            message = f"TIFF/JPG preparation complete: {success_count} prepared, {failed_count} failed, "
            message += f"{no_path_count} no path, {no_file_count} file not found"
            if output_dir_path:
                message += f"\n\n📂 Output directory: {output_dir_path}"
                message += f"\n📄 Created: values.csv + {success_count} JPG files"
                message += f"\n📋 Format: Harvard minimal CSV (mms_id, file_name_1 only)"
                message += f"\n\n⚠️ NEXT STEPS:"
                message += f"\n1. Launch Alma and navigate to: Resources > Advanced Tools > Digital Uploader"
                message += f"\n2. Select profile: 'CABB Function 11 - Add ONE File to Existing Representation' (ID: 7848184990004641)"
                message += f"\n3. Click 'Add new ingest' and give it a name"
                message += f"\n4. DRAG AND DROP all files (values.csv + all JPG files) into the upload box"
                message += f"\n5. Click 'Upload all', then 'Submit Selected', then 'Run MD Import'"
                message += f"\n6. See README.txt in the output directory for detailed instructions"
            self.log(message)
            return True, message, output_dir_path
            
        except Exception as e:
            error_msg = f"Error preparing TIFF/JPG representations: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.DEBUG)
            return False, error_msg, None
    
    def _prepare_jpg_from_tiff_representation(self, mms_id: str, tiff_path: str, jpg_filename: str, output_dir) -> tuple[bool, dict | str]:
        """
        Create a JPG representation and prepare the JPG file from TIFF (without uploading).
        
        This creates a representation with usage_type DERIVATIVE_COPY, converts TIFF to JPG,
        and saves it to the output directory with the specified filename.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            tiff_path: Full path to the TIFF file
            jpg_filename: Desired JPG filename (e.g., "123456789.jpg")
            output_dir: Path object for output directory
            
        Returns:
            tuple: (success: bool, result: dict or error_message: str)
                   result dict contains: {'rep_id': str, 'processed_file': str, 'message': str}
        """
        from pathlib import Path
        from PIL import Image
        
        try:
            
            self.log(f"Starting JPG preparation from TIFF for MMS {mms_id}")
            self.log(f"  Source TIFF: {Path(tiff_path).name}")
            self.log(f"  Output JPG: {jpg_filename}")
            
            # Verify file exists
            if not Path(tiff_path).exists():
                return False, f"File not found: {tiff_path}"
            
            file_size = Path(tiff_path).stat().st_size
            self.log(f"  File size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
            
            # Step 1: Check for existing JPG representation
            api_url = self._get_alma_api_url()
            rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
            
            headers = {
                'Authorization': f'apikey {self.api_key}',
                'Accept': 'application/json'
            }
            
            # Fetch existing representations
            self.log(f"Checking for existing JPG representation for {mms_id}")
            response = requests.get(rep_url, headers=headers)
            
            existing_rep_id = None
            jpg_position = None
            total_reps = 0
            
            if response.status_code == 200:
                reps_data = response.json()
                representations = reps_data.get('representation', [])
                total_reps = len(representations)
                
                # Look for existing DERIVATIVE_COPY representation with "JPG" in label
                for idx, rep in enumerate(representations):
                    label = rep.get('label', '')
                    usage_type = rep.get('usage_type', {}).get('value', '')
                    
                    if usage_type == 'DERIVATIVE_COPY' and ('JPG' in label or 'jpg' in label):
                        # Check if this representation has files
                        files = rep.get('files', {})
                        has_files = False
                        if isinstance(files, dict):
                            file_list = files.get('representation_file', [])
                            if file_list:
                                has_files = True
                        
                        if not has_files:
                            existing_rep_id = rep.get('id')
                            jpg_position = idx
                            self.log(f"  Found existing empty JPG representation: {existing_rep_id}")
                            self.log(f"  Position: {idx + 1} of {total_reps} representations")
                            break
            
            # Step 2: Create representation only if one doesn't already exist
            if existing_rep_id:
                rep_id = existing_rep_id
                self.log(f"Reusing existing representation ID: {rep_id}")
                
                if jpg_position is not None:
                    if jpg_position == 0:
                        self.log(f"  ✓ JPG representation is in first position", logging.INFO)
                    else:
                        self.log(f"  ⚠️ WARNING: JPG representation is at position {jpg_position + 1}, not first!", logging.WARNING)
                        self.log(f"  Alma may not use this as the primary display.", logging.WARNING)
            else:
                # Warn if creating new representation when others already exist
                if total_reps > 0:
                    self.log(f"  ⚠️ NOTE: Creating new JPG representation, but {total_reps} representation(s) already exist", logging.WARNING)
                    self.log(f"  The new JPG will be placed at the end (position {total_reps + 1})", logging.WARNING)
                    self.log(f"  Alma may not use this as the primary display.", logging.WARNING)
                
                rep_data = {
                    "label": f"JPG derivative - {jpg_filename}",
                    "usage_type": {"value": "DERIVATIVE_COPY"},
                    "library": {"value": "MAIN"},
                    "public_note": "JPG derivative created from TIFF (prepared for upload)"
                }
                
                headers_create = {
                    'Authorization': f'apikey {self.api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                
                self.log(f"Creating new JPG representation for {mms_id}")
                response = requests.post(rep_url, headers=headers_create, json=rep_data)
                
                if response.status_code not in [200, 201]:
                    self.log(f"  Response body: {response.text}", logging.ERROR)
                    return False, f"Failed to create representation: HTTP {response.status_code}"
                
                rep_response = response.json()
                rep_id = rep_response.get('id')
                self.log(f"Created representation ID: {rep_id}")
                
                if total_reps == 0:
                    self.log(f"  ✓ JPG representation created as first (and only) representation", logging.INFO)
            
            # Step 3: Create JPG from TIFF
            self.log(f"Creating JPG from TIFF...")
            output_file = output_dir / jpg_filename
            
            try:
                with Image.open(tiff_path) as img:
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
                    img.save(output_file, 'JPEG', quality=95, optimize=True)
                    
                    jpg_size = output_file.stat().st_size
                    self.log(f"  ✓ Created JPG: {jpg_filename} ({jpg_size / 1024 / 1024:.2f} MB)")
            
            except Exception as e:
                self.log(f"  ✗ JPG creation failed: {str(e)}", logging.ERROR)
                return False, f"Error creating JPG: {str(e)}"
            
            return True, {
                'rep_id': rep_id,
                'processed_file': jpg_filename,
                'message': f"{'Reused existing' if existing_rep_id else 'Created'} representation and JPG prepared (Rep ID: {rep_id})"
            }
            
        except Exception as e:
            self.log(f"Exception in _prepare_jpg_from_tiff_representation: {str(e)}", logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False, f"Error preparing JPG from TIFF: {str(e)}"
    
    def _prepare_jpg_from_tiff_representation_xml(self, mms_id: str, tiff_path: str, jpg_filename: str, output_dir) -> tuple[bool, dict | str]:
        """
        Create a JPG representation and prepare the JPG file from TIFF for XML-based upload.
        
        Similar to _prepare_jpg_from_tiff_representation but saves file in subdirectory.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            tiff_path: Full path to the TIFF file
            jpg_filename: Desired JPG filename (e.g., "123456789.jpg")
            output_dir: Path object for MMS ID subdirectory
            
        Returns:
            tuple: (success: bool, result: dict or error_message: str)
                   result dict contains: {'rep_id': str, 'processed_file': str, 'message': str}
        """
        from pathlib import Path
        from PIL import Image
        
        try:
            # Verify file exists
            if not Path(tiff_path).exists():
                return False, f"File not found: {tiff_path}"
            
            # Step 1: Check for existing JPG representation
            api_url = self._get_alma_api_url()
            rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
            
            headers = {
                'Authorization': f'apikey {self.api_key}',
                'Accept': 'application/json'
            }
            
            # Fetch existing representations
            response = requests.get(rep_url, headers=headers)
            
            existing_rep_id = None
            
            if response.status_code == 200:
                reps_data = response.json()
                representations = reps_data.get('representation', [])
                
                # Look for existing DERIVATIVE_COPY representation with "JPG" in label
                for rep in representations:
                    label = rep.get('label', '')
                    usage_type = rep.get('usage_type', {}).get('value', '')
                    
                    if usage_type == 'DERIVATIVE_COPY' and ('JPG' in label or 'jpg' in label):
                        # Check if this representation has files
                        files = rep.get('files', {})
                        has_files = False
                        if isinstance(files, dict):
                            file_list = files.get('representation_file', [])
                            if file_list:
                                has_files = True
                        
                        if not has_files:
                            existing_rep_id = rep.get('id')
                            break
            
            # Step 2: Create representation only if one doesn't already exist
            if existing_rep_id:
                rep_id = existing_rep_id
            else:
                rep_data = {
                    "label": f"JPG derivative - {jpg_filename}",
                    "usage_type": {"value": "DERIVATIVE_COPY"},
                    "library": {"value": "MAIN"},
                    "public_note": "JPG derivative created from TIFF"
                }
                
                headers_create = {
                    'Authorization': f'apikey {self.api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                
                response = requests.post(rep_url, headers=headers_create, json=rep_data)
                
                if response.status_code not in [200, 201]:
                    return False, f"Failed to create representation: HTTP {response.status_code}"
                
                rep_response = response.json()
                rep_id = rep_response.get('id')
            
            # Step 3: Create JPG from TIFF
            output_file = output_dir / jpg_filename
            
            try:
                with Image.open(tiff_path) as img:
                    # Handle 16-bit images
                    if img.mode in ('I', 'I;16', 'I;16B', 'I;16L', 'I;16N'):
                        img = img.point(lambda x: x / 256).convert('L').convert('RGB')
                    # Convert to RGB if necessary
                    elif img.mode in ('RGBA', 'LA', 'P'):
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = rgb_img
                    elif img.mode == 'L':
                        img = img.convert('RGB')
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Save as JPG with high quality
                    img.save(output_file, 'JPEG', quality=95, optimize=True)
            
            except Exception as e:
                return False, f"Error creating JPG: {str(e)}"
            
            return True, {
                'rep_id': rep_id,
                'processed_file': jpg_filename,
                'message': f"{'Reused existing' if existing_rep_id else 'Created'} representation and JPG prepared"
            }
            
        except Exception as e:
            return False, f"Error preparing JPG from TIFF: {str(e)}"
    
    def _create_metadata_xml(self, output_dir, mms_id: str, rep_id: str, filename: str) -> bool:
        """
        Create metadata.xml file for Alma Digital Uploader.
        
        Creates an XML file with the proper structure for uploading files to existing representations.
        
        Args:
            output_dir: Path object for the MMS ID subdirectory
            mms_id: The MMS ID
            rep_id: The representation ID
            filename: The JPG filename
            
        Returns:
            bool: Success status
        """
        import xml.etree.ElementTree as ET
        
        try:
            # Create root element
            root = ET.Element('row')
            
            # Add MMS ID element
            mms_element = ET.SubElement(root, 'dc_identifier')
            mms_element.text = mms_id
            
            # Add representation ID element
            rep_element = ET.SubElement(root, 'representation_id')
            rep_element.text = rep_id
            
            # Add file element
            file_element = ET.SubElement(root, 'file_name')
            file_element.text = filename
            
            # Create the XML tree and write with declaration
            tree = ET.ElementTree(root)
            ET.indent(tree, space='  ', level=0)  # Pretty print with 2-space indent
            
            # Write to file
            metadata_file = output_dir / 'metadata.xml'
            tree.write(metadata_file, encoding='utf-8', xml_declaration=True)
            
            return True
            
        except Exception as e:
            self.log(f"Error creating metadata.xml: {str(e)}", logging.ERROR)
            return False
    
    def _create_uploader_readme(self, count: int, timestamp: str) -> str:
        """
        Create README content with instructions for using the Digital Uploader.
        
        Args:
            count: Number of records processed
            timestamp: Timestamp string
            
        Returns:
            str: README content
        """
        readme = f"""ALMA DIGITAL UPLOADER PACKAGE
Generated: {timestamp}
Records: {count}

DIRECTORY STRUCTURE
===================
This package contains {count} subdirectories, one for each MMS ID.
Each subdirectory contains:
  - metadata.xml: XML metadata file with MMS ID, representation ID, and filename
  - [MMS_ID].jpg: The JPG derivative file

Example structure:
  991234567890104641/
    ├── metadata.xml
    └── 991234567890104641.jpg
  991234567890204641/
    ├── metadata.xml
    └── 991234567890204641.jpg

UPLOAD INSTRUCTIONS
===================
1. Log into Alma

2. Navigate to:
   Resources > Manage Digital Files > Digital Uploader

3. Select Upload Profile:
   REQUIRED: An XML-based Digital Import Profile that:
   - Supports XML metadata files (NOT CSV)
   - Processes subdirectory structure
   - Reads: dc_identifier, representation_id, file_name
   - Adds files to existing representations WITHOUT overlaying bib metadata
   
   WARNING: Do NOT use CSV-based overlay profiles - they destroy metadata!
   
   If you don't have this profile, contact your Alma administrator or 
   Ex Libris support to create one.

4. Upload Directory:
   - Click "Browse" or "Choose Files"  
   - Select THIS ENTIRE DIRECTORY (including all subdirectories)
   - Alma will process each subdirectory using its metadata.xml file

5. Start Upload:
   - Review the validation screen
   - Click "Submit" to begin upload
   - Monitor progress in Alma

6. Verify Upload:
   - Check a few records in Alma to confirm JPGs are attached
   - Verify JPG displays correctly in Digital Viewer
   - Confirm no error messages in Alma's upload log

METADATA.XML FORMAT
===================
Each metadata.xml file contains:
  <row>
    <dc_identifier>MMS_ID</dc_identifier>
    <representation_id>REP_ID</representation_id>
    <file_name>FILENAME.jpg</file_name>
  </row>

The dc_identifier tells Alma which record to update.
The representation_id tells Alma which representation to add the file to.
The file_name tells Alma which file to upload.

TROUBLESHOOTING
================
If upload fails:
  - Verify you're using an XML-based profile (not CSV)
  - Confirm all metadata.xml files are present
  - Check that MMS IDs match actual Alma records
  - Verify that representation IDs are valid
  - Ensure JPG files are readable
  - Try uploading a single subdirectory first to test

If profile not available:
  - Contact your Alma administrator
  - Reference Harvard Wiki: Alma Digital Uploader XML spec
  - URL: https://harvardwiki.atlassian.net/wiki/spaces/LibraryStaffDoc/
         pages/43394499/Alma+Digital+Uploader+XML+spec

AFTER SUCCESSFUL UPLOAD
========================
- Verify files in Alma
- Test a few records in the public interface
- Keep this directory until verification is complete
- After verification, you can safely delete this directory

For questions, consult:
- FUNCTION_11_PREPARE_TIFF_JPG.md in CABB workspace
- Harvard wiki (URL above)
- Ex Libris Knowledge Center: Digital Uploader guides
- Your institution's Alma administrator
"""
        return readme
    
    def _create_uploader_readme_csv(self, count: int, timestamp: str) -> str:
        """
        Create README content with instructions for using the Digital Uploader (CSV Harvard Method).
        
        Args:
            count: Number of records processed
            timestamp: Timestamp string
            
        Returns:
            str: README content
        """
        readme = f"""ALMA DIGITAL UPLOADER PACKAGE (Harvard CSV Method)
Generated: {timestamp}
Records: {count}

DIRECTORY STRUCTURE
===================
This package contains {count} JPG files and ONE values.csv file in a FLAT directory.
No subdirectories. Simple and clean.

Files:
  - values.csv: Maps MMS IDs to filenames (ONLY 2 columns)
  - 991234567890104641.jpg
  - 992345678901104641.jpg
  - etc.

VALUES.CSV FORMAT
=================
CRITICAL: Only 2 columns, NO bibliographic metadata fields!

mms_id,file_name_1
991234567890104641,991234567890104641.jpg
992345678901104641,992345678901104641.jpg

This minimal format prevents metadata destruction because:
- No dc:title, dc:creator, dc:rights, or other bib fields
- Only file placement information (which record, which file)
- Profile set to "Do not override Originating System"

UPLOAD INSTRUCTIONS (Harvard Method)
=====================================
1. Log into Alma

2. Navigate to:
   Resources > Advanced Tools > Digital Uploader

3. Select Upload Profile:
   Profile: "CABB Function 11 - Add ONE File to Existing Representation"
   Profile ID: 7848184990004641
   
   This profile is configured to:
   - Read minimal CSV (mms_id, file_name_1 only)
   - Match records by MMS ID
   - Add files to existing representations
   - NOT modify bibliographic metadata ("Do not override Originating System")

4. Add New Ingest:
   - Click "Add new ingest" button (upper right)
   - Give it a descriptive name (e.g., "CABB Batch {timestamp}")

5. Upload Files:
   - DRAG AND DROP all files into the upload box
     (This means: values.csv + ALL JPG files)
   - Wait for all files to show "Pending Upload" status
   - Click "Upload all" button (upper right)
   - Wait for all files to show "Uploaded" status
   - Click "OK"

6. Submit:
   - Check the box next to your ingest row
   - Click "Submit Selected"
   - Wait for status to change to "Submitted"

7. Run MD Import:
   - Click "Run MD Import"
   - Alma will process all records
   - You'll receive email notification when complete

8. Verify Upload:
   - Wait for email confirmation
   - Check a few records in Alma to confirm JPGs are attached
   - Verify JPG displays in Digital Viewer
   - Confirm bibliographic metadata was NOT modified
   - Test in public interface (Primo/Discovery) after 15 minutes

IMPORTANT NOTES
===============
- Maximum 1000 files per ingest (split larger batches)
- Maximum 1 GB per file
- Files are staged for 30 days
- Process runs automatically every 15 minutes
- Do NOT click "Run MD Import" twice - it will try to reload the same files!

TROUBLESHOOTING
================
If Submit button is greyed out:
  - Check values.csv format (exactly 2 columns, correct headers)
  - Verify filenames in CSV match actual JPG files (no typos)
  - Check for extra spaces or special characters in filenames

If files don't appear in Alma:
  - Check Monitor Jobs page for errors
  - Verify MMS IDs exist in Alma
  - Confirm representation IDs are valid
  - Review upload log in Monitor Jobs

If metadata was destroyed:
  - This should NOT happen with this profile!
  - Profile has "Do not override Originating System" enabled
  - values.csv has NO bibliographic metadata columns
  - Contact Ex Libris support immediately if this occurs

AFTER SUCCESSFUL UPLOAD
========================
- Verify files in several Alma records
- Test in public interface (wait 15 min for index update)
- Check that bibliographic metadata is unchanged
- Keep this directory until verification is complete
- After verification, you can safely delete this directory

REFERENCES
==========
- Harvard Wiki: https://harvardwiki.atlassian.net/wiki/spaces/LibraryStaffDoc/
               pages/43394499/Alma-D+batch+uploader
- FUNCTION_11_PREPARE_TIFF_JPG.md in CABB workspace
- FUNCTION_11_CSV_PROFILE_SETUP.md in CABB workspace
- Ex Libris Knowledge Center: Digital Uploader guides
- Your institution's Alma administrator

For questions, consult the references above or contact your Alma administrator.
"""
        return readme
    
    def _prepare_jpg_from_tiff_representation_csv(self, mms_id: str, tiff_path: str, jpg_filename: str, output_dir) -> tuple[bool, dict | str]:
        """
        Create a JPG representation and prepare the JPG file from TIFF for CSV-based upload (Harvard method).
        
        This creates or reuses a representation, converts TIFF to JPG, and saves it to the flat output directory.
        Unlike the XML version, this does NOT create subdirectories or metadata.xml files.
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            tiff_path: Full path to the TIFF file
            jpg_filename: Desired JPG filename (e.g., "123456789.jpg")
            output_dir: Path object for flat output directory (NOT a subdirectory)
            
        Returns:
            tuple: (success: bool, result: dict or error_message: str)
                   result dict contains: {'rep_id': str, 'processed_file': str, 'message': str}
        """
        from pathlib import Path
        from PIL import Image
        
        try:
            # Verify file exists
            if not Path(tiff_path).exists():
                return False, f"File not found: {tiff_path}"
            
            # Step 1: Check for existing JPG representation
            api_url = self._get_alma_api_url()
            rep_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
            
            headers = {
                'Authorization': f'apikey {self.api_key}',
                'Accept': 'application/json'
            }
            
            # Fetch existing representations
            response = requests.get(rep_url, headers=headers)
            
            existing_rep_id = None
            
            if response.status_code == 200:
                rep_data = response.json()
                if 'representation' in rep_data:
                    for rep in rep_data['representation']:
                        usage = rep.get('usage_type', {}).get('value', '')
                        # Look for existing JPG/Derivative representation that's empty or has no files
                        if usage in ['DERIVATIVE_COPY', 'VIEW']:
                            rep_id = rep.get('id')
                            files = rep.get('files', {}).get('file', [])
                            if not files or len(files) == 0:
                                existing_rep_id = rep_id
                                break
            
            # Step 2: Create or reuse representation
            if existing_rep_id:
                rep_id = existing_rep_id
                message = f"Reusing existing empty JPG representation"
            else:
                # Create new representation
                create_url = f"{api_url}/almaws/v1/bibs/{mms_id}/representations"
                headers_post = {
                    'Authorization': f'apikey {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                rep_payload = {
                    "usage_type": {"value": "DERIVATIVE_COPY"}
                }
                
                create_response = requests.post(create_url, headers=headers_post, json=rep_payload)
                
                if create_response.status_code != 200:
                    return False, f"Failed to create representation: {create_response.text}"
                
                rep_data = create_response.json()
                rep_id = rep_data.get('id')
                message = f"Created new JPG representation"
            
            # Step 3: Convert TIFF to JPG and save to flat output directory
            jpg_output_path = output_dir / jpg_filename
            
            with Image.open(tiff_path) as img:
                # Handle different image modes
                if img.mode in ('I;16', 'I;16B'):
                    img = img.point(lambda i: i * (1.0 / 256)).convert('L')
                elif img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # Save as JPG with 95% quality
                img.save(jpg_output_path, 'JPEG', quality=95)
            
            return True, {
                'rep_id': rep_id,
                'processed_file': jpg_filename,
                'message': message
            }
            
        except Exception as e:
            return False, f"Error processing TIFF: {str(e)}"
    
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
    def _setup_selenium_browser(self, browser: str = "firefox"):
        """
        Helper method: Set up and launch a browser for Selenium automation.
        
        This is shared between Function 11b (JPG upload), Function 14b (thumbnail upload),
        and Function 17 (metadata restore).
        
        Args:
            browser: Browser engine to launch ("firefox" or "chrome")
        
        Returns:
            WebDriver: Configured Selenium WebDriver instance
            
        Raises:
            Exception: If browser cannot be launched
        """
        from selenium import webdriver
        import os

        browser = (browser or "firefox").strip().lower()
        if browser not in {"firefox", "chrome"}:
            raise ValueError(f"Unsupported browser '{browser}'. Use 'firefox' or 'chrome'.")

        self.log(f"Starting {browser.title()} browser for automation...")
        self.log(f"Note: Selenium will launch a NEW {browser.title()} window (cannot attach to existing sessions)", logging.DEBUG)
        self.log("", logging.DEBUG)
        
        try:
            if browser == "chrome":
                from selenium.webdriver.chrome.service import Service as ChromeService

                options = webdriver.ChromeOptions()
                options.add_argument("--disable-popup-blocking")
                options.add_argument("--disable-notifications")
                # Prefer the standard installed Chrome app over Chrome for Testing.
                chrome_binary_candidates = [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                ]
                for chrome_binary in chrome_binary_candidates:
                    if os.path.exists(chrome_binary):
                        options.binary_location = chrome_binary
                        self.log(f"Using Chrome binary: {chrome_binary}", logging.DEBUG)
                        break
                else:
                    self.log(
                        "Standard Google Chrome binary not found; Selenium may launch Chrome for Testing.",
                        logging.WARNING,
                    )
                # Window is sized explicitly after launch via set_window_size()

                service = ChromeService()
                self.log("Launching Chrome via ChromeDriver...", logging.DEBUG)
                driver = webdriver.Chrome(service=service, options=options)
                self.log("✓ Chrome launched successfully")
                return driver

            from selenium.webdriver.firefox.service import Service as FirefoxService

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
            # Window is sized explicitly after launch via set_window_size()

            # Optional: inject Selenium IDE (or any other extension) into Firefox.
            xpi_search_paths = [
                os.path.expanduser("~/Downloads/selenium_ide.xpi"),
                os.path.join(os.path.dirname(__file__), "selenium_ide.xpi"),
            ]
            for xpi_path in xpi_search_paths:
                if os.path.isfile(xpi_path):
                    try:
                        options.add_extension(xpi_path)
                        self.log(f"✓ Loaded extension from {xpi_path}")
                    except Exception as xpi_err:
                        self.log(f"Could not load extension {xpi_path}: {xpi_err}", logging.WARNING)
                    break
            
            service = FirefoxService()
            self.log("Launching Firefox via GeckoDriver...", logging.DEBUG)
            driver = webdriver.Firefox(service=service, options=options)
            self.log("✓ Firefox launched successfully")
            return driver
            
        except Exception as e:
            if browser == "chrome":
                raise Exception(f"Could not start Chrome: {str(e)}. Please ensure ChromeDriver is installed (brew install --cask chromedriver).")
            raise Exception(f"Could not start Firefox: {str(e)}. Please ensure GeckoDriver is installed (brew install geckodriver).")

    def _get_browser_app_name(self, driver) -> str:
        """Return the macOS app name for the active Selenium driver."""
        try:
            browser_name = (driver.capabilities.get('browserName') or '').lower()
        except Exception:
            browser_name = ''

        if browser_name == 'chrome':
            return "Google Chrome"
        if browser_name == 'safari':
            return "Safari"
        return "Firefox"
    
    def _attempt_automatic_sso_login(self, driver, username: str, password: str) -> bool:
        """
        Helper method: Attempt automatic login through SSO (supports Microsoft SSO multi-step).
        
        This handles the username/password entry for SSO login pages, including
        Microsoft's multi-step login flow (username → Next → password → Sign in).
        
        Args:
            driver: Selenium WebDriver instance
            username: SSO username to enter
            password: SSO password to enter
            
        Returns:
            bool: True if login appeared successful, False if failed
            
        Note:
            This does NOT handle DUO authentication - that must still be done manually.
            The function returns True after submitting credentials, before DUO.
        """
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        import time
        
        try:
            # Wait for SSO login page to load
            time.sleep(2)
            
            # Look for username field (supports Microsoft SSO and generic forms)
            username_field = None
            username_selectors = [
                # Microsoft SSO specific selectors
                (By.ID, "i0116"),  # Microsoft SSO username field
                (By.NAME, "loginfmt"),  # Microsoft SSO username field name
                (By.CSS_SELECTOR, "input[type='email']"),  # Microsoft uses email type
                # Generic selectors
                (By.ID, "username"),
                (By.ID, "j_username"),
                (By.ID, "user"),
                (By.NAME, "username"),
                (By.NAME, "j_username"),
                (By.CSS_SELECTOR, "input[type='text'][name*='user' i]"),
                (By.CSS_SELECTOR, "input[type='text']"),
            ]
            
            for selector_type, selector_value in username_selectors:
                try:
                    username_field = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    self.log(f"✓ Found username field using: {selector_type}={selector_value}", logging.DEBUG)
                    break
                except TimeoutException:
                    continue
            
            if not username_field:
                self.log("⚠️ Could not find username field", logging.WARNING)
                return False
            
            # Enter username
            username_field.clear()
            username_field.send_keys(username)
            self.log(f"✓ Entered username: {username}", logging.DEBUG)
            time.sleep(0.5)
            
            # Look for "Next" button (Microsoft SSO has a separate step)
            next_button = None
            next_selectors = [
                (By.ID, "idSIButton9"),  # Microsoft SSO "Next" button
                (By.CSS_SELECTOR, "input[type='submit'][value*='Next' i]"),
                (By.XPATH, "//input[@type='submit' and contains(@value, 'Next')]"),
            ]
            
            for selector_type, selector_value in next_selectors:
                try:
                    next_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    self.log(f"✓ Found Next button using: {selector_type}={selector_value}", logging.DEBUG)
                    break
                except TimeoutException:
                    continue
            
            if next_button:
                next_button.click()
                self.log("✓ Clicked Next button (Microsoft SSO multi-step)", logging.DEBUG)
                time.sleep(2)  # Wait for password page to load
            
            # Look for password field
            password_field = None
            password_selectors = [
                # Microsoft SSO specific selectors
                (By.ID, "i0118"),  # Microsoft SSO password field
                (By.NAME, "passwd"),  # Microsoft SSO password field name
                # Generic selectors
                (By.ID, "password"),
                (By.ID, "j_password"),
                (By.ID, "pass"),
                (By.NAME, "password"),
                (By.NAME, "j_password"),
                (By.CSS_SELECTOR, "input[type='password']"),
            ]
            
            for selector_type, selector_value in password_selectors:
                try:
                    password_field = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    self.log(f"✓ Found password field using: {selector_type}={selector_value}", logging.DEBUG)
                    break
                except TimeoutException:
                    continue
            
            if not password_field:
                self.log("⚠️ Could not find password field", logging.WARNING)
                return False
            
            # Enter password
            password_field.clear()
            password_field.send_keys(password)
            self.log("✓ Entered password", logging.DEBUG)
            time.sleep(0.5)
            
            # Look for submit button
            submit_button = None
            submit_selectors = [
                # Microsoft SSO specific selector
                (By.ID, "idSIButton9"),  # Microsoft SSO "Sign in" button
                # Generic selectors
                (By.ID, "submit"),
                (By.ID, "loginbtn"),
                (By.NAME, "submit"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.XPATH, "//button[contains(text(), 'Sign') or contains(text(), 'Login') or contains(text(), 'Submit')]"),
                (By.XPATH, "//input[@type='submit' or @type='button']"),
            ]
            
            for selector_type, selector_value in submit_selectors:
                try:
                    submit_button = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((selector_type, selector_value))
                    )
                    self.log(f"✓ Found submit button using: {selector_type}={selector_value}", logging.DEBUG)
                    break
                except TimeoutException:
                    continue
            
            if submit_button:
                submit_button.click()
                self.log("✓ Clicked Sign In button", logging.DEBUG)
            else:
                # Fallback: press Enter in password field
                self.log("⚠️ Submit button not found, pressing ENTER in password field", logging.DEBUG)
                password_field.send_keys(Keys.RETURN)
            
            self.log("✓ SSO login submitted", logging.DEBUG)
            time.sleep(2)  # Brief wait for page to process
            
            return True
            
        except Exception as e:
            self.log(f"⚠️ Automatic SSO login error: {e}", logging.WARNING)
            return False
    
    def _perform_initial_alma_login(self, driver):
        """
        Helper method: Navigate to Alma SSO login and wait for user to complete authentication.
        
        This is shared between Function 11b (JPG upload) and Function 14b (thumbnail upload).
        
        Args:
            driver: Selenium WebDriver instance
            
        Performs:
        - Navigates to Alma SAML/SSO login page
        - If SSO_USERNAME and SSO_PASSWORD are in environment, automatically logs in
        - Otherwise, waits for user to manually log in
        - Waits for DUO authentication (manual)
        - Focuses Firefox window and dismisses popups
        """
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        import subprocess
        import time
        import os
        
        # Check if automatic login credentials are available
        sso_username = os.getenv('SSO_USERNAME')
        sso_password = os.getenv('SSO_PASSWORD')
        auto_login_enabled = sso_username and sso_password
        
        # Navigate to Alma SAML/SSO login page
        target_url = "https://grinnell.alma.exlibrisgroup.com/SAML"
        self.log("Navigating to Alma SSO login page...", logging.DEBUG)
        driver.get(target_url)
        
        if auto_login_enabled:
            # Attempt automatic SSO login
            self.log("")
            self.log("=" * 70)
            self.log("🔐 AUTOMATIC SSO LOGIN")
            self.log("=" * 70)
            self.log("SSO credentials found in environment - logging in automatically...")
            self.log("")
            
            # Call the helper function to perform login
            login_successful = self._attempt_automatic_sso_login(driver, sso_username, sso_password)
            
            if login_successful:
                # Automatic login submitted successfully
                self.log("")
                self.log("⏸️  WAITING FOR DUO AUTHENTICATION")
                self.log("=" * 70)
                self.log("Please approve the DUO push notification on your device...")
                self.log("")
                self.log("After DUO approval:")
                self.log("4. ⚙️  CONFIGURE THE SEARCH BAR (at top of Alma page):")
                self.log("   • Click the search dropdown (left side)")
                self.log("   • Select: 'Digital titles'")
                self.log("   • Click the field dropdown (middle)")
                self.log("   • Select: 'Representation ID' or 'Representation PID'")
                self.log("   • Leave the search box EMPTY")
                self.log("")
                self.log("Automation will begin in 45 seconds...")
                self.log("(Configure search settings while waiting)")
                self.log("")
                
                # Wait 45 seconds for DUO + page load + user to configure search
                # Increased from 30 because DUO redirect + page load can take time
                time.sleep(45)
                
                # After DUO, check for "Stay signed in?" popup and click "Yes"
                self.log("\n🔍 Checking for 'Stay signed in?' popup...", logging.DEBUG)
                try:
                    # Look for the popup and "Yes" button using multiple strategies
                    yes_clicked = driver.execute_script("""
                        // Strategy 1: Look for buttons with "Yes" text
                        var buttons = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
                        for (var i = 0; i < buttons.length; i++) {
                            var text = buttons[i].textContent || buttons[i].value || '';
                            if (text.trim().toLowerCase() === 'yes') {
                                // Check if there's "stay signed in" text nearby
                                var parent = buttons[i].closest('div, form');
                                if (parent && parent.textContent.toLowerCase().includes('stay signed in')) {
                                    buttons[i].click();
                                    return 'yes-button';
                                }
                            }
                        }
                        
                        // Strategy 2: Look for common Microsoft SSO "Yes" button IDs
                        var yesBtn = document.getElementById('idSIButton9');
                        if (yesBtn && yesBtn.textContent.toLowerCase().includes('yes')) {
                            yesBtn.click();
                            return 'idSIButton9';
                        }
                        
                        // Strategy 3: Look for any button with value="Yes"
                        var yesInputs = document.querySelectorAll('input[value="Yes" i], button[value="Yes" i]');
                        if (yesInputs.length > 0 && yesInputs[0].offsetParent !== null) {
                            yesInputs[0].click();
                            return 'yes-input';
                        }
                        
                        return false;
                    """)
                    
                    if yes_clicked:
                        self.log(f"  ✓ Clicked 'Yes' on 'Stay signed in?' popup (method: {yes_clicked})", logging.DEBUG)
                        time.sleep(2)  # Wait for page to process
                    else:
                        self.log("  ℹ️  No 'Stay signed in?' popup detected", logging.DEBUG)
                except Exception as popup_err:
                    self.log(f"  ⚠️  Could not check for 'Stay signed in?' popup: {popup_err}", logging.DEBUG)
            else:
                # Automatic login failed, fall back to manual
                self.log("Falling back to manual login...", logging.WARNING)
                self.log("")
                auto_login_enabled = False
        
        if not auto_login_enabled:
            # Manual login (original behavior)
            self.log("")
            self.log("=" * 70)
            self.log("⏸️  PLEASE LOG INTO ALMA NOW (via Grinnell SSO)")
            self.log("=" * 70)
            self.log("1. Complete the SSO login process in the Firefox window")
            self.log("2. Complete DUO authentication if prompted")
            self.log("3. Wait for the Alma home page to fully load")
            self.log("")
            self.log("4. ⚙️  CONFIGURE THE SEARCH BAR (at top of page):")
            self.log("   • Click the search dropdown (left side)")
            self.log("   • Select: 'Digital titles'")
            self.log("   • Click the field dropdown (middle)")
            self.log("   • Select: 'Representation ID' or 'Representation PID'")
            self.log("   • Leave the search box EMPTY")
            self.log("")
            self.log("5. Automation will begin automatically in 60 seconds...")
            self.log("")
            self.log("(If you need more time, the system will pause for 30 more seconds)")
            self.log("(Or use the Kill Switch and restart the function)")
            self.log("")
            
            # Give user time to log in via SSO + DUO
            time.sleep(60)
            
            # After manual DUO wait, also check for "Stay signed in?" popup
            self.log("\n🔍 Checking for 'Stay signed in?' popup...", logging.DEBUG)
            try:
                yes_clicked = driver.execute_script("""
                    var buttons = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].textContent || buttons[i].value || '';
                        if (text.trim().toLowerCase() === 'yes') {
                            var parent = buttons[i].closest('div, form');
                            if (parent && parent.textContent.toLowerCase().includes('stay signed in')) {
                                buttons[i].click();
                                return 'yes-button';
                            }
                        }
                    }
                    
                    var yesBtn = document.getElementById('idSIButton9');
                    if (yesBtn && yesBtn.textContent.toLowerCase().includes('yes')) {
                        yesBtn.click();
                        return 'idSIButton9';
                    }
                    
                    return false;
                """)
                
                if yes_clicked:
                    self.log(f"  ✓ Clicked 'Yes' on 'Stay signed in?' popup (method: {yes_clicked})", logging.DEBUG)
                    time.sleep(2)
                else:
                    self.log("  ℹ️  No 'Stay signed in?' popup detected", logging.DEBUG)
            except Exception as popup_err:
                self.log(f"  ⚠️  Could not check for 'Stay signed in?' popup: {popup_err}", logging.DEBUG)
        
        # Aggressively force Firefox to get focus and dismiss popups
        self.log("\n" + "=" * 70, logging.DEBUG)
        self.log("FOCUSING FIREFOX AND DISMISSING POPUPS", logging.DEBUG)
        self.log("=" * 70, logging.DEBUG)
        
        # Multiple attempts to activate and focus
        for attempt in range(3):
            self.log(f"\nFocus attempt {attempt + 1}/3...", logging.DEBUG)
            
            try:
                # Activate Firefox via AppleScript
                subprocess.run([
                    'osascript', '-e',
                    'tell application "Firefox" to activate'
                ], capture_output=True, timeout=5)
                self.log(f"  ✓ Firefox activated via AppleScript", logging.DEBUG)
                time.sleep(1)  # Wait for activation to take effect
                
                # Size and position window without maximising (leaves room for
                # other windows like Selenium IDE and VS Code)
                driver.set_window_size(1200, 900)
                driver.set_window_position(0, 0)
                driver.switch_to.window(driver.current_window_handle)
                driver.execute_script("window.focus();")
                self.log(f"  ✓ Window resized and focused", logging.DEBUG)
                time.sleep(0.5)
                
                # Use keyboard to dismiss popups (Tab + Enter, then Escape)
                # This works even when mouse focus is lost
                actions = ActionChains(driver)
                
                # Try pressing Escape to close any dialogs
                actions.send_keys(Keys.ESCAPE)
                actions.perform()
                time.sleep(0.3)
                
                # Try Tab + Enter to dismiss "Stay signed in" type prompts
                actions = ActionChains(driver)
                actions.send_keys(Keys.TAB)
                actions.send_keys(Keys.RETURN)
                actions.perform()
                time.sleep(0.3)
                
                self.log(f"  ✓ Keyboard popup dismissal attempted", logging.DEBUG)
                
            except Exception as e:
                self.log(f"  ⚠️  Focus attempt {attempt + 1} had issues: {e}", logging.DEBUG)
            
            time.sleep(0.5)
        
        # Try to dismiss common popups with JavaScript
        self.log("\nAttempting JavaScript popup dismissal...", logging.DEBUG)
        try:
            # Enhanced popup dismissal scripts - run multiple times
            for round_num in range(3):
                dismiss_scripts = [
                    # Press Escape key on any focused element
                    """
                    if (document.activeElement) {
                        var event = new KeyboardEvent('keydown', {'key': 'Escape', 'code': 'Escape', 'keyCode': 27});
                        document.activeElement.dispatchEvent(event);
                    }
                    """,
                    # Click "No" or "Not now" on stay signed in prompts
                    """
                    var buttons = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
                    for (var i = 0; i < buttons.length; i++) {
                        var text = buttons[i].textContent || buttons[i].value || '';
                        if (text.toLowerCase().includes('no') || 
                            text.toLowerCase().includes('not now') || 
                            text.toLowerCase().includes('dismiss') ||
                            text.toLowerCase().includes('cancel')) {
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
                    """,
                    # Close any modal overlays
                    """
                    var closeButtons = document.querySelectorAll('[class*="close"], [class*="dismiss"], [aria-label*="close" i]');
                    for (var i = 0; i < closeButtons.length; i++) {
                        if (closeButtons[i].offsetParent !== null) {
                            closeButtons[i].click();
                            break;
                        }
                    }
                    """,
                    # Dismiss "Manage Widgets" popup
                    """
                    var widgetButtons = document.querySelectorAll('button, a, [role="button"]');
                    for (var i = 0; i < widgetButtons.length; i++) {
                        var text = widgetButtons[i].textContent || widgetButtons[i].getAttribute('aria-label') || '';
                        if (text.toLowerCase().includes('manage widgets') || 
                            text.toLowerCase().includes('widget') ||
                            widgetButtons[i].classList.toString().toLowerCase().includes('widget')) {
                            // Try to find close button in parent/sibling elements
                            var parent = widgetButtons[i].closest('div[role="dialog"], div[class*="modal"], div[class*="popup"]');
                            if (parent) {
                                var closeBtn = parent.querySelector('[aria-label*="close" i], button[class*="close"], a[class*="close"]');
                                if (closeBtn) {
                                    closeBtn.click();
                                    break;
                                }
                            }
                        }
                    }
                    // Also try direct widget modal dismissal
                    var widgetModals = document.querySelectorAll('[class*="widget" i] [class*="close"], [aria-label*="widget" i] [aria-label*="close" i]');
                    for (var i = 0; i < widgetModals.length; i++) {
                        if (widgetModals[i].offsetParent !== null) {
                            widgetModals[i].click();
                            break;
                        }
                    }
                    """
                ]
                
                for script in dismiss_scripts:
                    driver.execute_script(script)
                    time.sleep(0.2)
                
                if round_num < 2:
                    time.sleep(0.5)  # Brief pause between rounds
            
            self.log("✓ JavaScript popup dismissal completed (3 rounds)", logging.DEBUG)
        except Exception as e:
            self.log(f"⚠️  Could not dismiss popups via JavaScript: {e}", logging.DEBUG)
        
        # Final focus attempt
        try:
            subprocess.run([
                'osascript', '-e',
                'tell application "Firefox" to activate'
            ], capture_output=True, timeout=5)
            driver.execute_script("window.focus();")
            self.log("✓ Final Firefox activation completed", logging.DEBUG)
        except Exception as e:
            self.log(f"⚠️  Final activation failed: {e}", logging.DEBUG)
        
        self.log("=" * 70, logging.DEBUG)
        
        # Debug: Log current page info
        current_url = driver.current_url
        self.log(f"\nCurrent URL: {current_url}", logging.DEBUG)
        self.log("", logging.DEBUG)
        
        # CRITICAL: Validate search selectors before proceeding
        self.log("🔍 Validating search configuration...", logging.DEBUG)
        try:
            search_config_valid = driver.execute_script("""
                // Find all spans with class 'sel-combobox-selected-value'
                var selectors = document.querySelectorAll('span.sel-combobox-selected-value');
                var hasDigitalTitles = false;
                var hasRepresentationPID = false;
                
                for (var i = 0; i < selectors.length; i++) {
                    var text = selectors[i].textContent.trim();
                    if (text === 'Digital titles' || text === 'Digital Titles') {
                        hasDigitalTitles = true;
                    }
                    if (text === 'Representation PID') {
                        hasRepresentationPID = true;
                    }
                }
                
                return {
                    hasDigitalTitles: hasDigitalTitles,
                    hasRepresentationPID: hasRepresentationPID,
                    valid: hasDigitalTitles && hasRepresentationPID
                };
            """)
            
            if not search_config_valid.get('valid'):
                error_msg = "❌ CRITICAL ERROR: Search configuration is incorrect!\n"
                error_msg += "=" * 70 + "\n"
                error_msg += "Required search settings:\n"
                error_msg += "  1. Search type: 'Digital titles' " + ("✓" if search_config_valid.get('hasDigitalTitles') else "❌ MISSING") + "\n"
                error_msg += "  2. Search field: 'Representation PID' " + ("✓" if search_config_valid.get('hasRepresentationPID') else "❌ MISSING") + "\n"
                error_msg += "\nPlease set the search configuration in Alma before running this function:\n"
                error_msg += "  1. Go to: https://grinnell.alma.exlibrisgroup.com/SAML\n"
                error_msg += "  2. In the top search bar, select:\n"
                error_msg += "     - Search type dropdown: 'Digital titles'\n"
                error_msg += "     - Search field dropdown: 'Representation PID'\n"
                error_msg += "  3. Perform any search to save these settings\n"
                error_msg += "  4. Then run this function again\n"
                error_msg += "=" * 70
                self.log(error_msg, logging.ERROR)
                raise ValueError("Search configuration validation failed - see error message above")
            
            self.log("  ✓ Search type: 'Digital titles'", logging.DEBUG)
            self.log("  ✓ Search field: 'Representation PID'", logging.DEBUG)
            self.log("✓ Search configuration validated successfully", logging.DEBUG)
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            error_msg = f"❌ CRITICAL ERROR: Could not validate search configuration: {e}\n"
            error_msg += "This may indicate the Alma page is not fully loaded or has changed structure.\n"
            error_msg += "Please verify the search configuration manually."
            self.log(error_msg, logging.ERROR)
            raise ValueError("Search configuration validation failed - page not ready or structure changed")
        
        self.log("Starting automated uploads...")
    
    def _search_for_representation(self, driver, rep_id: str):
        """
        Helper method: Search for a specific representation ID in Alma.
        
        This is shared between Function 11b (JPG upload) and Function 14b (thumbnail upload).
        
        Args:
            driver: Selenium WebDriver instance
            rep_id: Representation ID to search for
            
        Performs:
        - Waits for page to be ready
        - Dismisses any interfering popups
        - Enters representation ID in search field
        - Presses ENTER to initiate search
        - Waits for search results to load
        
        Raises:
            TimeoutException: If search field cannot be found or page not ready
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        import time

        # If Microsoft SSO prompt is still present, dismiss it before interacting with Alma UI.
        self._dismiss_stay_signed_in_prompt(driver, timeout_seconds=6)
        
        # Step 1: Wait for page to be ready
        self.log("  Step 1: Waiting for Alma page to load...", logging.DEBUG)
        
        # Wait for page to be ready
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            # If page not ready, user might still be logging in
            self.log("    ⏸️  Page not ready yet - waiting 30 more seconds for login...", logging.WARNING)
            time.sleep(30)
            # Try again
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        
        # Step 2: Enter representation ID and search
        self.log(f"  Step 2: Searching for representation {rep_id}...", logging.DEBUG)
        self.log("    ℹ️  Using retained search settings", logging.DEBUG)
        self.log("    ⚠️  Ensure search is set to: Digital titles / Representation ID", logging.DEBUG)
        
        # Dismiss any popups/widgets that might be blocking the search field
        self.log("    Dismissing any interfering popups...", logging.DEBUG)
        try:
            # Run the enhanced popup dismissal scripts
            dismiss_scripts = [
                # Press Escape to close any dialogs
                "if (document.activeElement) { var e = new KeyboardEvent('keydown', {'key': 'Escape', 'code': 'Escape', 'keyCode': 27}); document.activeElement.dispatchEvent(e); }",
                # Close Manage Widgets popup specifically
                """
                var btns = document.querySelectorAll('button, a, [role="button"]');
                for (var i = 0; i < btns.length; i++) {
                    var txt = (btns[i].textContent || btns[i].getAttribute('aria-label') || '').toLowerCase();
                    if (txt.includes('manage') || txt.includes('widget')) {
                        var p = btns[i].closest('div[role="dialog"], div[class*="modal"], div[class*="popup"]');
                        if (p) { var c = p.querySelector('[aria-label*="close" i], button[class*="close"]'); if (c) c.click(); }
                    }
                }
                """,
                # Close any modal overlays
                """
                var closeBtns = document.querySelectorAll('[class*="close"], [class*="dismiss"], [aria-label*="close" i]');
                for (var i = 0; i < closeBtns.length; i++) {
                    if (closeBtns[i].offsetParent !== null) { closeBtns[i].click(); break; }
                }
                """
            ]
            for script in dismiss_scripts:
                driver.execute_script(script)
                time.sleep(0.1)
            self.log("    ✓ Popup dismissal completed", logging.DEBUG)
        except Exception as e:
            self.log(f"    ⚠️  Popup dismissal had issues: {e}", logging.DEBUG)
        
        try:
            search_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "NEW_ALMA_MENU_TOP_NAV_Search_Text"))
            )
            
            # Check if element is disabled and try to enable it via JavaScript
            is_disabled = driver.execute_script("return arguments[0].disabled;", search_input)
            if is_disabled:
                self.log("    ⚠️  Search field is disabled, attempting to enable via JavaScript...", logging.DEBUG)
                driver.execute_script("arguments[0].disabled = false;", search_input)
                time.sleep(0.5)
            
            # Use JavaScript to clear and set value (more reliable than .clear() when elements are finicky)
            driver.execute_script("arguments[0].value = '';", search_input)
            driver.execute_script("arguments[0].value = arguments[1];", search_input, rep_id)
            # Trigger input event so Angular/framework detects the change
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
            self.log("    ✓ Entered representation ID in search field", logging.DEBUG)
            
            # Press ENTER to initiate search (use JavaScript to be safe)
            driver.execute_script("""
                var e = new KeyboardEvent('keydown', {'key': 'Enter', 'code': 'Enter', 'keyCode': 13, bubbles: true});
                arguments[0].dispatchEvent(e);
            """, search_input)
            self.log("    ✓ Search initiated (pressed ENTER)", logging.DEBUG)
        except TimeoutException:
            self.log("    ✗ Could not find search input field with id='NEW_ALMA_MENU_TOP_NAV_Search_Text'", logging.ERROR)
            self.log("    → You need to inspect the page and update the selector in app.py", logging.ERROR)
            self.log("    → Check the saved HTML file in ~/Downloads/alma_page_debug_*.html", logging.ERROR)
            raise
        except Exception as e:
            self.log(f"    ✗ Error interacting with search field: {str(e)}", logging.ERROR)
            self.log(f"    → This may be due to popups/widgets blocking interaction", logging.ERROR)
            self.log(f"    → Try manually closing any popups in the browser and restart", logging.ERROR)
            raise
        
        # Wait for search results to load
        self.log("    Waiting for search results to load...", logging.DEBUG)
        
        # Enhanced wait: Check for actual search results content (SPA rendering)
        results_loaded = False
        max_wait = 20  # seconds
        check_interval = 2
        elapsed = 0
        
        while elapsed < max_wait and not results_loaded:
            try:
                # Check if page has actual content (not just the loading shell)
                content_check = driver.execute_script("""
                    // Check for indicators that the SPA has rendered content
                    var hasLinks = document.querySelectorAll('a, ex-link, button').length > 50;
                    var hasContent = document.body.textContent.length > 1000;
                    var notJustLoading = !document.querySelector('#__loading__') || 
                                        window.getComputedStyle(document.querySelector('#__loading__')).display === 'none';
                    
                    return {
                        hasLinks: hasLinks,
                        hasContent: hasContent,
                        notJustLoading: notJustLoading,
                        ready: hasLinks && hasContent && notJustLoading
                    };
                """)
                
                if content_check.get('ready'):
                    self.log(f"    ✓ Search results page rendered ({elapsed}s)", logging.DEBUG)
                    results_loaded = True
                    break
                else:
                    if elapsed % 4 == 0:  # Log every 4 seconds
                        self.log(f"    ⏳ Waiting for SPA content to render... ({elapsed}s)", logging.DEBUG)
                        self.log(f"       links={content_check.get('hasLinks')}, "
                               f"content={content_check.get('hasContent')}, "
                               f"loaded={content_check.get('notJustLoading')}", logging.DEBUG)
                    time.sleep(check_interval)
                    elapsed += check_interval
                    
            except Exception as e:
                if elapsed % 4 == 0:
                    self.log(f"    ⏳ Waiting for page... ({elapsed}s)", logging.DEBUG)
                time.sleep(check_interval)
                elapsed += check_interval
        
        if not results_loaded:
            self.log(f"    ⚠️ Page did not fully render within {max_wait}s, proceeding anyway...", logging.WARNING)
        
        # Additional safety wait for any animations/transitions
        time.sleep(2)
    
    def _navigate_to_representation(self, driver, rep_id: str) -> None:
        """
        Helper method: Navigate from search results to a specific representation page.
        
        This is shared between Function 11b (JPG upload) and Function 14b (thumbnail upload).
        
        Steps performed:
        1. Find and click "Digital Representations" link (Step 3)
        2. Handle any overlay popups
        3. Find and click specific representation ID link (Step 4)
        
        Args:
            driver: Selenium WebDriver instance
            rep_id: Representation ID to navigate to
            
        Raises:
            TimeoutException: If Digital Representations link or representation ID cannot be found
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        from pathlib import Path
        import time
        
        # DIAGNOSTIC: Check page state BEFORE attempting Step 3
        self.log("  🔍 PRE-STEP 3 DIAGNOSTICS:", logging.DEBUG)
        try:
            current_url = driver.current_url
            self.log(f"    Current URL: {current_url}", logging.DEBUG)
            
            # Check what's actually on the page
            page_state = driver.execute_script("""
                var allLinks = document.querySelectorAll('a, ex-link, button, [role="button"]');
                var digitalElements = [];
                var allText = [];
                
                for (var i = 0; i < allLinks.length && allText.length < 20; i++) {
                    var elem = allLinks[i];
                    var text = (elem.textContent || '').trim();
                    if (text && text.length > 0 && text.length < 150) {
                        allText.push({
                            tag: elem.tagName,
                            text: text,
                            visible: elem.offsetParent !== null
                        });
                    }
                    
                    var lowerText = text.toLowerCase();
                    if (lowerText.includes('digital') || lowerText.includes('representation')) {
                        digitalElements.push({
                            tag: elem.tagName,
                            text: text.substring(0, 100),
                            visible: elem.offsetParent !== null,
                            length: text.length
                        });
                    }
                }
                
                return {
                    totalLinks: allLinks.length,
                    digitalElements: digitalElements,
                    sampleLinks: allText.slice(0, 20)
                };
            """)
            
            self.log(f"    Total clickable elements: {page_state['totalLinks']}", logging.DEBUG)
            
            if page_state['digitalElements']:
                self.log(f"    Elements with 'digital'/'representation' ({len(page_state['digitalElements'])}):", logging.DEBUG)
                for elem in page_state['digitalElements'][:5]:
                    vis = "✓" if elem['visible'] else "✗ HIDDEN"
                    self.log(f"      {vis} {elem['tag']} (len={elem['length']}): {elem['text'][:70]}", logging.DEBUG)
            else:
                self.log("    ⚠️ NO elements with 'digital' or 'representation' found!", logging.WARNING)
                self.log("    Sample of available links:", logging.DEBUG)
                for idx, link in enumerate(page_state['sampleLinks'][:15], 1):
                    vis = "✓" if link['visible'] else "✗"
                    self.log(f"      {idx}. {vis} {link['tag']}: {link['text'][:60]}", logging.DEBUG)
                    
        except Exception as diag_err:
            self.log(f"    ⚠️ Diagnostic failed: {diag_err}", logging.WARNING)
        
        # Step 3: Click on "Digital Representations (X)" link
        self.log("  Step 3: Opening Digital Representations...", logging.DEBUG)
        
        # FIRST: Check for and close "Sections" fly-in that may be obscuring the link
        # Look for the close button (mat-icon) rather than trying to detect the panel
        self.log("    Checking for Sections fly-in/panel...", logging.DEBUG)
        try:
            # Check if the close button exists (indicates panel is present)
            close_button_check = driver.execute_script("""
                // Look for the mat-icon close button
                var closeIcon = document.querySelector('mat-icon.sel-id-ex-svg-icon-close');
                if (closeIcon && closeIcon.offsetParent !== null) {
                    return {found: true, visible: true};
                }
                
                // Also check for SVG close button
                var closeSvg = document.getElementById('Close');
                if (closeSvg && closeSvg.offsetParent !== null) {
                    return {found: true, visible: true};
                }
                
                // Check for any visible overlays/panels that might be obscuring content
                var overlays = document.querySelectorAll('[role="dialog"], aside, [class*="panel"], [class*="sidebar"], [class*="drawer"]');
                for (var i = 0; i < overlays.length; i++) {
                    if (overlays[i].offsetParent !== null && overlays[i].offsetWidth > 200) {
                        return {found: true, visible: true, type: 'overlay'};
                    }
                }
                
                return {found: false};
            """)
            
            if close_button_check.get('found'):
                self.log(f"    ⚠️ Sections panel/overlay detected (close button found)", logging.DEBUG)
                
                # Try multiple strategies to close the Sections panel
                close_attempts = [
                    # Strategy 1: Click the mat-icon close button (most specific - the actual clickable element)
                    """
                    // Look for the mat-icon with the specific class
                    var closeIcon = document.querySelector('mat-icon.sel-id-ex-svg-icon-close');
                    if (closeIcon && closeIcon.offsetParent !== null) {
                        closeIcon.click();
                        return 'mat-icon.sel-id-ex-svg-icon-close';
                    }
                    // Also try any mat-icon containing the Close SVG
                    var matIcons = document.querySelectorAll('mat-icon');
                    for (var i = 0; i < matIcons.length; i++) {
                        var svg = matIcons[i].querySelector('svg#Close');
                        if (svg && matIcons[i].offsetParent !== null) {
                            matIcons[i].click();
                            return 'mat-icon with svg#Close';
                        }
                    }
                    return false;
                    """,
                    # Strategy 2: Click the specific SVG close button by ID
                    """
                    var closeSvg = document.getElementById('Close');
                    if (closeSvg) {
                        // The SVG might be inside mat-icon, button, or other clickable container
                        var clickable = closeSvg.closest('mat-icon, button, a, [role="button"], [onclick]') || closeSvg.parentElement;
                        if (clickable) {
                            clickable.click();
                            return 'parent of svg#Close';
                        }
                        // If no parent container, try clicking the SVG itself
                        closeSvg.click();
                        return 'svg#Close directly';
                    }
                    return false;
                    """,
                    # Strategy 3: Press Escape key multiple times
                    """
                    for (var i = 0; i < 3; i++) {
                        var event = new KeyboardEvent('keydown', {'key': 'Escape', 'code': 'Escape', 'keyCode': 27, bubbles: true});
                        document.dispatchEvent(event);
                        document.body.dispatchEvent(event);
                    }
                    return 'escape key';
                    """,
                    # Strategy 4: Look for ANY visible close icon/button
                    """
                    // Try mat-icon close icons first
                    var matIcons = document.querySelectorAll('mat-icon[class*="close" i], mat-icon svg[id*="close" i]');
                    for (var i = 0; i < matIcons.length; i++) {
                        var icon = matIcons[i].tagName === 'svg' ? matIcons[i].closest('mat-icon') : matIcons[i];
                        if (icon && icon.offsetParent !== null) {
                            icon.click();
                            return 'mat-icon close';
                        }
                    }
                    // Then try SVG close icons
                    var closeSvgs = document.querySelectorAll('svg[id*="Close" i], svg[id*="close" i]');
                    for (var i = 0; i < closeSvgs.length; i++) {
                        if (closeSvgs[i].offsetParent !== null) {
                            var clickable = closeSvgs[i].closest('mat-icon, button, a, [role="button"]') || closeSvgs[i].parentElement;
                            clickable.click();
                            return 'svg close icon';
                        }
                    }
                    // Finally try regular close buttons
                    var closeBtns = document.querySelectorAll('button[aria-label*="close" i], button[title*="close" i], [class*="close-btn"], [class*="closeBtn"], .close, button.close');
                    for (var i = 0; i < closeBtns.length; i++) {
                        if (closeBtns[i].offsetParent !== null && closeBtns[i].offsetWidth > 0) {
                            closeBtns[i].click();
                            return 'close button';
                        }
                    }
                    return false;
                    """,
                    # Strategy 5: Click close buttons specifically in Sections-related elements
                    """
                    var panels = document.querySelectorAll('div, aside, section, [role="complementary"]');
                    for (var i = 0; i < panels.length; i++) {
                        var text = (panels[i].textContent || '').toLowerCase();
                        if (text.includes('sections') || text.includes('section')) {
                            // Look for mat-icon close button first
                            var closeIcon = panels[i].querySelector('mat-icon.sel-id-ex-svg-icon-close');
                            if (closeIcon && closeIcon.offsetParent !== null) {
                                closeIcon.click();
                                return 'mat-icon in sections panel';
                            }
                            // Then SVG close button
                            var closeSvg = panels[i].querySelector('svg#Close');
                            if (closeSvg && closeSvg.offsetParent !== null) {
                                var clickable = closeSvg.closest('mat-icon, button, a') || closeSvg.parentElement;
                                clickable.click();
                                return 'svg in sections panel';
                            }
                            // Then try regular close buttons
                            var closeBtn = panels[i].querySelector('button[aria-label*="close" i], button[title*="close" i], [class*="close"]');
                            if (closeBtn && closeBtn.offsetParent !== null) {
                                closeBtn.click();
                                return 'button in sections panel';
                            }
                        }
                    }
                    return false;
                    """
                ]
                
                for idx, script in enumerate(close_attempts, 1):
                    try:
                        result = driver.execute_script(script)
                        time.sleep(0.5)
                        if result:
                            self.log(f"    ✓ Close strategy {idx} succeeded: {result}", logging.DEBUG)
                        else:
                            self.log(f"    🔄 Close strategy {idx}: no element found", logging.DEBUG)
                    except Exception as e:
                        self.log(f"    ⚠️ Close strategy {idx} failed: {e}", logging.DEBUG)
                
                # Wait longer for the panel to close and animations to complete
                time.sleep(2)
                self.log("    ✓ Attempted to close Sections panel", logging.DEBUG)
                
                # Verify if panel is gone
                try:
                    still_visible = driver.execute_script("""
                        var panels = document.querySelectorAll('div, aside, section');
                        for (var i = 0; i < panels.length; i++) {
                            var text = (panels[i].textContent || '').toLowerCase();
                            if (text.includes('sections') && panels[i].offsetParent !== null && panels[i].offsetWidth > 200) {
                                return true;
                            }
                        }
                        return false;
                    """)
                    
                    if still_visible:
                        self.log("    ⚠️ Sections panel may still be visible", logging.WARNING)
                    else:
                        self.log("    ✓ Sections panel appears to be closed", logging.DEBUG)
                except Exception:
                    pass
            else:
                self.log("    ✓ No Sections panel detected", logging.DEBUG)
                
        except Exception as sections_err:
            self.log(f"    ⚠️ Error checking Sections panel: {sections_err}", logging.DEBUG)
        
        self.log("    Waiting for Digital Representations link to be clickable...", logging.DEBUG)
        
        try:
            # Try multiple link text variations: "Digital (X)" or "Digital Representations (X)"
            # Strategy 1: ex-link with "Digital Representation" (full text)
            try:
                digital_reps_link = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//ex-link[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'digital representation') and string-length(normalize-space(.)) < 100]"))
                )
                self.log("    ✓ Found Digital Reps link (full text: 'Digital Representations')", logging.DEBUG)
            except TimeoutException:
                # Strategy 2: ex-link with just "Digital (" - the shorter version
                try:
                    digital_reps_link = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//ex-link[starts-with(normalize-space(.), 'Digital (') and string-length(normalize-space(.)) < 50]"))
                    )
                    self.log("    ✓ Found Digital Reps link (short text: 'Digital (X)')", logging.DEBUG)
                except TimeoutException:
                    # Strategy 3: Try button element
                    try:
                        digital_reps_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'digital representation') and string-length(normalize-space(.)) < 100]"))
                        )
                        self.log("    ✓ Found Digital Reps link (button element)", logging.DEBUG)
                    except TimeoutException:
                        # Strategy 4: Button with short text "Digital ("
                        try:
                            digital_reps_link = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//button[starts-with(normalize-space(.), 'Digital (') and string-length(normalize-space(.)) < 50]"))
                            )
                            self.log("    ✓ Found Digital Reps link (button with short text)", logging.DEBUG)
                        except TimeoutException:
                            # Strategy 5: Try the ex-link with span class selector
                            digital_reps_link = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, "//ex-link[.//span[contains(@class, 'sel-smart-link-nggeneralsectiontitleall_titles_details_digital_representations')]]"))
                            )
                            self.log("    ✓ Found Digital Reps link (ex-link/span selector)", logging.DEBUG)
        except TimeoutException:
            # All methods failed - gather extensive diagnostics
            self.log("    ✗ Digital Representations link not found with any selector", logging.ERROR)
            
            # DIAGNOSTIC: Save page state for analysis
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            debug_file = Path.home() / "Downloads" / f"step3_failure_{timestamp}.html"
            
            try:
                page_source = driver.page_source
                debug_file.write_text(page_source, encoding='utf-8')
                self.log(f"    📄 Page HTML saved to: {debug_file}", logging.ERROR)
            except Exception as save_err:
                self.log(f"    ⚠️ Could not save page HTML: {save_err}", logging.ERROR)
            
            # DIAGNOSTIC: Log current URL
            try:
                current_url = driver.current_url
                self.log(f"    🌐 Current URL: {current_url}", logging.ERROR)
            except Exception:
                pass
            
            # DIAGNOSTIC: Find all clickable elements with "digital" or "representation" text
            try:
                clickable_elements = driver.execute_script("""
                    var elements = [];
                    var allElements = document.querySelectorAll('a, button, ex-link, [role="button"], [onclick]');
                    
                    for (var i = 0; i < allElements.length; i++) {
                        var elem = allElements[i];
                        var text = (elem.textContent || elem.innerText || '').trim();
                        var lowerText = text.toLowerCase();
                        
                        if (lowerText.includes('digital') || lowerText.includes('representation')) {
                            elements.push({
                                tag: elem.tagName,
                                text: text.substring(0, 100),
                                textLength: text.length,
                                visible: elem.offsetParent !== null,
                                class: elem.className
                            });
                        }
                    }
                    
                    return elements;
                """)
                
                if clickable_elements:
                    self.log(f"    🔍 Found {len(clickable_elements)} elements with 'digital' or 'representation':", logging.ERROR)
                    for idx, elem in enumerate(clickable_elements[:10], 1):  # Show first 10
                        visibility = "visible" if elem['visible'] else "HIDDEN"
                        self.log(f"       {idx}. {elem['tag']} ({visibility}, len={elem['textLength']}): {elem['text'][:80]}", logging.ERROR)
                else:
                    self.log("    ⚠️ NO elements found containing 'digital' or 'representation'", logging.ERROR)
                    
            except Exception as diag_err:
                self.log(f"    ⚠️ Diagnostic scan failed: {diag_err}", logging.ERROR)
            
            # DIAGNOSTIC: Check if we're still on search results or moved to detail page
            try:
                page_indicators = driver.execute_script("""
                    return {
                        hasSearchResults: document.querySelector('[class*="search-result"], [class*="result-list"]') !== null,
                        hasTitleList: document.querySelector('table, ul, [class*="list"]') !== null,
                        bodyClasses: document.body.className,
                        mainContentId: document.querySelector('main, [role="main"], #main-content') ? 
                            (document.querySelector('main, [role="main"], #main-content').id || 'no-id') : 'no-main-element'
                    };
                """)
                
                self.log(f"    📊 Page state: searchResults={page_indicators['hasSearchResults']}, "
                        f"titleList={page_indicators['hasTitleList']}, "
                        f"mainContent={page_indicators['mainContentId']}", logging.ERROR)
                        
            except Exception:
                pass
            
            raise TimeoutException("Digital Representations link not found after trying all selectors - see diagnostics above")
        
        # Additional wait to ensure any overlays/animations are complete
        time.sleep(1)
        
        # Get info about the link we found (for debugging if needed)
        try:
            link_info = driver.execute_script("""
                return {
                    tag: arguments[0].tagName,
                    text: arguments[0].textContent.trim().substring(0, 50)
                };
            """, digital_reps_link)
            self.log(f"    🔍 Clicking: {link_info['tag']} - '{link_info['text']}'", logging.DEBUG)
        except Exception:
            pass
        
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView(true);", digital_reps_link)
        time.sleep(0.5)
        
        # Try regular click first
        try:
            digital_reps_link.click()
            self.log("    ✓ Clicked Digital Reps link", logging.DEBUG)
        except Exception as click_err:
            # If regular click fails, use JavaScript
            self.log(f"    ⚠️ Regular click failed, trying JavaScript...", logging.DEBUG)
            driver.execute_script("arguments[0].click();", digital_reps_link)
            self.log("    ✓ Clicked Digital Reps link (JavaScript)", logging.DEBUG)
        
        # Wait for the Digital Representations section to load (SPA/AJAX)
        self.log("    ⏳ Waiting for Digital Representations section to load...", logging.DEBUG)
        time.sleep(3)  # Initial wait for AJAX/rendering
        
        # Check for and close any overlay/popup that might obscure the content
        try:
            close_button = driver.find_element(By.CSS_SELECTOR, ".sel-id-ex-svg-icon-close")
            close_button.click()
            self.log("    ✓ Closed overlay popup", logging.DEBUG)
            time.sleep(1)
        except NoSuchElementException:
            pass  # No popup, continue
        except Exception:
            pass  # Popup handling failed, continue anyway
        
        # Wait for representation list to  populate (wait for links with 12+ digit IDs)
        representation_content_loaded = False
        max_wait = 15  # seconds
        wait_interval = 1
        elapsed = 0
        
        while elapsed < max_wait and not representation_content_loaded:
            try:
                # Check if representation ID links have appeared (12+ digit numbers)
                rep_count = driver.execute_script("""
                    var links = document.querySelectorAll('a');
                    var count = 0;
                    for (var i = 0; i < links.length; i++) {
                        if (links[i].textContent.trim().match(/^\\d{12,}$/)) {
                            count++;
                        }
                    }
                    return count;
                """)
                
                if rep_count > 0:
                    self.log(f"    ✓ Representation list loaded ({rep_count} representation(s) found)", logging.DEBUG)
                    representation_content_loaded = True
                    break
                else:
                    if elapsed % 3 == 0:  # Log every 3 seconds
                        self.log(f"    ⏳ Waiting for representation links... ({elapsed}s)", logging.DEBUG)
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    
            except Exception as e:
                time.sleep(wait_interval)
                elapsed += wait_interval
        
        if not representation_content_loaded:
            self.log(f"    ⚠️ Representation links did not appear within {max_wait}s, proceeding anyway...", logging.WARNING)
        
        # Additional safety wait
        time.sleep(1)
        
        # Legacy check for list structure (kept for compatibility)
        try:
            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.XPATH, "//table | //ul | //div[contains(@class, 'list')]")
            )
            self.log("    ✓ Representation list structure confirmed", logging.DEBUG)
        except TimeoutException:
            self.log("    ⚠️ Could not detect representation list structure", logging.WARNING)
        
        # Step 4: Click on the specific representation ID link
        self.log(f"  Step 4: Looking for representation {rep_id}...", logging.DEBUG)
        
        # Scroll the page to ensure any representation list is visible
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)
        
        try:
            # Try multiple strategies to find the representation ID link
            # Strategy 1: Exact link text (give this more time as it's most reliable)
            try:
                rep_link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, rep_id))
                )
                self.log(f"    ✓ Found representation (exact link text)", logging.DEBUG)
            except TimeoutException:
                # Strategy 2: Partial link text
                try:
                    rep_link = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, rep_id))
                    )
                    self.log(f"    ✓ Found representation (partial link text)", logging.DEBUG)
                except TimeoutException:
                    # Strategy 3: XPath text search
                    try:
                        rep_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{rep_id}')]"))
                        )
                        self.log(f"    ✓ Found representation (XPath text search)", logging.DEBUG)
                    except TimeoutException:
                        # Strategy 4: XPath anchor search
                        rep_link = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, f"//a[contains(., '{rep_id}')]"))
                        )
                        self.log(f"    ✓ Found representation (XPath anchor search)", logging.DEBUG)
            
            # Try clicking, but if it's intercepted, use JavaScript
            try:
                rep_link.click()
                self.log("    ✓ Clicked representation link", logging.DEBUG)
            except Exception as click_err:
                self.log(f"    ⚠️ Normal click failed ({str(click_err)}), using JavaScript...", logging.WARNING)
                driver.execute_script("arguments[0].click();", rep_link)
                self.log("    ✓ Clicked representation link (via JavaScript)", logging.DEBUG)
            
            time.sleep(3)
        except TimeoutException:
            self.log(f"    ✗ Could not find representation ID {rep_id} on page", logging.ERROR)
            self.log(f"    → The representation might not exist in this record", logging.ERROR)
            self.log(f"    → Or the Digital Representations section didn't fully load", logging.ERROR)
            
            # Try to list what's actually on the page
            try:
                links = driver.execute_script("""
                    var links = document.querySelectorAll('a');
                    var linkTexts = [];
                    for (var i = 0; i < Math.min(links.length, 20); i++) {
                        if (links[i].textContent.trim()) {
                            linkTexts.push(links[i].textContent.trim().substring(0, 50));
                        }
                    }
                    return linkTexts;
                """)
                self.log(f"    ℹ️  First 20 links on page: {links}", logging.ERROR)
            except Exception as list_err:
                self.log(f"    ⚠️ Could not list links: {list_err}", logging.WARNING)
            
            # Save debug info
            try:
                from datetime import datetime
                screenshot_file = Path.home() / "Downloads" / f"alma_missing_rep_{rep_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                driver.save_screenshot(str(screenshot_file))
                self.log(f"    📸 Screenshot saved: {screenshot_file}", logging.ERROR)
                
                html_file = Path.home() / "Downloads" / f"alma_missing_rep_{rep_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                self.log(f"    📄 Page source saved: {html_file}", logging.ERROR)
            except Exception as debug_err:
                self.log(f"    ⚠️ Could not save debug files: {debug_err}", logging.WARNING)
            
            raise
    
    def upload_thumbnails_selenium(self, csv_file_path: str, progress_callback=None, log_level: str = "INFO") -> tuple[bool, str, int, int, str | None]:
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
            log_level: Minimum log level to display (ERROR, WARNING, INFO, DEBUG)
            
        Returns:
            tuple: (success: bool, message: str, success_count: int, failed_count: int, failed_csv_path: str | None)
        """
        # Convert log level string to logging constant
        min_log_level = getattr(logging, log_level, logging.INFO)
        # Store original min level to restore later
        original_min_level = self.min_log_level
        # Set temporary min level for this function
        self.min_log_level = min_log_level
        
        # Suppress noisy loggers from Selenium and urllib3
        # These libraries log every HTTP request at DEBUG level, flooding the terminal
        logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
        
        import csv
        from pathlib import Path
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select
        from selenium.common.exceptions import TimeoutException, NoSuchElementException
        import time
        
        try:
            self.log(f"Starting Function 14b: Upload Thumbnails via Selenium")
            self.log(f"Log level: {log_level}")
            self.log(f"Reading CSV file: {csv_file_path}", logging.DEBUG)
            
            # Read CSV file
            csv_path = Path(csv_file_path)
            if not csv_path.exists():
                return False, f"CSV file not found: {csv_file_path}", 0, 0, None
            
            records = []
            fieldnames = None
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames  # Save field names for later
                for row in reader:
                    records.append(row)
            
            if not records:
                return False, "No records found in CSV file", 0, 0, None
            
            self.log(f"Loaded {len(records)} record(s) from CSV")
            
            # Track successful uploads to filter CSV later
            successful_mms_ids = set()
            
            # Setup browser (shared helper method)
            try:
                driver = self._setup_selenium_browser()
                
                # Perform initial login and focus (shared helper method)
                self._perform_initial_alma_login(driver)
            except Exception as e:
                return False, f"Could not start Firefox: {str(e)}. Please ensure GeckoDriver is installed (brew install geckodriver).", 0, 0, None
            
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
                    self.log(f"  Rep ID: {rep_id}", logging.DEBUG)
                    self.log(f"  File: {filename}", logging.DEBUG)
                    
                    # Verify file exists
                    file_path = Path(filename)
                    if not file_path.exists():
                        self.log(f"  ✗ File not found: {filename}", logging.ERROR)
                        failed_count += 1
                        self.log(f"\n⚠️  STOPPING ON FIRST FAILURE for debugging", logging.WARNING)
                        self.log(f"    Successes so far: {success_count}", logging.INFO)
                        self.log(f"    Failures: {failed_count}", logging.INFO)
                        self.log(f"    Remaining: {len(records) - current}", logging.INFO)
                        break
                    
                    # Verify file is not empty (zero bytes)
                    file_size = file_path.stat().st_size
                    if file_size == 0:
                        self.log(f"  ⚠️  File is empty (0 bytes): {filename}", logging.WARNING)
                        self.log(f"    → Skipping zero-byte file", logging.WARNING)
                        continue
                    
                    try:
                        # Steps 1-2: Search for representation (shared helper method)
                        self._search_for_representation(driver, rep_id)
                        
                        # Steps 3-4: Navigate to the specific representation (shared helper method)
                        self._navigate_to_representation(driver, rep_id)
                        
                        # Wait for representation page to load
                        time.sleep(2)
                        
                        # # Debug: Save screenshot and HTML of representation page (COMMENTED OUT - fills up Downloads)
                        # try:
                        #     screenshot_file = Path.home() / "Downloads" / f"alma_rep_page_{rep_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        #     driver.save_screenshot(str(screenshot_file))
                        #     self.log(f"    📸 Representation page screenshot: {screenshot_file}")
                        #     
                        #     html_file = Path.home() / "Downloads" / f"alma_rep_page_{rep_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                        #     with open(html_file, 'w', encoding='utf-8') as f:
                        #         f.write(driver.page_source)
                        #     self.log(f"    📄 Representation page HTML: {html_file}")
                        # except Exception as debug_err:
                        #     self.log(f"    ⚠️ Could not save debug files: {debug_err}", logging.WARNING)
                        
                        # Step 5: Find and use the thumbnail upload control
                        self.log("  Step 5: Looking for thumbnail upload control...", logging.DEBUG)
                        
                        try:
                            # File input has id="pageBeansavedFile"
                            file_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.ID, "pageBeansavedFile"))
                            )
                            self.log("    ✓ Found file input (id=pageBeansavedFile)")
                        except TimeoutException:
                            # Fallback: try generic file input selector
                            self.log("    ⚠️ ID not found, trying input[type='file']...", logging.WARNING)
                            file_input = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                            )
                            self.log("    ✓ Found file input using type='file'")
                        
                        file_input.send_keys(str(file_path.absolute()))
                        self.log(f"    ✓ File path sent to input", logging.DEBUG)
                        
                        # Trigger change event to ensure JavaScript recognizes the file selection
                        try:
                            driver.execute_script("""
                                var input = arguments[0];
                                var event = new Event('change', { bubbles: true });
                                input.dispatchEvent(event);
                            """, file_input)
                            self.log(f"    ✓ Triggered 'change' event on file input", logging.DEBUG)
                        except Exception as event_err:
                            self.log(f"    ⚠️ Could not trigger change event: {event_err}", logging.DEBUG)
                        
                        # Verify the file was actually selected
                        self.log(f"    🔍 Verifying file selection...", logging.DEBUG)
                        time.sleep(1)  # Brief wait for UI to update
                        
                        try:
                            # Check if the file input has a value (the filename)
                            file_input_value = driver.execute_script("""
                                var input = document.getElementById('pageBeansavedFile');
                                if (!input) input = document.querySelector('input[type="file"]');
                                if (input && input.files && input.files.length > 0) {
                                    return {
                                        selected: true,
                                        filename: input.files[0].name,
                                        size: input.files[0].size
                                    };
                                }
                                return {selected: false};
                            """)
                            
                            if file_input_value.get('selected'):
                                self.log(f"    ✓ File selected: {file_input_value.get('filename')} ({file_input_value.get('size')} bytes)", logging.DEBUG)
                            else:
                                self.log(f"    ⚠️ File selection not confirmed - input may not have accepted the file", logging.WARNING)
                        except Exception as verify_err:
                            self.log(f"    ⚠️ Could not verify file selection: {verify_err}", logging.DEBUG)
                        
                        # Wait for file to be processed
                        time.sleep(1)
                        
                        # Step 6: Click Save button
                        self.log("  Step 6: Saving changes...")
                        try:
                            save_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.ID, "PAGE_BUTTONS_cbuttonsave"))
                            )
                            save_button.click()
                            self.log("    ✓ Clicked Save button")
                        except TimeoutException:
                            # Fallback: try finding button by text
                            self.log("    ⚠️ Save button ID not found, trying button text...", logging.WARNING)
                            save_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Save')]"))
                            )
                            save_button.click()
                            self.log("    ✓ Clicked Save button (via text)")
                        
                        # Wait for save to complete
                        time.sleep(3)
                        self.log("    ✓ Changes saved")
                        
                        self.log(f"  ✓ Successfully uploaded thumbnail for {mms_id}")
                        success_count += 1
                        successful_mms_ids.add(mms_id)  # Track success for CSV filtering
                        
                    except TimeoutException as e:
                        self.log(f"  ✗ Timeout waiting for page element: {str(e)}", logging.ERROR)
                        self.log(f"    This may indicate:", logging.ERROR)
                        self.log(f"    - The page structure has changed (check screenshot/HTML in Downloads)", logging.ERROR)
                        self.log(f"    - The search returned no results (wrong search settings?)", logging.ERROR)
                        self.log(f"    - The page didn't load in time (network issues?)", logging.ERROR)
                        failed_count += 1
                        self.log(f"\n⚠️  STOPPING ON FIRST FAILURE for debugging", logging.WARNING)
                        self.log(f"    Successes so far: {success_count}", logging.INFO)
                        self.log(f"    Failures: {failed_count}", logging.INFO)
                        self.log(f"    Remaining: {len(records) - current}", logging.INFO)
                        break
                    except NoSuchElementException as e:
                        self.log(f"  ✗ Could not find required element: {str(e)}", logging.ERROR)
                        failed_count += 1
                        self.log(f"\n⚠️  STOPPING ON FIRST FAILURE for debugging", logging.WARNING)
                        self.log(f"    Successes so far: {success_count}", logging.INFO)
                        self.log(f"    Failures: {failed_count}", logging.INFO)
                        self.log(f"    Remaining: {len(records) - current}", logging.INFO)
                        break
                    except Exception as e:
                        self.log(f"  ✗ Error uploading thumbnail: {str(e)}", logging.ERROR)
                        import traceback
                        self.log(traceback.format_exc(), logging.DEBUG)
                        failed_count += 1
                        self.log(f"\n⚠️  STOPPING ON FIRST FAILURE for debugging", logging.WARNING)
                        self.log(f"    Successes so far: {success_count}", logging.INFO)
                        self.log(f"    Failures: {failed_count}", logging.INFO)
                        self.log(f"    Remaining: {len(records) - current}", logging.INFO)
                        break
                
            finally:
                # Note: We don't close the driver since we're using an existing session
                self.log("\n⚠️ NOTE: Firefox browser has been left open for your review")
                self.log("You can manually close Firefox when done reviewing the results", logging.DEBUG)
            
            # Create a new CSV with only failed records for next iteration
            failed_csv_path = None
            if success_count > 0 and failed_count > 0:
                # Filter out successful records
                failed_records = [r for r in records if r['mms_id'] not in successful_mms_ids]
                
                # Create new CSV filename with timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                failed_csv_path = csv_path.parent / f"{csv_path.stem}_failed_{timestamp}.csv"
                
                # Write failed records to new CSV
                with open(failed_csv_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(failed_records)
                
                self.log(f"\n📄 Created CSV with {failed_count} failed record(s): {failed_csv_path}")
                self.log(f"   Use this file for the next iteration to retry only failed uploads")
                failed_csv_path = str(failed_csv_path.absolute())
            elif failed_count > 0:
                self.log(f"\n⚠️ All {failed_count} upload(s) failed - original CSV unchanged")
            
            message = f"Thumbnail upload complete: {success_count} uploaded, {failed_count} failed"
            self.log(message)
            
            if failed_count > 0:
                self.log(f"⚠️ {failed_count} upload(s) failed - check logs for details", logging.WARNING)
            
            return True, message, success_count, failed_count, failed_csv_path
            
        except Exception as e:
            error_msg = f"Error in selenium upload: {str(e)}"
            self.log(error_msg, logging.ERROR)
            import traceback
            self.log(traceback.format_exc(), logging.ERROR)
            return False, error_msg, 0, 0, None
        finally:
            # Restore original min log level
            self.min_log_level = original_min_level
    
    def upload_jpg_selenium(self, csv_file_path: str, progress_callback=None, log_level: str = "INFO") -> tuple[bool, str, int, int, str | None]:
        """
        Function 11b: DISABLED - Upload JPG files to Alma representations using Selenium
        
        This function has been disabled due to insurmountable automation challenges with Alma's file upload system.
        """
        error_msg = (
            "❌ FUNCTION 11b DISABLED ❌\n\n"
            "Sorry, functions 11a and 11b have been disabled and abandoned because Alma's incompetence "
            "won't allow automation to replace a human, not even for the mind-numbing and error-prone task "
            "of attaching a known digital file to an empty representation.\n\n"
            "Said human must accept their fate and faithfully serve the evil that is Alma, toiling in "
            "clickity, click, click, click hell for eternity."
        )
        self.log(error_msg, logging.ERROR)
        return False, error_msg, 0, 0, None
    
    ### ARCHIVED FUNCTION 11b CODE - moved to inactive_functions.py ###
    # Original implementation preserved for potential future use if Alma's
    # incompetence is ever resolved. See inactive_functions.py for details.
    
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
    
    def analyze_identifier_match(self, mms_ids: list, progress_callback=None) -> tuple[bool, str, str | None]:
        """
        Function 15: Analyze dc:identifier fields for MMS ID matching
        
        Processes MMS IDs and categorizes them based on whether they have a dc:identifier
        that exactly matches the MMS ID. Creates up to three CSV files in a temporary directory:
        1. identifier_matching_{timestamp}.csv - Records WITH matching dc:identifier
        2. identifier_non_matching_{timestamp}.csv - Records WITHOUT matching dc:identifier
        3. identifier_failed_{timestamp}.csv - Records that failed to process (with error messages)
        
        Args:
            mms_ids: List of MMS IDs to analyze
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str, output_dir_path: str | None)
        """
        import csv
        from datetime import datetime
        from pathlib import Path
        
        # Create timestamped output directory in Downloads folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads_dir = Path.home() / "Downloads"
        output_dir = downloads_dir / f"CABB_identifier_analysis_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        matching_file = output_dir / f"identifier_matching_{timestamp}.csv"
        non_matching_file = output_dir / f"identifier_non_matching_{timestamp}.csv"
        failed_file = output_dir / f"identifier_failed_{timestamp}.csv"
        
        self.log(f"Starting identifier match analysis for {len(mms_ids)} records")
        self.log(f"Output directory: {output_dir.absolute()}")
        self.log(f"Output files: {matching_file.name}, {non_matching_file.name}, {failed_file.name}")
        
        try:
            matching_rows = []
            non_matching_rows = []
            failed_rows = []
            
            success_count = 0
            failed_count = 0
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
                    record_index = batch_start + i + 1
                    mms_id = batch_ids[i]
                    
                    try:
                        # Check if record was successfully fetched
                        if mms_id in batch_records:
                            # Set as current record for field extraction
                            self.current_record = batch_records[mms_id]
                            
                            # Extract all dc:identifier values
                            identifiers = self._extract_dc_field("identifier", "dc")
                            
                            # Check if MMS ID is in the identifier list
                            if mms_id in identifiers:
                                # MMS ID matches - add to matching CSV
                                matching_rows.append({
                                    "MMS ID": mms_id,
                                    "dc:identifier": mms_id
                                })
                                self.log(f"  ✓ {mms_id}: MATCH found", logging.DEBUG)
                            else:
                                # No match - add to non-matching CSV with all identifiers
                                row = {"MMS ID": mms_id}
                                for idx, identifier in enumerate(identifiers, start=1):
                                    row[f"dc:identifier_{idx}"] = identifier
                                non_matching_rows.append(row)
                                self.log(f"  ⊘ {mms_id}: No match (found {len(identifiers)} identifiers)", logging.DEBUG)
                            
                            success_count += 1
                        else:
                            self.log(f"Record not returned in batch: {mms_id}", logging.WARNING)
                            failed_rows.append({
                                "MMS ID": mms_id,
                                "Error": "Record not returned in batch API call"
                            })
                            failed_count += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_callback(record_index, total)
                        
                        if record_index % 50 == 0:
                            self.log(f"Analyzed {record_index}/{total} records")
                            
                    except Exception as e:
                        self.log(f"Error analyzing {mms_id}: {str(e)}", logging.ERROR)
                        failed_rows.append({
                            "MMS ID": mms_id,
                            "Error": str(e)
                        })
                        failed_count += 1
            
            # Write matching identifiers CSV
            if matching_rows:
                with open(matching_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["MMS ID", "dc:identifier"])
                    writer.writeheader()
                    writer.writerows(matching_rows)
                self.log(f"✓ Created {matching_file.name} with {len(matching_rows)} records")
            else:
                self.log("No records with matching dc:identifier found")
            
            # Write non-matching identifiers CSV
            if non_matching_rows:
                # Determine maximum number of identifiers across all rows
                max_identifiers = 0
                for row in non_matching_rows:
                    num_identifiers = len([k for k in row.keys() if k.startswith("dc:identifier_")])
                    max_identifiers = max(max_identifiers, num_identifiers)
                
                # Build fieldnames
                fieldnames = ["MMS ID"]
                for i in range(1, max_identifiers + 1):
                    fieldnames.append(f"dc:identifier_{i}")
                
                with open(non_matching_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(non_matching_rows)
                self.log(f"✓ Created {non_matching_file.name} with {len(non_matching_rows)} records")
            else:
                self.log("All records have matching dc:identifier!")
            
            # Write failed records CSV
            if failed_rows:
                with open(failed_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["MMS ID", "Error"])
                    writer.writeheader()
                    writer.writerows(failed_rows)
                self.log(f"✓ Created {failed_file.name} with {len(failed_rows)} failed records")
            else:
                self.log("No failed records!")
            
            message = f"Analysis complete: {len(matching_rows)} with matching ID, {len(non_matching_rows)} without match, {failed_count} failed. Output directory: {output_dir.absolute()}"
            self.log(message)
            self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
            return True, message, str(output_dir.absolute())
                
        except Exception as e:
            error_msg = f"Error in identifier match analysis: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg, None
    
    def add_mms_id_identifier(self, mms_ids: list, progress_callback=None) -> tuple[bool, str, str | None]:
        """
        Function 16: Add MMS ID as dc:identifier
        
        Processes MMS IDs and adds the bare MMS ID as a dc:identifier field if not already present.
        Creates up to three CSV files in a temporary directory:
        1. mms_id_already_present_{timestamp}.csv - Records that already have MMS ID as dc:identifier
        2. mms_id_added_{timestamp}.csv - Records that were updated with MMS ID dc:identifier
        3. mms_id_failed_{timestamp}.csv - Records that failed to process (with error messages)
        
        Special handling for duplicates:
        - If a record has TWO or more IDENTICAL dc:identifier values, REPLACE one with the MMS ID
        - Otherwise, ADD the MMS ID as a new dc:identifier field
        
        Args:
            mms_ids: List of MMS IDs to process
            progress_callback: Optional callback function(current, total) for progress updates
            
        Returns:
            tuple: (success: bool, message: str, output_dir_path: str | None)
        """
        import csv
        from datetime import datetime
        from pathlib import Path
        
        # Create timestamped output directory in Downloads folder
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads_dir = Path.home() / "Downloads"
        output_dir = downloads_dir / f"CABB_mms_id_identifier_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        already_present_file = output_dir / f"mms_id_already_present_{timestamp}.csv"
        added_file = output_dir / f"mms_id_added_{timestamp}.csv"
        failed_file = output_dir / f"mms_id_failed_{timestamp}.csv"
        
        self.log(f"Starting MMS ID identifier addition for {len(mms_ids)} records")
        self.log(f"Output directory: {output_dir.absolute()}")
        self.log(f"Output files: {already_present_file.name}, {added_file.name}, {failed_file.name}")
        
        try:
            already_present_rows = []
            added_rows = []
            failed_rows = []
            
            success_count = 0
            failed_count = 0
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
                    record_index = batch_start + i + 1
                    mms_id = batch_ids[i]
                    
                    try:
                        # Check if record was successfully fetched
                        if mms_id in batch_records:
                            # Set as current record for field extraction
                            self.current_record = batch_records[mms_id]
                            
                            # Extract all dc:identifier values
                            identifiers = self._extract_dc_field("identifier", "dc")
                            
                            # Check if MMS ID is already in the identifier list
                            if mms_id in identifiers:
                                # MMS ID already present - add to report CSV
                                already_present_rows.append({
                                    "MMS ID": mms_id,
                                    "dc:identifier": mms_id
                                })
                                self.log(f"  ⊘ {mms_id}: MMS ID already in dc:identifier", logging.DEBUG)
                                success_count += 1
                            else:
                                # MMS ID not present - need to add it
                                # Check for duplicate identifiers
                                identifier_counts = {}
                                for identifier in identifiers:
                                    identifier_counts[identifier] = identifier_counts.get(identifier, 0) + 1
                                
                                # Find duplicates (count > 1)
                                duplicates = {k: v for k, v in identifier_counts.items() if v > 1}
                                
                                if duplicates:
                                    # Replace one duplicate with MMS ID
                                    duplicate_to_replace = list(duplicates.keys())[0]
                                    self.log(f"  Found duplicate identifier: {duplicate_to_replace} (appears {duplicates[duplicate_to_replace]} times)")
                                    
                                    # Update the record - replace one duplicate
                                    update_success, update_message = self._replace_duplicate_identifier(
                                        mms_id, duplicate_to_replace, mms_id
                                    )
                                    
                                    if update_success:
                                        added_rows.append({
                                            "MMS ID": mms_id,
                                            "Action": "Replaced duplicate",
                                            "Old Value": duplicate_to_replace,
                                            "New Value": mms_id
                                        })
                                        self.log(f"  ✓ {mms_id}: Replaced duplicate '{duplicate_to_replace}' with MMS ID", logging.DEBUG)
                                        success_count += 1
                                    else:
                                        failed_rows.append({
                                            "MMS ID": mms_id,
                                            "Error": f"Failed to replace duplicate: {update_message}"
                                        })
                                        self.log(f"  ✗ {mms_id}: {update_message}", logging.ERROR)
                                        failed_count += 1
                                else:
                                    # No duplicates - add MMS ID as new identifier
                                    update_success, update_message = self._add_identifier_field(mms_id, mms_id)
                                    
                                    if update_success:
                                        added_rows.append({
                                            "MMS ID": mms_id,
                                            "Action": "Added new identifier",
                                            "Old Value": "",
                                            "New Value": mms_id
                                        })
                                        self.log(f"  ✓ {mms_id}: Added MMS ID as new dc:identifier", logging.DEBUG)
                                        success_count += 1
                                    else:
                                        failed_rows.append({
                                            "MMS ID": mms_id,
                                            "Error": f"Failed to add identifier: {update_message}"
                                        })
                                        self.log(f"  ✗ {mms_id}: {update_message}", logging.ERROR)
                                        failed_count += 1
                        else:
                            self.log(f"Record not returned in batch: {mms_id}", logging.WARNING)
                            failed_rows.append({
                                "MMS ID": mms_id,
                                "Error": "Record not returned in batch API call"
                            })
                            failed_count += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_callback(record_index, total)
                        
                        if record_index % 50 == 0:
                            self.log(f"Processed {record_index}/{total} records")
                            
                    except Exception as e:
                        self.log(f"Error processing {mms_id}: {str(e)}", logging.ERROR)
                        failed_rows.append({
                            "MMS ID": mms_id,
                            "Error": str(e)
                        })
                        failed_count += 1
            
            # Write already-present CSV
            if already_present_rows:
                with open(already_present_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["MMS ID", "dc:identifier"])
                    writer.writeheader()
                    writer.writerows(already_present_rows)
                self.log(f"✓ Created {already_present_file.name} with {len(already_present_rows)} records")
            else:
                self.log("No records with MMS ID already present")
            
            # Write added identifiers CSV
            if added_rows:
                with open(added_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["MMS ID", "Action", "Old Value", "New Value"])
                    writer.writeheader()
                    writer.writerows(added_rows)
                self.log(f"✓ Created {added_file.name} with {len(added_rows)} records")
            else:
                self.log("No records were updated")
            
            # Write failed records CSV
            if failed_rows:
                with open(failed_file, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=["MMS ID", "Error"])
                    writer.writeheader()
                    writer.writerows(failed_rows)
                self.log(f"✓ Created {failed_file.name} with {len(failed_rows)} failed records")
            else:
                self.log("No failed records!")
            
            message = f"MMS ID identifier addition complete: {len(already_present_rows)} already present, {len(added_rows)} updated, {failed_count} failed. Output directory: {output_dir.absolute()}"
            self.log(message)
            self.log(f"API efficiency: {total_batches} batch calls vs {total} individual calls (saved {total - total_batches} calls)")
            return True, message, str(output_dir.absolute())
                
        except Exception as e:
            error_msg = f"Error in MMS ID identifier addition: {str(e)}"
            self.log(error_msg, logging.ERROR)
            return False, error_msg, None
    
    def _replace_duplicate_identifier(self, mms_id: str, old_value: str, new_value: str) -> tuple[bool, str]:
        """
        Replace one occurrence of a duplicate dc:identifier with a new value
        
        Args:
            mms_id: The MMS ID of the record
            old_value: The duplicate identifier value to replace
            new_value: The new identifier value (typically the MMS ID)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Get the Alma API base URL
            api_url = self._get_alma_api_url()
            
            # Fetch the record as XML
            self.log(f"Fetching record {mms_id} for duplicate replacement", logging.DEBUG)
            headers = {'Accept': 'application/xml'}
            response = requests.get(
                f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={self.api_key}",
                headers=headers
            )
            
            if response.status_code != 200:
                return False, f"Failed to fetch record: {response.status_code}"
            
            # Parse XML
            root = ET.fromstring(response.text)
            
            # Register namespaces
            namespaces_to_register = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
            }
            for prefix, uri in namespaces_to_register.items():
                ET.register_namespace(prefix, uri)
            
            # Find all dc:identifier elements
            search_namespaces = {'dc': 'http://purl.org/dc/elements/1.1/'}
            identifiers = root.findall('.//dc:identifier', search_namespaces)
            
            # Replace the first occurrence of old_value
            replaced = False
            for identifier in identifiers:
                if identifier.text == old_value and not replaced:
                    identifier.text = new_value
                    replaced = True
                    break
            
            if not replaced:
                return False, f"Duplicate identifier '{old_value}' not found in record"
            
            # Convert back to XML
            xml_bytes = ET.tostring(root, encoding='utf-8', method='xml')
            
            # Update the record
            headers = {'Content-Type': 'application/xml'}
            response = requests.put(
                f"{api_url}/almaws/v1/bibs/{mms_id}?apikey={self.api_key}",
                headers=headers,
                data=xml_bytes
            )
            
            if response.status_code == 200:
                return True, f"Replaced duplicate identifier with {new_value}"
            else:
                return False, f"Failed to update record: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, f"Exception during replacement: {str(e)}"
    
    def _add_identifier_field(self, mms_id: str, identifier_value: str) -> tuple[bool, str]:
        """
        Add a new dc:identifier field to a record
        
        Args:
            mms_id: The MMS ID of the record
            identifier_value: The identifier value to add (typically the MMS ID)
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Get the Alma API base URL
            api_url = self._get_alma_api_url()
            
            # Fetch the record as XML
            self.log(f"Fetching record {mms_id} to add identifier", logging.DEBUG)
            headers = {'Accept': 'application/xml'}
            response = requests.get(
                f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={self.api_key}",
                headers=headers
            )
            
            if response.status_code != 200:
                return False, f"Failed to fetch record: {response.status_code}"
            
            # Parse XML
            root = ET.fromstring(response.text)
            
            # Register namespaces
            namespaces_to_register = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'dcterms': 'http://purl.org/dc/terms/',
                'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
            }
            for prefix, uri in namespaces_to_register.items():
                ET.register_namespace(prefix, uri)
            
            # Find the parent element that contains dc:identifier elements
            search_namespaces = {'dc': 'http://purl.org/dc/elements/1.1/'}
            existing_identifiers = root.findall('.//dc:identifier', search_namespaces)
            
            if existing_identifiers:
                # Find the parent of the first identifier
                for parent in root.iter():
                    if existing_identifiers[0] in list(parent):
                        # Create new identifier element
                        new_identifier = ET.Element('{http://purl.org/dc/elements/1.1/}identifier')
                        new_identifier.text = identifier_value
                        parent.append(new_identifier)
                        break
            else:
                # No existing identifiers - find record element and add there
                record_elem = root.find('.//{http://purl.org/dc/elements/1.1/}record')
                if record_elem is None:
                    # Try finding any element that could be the parent
                    record_elem = root
                new_identifier = ET.Element('{http://purl.org/dc/elements/1.1/}identifier')
                new_identifier.text = identifier_value
                record_elem.append(new_identifier)
            
            # Convert back to XML
            xml_bytes = ET.tostring(root, encoding='utf-8', method='xml')
            
            # Update the record
            headers = {'Content-Type': 'application/xml'}
            response = requests.put(
                f"{api_url}/almaws/v1/bibs/{mms_id}?apikey={self.api_key}",
                headers=headers,
                data=xml_bytes
            )
            
            if response.status_code == 200:
                return True, f"Added identifier {identifier_value}"
            else:
                return False, f"Failed to update record: {response.status_code} - {response.text}"
                
        except Exception as e:
            return False, f"Exception during identifier addition: {str(e)}"

    def restore_metadata_from_previous_version(self, mms_ids: list, progress_callback=None) -> tuple[bool, str, str | None]:
        """
        Function 17: Restore bibliographic metadata from previous versions via Selenium.

        Status: Successfully navigating to View Versions panel (milestone: 2026-03-17)

        Note: The Alma REST API does not expose a /bibs/{mms_id}/versions endpoint
        (returns HTTP 404 for all institution environments). This function therefore
        automates the MDE manual process via Selenium/Chrome:
          View Related Data > View Versions > Restore

        For each MMS ID, opens Chrome, logs into Alma, then:
        1. Searches for the record under 'All titles / MMS ID'
        2. Clicks into the bib record from search results
        3. Opens the record in the Metadata Editor (MDE)
        4. Navigates to: View Related Data > View Versions (Angular Material menu)
        5. Clicks Restore on the most recent prior (non-current) version
        6. Writes a CSV audit report with per-record outcomes

        Technical: Menu dropdown renders in parent frame; only switch to yards_iframe
        for interacting with the versions panel content itself.

        Prerequisite: ChromeDriver must be installed (brew install --cask chromedriver).

        Args:
            mms_ids: List of MMS IDs to process
            progress_callback: Optional callback function(current, total) for progress updates

        Returns:
            tuple: (success: bool, message: str, report_csv_path: str | None)
        """
        import csv
        from datetime import datetime
        from pathlib import Path

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads_dir = Path.home() / "Downloads"
        output_dir = downloads_dir / f"CABB_restore_metadata_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_file = output_dir / f"metadata_restore_report_{timestamp}.csv"

        self.log(f"Starting Function 17 (Selenium/Chrome): Restore metadata for {len(mms_ids)} record(s)")
        self.log(f"Report: {report_file}")

        rows = []
        success_count = 0
        failed_count = 0
        driver = None
        total = len(mms_ids)

        try:
            # Close previously pinned debug browser so only one inspection window remains.
            if self._pinned_debug_driver:
                try:
                    self._pinned_debug_driver.quit()
                except Exception:
                    pass
                self._pinned_debug_driver = None

            driver = self._setup_selenium_browser(browser="chrome")
            self._perform_alma_login_for_mde_restore(driver)

            for idx, mms_id in enumerate(mms_ids, start=1):
                if self.kill_switch:
                    self.log("Kill switch activated — stopping", logging.WARNING)
                    break

                self.log(f"[{idx}/{total}] Restoring {mms_id}...")

                try:
                    ok, msg = self._restore_record_via_mde(driver, mms_id)
                except Exception as e:
                    ok, msg = False, f"Exception: {e}"

                rows.append({
                    "MMS ID": mms_id,
                    "Status": "Restored" if ok else "Failed",
                    "Message": msg,
                })

                if ok:
                    success_count += 1
                    self.log(f"  ✓ {msg}")
                else:
                    failed_count += 1
                    self.log(f"  ✗ {msg}", logging.ERROR)
                    self.log("Stopping batch processing due to failure", logging.ERROR)
                    break

                if progress_callback:
                    progress_callback(idx, total)

        except Exception as top_e:
            self.log(f"Function 17 aborted: {top_e}", logging.ERROR)
            return False, f"Aborted: {top_e}", None

        finally:
            # Keep browser open on failures so user can inspect
            # Only quit on success
            if driver and success_count > 0 and failed_count == 0:
                try:
                    driver.quit()
                except Exception:
                    pass
            elif driver:
                # Prevent Selenium from closing Chrome when local variable goes out of scope.
                self._pinned_debug_driver = driver
                self.log("Function 17 left browser open for inspection.", logging.WARNING)

        with open(report_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["MMS ID", "Status", "Message"])
            writer.writeheader()
            writer.writerows(rows)

        summary = (
            f"Metadata restore complete: {success_count} restored, {failed_count} failed. "
            f"Report: {report_file}"
        )
        self.log(summary)
        return True, summary, str(report_file)

    def _show_manual_capture_prompt(self, driver, mms_id: str):
        """
        Show an in-browser popup and banner indicating manual capture point.

        For Firefox, attempts to install Selenium IDE automatically. For Chrome,
        prompts the user for manual recording steps directly in the active window.
        """
        import time
        import os
        import urllib.request

        browser_app = self._get_browser_app_name(driver)
        is_firefox = (browser_app == "Firefox")

        self.log("")
        self.log("=" * 70)
        self.log("MANUAL CAPTURE HANDOFF")
        self.log("=" * 70)
        self.log(f"MMS ID for capture: {mms_id}")
        self.log(f"Automation is paused. {browser_app} remains open.")

        if is_firefox:
            # --- Auto-install Selenium IDE into the live Firefox session ---
            # Store the XPI in the project directory so it survives Downloads cleanups.
            project_xpi = os.path.join(os.path.dirname(os.path.abspath(__file__)), "selenium_ide.xpi")
            downloads_xpi = os.path.expanduser("~/Downloads/selenium_ide.xpi")
            xpi_path = project_xpi if os.path.isfile(project_xpi) else (
                downloads_xpi if os.path.isfile(downloads_xpi) else None
            )

            if not xpi_path:
                self.log("Downloading Selenium IDE extension...")
                try:
                    # Mozilla AMO canonical download URL for Selenium IDE
                    amo_url = (
                        "https://addons.mozilla.org/firefox/downloads/latest/"
                        "selenium-ide/addon-selenium-ide-latest.xpi"
                    )
                    urllib.request.urlretrieve(amo_url, project_xpi)
                    xpi_path = project_xpi
                    self.log(f"  Downloaded to {xpi_path}")
                except Exception as dl_err:
                    self.log(f"  Download failed: {dl_err}", logging.WARNING)
                    xpi_path = None

            if xpi_path and os.path.isfile(xpi_path):
                try:
                    driver.install_addon(xpi_path, temporary=True)
                    self.log("  Selenium IDE installed into this Firefox session.")
                    self.log("  Look for its icon in the toolbar (puzzle-piece or Se icon).")
                    time.sleep(2)  # give the extension a moment to initialise
                except Exception as ins_err:
                    self.log(f"  Could not install extension: {ins_err}", logging.WARNING)
                    self.log("  You may need to install Selenium IDE manually from the Firefox Add-ons menu.")
            else:
                self.log("  Could not obtain Selenium IDE XPI — install it manually if needed.")
        else:
            self.log(f"Selenium IDE auto-install is Firefox-only; proceeding with manual capture in {browser_app}.")

        self.log("")
        self.log("Click the Selenium IDE icon, create a new project, start recording,")
        self.log("then perform the full per-record flow manually.")
        self.log("Suggested flow: Search MMS -> Open Record -> Edit in MDE -> Record Actions -> View Related Data -> View Versions -> Restore")
        self.log("IMPORTANT: In MDE, confirm the record is in EDIT/LOCKED state before opening Versions.")
        self.log("If version rows do not select (and Restore stays gray), close Versions, re-open 'Edit in MDE', then open Versions again.")

        banner_mms = mms_id.replace("'", "")  # sanitize for JS string
        try:
            driver.execute_script(
                """
                (function(mms){
                    var existing = document.getElementById('cabb-manual-capture-banner');
                    if (existing) existing.remove();
                    var b = document.createElement('div');
                    b.id = 'cabb-manual-capture-banner';
                    b.style.cssText = 'position:fixed;bottom:14px;right:14px;z-index:2147483647;'
                        + 'max-width:460px;background:#b00020;color:white;padding:10px 12px;border-radius:8px;'
                        + 'font:600 12px/1.4 sans-serif;box-shadow:0 2px 8px rgba(0,0,0,.3);'
                        + 'pointer-events:none;';
                    b.innerHTML = '<b>CABB Manual Capture Mode</b> &mdash; '
                        + 'Browser is paused for manual capture. MMS: '
                        + '<code style="background:rgba(255,255,255,.2);padding:1px 6px;border-radius:3px">' + mms + '</code><br>'
                        + '<span style="font-weight:normal;font-size:13px">'
                        + '1\ufe0f\u20e3 Start your recorder/tool of choice &nbsp;'
                        + '2\ufe0f\u20e3 Begin recording/manual capture &nbsp;'
                        + '3\ufe0f\u20e3 Search MMS &rarr; Open Record &rarr; Edit in MDE '
                        + '&rarr; Record Actions &rarr; View Related Data &rarr; View Versions &rarr; Restore<br>'
                        + '<b>Note:</b> record must be in edit/locked state; otherwise version rows are not selectable and Restore remains disabled.'
                        + '</span>';
                    document.body.appendChild(b);
                })(arguments[0]);
                """,
                banner_mms
            )
        except Exception as e:
            self.log(f"Could not inject capture banner: {e}", logging.DEBUG)

        # Do not use alert() here; browser alerts block page interaction and can
        # make Alma appear "unclickable" during manual recording.
        self.log("Manual capture instructions are shown in the red in-page banner.")

        # Best effort: dismiss any stale modal alert if one is still open.
        try:
            active_alert = driver.switch_to.alert
            alert_text = active_alert.text
            active_alert.dismiss()
            self.log(f"Dismissed blocking browser alert: {alert_text[:120]}", logging.DEBUG)
        except Exception:
            pass

        # Keep session open for manual work.
        pause_seconds = 600
        self.log(f"Holding browser session open for {pause_seconds} seconds for recording...", logging.WARNING)
        time.sleep(pause_seconds)

    def _perform_alma_login_for_mde_restore(self, driver):
        """
        Log into Alma for Function 17 MDE metadata restore.

        Navigates to SAML login, handles SSO auto-login if SSO_USERNAME / SSO_PASSWORD
        are in the environment, waits for DUO, and dismisses post-login popups.

        After login the user must configure the Alma search bar:
          Search type  (left dropdown):   All titles
          Search field (middle dropdown): MMS ID
        This is validated before returning.
        """
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys
        import subprocess
        import time
        import os

        sso_username = os.getenv('SSO_USERNAME')
        sso_password = os.getenv('SSO_PASSWORD')
        auto_login_enabled = bool(sso_username and sso_password)
        browser_app = self._get_browser_app_name(driver)

        driver.get("https://grinnell.alma.exlibrisgroup.com/SAML")

        if auto_login_enabled:
            self.log("")
            self.log("=" * 70)
            self.log("🔐 AUTOMATIC SSO LOGIN — Function 17: Restore Metadata")
            self.log("=" * 70)
            login_ok = self._attempt_automatic_sso_login(driver, sso_username, sso_password)
            if login_ok:
                self.log("")
                self.log("⏸️  WAITING FOR DUO AUTHENTICATION")
                self.log("=" * 70)
                self.log("Please approve the DUO push notification on your device...")
                self.log("")
                self.log("After DUO approval, configure the Alma search bar:")
                self.log("   • Search type  (left dropdown):   All titles")
                self.log("   • Search field (middle dropdown): MMS ID")
                self.log("   • Leave the search box EMPTY")
                self.log("")
                self.log("Automation begins in 45 seconds...")
                time.sleep(45)
            else:
                self.log("Auto-login failed — falling back to manual login", logging.WARNING)
                auto_login_enabled = False

        if not auto_login_enabled:
            self.log("")
            self.log("=" * 70)
            self.log("⏸️  PLEASE LOG INTO ALMA NOW — Function 17: Restore Metadata")
            self.log("=" * 70)
            self.log(f"1. Complete the SSO login in {browser_app}")
            self.log("2. Complete DUO authentication if prompted")
            self.log("3. Wait for the Alma home page to fully load")
            self.log("")
            self.log("4. ⚙️  CONFIGURE THE SEARCH BAR (at top of page):")
            self.log("   • Search type  (left dropdown):   All titles")
            self.log("   • Search field (middle dropdown): MMS ID")
            self.log("   • Leave the search box EMPTY")
            self.log("")
            self.log("5. Automation begins in 60 seconds...")
            time.sleep(60)

        # Recover from common Microsoft auth error pages that can appear if a
        # stale/callback URL is opened out of sequence.
        if self._recover_from_aad_state_error(driver):
            self.log("Detected Microsoft auth state error; restarted via Alma SAML.", logging.WARNING)
            self.log("Please complete SSO/DUO again if prompted. Continuing in 45 seconds...")
            time.sleep(45)

        # Handle Microsoft "Stay signed in?" prompt (can appear late after DUO redirect)
        prompt_handled = self._dismiss_stay_signed_in_prompt(driver, timeout_seconds=25)
        if prompt_handled:
            time.sleep(2)

        # Focus browser and dismiss interfering popups
        try:
            subprocess.run([
                'osascript', '-e',
                f'tell application "{browser_app}" to activate'
            ], capture_output=True, timeout=5)
            driver.set_window_size(1200, 900)
            driver.set_window_position(0, 0)
            driver.execute_script("window.focus();")
            time.sleep(1)
            actions = ActionChains(driver)
            actions.send_keys(Keys.ESCAPE)
            actions.perform()
            time.sleep(0.5)
        except Exception as e:
            self.log(f"{browser_app} focus: {e}", logging.DEBUG)

        # Prompt can re-appear after focus/redirect; check again before continuing.
        self._dismiss_stay_signed_in_prompt(driver, timeout_seconds=10)

        # One more safety check before processing records.
        if self._recover_from_aad_state_error(driver):
            self.log("Recovered from Microsoft auth state error. Waiting 30 seconds...", logging.WARNING)
            time.sleep(30)

        # Validate search config: All titles / MMS ID
        self.log("Validating search configuration...", logging.DEBUG)
        try:
            config = driver.execute_script("""
                var spans = document.querySelectorAll('span.sel-combobox-selected-value');
                var hasAllTitles = false, hasMmsNumber = false;
                for (var i = 0; i < spans.length; i++) {
                    var t = spans[i].textContent.trim();
                    if (/all\\s+titles/i.test(t)) hasAllTitles = true;
                    if (/mms.*(id|number|no)/i.test(t)) hasMmsNumber = true;
                }
                return { hasAllTitles: hasAllTitles, hasMmsNumber: hasMmsNumber };
            """)
            if config.get('hasAllTitles') and config.get('hasMmsNumber'):
                self.log("  ✓ Search: All titles / MMS ID", logging.DEBUG)
            else:
                missing = []
                if not config.get('hasAllTitles'):
                    missing.append("Search type: 'All titles'")
                if not config.get('hasMmsNumber'):
                    missing.append("Search field: 'MMS ID'")
                self.log(f"  ⚠️ Search config may not be set: {', '.join(missing)}", logging.WARNING)
                self.log("  Proceeding — ensure search is set to: All titles / MMS ID", logging.WARNING)
        except Exception as e:
            self.log(f"  Could not validate search config: {e}", logging.DEBUG)

        self.log("Login complete — beginning record processing...")
        self.log("")

    def _recover_from_aad_state_error(self, driver) -> bool:
        """
        Detect AADSTS900144 ('state' missing) and restart from Alma SAML.

        Returns True when recovery was triggered, otherwise False.
        """
        import time

        try:
            current_url = (driver.current_url or "").lower()
            page_text = (driver.page_source or "").lower()
        except Exception:
            return False

        aad_state_error = (
            "aadsts900144" in page_text
            or "following parameter: 'state'" in page_text
            or ("login.microsoftonline.com" in current_url and "aadsts900144" in page_text)
        )

        if not aad_state_error:
            return False

        self.log("Microsoft AADSTS900144 page detected; restarting login from Alma SAML...", logging.WARNING)
        try:
            driver.get("https://grinnell.alma.exlibrisgroup.com/SAML")
            time.sleep(2)
            return True
        except Exception as e:
            self.log(f"Could not restart SAML login after AADSTS900144: {e}", logging.ERROR)
            return False

    def _dismiss_stay_signed_in_prompt(self, driver, timeout_seconds: int = 20) -> bool:
        """
        Dismiss Microsoft 'Stay signed in?' prompts after SSO/DUO.

        Returns True if a prompt button was clicked, else False.
        """
        import time

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                result = driver.execute_script("""
                    function visible(el) {
                        return !!(el && (el.offsetParent !== null || el.getClientRects().length));
                    }

                    var body = (document.body && document.body.textContent || '').toLowerCase();
                    var promptSeen = body.includes('stay signed in') || body.includes('sign in to this app only');

                    // Microsoft IDs first (most reliable)
                    var noBtn = document.getElementById('idBtn_Back');
                    if (visible(noBtn)) {
                        noBtn.click();
                        return 'clicked-idBtn_Back';
                    }

                    var yesBtn = document.getElementById('idSIButton9');
                    if (visible(yesBtn) && promptSeen) {
                        yesBtn.click();
                        return 'clicked-idSIButton9';
                    }

                    // Generic text-based fallback when prompt text is visible
                    if (promptSeen) {
                        var buttons = document.querySelectorAll('button, input[type="button"], input[type="submit"]');
                        for (var i = 0; i < buttons.length; i++) {
                            var text = (buttons[i].textContent || buttons[i].value || '').trim().toLowerCase();
                            if ((text === 'no' || text === 'yes' || text === 'ok') && visible(buttons[i])) {
                                buttons[i].click();
                                return 'clicked-text-' + text;
                            }
                        }
                    }

                    return false;
                """)

                if result:
                    self.log(f"✓ Dismissed Microsoft sign-in prompt ({result})", logging.DEBUG)
                    return True

            except Exception:
                pass

            time.sleep(1)

        return False

    def _restore_record_via_mde(self, driver, mms_id: str) -> tuple[bool, str]:
        """
        Navigate to an Alma bib record in the MDE and restore its previous version.

        Steps:
        1. Search for MMS ID under 'All titles / MMS ID'
        2. Click on the bib record from search results
        3. Click 'Edit in MD Editor' to open the MDE
        4. In MDE: Record Actions > View Related Data > View Versions
        5. Restore the most recent prior (non-current) version
        """
        import time

        # Step 1: Search for this MMS ID using the existing helper
        print(f"\n=== Processing MMS ID: {mms_id} ===")
        print(f"Step 1: Searching for record...")
        self.log(f"  → Searching for {mms_id}...", logging.DEBUG)
        self._search_for_representation(driver, mms_id)

        # Step 2: Click into the bib record result
        print(f"Step 2: Opening bib record...")
        self.log(f"  → Opening bib record...", logging.DEBUG)
        ok, msg = self._click_bib_record_from_search(driver, mms_id)
        if not ok:
            return False, msg

        # Step 3: Click 'Edit in MD Editor'
        print(f"Step 3: Opening in Metadata Editor...")
        self.log(f"  → Opening in MDE...", logging.DEBUG)
        ok, msg = self._click_edit_in_metadata_editor(driver, mms_id)
        if not ok:
            return False, msg

        # MDE may open in a new tab — switch to it if so
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            print(f"Switched to MDE tab")
            self.log(f"  → Switched to MDE tab", logging.DEBUG)
            time.sleep(2)

        # Alma may host the MDE inside an iframe (yardsNgWrapper); enter it before toolbar actions.
        self._switch_to_mde_iframe_if_present(driver)

        # Wait for MDE Angular app to finish loading (loading spinner should disappear)
        print(f"  Waiting for MDE to finish loading...")
        self.log(f"  → Waiting for MDE to finish loading...", logging.DEBUG)
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        try:
            # Wait for loading spinner to disappear (up to 30 seconds)
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located((By.ID, "__loading__"))
            )
            print(f"  ✓ MDE finished loading")
            self.log(f"  ✓ MDE finished loading", logging.DEBUG)
        except Exception as e:
            # If we can't find the loading spinner, log but continue (may already be loaded)
            self.log(f"  ⚠️ Could not detect loading completion: {e}", logging.WARNING)
            time.sleep(3)  # Fallback wait
        
        # Optional manual capture mode for collecting real user clicks in the MDE UI.
        # Enable with: FN17_MANUAL_CAPTURE=1
        if os.getenv("FN17_MANUAL_CAPTURE", "0").strip().lower() in ("1", "true", "yes", "on"):
            return self._capture_manual_fn17_clicks(driver, mms_id)

        # Step 4: Navigate to View Versions via Record Actions menu
        print(f"Step 4: Navigating to View Versions...")
        self.log(f"  → Navigating to View Versions...", logging.DEBUG)
        ok, msg = self._open_view_versions_in_mde(driver, mms_id)
        if not ok:
            return False, msg

        # Step 5: Restore the previous version
        print(f"Step 5: Restoring previous version...")
        self.log(f"  → Restoring previous version...", logging.DEBUG)
        ok, msg = self._restore_previous_version(driver, mms_id)
        
        if not ok:
            return False, msg
        
        # Step 6: Navigate back to Alma search page for next record
        print(f"Step 6: Returning to search page for next record...")
        self.log(f"  → Navigating back to search page...", logging.DEBUG)
        try:
            # After restore, Alma may close the MDE tab/window
            # Check if we have multiple windows and close the MDE if it's still open
            if len(driver.window_handles) > 1:
                driver.close()  # Close current tab (MDE)
                driver.switch_to.window(driver.window_handles[0])  # Switch back to main window
                print(f"  Closed MDE tab, switched to main window")
            
            # Navigate to Alma home page (ready for next search)
            driver.get("https://grinnell.alma.exlibrisgroup.com/mng/action/home.do")
            time.sleep(2)
            print(f"  ✓ Ready for next record")
            self.log(f"  ✓ Returned to search page", logging.DEBUG)
            
        except Exception as e:
            self.log(f"  ⚠️ Error navigating back: {e}", logging.WARNING)
            # Even if navigation fails, the restore was successful
            pass
        
        return ok, msg

        def _capture_manual_fn17_clicks(self, driver, mms_id: str) -> tuple[bool, str]:
                """
                Capture manual clicks in the active Selenium browser window for Function 17 debugging.

                This mode is intended for collecting the exact click sequence directly from the
                in-environment browser when external Chrome tooling is unavailable.
                """
                import json
                import time
                from pathlib import Path

                capture_seconds = int(os.getenv("FN17_MANUAL_CAPTURE_SECONDS", "180"))
                downloads_dir = Path.home() / "Downloads"
                click_file = downloads_dir / f"fn17_manual_clicks_{mms_id}.json"
                page_file = downloads_dir / f"fn17_manual_capture_page_{mms_id}.html"

                try:
                        driver.execute_script(
                                """
                                (function() {
                                    if (window.__fn17CaptureInstalled) {
                                        return;
                                    }

                                    function cssPath(el) {
                                        if (!el || !el.nodeType || el.nodeType !== 1) return '';
                                        var parts = [];
                                        while (el && el.nodeType === 1 && el !== document.body) {
                                            var part = el.nodeName.toLowerCase();
                                            if (el.id) {
                                                part += '#' + el.id;
                                                parts.unshift(part);
                                                break;
                                            }
                                              var cls = (el.className || '').toString().trim().split(/\\s+/).filter(Boolean).slice(0, 2);
                                            if (cls.length) {
                                                part += '.' + cls.join('.');
                                            }
                                            var sib = el, idx = 1;
                                            while (sib = sib.previousElementSibling) {
                                                if (sib.nodeName.toLowerCase() === el.nodeName.toLowerCase()) idx++;
                                            }
                                            part += ':nth-of-type(' + idx + ')';
                                            parts.unshift(part);
                                            el = el.parentElement;
                                        }
                                        return parts.join(' > ');
                                    }

                                    window.__fn17Clicks = [];
                                    window.__fn17ClickHandler = function(evt) {
                                        var t = evt.target;
                                        if (!t) return;
                                        var txt = (t.innerText || t.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 240);
                                        window.__fn17Clicks.push({
                                            ts: new Date().toISOString(),
                                            tag: (t.tagName || '').toLowerCase(),
                                            text: txt,
                                            id: t.id || '',
                                            classes: (t.className || '').toString(),
                                            ariaLabel: t.getAttribute ? (t.getAttribute('aria-label') || '') : '',
                                            dataAutomationId: t.getAttribute ? (t.getAttribute('data-automation-id') || '') : '',
                                            cssPath: cssPath(t)
                                        });
                                    };

                                    document.addEventListener('click', window.__fn17ClickHandler, true);
                                    window.__fn17CaptureInstalled = true;
                                })();
                                """
                        )
                except Exception as e:
                        return False, f"Manual capture setup failed: {e}"

                self.log(f"  ⚠️ Manual capture mode enabled for {mms_id}", logging.WARNING)
                self.log(f"  ⚠️ Perform the correct clicks in the browser now. Capturing for {capture_seconds} seconds...", logging.WARNING)

                slept = 0
                while slept < capture_seconds:
                        time.sleep(5)
                        slept += 5

                try:
                        clicks = driver.execute_script("return window.__fn17Clicks || [];") or []
                        driver.execute_script(
                                """
                                if (window.__fn17CaptureInstalled && window.__fn17ClickHandler) {
                                    document.removeEventListener('click', window.__fn17ClickHandler, true);
                                }
                                window.__fn17CaptureInstalled = false;
                                """
                        )

                        click_file.write_text(json.dumps(clicks, indent=2), encoding="utf-8")
                        page_file.write_text(driver.page_source, encoding="utf-8")

                        return False, (
                                f"Manual click capture complete ({len(clicks)} click events). "
                                f"Clicks: {click_file} | Page: {page_file}"
                        )
                except Exception as e:
                        return False, f"Manual capture export failed: {e}"

    def _switch_to_mde_iframe_if_present(self, driver):
        """
        Switch Selenium context into the Alma Metadata Editor iframe when present.

        Some Alma flows open MDE in an iframe (`yardsNgWrapper`) on the same page,
        while others open a separate tab/page. Function 17 needs to handle both.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        try:
            driver.switch_to.default_content()
            iframe = WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#yardsNgWrapper, iframe[title='MDEditor']"))
            )
            driver.switch_to.frame(iframe)
            self.log("  ✓ Switched into MDE iframe", logging.DEBUG)
        except TimeoutException:
            # No iframe found; likely already in direct MDE page context.
            self.log("  ℹ️ MDE iframe not present; using current page context", logging.DEBUG)
        except Exception as e:
            self.log(f"  ⚠️ Could not switch to MDE iframe: {e}", logging.DEBUG)

    def _click_bib_record_from_search(self, driver, mms_id: str) -> tuple[bool, str]:
        """
        After searching for an MMS ID under 'All titles', click the bib record result.
        Tries multiple selector strategies to find the result link.
        Saves a debug HTML to ~/Downloads if all strategies fail.
        """
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        from pathlib import Path

        time.sleep(2)

        strategies = [
            # Exact MMS ID text in a link
            (By.XPATH, f"//ex-link[normalize-space(.) = '{mms_id}']"),
            (By.XPATH, f"//a[normalize-space(.) = '{mms_id}']"),
            # MMS ID contained in link text
            (By.XPATH, f"//ex-link[contains(., '{mms_id}')]"),
            (By.XPATH, f"//a[contains(., '{mms_id}')]"),
            # MMS ID in title/aria-label attributes
            (By.XPATH, f"//*[contains(@title, '{mms_id}') or contains(@aria-label, '{mms_id}')]"),
            # Title link for the first search result (text-based title link, not checkbox or action button)
            (By.XPATH, "//ex-link[not(contains(@class,'checkbox')) and not(contains(@class,'action'))][1]"),
            (By.XPATH, "(//a[@class and not(contains(@class,'action'))])[1]"),
        ]

        for by, selector in strategies:
            try:
                elem = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((by, selector))
                )
                self.log(f"  ✓ Found bib record result", logging.DEBUG)
                driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                time.sleep(0.3)
                try:
                    elem.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", elem)
                self.log(f"  ✓ Clicked bib record result", logging.DEBUG)
                time.sleep(3)
                return True, "Opened bib record"
            except (TimeoutException, Exception):
                continue

        try:
            debug_file = Path.home() / "Downloads" / f"fn17_search_result_{mms_id}.html"
            debug_file.write_text(driver.page_source, encoding='utf-8')
            self.log(f"  ✗ Bib record result not found — page saved: {debug_file}", logging.ERROR)
        except Exception:
            pass
        return False, f"Could not find bib record in search results for {mms_id}"

    def _click_edit_in_metadata_editor(self, driver, mms_id: str) -> tuple[bool, str]:
        """
        In the Alma bib record detail view, click 'Edit in MD Editor' (or equivalent).
        Tries ExLibris CSS automation selectors, then falls back to text-based XPath.
        Saves a debug HTML to ~/Downloads if all strategies fail.
        """
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        from pathlib import Path

        time.sleep(2)

        # ExLibris data-automation-id and CSS patterns for the Edit button
        css_selectors = [
            "[data-automation-id='title-edit-bib']",
            "[data-automation-id='edit-bib-record']",
            "[data-automation-id='btn-edit-md-editor']",
            "[data-automation-id='openMDE']",
            ".ex-record-actions-first",
            ".ex-record-actions-main-buttons button:first-child",
        ]

        for sel in css_selectors:
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                self.log(f"  Found Edit button ({sel})", logging.DEBUG)
                driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                time.sleep(0.3)
                try:
                    btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", btn)
                self.log(f"  ✓ Clicked Edit in MD Editor", logging.DEBUG)
                time.sleep(3)
                return True, "Opened MDE"
            except (TimeoutException, Exception):
                continue

        # Text-based XPath fallbacks for the Edit button
        edit_texts = [
            "Edit in MD Editor",
            "Open in Metadata Editor",
            "Edit in Metadata Editor",
            "Open MD Editor",
        ]
        for text in edit_texts:
            for tag in ('button', 'a', 'ex-link', '*'):
                xpath = f"//{tag}[contains(normalize-space(.), '{text}')]"
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    self.log(f"  Found '{text}' ({xpath[:60]})", logging.DEBUG)
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    time.sleep(0.3)
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    self.log(f"  ✓ Clicked Edit in MD Editor", logging.DEBUG)
                    time.sleep(3)
                    return True, "Opened MDE"
                except (TimeoutException, Exception):
                    continue

        try:
            debug_file = Path.home() / "Downloads" / f"fn17_edit_btn_{mms_id}.html"
            debug_file.write_text(driver.page_source, encoding='utf-8')
            self.log(f"  ✗ 'Edit in MD Editor' button not found — page saved: {debug_file}", logging.ERROR)
        except Exception:
            pass
        return False, f"Could not find 'Edit in MD Editor' button for {mms_id}"

    def _open_view_versions_in_mde(self, driver, mms_id: str) -> tuple[bool, str]:
        """
        In the Alma MDE, navigate to View Versions panel:
          View Related Data > View Versions

        Key technical detail: The Angular Material dropdown menu renders in the 
        PARENT frame context (not inside yards_iframe). Must stay in parent context
        when clicking menu items. Only switch to yards_iframe later for interacting
        with the versions panel content.

        Fails fast on any missing element to help debug the UI flow.
        Saves page to ~/Downloads on failure for manual inspection.
        """
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        from pathlib import Path

        time.sleep(1)

        # --- Step A: Click 'View Related Data' button to open dropdown ---
        print(f"Looking for 'View Related Data' button...")
        self.log(f"  → Finding 'View Related Data' button", logging.DEBUG)
        
        view_related_button = None
        try:
            # First, find the span containing "View Related Data"
            spans = driver.find_elements(By.XPATH, "//span[contains(@class, 'menu-label') and contains(., 'View Related Data')]")
            if spans:
                span = spans[0]
                print(f"  Found span.menu-label with 'View Related Data'")
                # Now get the parent button
                try:
                    view_related_button = span.find_element(By.XPATH, "./ancestor::button")
                    print(f"  Found parent button")
                except Exception as e:
                    print(f"  Could not find parent button: {e}")
                    # Try clicking the span itself as fallback
                    view_related_button = span
        except Exception as e:
            print(f"  Could not find 'View Related Data': {e}")
        
        if not view_related_button:
            try:
                debug_file = Path.home() / "Downloads" / f"fn17_step_A_view_related_{mms_id}.html"
                debug_file.write_text(driver.page_source, encoding='utf-8')
                self.log(f"  ✗ FAIL: 'View Related Data' button not found — page: {debug_file}", logging.ERROR)
            except Exception:
                pass
            return False, f"Could not find 'View Related Data' button for {mms_id}"
        
        # Now click the button using multiple strategies
        print(f"Clicking 'View Related Data' button...")
        clicked = False
        
        # Strategy 1: JavaScript click
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", view_related_button)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", view_related_button)
            print(f"  ✓ Clicked with JavaScript")
            clicked = True
        except Exception as e:
            print(f"  JavaScript click failed: {e}")
        
        # Strategy 2: Regular Selenium click (if JavaScript failed)
        if not clicked:
            try:
                view_related_button.click()
                print(f"  ✓ Clicked with Selenium")
                clicked = True
            except Exception as e:
                print(f"  Selenium click failed: {e}")
        
        if not clicked:
            return False, f"Could not click 'View Related Data' button for {mms_id}"
        
        print(f"Waiting for dropdown to expand...")
        time.sleep(3)  # Wait for dropdown animation
        self.log(f"  ✓ Clicked View Related Data", logging.DEBUG)

        # --- Step B: Stay in current iframe context to find dropdown items ---
        # The dropdown menu should now be visible in the current iframe where the MDE is loaded
        print(f"Looking for dropdown menu in current iframe context")
        self.log("  ℹ️ Staying in current iframe context for dropdown menu", logging.DEBUG)

        # --- Step C: Click 'View Versions' from dropdown ---
        print(f"Looking for: View Versions menu item")
        view_versions = None
        
        # Try multiple strategies to find the View Versions menu item
        # Based on actual HTML: <button id="SubMenuItem_menu_records_viewRelatedData_viewVersions">
        #   containing <span class="menu-label"> View Versions  </span>
        
        strategies = [
            # Strategy 1: Direct ID lookup
            ("ID", By.ID, "SubMenuItem_menu_records_viewRelatedData_viewVersions"),
            # Strategy 2: Button by name attribute
            ("name attribute", By.CSS_SELECTOR, "button[name='menu.records.viewRelatedData.viewVersions']"),
            # Strategy 3: mat-menu-item button containing 'View Versions' text
            ("mat-menu-item", By.XPATH, "//button[@mat-menu-item and contains(., 'View Versions')]"),
            # Strategy 4: span.menu-label with View Versions (handles whitespace)
            ("span.menu-label", By.XPATH, "//span[contains(@class, 'menu-label') and contains(., 'View Versions')]"),
            # Strategy 5: Parent button of the span.menu-label
            ("parent button", By.XPATH, "//span[contains(@class, 'menu-label') and contains(., 'View Versions')]/ancestor::button"),
        ]
        
        for idx, (desc, by_method, selector) in enumerate(strategies, 1):
            try:
                print(f"  Strategy {idx} ({desc})...")
                view_versions = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((by_method, selector))
                )
                if view_versions:
                    print(f"Found it ✓ ({desc})")
                    self.log(f"  ✓ Found 'View Versions' using {desc}", logging.DEBUG)
                    break
            except TimeoutException:
                continue
        
        # If we didn't find 'View Versions', debug and fail
        if not view_versions:
            print(f"Failed to find 'View Versions' - saving debug info...")
            try:
                debug_file = Path.home() / "Downloads" / f"fn17_step_C_view_versions_{mms_id}.html"
                debug_file.write_text(driver.page_source, encoding='utf-8')
                self.log(f"  ✗ FAIL: 'View Versions' not found — page: {debug_file}", logging.ERROR)
                
                # Try to list relevant Angular Material and menu elements
                try:
                    # Look for mat-menu-item buttons
                    mat_items = driver.find_elements(By.CSS_SELECTOR, "button[mat-menu-item]")
                    print(f"  Found {len(mat_items)} mat-menu-item buttons")
                    for elem in mat_items[:10]:
                        elem_id = elem.get_attribute("id") or "no-id"
                        text = elem.text.strip()[:60] if elem.text else ""
                        print(f"    - id={elem_id}: '{text}'")
                    
                    # Look for span.menu-label elements
                    menu_labels = driver.find_elements(By.CSS_SELECTOR, "span.menu-label")
                    print(f"  Found {len(menu_labels)} span.menu-label elements")
                    for elem in menu_labels[:10]:
                        text = elem.text.strip() if elem.text else ""
                        print(f"    - '{text}'")
                        
                except Exception as e:
                    print(f"  Could not enumerate menu elements: {e}")
                
                # Also enumerate frames for debugging
                self.log(f"  ℹ️ Attempting to capture all frame info...", logging.DEBUG)
                try:
                    all_frames = driver.find_elements(By.TAG_NAME, "iframe")
                    self.log(f"  ℹ️ Found {len(all_frames)} iframe(s) on page", logging.DEBUG)
                    print(f"  Found {len(all_frames)} iframe(s) on page")
                    for idx, frame in enumerate(all_frames):
                        frame_id = frame.get_attribute("id") or f"unnamed_{idx}"
                        self.log(f"    Frame {idx}: id='{frame_id}'", logging.DEBUG)
                except Exception as frame_err:
                    self.log(f"  ⚠️ Frame enumeration failed: {frame_err}", logging.DEBUG)
            except Exception as debug_err:
                self.log(f"  ⚠️ Debug capture failed: {debug_err}", logging.DEBUG)
            return False, f"Could not find 'View Versions' menu item for {mms_id}"

        try:
            view_versions.click()
        except Exception:
            driver.execute_script("arguments[0].click();", view_versions)
        print(f"Clicked 'View Versions'")
        self.log(f"  ✓ Clicked View Versions", logging.DEBUG)
        
        time.sleep(1)
        return True, "Opened View Versions panel"

    def _restore_previous_version(self, driver, mms_id: str) -> tuple[bool, str]:
        """
        In the Alma MDE View Versions panel, click 'Restore' on the most recent version
        that contains valid bibliographic metadata.
        
        Version Selection Logic:
        - Examines versions from newest to oldest
        - Selects the first version containing "Subjects:" field (plural with colon)
        - Versions without "Subjects:" are skipped (incomplete bibliographic metadata)
        
        Note: The View Versions panel loads dynamically with a progress spinner.
        Must wait for content to fully load before trying to find Restore buttons.
        """
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        from pathlib import Path

        print(f"Waiting for View Versions panel to load...")
        time.sleep(3)  # Initial wait for panel to start loading

        # Try switching to yards_iframe if it exists (Alma may render View Versions in an iframe)
        print(f"Checking for iframe context...")
        try:
            iframe = driver.find_element(By.CSS_SELECTOR, "iframe#yards_iframe, iframe[id*='yards']")
            driver.switch_to.frame(iframe)
            print(f"Switched to yards_iframe ✓")
            self.log("  ✓ Switched to yards_iframe", logging.DEBUG)
            time.sleep(1)
        except Exception:
            print(f"No iframe found, searching in current context")
            self.log("  ℹ️ yards_iframe not found; searching in current context", logging.DEBUG)

        # Wait for any loading spinners to disappear
        print(f"Waiting for any loading spinners to finish...")
        try:
            # Common spinner patterns in Alma
            spinner_selectors = [
                "div.spinner", "div.loading", ".lds-spinner", 
                "*[class*='spinner']", "*[class*='loading']",
                "md-progress-circular"
            ]
            for selector in spinner_selectors:
                try:
                    spinners = driver.find_elements(By.CSS_SELECTOR, selector)
                    if spinners:
                        print(f"  Found spinner ({selector}), waiting for it to disappear...")
                        WebDriverWait(driver, 10).until(
                            EC.invisibility_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        print(f"  Spinner disappeared ✓")
                        break
                except Exception:
                    continue
        except Exception as e:
            self.log(f"  ℹ️ No spinner found or already gone: {e}", logging.DEBUG)
        
        # Additional wait after spinner disappears for content to render
        time.sleep(2)
        
        # Look for "Restore Metadata" buttons (actual button elements only)
        print(f"Looking for: 'Restore Metadata' buttons in View Versions panel")
        all_restore_btns = []
        
        try:
            print(f"  Searching for button elements with text 'Restore Metadata'...")
            # Search specifically for BUTTON elements with "Restore Metadata" text
            # This prevents finding other elements that might contain "Restore"
            elements = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH,
                    "//button[contains(normalize-space(.), 'Restore Metadata')]"
                ))
            )
            # Filter for visible and enabled button elements only
            visible = [e for e in elements if e.is_displayed() and e.is_enabled() and e.tag_name.lower() == 'button']
            if visible:
                print(f"Found ✓ ({len(visible)} button(s))")
                self.log(f"  ✓ Found {len(visible)} 'Restore Metadata' button(s)", logging.DEBUG)
                all_restore_btns = visible
        except TimeoutException:
            print(f"  'Restore Metadata' buttons not found")
            self.log(f"  ⚠️ 'Restore Metadata' buttons not found", logging.DEBUG)
        except Exception as e:
            self.log(f"  ⚠️ Error searching for 'Restore Metadata' buttons: {e}", logging.DEBUG)

        if not all_restore_btns:
            try:
                debug_file = Path.home() / "Downloads" / f"fn17_versions_panel_{mms_id}.html"
                debug_file.write_text(driver.page_source, encoding='utf-8')
                self.log(f"  ✗ FAIL: No 'Restore' buttons found — page: {debug_file}", logging.ERROR)
            except Exception:
                pass
            return False, f"No 'Restore' buttons found in View Versions panel for {mms_id}"

        # Select the correct Restore button based on version metadata
        # Rule: Choose the most recent version that contains "Subjects:" field
        print(f"Examining {len(all_restore_btns)} version(s) to find the correct one to restore...")
        self.log(f"  ℹ️ Evaluating {len(all_restore_btns)} version(s) for valid metadata...", logging.DEBUG)
        
        clicked_restore = False
        for idx, btn in enumerate(all_restore_btns):
            try:
                # Traverse up the DOM to find the version container
                # Look for the table with class="resultContainerStyle" which wraps each version
                version_container = btn
                max_levels = 15  # Safety limit
                for level in range(max_levels):
                    version_container = version_container.find_element(By.XPATH, "..")
                    # Check if we've reached the resultContainerStyle table
                    try:
                        if 'resultContainerStyle' in version_container.get_attribute('class'):
                            break
                    except:
                        pass
                
                # Get all text content from this version container
                container_text = version_container.text
                
                # Debug: log what we found
                if container_text:
                    preview = container_text.replace('\n', ' ')[:150]
                    print(f"  Version {idx + 1} text preview: {preview}...")
                    self.log(f"  Version {idx + 1} preview: {preview}...", logging.DEBUG)
                
                # Check if this version has "Subjects:" field (the key validation criterion)
                # Valid bibliographic records have "Subjects:" (plural with colon)
                has_subjects = "Subjects:" in container_text
                
                if has_subjects:
                    print(f"  Version {idx + 1}: ✓ VALID (has 'Subjects:' field)")
                    self.log(f"  ✓ Version {idx + 1} is valid: has 'Subjects:' field", logging.DEBUG)
                    
                    # Click this button IMMEDIATELY while the element reference is fresh
                    print(f"Clicking Restore button for version {idx + 1}...")
                    self.log(f"  ✓ Clicking Restore button for version {idx + 1}...", logging.DEBUG)
                    
                    # Scroll to the button
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    time.sleep(0.5)
                    
                    # Try multiple click strategies
                    try:
                        # Strategy 1: Regular click
                        btn.click()
                        print(f"  ✓ Clicked with regular click()")
                    except Exception as e1:
                        print(f"  Regular click failed: {e1}")
                        try:
                            # Strategy 2: JavaScript click
                            driver.execute_script("arguments[0].click();", btn)
                            print(f"  ✓ Clicked with JavaScript click()")
                        except Exception as e2:
                            print(f"  JavaScript click failed: {e2}")
                            # Strategy 3: Move to element and click
                            from selenium.webdriver.common.action_chains import ActionChains
                            actions = ActionChains(driver)
                            actions.move_to_element(btn).click().perform()
                            print(f"  ✓ Clicked with ActionChains")
                    
                    clicked_restore = True
                    time.sleep(1)
                    break  # Found and clicked the correct version, stop searching
                else:
                    print(f"  Version {idx + 1}: ✗ SKIP (no 'Subjects:' field)")
                    self.log(f"  ✗ Version {idx + 1} skipped: no 'Subjects:' field", logging.DEBUG)
                    
            except Exception as e:
                self.log(f"  ⚠️ Error examining version {idx + 1}: {e}", logging.DEBUG)
                continue
        
        # Fallback: if no version was clicked, click the first button
        if not clicked_restore:
            print(f"  ⚠️ No version has 'Subjects:' field — using first version as fallback")
            self.log(f"  ⚠️ No version has 'Subjects:' field — clicking first restore button", logging.WARNING)
            btn = all_restore_btns[0]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        
        print(f"Restore button clicked ✓")
        self.log(f"  ✓ Restore button clicked", logging.DEBUG)

        # Handle confirmation dialog (if one appears)
        confirmed = False
        for text in ("Confirm", "OK", "Yes", "Restore", "Yes, Restore"):
            try:
                confirm_btn = driver.find_element(By.XPATH,
                    f"//button[normalize-space(.)='{text}' or normalize-space(text())='{text}']"
                    f" | //input[@type='button' and (@value='{text}' or @aria-label='{text}')]"
                )
                if confirm_btn.is_displayed():
                    try:
                        confirm_btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", confirm_btn)
                    self.log(f"  ✓ Confirmed restore dialog ('{text}')", logging.DEBUG)
                    confirmed = True
                    time.sleep(1)
                    break
            except Exception:
                continue

        if not confirmed:
            self.log(f"  ℹ️ No confirmation dialog found — restore should apply automatically", logging.DEBUG)

        # Wait for restore to complete (saves automatically in Alma)
        time.sleep(2)
        
        print(f"✓ Metadata restored for {mms_id}")
        return True, f"Restored previous version for {mms_id}"
    
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
    
    log_level_dropdown = ft.Dropdown(
        label="Log Verbosity",
        hint_text="Select log detail level",
        width=150,
        value=storage.get_ui_state("log_level", "INFO"),
        options=[
            ft.dropdown.Option("ERROR", "Errors Only"),
            ft.dropdown.Option("WARNING", "Warnings+"),
            ft.dropdown.Option("INFO", "Normal"),
            ft.dropdown.Option("DEBUG", "Verbose")
        ],
        tooltip="Controls how much detail appears in logs. Use 'Errors Only' for cleaner output during Function 14b",
        on_change=lambda e: storage.set_ui_state("log_level", e.control.value)
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
        storage.record_function_usage("function_8_export_identifiers")
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
        storage.record_function_usage("function_9_validate_handles")
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
        """Handle Function 11: Prepare TIFF/JPG Representations"""
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
        def proceed_with_prep(e):
            warning_dialog.open = False
            page.update()
            
            if is_batch:
                add_log_message(f"Starting TIFF/JPG preparation for {len(mms_ids_to_process)} records")
                update_status(f"Preparing TIFF/JPG representations for {len(mms_ids_to_process)} records...", False)
                
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
                    status_text.value = f"Preparing TIFF/JPG reps: {current}/{total} records ({progress*100:.1f}%)"
                    page.update()
            else:
                add_log_message(f"Starting TIFF/JPG preparation for MMS ID: {mms_ids_to_process[0]}")
                update_status(f"Preparing TIFF/JPG representation for {mms_ids_to_process[0]}...", False)
                progress_update = None
            
            # Prepare TIFF/JPG representations
            storage.record_function_usage("function_11_prepare_tiff_jpg")
            success, message, csv_file_path = editor.prepare_tiff_jpg_representations(
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
                # Auto-populate Set ID field with output directory path
                if csv_file_path:
                    set_id_input.value = csv_file_path
                    add_log_message(f"📋 Output directory path copied to Set ID field")
                    page.update()
                
                if is_batch:
                    add_log_message(f"TIFF/JPG preparation complete")
                    add_log_message("💡 Check the logs for details on prepared files and any failures")
                    add_log_message("")
                    add_log_message("⚠️ NEXT STEPS:")
                    add_log_message("1. Launch Alma")
                    add_log_message("2. Navigate to: Resources > Manage Digital Files > Digital Uploader")
                    add_log_message("3. Select profile: 'Add Digital Files to Existing Digital Representations'")
                    add_log_message("4. Upload the directory shown above")
                else:
                    add_log_message("TIFF/JPG preparation complete for single record")
                    add_log_message("Use Alma Digital Uploader to complete the upload")
        
        def cancel_prep(e):
            warning_dialog.open = False
            page.update()
            add_log_message("TIFF/JPG preparation cancelled by user")
        
        warning_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ WARNING: Alma Data Modification", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "This will create JPG representations in Alma and prepare JPG files from TIFFs.",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        record_info,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Function: 11 - Prepare TIFF/JPG Representations",
                        italic=True,
                        color=ft.Colors.GREY_700
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "This action will PERMANENTLY create JPG representations in Alma. "
                        "JPG derivatives will be created from TIFF files found in all_single_tiffs_with_local_paths.csv. "
                        "\n\nOutput: values.csv + JPG files (named <mms_id>.jpg) ready for Alma Digital Uploader.",
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
                ft.TextButton("Cancel", on_click=cancel_prep),
                ft.TextButton(
                    "Proceed",
                    on_click=proceed_with_prep,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_700,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(warning_dialog)
    
    def on_function_12_click(e):
        """Handle Function 11b: DISABLED - Upload JPG Files (Selenium approach abandoned)"""
        
        # Show abandonment message dialog
        def close_dialog(e):
            message_dialog.open = False
            page.update()
        
        message_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("❌ FUNCTION 11b DISABLED", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Sorry, Function 11b (Upload JPG Files via Selenium) has been disabled and abandoned "
                        "because Alma's incompetence won't allow automation to replace a human, not even for the mind-numbing "
                        "and error-prone task of attaching a known digital file to an empty representation.",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Said human must accept their fate and faithfully serve the evil that is Alma, toiling in "
                        "clickity, click, click, click hell for eternity.",
                        size=14,
                        italic=True,
                        color=ft.Colors.ORANGE_700
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "The Selenium-based upload automation code has been archived in inactive_functions.py.",
                        size=12,
                        color=ft.Colors.GREY_700,
                        italic=True
                    ),
                ]),
                padding=20,
                width=500
            ),
            actions=[
                ft.TextButton("Close", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(message_dialog)
        add_log_message("❌ Function 11b (Selenium upload) is currently disabled due to Alma's automation limitations")
    
    def on_function_12_sound_click(e):
        """Handle Function 12: Analyze Sound Records by Decade"""
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
        storage.record_function_usage("function_12_sound_by_decade")
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
    
    def on_function_13_placeholder_click(e):
        """Handle Function 13 Placeholder - Explain why 13 is skipped"""
        
        def close_dialog(e):
            placeholder_dialog.open = False
            page.update()
        
        placeholder_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("🔢 Why No Function 13?", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "Triskaidekaphobia",
                        size=18,
                        weight=ft.FontWeight.W_500,
                        italic=True
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "The fear of the number 13 is common across many cultures. "
                        "Buildings skip the 13th floor, airlines avoid row 13, and many people consider it unlucky.",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "In the spirit of tradition (and perhaps a bit of superstition), "
                        "we've chosen to skip Function 13 in CABB.",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Why tempt fate when manipulating bibliographic records?",
                        size=14,
                        italic=True,
                        color=ft.Colors.GREY_700
                    ),
                    ft.Container(height=15),
                    ft.Text(
                        "Function 12: Sound Records by Decade",
                        size=13,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Text(
                        "Function 14a: Prepare Thumbnails",
                        size=13,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Container(height=5),
                    ft.Text(
                        "➡️  We go straight from 12 to 14.",
                        size=14,
                        color=ft.Colors.BLUE_700
                    ),
                ]),
                padding=20,
                width=500
            ),
            actions=[
                ft.TextButton(
                    "Understood 😊",
                    on_click=close_dialog,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.BLUE_700,
                    )
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(placeholder_dialog)
        add_log_message("ℹ️  Function 13 intentionally skipped (avoiding unlucky number)")
    
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
            storage.record_function_usage("function_14a_prepare_thumbnails")
            success, message, csv_file_path = editor.upload_clientthumb_thumbnails(
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
                # Auto-populate Set ID field with CSV path for Function 14b
                if csv_file_path:
                    set_id_input.value = csv_file_path
                    add_log_message(f"📋 CSV path copied to Set ID field for Function 14b")
                    page.update()
                
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
            
            # Get log level from dropdown
            selected_log_level = log_level_dropdown.value if log_level_dropdown.value else "INFO"
            
            success, message, success_count, failed_count, failed_csv_path = editor.upload_thumbnails_selenium(
                csv_path,
                progress_callback=progress_update,
                log_level=selected_log_level
            )
            
            # Hide progress bar
            set_progress_bar.visible = False
            set_progress_text.visible = False
            page.update()
            
            update_status(message, not success)
            if success:
                # Auto-populate Set ID field with failed CSV path if there were failures
                if failed_csv_path:
                    set_id_input.value = failed_csv_path
                    add_log_message(f"📋 Failed CSV path copied to Set ID field for retry")
                    page.update()
                
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
    
    def on_function_15_click(e):
        """Handle Function 15: Analyze dc:identifier Match"""
        # Determine if batch or single mode
        is_batch = editor.set_members and len(editor.set_members) > 0
        
        if not is_batch:
            # Single record mode
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            mms_ids_to_process = [mms_id_input.value]
        else:
            # Batch mode
            mms_ids_to_process = editor.set_members
        
        add_log_message(f"Starting dc:identifier match analysis for {len(mms_ids_to_process)} record(s)")
        update_status(f"Analyzing dc:identifier fields for {len(mms_ids_to_process)} record(s)...", False)
        
        if is_batch:
            # Show progress bar for batch processing
            set_progress_bar.visible = True
            set_progress_bar.value = 0
            set_progress_text.visible = True
            set_progress_text.value = f"Processing: 0/{len(mms_ids_to_process)} records"
            page.update()
            
            def progress_update(current, total):
                progress = current / total
                set_progress_bar.value = progress
                set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
                status_text.value = f"Analyzing identifiers: {current}/{total} records ({progress*100:.1f}%)"
                page.update()
        else:
            progress_update = None
        
        # Analyze identifier match
        storage.record_function_usage("function_15_analyze_identifier_match")
        success, message, output_dir = editor.analyze_identifier_match(
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
            # Auto-populate Set ID field with output directory path
            if output_dir:
                set_id_input.value = output_dir
                add_log_message(f"📋 Output directory path copied to Set ID field")
                page.update()
            
            add_log_message("dc:identifier match analysis complete")
            add_log_message("💡 Tip: Check the output directory for up to three CSV files:")
            add_log_message("    - identifier_matching_*.csv: Records with MMS ID in dc:identifier")
            add_log_message("    - identifier_non_matching_*.csv: Records without MMS ID match")
            add_log_message("    - identifier_failed_*.csv: Records that failed to process (if any)")
    
    def on_function_16_click(e):
        """Handle Function 16: Add MMS ID as dc:identifier"""
        # Determine if batch or single mode
        is_batch = editor.set_members and len(editor.set_members) > 0
        
        if not is_batch:
            # Single record mode
            if not mms_id_input.value:
                update_status("Please enter an MMS ID or load a set", True)
                return
            mms_ids_to_process = [mms_id_input.value]
        else:
            # Batch mode
            mms_ids_to_process = editor.set_members
        
        # Show confirmation dialog
        def proceed_with_update(e):
            warning_dialog.open = False
            page.update()
            
            add_log_message(f"Starting MMS ID identifier addition for {len(mms_ids_to_process)} record(s)")
            update_status(f"Adding MMS ID as dc:identifier for {len(mms_ids_to_process)} record(s)...", False)
            
            if is_batch:
                # Show progress bar for batch processing
                set_progress_bar.visible = True
                set_progress_bar.value = 0
                set_progress_text.visible = True
                set_progress_text.value = f"Processing: 0/{len(mms_ids_to_process)} records"
                page.update()
                
                def progress_update(current, total):
                    progress = current / total
                    set_progress_bar.value = progress
                    set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
                    status_text.value = f"Adding MMS ID identifiers: {current}/{total} records ({progress*100:.1f}%)"
                    page.update()
            else:
                progress_update = None
            
            # Add MMS ID as identifier
            storage.record_function_usage("function_16_add_mms_id_identifier")
            success, message, output_dir = editor.add_mms_id_identifier(
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
                # Auto-populate Set ID field with output directory path
                if output_dir:
                    set_id_input.value = output_dir
                    add_log_message(f"📋 Output directory path copied to Set ID field")
                    page.update()
                
                add_log_message("MMS ID identifier addition complete")
                add_log_message("💡 Tip: Check the output directory for up to three CSV files:")
                add_log_message("    - mms_id_already_present_*.csv: Records already having MMS ID as dc:identifier")
                add_log_message("    - mms_id_added_*.csv: Records updated with MMS ID dc:identifier")
                add_log_message("    - mms_id_failed_*.csv: Records that failed to process (if any)")
        
        def cancel_update(e):
            warning_dialog.open = False
            page.update()
            update_status("Operation cancelled by user", False)
        
        # Build warning message
        if is_batch:
            warning_msg = (
                f"⚠️ WARNING: This will modify up to {len(mms_ids_to_process)} bibliographic record(s) in Alma.\n\n"
                "Function: Add MMS ID as dc:identifier\n\n"
                "This action will:\n"
                "• Add the bare MMS ID as a dc:identifier field if not already present\n"
                "• Replace one duplicate dc:identifier with the MMS ID if duplicates exist\n"
                "• Create CSV files with results in a temporary directory\n\n"
                "Do you want to continue?"
            )
        else:
            warning_msg = (
                f"⚠️ WARNING: This will modify the bibliographic record in Alma.\n\n"
                f"MMS ID: {mms_ids_to_process[0]}\n"
                "Function: Add MMS ID as dc:identifier\n\n"
                "This action will add the MMS ID as a dc:identifier field if not already present.\n\n"
                "Do you want to continue?"
            )
        
        warning_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirm Data Modification", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(warning_msg, size=13),
                ]),
                padding=10,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_update),
                ft.TextButton(
                    "Proceed",
                    on_click=proceed_with_update,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_700,
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        page.open(warning_dialog)

    def on_function_17_click(e):
        """Handle Function 17: Restore Metadata from Previous Version"""
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

        def proceed_with_restore(e):
            warning_dialog.open = False
            page.update()

            add_log_message(f"Starting metadata restore for {len(mms_ids_to_process)} record(s)")
            update_status(f"Restoring metadata for {len(mms_ids_to_process)} record(s)...", False)

            if is_batch:
                # Show progress bar for batch processing
                set_progress_bar.visible = True
                set_progress_bar.value = 0
                set_progress_text.visible = True
                set_progress_text.value = f"Processing: 0/{len(mms_ids_to_process)} records"
                page.update()

                def progress_update(current, total):
                    progress = current / total
                    set_progress_bar.value = progress
                    set_progress_text.value = f"Processing: {current}/{total} records ({progress*100:.1f}%)"
                    status_text.value = f"Restoring metadata: {current}/{total} records ({progress*100:.1f}%)"
                    page.update()
            else:
                progress_update = None

            storage.record_function_usage("function_17_restore_metadata")
            success, message, report_csv = editor.restore_metadata_from_previous_version(
                mms_ids_to_process,
                progress_callback=progress_update
            )

            if is_batch:
                set_progress_bar.visible = False
                set_progress_text.visible = False
                page.update()

            update_status(message, not success)

            if report_csv:
                set_id_input.value = report_csv
                add_log_message("📋 Report CSV path copied to Set ID field")
                page.update()

            if success:
                add_log_message("Metadata restore via Selenium complete")
                add_log_message("💡 Review the report CSV for per-record outcomes")
                add_log_message("💡 If selectors need adjustment, check the debug HTML files saved to ~/Downloads")

        def cancel_restore(e):
            warning_dialog.open = False
            page.update()
            update_status("Metadata restore cancelled by user", False)

        warning_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("⚠️ Confirm Metadata Restore", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        "This will launch Chrome and automate the Alma MDE to restore each record "
                        "to its most recent prior metadata version.",
                        size=14
                    ),
                    ft.Container(height=10),
                    ft.Text(record_info, weight=ft.FontWeight.BOLD),
                    ft.Container(height=10),
                    ft.Text(
                        "Function: 17 - Restore Metadata from Previous Version (Selenium)",
                        italic=True,
                        color=ft.Colors.GREY_700
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Chrome will open and log into Alma via SSO. After DUO, set the search bar to "
                        "'All titles / MMS ID' before automation begins. "
                        "A CSV report of successes and failures will be saved to ~/Downloads.",
                        size=13
                    ),
                    ft.Container(height=10),
                    ft.Text("Do you want to continue?", weight=ft.FontWeight.BOLD),
                ]),
                padding=10,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_restore),
                ft.TextButton(
                    "Proceed",
                    on_click=proceed_with_restore,
                    style=ft.ButtonStyle(
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_700,
                    ),
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
        "function_11_prepare_tiff_jpg",
        "function_12_sound_by_decade",
        "function_14a_prepare_thumbnails",
        "function_14b_upload_thumbnails",
        "function_15_analyze_identifier_match",
        "function_16_add_mms_id_identifier",
        "function_17_restore_metadata"
    ]
    
    # Inactive functions - less frequently used
    inactive_functions = [
        "function_2_clear_dc_relation",
        "function_4_filter_pre1930",
        "function_6_replace_rights",
        "function_7_add_grinnell_id",
        "function_11b_upload_jpg",
        "function_13_placeholder"
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
        "function_11_prepare_tiff_jpg": {
            "label": "11: Prepare TIFF/JPG Representations",
            "icon": "🖼️",
            "handler": on_function_11_click,
            "help_file": "FUNCTION_11_IDENTIFY_SINGLE_TIFF.md"
        },
        "function_11b_upload_jpg": {
            "label": "11b: Upload JPG Files (DISABLED - Selenium abandoned)",
            "icon": "⊘",
            "handler": on_function_12_click,
            "help_file": "FUNCTION_12_***FAILED***_ADD_JPG_REPS.md"
        },
        "function_12_sound_by_decade": {
            "label": "12: Analyze Sound Records by Decade",
            "icon": "🎵",
            "handler": on_function_12_sound_click,
            "help_file": "FUNCTION_12_SOUND_BY_DECADE.md"
        },
        "function_13_placeholder": {
            "label": "13: (Intentionally Left Blank)",
            "icon": "⊘",
            "handler": on_function_13_placeholder_click,
            "help_file": "FUNCTION_13_PLACEHOLDER.md"
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
        },
        "function_15_analyze_identifier_match": {
            "label": "15: Analyze dc:identifier Match with MMS ID",
            "icon": "🔍",
            "handler": on_function_15_click,
            "help_file": "FUNCTION_15_ANALYZE_IDENTIFIER_MATCH.md"
        },
        "function_16_add_mms_id_identifier": {
            "label": "16: Add MMS ID as dc:identifier",
            "icon": "🏷️",
            "handler": on_function_16_click,
            "help_file": "FUNCTION_16_ADD_MMS_ID_IDENTIFIER.md"
        },
        "function_17_restore_metadata": {
            "label": "17: Restore Metadata from Previous Version",
            "icon": "♻️",
            "handler": on_function_17_click,
            "help_file": "FUNCTION_17_RESTORE_METADATA.md"
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
                        log_level_dropdown,
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
