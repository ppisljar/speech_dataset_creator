#!/usr/bin/env python3
"""
Convert existing 3D-Speaker CSV files to the standard format

This script finds all 3D-Speaker diarization CSV files in project directories
and converts them to match the format used by pyannote and wespeaker.

The standard format includes columns: speaker, start, end, duration
All times are in seconds with 3 decimal places precision.

Usage:
    python m5_3dspeaker_convert.py [--projects_dir projects] [--dry_run]
"""

import os
import sys
import argparse
import pandas as pd
import glob
from pathlib import Path


def convert_3dspeaker_csv(input_file, output_file=None, dry_run=False):
    """
    Convert a 3D-Speaker CSV file to the standard format.
    
    Args:
        input_file (str): Path to input 3D-Speaker CSV file
        output_file (str): Path to output CSV file (default: overwrite input)
        dry_run (bool): If True, only show what would be done
        
    Returns:
        bool: True if conversion was successful
    """
    try:
        df = pd.read_csv(input_file)
        
        # Identify column mappings
        columns = df.columns.str.lower()
        column_mapping = {}
        
        # Find speaker column
        speaker_cols = [col for col in df.columns if 'speaker' in col.lower()]
        if speaker_cols:
            column_mapping['speaker'] = speaker_cols[0]
        else:
            print(f"Warning: No speaker column found in {input_file}")
            return False
        
        # Find time columns
        start_cols = [col for col in df.columns if col.lower() in ['start', 'start_time', 'begin']]
        end_cols = [col for col in df.columns if col.lower() in ['end', 'end_time', 'stop']]
        duration_cols = [col for col in df.columns if col.lower() in ['duration', 'length']]
        
        if start_cols:
            column_mapping['start'] = start_cols[0]
        else:
            print(f"Warning: No start time column found in {input_file}")
            return False
            
        if end_cols:
            column_mapping['end'] = end_cols[0]
        elif duration_cols and start_cols:
            # Calculate end from start + duration
            print(f"Calculating end time from start + duration in {input_file}")
            df['end'] = df[start_cols[0]] + df[duration_cols[0]]
            column_mapping['end'] = 'end'
        else:
            print(f"Warning: No end time column found in {input_file}")
            return False
        
        # Create standardized dataframe
        new_df = pd.DataFrame()
        
        # Map speaker column and standardize format
        speaker_col = column_mapping['speaker']
        new_df['speaker'] = df[speaker_col].astype(str)
        
        # Convert SPEAKER_XX format to spk_XX format for consistency
        new_df['speaker'] = new_df['speaker'].str.replace('SPEAKER_', 'spk_', regex=False)
        
        # Ensure speaker names are in spk_XX format
        for idx, speaker in new_df['speaker'].items():
            if not speaker.startswith('spk_'):
                # Try to extract number from various formats
                import re
                match = re.search(r'(\d+)', speaker)
                if match:
                    new_df.loc[idx, 'speaker'] = f"spk_{match.group(1)}"
                else:
                    new_df.loc[idx, 'speaker'] = f"spk_{speaker}"
        
        # Map time columns and ensure proper precision
        new_df['start'] = pd.to_numeric(df[column_mapping['start']], errors='coerce').round(3)
        new_df['end'] = pd.to_numeric(df[column_mapping['end']], errors='coerce').round(3)
        
        # Calculate duration
        new_df['duration'] = (new_df['end'] - new_df['start']).round(3)
        
        # Remove invalid rows
        initial_rows = len(new_df)
        new_df = new_df.dropna()
        new_df = new_df[new_df['duration'] > 0]
        final_rows = len(new_df)
        
        if initial_rows != final_rows:
            print(f"Removed {initial_rows - final_rows} invalid rows from {input_file}")
        
        # Sort by start time
        new_df = new_df.sort_values(['start', 'end']).reset_index(drop=True)
        
        if dry_run:
            print(f"Would convert {input_file}:")
            print(f"  Original columns: {list(df.columns)}")
            print(f"  New format: {list(new_df.columns)}")
            print(f"  Rows: {len(df)} -> {len(new_df)}")
            print(f"  Sample data:")
            print(new_df.head().to_string(index=False))
            return True
        
        # Save converted file
        if output_file is None:
            output_file = input_file
        
        new_df.to_csv(output_file, index=False)
        print(f"Converted {input_file} -> {output_file}")
        print(f"  Rows: {len(df)} -> {len(new_df)}")
        
        return True
        
    except Exception as e:
        print(f"Error converting {input_file}: {e}")
        return False


def find_3dspeaker_csvs(projects_dir):
    """
    Find all 3D-Speaker CSV files in the projects directory.
    Only searches for files with exact _3dspeaker.csv suffix.
    
    Args:
        projects_dir (str): Path to projects directory
        
    Returns:
        list: List of CSV file paths from 3D-Speaker
    """
    csv_files = []
    
    # Only search for files with exact _3dspeaker.csv suffix to avoid false positives
    csv_files = glob.glob(os.path.join(projects_dir, '**/*_3dspeaker.csv'), recursive=True)
    
    # Remove duplicates and sort
    csv_files = sorted(list(set(csv_files)))
    
    return csv_files


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description='Convert existing 3D-Speaker CSV files to standard format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert all 3D-Speaker CSV files in projects directory
    python m5_3dspeaker_convert.py
    
    # Dry run to see what would be converted
    python m5_3dspeaker_convert.py --dry_run
    
    # Convert files in a specific directory
    python m5_3dspeaker_convert.py --projects_dir /path/to/projects
    
    # Convert a specific file
    python m5_3dspeaker_convert.py --file input.csv --output output.csv
        """
    )
    
    parser.add_argument('--projects_dir', default='projects', 
                       help='Directory containing project folders (default: projects)')
    parser.add_argument('--file', help='Convert a specific CSV file')
    parser.add_argument('--output', help='Output file path (for --file option)')
    parser.add_argument('--dry_run', action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if args.file:
        # Convert a specific file
        if not os.path.exists(args.file):
            print(f"Error: File {args.file} does not exist")
            sys.exit(1)
        
        success = convert_3dspeaker_csv(args.file, args.output, args.dry_run)
        if not success:
            sys.exit(1)
    else:
        # Find and convert all 3D-Speaker CSV files
        if not os.path.exists(args.projects_dir):
            print(f"Error: Projects directory {args.projects_dir} does not exist")
            sys.exit(1)
        
        print(f"Searching for 3D-Speaker CSV files in {args.projects_dir}...")
        csv_files = find_3dspeaker_csvs(args.projects_dir)
        
        if not csv_files:
            print("No 3D-Speaker CSV files found")
            return
        
        print(f"Found {len(csv_files)} potential 3D-Speaker CSV files:")
        for csv_file in csv_files:
            print(f"  {csv_file}")
        
        if args.dry_run:
            print("\nDry run mode - showing what would be converted:")
        
        converted = 0
        failed = 0
        
        for csv_file in csv_files:
            if convert_3dspeaker_csv(csv_file, dry_run=args.dry_run):
                converted += 1
            else:
                failed += 1
        
        if args.dry_run:
            print(f"\nWould convert {converted} files, {failed} files would fail")
        else:
            print(f"\nConverted {converted} files successfully, {failed} files failed")


if __name__ == "__main__":
    main()
