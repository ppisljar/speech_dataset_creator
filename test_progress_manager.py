#!/usr/bin/env python3
"""
Test script to demonstrate the progress manager functionality.
"""

import time
import os
from progress_manager import ProgressManager

def simulate_processing():
    """Simulate the processing workflow with progress tracking."""
    
    # Simulate finding files to process
    files = ["file1.mp3", "file2.wav", "file3.m4a"]
    steps = ["process files", "validate", "generate metadata"]
    
    with ProgressManager() as pm:
        # Initialize overall progress
        pm.init_overall_progress(len(steps), "Overall Processing")
        
        # Step 1: Process Files
        pm.update_overall(0, f"Step 1/{len(steps)}: Processing Files")
        pm.init_file_progress(len(files), "Processing Audio Files")
        
        for i, filename in enumerate(files):
            pm.update_file(0, f"[{i+1}/{len(files)}] Processing: {filename}")
            pm.print_log(f"[{i+1}/{len(files)}] Processing: {filename}")
            
            # Simulate splits for this file
            splits = ["split_1.wav", "split_2.wav", "split_3.wav"]
            pm.init_split_progress(len(splits), "Processing Splits")
            
            for j, split in enumerate(splits):
                pm.update_split(0, f"Processing split {j+1}: {split}")
                pm.print_log(f"  Processing split file: {split}")
                
                # Simulate processing steps for this split
                processing_steps = ["cleaning", "transcription", "speaker detection", "segmentation"]
                pm.init_step_progress(len(processing_steps), "Processing Steps")
                
                for k, step in enumerate(processing_steps):
                    pm.update_step(0, f"Step {k+1}: {step}")
                    pm.print_log(f"    {step.capitalize()} {split}")
                    time.sleep(0.5)  # Simulate work
                    pm.update_step(1)
                
                pm.update_split(1)
                pm.print_log(f"  ✓ Completed split: {split}")
            
            pm.update_file(1)
            pm.print_log(f"✓ Successfully processed: {filename}")
            pm.print_log("")
            
        pm.update_overall(1)
        
        # Step 2: Validation
        pm.update_overall(0, f"Step 2/{len(steps)}: Validation")
        pm.print_log("\n" + "=" * 60)
        pm.print_log("VALIDATION PHASE")
        pm.print_log("=" * 60)
        
        # Simulate validation of multiple speakers
        speakers = ["speaker_01", "speaker_02", "speaker_03"]
        pm.init_step_progress(len(speakers), "Validating Speakers")
        
        for i, speaker in enumerate(speakers):
            pm.update_step(0, f"Validating speaker {i+1}/{len(speakers)}: {speaker}")
            pm.print_log(f"Validating speaker: {speaker}")
            
            # Simulate validating segments for this speaker
            for segment_num in range(5):
                pm.print_log(f"  Validating segment {segment_num + 1}/5")
                time.sleep(0.3)
            
            pm.print_log(f"  ✓ Speaker {speaker} validation complete")
            pm.update_step(1)
        
        pm.update_overall(1)
        
        # Step 3: Generate Metadata
        pm.update_overall(0, f"Step 3/{len(steps)}: Generating Metadata")
        pm.print_log("\n" + "=" * 60)
        pm.print_log("METADATA GENERATION")
        pm.print_log("=" * 60)
        
        pm.print_log("Generating metadata file...")
        time.sleep(1)
        pm.print_log("✓ Metadata file generated: metadata.csv")
        
        pm.update_overall(1)
        
        # Final summary
        pm.print_log("\n" + "=" * 60)
        pm.print_log("PROCESSING COMPLETE")
        pm.print_log("=" * 60)
        pm.print_log(f"Total files processed: {len(files)}")
        pm.print_log(f"All files processed successfully!")

if __name__ == "__main__":
    print("Testing Progress Manager...")
    print("This demonstrates the multiple progress bars that will be used in run_all.py")
    print()
    simulate_processing()