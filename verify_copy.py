#!/usr/bin/env python3
"""Verify files were copied successfully"""

import csv
import os

csv_file = "broken_single_tiffs_with_local_paths.csv"
destination = "/Volumes/Acasis1TB"

copied = []
missing = []

with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        local_path = row.get('Local Path', '').strip()
        if not local_path or local_path.startswith('#'):
            continue
        
        filename = os.path.basename(local_path)
        dest_path = os.path.join(destination, filename)
        
        if os.path.exists(dest_path):
            copied.append(filename)
        else:
            missing.append(filename)

print(f"✓ Successfully copied: {len(copied)} files")
print(f"✗ Missing: {len(missing)} files")

if missing:
    print("\nMissing files:")
    for f in missing[:10]:
        print(f"  - {f}")
    if len(missing) > 10:
        print(f"  ... and {len(missing) - 10} more")
