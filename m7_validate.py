# validate speakers 

# validate text files against audio files ?

# outlier detection ?

import json
import os
import re
import difflib
import argparse
import shutil
from pathlib import Path
import librosa
import soundfile as sf
import numpy as np
from m4_transcribe_file import transcribe_file

def validate_transcription(segment_json, delete_bad=False, score_threshold=85):
    """
    Validate the segment JSON against the audio file transcriptions.
    
    Args:
        segment_json (str): Path to the segment JSON file.
        delete_bad (bool): Whether to delete bad segment files.
        score_threshold (int): Minimum score threshold (default: 85).

    Returns:
        list: List of bad segments with their scores.
    """

    # for each segment:
    # - trim anything more than 5ms of silence (complete silence) from start/end of segment (inplace)
    # - translate file using soniox (m4_transcribe_file) and check if transcription matches the transcription in the segment file. (expect segments were "build", so each segment has the audio and txt file in appropriate place)
    # --- calculate score (complete match = 100, complete mismatch = 0, if just special chars differ (comma, .!? ...) it should get score from 90-99, if text differs it should get score from 0 - 90 (depending how muchj difference))
    # - if score < 85 mark segment as bad, optionally (depending on args) delete the bad segment file and its matching .txt file
    # return list of bad segments

    if not os.path.exists(segment_json):
        print(f"Segment JSON file not found: {segment_json}")
        return []

    with open(segment_json, 'r', encoding='utf-8') as f:
        segments = json.load(f)

    bad_segments = []
    segment_dir = os.path.dirname(segment_json)
    
    for i, segment in enumerate(segments):
        try:
            # Get segment file paths
            segment_audio_file = os.path.join(segment_dir, segment['filename'])
            segment_text_file = os.path.splitext(segment_audio_file)[0] + '.txt'
            
            if not os.path.exists(segment_audio_file):
                print(f"Audio file not found: {segment_audio_file}")
                continue
                
            if not os.path.exists(segment_text_file):
                print(f"Text file not found: {segment_text_file}")
                continue

            # Read the existing transcription
            with open(segment_text_file, 'r', encoding='utf-8') as f:
                original_transcription = f.read().strip()

            # Trim silence from audio file
            trimmed_audio_file = _trim_silence(segment_audio_file)
            
            # Transcribe the trimmed audio
            try:
                new_transcription = transcribe_file(trimmed_audio_file, skip_file_output=True)
                if isinstance(new_transcription, dict) and 'transcript' in new_transcription:
                    new_transcription = new_transcription['transcript']
            except Exception as e:
                print(f"Error transcribing {trimmed_audio_file}: {e}")
                continue
            
            # Calculate similarity score
            score = _calculate_similarity_score(original_transcription, new_transcription)
            
            # Check if segment is bad
            if score < score_threshold:
                bad_segment = {
                    'index': i,
                    'filename': segment['filename'],
                    'score': score,
                    'original_transcription': original_transcription,
                    'new_transcription': new_transcription
                }
                bad_segments.append(bad_segment)
                
                print(f"Bad segment found: {segment['filename']} (score: {score})")
                print(f"  Original: '{original_transcription}'")
                print(f"  New: '{new_transcription}'")
                
                # Delete bad segment files if requested
                if delete_bad:
                    try:
                        os.remove(segment_audio_file)
                        os.remove(segment_text_file)
                        print(f"  Deleted: {segment_audio_file} and {segment_text_file}")
                    except Exception as e:
                        print(f"  Error deleting files: {e}")
            else:
                print(f"Good segment: {segment['filename']} (score: {score})")
                
            # Clean up trimmed file if it's different from original
            if trimmed_audio_file != segment_audio_file and os.path.exists(trimmed_audio_file):
                os.remove(trimmed_audio_file)
                
        except Exception as e:
            print(f"Error processing segment {i}: {e}")
            continue

    return bad_segments


