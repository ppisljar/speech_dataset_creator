from m0_get import get_podcasts
from m1_clean import clean_audio
from m2_silences import find_silences_in_file
from m3_split import split_audio, NoAdequateSilenceError
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

def process_file(file_path, temp_dir="./output", override=False, segment=False, settings=None):
    """
    Process a single podcast file through the pipeline.
    
    Args:
        file_path (str): Path to the podcast file.
        temp_dir (str): Temporary directory for processing.
        override (bool): Whether to override existing output files. Defaults to False.
        segment (bool): Whether to enable segmentation. Defaults to False.
        settings (dict): Project settings dictionary. Defaults to None.
    
    Returns:
        None
    """
    file_name = os.path.basename(file_path)
    print(f"Processing file: {file_name}")
    
    # Initialize settings if not provided
    if settings is None:
        settings = {}
    
    # Show silence detection settings being used
    silence_thresh = settings.get('silenceThreshold', -30)
    min_silence_len = settings.get('minSilenceLength', 100)
    max_speakers = settings.get('maxSpeakers', 0)
    silence_pad = settings.get('silencePad', 50)
    transcription_language = settings.get('language', 'sl')
    print(f"Silence detection settings: threshold={silence_thresh}dB, min_length={min_silence_len}ms")
    print(f"Silence padding: {silence_pad}ms")
    print(f"Transcription language: {transcription_language}")
    if max_speakers > 0:
        print(f"Speaker diarization settings: max_speakers={max_speakers}")
    else:
        print(f"Speaker diarization settings: max_speakers=auto")

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
        try:
            # Extract silence settings from project config
            silence_thresh = settings.get('silenceThreshold', -35) if settings else -35
            min_silence_len = settings.get('minSilenceLength', 500) / 1000.0 if settings else 0.5  # Convert ms to seconds
            print(f"[info] Split settings: silence_db={silence_thresh}dB, min_silence_length={min_silence_len}s")
            
            split_audio(clean_file, file_temp_dir, silence_db=silence_thresh, silence_min=min_silence_len)
        except NoAdequateSilenceError as e:
            print(f"Error: {e}")
            print(f"Skipping file {file_name} due to splitting failure.")
            return False

    # for each split audio file, perform transcription and diarization
    split_count = sum(1 for f in os.listdir(file_temp_dir) if f.endswith(".wav"))
    
    # If no wav files were created (splitting failed), return False
    if split_count == 0:
        print(f"No audio files found after splitting. Skipping further processing for {file_name}.")
        return False
    
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
                # Extract silence detection settings
                silence_thresh = settings.get('silenceThreshold', -30)
                min_silence_len = settings.get('minSilenceLength', 100)
                find_silences_in_file(split_path, silence_file, min_silence_len, silence_thresh)

            if not override and os.path.exists(transcription_file):
                print(f"Transcription file already exists, skipping transcription.")
            else:
                # Transcribe the split audio file
                print(f"Transcribing {split_path}")
                transcribe_file(split_path, transcription_file, language=transcription_language)

            if not override and os.path.exists(pyannote_file + '.csv'):
                print(f"Pyannote file already exists, skipping pyannote processing.")
            else:
                # Run pyannote on the split audio file
                print(f"Running pyannote on {split_path}")
                # Determine max_speakers parameter - if 0, use None (auto-detect)
                max_speakers_param = max_speakers if max_speakers > 0 else None
                pyannote(split_path, pyannote_file, max_speakers=max_speakers_param, speaker_db=speaker_db_file)

            if not override and os.path.exists(threedspeaker_file + '.csv'):
                print(f"3D-Speaker file already exists, skipping 3D-Speaker processing.")
            else:
                # Run 3D-Speaker on the split audio file
                print(f"Running 3D-Speaker on {split_path}")
                try:
                    from m5_3dspeaker import threed_speaker_diarize
                    # Determine max_speakers parameter - if 0, use None (auto-detect)
                    max_speakers_param = max_speakers if max_speakers > 0 else None
                    threed_speaker_diarize(split_path, output_file=threedspeaker_file, max_speakers=max_speakers_param)
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
                    # Determine max_speakers parameter - if 0, use None (auto-detect)
                    max_speakers_param = max_speakers if max_speakers > 0 else None
                    wespeaker_diarize(split_path, output_file=wespeaker_file, max_speakers=max_speakers_param)
                except ImportError as e:
                    print(f"Warning: Could not import WeSpeaker: {e}")
                except Exception as e:
                    print(f"Error running WeSpeaker: {e}")

            if not override and os.path.exists(segments_file):
                print(f"Segments file already exists, skipping segmentation.")
            else:
                # Segment the audio based on transcription
                print(f"Segmenting {split_path}")
                segment_audio(split_path, transcription_file, segments_file, silence_pad_ms=silence_pad)

            if segment:
                # check if segmenting was already done (files exist inside {split_path}_segments)
                segments_output_path = f"{split_path}_segments"
                if os.path.exists(segments_output_path):
                    print(f"Segments already exist, skipping segmentation.")
                else:
                    # If segmentation is enabled, process the segments
                    print(f"Segmenting {split_path} with segments file {segments_file}")
                    # Extract subsegment settings from project config
                    build_subsegments = settings.get('buildSubsegments', True) if settings else True
                    join_subsegments = settings.get('joinSubsegments', False) if settings else False
                    generate_segments(segments_file, split_path, segments_output_path, silence_pad_ms=silence_pad, build_subsegments=build_subsegments, join_subsegments=join_subsegments)

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