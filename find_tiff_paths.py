#!/usr/bin/env python3
"""
Script to find TIFF files on the Mac and update CSV with their full paths.
"""

import csv
import os
import subprocess
from pathlib import Path

def find_file_on_mac(basename):
    """
    Search for a file on the Mac using mdfind (Spotlight).
    Returns the full path if found, otherwise None.
    """
    try:
        # Use mdfind (Spotlight) to search for the file
        result = subprocess.run(
            ['mdfind', f'kMDItemFSName == "{basename}"'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Return the first match
            paths = result.stdout.strip().split('\n')
            if paths:
                return paths[0]
        return None
    except Exception as e:
        print(f"Error searching for {basename}: {e}")
        return None

def process_csv(input_file, output_file):
    """
    Read the CSV, find TIFF files, and append their full paths.
    """
    rows_processed = 0
    rows_found = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        # Read and write header
        header = next(reader)
        header.append('Local Path')
        writer.writerow(header)
        
        # Process each row
        for row in reader:
            rows_processed += 1
            
            # Extract basename from S3 path (last part)
            s3_path = row[1]
            basename = os.path.basename(s3_path)
            
            # Search for the file on Mac
            local_path = find_file_on_mac(basename)
            
            # Append the local path (or empty string if not found)
            if local_path:
                row.append(local_path)
                rows_found += 1
                print(f"[{rows_processed}] Found: {basename} -> {local_path}")
            else:
                row.append('')
                print(f"[{rows_processed}] Not found: {basename}")
            
            writer.writerow(row)
            
            # Progress update every 100 rows
            if rows_processed % 100 == 0:
                print(f"Progress: {rows_processed} rows processed, {rows_found} files found")
    
    print(f"\nComplete! Processed {rows_processed} rows, found {rows_found} files.")
    print(f"Output saved to: {output_file}")

if __name__ == '__main__':
    input_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs.csv'
    output_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs_with_paths.csv'
    
    print(f"Starting to process {input_file}...")
    print("This may take a while as we search for each file...\n")
    
    process_csv(input_file, output_file)
