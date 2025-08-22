#!/usr/bin/env python3
"""
Test the new progress manager to see how it looks.
"""

import time
from progress_manager import ProgressManager

def main():
    # Test the progress manager with context manager
    with ProgressManager() as pm:
        # Initialize different progress bars
        pm.init_overall_progress(5, "Overall Test Progress")
        pm.init_file_progress(3, "Processing Files")
        pm.init_split_progress(10, "Processing Splits")
        pm.init_step_progress(4, "Current Steps")
        
        pm.print_log("Starting test run...")
        
        for i in range(5):
            pm.update_overall(0, f"Overall step {i+1}/5")
            pm.print_log(f"Working on overall step {i+1}")
            
            for j in range(3):
                pm.update_file(0, f"File {j+1}/3")
                pm.print_log(f"Processing file {j+1}")
                
                for k in range(10):
                    pm.update_split(0, f"Split {k+1}/10")
                    time.sleep(0.1)
                    pm.update_split(1)
                    
                pm.update_file(1)
                pm.set_split_complete(0, "Splits completed")
                
            pm.update_overall(1)
            pm.set_file_complete(0, "Files completed")
            
        pm.print_log("Test completed successfully!")
        time.sleep(2)  # Let user see final state

if __name__ == "__main__":
    main()
