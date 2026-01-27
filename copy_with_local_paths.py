#!/usr/bin/env python3
"""
Copy only rows with non-blank Local Path values to a new CSV file.
"""

import csv

def filter_and_copy_csv(input_file, output_file):
    """
    Read the CSV and copy only rows where Local Path is NOT blank/empty.
    """
    rows_total = 0
    rows_copied = 0
    filtered_rows = []
    
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        header = next(reader)
        filtered_rows.append(header)
        
        for row in reader:
            rows_total += 1
            # Check if Local Path (column 2) is NOT empty or blank
            if len(row) >= 3 and row[2].strip():
                filtered_rows.append(row)
                rows_copied += 1
    
    # Write to the new file
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(filtered_rows)
    
    rows_skipped = rows_total - rows_copied
    print(f"Total rows processed: {rows_total}")
    print(f"Rows copied (non-blank Local Path): {rows_copied}")
    print(f"Rows skipped (blank Local Path): {rows_skipped}")
    print(f"Created: {output_file}")

if __name__ == '__main__':
    input_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs_with_paths.csv'
    output_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs_with_local_paths.csv'
    filter_and_copy_csv(input_file, output_file)
