#!/usr/bin/env python3
"""
Simple test to understand the progress manager behavior
"""

import time
import sys
from progress_manager import ProgressManager

def test_progress_manager():
    """Test the progress manager with simulated work."""
    print("Starting progress manager test...")
    
    with ProgressManager() as pm:
        # Initialize progress bars
        pm.init_overall_progress(3, "Overall Progress")
        pm.init_file_progress(2, "Processing Files") 
        pm.init_split_progress(5, "Processing Splits")
        pm.init_step_progress(4, "Processing Steps")
        
        # Simulate overall step 1
        pm.update_overall(0, "Step 1/3: Processing Files")
        
        # Simulate processing files
        for i in range(2):
            pm.update_file(0, f"Processing file {i+1}/2")
            pm.print_log(f"Starting file {i+1}")
            
            # Simulate processing splits
            for j in range(5):
                pm.update_split(0, f"Processing split {j+1}/5")
                pm.print_log(f"  Processing split {j+1}")
                
                # Simulate processing steps
                for k in range(4):
                    pm.update_step(0, f"Step {k+1}/4")
                    pm.print_log(f"    Step {k+1}: Some operation")
                    time.sleep(0.5)  # Simulate work
                    pm.update_step(1)
                
                pm.update_split(1)
            
            pm.print_log(f"Completed file {i+1}")
            pm.update_file(1)
        
        pm.update_overall(1)
        
        # Simulate overall step 2
        pm.update_overall(0, "Step 2/3: Validation")
        pm.print_log("Running validation...")
        time.sleep(2)
        pm.update_overall(1)
        
        # Simulate overall step 3
        pm.update_overall(0, "Step 3/3: Metadata")
        pm.print_log("Generating metadata...")
        time.sleep(1)
        pm.update_overall(1)
        
        pm.print_log("All processing complete!")

if __name__ == "__main__":
    test_progress_manager()