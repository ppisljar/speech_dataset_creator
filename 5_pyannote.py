
import os
import sys
import subprocess
import pandas as pd
from pyannote.audio import Pipeline
import argparse

# Read audio filename and (optional) min/max speakers from command line
parser = argparse.ArgumentParser(description="Speaker diarization with pyannote.audio")
parser.add_argument("audio", help="Input audio file (wav or mp3)")
parser.add_argument("--min_speakers", type=int, default=None, help="Minimum number of speakers")
parser.add_argument("--max_speakers", type=int, default=None, help="Maximum number of speakers")
args = parser.parse_args()
AUDIO = args.audio

HF_TOKEN = os.environ.get("HF_TOKEN")  # or set to string, e.g., "hf_abc..."

# If input is mp3, convert to 16kHz mono wav if not already present
if AUDIO.lower().endswith(".mp3"):
    wav_file = os.path.splitext(AUDIO)[0] + "_16khz.wav"
    if not os.path.exists(wav_file):
        print(f"Converting {AUDIO} to {wav_file} (16kHz mono)...")
        result = subprocess.run([
            "ffmpeg", "-y", "-i", AUDIO, "-ac", "1", "-ar", "16000", wav_file
        ], capture_output=True)

# Load overlap-aware diarization pipeline
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
if args.min_speakers is not None:
    pipeline_kwargs["min_speakers"] = args.min_speakers
if args.max_speakers is not None:
    pipeline_kwargs["max_speakers"] = args.max_speakers

# Run diarization
diarization = pipeline(AUDIO, **pipeline_kwargs)

# --- Save RTTM (standard diarization format) ---
with open("audio.rttm", "w") as f:
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
pd.DataFrame(rows).sort_values(["start","end"]).to_csv("segments.csv", index=False)

print("Wrote audio.rttm and segments.csv")
