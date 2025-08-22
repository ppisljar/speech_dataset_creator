#!/usr/bin/env python3
"""
Calculate total audio length for each speaker in a project.

This script analyzes the audio files in projects/<project_name>/audio/ directory
and calculates the total duration for each speaker.

Usage:
    python m11_stats.py <project_name>

Output format: hours:minutes:seconds
"""

import argparse
import os
import sys
from pathlib import Path
import librosa
from collections import defaultdict


def format_duration(total_seconds):
    """
    Convert total seconds to hours:minutes:seconds format.
    
    Args:
        total_seconds (float): Total duration in seconds.
        
    Returns:
        str: Formatted duration string (HH:MM:SS).
    """
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_audio_duration(audio_path):
    """
    Get the duration of an audio file using librosa.
    
    Args:
        audio_path (str): Path to the audio file.
        
    Returns:
        float: Duration in seconds. Returns 0 if file cannot be read.
    """
    try:
        duration = librosa.get_duration(filename=audio_path)
        return duration
    except Exception as e:
        print(f"Warning: Could not read audio file {audio_path}: {e}")
        return 0.0


def calculate_speaker_stats(project_name):
    """
    Calculate total audio length for each speaker in a project.
    
    Args:
        project_name (str): Name of the project.
        
    Returns:
        dict: Dictionary with speaker names as keys and durations as values.
    """
    # Try the main structure first: projects/<project_name>/audio/
    project_audio_dir = os.path.join('projects', project_name, 'audio')
    
    if not os.path.exists(project_audio_dir):
        print(f"Project audio directory not found: {project_audio_dir}")
        
        # Fallback: Try the splits structure for direct speaker folders
        project_splits_dir = os.path.join('projects', project_name, 'splits')
        
        if os.path.exists(project_splits_dir):
            print(f"Checking splits directory: {project_splits_dir}")
            speaker_folders = []
            
            # Walk through splits directory to find all speakers folders
            for root, dirs, files in os.walk(project_splits_dir):
                if 'speakers' in dirs:
                    speakers_dir = os.path.join(root, 'speakers')
                    # Find all speaker ID folders within speakers directory
                    for speaker_id in os.listdir(speakers_dir):
                        speaker_path = os.path.join(speakers_dir, speaker_id)
                        if os.path.isdir(speaker_path):
                            speaker_folders.append((speaker_id, speaker_path))
        else:
            print(f"No valid project structure found for: {project_name}")
            return {}
    else:
        # Find all speaker folders in the audio directory
        speaker_folders = []
        for item in os.listdir(project_audio_dir):
            item_path = os.path.join(project_audio_dir, item)
            if os.path.isdir(item_path):
                speaker_folders.append((item, item_path))
    
    if not speaker_folders:
        print(f"No speaker folders found in project: {project_name}")
        return {}
    
    print(f"Found {len(speaker_folders)} speaker folders in project '{project_name}':")
    
    speaker_stats = {}
    total_files_processed = 0
    
    for speaker_name, speaker_folder in speaker_folders:
        print(f"  Processing speaker: {speaker_name}")
        
        # Find all .wav files in the speaker folder
        wav_files = []
        for root, dirs, files in os.walk(speaker_folder):
            for file in files:
                if file.endswith('.wav'):
                    wav_files.append(os.path.join(root, file))
        
        if not wav_files:
            print(f"    No .wav files found in speaker folder: {speaker_folder}")
            speaker_stats[speaker_name] = 0.0
            continue
        
        print(f"    Found {len(wav_files)} audio files")
        
        # Calculate total duration for this speaker
        total_duration = 0.0
        files_processed = 0
        
        # Process files in batches for efficiency with thousands of files
        batch_size = 100
        for i in range(0, len(wav_files), batch_size):
            batch = wav_files[i:i+batch_size]
            
            for wav_file in batch:
                duration = get_audio_duration(wav_file)
                total_duration += duration
                files_processed += 1
            
            # Show progress for large numbers of files
            if len(wav_files) > 500:
                progress = min(i + batch_size, len(wav_files))
                print(f"    Progress: {progress}/{len(wav_files)} files processed")
        
        speaker_stats[speaker_name] = total_duration
        total_files_processed += files_processed
        
        print(f"    Speaker {speaker_name}: {format_duration(total_duration)} ({files_processed} files)")
    
    print(f"\nTotal files processed: {total_files_processed}")
    return speaker_stats


def print_speaker_stats(speaker_stats, project_name):
    """
    Print speaker statistics in a formatted table.
    
    Args:
        speaker_stats (dict): Dictionary with speaker names and durations.
        project_name (str): Name of the project.
    """
    if not speaker_stats:
        print(f"No speaker statistics available for project: {project_name}")
        return
    
    print(f"\n=== Audio Duration Statistics for Project: {project_name} ===")
    print(f"{'Speaker':<20} {'Duration (H:M:S)':<15} {'Duration (seconds)':<18}")
    print("-" * 55)
    
    # Sort speakers by name for consistent output
    sorted_speakers = sorted(speaker_stats.items())
    total_duration = 0.0
    
    for speaker_name, duration in sorted_speakers:
        total_duration += duration
        print(f"{speaker_name:<20} {format_duration(duration):<15} {duration:<18.2f}")
    
    print("-" * 55)
    print(f"{'TOTAL':<20} {format_duration(total_duration):<15} {total_duration:<18.2f}")
    print(f"\nTotal speakers: {len(speaker_stats)}")


def main():
    """Main entry point of the script."""
    parser = argparse.ArgumentParser(description='Calculate total audio length for each speaker in a project')
    parser.add_argument('project_name', help='Name of the project to analyze')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file to save statistics (optional)')
    
    args = parser.parse_args()
    
    # Check if project directory exists
    project_dir = os.path.join('projects', args.project_name)
    if not os.path.exists(project_dir):
        print(f"Project directory not found: {project_dir}")
        print("Available projects:")
        projects_root = 'projects'
        if os.path.exists(projects_root):
            for item in os.listdir(projects_root):
                item_path = os.path.join(projects_root, item)
                if os.path.isdir(item_path):
                    print(f"  - {item}")
        else:
            print("  No projects directory found")
        sys.exit(1)
    
    print(f"Analyzing project: {args.project_name}")
    
    # Calculate speaker statistics
    speaker_stats = calculate_speaker_stats(args.project_name)
    
    # Print results
    print_speaker_stats(speaker_stats, args.project_name)
    
    # Save to file if requested
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(f"Audio Duration Statistics for Project: {args.project_name}\n")
                f.write(f"{'Speaker':<20} {'Duration (H:M:S)':<15} {'Duration (seconds)':<18}\n")
                f.write("-" * 55 + "\n")
                
                sorted_speakers = sorted(speaker_stats.items())
                total_duration = 0.0
                
                for speaker_name, duration in sorted_speakers:
                    total_duration += duration
                    f.write(f"{speaker_name:<20} {format_duration(duration):<15} {duration:<18.2f}\n")
                
                f.write("-" * 55 + "\n")
                f.write(f"{'TOTAL':<20} {format_duration(total_duration):<15} {total_duration:<18.2f}\n")
                f.write(f"\nTotal speakers: {len(speaker_stats)}\n")
            
            print(f"\nStatistics saved to: {args.output}")
        except Exception as e:
            print(f"Error saving statistics to {args.output}: {e}")


if __name__ == "__main__":
    main()
