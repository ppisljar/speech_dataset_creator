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
from pathlib import Path

# Add the current directory to the path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from speakerlab.bin.infer_diarization import Diarization3Dspeaker
    THREED_SPEAKER_AVAILABLE = True
except ImportError:
    THREED_SPEAKER_AVAILABLE = False
    print("Warning: 3D-Speaker not available. Please install it with: pip install 3dspeaker")


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


def threed_speaker_diarize(audio_file_path, output_file=None, speaker_database=None, include_overlap=False):
    """
    Perform speaker diarization using 3D-Speaker.
    
    Args:
        audio_file_path (str): Path to the audio file
        output_file (str): Base path for output files (will create .rttm and .csv)
        speaker_database (dict): Dictionary mapping speaker names to embeddings (optional)
        include_overlap (bool): Whether to include overlapping speech detection
        
    Returns:
        dict: Dictionary with segments, rttm_file, and csv_file paths
    """
    if not THREED_SPEAKER_AVAILABLE:
        raise ImportError("3D-Speaker is not available. Please install it with: pip install 3dspeaker")
    
    # Convert audio to WAV if needed
    wav_path = convert_to_wav_if_needed(audio_file_path)
    
    try:
        # Initialize 3D-Speaker diarization pipeline
        pipeline = Diarization3Dspeaker(
            device=None,  # Auto-detect device
            include_overlap=include_overlap,
            hf_access_token=None,  # Not needed unless include_overlap is True
            speaker_num=None,  # Auto-detect number of speakers
            model_cache_dir=None  # Use default cache directory
        )
        
        # Perform diarization
        diarization_result = pipeline(wav_path)
        
        # Convert results to the expected format
        segments = []
        rows = []
        for segment in diarization_result:
            start_time, end_time, speaker_id = segment
            segments.append([start_time, end_time, speaker_id])
            
            # Create row data for CSV output (matching pyannote format)
            rows.append({
                'start': start_time,
                'end': end_time,
                'duration': end_time - start_time,
                'speaker': f"SPEAKER_{speaker_id:02d}",
                'speaker_id': speaker_id
            })
        
        # Generate output files if output_file is specified
        if output_file:
            # Create directory if it doesn't exist
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            # Save RTTM file
            base_name = os.path.basename(audio_file_path).rsplit('.', 1)[0]
            rttm_file = f"{output_file}.rttm"
            pipeline.save_diar_output(rttm_file, wav_id=base_name, output_field_labels=diarization_result)
            
            # Save CSV file for inspection (matching pyannote format)
            csv_file = f"{output_file}.csv"
            df = pd.DataFrame(rows)
            df.to_csv(csv_file, index=False)
            print(f"Saved diarization results to {rttm_file} and {csv_file}")
        else:
            rttm_file = None
            csv_file = None
        
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


def pyannote(audio_file_path, output_file=None, speaker_database=None):
    """
    Compatibility wrapper for the original pyannote function.
    This function maintains the same interface as the original pyannote module.
    
    Args:
        audio_file_path (str): Path to the audio file
        output_file (str): Base path for output files (will create .rttm and .csv)
        speaker_database (dict): Dictionary mapping speaker names to embeddings (optional)
        
    Returns:
        dict: Dictionary with segments, rttm_file, and csv_file paths
    """
    return threed_speaker_diarize(audio_file_path, output_file, speaker_database, include_overlap=False)


def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Speaker Diarization using 3D-Speaker')
    parser.add_argument('audio_file', help='Path to the audio file')
    parser.add_argument('--output_dir', help='Directory to save output files')
    parser.add_argument('--include_overlap', action='store_true', 
                       help='Include overlapping speech detection (requires HuggingFace token)')
    parser.add_argument('--hf_token', help='HuggingFace access token (required for overlap detection)')
    
    args = parser.parse_args()
    
    if args.include_overlap and not args.hf_token:
        print("Warning: --hf_token is required when using --include_overlap")
        args.include_overlap = False
    
    try:
        # Perform diarization
        segments = threed_speaker_diarize(
            args.audio_file, 
            args.output_dir, 
            include_overlap=args.include_overlap
        )
        
        # Print results
        print(f"\nDiarization completed! Found {len(segments)} segments:")
        for i, (start, end, speaker) in enumerate(segments):
            print(f"  Segment {i+1}: {start:.2f}s - {end:.2f}s, Speaker {speaker}")
            
    except Exception as e:
        print(f"Error during diarization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
