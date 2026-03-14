#!/usr/bin/env python3
"""
Generate rsync commands to copy files from network storage to /Volumes/Acasis1TB
Reads Local Path column from CSV and creates rsync commands.
"""

import csv
import os
import sys
from pathlib import Path


def generate_rsync_commands(csv_file, destination_base="/Volumes/Acasis1TB", preserve_structure=False):
    """
    Generate rsync commands from CSV file.
    
    Args:
        csv_file: Path to the CSV file with Local Path column
        destination_base: Base destination directory on the external drive
        preserve_structure: If True, preserve the folder structure from source
    """
    
    if not os.path.exists(csv_file):
        print(f"Error: CSV file not found: {csv_file}", file=sys.stderr)
        sys.exit(1)
    
    rsync_commands = []
    skipped_files = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Check if Local Path column exists
        if 'Local Path' not in reader.fieldnames:
            print(f"Error: 'Local Path' column not found in CSV", file=sys.stderr)
            print(f"Available columns: {reader.fieldnames}", file=sys.stderr)
            sys.exit(1)
        
        for row in reader:
            local_path = row.get('Local Path', '').strip()
            
            # Skip empty paths or commented lines
            if not local_path or local_path.startswith('#'):
                continue
            
            # Check if file exists
            if not os.path.exists(local_path):
                skipped_files.append(local_path)
                continue
            
            # Determine destination path
            if preserve_structure:
                # Extract relative path from a common base (e.g., after "DG-Exports/")
                path_parts = Path(local_path).parts
                if 'DG-Exports' in path_parts:
                    idx = path_parts.index('DG-Exports')
                    relative_path = os.path.join(*path_parts[idx+1:])
                    destination = os.path.join(destination_base, 'DG-Exports', relative_path)
                else:
                    # Just use the filename
                    destination = os.path.join(destination_base, os.path.basename(local_path))
            else:
                # Just copy to destination base with filename
                destination = os.path.join(destination_base, os.path.basename(local_path))
            
            # Create rsync command
            # -a: archive mode (preserves permissions, timestamps, etc.)
            # -v: verbose
            # -h: human-readable
            # --progress: show progress
            rsync_cmd = f'rsync -avh --progress "{local_path}" "{destination}"'
            rsync_commands.append(rsync_cmd)
    
    return rsync_commands, skipped_files


def main():
    # Default to the broken_single_tiffs_with_local_paths.csv in current directory
    csv_file = "broken_single_tiffs_with_local_paths.csv"
    
    # Allow command line argument for different CSV file
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    # Change preserve_structure to True if you want to maintain folder hierarchy
    preserve_structure = False  # Set to True to preserve DG-Exports structure
    
    print("# rsync commands to copy files to /Volumes/Acasis1TB")
    print("# Generated from:", csv_file)
    print("# You can run this script or redirect output to a shell script:")
    print("# python generate_rsync_commands.py > copy_files.sh")
    print("# chmod +x copy_files.sh")
    print("# ./copy_files.sh")
    print()
    
    rsync_commands, skipped_files = generate_rsync_commands(csv_file, preserve_structure=preserve_structure)
    
    # Output rsync commands
    for cmd in rsync_commands:
        print(cmd)
    
    # Report skipped files to stderr
    if skipped_files:
        print(f"\n# Warning: {len(skipped_files)} files not found and skipped:", file=sys.stderr)
        for skipped in skipped_files[:10]:  # Show first 10
            print(f"#   {skipped}", file=sys.stderr)
        if len(skipped_files) > 10:
            print(f"#   ... and {len(skipped_files) - 10} more", file=sys.stderr)
    
    print(f"\n# Total: {len(rsync_commands)} rsync commands generated", file=sys.stderr)


if __name__ == "__main__":
    main()
