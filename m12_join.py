#!/usr/bin/env python3
"""
Module 12: Join Speaker Folders

This module allows joining speaker folders in the audio/ directory of a project.
Can either list all speakers with their clip counts or join specified speakers into the first speaker folder.

Usage:
    python m12_join.py <project_name>                              # List all speakers
    python m12_join.py <project_name> --join speaker_00,speaker_01 # Join specific speakers into first one
    python m12_join.py <project_name> --all                       # Join all speakers into first one
    python m12_join.py <project_name> --all --override            # Join all speakers, skip confirmation

Arguments:
    project_name: Name of the project
    --join: Comma-separated list of speaker IDs to join (first one becomes the target)
    --all: Join all speakers in the project into the first one (alphabetically)
    --override: Skip confirmation prompt

Examples:
    python m12_join.py my_project
    python m12_join.py my_project --join speaker_00,speaker_01
    python m12_join.py my_project --join speaker_00,speaker_01,speaker_03 --override
    python m12_join.py my_project --all
    python m12_join.py my_project --all --override
"""

import os
import sys
import argparse
import json
import shutil
from pathlib import Path


def list_speakers(project_name):
    """
    List all speaker folders and their clip counts for a project.
    
    Args:
        project_name (str): Name of the project
        
    Returns:
        dict: Dictionary with speaker IDs as keys and clip counts as values
    """
    # Base directory for projects
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
    project_dir = os.path.join(projects_dir, project_name)
    audio_dir = os.path.join(project_dir, 'audio')
    
    # Check if project exists
    if not os.path.exists(project_dir):
        print(f"Error: Project '{project_name}' does not exist.")
        available_projects = []
        if os.path.exists(projects_dir):
            available_projects = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
        print(f"Available projects: {', '.join(available_projects) if available_projects else 'None'}")
        return {}
    
    # Check if audio directory exists
    if not os.path.exists(audio_dir):
        print(f"Error: Audio directory not found for project '{project_name}'.")
        print(f"Expected: {audio_dir}")
        return {}
    
    # Find all speaker folders
    speaker_info = {}
    
    for item in os.listdir(audio_dir):
        item_path = os.path.join(audio_dir, item)
        if os.path.isdir(item_path) and item.startswith('speaker_'):
            # Count .wav files in this speaker folder
            wav_files = [f for f in os.listdir(item_path) if f.endswith('.wav')]
            txt_files = [f for f in os.listdir(item_path) if f.endswith('.txt')]
            
            speaker_info[item] = {
                'clips': len(wav_files),
                'text_files': len(txt_files),
                'path': item_path
            }
    
    return speaker_info


