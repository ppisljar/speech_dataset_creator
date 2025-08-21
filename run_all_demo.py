#!/usr/bin/env python3
"""
Demo version of run_all.py to showcase the progress UI functionality.
This version simulates the processing without requiring heavy dependencies.
"""

import os
import sys
import argparse
import time
import random
from progress_manager import ProgressManager

def simulate_process_file(file_path, temp_dir, override, segment, settings, skip, progress_manager):
    """Simulate processing a single file."""
    def log_print(message):
        if progress_manager:
            progress_manager.print_log(message)
        else:
            print(message)
    
    file_name = os.path.basename(file_path)
    log_print(f"Processing file: {file_name}")
    
    # Simulate cleaning
    time.sleep(0.5)
    log_print(f"Cleaning audio {file_path}")
    
    # Simulate splitting into multiple files
    split_count = random.randint(2, 5)
    splits = [f"split_{i+1}.wav" for i in range(split_count)]
    
    if progress_manager:
        progress_manager.init_split_progress(len(splits), "Processing Splits")
    
    for i, split_file in enumerate(splits):
        if progress_manager:
            progress_manager.update_split(0, f"Processing split {i+1}: {split_file}")
        
        log_print(f"Processing split file: {split_file}")
        
        # Simulate processing steps
        steps = ["silence detection", "transcription", "pyannote", "segmentation"]
        if segment:
            steps.append("generate segments")
        
        if progress_manager:
            progress_manager.init_step_progress(len(steps), "Processing Steps")
        
        for j, step in enumerate(steps):
            if progress_manager:
                progress_manager.update_step(0, f"Step {j+1}: {step}")
            log_print(f"  {step.capitalize()}")
            time.sleep(random.uniform(0.3, 0.8))
            if progress_manager:
                progress_manager.update_step(1)
        
        if progress_manager:
            progress_manager.update_split(1)
    
    # Randomly simulate success or failure
    success = random.random() > 0.1  # 90% success rate
    if not success:
        log_print(f"✗ Failed to process: {file_name}")
        return False
    else:
        log_print(f"✓ Successfully processed: {file_name}")
        return True

def simulate_validate_project(project_name, delete_bad, score_threshold, force_revalidate, progress_manager):
    """Simulate project validation."""
    def log_print(message):
        if progress_manager:
            progress_manager.print_log(message)
        else:
            print(message)
    
    # Simulate finding speaker folders
    speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    
    if progress_manager:
        progress_manager.init_step_progress(len(speakers), "Validating Speakers")
    
    for i, speaker in enumerate(speakers):
        if progress_manager:
            progress_manager.update_step(0, f"Validating speaker {i+1}/{len(speakers)}: {speaker}")
        
        log_print(f"\n--- Validating speaker: {speaker} ---")
        
        # Simulate validating segments
        segment_count = random.randint(10, 30)
        bad_segments = random.randint(0, 5)
        
        for j in range(segment_count):
            time.sleep(0.05)  # Fast simulation
            if j < bad_segments:
                log_print(f"Bad segment found: segment_{j+1}.wav (score: {random.randint(50, 84)})")
            
        log_print(f"Found {bad_segments} bad segments out of {segment_count}")
        
        if delete_bad and bad_segments > 0:
            log_print(f"Cleaning {bad_segments} bad segments for speaker: {speaker}")
        
        if progress_manager:
            progress_manager.update_step(1)
    
    return True

def simulate_copy_good_segments(project_name):
    """Simulate copying good segments."""
    time.sleep(1)
    return {"total_copied": 150, "speakers": 3}

def simulate_generate_metadata(project_dir, metadata_file):
    """Simulate metadata generation."""
    time.sleep(0.5)

def main():
    """Demo main function."""
    parser = argparse.ArgumentParser(description="Demo: Process all audio files in a project's raw directory.")
    parser.add_argument("project_name", type=str, help="Name of the project to process")
    parser.add_argument("--override", action="store_true", help="Override existing output files")
    parser.add_argument("--segment", action="store_true", help="Enable segmentation")
    parser.add_argument("--validate", action="store_true", help="Run validation on the project's segments")
    parser.add_argument("--clean", action="store_true", help="Remove files that fail validation")
    parser.add_argument("--meta", action="store_true", help="Generate metadata file for the project")
    parser.add_argument("--copy", action="store_true", help="Copy all good segments to project/audio folder")
    parser.add_argument("--skip", action="store_true", help="Skip processing split files if conditions met")
    
    args = parser.parse_args()
    
    # Simulate finding audio files
    audio_files = ["podcast_episode_1.mp3", "interview_2.wav", "speech_sample_3.m4a"]
    
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
        print(f"  Run validation: Yes")
        print(f"  Clean failed segments: {'Yes' if args.clean else 'No'}")
    elif args.clean:
        print(f"  Clean existing bad segments: Yes")
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
                # Simulate file processing
                success = simulate_process_file(f"raw/{filename}", f"splits/{filename}", 
                                              args.override, args.segment, {}, args.skip, pm)
                
                if success:
                    success_count += 1
                else:
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
                
                validation_results = simulate_validate_project(args.project_name, delete_bad=args.clean,
                                                             score_threshold=85, force_revalidate=True,
                                                             progress_manager=pm)
                
                if validation_results:
                    pm.print_log("\nValidation completed successfully!")
                else:
                    pm.print_log("\nValidation failed or no segments found to validate.")
                    
            elif args.clean:
                pm.print_log(f"Cleaning existing bad segments for project: {args.project_name}")
                pm.print_log("=" * 60)
                
                validation_results = simulate_validate_project(args.project_name, delete_bad=True,
                                                             score_threshold=85, force_revalidate=False,
                                                             progress_manager=pm)
                
                if validation_results:
                    pm.print_log("\nCleaning completed successfully!")
                else:
                    pm.print_log("\nNo bad segments found to clean or cleaning failed.")
            
            pm.update_overall(1)
            current_step += 1
        
        # Handle copying good segments if requested
        if args.copy:
            pm.update_overall(0, f"Step {current_step}/{total_steps}: Copying Segments")
            pm.print_log("\n" + "=" * 60)
            pm.print_log(f"Copying good segments to project/audio folder for project: {args.project_name}")
            pm.print_log("=" * 60)
            
            copy_stats = simulate_copy_good_segments(args.project_name)
            if copy_stats:
                pm.print_log("\nCopy operation completed successfully!")
                pm.print_log(f"Copied {copy_stats['total_copied']} segments from {copy_stats['speakers']} speakers")
            else:
                pm.print_log("\nCopy operation failed or no segments to copy.")
            
            pm.update_overall(1)
            current_step += 1
            
        # Generate metadata if requested
        if args.meta:
            pm.update_overall(0, f"Step {current_step}/{total_steps}: Generating Metadata")
            pm.print_log("\n" + "=" * 60)
            pm.print_log(f"Generating metadata for project: {args.project_name}")
            pm.print_log("=" * 60)
            
            simulate_generate_metadata("project_dir", "metadata.csv")
            pm.print_log(f"✓ Metadata file generated: metadata.csv")
            
            pm.update_overall(1)
        
        # Final summary
        if failed_files:
            pm.print_log(f"\nFailed files:")
            for filename in failed_files:
                pm.print_log(f"  - {filename}")
        else:
            pm.print_log(f"\nAll files processed successfully!")
            pm.print_log(f"Output directory: splits/")

if __name__ == "__main__":
    main()