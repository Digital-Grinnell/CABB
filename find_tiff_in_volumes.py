#!/usr/bin/env python3
"""
Script to find TIFF files in /Volumes/exports for rows without a Local Path.
Updates the same CSV file in place.
"""

import csv
import subprocess
import os

def find_file_in_volumes(basename, search_path='/Volumes/exports'):
    """
    Search for a file in /Volumes/exports using find command.
    Returns the full path if found, otherwise None.
    """
    try:
        # Use find command to search in the specific directory
        result = subprocess.run(
            ['find', search_path, '-name', basename, '-type', 'f'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Return the first match
            paths = result.stdout.strip().split('\n')
            if paths and paths[0]:
                return paths[0]
        return None
    except Exception as e:
        print(f"Error searching for {basename}: {e}")
        return None

def process_csv(csv_file):
    """
    Read the CSV, find TIFF files in /Volumes/exports for empty Local Path rows,
    and update the CSV in place.
    """
    # Read all rows first
    rows = []
    with open(csv_file, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        header = next(reader)
        rows = list(reader)
    
    # Process rows that don't have a Local Path
    rows_processed = 0
    rows_found = 0
    
    for i, row in enumerate(rows):
        # Check if Local Path (column 2) is empty
        if len(row) >= 3 and not row[2]:
            rows_processed += 1
            
            # Extract basename from S3 path (column 1)
            s3_path = row[1]
            basename = os.path.basename(s3_path)
            
            # Search for the file in /Volumes/exports
            local_path = find_file_in_volumes(basename)
            
            if local_path:
                row[2] = local_path
                rows_found += 1
                print(f"[{rows_processed}] Found: {basename} -> {local_path}")
            else:
                print(f"[{rows_processed}] Not found: {basename}")
            
            # Progress update every 100 rows
            if rows_processed % 100 == 0:
                print(f"Progress: {rows_processed} rows searched, {rows_found} files found")
    
    # Write updated rows back to the same file
    with open(csv_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(header)
        writer.writerows(rows)
    
    print(f"\nComplete! Searched {rows_processed} rows, found {rows_found} files in /Volumes/exports.")
    print(f"Updated: {csv_file}")

if __name__ == '__main__':
    csv_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs_with_paths.csv'
    
    # Check if /Volumes/exports exists
    if not os.path.exists('/Volumes/exports'):
        print("ERROR: /Volumes/exports does not exist or is not mounted!")
        exit(1)
    
    print(f"Starting to process {csv_file}...")
    print("Searching for files in /Volumes/exports...")
    print("This may take a while...\n")
    
    process_csv(csv_file)
