"""
Alma-D Bulk Bib Records Editor
A Flet UI app designed to perform various Alma-Digital bib record editing functions.
"""

import flet as ft
import os
from dotenv import load_dotenv
from almapipy import AlmaCnxn
import xml.etree.ElementTree as ET

# Load environment variables
load_dotenv()


class AlmaBibEditor:
    """Main application class for Alma Bib Records Editor"""
    
    def __init__(self):
        self.api_key = os.getenv('ALMA_API_KEY', '')
        self.api_url = os.getenv('ALMA_API_URL', 'https://api-na.hosted.exlibrisgroup.com')
        self.alma_cnxn = None
        self.status_text = None
        
    def initialize_alma_connection(self):
        """Initialize connection to Alma API"""
        if not self.api_key:
            return False, "API Key not configured. Please set ALMA_API_KEY in .env file"
        
        try:
            self.alma_cnxn = AlmaCnxn(self.api_key, self.api_url)
            return True, "Connected to Alma API"
        except Exception as e:
            return False, f"Failed to connect to Alma API: {str(e)}"
    
    def clear_dc_relation_collections(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 1: Clear all dc:relation fields having a value that begins with 
        "alma:01GCL_INST/bibs/collections/"
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.alma_cnxn:
            return False, "Alma API connection not initialized"
        
        try:
            # Fetch the bibliographic record
            bib = self.alma_cnxn.get_bib(mms_id)
            
            if not bib:
                return False, f"Record {mms_id} not found"
            
            # Parse the XML record
            # Note: This is a placeholder implementation
            # In a real scenario, you would parse and modify the XML
            # to remove dc:relation fields with the specified pattern
            
            # Example XML parsing logic would go here
            # root = ET.fromstring(bib)
            # namespace = {'dc': 'http://purl.org/dc/elements/1.1/'}
            # relations = root.findall('.//dc:relation', namespace)
            # for relation in relations:
            #     if relation.text and relation.text.startswith('alma:01GCL_INST/bibs/collections/'):
            #         relation.getparent().remove(relation)
            
            # Update the record
            # updated_bib = self.alma_cnxn.update_bib(mms_id, modified_xml)
            
            return True, f"Successfully processed record {mms_id} (Placeholder)"
            
        except Exception as e:
            return False, f"Error processing record {mms_id}: {str(e)}"
    
    def placeholder_function_2(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 2: Placeholder for future Alma-Digital record editing function
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        return True, f"Placeholder Function 2 executed for record {mms_id}"
    
    def placeholder_function_3(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 3: Placeholder for future Alma-Digital record editing function
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        return True, f"Placeholder Function 3 executed for record {mms_id}"
    
    def placeholder_function_4(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 4: Placeholder for future Alma-Digital record editing function
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        return True, f"Placeholder Function 4 executed for record {mms_id}"
    
    def placeholder_function_5(self, mms_id: str) -> tuple[bool, str]:
        """
        Function 5: Placeholder for future Alma-Digital record editing function
        
        Args:
            mms_id: The MMS ID of the bibliographic record
            
        Returns:
            tuple: (success: bool, message: str)
        """
        return True, f"Placeholder Function 5 executed for record {mms_id}"


def main(page: ft.Page):
    """Main Flet application"""
    page.title = "Alma-D Bulk Bib Records Editor"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 20
    
    # Initialize editor
    editor = AlmaBibEditor()
    
    # UI Components
    status_text = ft.Text("", color=ft.colors.BLUE)
    mms_id_input = ft.TextField(
        label="MMS ID",
        hint_text="Enter bibliographic record MMS ID",
        width=400
    )
    
    def update_status(message: str, is_error: bool = False):
        """Update status message"""
        status_text.value = message
        status_text.color = ft.colors.RED if is_error else ft.colors.GREEN
        page.update()
    
    def on_connect_click(e):
        """Handle connect button click"""
        success, message = editor.initialize_alma_connection()
        update_status(message, not success)
    
    def on_clear_dc_relation_click(e):
        """Handle Function 1: Clear dc:relation collections"""
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        success, message = editor.clear_dc_relation_collections(mms_id_input.value)
        update_status(message, not success)
    
    def on_function_2_click(e):
        """Handle Function 2 click"""
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        success, message = editor.placeholder_function_2(mms_id_input.value)
        update_status(message, not success)
    
    def on_function_3_click(e):
        """Handle Function 3 click"""
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        success, message = editor.placeholder_function_3(mms_id_input.value)
        update_status(message, not success)
    
    def on_function_4_click(e):
        """Handle Function 4 click"""
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        success, message = editor.placeholder_function_4(mms_id_input.value)
        update_status(message, not success)
    
    def on_function_5_click(e):
        """Handle Function 5 click"""
        if not mms_id_input.value:
            update_status("Please enter an MMS ID", True)
            return
        
        success, message = editor.placeholder_function_5(mms_id_input.value)
        update_status(message, not success)
    
    # Build UI
    page.add(
        ft.Column([
            ft.Text("Alma-D Bulk Bib Records Editor", 
                   size=24, 
                   weight=ft.FontWeight.BOLD),
            ft.Divider(),
            
            # Connection section
            ft.Container(
                content=ft.Column([
                    ft.Text("Connection", size=18, weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton(
                        "Connect to Alma API",
                        on_click=on_connect_click,
                        icon=ft.icons.CONNECT_WITHOUT_CONTACT
                    ),
                ]),
                padding=10,
            ),
            
            ft.Divider(),
            
            # Input section
            ft.Container(
                content=ft.Column([
                    ft.Text("Record Input", size=18, weight=ft.FontWeight.BOLD),
                    mms_id_input,
                ]),
                padding=10,
            ),
            
            ft.Divider(),
            
            # Functions section
            ft.Container(
                content=ft.Column([
                    ft.Text("Editing Functions", size=18, weight=ft.FontWeight.BOLD),
                    
                    ft.ElevatedButton(
                        "1. Clear dc:relation Collections Fields",
                        on_click=on_clear_dc_relation_click,
                        icon=ft.icons.CLEAR_ALL,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "2. Placeholder Function 2",
                        on_click=on_function_2_click,
                        icon=ft.icons.EDIT,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "3. Placeholder Function 3",
                        on_click=on_function_3_click,
                        icon=ft.icons.EDIT,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "4. Placeholder Function 4",
                        on_click=on_function_4_click,
                        icon=ft.icons.EDIT,
                        width=400
                    ),
                    
                    ft.ElevatedButton(
                        "5. Placeholder Function 5",
                        on_click=on_function_5_click,
                        icon=ft.icons.EDIT,
                        width=400
                    ),
                ]),
                padding=10,
            ),
            
            ft.Divider(),
            
            # Status section
            ft.Container(
                content=ft.Column([
                    ft.Text("Status", size=18, weight=ft.FontWeight.BOLD),
                    status_text,
                ]),
                padding=10,
            ),
        ])
    )


if __name__ == "__main__":
    ft.app(target=main)
