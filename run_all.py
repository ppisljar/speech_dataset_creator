#!/usr/bin/env python3
"""
Script to process all audio files in a project's raw directory.

This script will automatically find all audio files in the specified project's
raw directory and process them through the complete pipeline.

Usage:
    python run_all.py <project_name> [--override] [--segment] [--validate] [--clean] [--meta] [--copy] [--skip]

Arguments:
    project_name: Name of the project to process
    --override: Override existing output files (optional)
    --segment: Enable segmentation (optional)
    --validate: Run validation on the project's segments (optional)
    --clean: Remove files that fail validation (can be used alone if bad_segments.json exists) (optional)
    --meta: Generate metadata file for the project after processing segments (optional)
    --copy: Copy all good segments to project/audio folder with organized speaker subfolders and renumbered clips (optional)
    --skip: Skip processing split files if split audio and silence files exist but transcription doesn't (optional)

Examples:
    python run_all.py my_project
    python run_all.py my_project --override
    python run_all.py my_project --segment --override
    python run_all.py my_project --validate
    python run_all.py my_project --validate --clean
    python run_all.py my_project --clean
    python run_all.py my_project --segment --meta
    python run_all.py my_project --validate --copy
    python run_all.py my_project --copy
    python run_all.py my_project --skip
"""

import os

os.environ['NUMBER_THREADS'] = '32'  # Set to 1 to avoid parallel processing issues

import sys
import argparse
import json
from pathlib import Path
from run import process_file
from m7_validate import validate_project, copy_good_segments_to_project_audio
from m8_meta import generate_metadata
from progress_manager import ProgressManager