def _trim_silence(audio_file, silence_threshold_db=-40, min_silence_duration=0.005):
    """
    Trim silence from the beginning and end of an audio file.
    
    Args:
        audio_file (str): Path to the audio file.
        silence_threshold_db (float): Silence threshold in dB.
        min_silence_duration (float): Minimum silence duration in seconds (5ms).
        
    Returns:
        str: Path to the trimmed audio file.
    """
    try:
        # Load audio
        audio, sr = librosa.load(audio_file, sr=None)
        
        # Convert to dB
        audio_db = librosa.amplitude_to_db(np.abs(audio))
        
        # Find non-silent regions
        non_silent = audio_db > silence_threshold_db
        
        # Find start and end of non-silent regions
        if np.any(non_silent):
            start_idx = np.argmax(non_silent)
            end_idx = len(audio) - np.argmax(non_silent[::-1]) - 1
            
            # Ensure we don't trim too aggressively (keep at least min_silence_duration)
            min_samples = int(min_silence_duration * sr)
            start_idx = max(0, start_idx - min_samples)
            end_idx = min(len(audio), end_idx + min_samples)
            
            # Trim audio
            trimmed_audio = audio[start_idx:end_idx]
            
            # If significant trimming occurred, save to a new file
            if start_idx > min_samples or end_idx < len(audio) - min_samples:
                trimmed_file = audio_file.replace('.wav', '_trimmed.wav')
                sf.write(trimmed_file, trimmed_audio, sr)
                return trimmed_file
        
        # Return original file if no significant trimming needed
        return audio_file
        
    except Exception as e:
        print(f"Error trimming silence from {audio_file}: {e}")
        return audio_file


def _calculate_similarity_score(original, new):
    """
    Calculate similarity score between two transcriptions.
    
    Args:
        original (str): Original transcription.
        new (str): New transcription.
        
    Returns:
        int: Similarity score (0-100).
    """
    if not original or not new:
        return 0
    
    # Normalize text for comparison
    def normalize_text(text):
        # Convert to lowercase
        text = text.lower().strip()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def normalize_punctuation(text):
        # Remove punctuation for content comparison
        text = re.sub(r'[^\w\s]', '', text)
        return normalize_text(text)
    
    original_norm = normalize_text(original)
    new_norm = normalize_text(new)
    
    # Check for exact match
    if original_norm == new_norm:
        return 100
    
    # Check if only punctuation differs
    original_no_punct = normalize_punctuation(original)
    new_no_punct = normalize_punctuation(new)
    
    if original_no_punct == new_no_punct:
        # Only punctuation differs, score 90-99
        punct_similarity = difflib.SequenceMatcher(None, original_norm, new_norm).ratio()
        return int(90 + (punct_similarity * 9))
    
    # Calculate text similarity using difflib
    similarity_ratio = difflib.SequenceMatcher(None, original_no_punct, new_no_punct).ratio()
    
    # Score 0-90 based on text similarity
    return int(similarity_ratio * 90)


