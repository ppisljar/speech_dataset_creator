
#!/usr/bin/env python3
"""
Speaker Diarization using WeSeaker

This script performs speaker diarization on audio files using the wespeaker toolkit.
It's a drop-in replacement for the pyannote-based diarization in m5_pyannote.py.

Installation requirements:
    pip install git+https://github.com/wenet-e2e/wespeaker.git

For more information about wespeaker, see:
https://github.com/wenet-e2e/wespeaker
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np
import uuid
import argparse
import torch
import wespeaker

def load_db(path="speaker_db.npy"):
    return np.load(path, allow_pickle=True).item() if os.path.exists(path) else {}

def save_db(db, path="speaker_db.npy"):
    np.save(path, db)

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def wespeaker_diarize(input_file, output_file, min_speakers=None, max_speakers=None, speaker_db=None, speaker_threshold=0.75):
    """
    Perform speaker diarization on an audio file using wespeaker
    
    Args:
        input_file (str): Path to input audio file (wav or mp3)
        output_file (str): Base path for output files (will create .rttm and .csv)
        min_speakers (int, optional): Minimum number of speakers (not used by wespeaker)
        max_speakers (int, optional): Maximum number of speakers (not used by wespeaker)
        speaker_db (str, optional): Path to speaker database file (optional)
        speaker_threshold (float, optional): Similarity threshold for speaker matching
    
    Returns:
        dict: Dictionary containing diarization results with speaker segments
    """
    AUDIO = input_file
    
    # If input is mp3, convert to 16kHz mono wav if not already present
    if AUDIO.lower().endswith(('.mp3', '.m4a', '.flac')):
        wav_file = os.path.splitext(AUDIO)[0] + "_16khz.wav"
        if not os.path.exists(wav_file):
            print(f"Converting {AUDIO} to {wav_file} (16kHz mono)...")
            result = subprocess.run([
                "ffmpeg", "-y", "-i", AUDIO, "-ac", "1", "-ar", "16000", wav_file
            ], capture_output=True)
            
            if result.returncode != 0:
                print("ffmpeg conversion failed:", result.stderr.decode())
                sys.exit(1)
        AUDIO = wav_file

    # Set device for GPU acceleration
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        print(f"Using GPU: {torch.cuda.get_device_name()}")
    else:
        print("WARNING: running on CPU")

    # Load wespeaker model
    try:
        model = wespeaker.load_model('english')  # You can change to 'chinese' if needed
        
        # Set device for GPU acceleration
        if torch.cuda.is_available():
            model.set_device('cuda:0')
            print("Model configured to use GPU")
        else:
            model.set_device('cpu')
            print("Model configured to use CPU")
            
        print("Loaded wespeaker model successfully")
    except Exception as e:
        print(f"Error loading wespeaker model: {e}")
        sys.exit(1)

    # Load speaker database if provided
    speakers = {}
    if speaker_db is not None:
        speakers = load_db(speaker_db)

    # Run diarization using wespeaker
    try:
        print(f"Running wespeaker diarization on {AUDIO}")
        # Get basename of audio file for utterance ID
        utt_id = os.path.splitext(os.path.basename(AUDIO))[0]
        diar_result = model.diarize(AUDIO, utt_id)
        print(f"Diarization completed. Found {len(diar_result)} segments")
    except Exception as e:
        print(f"Error during diarization: {e}")
        sys.exit(1)

    # Process results and create output files
    rows = []
    
    # wespeaker.diarize() returns a list of tuples in format: (utt, begin, end, label)
    for segment in diar_result:
        if len(segment) == 4:  # Expected format: (utt, begin, end, label)
            utt, start_time, end_time, speaker_label = segment
            duration = end_time - start_time
            
            # For now, use original speaker labels since wespeaker doesn't provide
            # direct embedding extraction for specific time segments in the simple API
            speaker_name = f"spk_{speaker_label}"
            
            rows.append({
                "speaker": speaker_name,
                "start": round(start_time, 3),
                "end": round(end_time, 3),
                "duration": round(duration, 3),
            })
        else:
            print(f"Unexpected segment format: {segment}")
            continue
    
    # Save updated speaker database
    if speaker_db is not None:
        save_db(speakers, speaker_db)

    # Save CSV file
    csv_file = f"{output_file}.csv"
    pd.DataFrame(rows).sort_values(["start","end"]).to_csv(csv_file, index=False)

    # Create RTTM file (standard diarization format)
    rttm_file = f"{output_file}.rttm"
    with open(rttm_file, "w") as f:
        for row in rows:
            # RTTM format: SPEAKER filename channel_id start_time duration <NA> <NA> speaker_label <NA> <NA>
            f.write(f"SPEAKER {os.path.basename(AUDIO)} 1 {row['start']:.3f} {row['duration']:.3f} <NA> <NA> {row['speaker']} <NA> <NA>\n")

    print(f"Wrote {rttm_file} and {csv_file}")
    
    return {
        "segments": rows,
        "rttm_file": rttm_file,
        "csv_file": csv_file
    }

# Alias for backward compatibility with existing code that imports pyannote function
def pyannote(input_file, output_file, min_speakers=None, max_speakers=None, speaker_db=None, speaker_threshold=0.75):
    """
    Backward compatibility wrapper for wespeaker_diarize function.
    This allows existing code that imports 'pyannote' to work with wespeaker.
    """
    return wespeaker_diarize(input_file, output_file, min_speakers, max_speakers, speaker_db, speaker_threshold)

def main():
    """Main function for command line usage"""
    # Read audio filename and (optional) min/max speakers from command line
    parser = argparse.ArgumentParser(description="Speaker diarization with wespeaker")
    parser.add_argument("audio", help="Input audio file (wav or mp3)")
    parser.add_argument("--min_speakers", type=int, default=None, help="Minimum number of speakers (not used by wespeaker)")
    parser.add_argument("--max_speakers", type=int, default=None, help="Maximum number of speakers (not used by wespeaker)")
    parser.add_argument("--output", default="audio", help="Output file base name (default: 'audio')")
    parser.add_argument("--speaker_db", default=None, help="Path to speaker database file")
    parser.add_argument("--speaker_threshold", type=float, default=0.75, help="Similarity threshold for speaker matching")
    args = parser.parse_args()
    
    wespeaker_diarize(args.audio, args.output, args.min_speakers, args.max_speakers, args.speaker_db, args.speaker_threshold)

if __name__ == "__main__":
    main()
