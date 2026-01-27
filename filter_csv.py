#!/usr/bin/env python3
"""
Filter CSV to keep only rows with blank Local Path values.
"""

import csv

def filter_csv(input_file):
    """
    Read the CSV and keep only rows where Local Path is blank/empty.
    Overwrites the original file.
    """
    rows_total = 0
    rows_kept = 0
    filtered_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        header = next(reader)
        filtered_rows.append(header)
        
        for row in reader:
            rows_total += 1
            # Check if Local Path (column 2) is empty or blank
            if len(row) >= 3 and not row[2].strip():
                filtered_rows.append(row)
                rows_kept += 1
    
    # Write back to the same file
    with open(input_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(filtered_rows)
    
    rows_removed = rows_total - rows_kept
    print(f"Total rows processed: {rows_total}")
    print(f"Rows kept (blank Local Path): {rows_kept}")
    print(f"Rows removed (non-blank Local Path): {rows_removed}")
    print(f"Updated: {input_file}")

if __name__ == '__main__':
    input_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs_without_local_paths.csv'
    filter_csv(input_file)
