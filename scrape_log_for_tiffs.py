#!/usr/bin/env python3
"""
Scrape the log file to extract MMS IDs and file paths for single TIFF representations
"""
import re
import csv

log_file = '/Users/mcfatem/GitHub/CABB/logfiles/cabb_20260126_162853.log'
output_file = '/Users/mcfatem/GitHub/CABB/scraped_single_tiffs.csv'

results = []
current_mms = None

print(f"Reading log file: {log_file}")

with open(log_file, 'r') as f:
    for line in f:
        # Look for MMS ID with 'Found 1 file(s)' 
        mms_match = re.search(r'MMS (\d+): Found 1 file\(s\) in representation', line)
        if mms_match:
            current_mms = mms_match.group(1)
        
        # Look for File path (should come after MMS ID)
        file_match = re.search(r'File: (.+\.tiff?)$', line)
        if file_match and current_mms:
            file_path = file_match.group(1).strip()
            results.append({'MMS ID': current_mms, 'File Path': file_path})
            current_mms = None  # Reset

print(f'Found {len(results)} single TIFF records')

# Write to CSV
with open(output_file, 'w', newline='') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=['MMS ID', 'File Path'])
    writer.writeheader()
    writer.writerows(results)

print(f'Written to {output_file}')

# Show first few records
print("\nFirst 10 records:")
for i, record in enumerate(results[:10], 1):
    print(f"{i}. MMS {record['MMS ID']}: {record['File Path']}")
