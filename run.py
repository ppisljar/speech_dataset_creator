from m0_get import get_podcasts
from m1_clean import clean_audio
from m2_silences import find_silences_in_file
from m3_split import split_audio
from m4_transcribe_file import transcribe_file
from m5_pyannote import pyannote
from m6_segment import segment_audio
from m7_validate import validate_transcription
from m8_meta import generate_metadata
from m9_align_and_phonetize import align_and_phonetize
from m10_archive import archive_dataset

import os
import sys

def process_file(file_path, temp_dir="./output"):
    """
    Process a single podcast file through the pipeline.
    
    Args:
        file_path (str): Path to the podcast file.
    
    Returns:
        None
    """
    file_name = os.path.basename(file_path)
    print(f"Processing file: {file_name}")

    # in temp folder we create a cleaned audio file and temp_folder/<file_name>/ where we store all the split audio files
    file_temp_dir = os.path.join(temp_dir, file_name)
    if not os.path.exists(file_temp_dir):
        os.makedirs(file_temp_dir, exist_ok=True)

    clean_file = os.path.join(temp_dir, f"{file_name}_cleaned_audio.wav")

    clean_audio(file_path, clean_file)
    split_audio(clean_file, file_temp_dir)

    # for each split audio file, perform transcription and diarization
    for split_file in os.listdir(file_temp_dir):
        if split_file.endswith(".wav"):
            split_path = os.path.join(file_temp_dir, split_file)
            find_silences_in_file(split_path, f"{split_file}_silences.json")
            transcribe_file(split_path, f"{split_file}_transcription.json")
            pyannote(split_path, f"{split_file}_pyannote.json")
            segment_audio(split_path, f"{split_file}_transcription.json", f"{split_file}_segments.json")

    # Validate transcriptions

    # construct metadata

    # align and phonetize

    # archive dataset

def main():
    """
    Main function to run the podcast processing pipeline.
    
    Usage:
        python run.py <file_path> [temp_dir]
    
    Args:
        file_path (str): Path to the podcast file (required)
        temp_dir (str): Output directory (optional, defaults to "./output")
    
    Returns:
        None
    """
    if len(sys.argv) < 2:
        print("Usage: python run.py <file_path> [temp_dir]")
        print("  file_path: Path to the podcast file (required)")
        print("  temp_dir:  Output directory (optional, defaults to './output')")
        sys.exit(1)
    
    file_path = sys.argv[1]
    temp_dir = sys.argv[2] if len(sys.argv) > 2 else "./output"

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    process_file(file_path, temp_dir)

    # for podcast in podcasts:
    #     process_file(podcast, temp_dir)

    # generate_metadata(temp_dir)
    # align_and_phonetize()
    # archive_dataset()


if __name__ == "__main__":
    main()