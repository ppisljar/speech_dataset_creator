# validate speakers 

# validate text files against audio files ?

# outlier detection ?

import json
import os
import re
import difflib
import argparse
from pathlib import Path
import librosa
import soundfile as sf
import numpy as np
from m4_transcribe_file import transcribe_audio

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
            segment_text_file = segment_audio_file.replace('.wav', '.txt')
            
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
                new_transcription = transcribe_audio(trimmed_audio_file)
                if isinstance(new_transcription, dict) and 'transcription' in new_transcription:
                    new_transcription = new_transcription['transcription']
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


def validate_project(project_name, delete_bad=False, score_threshold=85):
    """
    Validate all segment JSON files in a project.
    
    Args:
        project_name (str): Name of the project.
        delete_bad (bool): Whether to delete bad segment files.
        score_threshold (int): Minimum score threshold.
        
    Returns:
        dict: Dictionary with segment file paths as keys and bad segments as values.
    """
    project_dir = os.path.join('projects', project_name, 'splits')
    
    if not os.path.exists(project_dir):
        print(f"Project directory not found: {project_dir}")
        return {}
    
    # Find all *_segments.json files
    segment_files = []
    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith('_segments.json'):
                segment_files.append(os.path.join(root, file))
    
    if not segment_files:
        print(f"No segment JSON files found in project: {project_name}")
        return {}
    
    print(f"Found {len(segment_files)} segment files in project '{project_name}':")
    for segment_file in segment_files:
        print(f"  {segment_file}")
    
    all_results = {}
    
    for segment_file in segment_files:
        print(f"\n--- Validating: {segment_file} ---")
        
        bad_segments = validate_transcription(segment_file, 
                                            delete_bad=delete_bad,
                                            score_threshold=score_threshold)
        
        all_results[segment_file] = bad_segments
        
        # Save bad segments to JSON file in the same directory as the segment file
        segment_dir = os.path.dirname(segment_file)
        output_file = os.path.join(segment_dir, 'bad_segments.json')
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(bad_segments, f, indent=2, ensure_ascii=False)
            print(f"Bad segments saved to: {output_file}")
        except Exception as e:
            print(f"Error saving bad segments to {output_file}: {e}")
    
    # Print summary
    total_bad = sum(len(bad_segments) for bad_segments in all_results.values())
    print(f"\n=== Project Validation Summary ===")
    print(f"Project: {project_name}")
    print(f"Total segment files processed: {len(segment_files)}")
    print(f"Total bad segments found: {total_bad}")
    
    return all_results


def main():
    parser = argparse.ArgumentParser(description='Validate transcriptions in segment files or entire projects')
    parser.add_argument('input_path', help='Path to segment JSON file or project name')
    parser.add_argument('--delete-bad', action='store_true', 
                        help='Delete bad segment files')
    parser.add_argument('--threshold', type=int, default=85,
                        help='Score threshold for marking segments as bad (default: 85)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output file for bad segments (only used for single segment file, default: bad_segments.json in same folder)')
    
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
            print("Warning: --output option is ignored when validating entire projects. Bad segments are saved in each split folder.")
        
        all_results = validate_project(args.input_path,
                                     delete_bad=args.delete_bad,
                                     score_threshold=args.threshold)
        
        return all_results


if __name__ == "__main__":
    main()