def validate_project(project_name, delete_bad=False, score_threshold=85, force_revalidate=False, progress_manager=None):
    """
    Validate all segments in a project by looking at the generated segments folder.
    
    Args:
        project_name (str): Name of the project.
        delete_bad (bool): Whether to delete bad segment files.
        score_threshold (int): Minimum score threshold.
        force_revalidate (bool): Whether to ignore existing bad_segments.json files and revalidate.
        progress_manager: ProgressManager instance for tracking progress. Defaults to None.
        
    Returns:
        dict: Dictionary with speaker folders as keys and bad segments as values.
    """
    def log_print(message):
        """Print message using progress manager if available, otherwise regular print."""
        if progress_manager:
            progress_manager.print_log(message)
        else:
            print(message)
    
    # First try the new m6 folder structure: projects/<project_name>/splits/*/segments/speakers/
    project_splits_dir = os.path.join('projects', project_name, 'splits')
    
    # Find all speaker folders in the m6 structure
    speaker_folders = []
    
    if os.path.exists(project_splits_dir):
        log_print(f"Looking for segments in m6 structure: {project_splits_dir}")
        
        # Walk through splits directory to find all speakers folders
        for root, dirs, files in os.walk(project_splits_dir):
            dirs.sort()  # Sort directories for consistent ordering
            if 'speakers' in dirs:
                speakers_dir = os.path.join(root, 'speakers')
                # Find all speaker ID folders within speakers directory
                for speaker_id in sorted(os.listdir(speakers_dir)):
                    speaker_path = os.path.join(speakers_dir, speaker_id)
                    if os.path.isdir(speaker_path):
                        speaker_folders.append(speaker_path)
    
    # Fallback to old structure: projects/<project_name>/audio/
    if not speaker_folders:
        project_segments_dir = os.path.join('projects', project_name, 'audio')
        
        if os.path.exists(project_segments_dir):
            log_print(f"Looking for segments in legacy structure: {project_segments_dir}")
            
            # Find all speaker folders directly under audio
            for item in sorted(os.listdir(project_segments_dir)):
                item_path = os.path.join(project_segments_dir, item)
                if os.path.isdir(item_path):
                    speaker_folders.append(item_path)
    
    if not speaker_folders:
        log_print(f"No speaker folders found in project: {project_name}")
        log_print(f"Checked paths:")
        log_print(f"  - {project_splits_dir} (m6 structure)")
        log_print(f"  - {os.path.join('projects', project_name, 'audio')} (legacy structure)")
        return {}
    
    log_print(f"Found {len(speaker_folders)} speaker folders in project '{project_name}':")
    for speaker_folder in speaker_folders:
        log_print(f"  {speaker_folder}")
    
    # Project-level bad segments file
    project_bad_segments_file = os.path.join('projects', project_name, 'bad_segments.json')
    all_results = {}
    
    # Check if we should use existing project bad_segments.json file
    if not force_revalidate and os.path.exists(project_bad_segments_file):
        log_print(f"\n--- Using existing project bad segments file: {project_bad_segments_file} ---")
        try:
            with open(project_bad_segments_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Convert to the expected format if needed
            if isinstance(existing_data, dict) and 'speakers' in existing_data:
                for speaker_path, bad_segments in existing_data['speakers'].items():
                    all_results[speaker_path] = bad_segments
                log_print(f"Loaded {sum(len(segs) for segs in all_results.values())} bad segments from existing project file")
                
                # If delete_bad is True, clean the segments
                if delete_bad:
                    if progress_manager:
                        progress_manager.init_step_progress(len(speaker_folders), "Cleaning Bad Segments")
                    
                    for i, speaker_folder in enumerate(speaker_folders):
                        if progress_manager:
                            progress_manager.update_step(0, f"Cleaning speaker {i+1}/{len(speaker_folders)}")
                        
                        speaker_bad_segments = all_results.get(speaker_folder, [])
                        if speaker_bad_segments:
                            clean_bad_segments_from_speaker(speaker_folder, speaker_bad_segments, progress_manager)
                        
                        if progress_manager:
                            progress_manager.update_step(1)
                
                return all_results
                
        except Exception as e:
            log_print(f"Error reading existing project bad_segments.json: {e}")
            log_print("Proceeding with revalidation...")
    
    # Load existing bad segments data for resumption support
    existing_bad_segments_data = None
    if not force_revalidate and os.path.exists(project_bad_segments_file):
        try:
            with open(project_bad_segments_file, 'r', encoding='utf-8') as f:
                existing_bad_segments_data = json.load(f)
            log_print(f"Loaded existing validation data for resumption")
        except Exception as e:
            log_print(f"Could not load existing validation data: {e}")
    
    # Initialize the bad segments data structure if not loaded
    if existing_bad_segments_data is None:
        existing_bad_segments_data = {
            'project_name': project_name,
            'validation_timestamp': json.dumps(None),
            'total_speakers': len(speaker_folders),
            'total_bad_segments': 0,
            'progress': {'speakers': {}},
            'speakers': {}
        }
    
    # Delete existing project bad_segments.json if force_revalidate is True
    if force_revalidate and os.path.exists(project_bad_segments_file):
        try:
            os.remove(project_bad_segments_file)
            log_print(f"Deleted existing project bad_segments.json")
            # Reset the data structure for fresh validation
            existing_bad_segments_data = {
                'project_name': project_name,
                'validation_timestamp': json.dumps(None),
                'total_speakers': len(speaker_folders),
                'total_bad_segments': 0,
                'progress': {'speakers': {}},
                'speakers': {}
            }
        except Exception as e:
            log_print(f"Warning: Could not delete existing project bad_segments.json: {e}")
    
    # Initialize step progress for validation
    if progress_manager:
        progress_manager.init_step_progress(len(speaker_folders), "Validating Speakers")
    
    # Validate each speaker folder
    for i, speaker_folder in enumerate(speaker_folders):
        speaker_name = os.path.basename(speaker_folder)
        if progress_manager:
            progress_manager.update_step(0, f"Validating speaker {i+1}/{len(speaker_folders)}: {speaker_name}")
        
        log_print(f"\n--- Validating speaker: {speaker_name} ---")
        
        # Run validation with resumption support
        bad_segments = validate_speaker_segments(speaker_folder, 
                                               delete_bad=False,
                                               score_threshold=score_threshold,
                                               progress_manager=progress_manager,
                                               existing_bad_segments_data=existing_bad_segments_data)
        
        # Add speaker path to each bad segment for identification
        for bad_segment in bad_segments:
            bad_segment['speaker_folder'] = speaker_folder
            bad_segment['speaker_name'] = speaker_name
        
        all_results[speaker_folder] = bad_segments
        
        # If delete_bad is True, clean the bad segments after validation
        if delete_bad and bad_segments:
            clean_bad_segments_from_speaker(speaker_folder, bad_segments, progress_manager)
        
        if progress_manager:
            progress_manager.update_step(1)
    
    # Final update to the project data
    existing_bad_segments_data['speakers'] = all_results
    existing_bad_segments_data['total_bad_segments'] = sum(len(bad_segments) for bad_segments in all_results.values())
    
    # Save final results
    try:
        os.makedirs(os.path.dirname(project_bad_segments_file), exist_ok=True)
        with open(project_bad_segments_file, 'w', encoding='utf-8') as f:
            json.dump(existing_bad_segments_data, f, indent=2, ensure_ascii=False)
        log_print(f"\nProject bad segments saved to: {project_bad_segments_file}")
    except Exception as e:
        log_print(f"Error saving project bad segments to {project_bad_segments_file}: {e}")
    
    # Print summary
    total_bad = sum(len(bad_segments) for bad_segments in all_results.values())
    total_segments = sum(len([f for f in sorted(os.listdir(folder)) if f.endswith('.wav')]) for folder in speaker_folders if os.path.exists(folder))
    log_print(f"\n=== Project Validation Summary ===")
    log_print(f"Project: {project_name}")
    log_print(f"Speaker folders processed: {len(speaker_folders)}")
    log_print(f"Total segments processed: {total_segments}")
    log_print(f"Total bad segments found: {total_bad}")
    
    return all_results


def clean_bad_segments_from_speaker(speaker_folder, bad_segments, progress_manager=None):
    """
    Clean bad segments from a speaker folder based on a list of bad segments.
    
    Args:
        speaker_folder (str): Path to the speaker folder containing .wav and .txt files.
        bad_segments (list): List of bad segment dictionaries.
        progress_manager: ProgressManager instance for tracking progress. Defaults to None.
        
    Returns:
        int: Number of segments cleaned.
    """
    def log_print(message):
        """Print message using progress manager if available, otherwise regular print."""
        if progress_manager:
            progress_manager.print_log(message)
        else:
            print(message)
    
    if not bad_segments:
        log_print(f"No bad segments to clean for speaker: {os.path.basename(speaker_folder)}")
        return 0
    
    cleaned_count = 0
    speaker_name = os.path.basename(speaker_folder)
    log_print(f"Cleaning {len(bad_segments)} bad segments for speaker: {speaker_name}")
    
    for bad_segment in bad_segments:
        filename = bad_segment.get('filename', '')
        if not filename:
            continue
            
        wav_file = os.path.join(speaker_folder, filename)
        txt_file = os.path.splitext(wav_file)[0] + '.txt'
        
        files_deleted = 0
        if os.path.exists(wav_file):
            try:
                os.remove(wav_file)
                files_deleted += 1
                log_print(f"  Deleted: {wav_file}")
            except Exception as e:
                log_print(f"  Error deleting {wav_file}: {e}")
        
        if os.path.exists(txt_file):
            try:
                os.remove(txt_file)
                files_deleted += 1
                log_print(f"  Deleted: {txt_file}")
            except Exception as e:
                log_print(f"  Error deleting {txt_file}: {e}")
        
        if files_deleted > 0:
            cleaned_count += 1
    
    log_print(f"Cleaned {cleaned_count} segments for speaker: {speaker_name}")
    return cleaned_count


def clean_bad_segments_from_project(project_name):
    """
    Clean bad segments from all speakers in a project based on the project-level bad_segments.json file.
    
    Args:
        project_name (str): Name of the project.
        
    Returns:
        int: Total number of segments cleaned.
    """
    project_bad_segments_file = os.path.join('projects', project_name, 'bad_segments.json')
    
    if not os.path.exists(project_bad_segments_file):
        print(f"No project bad_segments.json found: {project_bad_segments_file}")
        return 0
    
    try:
        with open(project_bad_segments_file, 'r', encoding='utf-8') as f:
            project_data = json.load(f)
    except Exception as e:
        print(f"Error reading project bad_segments.json: {e}")
        return 0
    
    if 'speakers' not in project_data:
        print(f"Invalid project bad_segments.json format: missing 'speakers' key")
        return 0
    
    total_cleaned = 0
    for speaker_folder, bad_segments in project_data['speakers'].items():
        if bad_segments:
            cleaned_count = clean_bad_segments_from_speaker(speaker_folder, bad_segments)
            total_cleaned += cleaned_count
    
    print(f"Total segments cleaned for project '{project_name}': {total_cleaned}")
    return total_cleaned


def _save_validation_progress(bad_segments_data, speaker_folder, bad_segments, processed_files):
    """
    Save validation progress to the bad_segments.json file.
    
    Args:
        bad_segments_data (dict): The current bad segments data structure
        speaker_folder (str): Path to the speaker folder being processed
        bad_segments (list): List of bad segments found so far
        processed_files (list): List of files that have been processed
    """
    try:
        # Update the speakers data
        if 'speakers' not in bad_segments_data:
            bad_segments_data['speakers'] = {}
        bad_segments_data['speakers'][speaker_folder] = bad_segments
        
        # Update progress tracking
        if 'progress' not in bad_segments_data:
            bad_segments_data['progress'] = {'speakers': {}}
        if 'speakers' not in bad_segments_data['progress']:
            bad_segments_data['progress']['speakers'] = {}
        
        bad_segments_data['progress']['speakers'][speaker_folder] = {
            'processed_files': processed_files,
            'total_processed': len(processed_files),
            'bad_segments_count': len(bad_segments)
        }
        
        # Update total counts
        bad_segments_data['total_bad_segments'] = sum(len(segs) for segs in bad_segments_data['speakers'].values())
        
        # Determine file path - extract from project structure
        # Assuming speaker_folder is something like "projects/PROJECT_NAME/splits/.../speakers/SPEAKER_ID"
        project_name = bad_segments_data.get('project_name')
        if project_name:
            project_bad_segments_file = os.path.join('projects', project_name, 'bad_segments.json')
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(project_bad_segments_file), exist_ok=True)
            
            # Save the file
            with open(project_bad_segments_file, 'w', encoding='utf-8') as f:
                json.dump(bad_segments_data, f, indent=2, ensure_ascii=False)
                
    except Exception as e:
        print(f"Warning: Could not save validation progress: {e}")


