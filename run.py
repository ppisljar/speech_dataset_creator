from m0_get import get_podcasts
from m1_clean import clean_audio
from m2_silences import find_silences_in_file
from m3_split import split_audio
from m4_transcribe_file import transcribe_file
from m5_pyannote import pyannote
from m6_segment import segment_audio, generate_segments
from m7_validate import validate_transcription
from m8_meta import generate_metadata
from m9_align_and_phonetize import align_and_phonetize
from m10_archive import archive_dataset

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def process_file(file_path, temp_dir="./output", override=False, segment=False):
    """
    Process a single podcast file through the pipeline.
    
    Args:
        file_path (str): Path to the podcast file.
        temp_dir (str): Temporary directory for processing.
        override (bool): Whether to override existing output files. Defaults to False.
        segment (bool): Whether to enable segmentation. Defaults to False.
    
    Returns:
        None
    """
    file_name = os.path.basename(file_path)
    print(f"Processing file: {file_name}")

    # in temp folder we create a cleaned audio file and temp_folder/<file_name>/ where we store all the split audio files
    file_temp_dir = Path(temp_dir) # Path(os.path.join(temp_dir, file_name))
    if not file_temp_dir.exists():
        file_temp_dir.mkdir(parents=True, exist_ok=True)

    clean_file = Path(os.path.join(temp_dir, f"{file_name}_cleaned_audio.wav"))
    if not override and clean_file.exists():
        print(f"Cleaned audio file {clean_file} already exists, skipping cleaning.")
    else:
        # Clean the audio file
        print(f"Cleaning audio {file_path} to {clean_file}")
        clean_audio(file_path, clean_file)

    # if any wav inside file_temp_dir exists, we skip the splitting
    if any(f.endswith('.wav') and not f.endswith('_cleaned_audio.wav') for f in os.listdir(file_temp_dir)) and not override:
        print(f"Split audio files already exist in {file_temp_dir}, skipping splitting.")
    else:
        print(f"Splitting audio {clean_file} into segments in {file_temp_dir}")
        split_audio(clean_file, file_temp_dir)

    # for each split audio file, perform transcription and diarization
    split_count = sum(1 for f in os.listdir(file_temp_dir) if f.endswith(".wav"))
    for split_file in os.listdir(file_temp_dir):
        # if we have more than single split (more than 1 .wav file in the folder):
        if split_file.endswith(f"_cleaned_audio.wav") and split_count > 1:
            continue
        if split_file.endswith(".wav"):
            print(f"Processing split file: {split_file}")
            split_path = os.path.join(file_temp_dir, split_file)

            silence_file = f"{split_path}_silences.json"
            transcription_file = f"{split_path}_transcription.json"
            pyannote_file = f"{split_path}_pyannote"
            threedspeaker_file = f"{split_path}_3dspeaker"
            wespeaker_file = f"{split_path}_wespeaker"
            segments_file = f"{split_path}_segments.json"
            speaker_db_file = f"{split_path}_speaker_db.npy"

            if not override and os.path.exists(silence_file):
                print(f"Silence file already exists, skipping silence detection.")
            else:
                # Find silences in the split audio file
                print(f"Finding silences in {split_path}")
                find_silences_in_file(split_path, silence_file)

            if not override and os.path.exists(transcription_file):
                print(f"Transcription file already exists, skipping transcription.")
            else:
                # Transcribe the split audio file
                print(f"Transcribing {split_path}")
                transcribe_file(split_path, transcription_file)

            if not override and os.path.exists(pyannote_file + '.csv'):
                print(f"Pyannote file already exists, skipping pyannote processing.")
            else:
                # Run pyannote on the split audio file
                print(f"Running pyannote on {split_path}")
                pyannote(split_path, pyannote_file, speaker_db=speaker_db_file)

            if not override and os.path.exists(threedspeaker_file + '.csv'):
                print(f"3D-Speaker file already exists, skipping 3D-Speaker processing.")
            else:
                # Run 3D-Speaker on the split audio file
                print(f"Running 3D-Speaker on {split_path}")
                try:
                    from m5_3dspeaker import threed_speaker_diarize
                    threed_speaker_diarize(split_path, output_file=threedspeaker_file)
                except ImportError as e:
                    print(f"Warning: Could not import 3D-Speaker: {e}")
                except Exception as e:
                    print(f"Error running 3D-Speaker: {e}")

            if not override and os.path.exists(wespeaker_file + '.csv'):
                print(f"WeSpeaker file already exists, skipping WeSpeaker processing.")
            else:
                # Run WeSpeaker on the split audio file
                print(f"Running WeSpeaker on {split_path}")
                try:
                    from m5_wespeaker import wespeaker_diarize
                    wespeaker_diarize(split_path, output_file=wespeaker_file)
                except ImportError as e:
                    print(f"Warning: Could not import WeSpeaker: {e}")
                except Exception as e:
                    print(f"Error running WeSpeaker: {e}")

            if not override and os.path.exists(segments_file):
                print(f"Segments file already exists, skipping segmentation.")
            else:
                # Segment the audio based on transcription
                print(f"Segmenting {split_path}")
                segment_audio(split_path, transcription_file, segments_file)

            if segment:
                # check if segmenting was already done (files exist inside {split_path}_segments)
                segments_output_path = f"{split_path}_segments"
                if os.path.exists(segments_output_path):
                    print(f"Segments already exist, skipping segmentation.")
                else:
                    # If segmentation is enabled, process the segments
                    print(f"Segmenting {split_path} with segments file {segments_file}")
                    generate_segments(segments_file, split_path, segments_output_path)

def main():
    """
    Main function to run the podcast processing pipeline.

    Usage:
        python run.py <file_path> [temp_dir] [--override] [--segment]

    Args:
        file_path (str): Path to the podcast file (required)
        temp_dir (str): Output directory (optional, defaults to "./output")
        --override (bool): Whether to override existing output files (optional, defaults to False).
        --segment (bool): Whether to enable segmentation (optional, defaults to False).

    Returns:
        None
    """
    import argparse

    parser = argparse.ArgumentParser(description="Run the podcast processing pipeline.")
    parser.add_argument("file_path", type=str, help="Path to the podcast file (required)")
    parser.add_argument("temp_dir", type=str, nargs="?", default="./output", help="Output directory (optional, defaults to './output')")
    parser.add_argument("--override", action="store_true", help="Override existing output files")
    parser.add_argument("--segment", action="store_true", help="Enable segmentation")

    args = parser.parse_args()

    if not os.path.exists(args.temp_dir):
        os.makedirs(args.temp_dir)

    process_file(args.file_path, args.temp_dir, args.override, args.segment)

    # for podcast in podcasts:
    #     process_file(podcast, args.temp_dir, args.override)

    # if args.segment:
    #     generate_metadata(args.temp_dir)
    #     align_and_phonetize()
    #     archive_dataset()


if __name__ == "__main__":
    main()