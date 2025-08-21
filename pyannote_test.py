#!/usr/bin/env python3

import os
import pandas as pd
import torch
import torchaudio
from pyannote.audio import Model

# Set up the environment
HF_TOKEN = os.environ.get("HF_TOKEN")

def test_embedder():
    """Test the pyannote embedder to see what it outputs"""
    
    # File paths
    audio_file = "output/test.mp3/test.mp3_cleaned_audio_01.wav"
    csv_file = "output/test.mp3/test.mp3_cleaned_audio_01.wav_pyannote.csv"
    
    print(f"Loading audio file: {audio_file}")
    print(f"Loading CSV file: {csv_file}")
    
    # Check if files exist
    if not os.path.exists(audio_file):
        print(f"ERROR: Audio file {audio_file} not found!")
        return
    
    if not os.path.exists(csv_file):
        print(f"ERROR: CSV file {csv_file} not found!")
        return
    
    # Load audio
    waveform, sample_rate = torchaudio.load(audio_file)
    print(f"Audio loaded: shape={waveform.shape}, sample_rate={sample_rate}")
    
    # Ensure mono audio
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
        print(f"Converted to mono: shape={waveform.shape}")
    
    # Load CSV to get segments
    df = pd.read_csv(csv_file)
    print(f"Found {len(df)} segments in CSV")
    
    # Load embedder
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    embedder = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
    embedder.to(device)
    print("Embedder loaded successfully")
    
    # Test with first few segments
    for i, row in df.head(3).iterrows():
        start_time = row['start']
        end_time = row['end']
        speaker = row['speaker']
        
        print(f"\n--- Testing segment {i+1}: {speaker} ({start_time:.3f}-{end_time:.3f}s) ---")
        
        # Extract segment waveform
        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)
        segment_waveform = waveform[:, start_sample:end_sample]
        
        print(f"Segment waveform shape: {segment_waveform.shape}")
        print(f"Segment duration: {segment_waveform.shape[1] / sample_rate:.3f}s")
        
        print(f"segment_waveform type: {type(segment_waveform)}")
        print(f"segment_waveform shape: {segment_waveform.shape}")
        
        # Run embedder (pass tensor directly, not dict)
        with torch.no_grad():
            try:
                embedding = embedder(segment_waveform)
                
                print(f"\n=== EMBEDDER OUTPUT ===")
                print(f"Type: {type(embedding)}")
                
                if isinstance(embedding, dict):
                    print(f"Dictionary with keys: {list(embedding.keys())}")
                    for key, value in embedding.items():
                        print(f"  {key}: type={type(value)}, ", end="")
                        if hasattr(value, 'shape'):
                            print(f"shape={value.shape}, ", end="")
                        if hasattr(value, 'dtype'):
                            print(f"dtype={value.dtype}")
                        else:
                            print(f"value={value}")
                elif hasattr(embedding, 'shape'):
                    print(f"Shape: {embedding.shape}")
                    print(f"Dtype: {embedding.dtype}")
                else:
                    print(f"Value: {embedding}")
                
                print(f"=== END EMBEDDER OUTPUT ===\n")
                
            except Exception as e:
                print(f"ERROR running embedder: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    test_embedder()