def validate_speaker_segments(speaker_folder, delete_bad=False, score_threshold=85, progress_manager=None, existing_bad_segments_data=None):
    """
    Validate all segments in a speaker folder.
    
    Args:
        speaker_folder (str): Path to the speaker folder containing .wav and .txt files.
        delete_bad (bool): Whether to delete bad segment files (deprecated - use clean_bad_segments_from_speaker).
        score_threshold (int): Minimum score threshold.
        progress_manager: ProgressManager instance for tracking progress. Defaults to None.
        existing_bad_segments_data (dict): Existing bad segments data to enable resumption.
        
    Returns:
        list: List of bad segments with their scores.
    """
    def log_print(message):
        """Print message using progress manager if available, otherwise regular print."""
        if progress_manager:
            progress_manager.print_log(message)
        else:
            print(message)
    
    if not os.path.exists(speaker_folder):
        log_print(f"Speaker folder not found: {speaker_folder}")
        return []

    # Find all .wav files in the speaker folder and sort alphabetically
    wav_files = sorted([f for f in os.listdir(speaker_folder) if f.endswith('.wav')])
    
    if not wav_files:
        log_print(f"No .wav files found in speaker folder: {speaker_folder}")
        return []

    # Load existing validation results to support resumption
    bad_segments = []
    processed_files = set()
    
    if existing_bad_segments_data:
        speakers_data = existing_bad_segments_data.get('speakers', {})
        speaker_data = speakers_data.get(speaker_folder, [])
        
        # Extract existing bad segments
        if isinstance(speaker_data, list):
            bad_segments = speaker_data.copy()
        
        # Extract processed files from progress tracking
        progress_data = existing_bad_segments_data.get('progress', {})
        speaker_progress = progress_data.get('speakers', {}).get(speaker_folder, {})
        processed_files = set(speaker_progress.get('processed_files', []))
        
        log_print(f"Resuming validation: {len(processed_files)} files already processed, {len(bad_segments)} bad segments found previously")
    
    # Filter out already processed files
    files_to_process = [f for f in wav_files if f not in processed_files]
    
    if not files_to_process:
        log_print(f"All files already processed in speaker folder: {speaker_folder}")
        return bad_segments
    
    log_print(f"Processing {len(files_to_process)} files out of {len(wav_files)} total files")
    
    # Initialize progress for individual segments within this speaker if we have a progress manager
    # and there are enough segments to warrant sub-progress tracking
    if progress_manager and len(files_to_process) > 10:
        progress_manager.init_step_progress(len(files_to_process), f"Validating {len(files_to_process)} segments")
    
    # Process files and save progress every 100 files
    processed_count = 0
    checkpoint_interval = 100
    
    for i, wav_filename in enumerate(files_to_process):
        if progress_manager and len(files_to_process) > 10:
            progress_manager.update_step(0, f"Validating segment {i+1}/{len(files_to_process)}: {wav_filename}")
        
        try:
            # Get file paths
            wav_file = os.path.join(speaker_folder, wav_filename)
            txt_file = os.path.splitext(wav_file)[0] + '.txt'
            
            if not os.path.exists(txt_file):
                log_print(f"Text file not found for {wav_filename}: {txt_file}")
                processed_files.add(wav_filename)  # Mark as processed even if no txt file
                processed_count += 1
                if progress_manager and len(files_to_process) > 10:
                    progress_manager.update_step(1)
                continue

            # Read the existing transcription
            with open(txt_file, 'r', encoding='utf-8') as f:
                original_transcription = f.read().strip()

            # Trim silence from audio file
            trimmed_audio_file = wav_file # _trim_silence(wav_file)
            
            # Transcribe the trimmed audio
            try:
                new_transcription = transcribe_file(trimmed_audio_file, skip_file_output=True)
                if isinstance(new_transcription, dict) and 'text' in new_transcription:
                    new_transcription = new_transcription['text']
            except Exception as e:
                log_print(f"Error transcribing {trimmed_audio_file}: {e}")
                processed_files.add(wav_filename)  # Mark as processed even if transcription failed
                processed_count += 1
                if progress_manager and len(files_to_process) > 10:
                    progress_manager.update_step(1)
                continue
            
            # Calculate similarity score
            score = _calculate_similarity_score(original_transcription, new_transcription)
            
            # Check if segment is bad
            if score < score_threshold:
                bad_segment = {
                    'filename': wav_filename,
                    'score': score,
                    'original_transcription': original_transcription,
                    'new_transcription': new_transcription,
                    'speaker_folder': speaker_folder
                }
                bad_segments.append(bad_segment)
                
                log_print(f"Bad segment found: {wav_filename} (score: {score})")
                log_print(f"  Original: '{original_transcription}'")
                log_print(f"  New: '{new_transcription}'")
                
            else:
                log_print(f"Good segment: {wav_filename} (score: {score})")
            
            # Mark file as processed
            processed_files.add(wav_filename)
            processed_count += 1
                
            # Clean up trimmed file if it's different from original
            if trimmed_audio_file != wav_file and os.path.exists(trimmed_audio_file):
                os.remove(trimmed_audio_file)
                
        except Exception as e:
            log_print(f"Error processing segment {wav_filename}: {e}")
            processed_files.add(wav_filename)  # Mark as processed even if error occurred
            processed_count += 1
            if progress_manager and len(files_to_process) > 10:
                progress_manager.update_step(1)
            continue
        
        if progress_manager and len(files_to_process) > 10:
            progress_manager.update_step(1)
        
        # Save progress every checkpoint_interval files
        if processed_count % checkpoint_interval == 0 and existing_bad_segments_data is not None:
            log_print(f"Checkpoint: Processed {processed_count} files, saving progress...")
            _save_validation_progress(existing_bad_segments_data, speaker_folder, bad_segments, list(processed_files))

    # Final save if there's remaining progress to save
    if existing_bad_segments_data is not None:
        _save_validation_progress(existing_bad_segments_data, speaker_folder, bad_segments, list(processed_files))

    return bad_segments


