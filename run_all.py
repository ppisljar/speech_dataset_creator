#!/usr/bin/env python3
"""
Script to process all audio files in a project's raw directory.

This script will automatically find all audio files in the specified project's
raw directory and process them through the complete pipeline.

Usage:
    python run_all.py <project_name> [--override] [--segment]

Arguments:
    project_name: Name of the project to process
    --override: Override existing output files (optional)
    --segment: Enable segmentation (optional)

Examples:
    python run_all.py my_project
    python run_all.py my_project --override
    python run_all.py my_project --segment --override
"""

import os
import sys
import argparse
from pathlib import Path
from run import process_file

def main():
    """Main function to process all files in a project."""
    parser = argparse.ArgumentParser(description="Process all audio files in a project's raw directory.")
    parser.add_argument("project_name", type=str, help="Name of the project to process")
    parser.add_argument("--override", action="store_true", help="Override existing output files")
    parser.add_argument("--segment", action="store_true", help="Enable segmentation")
    
    args = parser.parse_args()
    
    # Base directory for projects
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
    project_dir = os.path.join(projects_dir, args.project_name)
    raw_dir = os.path.join(project_dir, 'raw')
    splits_dir = os.path.join(project_dir, 'splits')
    
    # Check if project exists
    if not os.path.exists(project_dir):
        print(f"Error: Project '{args.project_name}' does not exist.")
        print(f"Available projects: {', '.join(os.listdir(projects_dir)) if os.path.exists(projects_dir) else 'None'}")
        sys.exit(1)
    
    # Check if raw directory exists
    if not os.path.exists(raw_dir):
        print(f"Error: Raw directory not found for project '{args.project_name}'.")
        sys.exit(1)
    
    # Create splits directory if it doesn't exist
    os.makedirs(splits_dir, exist_ok=True)
    
    # Find all audio files in the raw directory
    audio_extensions = ('.mp3', '.wav', '.m4a', '.flac', '.ogg')
    audio_files = []
    
    for item in os.listdir(raw_dir):
        if item.lower().endswith(audio_extensions):
            audio_files.append(item)
    
    if not audio_files:
        print(f"No audio files found in {raw_dir}")
        print(f"Supported formats: {', '.join(audio_extensions)}")
        sys.exit(1)
    
    print(f"Found {len(audio_files)} audio files in project '{args.project_name}':")
    for i, filename in enumerate(audio_files, 1):
        print(f"  {i}. {filename}")
    
    print(f"\nProcessing settings:")
    print(f"  Override existing files: {'Yes' if args.override else 'No'}")
    print(f"  Enable segmentation: {'Yes' if args.segment else 'No'}")
    print()
    
    # Process each file
    success_count = 0
    failed_files = []
    
    for i, filename in enumerate(audio_files, 1):
        print(f"[{i}/{len(audio_files)}] Processing: {filename}")
        print("-" * 50)
        
        try:
            # File paths
            raw_file_path = os.path.join(raw_dir, filename)
            output_dir = os.path.join(splits_dir, filename)
            
            # Create output directory for this file
            os.makedirs(output_dir, exist_ok=True)
            
            # Process the file
            success = process_file(raw_file_path, output_dir, args.override, args.segment)
            
            if success is not False:  # process_file returns None on success, False on failure
                print(f"✓ Successfully processed: {filename}")
                success_count += 1
            else:
                print(f"✗ Failed to process: {filename}")
                failed_files.append(filename)
                
        except Exception as e:
            print(f"✗ Error processing {filename}: {str(e)}")
            failed_files.append(filename)
        
        print()
    
    # Summary
    print("=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total files: {len(audio_files)}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed: {len(failed_files)}")
    
    if failed_files:
        print(f"\nFailed files:")
        for filename in failed_files:
            print(f"  - {filename}")
        sys.exit(1)
    else:
        print(f"\nAll files processed successfully!")
        print(f"Output directory: {splits_dir}")


if __name__ == "__main__":
    main()
