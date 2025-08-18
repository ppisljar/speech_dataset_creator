#!/usr/bin/env python3
"""
3D-Speaker Embedding Extraction

This script extracts speaker embeddings from audio files using the 3D-Speaker ERes2Net model.
Based on: https://github.com/modelscope/3D-Speaker/blob/main/speakerlab/bin/infer_sv.py

Model: damo/speech_eres2net_large_sv_zh-cn_3dspeaker_16k
"""

import os
import sys
import numpy as np
import torch
import torchaudio
from pathlib import Path

try:
    from speakerlab.process.processor import FBank
    from speakerlab.utils.builder import dynamic_import
    from modelscope.hub.snapshot_download import snapshot_download
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please install required packages:")
    print("pip install modelscope torch torchaudio")
    sys.exit(1)


# Model configuration for damo/speech_eres2net_large_sv_zh-cn_3dspeaker_16k
MODEL_CONFIG = {
    'obj': 'speakerlab.models.eres2net.ERes2Net.ERes2Net',
    'args': {
        'feat_dim': 80,
        'embedding_size': 512,
        'm_channels': 64,
    },
}

MODEL_ID = 'damo/speech_eres2net_large_sv_zh-cn_3dspeaker_16k'
MODEL_REVISION = 'v1.0.0'
MODEL_PT = 'eres2net_large_model.ckpt'


def extract_speaker_embedding(audio_file_path):
    """
    Extract speaker embedding from an audio file using 3D-Speaker ERes2Net model.
    
    Args:
        audio_file_path (str): Path to the audio file
        
    Returns:
        numpy.ndarray: Speaker embedding vector
    """
    
    # Check if file exists
    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    
    # Set device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Download model
    print(f"Downloading model {MODEL_ID}...")
    model_dir = snapshot_download(
        MODEL_ID, 
        revision=MODEL_REVISION,
        cache_dir='pretrained'
    )
    
    # Load model
    print("Loading model...")
    model_path = os.path.join(model_dir, MODEL_PT)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # Build model
    model_class = dynamic_import(MODEL_CONFIG['obj'])
    embedding_model = model_class(**MODEL_CONFIG['args'])
    
    # Load checkpoint
    checkpoint = torch.load(model_path, map_location=device)
    embedding_model.load_state_dict(checkpoint)
    embedding_model.to(device)
    embedding_model.eval()
    
    # Initialize feature extractor
    feature_extractor = FBank(80, sample_rate=16000, mean_nor=True)
    
    def load_wav(wav_file):
        """Load and preprocess audio file"""
        wav, fs = torchaudio.load(wav_file)
        
        # Resample to 16kHz if needed
        target_fs = 16000
        if fs != target_fs:
            print(f"Resampling from {fs}Hz to {target_fs}Hz")
            wav, fs = torchaudio.sox_effects.apply_effects_tensor(
                wav, fs, effects=[['rate', str(target_fs)]]
            )
        
        # Convert to mono if stereo
        if wav.shape[0] > 1:
            wav = wav[0, :].unsqueeze(0)
            
        return wav
    
    # Load and process audio
    print(f"Processing audio file: {audio_file_path}")
    wav = load_wav(audio_file_path)
    
    # Extract features
    feat = feature_extractor(wav).unsqueeze(0).to(device)
    
    # Extract embedding
    with torch.no_grad():
        embedding = embedding_model(feat).detach().squeeze(0).cpu().numpy()
    
    print(f"Extracted embedding with shape: {embedding.shape}")
    return embedding


def main():
    """Main function to test the embedding extraction"""
    
    # Default test audio file
    default_audio = "output/test.mp3_cleaned_audio.wav"
    
    # Check if default file exists
    if os.path.exists(default_audio):
        audio_file = default_audio
    else:
        # Try to find any audio file in the output directory
        output_dir = Path("output")
        if output_dir.exists():
            audio_files = list(output_dir.glob("*.wav")) + list(output_dir.glob("*.mp3"))
            if audio_files:
                audio_file = str(audio_files[0])
            else:
                print("No audio files found in output directory")
                print("Please provide an audio file as argument or place one in the output directory")
                return
        else:
            print("Output directory not found")
            print("Please provide an audio file as argument")
            return
    
    # Allow command line argument for audio file
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    
    try:
        # Extract embedding
        embedding = extract_speaker_embedding(audio_file)
        
        # Print results
        print(f"\nSpeaker Embedding for: {audio_file}")
        print(f"Embedding shape: {embedding.shape}")
        print(f"Embedding dtype: {embedding.dtype}")
        print(f"Embedding range: [{embedding.min():.4f}, {embedding.max():.4f}]")
        print(f"Embedding mean: {embedding.mean():.4f}")
        print(f"Embedding std: {embedding.std():.4f}")
        print("\nFirst 10 values:")
        print(embedding[:10])
        
    except Exception as e:
        print(f"Error extracting embedding: {e}")
        return


if __name__ == "__main__":
    main()