def join_speakers(project_name, speaker_ids, override=False):
    """
    Join multiple speaker folders into the first speaker folder.
    Moves all files from other speakers into the first speaker and renumbers all clips.
    
    Args:
        project_name (str): Name of the project
        speaker_ids (list): List of speaker IDs to join (first one will be the target)
        override (bool): Whether to proceed without confirmation
        
    Returns:
        dict: Statistics about the join operation
    """
    # Base directory for projects
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
    project_dir = os.path.join(projects_dir, project_name)
    audio_dir = os.path.join(project_dir, 'audio')
    
    # Check if project exists
    if not os.path.exists(project_dir):
        print(f"Error: Project '{project_name}' does not exist.")
        return {}
    
    # Check if audio directory exists
    if not os.path.exists(audio_dir):
        print(f"Error: Audio directory not found for project '{project_name}'.")
        return {}
    
    # Check if we have at least 2 speakers to join
    if len(speaker_ids) < 2:
        print(f"Error: Need at least 2 speakers to join. Provided: {len(speaker_ids)}")
        return {}
    
    # Validate all speaker IDs exist
    available_speakers = list_speakers(project_name)
    missing_speakers = [sid for sid in speaker_ids if sid not in available_speakers]
    
    if missing_speakers:
        print(f"Error: Speaker(s) not found: {', '.join(missing_speakers)}")
        print(f"Available speakers: {', '.join(available_speakers.keys())}")
        return {}
    
    # The target speaker (first in the list) - this is where all files will be moved
    target_speaker = speaker_ids[0]
    source_speakers = speaker_ids[1:]  # All other speakers to be merged
    target_dir = available_speakers[target_speaker]['path']
    
    # Confirm operation if not overriding
    if not override:
        print(f"This will move all clips from {', '.join(source_speakers)} into {target_speaker}")
        print(f"The source speaker folders will be removed after moving files.")
        print(f"All clips in {target_speaker} will be renumbered.")
        response = input("Continue? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Operation cancelled.")
            return {}
    
    # Collect all segments from all speakers (including target)
    all_segments = []
    join_stats = {
        'target_speaker': target_speaker,
        'source_speakers': source_speakers,
        'clips_per_speaker': {},
        'target_folder': target_dir
    }
    
    print(f"Joining speakers into: {target_speaker}")
    print(f"Source speakers: {', '.join(source_speakers)}")
    print()
    
    # First, collect all files from all speakers
    for speaker_id in speaker_ids:
        speaker_path = available_speakers[speaker_id]['path']
        clip_count = available_speakers[speaker_id]['clips']
        
        print(f"Processing {speaker_id}: {clip_count} clips")
        
        # Find all .wav files in this speaker folder
        wav_files = [f for f in sorted(os.listdir(speaker_path)) if f.endswith('.wav')]
        
        for wav_filename in wav_files:
            src_wav = os.path.join(speaker_path, wav_filename)
            src_txt = os.path.splitext(src_wav)[0] + '.txt'
            
            if os.path.exists(src_txt):
                all_segments.append((src_wav, src_txt, speaker_id))
            else:
                print(f"  Warning: Text file not found for {wav_filename}, skipping")
        
        join_stats['clips_per_speaker'][speaker_id] = clip_count
    
    # Sort all segments for consistent numbering
    all_segments.sort(key=lambda x: (x[2], x[0]))  # Sort by speaker_id, then wav file path
    
    # Create a temporary directory to store files during renumbering
    temp_dir = os.path.join(os.path.dirname(target_dir), f"{target_speaker}_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Copy all segments to temp directory with new numbering
        clip_counter = 1
        copied_count = 0
        
        print(f"\nRenumbering and copying {len(all_segments)} segments...")
        
        for src_wav, src_txt, original_speaker in all_segments:
            try:
                # Destination paths in temp directory
                dst_wav = os.path.join(temp_dir, f"clip_{clip_counter:05d}.wav")
                dst_txt = os.path.join(temp_dir, f"clip_{clip_counter:05d}.txt")
                
                # Copy files
                shutil.copy2(src_wav, dst_wav)
                shutil.copy2(src_txt, dst_txt)
                
                copied_count += 1
                clip_counter += 1
                
                if copied_count % 100 == 0:  # Progress indicator
                    print(f"  Copied {copied_count}/{len(all_segments)} clips...")
                    
            except Exception as e:
                print(f"  Error copying {os.path.basename(src_wav)}: {e}")
                continue
        
        # Clear the target directory
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
        
        # Move all files from temp directory to target directory
        for item in os.listdir(temp_dir):
            src_path = os.path.join(temp_dir, item)
            dst_path = os.path.join(target_dir, item)
            shutil.move(src_path, dst_path)
        
        # Remove source speaker directories (but not the target)
        for speaker_id in source_speakers:
            speaker_path = available_speakers[speaker_id]['path']
            print(f"Removing source folder: {speaker_path}")
            shutil.rmtree(speaker_path)
        
        join_stats['total_clips'] = copied_count
        
        # Save join statistics in the target directory
        stats_file = os.path.join(target_dir, 'join_stats.json')
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(join_stats, f, indent=2, ensure_ascii=False)
            print(f"Join statistics saved to: {stats_file}")
        except Exception as e:
            print(f"Warning: Could not save join statistics: {e}")
        
    finally:
        # Clean up temp directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    return join_stats


def main():
    """Main function to handle command line arguments and execute operations."""
    parser = argparse.ArgumentParser(description="Join speaker folders or list speakers in a project.")
    parser.add_argument("project_name", type=str, help="Name of the project")
    parser.add_argument("--join", type=str, help="Comma-separated list of speaker IDs to join (first one becomes the target)")
    parser.add_argument("--all", action="store_true", help="Join all speakers in the project into the first one (alphabetically)")
    parser.add_argument("--override", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    # Check for mutually exclusive options
    if args.join and args.all:
        print("Error: Cannot use both --join and --all options simultaneously.")
        sys.exit(1)
    
    if args.join or args.all:
        # Join speakers mode
        if args.all:
            # Get all speakers and use them all
            speaker_info = list_speakers(args.project_name)
            if not speaker_info:
                print("No speakers found or project does not exist.")
                sys.exit(1)
            
            speaker_ids = sorted(speaker_info.keys())
            
            if len(speaker_ids) < 2:
                print(f"Error: Found only {len(speaker_ids)} speaker(s). Need at least 2 speakers to join.")
                if speaker_ids:
                    print(f"Available speaker: {speaker_ids[0]}")
                sys.exit(1)
                
            print(f"Using --all option: Found {len(speaker_ids)} speakers")
            
        else:
            # Use specified speakers from --join
            speaker_ids = [sid.strip() for sid in args.join.split(',')]
        
        # Validate speaker ID format
        invalid_ids = [sid for sid in speaker_ids if not sid.startswith('speaker_')]
        if invalid_ids:
            print(f"Error: Invalid speaker ID format: {', '.join(invalid_ids)}")
            print("Speaker IDs should be in format 'speaker_XX' (e.g., speaker_00, speaker_01)")
            sys.exit(1)
        
        # Need at least 2 speakers to join
        if len(speaker_ids) < 2:
            print("Error: Need at least 2 speakers to join.")
            sys.exit(1)
        
        print(f"Joining speakers for project: {args.project_name}")
        print(f"Target speaker (will receive all clips): {speaker_ids[0]}")
        print(f"Source speakers (will be merged and removed): {', '.join(speaker_ids[1:])}")
        print(f"Skip confirmation: {'Yes' if args.override else 'No'}")
        print()
        
        # Perform join operation
        join_stats = join_speakers(args.project_name, speaker_ids, args.override)
        
        if join_stats:
            print("\n" + "=" * 60)
            print("JOIN OPERATION SUMMARY")
            print("=" * 60)
            print(f"Project: {args.project_name}")
            print(f"Target speaker: {join_stats['target_speaker']}")
            print(f"Source speakers merged: {', '.join(join_stats['source_speakers'])}")
            print(f"Total clips in target: {join_stats['total_clips']}")
            print("\nOriginal clips per speaker:")
            for speaker_id, count in join_stats['clips_per_speaker'].items():
                print(f"  {speaker_id}: {count} clips")
            print(f"\nAll clips are now in: {join_stats['target_folder']}")
            print("Join operation completed successfully!")
        else:
            print("Join operation failed.")
            sys.exit(1)
            
    else:
        # List speakers mode
        print(f"Listing speakers for project: {args.project_name}")
        print()
        
        speaker_info = list_speakers(args.project_name)
        
        if speaker_info:
            print("=" * 60)
            print("SPEAKER INFORMATION")
            print("=" * 60)
            print(f"Project: {args.project_name}")
            print(f"Total speakers: {len(speaker_info)}")
            print()
            
            total_clips = 0
            for speaker_id in sorted(speaker_info.keys()):
                info = speaker_info[speaker_id]
                clips = info['clips']
                txt_files = info['text_files']
                total_clips += clips
                
                status = "✓" if clips == txt_files else f"⚠ (missing {clips - txt_files} text files)"
                print(f"  {speaker_id}: {clips} clips {status}")
            
            print()
            print(f"Total clips across all speakers: {total_clips}")
            
            if len(speaker_info) > 1:
                print()
                print("To join specific speakers into the first one, use:")
                example_speakers = ','.join(sorted(speaker_info.keys())[:2])
                print(f"  python m12_join.py {args.project_name} --join {example_speakers}")
                print("To join ALL speakers into the first one, use:")
                print(f"  python m12_join.py {args.project_name} --all")
                print("Note: Files from all speakers except the first will be moved into the first speaker folder.")
        else:
            print("No speakers found or project does not exist.")
            sys.exit(1)


if __name__ == "__main__":
    main()
