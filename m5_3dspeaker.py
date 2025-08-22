#!/usr/bin/env python3
"""
Speaker Diarization using 3D-Speaker

This module provides speaker diarization functionality using the 3D-Speaker toolkit.
It follows the same interface as the original pyannote module for compatibility.

Requirements:
    pip install 3dspeaker

Author: Automated conversion from pyannote to 3D-Speaker
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import subprocess
import torch
from pathlib import Path

# Add the current directory to the path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from speakerlab.bin.infer_diarization import Diarization3Dspeaker
    THREED_SPEAKER_AVAILABLE = True
except ImportError:
    THREED_SPEAKER_AVAILABLE = False
    print("Warning: 3D-Speaker not available. Please install it with: pip install 3dspeaker")


def load_db(path):
    """Load speaker database from file."""
    return np.load(path, allow_pickle=True).item() if os.path.exists(path) else {}


def save_db(db, path):
    """Save speaker database to file."""
    np.save(path, db)


def convert_to_wav_if_needed(audio_file_path):
    """Convert audio file to WAV format if it's not already in WAV format."""
    if audio_file_path.lower().endswith('.wav'):
        return audio_file_path
    
    # Convert to WAV using ffmpeg
    wav_path = audio_file_path.rsplit('.', 1)[0] + '_converted.wav'
    cmd = [
        'ffmpeg', '-y', '-i', audio_file_path,
        '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
        wav_path
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return wav_path
    except subprocess.CalledProcessError as e:
        print(f"Error converting audio file: {e}")
        return audio_file_path


def find_closest_speaker(embedding, speaker_database, threshold=0.8):
    """Find the closest speaker in the database using cosine similarity."""
    if not speaker_database:
        return None
    
    max_similarity = -1
    closest_speaker = None
    
    for speaker_name, speaker_embedding in speaker_database.items():
        # Calculate cosine similarity
        similarity = np.dot(embedding, speaker_embedding) / (
            np.linalg.norm(embedding) * np.linalg.norm(speaker_embedding)
        )
        
        if similarity > max_similarity and similarity > threshold:
            max_similarity = similarity
            closest_speaker = speaker_name
    
    return closest_speaker


def threed_speaker_diarize(audio_file_path, output_file=None, speaker_database=None, include_overlap=False, max_speakers=None, speaker_db=None):
    """
    Perform speaker diarization using 3D-Speaker.
    
    Args:
        audio_file_path (str): Path to the audio file
        output_file (str): Base path for output files (will create .rttm and .csv)
        speaker_database (dict): Dictionary mapping speaker names to embeddings (optional, deprecated)
        include_overlap (bool): Whether to include overlapping speech detection
        max_speakers (int): Maximum number of speakers (optional, if None uses auto-detect)
        speaker_db (str): Path to project-level speaker database file (optional)
        
    Returns:
        dict: Dictionary with segments, rttm_file, and csv_file paths
    """
    if not THREED_SPEAKER_AVAILABLE:
        raise ImportError("3D-Speaker is not available. Please install it with: pip install 3dspeaker")
    
    # Convert audio to WAV if needed
    wav_path = convert_to_wav_if_needed(audio_file_path)
    
    # Load speaker database if provided
    speakers = {}
    if speaker_db is not None:
        speakers = load_db(speaker_db)
    elif speaker_database is not None:
        # Backward compatibility with old parameter
        speakers = speaker_database
    
    # Set device for GPU acceleration
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        print(f"Using GPU: {torch.cuda.get_device_name()}")
    else:
        print("WARNING: running on CPU")
    
    try:
        # Initialize 3D-Speaker diarization pipeline
        device_str = "cuda" if torch.cuda.is_available() else "cpu"
        pipeline = Diarization3Dspeaker(
            device=device_str,  # Use GPU if available
            include_overlap=include_overlap,
            hf_access_token=None,  # Not needed unless include_overlap is True
            speaker_num=max_speakers,  # Use max_speakers parameter if provided
            model_cache_dir=None  # Use default cache directory
        )
        
        # Perform diarization
        diarization_result = pipeline(wav_path)
        
        # Convert results to the expected format
        segments = []
        rows = []
        
        # The 3dspeaker result format may vary, handle different formats
        if hasattr(diarization_result, 'itertracks'):
            # If it's a pyannote-style result
            for segment, track, speaker in diarization_result.itertracks(yield_label=True):
                start_time = segment.start
                end_time = segment.end
                duration = end_time - start_time
                speaker_name = f"spk_{speaker}"
                
                rows.append({
                    'speaker': speaker_name,
                    'start': round(start_time, 3),
                    'end': round(end_time, 3),
                    'duration': round(duration, 3),
                })
        elif isinstance(diarization_result, list):
            # If it's a list of segments
            for i, segment in enumerate(diarization_result):
                if len(segment) >= 3:
                    start_time, end_time, speaker_id = segment[:3]
                    duration = end_time - start_time
                    speaker_name = f"spk_{speaker_id}"
                    
                    rows.append({
                        'speaker': speaker_name,
                        'start': round(start_time, 3),
                        'end': round(end_time, 3),
                        'duration': round(duration, 3),
                    })
        else:
            # Handle other formats by iterating over the result
            try:
                for segment in diarization_result:
                    # Try to extract start, end, speaker from various formats
                    if hasattr(segment, 'start') and hasattr(segment, 'end'):
                        start_time = segment.start
                        end_time = segment.end
                        speaker_id = getattr(segment, 'speaker', getattr(segment, 'label', 'unknown'))
                    elif isinstance(segment, (list, tuple)) and len(segment) >= 3:
                        start_time, end_time, speaker_id = segment[:3]
                    else:
                        continue
                    
                    duration = end_time - start_time
                    speaker_name = f"spk_{speaker_id}"
                    
                    rows.append({
                        'speaker': speaker_name,
                        'start': round(start_time, 3),
                        'end': round(end_time, 3),
                        'duration': round(duration, 3),
                    })
            except Exception as e:
                print(f"Warning: Could not parse diarization result: {e}")
                print(f"Result type: {type(diarization_result)}")
                if hasattr(diarization_result, '__dict__'):
                    print(f"Result attributes: {diarization_result.__dict__}")
                return {
                    "segments": [],
                    "rttm_file": None,
                    "csv_file": None
                }
        
        # Generate output files if output_file is specified
        if output_file:
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Save RTTM file (standard diarization format)
            base_name = os.path.basename(audio_file_path).rsplit('.', 1)[0]
            rttm_file = f"{output_file}.rttm"
            
            with open(rttm_file, "w") as f:
                for row in rows:
                    # RTTM format: SPEAKER filename channel_id start_time duration <NA> <NA> speaker_label <NA> <NA>
                    f.write(f"SPEAKER {base_name} 1 {row['start']:.3f} {row['duration']:.3f} <NA> <NA> {row['speaker']} <NA> <NA>\n")
            
            # Save CSV file for inspection (matching pyannote format)
            csv_file = f"{output_file}.csv"
            df = pd.DataFrame(rows)
            df.sort_values(["start", "end"], inplace=True)
            df.to_csv(csv_file, index=False)
            print(f"Saved diarization results to {rttm_file} and {csv_file}")
        else:
            rttm_file = None
            csv_file = None
        
        # Save updated speaker database if provided
        # Note: Current 3D-Speaker implementation doesn't extract embeddings for speaker matching
        # This is a placeholder for future implementation
        if speaker_db is not None:
            save_db(speakers, speaker_db)
        
        # Clean up converted file if we created one
        if wav_path != audio_file_path and os.path.exists(wav_path):
            os.remove(wav_path)
        
        return {
            "segments": rows,
            "rttm_file": rttm_file,
            "csv_file": csv_file
        }
        
    except Exception as e:
        # Clean up converted file if we created one
        if wav_path != audio_file_path and os.path.exists(wav_path):
            os.remove(wav_path)
        raise e


def pyannote(audio_file_path, output_file=None, speaker_database=None, max_speakers=None):
    """
    Compatibility wrapper for the original pyannote function.
    This function maintains the same interface as the original pyannote module.
    
    Args:
        audio_file_path (str): Path to the audio file
        output_file (str): Base path for output files (will create .rttm and .csv)
        speaker_database (dict): Dictionary mapping speaker names to embeddings (optional)
        max_speakers (int): Maximum number of speakers (optional)
        
    Returns:
        dict: Dictionary with segments, rttm_file, and csv_file paths
    """
    return threed_speaker_diarize(audio_file_path, output_file, speaker_database, include_overlap=False, max_speakers=max_speakers)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Speaker Diarization using 3D-Speaker')
    parser.add_argument('audio_file', help='Path to the audio file')
    parser.add_argument('--output', default=None, help='Base path for output files (will create .rttm and .csv)')
    parser.add_argument('--include_overlap', action='store_true', 
                       help='Include overlapping speech detection (requires HuggingFace token)')
    parser.add_argument('--hf_token', help='HuggingFace access token (required for overlap detection)')
    parser.add_argument('--speaker_db', help='Path to speaker database file (optional)')
    parser.add_argument('--speaker_threshold', type=float, default=0.75, 
                       help='Similarity threshold for speaker matching')
    parser.add_argument('--max_speakers', type=int, default=None,
                       help='Maximum number of speakers (optional, if not provided uses auto-detect)')
    
    args = parser.parse_args()
    
    if args.include_overlap and not args.hf_token:
        print("Warning: --hf_token is required when using --include_overlap")
        args.include_overlap = False
    
    # Set default output path if not provided
    if args.output is None:
        base_name = os.path.splitext(args.audio_file)[0]
        args.output = f"{base_name}_3dspeaker"
    
    try:
        # Perform diarization
        result = threed_speaker_diarize(
            args.audio_file, 
            args.output,
            speaker_database=None,  # Could load from speaker_db file if needed
            include_overlap=args.include_overlap,
            max_speakers=args.max_speakers
        )
        
        # Print results
        segments = result.get('segments', [])
        print(f"\nDiarization completed! Found {len(segments)} segments:")
        for i, segment in enumerate(segments):
            print(f"  Segment {i+1}: {segment['start']:.2f}s - {segment['end']:.2f}s, {segment['speaker']}")
            
    except Exception as e:
        print(f"Error during diarization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
