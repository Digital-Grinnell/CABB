#!/usr/bin/env python3
"""
Helper script to inspect saved Alma page HTML and extract element IDs/names
Usage: python inspect_alma_page.py ~/Downloads/alma_page_debug_*.html
"""

import sys
from pathlib import Path
from bs4 import BeautifulSoup

def inspect_html(file_path):
    """Extract and display useful element information from HTML"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    print("=" * 80)
    print(f"Inspecting: {file_path}")
    print("=" * 80)
    print()
    
    # Find all elements with IDs
    print("ELEMENTS WITH IDs:")
    print("-" * 80)
    elements_with_ids = soup.find_all(id=True)
    for elem in elements_with_ids[:50]:  # Limit to first 50
        elem_type = elem.name
        elem_id = elem.get('id')
        elem_class = elem.get('class', [])
        elem_name = elem.get('name', '')
        
        # Try to get some context
        text = elem.get_text(strip=True)[:50] if elem.get_text(strip=True) else ''
        
        print(f"  <{elem_type} id=\"{elem_id}\"", end='')
        if elem_name:
            print(f" name=\"{elem_name}\"", end='')
        if elem_class:
            print(f" class=\"{' '.join(elem_class)}\"", end='')
        if text:
            print(f"> {text[:40]}...", end='')
        print()
    
    print()
    print("FORM INPUTS (input, select, button):")
    print("-" * 80)
    form_elements = soup.find_all(['input', 'select', 'button', 'textarea'])
    for elem in form_elements[:30]:  # Limit to first 30
        elem_type = elem.name
        elem_id = elem.get('id', 'NO_ID')
        elem_name = elem.get('name', 'NO_NAME')
        elem_class = elem.get('class', [])
        input_type = elem.get('type', '')
        placeholder = elem.get('placeholder', '')
        
        print(f"  <{elem_type}", end='')
        if input_type:
            print(f" type=\"{input_type}\"", end='')
        print(f" id=\"{elem_id}\" name=\"{elem_name}\"", end='')
        if elem_class:
            print(f" class=\"{' '.join(elem_class[:2])}\"", end='')
        if placeholder:
            print(f" placeholder=\"{placeholder}\"", end='')
        print(">")
    
    print()
    print("SEARCH FOR COMMON ALMA SEARCH ELEMENTS:")
    print("-" * 80)
    
    # Look for elements containing "search" in id, name, or class
    search_elements = soup.find_all(lambda tag: (
        (tag.get('id') and 'search' in tag.get('id').lower()) or
        (tag.get('name') and 'search' in tag.get('name').lower()) or
        (tag.get('class') and any('search' in c.lower() for c in tag.get('class')))
    ))
    
    for elem in search_elements[:20]:
        elem_id = elem.get('id', 'NO_ID')
        elem_name = elem.get('name', 'NO_NAME')
        print(f"  <{elem.name} id=\"{elem_id}\" name=\"{elem_name}\">")
    
    print()
    print("=" * 80)
    print("Next steps:")
    print("1. Look for elements related to search (search bar, search type dropdown)")
    print("2. Find their 'id' or 'name' attributes")
    print("3. Update the selectors in app.py:")
    print("   - Line ~4050: search_type_select (By.ID, 'searchType')")
    print("   - Line ~4060: search_field_select (By.ID, 'searchField')")
    print("   - Line ~4070: search_input (By.ID, 'searchInput')")
    print("   - Line ~4085: search_button (By.ID, 'searchButton')")
    print("=" * 80)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python inspect_alma_page.py <path_to_html_file>")
        print()
        print("Example:")
        print("  python inspect_alma_page.py ~/Downloads/alma_page_debug_20260226_161950.html")
        sys.exit(1)
    
    html_file = Path(sys.argv[1])
    if not html_file.exists():
        print(f"Error: File not found: {html_file}")
        sys.exit(1)
    
    inspect_html(html_file)
