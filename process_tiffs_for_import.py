#!/usr/bin/env python3
"""
Script to process TIFF files from CSV:
1. Read first 5 rows from all_single_tiffs_with_local_paths.csv
2. Copy TIFF files to For-Import directory
3. Create JPG derivatives and save to For-Import directory
4. Update alma_export CSV with file names
"""

import csv
import os
import shutil
from pathlib import Path
from PIL import Image

def process_tiffs():
    """Process TIFF files from CSV and create JPG derivatives"""
    
    # Define paths
    csv_file = "all_single_tiffs_with_local_paths.csv"
    alma_export_csv = "alma_export_20260127_155208.csv"
    for_import_dir = Path("For-Import")
    
    # Create For-Import directory if it doesn't exist
    for_import_dir.mkdir(exist_ok=True)
    print(f"Created/verified directory: {for_import_dir}")
    
    # Read alma_export CSV into memory
    print(f"Reading {alma_export_csv}...")
    alma_rows = []
    alma_fieldnames = []
    with open(alma_export_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        alma_fieldnames = reader.fieldnames
        alma_rows = list(reader)
    
    # Create a mapping of mms_id to row index for quick lookup
    mms_to_index = {row['mms_id']: idx for idx, row in enumerate(alma_rows)}
    
    # Read CSV and process first 5 data rows
    processed_count = 0
    updated_mms_ids = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            if processed_count >= 5:
                break
            
            mms_id = row['MMS ID']
            local_path = row['Local Path']
            
            if not local_path:
                print(f"Skipping MMS ID {mms_id}: No local path")
                continue
            
            source_tiff = Path(local_path)
            
            # Check if source file exists
            if not source_tiff.exists():
                print(f"WARNING: File not found: {source_tiff}")
                continue
            
            # Get filename
            tiff_filename = source_tiff.name
            jpg_filename = tiff_filename.replace('.tiff', '.jpg').replace('.tif', '.jpg')
            
            # Define destination paths
            dest_tiff = for_import_dir / tiff_filename
            dest_jpg = for_import_dir / jpg_filename
            
            # Copy TIFF file
            print(f"\nProcessing MMS ID {mms_id}:")
            print(f"  Copying TIFF: {tiff_filename}")
            shutil.copy2(source_tiff, dest_tiff)
            print(f"    ✓ Copied to {dest_tiff}")
            
            # Create JPG derivative
            print(f"  Creating JPG: {jpg_filename}")
            try:
                with Image.open(source_tiff) as img:
                    # Convert to RGB if necessary (TIFF might have alpha channel or be in different mode)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                        img = rgb_img
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Save as JPG with high quality
                    img.save(dest_jpg, 'JPEG', quality=95, optimize=True)
                    print(f"    ✓ Created JPG at {dest_jpg}")
                    
            except Exception as e:
                print(f"    ✗ ERROR creating JPG: {e}")
                continue
            
            # Update alma_export CSV with file names
            if mms_id in mms_to_index:
                row_idx = mms_to_index[mms_id]
                alma_rows[row_idx]['file_name_1'] = jpg_filename
                alma_rows[row_idx]['file_name_2'] = tiff_filename
                updated_mms_ids.append(mms_id)
                print(f"  Updating alma_export CSV:")
                print(f"    file_name_1: {jpg_filename}")
                print(f"    file_name_2: {tiff_filename}")
            else:
                print(f"  WARNING: MMS ID {mms_id} not found in alma_export CSV")
            
            processed_count += 1
    
    # Write updated alma_export CSV
    if updated_mms_ids:
        print(f"\n{'='*60}")
        print(f"Writing updated {alma_export_csv}...")
        with open(alma_export_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=alma_fieldnames)
            writer.writeheader()
            writer.writerows(alma_rows)
        print(f"✓ Updated {len(updated_mms_ids)} records in {alma_export_csv}")
    
    print(f"\n{'='*60}")
    print(f"Processed {processed_count} files successfully")
    print(f"Files saved to: {for_import_dir.absolute()}")

if __name__ == "__main__":
    process_tiffs()
