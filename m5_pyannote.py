
import os
import sys
import subprocess
import pandas as pd
from pyannote.audio import Pipeline
import argparse

HF_TOKEN = os.environ.get("HF_TOKEN")  # or set to string, e.g., "hf_abc..."

def pyannote(input_file, output_file, min_speakers=None, max_speakers=None):
    """
    Perform speaker diarization on an audio file using pyannote.audio
    
    Args:
        input_file (str): Path to input audio file (wav or mp3)
        output_file (str): Base path for output files (will create .rttm and .csv)
        min_speakers (int, optional): Minimum number of speakers
        max_speakers (int, optional): Maximum number of speakers
    
    Returns:
        dict: Dictionary containing diarization results with speaker segments
    """
    AUDIO = input_file
    
    # If input is mp3, convert to 16kHz mono wav if not already present
    if AUDIO.lower().endswith(".mp3"):
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
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=HF_TOKEN,
    )

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
        rows.append({
            "speaker": speaker,
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "duration": round(turn.duration, 3),
        })
    
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
