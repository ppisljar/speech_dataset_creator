
import os
import sys
import subprocess
import pandas as pd
import numpy as np
import uuid
import traceback
from pyannote.audio import Pipeline, Model
from pyannote.core import Segment
import argparse
import torch
import torchaudio

HF_TOKEN = os.environ.get("HF_TOKEN")  # or set to string, e.g., "hf_abc..."

def load_db(path="speaker_db.npy"):
    return np.load(path, allow_pickle=True).item() if os.path.exists(path) else {}

def save_db(db, path="speaker_db.npy"):
    np.save(path, db)

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def pyannote(input_file, output_file, min_speakers=None, max_speakers=None, speaker_db=None, speaker_threshold=0.75):
    """
    Perform speaker diarization on an audio file using pyannote.audio
    
    Args:
        input_file (str): Path to input audio file (wav or mp3)
        output_file (str): Base path for output files (will create .rttm and .csv)
        min_speakers (int, optional): Minimum number of speakers
        max_speakers (int, optional): Maximum number of speakers
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

    # Load overlap-aware diarization pipeline
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("WARNING: running on CPU")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN,
    )

    pipeline.to(device)

    # Load embedding model for speaker matching
    speakers = {}
    embedder = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
    embedder.to(device)
    if speaker_db is not None:
        speakers = load_db(speaker_db)

    # Load audio using torchaudio (correct way for current pyannote)
    waveform, sample_rate = torchaudio.load(AUDIO)
    
    # Ensure mono audio for embedder
    if isinstance(waveform, torch.Tensor) and waveform.shape[0] > 1:
        # Average across channels (dim=0) to convert stereo to mono
        waveform = torch.mean(waveform, dim=0, keepdim=True)
    
    # Move waveform to the same device as the embedder
    waveform = waveform.to(device)
    
    # Prepare pipeline arguments for min/max speakers
    pipeline_kwargs = {}
    if min_speakers is not None:
        pipeline_kwargs["min_speakers"] = min_speakers
    if max_speakers is not None:
        pipeline_kwargs["max_speakers"] = max_speakers

    # Run diarization
    diarization = pipeline(AUDIO, **pipeline_kwargs)

    # --- Save RTTM (standard diarization format) ---
    rttm_file = f"{output_file}.rttm"
    with open(rttm_file, "w") as f:
        diarization.write_rttm(f)

    # --- Also save a simple CSV for inspection ---
    rows = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        # Extract segment waveform for embedding
        start_sample = int(turn.start * sample_rate)
        end_sample = int(turn.end * sample_rate)
        segment_waveform = waveform[:, start_sample:end_sample]
        
        # Extract embedding for this segment
        # Note: embedder expects just the waveform tensor, not a dict
        with torch.no_grad():
            try:
                embedding = embedder(segment_waveform)
                print (f"Extracted embedding for segment {turn.start}-{turn.end} with shape {embedding}")
                
                # Handle different types of embedding output
                if isinstance(embedding, dict):
                    # If it's a dict, try to get the 'waveform' or 'embedding' key
                    if 'embedding' in embedding:
                        embedding = embedding['embedding']
                    elif 'waveform' in embedding:
                        embedding = embedding['waveform']
                    else:
                        # Take the first tensor value from the dict
                        embedding = next(iter(embedding.values()))
                        # Handle nested dicts
                        while isinstance(embedding, dict):
                            embedding = next(iter(embedding.values()))
                
                if isinstance(embedding, torch.Tensor):
                    embedding = embedding.cpu().numpy()
                elif hasattr(embedding, 'numpy'):
                    embedding = embedding.cpu().numpy()
                else:
                    # If it's already a numpy array or list
                    embedding = np.array(embedding)
                
                # Ensure it's 1D - only check ndim if it's not a dict
                if not isinstance(embedding, dict) and hasattr(embedding, 'ndim') and embedding.ndim > 1:
                    embedding = embedding.flatten()
                    
            except Exception as e:
                print(f"Warning: Could not extract embedding for segment {turn.start}-{turn.end}: {e}")
                print("Full stack trace:")
                traceback.print_exc()
                # Fall back to using the original speaker label
                speaker_name = speaker
                rows.append({
                    "speaker": speaker_name,
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                    "duration": round(turn.duration, 3),
                })
                continue
        
        # Try to match to known speakers
        best_name = None
        best_score = -1
        for name, ref_vector in speakers.items():
            try:
                sim = cosine_similarity(embedding, ref_vector)
                if sim > speaker_threshold and sim > best_score:
                    best_name = name
                    best_score = sim
            except Exception as e:
                print(f"Warning: Could not compare with speaker {name}: {e}")
                continue

        if best_name:
            speaker_name = best_name
        else:
            speaker_name = f"spk_{str(uuid.uuid4())[:8]}"
            speakers[speaker_name] = embedding  # Add new speaker

        rows.append({
            "speaker": speaker_name,
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "duration": round(turn.duration, 3),
        })
    
    # Save updated speaker database
    if speaker_db is not None:
        save_db(speakers, speaker_db)

    csv_file = f"{output_file}.csv"
    pd.DataFrame(rows).sort_values(["start","end"]).to_csv(csv_file, index=False)

    print(f"Wrote {rttm_file} and {csv_file}")
    
    return {
        "segments": rows,
        "rttm_file": rttm_file,
        "csv_file": csv_file
    }

def main():
    """Main function for command line usage"""
    # Read audio filename and (optional) min/max speakers from command line
    parser = argparse.ArgumentParser(description="Speaker diarization with pyannote.audio")
    parser.add_argument("audio", help="Input audio file (wav or mp3)")
    parser.add_argument("--min_speakers", type=int, default=None, help="Minimum number of speakers")
    parser.add_argument("--max_speakers", type=int, default=None, help="Maximum number of speakers")
    parser.add_argument("--output", default="audio", help="Output file base name (default: 'audio')")
    args = parser.parse_args()
    
    pyannote(args.audio, args.output, args.min_speakers, args.max_speakers)

if __name__ == "__main__":
    main()
