#!/usr/bin/env python3
"""
Combine scraped_single_tiffs.csv and single_tiff_objects_20260127_092620.csv
into a single deduplicated CSV with MMS ID and S3 Path
"""
import csv

scraped_file = '/Users/mcfatem/GitHub/CABB/scraped_single_tiffs.csv'
current_file = '/Users/mcfatem/GitHub/CABB/single_tiff_objects_20260127_092620.csv'
output_file = '/Users/mcfatem/GitHub/CABB/all_single_tiffs.csv'

# Dictionary to store unique records (keyed by MMS ID)
records = {}

# Read scraped file (columns: MMS ID, File Path)
print(f"Reading {scraped_file}...")
with open(scraped_file, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        mms_id = row['MMS ID']
        s3_path = row['File Path']
        records[mms_id] = s3_path

scraped_count = len(records)
print(f"  Loaded {scraped_count} records from scraped file")

# Read current file (columns: MMS ID, Title, Representation ID, TIFF Filename, S3 Path, ...)
print(f"Reading {current_file}...")
with open(current_file, 'r') as f:
    reader = csv.DictReader(f)
    added_count = 0
    for row in reader:
        mms_id = row['MMS ID']
        s3_path = row['S3 Path']
        if mms_id not in records:
            records[mms_id] = s3_path
            added_count += 1

print(f"  Added {added_count} new records from current file")
print(f"  Total unique records: {len(records)}")

# Sort by MMS ID and write output
print(f"Writing to {output_file}...")
sorted_records = sorted(records.items(), key=lambda x: x[0])

with open(output_file, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['MMS ID', 'S3 Path'])
    for mms_id, s3_path in sorted_records:
        writer.writerow([mms_id, s3_path])

print(f"Successfully wrote {len(sorted_records)} records to {output_file}")
