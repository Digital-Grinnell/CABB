#!/usr/bin/env python3
"""
Sort handle_validation_*.csv files by the last 2 columns (columns 7 and 8),
keeping the header row fixed at the top.
"""

import csv
import glob
import sys
from pathlib import Path


def sort_csv_file(filepath):
    """Sort a CSV file by the last 2 columns while keeping the header."""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        # Read header
        header = next(reader)
        
        # Read all data rows
        data_rows = list(reader)
    
    # Sort by column 7 (index 6) and then column 8 (index 7)
    # Handle cases where columns might be missing
    def sort_key(row):
        col7 = row[6] if len(row) > 6 else ''
        col8 = row[7] if len(row) > 7 else ''
        return (col7, col8)
    
    sorted_rows = sorted(data_rows, key=sort_key)
    
    # Write back to file
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(sorted_rows)
    
    print(f"Sorted: {filepath}")


def main():
    # Find all handle_validation_*.csv files in the current directory
    pattern = str(Path(__file__).parent / 'handle_validation_*.csv')
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        print("No handle_validation_*.csv files found in the current directory.")
        sys.exit(1)
    
    print(f"Found {len(csv_files)} file(s) to sort:")
    for filepath in csv_files:
        sort_csv_file(filepath)
    
    print("\nAll files sorted successfully!")


if __name__ == '__main__':
    main()