def copy_good_segments_to_project_audio(project_name, bad_segments_file=None):
    """
    Copy all good segments to project/audio folder with organized speaker subfolders and renumbered clips.
    Groups speakers by their ID across all segments (e.g., all SPEAKER_00 folders merged into one).
    
    Args:
        project_name (str): Name of the project.
        bad_segments_file (str): Path to bad_segments.json file. If None, uses default location.
        
    Returns:
        dict: Statistics about copied segments per speaker.
    """
    # Load bad segments to know which ones to skip
    bad_segments_dict = {}
    if bad_segments_file is None:
        bad_segments_file = os.path.join('projects', project_name, 'bad_segments.json')
    
    if os.path.exists(bad_segments_file):
        try:
            with open(bad_segments_file, 'r', encoding='utf-8') as f:
                bad_segments_data = json.load(f)
                
                # Handle the project-level structure with 'speakers' key
                if isinstance(bad_segments_data, dict) and 'speakers' in bad_segments_data:
                    speakers_data = bad_segments_data['speakers']
                    # Create a lookup dict by speaker folder and filename
                    for speaker_folder, bad_segments in speakers_data.items():
                        if isinstance(bad_segments, list):
                            bad_segments_dict[speaker_folder] = {
                                segment['filename'] for segment in bad_segments if isinstance(segment, dict) and 'filename' in segment
                            }
                else:
                    # Handle legacy format where it's directly speaker_folder -> bad_segments
                    for speaker_folder, bad_segments in bad_segments_data.items():
                        if isinstance(bad_segments, list):
                            bad_segments_dict[speaker_folder] = {
                                segment['filename'] for segment in bad_segments if isinstance(segment, dict) and 'filename' in segment
                            }
        except Exception as e:
            print(f"Warning: Could not load bad segments file {bad_segments_file}: {e}")
    
    # Find all speaker folders in the m6 structure
    project_splits_dir = os.path.join('projects', project_name, 'splits')
    project_audio_dir = os.path.join('projects', project_name, 'audio')
    
    # Create audio directory if it doesn't exist
    os.makedirs(project_audio_dir, exist_ok=True)
    
    speaker_folders = []
    
    if os.path.exists(project_splits_dir):
        print(f"Looking for segments in: {project_splits_dir}")
        
        # Walk through splits directory to find all speakers folders
        for root, dirs, files in os.walk(project_splits_dir):
            dirs.sort()  # Sort directories for consistent ordering
            if 'speakers' in dirs:
                speakers_dir = os.path.join(root, 'speakers')
                # Find all speaker ID folders within speakers directory
                for speaker_id in sorted(os.listdir(speakers_dir)):
                    speaker_path = os.path.join(speakers_dir, speaker_id)
                    if os.path.isdir(speaker_path):
                        speaker_folders.append(speaker_path)
    
    if not speaker_folders:
        print(f"No speaker folders found in project: {project_name}")
        return {}
    
    print(f"Found {len(speaker_folders)} speaker folders to process")
    
    # Group speaker folders by their actual speaker ID (basename)
    # This is the key fix: merge all SPEAKER_00 folders from different segments
    speakers_by_id = {}
    for speaker_folder in speaker_folders:
        speaker_id = os.path.basename(speaker_folder)
        if speaker_id not in speakers_by_id:
            speakers_by_id[speaker_id] = []
        speakers_by_id[speaker_id].append(speaker_folder)
    
    print(f"Grouped into {len(speakers_by_id)} unique speakers:")
    for speaker_id, folders in speakers_by_id.items():
        print(f"  {speaker_id}: {len(folders)} source folders")
    
    # Statistics
    copy_stats = {}
    speaker_counter = 0
    
    # Process each unique speaker ID
    for speaker_id, source_folders in speakers_by_id.items():
        print(f"\n--- Processing speaker: {speaker_id} ---")
        
        # Create speaker subfolder in audio directory
        speaker_audio_dir = os.path.join(project_audio_dir, f"speaker_{speaker_counter:02d}")
        os.makedirs(speaker_audio_dir, exist_ok=True)
        
        # Collect all segments from all source folders for this speaker
        all_segments = []
        total_wav_files = 0
        total_bad_count = 0
        
        for speaker_folder in source_folders:
            print(f"  Processing source folder: {speaker_folder}")
            
            # Find all .wav files in this speaker folder
            wav_files = [f for f in sorted(os.listdir(speaker_folder)) if f.endswith('.wav')]
            total_wav_files += len(wav_files)
            
            if not wav_files:
                print(f"    No .wav files found")
                continue
            
            # Get list of bad segments for this specific speaker folder
            bad_filenames = bad_segments_dict.get(speaker_folder, set())
            total_bad_count += len(bad_filenames)
            
            # Filter out bad segments and add to collection
            good_wav_files = [f for f in wav_files if f not in bad_filenames]
            
            for wav_filename in good_wav_files:
                src_wav = os.path.join(speaker_folder, wav_filename)
                src_txt = os.path.splitext(src_wav)[0] + '.txt'
                
                if os.path.exists(src_txt):
                    all_segments.append((src_wav, src_txt))
                else:
                    print(f"    Warning: Text file not found for {wav_filename}, skipping")
            
            print(f"    Found {len(wav_files)} total, {len(bad_filenames)} bad, {len(good_wav_files)} good")
        
        # Sort all segments for consistent numbering
        all_segments.sort(key=lambda x: x[0])  # Sort by wav file path
        
        # Copy all segments with renumbering
        clip_counter = 1
        copied_count = 0
        
        for src_wav, src_txt in all_segments:
            try:
                # Destination paths
                dst_wav = os.path.join(speaker_audio_dir, f"clip_{clip_counter:05d}.wav")
                dst_txt = os.path.join(speaker_audio_dir, f"clip_{clip_counter:05d}.txt")
                
                # Copy files
                shutil.copy2(src_wav, dst_wav)
                shutil.copy2(src_txt, dst_txt)
                
                copied_count += 1
                clip_counter += 1
                
            except Exception as e:
                print(f"  Error copying {os.path.basename(src_wav)}: {e}")
                continue
        
        copy_stats[f"speaker_{speaker_counter:02d}"] = {
            'original_speaker_id': speaker_id,
            'source_folders': source_folders,
            'destination_folder': speaker_audio_dir,
            'total_segments': total_wav_files,
            'bad_segments': total_bad_count,
            'copied_segments': copied_count
        }
        
        print(f"  Copied {copied_count} good segments to {speaker_audio_dir}")
        speaker_counter += 1
    
    # Save copy statistics to splits folder instead of audio folder
    project_splits_dir = os.path.join('projects', project_name, 'splits')
    os.makedirs(project_splits_dir, exist_ok=True)
    stats_file = os.path.join(project_splits_dir, 'copy_stats.json')
    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(copy_stats, f, indent=2, ensure_ascii=False)
        print(f"Copy statistics saved to: {stats_file}")
    except Exception as e:
        print(f"Error saving copy statistics: {e}")
    
    # Print summary
    total_copied = sum(stats['copied_segments'] for stats in copy_stats.values())
    total_bad = sum(stats['bad_segments'] for stats in copy_stats.values())
    total_segments = sum(stats['total_segments'] for stats in copy_stats.values())
    
    print(f"\n=== Copy Summary ===")
    print(f"Project: {project_name}")
    print(f"Unique speakers: {len(copy_stats)}")
    print(f"Total segments: {total_segments}")
    print(f"Bad segments skipped: {total_bad}")
    print(f"Good segments copied: {total_copied}")
    print(f"Destination: {project_audio_dir}")
    
    return copy_stats


