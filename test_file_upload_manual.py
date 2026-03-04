#!/usr/bin/env python3
"""
Manual test script for Function 11b file upload.
This will pause at the file selection step so you can manually complete it,
allowing us to observe the correct process.
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from pathlib import Path

def test_manual_upload():
    # TEST CONFIGURATION - EDIT THESE VALUES
    rep_id = "12349952590004641"  # Replace with actual rep_id from CSV
    jpg_file_path = "/Users/mcfatem/Downloads/CABB_tiff_jpg_prep_20260303_155341/grinnell_5287_OBJ.jpg"  # Replace with actual JPG file path
    
    print("\n" + "="*70)
    print("MANUAL FILE UPLOAD TEST")
    print("="*70)
    print(f"\nRep ID: {rep_id}")
    print(f"File: {jpg_file_path}")
    
    # Verify file exists
    file_path = Path(jpg_file_path)
    if not file_path.exists():
        print(f"\n❌ ERROR: File not found: {jpg_file_path}")
        return
    
    print(f"✓ File exists ({file_path.stat().st_size} bytes)")
    
    # Start Firefox
    print("\n📂 Starting Firefox...")
    options = webdriver.FirefoxOptions()
    # Don't run headless - we need to see the browser
    driver = webdriver.Firefox(options=options)
    driver.maximize_window()
    
    try:
        # Step 1: Navigate to Alma
        print("\n🌐 Step 1: Navigating to Alma...")
        driver.get("https://grinnell.alma.exlibrisgroup.com/mng/login")
        print("✓ Page loaded")
        
        # Step 2: Wait for SSO login
        print("\n🔐 Step 2: Please log in manually (SSO + DUO)...")
        print("   Waiting up to 120 seconds for you to complete login...")
        
        # Wait for search box to appear (indicates successful login)
        try:
            WebDriverWait(driver, 120).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[aria-label='Search query']"))
            )
            print("✓ Login successful - search box detected")
        except TimeoutException:
            print("❌ Login timeout - please try again")
            return
        
        time.sleep(2)
        
        # Step 3: Search for representation
        print(f"\n🔍 Step 3: Searching for rep_id: {rep_id}")
        
        # Enter search query
        search_box = driver.find_element(By.CSS_SELECTOR, "input[aria-label='Search query']")
        search_box.clear()
        search_box.send_keys(rep_id)
        print("✓ Entered search query")
        
        time.sleep(1)
        
        # Click Search button
        search_button = driver.find_element(By.CSS_SELECTOR, "button#search-button")
        search_button.click()
        print("✓ Clicked search button")
        
        time.sleep(3)
        
        # Step 4: Click Digital Representations link
        print("\n📋 Step 4: Navigating to Digital Representations...")
        
        try:
            dig_rep_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Digital Representations"))
            )
            dig_rep_link.click()
            print("✓ Clicked Digital Representations link")
        except TimeoutException:
            print("❌ Could not find Digital Representations link")
            print("   Please check if search returned results")
            input("\nPress Enter to close browser...")
            return
        
        time.sleep(3)
        
        # Step 5: Click Files List tab
        print("\n📁 Step 5: Opening Files List tab...")
        
        try:
            files_list_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "A_NAV_LINK_cresource_editordigitalrep_tabsfiles_list_span"))
            )
            files_list_tab.click()
            print("✓ Clicked Files List tab")
        except TimeoutException:
            try:
                files_list_tab = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[@role='tab'][contains(., 'Files List')]"))
                )
                files_list_tab.click()
                print("✓ Clicked Files List tab (via text)")
            except TimeoutException:
                print("❌ Could not find Files List tab")
                input("\nPress Enter to close browser...")
                return
        
        time.sleep(2)
        
        # Step 6: Click Add Files link
        print("\n➕ Step 6: Clicking 'Add Files' link...")
        
        try:
            add_files_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Add Files')]"))
            )
            add_files_link.click()
            print("✓ Clicked 'Add Files' link")
        except TimeoutException:
            print("❌ Could not find 'Add Files' link")
            input("\nPress Enter to close browser...")
            return
        
        print("   ⏳ Waiting for page to reload with upload interface...")
        time.sleep(5)
        
        # Step 7: Check for iframe
        print("\n🖼️  Step 7: Checking for iframe...")
        
        try:
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title='fileUpload']"))
            )
            print("✓ Found iframe with title='fileUpload'")
            
            # Switch to iframe
            driver.switch_to.frame(iframe)
            print("✓ Switched to iframe context")
            time.sleep(2)
            
            # Look for file inputs
            print("\n📎 Step 8: Analyzing file input elements in iframe...")
            
            file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            print(f"✓ Found {len(file_inputs)} file input element(s)")
            
            for idx, fi in enumerate(file_inputs):
                attrs = driver.execute_script("""
                    var elem = arguments[0];
                    var style = window.getComputedStyle(elem);
                    return {
                        id: elem.id || '(none)',
                        name: elem.name || '(none)',
                        className: elem.className || '(none)',
                        display: style.display,
                        visibility: style.visibility,
                        offsetParent: elem.offsetParent !== null,
                        tagName: elem.tagName
                    };
                """, fi)
                
                print(f"\n  Input #{idx+1}:")
                print(f"    ID: {attrs['id']}")
                print(f"    Name: {attrs['name']}")
                print(f"    Class: {attrs['className'][:50]}")
                print(f"    Display: {attrs['display']}")
                print(f"    Visibility: {attrs['visibility']}")
                print(f"    Has offsetParent: {attrs['offsetParent']}")
                is_hidden = attrs['display'] == 'none' or not attrs['offsetParent']
                print(f"    → Hidden: {is_hidden}")
            
            # NOW PAUSE FOR MANUAL INTERACTION
            print("\n" + "="*70)
            print("⏸️  PAUSED FOR MANUAL FILE SELECTION")
            print("="*70)
            print("\nPlease manually select the file in the browser:")
            print(f"  File to select: {file_path.name}")
            print(f"  Full path: {file_path.absolute()}")
            print("\nOBSERVE:")
            print("  - Does a system file picker dialog open?")
            print("  - What button/link do you click to trigger it?")
            print("  - Does the file appear in a table after selection?")
            print("  - Is there a Save button in the iframe?")
            print("\nAfter you've manually uploaded the file, press Enter to continue...")
            input()
            
            # Check if file was added
            print("\n🔍 Checking if file was successfully added...")
            
            try:
                # Look for table rows
                table_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
                print(f"✓ Found {len(table_rows)} row(s) in table")
                
                # Look for the filename
                page_text = driver.find_element(By.TAG_NAME, "body").text
                if file_path.name in page_text:
                    print(f"✓ File name '{file_path.name}' appears on page")
                else:
                    print(f"⚠️  File name '{file_path.name}' NOT found on page")
                
                # Look for Save button
                save_buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Save')]")
                if save_buttons:
                    print(f"✓ Found {len(save_buttons)} Save button(s)")
                    print("\nShould I click Save? (y/n)")
                    response = input().strip().lower()
                    if response == 'y':
                        save_buttons[0].click()
                        print("✓ Clicked Save button")
                        time.sleep(3)
                else:
                    print("⚠️  No Save button found")
                    
            except Exception as e:
                print(f"⚠️  Error checking results: {e}")
            
            # Switch back to main content
            driver.switch_to.default_content()
            print("\n✓ Switched back to main page context")
            
        except TimeoutException:
            print("❌ iframe not found - upload interface may work differently")
        
        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70)
        print("\nBrowser will remain open for your inspection.")
        print("Press Enter to close browser...")
        input()
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("\nPress Enter to close browser...")
        input()
    finally:
        driver.quit()
        print("\n✓ Browser closed")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("⚠️  BEFORE RUNNING:")
    print("="*70)
    print("1. Edit this file and set:")
    print("   - rep_id = 'YOUR_ACTUAL_REP_ID'")
    print("   - jpg_file_path = '/full/path/to/your/file.jpg'")
    print("2. Run: python3 test_file_upload_manual.py")
    print("="*70)
    
    test_manual_upload()
