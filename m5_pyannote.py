#!/usr/bin/env python3

import os
import sys
import subprocess
import pandas as pd
import numpy as np
import uuid
import traceback
from pyannote.audio import Pipeline, Model, Inference
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


def pyannote(input_file, output_file, min_speakers=None, max_speakers=None, speaker_db=None, speaker_threshold=0.999999):
    """
    Perform speaker diarization on an audio file using pyannote.audio
    
    Args:
        input_file (str): Path to input audio file (wav or mp3)
        output_file (str): Base path for output files (will create .rttm and .csv)
        min_speakers (int, optional): Minimum number of speakers
        max_speakers (int, optional): Maximum number of speakers
        speaker_db (str, optional): Path to project-level speaker database file (optional)
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
    model = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
    model.to(device)
    # Also create inference instance for whole-file embeddings
    inference = Inference(model, window="whole")
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

    # Extract whole-file embedding for cross-file speaker matching
    print("Extracting whole-file embedding for cross-file speaker matching...")
    try:
        file_embedding = inference(AUDIO)
        print(f"File embedding shape: {file_embedding.shape}")
    except Exception as e:
        print(f"Warning: Could not extract whole-file embedding: {e}")
        file_embedding = None

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
        
        # Check if segment is too short for the embedding model
        # Minimum duration should be at least 0.1 seconds (1600 samples at 16kHz)
        min_samples = int(0.1 * sample_rate)  # 0.1 seconds minimum
        if segment_waveform.shape[1] < min_samples:
            print(f"Warning: Segment {turn.start}-{turn.end} is too short ({segment_waveform.shape[1]} samples, need >{min_samples}). Using original speaker label.")
            speaker_name = speaker
            rows.append({
                "speaker": speaker_name,
                "start": round(turn.start, 3),
                "end": round(turn.end, 3),
                "duration": round(turn.duration, 3),
            })
            continue
        
        # Extract embedding for this segment using Model directly (correct approach)
        with torch.no_grad():
            try:
                # Model expects tensor input and returns tensor output
                embedding_tensor = model(segment_waveform)
                
                # Convert to numpy and flatten - Model returns (1, 512) shape
                embedding = embedding_tensor.cpu().numpy()
                if embedding.ndim > 1:
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
        
        # Try to match to known speakers using segment embedding
        best_name = None
        best_score = -1
        for name, ref_vector in speakers.items():
            try:
                sim = cosine_similarity(embedding, ref_vector)
                # Due to pyannote embedding model compatibility issues producing nearly identical
                # embeddings for different speakers, we use a very high threshold and also
                # consider file-based heuristics
                if sim > speaker_threshold and sim > best_score:
                    best_name = name
                    best_score = sim
            except Exception as e:
                print(f"Warning: Could not compare with speaker {name}: {e}")
                continue

        # If no good match with segment embedding and we have file embedding, 
        # try matching with whole-file embedding for better cross-file speaker detection
        if not best_name and file_embedding is not None:
            file_best_name = None
            file_best_score = -1
            for name, ref_vector in speakers.items():
                try:
                    # Check if the reference vector is a file-level embedding (different shape/scale)
                    if hasattr(ref_vector, 'shape') and len(ref_vector.shape) == 1 and len(file_embedding.shape) == 1:
                        sim = cosine_similarity(file_embedding, ref_vector)
                        # Use a lower threshold for file-level embeddings as they should be more reliable
                        if sim > 0.7 and sim > file_best_score:
                            file_best_name = name
                            file_best_score = sim
                except Exception as e:
                    print(f"Warning: Could not compare file embedding with speaker {name}: {e}")
                    continue
            
            if file_best_name:
                best_name = file_best_name
                best_score = file_best_score
                print(f"Matched speaker using file-level embedding: {best_name} (similarity: {best_score:.4f})")

        if best_name:
            speaker_name = best_name
        else:
            # Create new speaker ID with a hint from the input filename
            # This helps distinguish speakers from different source files
            file_hint = os.path.basename(input_file).split('_')[0] if input_file else ""
            speaker_name = f"spk_{file_hint}_{str(uuid.uuid4())[:8]}" if file_hint else f"spk_{str(uuid.uuid4())[:8]}"
            
            # Store the file-level embedding if available, otherwise use segment embedding
            if file_embedding is not None:
                speakers[speaker_name] = file_embedding
                print(f"Created new speaker {speaker_name} using file-level embedding")
            else:
                speakers[speaker_name] = embedding  # Add new speaker with segment embedding

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