def main():
    """Main function to process all files in a project."""
    parser = argparse.ArgumentParser(description="Process all audio files in a project's raw directory.")
    parser.add_argument("project_name", type=str, help="Name of the project to process")
    parser.add_argument("--override", action="store_true", help="Override existing output files")
    parser.add_argument("--segment", action="store_true", help="Enable segmentation")
    parser.add_argument("--validate", action="store_true", help="Run validation on the project's segments")
    parser.add_argument("--clean", action="store_true", help="Remove files that fail validation (can be used alone if bad_segments.json exists)")
    parser.add_argument("--meta", action="store_true", help="Generate metadata file for the project after processing segments")
    parser.add_argument("--copy", action="store_true", help="Copy all good segments to project/audio folder with organized speaker subfolders and renumbered clips")
    parser.add_argument("--skip", action="store_true", help="Skip processing split files if split audio and silence files exist but transcription doesn't")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum number of parallel workers for validation (default: 4)")
    
    args = parser.parse_args()
   
    
    # Base directory for projects
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
    project_dir = os.path.join(projects_dir, args.project_name)
    raw_dir = os.path.join(project_dir, 'raw')
    splits_dir = os.path.join(project_dir, 'splits')
    audio_dir = os.path.join(project_dir, 'audio')
    
    # Check if project exists
    if not os.path.exists(project_dir):
        print(f"Error: Project '{args.project_name}' does not exist.")
        print(f"Available projects: {', '.join(os.listdir(projects_dir)) if os.path.exists(projects_dir) else 'None'}")
        sys.exit(1)
    
    # Load project settings
    settings_file = os.path.join(project_dir, 'settings.json')
    settings = {}
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            print(f"Loaded settings from {settings_file}")
        except json.JSONDecodeError as e:
            print(f"Warning: Error parsing settings.json: {e}")
            print("Using default settings")
        except Exception as e:
            print(f"Warning: Error reading settings.json: {e}")
            print("Using default settings")
    else:
        print(f"No settings.json found in project directory, using default settings")
    
    # Check if raw directory exists
    if not os.path.exists(raw_dir):
        print(f"Error: Raw directory not found for project '{args.project_name}'.")
        sys.exit(1)
    
    # Create splits directory if it doesn't exist
    os.makedirs(splits_dir, exist_ok=True)
    
    # Find all audio files in the raw directory
    audio_extensions = ('.mp3', '.wav', '.m4a', '.flac', '.ogg')
    audio_files = []
    
    for item in sorted(os.listdir(raw_dir)):
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
    print(f"  Skip incomplete splits: {'Yes' if args.skip else 'No'}")
    print(f"  Generate metadata: {'Yes' if args.meta else 'No'}")
    print(f"  Copy good segments to audio folder: {'Yes' if args.copy else 'No'}")
    if args.validate:
        print(f"  Run validation: Yes (with {args.max_workers} parallel workers)")
        print(f"  Clean failed segments: {'Yes' if args.clean else 'No'}")
    elif args.clean:
        print(f"  Clean existing bad segments: Yes (with {args.max_workers} parallel workers)")
    
    # Show project-specific settings
    if settings:
        print(f"\nProject settings:")
        for key, value in settings.items():
            print(f"  {key}: {value}")
    print()
    
    # Calculate total steps for overall progress
    total_steps = 1  # File processing
    if args.validate or args.clean:
        total_steps += 1
    if args.copy:
        total_steps += 1
    if args.meta:
        total_steps += 1
    
    # Start the progress manager
    with ProgressManager() as pm:
        pm.init_overall_progress(total_steps, "Overall Progress")
        pm.init_file_progress(len(audio_files), "Processing Files")
        
        # Process each file
        success_count = 0
        failed_files = []
        current_step = 1
        
        pm.update_overall(0, f"Step {current_step}/{total_steps}: Processing Files")
        
        for i, filename in enumerate(audio_files, 1):
            pm.update_file(0, f"[{i}/{len(audio_files)}] Processing: {filename}")
            pm.print_log(f"[{i}/{len(audio_files)}] Processing: {filename}")
            pm.print_log("-" * 50)
            
            try:
                # File paths
                raw_file_path = os.path.join(raw_dir, filename)
                output_dir = os.path.join(splits_dir, filename)
                
                # Create output directory for this file
                os.makedirs(output_dir, exist_ok=True)
                
                # Process the file
                success = process_file(raw_file_path, output_dir, args.override, args.segment, settings, args.skip, pm)
                
                if success is not False:  # process_file returns None on success, False on failure
                    pm.print_log(f"✓ Successfully processed: {filename}")
                    success_count += 1
                else:
                    pm.print_log(f"✗ Failed to process: {filename}")
                    failed_files.append(filename)
                    
            except Exception as e:
                pm.print_log(f"✗ Error processing {filename}: {str(e)}")
                failed_files.append(filename)
            
            pm.update_file(1)
            pm.print_log("")
        
        # Update overall progress after file processing
        pm.update_overall(1)
        current_step += 1
        
        # Summary
        pm.print_log("=" * 60)
        pm.print_log("PROCESSING SUMMARY")
        pm.print_log("=" * 60)
        pm.print_log(f"Total files: {len(audio_files)}")
        pm.print_log(f"Successfully processed: {success_count}")
        pm.print_log(f"Failed: {len(failed_files)}")

        # Handle validation and/or cleaning
        if args.validate or args.clean:
            pm.update_overall(0, f"Step {current_step}/{total_steps}: Validation")
            pm.print_log("\n" + "=" * 60)
            
            if args.validate:
                pm.print_log(f"Running validation for project: {args.project_name}")
                if args.clean:
                    pm.print_log("Files that fail validation will be removed.")
                pm.print_log("=" * 60)
                
                # Run validation with clean option if specified
                validation_results = validate_project(args.project_name, delete_bad=args.clean, score_threshold=85, force_revalidate=True, progress_manager=pm, max_workers=args.max_workers)
                
                if validation_results:
                    pm.print_log("\nValidation completed successfully!")
                else:
                    pm.print_log("\nValidation failed or no segments found to validate.")
                    pm.stop()
                    sys.exit(1)
                    
            elif args.clean:
                pm.print_log(f"Cleaning existing bad segments for project: {args.project_name}")
                pm.print_log("=" * 60)
                
                # Use validate_project with delete_bad=True and force_revalidate=False to clean existing bad segments
                validation_results = validate_project(args.project_name, delete_bad=True, score_threshold=85, force_revalidate=False, progress_manager=pm, max_workers=args.max_workers)
                
                if validation_results:
                    pm.print_log("\nCleaning completed successfully!")
                else:
                    pm.print_log("\nNo bad segments found to clean or cleaning failed.")
                    pm.stop()
                    sys.exit(1)
            
            pm.update_overall(1)
            current_step += 1
        
        # Handle copying good segments if requested
        if args.copy:
            pm.update_overall(0, f"Step {current_step}/{total_steps}: Copying Segments")
            pm.print_log("\n" + "=" * 60)
            pm.print_log(f"Copying good segments to project/audio folder for project: {args.project_name}")
            pm.print_log("=" * 60)
            
            try:
                copy_stats = copy_good_segments_to_project_audio(args.project_name)
                if copy_stats:
                    pm.print_log("\nCopy operation completed successfully!")
                else:
                    pm.print_log("\nCopy operation failed or no segments to copy.")
            except Exception as e:
                pm.print_log(f"\nError during copy operation: {str(e)}")
                pm.stop()
                sys.exit(1)
            
            pm.update_overall(1)
            current_step += 1
            
        # Generate metadata if requested
        if args.meta:
            pm.update_overall(0, f"Step {current_step}/{total_steps}: Generating Metadata")
            pm.print_log("\n" + "=" * 60)
            pm.print_log(f"Generating metadata for project: {args.project_name}")
            pm.print_log("=" * 60)
            
            try:
                metadata_file = os.path.join(audio_dir, "metadata.csv")
                generate_metadata(project_dir, metadata_file)
                pm.print_log(f"✓ Metadata file generated: {metadata_file}")
            except Exception as e:
                pm.print_log(f"✗ Error generating metadata: {str(e)}")
            
            pm.update_overall(1)
        
        # Final summary
        if failed_files:
            pm.print_log(f"\nFailed files:")
            for filename in failed_files:
                pm.print_log(f"  - {filename}")
            pm.stop()
            sys.exit(1)
        else:
            pm.print_log(f"\nAll files processed successfully!")
            pm.print_log(f"Output directory: {splits_dir}")


if __name__ == "__main__":
    main()