def main():
    parser = argparse.ArgumentParser(description='Validate transcriptions in segment files or entire projects')
    parser.add_argument('input_path', help='Path to segment JSON file or project name')
    parser.add_argument('--delete-bad', action='store_true', 
                        help='Delete bad segment files')
    parser.add_argument('--threshold', type=int, default=85,
                        help='Score threshold for marking segments as bad (default: 85)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file for bad segments (only used for single segment file, default: bad_segments.json in same folder)')
    parser.add_argument('--copy', action='store_true',
                        help='Copy all good segments to project/audio folder with organized speaker subfolders and renumbered clips')
    
    args = parser.parse_args()
    
    # Check if input_path is a project name or a file path
    if args.input_path.endswith('.json') and os.path.exists(args.input_path):
        # Single segment JSON file
        print(f"Validating single segment file: {args.input_path}")
        
        bad_segments = validate_transcription(args.input_path, 
                                            delete_bad=args.delete_bad,
                                            score_threshold=args.threshold)
        
        print(f"\nValidation complete. Found {len(bad_segments)} bad segments.")
        
        # Determine output file path
        if args.output:
            output_file = args.output
        else:
            segment_dir = os.path.dirname(args.input_path)
            output_file = os.path.join(segment_dir, 'bad_segments.json')
        
        # Save bad segments to JSON file
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(bad_segments, f, indent=2, ensure_ascii=False)
            print(f"Bad segments saved to: {output_file}")
        except Exception as e:
            print(f"Error saving bad segments to {output_file}: {e}")
        
        return bad_segments
    
    else:
        # Project name
        print(f"Validating project: {args.input_path}")
        
        if args.output:
            print("Warning: --output option is ignored when validating entire projects. Bad segments are saved in project folder.")
        
        all_results = validate_project(args.input_path,
                                     delete_bad=args.delete_bad,
                                     score_threshold=args.threshold)
        
        # Copy good segments if requested
        if args.copy:
            print(f"\n=== Copying good segments to project/audio folder ===")
            copy_stats = copy_good_segments_to_project_audio(args.input_path)
            if copy_stats:
                print("Copy operation completed successfully!")
            else:
                print("Copy operation failed or no segments to copy.")
        
        return all_results


if __name__ == "__main__":
    main()
