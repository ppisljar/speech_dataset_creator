#!/usr/bin/env python3
"""
Slow demo version to show progress bars updating in real time.
"""

import time
from progress_manager import ProgressManager

def slow_demo():
    """Demonstrate the progress UI with slower updates to see the bars in action."""
    
    # Simulate files to process
    files = ["long_podcast_episode.mp3", "interview_recording.wav"]
    
    with ProgressManager() as pm:
        # Initialize overall progress (4 major steps)
        pm.init_overall_progress(4, "Overall Processing Pipeline")
        
        # Step 1: File Processing
        pm.update_overall(0, "Step 1/4: Processing Audio Files")
        pm.init_file_progress(len(files), "Processing Audio Files")
        
        for i, filename in enumerate(files):
            pm.update_file(0, f"[{i+1}/{len(files)}] Processing: {filename}")
            pm.print_log(f"Starting processing of {filename}")
            
            # Each file has multiple splits
            splits = [f"split_{j+1}.wav" for j in range(4)]
            pm.init_split_progress(len(splits), "Processing Audio Splits")
            
            for j, split in enumerate(splits):
                pm.update_split(0, f"Split {j+1}/{len(splits)}: {split}")
                pm.print_log(f"  Processing split: {split}")
                
                # Each split has processing steps
                steps = ["Audio Cleaning", "Silence Detection", "Transcription", "Speaker Diarization", "Segmentation"]
                pm.init_step_progress(len(steps), "Processing Steps")
                
                for k, step in enumerate(steps):
                    pm.update_step(0, f"Step {k+1}/{len(steps)}: {step}")
                    pm.print_log(f"    {step}...")
                    time.sleep(1.2)  # Slow enough to see progress
                    pm.update_step(1)
                
                pm.print_log(f"  ✓ Completed split: {split}")
                pm.update_split(1)
                time.sleep(0.5)
            
            pm.print_log(f"✓ Successfully processed: {filename}")
            pm.update_file(1)
            time.sleep(0.5)
        
        pm.update_overall(1)
        time.sleep(0.5)
        
        # Step 2: Validation
        pm.update_overall(0, "Step 2/4: Validating Transcriptions")
        pm.print_log("\n" + "=" * 60)
        pm.print_log("VALIDATION PHASE")
        pm.print_log("=" * 60)
        
        speakers = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]
        pm.init_step_progress(len(speakers), "Validating Speaker Segments")
        
        for i, speaker in enumerate(speakers):
            pm.update_step(0, f"Validating {i+1}/{len(speakers)}: {speaker}")
            pm.print_log(f"Validating speaker: {speaker}")
            
            # Simulate checking multiple segments
            for seg in range(8):
                pm.print_log(f"  Checking segment {seg+1}/8...")
                time.sleep(0.3)
            
            pm.print_log(f"  ✓ {speaker} validation complete")
            pm.update_step(1)
            time.sleep(0.3)
        
        pm.update_overall(1)
        time.sleep(0.5)
        
        # Step 3: Copy Operation
        pm.update_overall(0, "Step 3/4: Copying Good Segments")
        pm.print_log("\n" + "=" * 60)
        pm.print_log("COPYING SEGMENTS")
        pm.print_log("=" * 60)
        
        pm.print_log("Organizing segments by speaker...")
        time.sleep(1)
        pm.print_log("Copying audio files...")
        time.sleep(1.5)
        pm.print_log("Copying transcription files...")
        time.sleep(1)
        pm.print_log("✓ Copy operation completed!")
        
        pm.update_overall(1)
        time.sleep(0.5)
        
        # Step 4: Metadata Generation
        pm.update_overall(0, "Step 4/4: Generating Metadata")
        pm.print_log("\n" + "=" * 60)
        pm.print_log("METADATA GENERATION")
        pm.print_log("=" * 60)
        
        pm.print_log("Scanning audio files...")
        time.sleep(1)
        pm.print_log("Calculating statistics...")
        time.sleep(1)
        pm.print_log("Writing metadata.csv...")
        time.sleep(1)
        pm.print_log("✓ Metadata generation complete!")
        
        pm.update_overall(1)
        
        # Final summary
        pm.print_log("\n" + "=" * 60)
        pm.print_log("🎉 PROCESSING COMPLETE! 🎉")
        pm.print_log("=" * 60)
        pm.print_log("All audio files have been successfully processed!")
        pm.print_log("Ready for text-to-speech training!")
        
        time.sleep(2)  # Let user see final state

if __name__ == "__main__":
    print("Starting speech dataset processing...")
    print("This demo shows the multi-level progress tracking system.")
    print()
    slow_demo()