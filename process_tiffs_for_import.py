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
    alma_export_csv = "alma_export_20260127_161511.csv"
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
    
    # Read CSV and process all rows
    processed_count = 0
    updated_mms_ids = []
    failed_files = []
    skipped_files = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            mms_id = row['MMS ID']
            local_path = row['Local Path']
            
            if not local_path:
                skipped_files.append({'mms_id': mms_id, 'reason': 'No local path'})
                continue
            
            source_tiff = Path(local_path)
            
            # Check if source file exists
            if not source_tiff.exists():
                failed_files.append({'mms_id': mms_id, 'path': local_path, 'reason': 'File not found'})
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
            try:
                shutil.copy2(source_tiff, dest_tiff)
                print(f"    ✓ Copied to {dest_tiff}")
            except (OSError, IOError) as e:
                error_msg = f"Copy failed: {str(e)}"
                print(f"    ✗ ERROR: {error_msg}")
                failed_files.append({'mms_id': mms_id, 'path': str(source_tiff), 'reason': error_msg})
                continue
            
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
                error_msg = f"JPG creation failed: {str(e)}"
                print(f"    ✗ ERROR: {error_msg}")
                failed_files.append({'mms_id': mms_id, 'path': str(source_tiff), 'reason': error_msg})
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
    
    # Write failed files report
    if failed_files:
        failed_csv = "process_tiffs_failures.csv"
        print(f"\n{'='*60}")
        print(f"Writing failed files report to {failed_csv}...")
        with open(failed_csv, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['mms_id', 'path', 'reason']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(failed_files)
        print(f"✓ Logged {len(failed_files)} failed files")
    
    # Print summary report
    print(f"\n{'='*60}")
    print(f"PROCESSING SUMMARY:")
    print(f"{'='*60}")
    print(f"Successfully processed: {processed_count} files")
    print(f"Failed:                 {len(failed_files)} files")
    print(f"Skipped (no path):      {len(skipped_files)} files")
    print(f"Total records:          {processed_count + len(failed_files) + len(skipped_files)}")
    print(f"\nFiles saved to: {for_import_dir.absolute()}")
    if failed_files:
        print(f"Failed files logged to: process_tiffs_failures.csv")

if __name__ == "__main__":
    process_tiffs()
