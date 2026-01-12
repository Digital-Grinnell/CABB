#!/usr/bin/env python3
"""
Fetch a sample XML record to examine its structure
"""
import requests
import json
import xml.etree.ElementTree as ET

# Load persistent config
with open('persistent.json', 'r') as f:
    config = json.load(f)

api_key = config.get('api_key')
api_region = config.get('api_region', 'North America')

# MMS ID that's failing
mms_id = '991011546793604641'

# Get the API URL
if api_region == 'EU':
    api_url = 'https://api-eu.hosted.exlibrisgroup.com'
elif api_region == 'Asia Pacific':
    api_url = 'https://api-ap.hosted.exlibrisgroup.com'
else:  # North America
    api_url = 'https://api-na.hosted.exlibrisgroup.com'

# Fetch the record
print(f"Fetching MMS ID: {mms_id}")
response = requests.get(
    f"{api_url}/almaws/v1/bibs/{mms_id}?view=full&expand=None&apikey={api_key}",
    headers={'Accept': 'application/xml'}
)

if response.status_code != 200:
    print(f"Error: {response.status_code}")
    print(response.text)
    exit(1)

# Parse the XML
root = ET.fromstring(response.text)

# Print the XML structure
print("\n" + "="*80)
print("XML Root element:", root.tag)
print("="*80)

# Print all top-level children
print("\nTop-level children:")
for child in root:
    print(f"  - {child.tag}: {len(list(child))} sub-elements")

# Look for 'anies' element
anies = root.find('.//{http://com/exlibris/urm/general/xmlbeans}anies')
if anies is not None:
    print("\n" + "="*80)
    print("Found 'anies' element")
    print("="*80)
    print(f"Number of 'any' children: {len(list(anies))}")
    
    # Look for metadata element
    for any_elem in anies:
        for child in any_elem:
            print(f"\n  any > {child.tag}")
            if 'metadata' in child.tag.lower():
                print(f"    *** FOUND METADATA: {child.tag} ***")
                print(f"    Attributes: {child.attrib}")
                print(f"    Children ({len(list(child))}):")
                for sub in child:
                    print(f"      - {sub.tag}: {sub.text[:50] if sub.text else '(no text)'}")
else:
    print("\nNo 'anies' element found!")

# Save full XML to file
with open('sample_failing_record.xml', 'w') as f:
    f.write(response.text)
print(f"\nFull XML saved to sample_failing_record.xml")
