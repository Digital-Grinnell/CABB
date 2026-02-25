#!/usr/bin/env python3
"""
Analyze sound records distribution by decade and half-decade.
"""

import csv
from collections import defaultdict
from datetime import datetime

def analyze_distributions(input_file):
    """Analyze record counts by decade and half-decade."""
    
    decade_counts = defaultdict(int)
    half_decade_counts = defaultdict(int)
    
    # Read the input CSV
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            year = int(row['Year'])
            decade = row['Decade']
            
            # Count by decade
            decade_counts[decade] += 1
            
            # Determine half-decade
            # E.g., 1960-1964 or 1965-1969
            start_year = (year // 5) * 5
            end_year = start_year + 4
            half_decade = f"{start_year}-{end_year}"
            half_decade_counts[half_decade] += 1
    
    return decade_counts, half_decade_counts

def write_decade_distribution(decade_counts, output_file):
    """Write decade distribution to CSV."""
    
    # Sort by decade
    sorted_decades = sorted(decade_counts.items())
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Decade', 'Record Count'])
        
        total = 0
        for decade, count in sorted_decades:
            writer.writerow([decade, count])
            total += count
        
        # Add total row
        writer.writerow(['TOTAL', total])
    
    print(f"Decade distribution written to {output_file}")
    print(f"Total records: {total}")
    
def write_half_decade_distribution(half_decade_counts, output_file):
    """Write half-decade distribution to CSV."""
    
    # Sort by start year
    sorted_halves = sorted(half_decade_counts.items(), 
                          key=lambda x: int(x[0].split('-')[0]))
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Half-Decade Range', 'Record Count'])
        
        total = 0
        for half_decade, count in sorted_halves:
            writer.writerow([half_decade, count])
            total += count
        
        # Add total row
        writer.writerow(['TOTAL', total])
    
    print(f"Half-decade distribution written to {output_file}")
    print(f"Total records: {total}")

def main():
    input_file = 'sound_records_by_decade_20260224_152304.csv'
    
    # Generate timestamped output filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    decade_output = f'decade_distribution_{timestamp}.csv'
    half_decade_output = f'half_decade_distribution_{timestamp}.csv'
    
    # Analyze the data
    decade_counts, half_decade_counts = analyze_distributions(input_file)
    
    # Write output files
    write_decade_distribution(decade_counts, decade_output)
    write_half_decade_distribution(half_decade_counts, half_decade_output)
    
    # Print summary to console
    print("\n=== DECADE DISTRIBUTION ===")
    for decade, count in sorted(decade_counts.items()):
        print(f"{decade:10s}: {count:3d} records")
    
    print("\n=== HALF-DECADE DISTRIBUTION ===")
    sorted_halves = sorted(half_decade_counts.items(), 
                          key=lambda x: int(x[0].split('-')[0]))
    for half_decade, count in sorted_halves:
        print(f"{half_decade}: {count:3d} records")

if __name__ == '__main__':
    main()
