#!/usr/bin/env python3
"""
Extract specific segments from a _segments.json file and create a new output file.

Usage:
    python m6_get_segment.py segments.json start_segment end_segment output_audio.wav

This script:
1. Loads a _segments.json file
2. Extracts segments from start_segment to end_segment (inclusive)
3. Merges the audio ranges and exports to output_audio.wav
4. Creates a new _segments.json file with only the selected segments
5. Creates a corresponding _segments_raw.json file with raw subsegments

Arguments:
    segments_json: Path to the input _segments.json file
    start_segment: First segment number to extract (1-based)
    end_segment: Last segment number to extract (1-based)
    output_audio: Path for the output audio file (.wav)

The script will also create:
    - {output_audio}_segments.json: New segments file with selected segments
    - {output_audio}_segments_raw.json: Raw segments file (if original raw file exists)
"""

import argparse
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any


def load_segments(segments_json_path: Path) -> Dict[str, Any]:
    """Load segments from JSON file."""
    with segments_json_path.open('r', encoding='utf-8') as f:
        return json.load(f)


def extract_audio_range(input_audio: Path, start_ms: int, end_ms: int, output_audio: Path) -> None:
    """Extract audio range using ffmpeg."""
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    
    start_sec = start_ms / 1000.0
    duration_sec = (end_ms - start_ms) / 1000.0
    
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start_sec:.3f}",
        "-t", f"{duration_sec:.3f}",
        "-i", str(input_audio),
        "-vn", "-c:a", "pcm_s16le",
        "-ar", "16000",
        str(output_audio)
    ]
    
    subprocess.run(cmd, check=True)


def adjust_segment_times(segments: List[Dict[str, Any]], time_offset_ms: int) -> List[Dict[str, Any]]:
    """Adjust segment times by subtracting the time offset."""
    adjusted_segments = []
    
    for i, segment in enumerate(segments, 1):
        # Adjust main segment
        main_seg = segment['main'].copy()
        main_seg['start_ms'] -= time_offset_ms
        main_seg['end_ms'] -= time_offset_ms
        
        # Adjust subsegments
        adjusted_subs = []
        for sub_seg in segment['subs']:
            adjusted_sub = sub_seg.copy()
            adjusted_sub['start_ms'] -= time_offset_ms
            adjusted_sub['end_ms'] -= time_offset_ms
            adjusted_subs.append(adjusted_sub)
        
        adjusted_segment = {
            'seg_idx': i,  # Renumber segments starting from 1
            'main': main_seg,
            'subs': adjusted_subs
        }
        
        adjusted_segments.append(adjusted_segment)
    
    return adjusted_segments


def main():
    parser = argparse.ArgumentParser(
        description="Extract specific segments from a _segments.json file and create a new output file."
    )
    parser.add_argument("segments_json", type=Path, help="Path to the input _segments.json file")
    parser.add_argument("start_segment", type=int, help="First segment number to extract (1-based)")
    parser.add_argument("end_segment", type=int, help="Last segment number to extract (1-based)")
    parser.add_argument("output_audio", type=Path, help="Path for the output audio file (.wav)")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.segments_json.exists():
        raise SystemExit(f"Segments file not found: {args.segments_json}")
    
    if args.start_segment < 1:
        raise SystemExit("start_segment must be >= 1")
        
    if args.end_segment < args.start_segment:
        raise SystemExit("end_segment must be >= start_segment")
    
    # Load segments data
    print(f"Loading segments from {args.segments_json}")
    segments_data = load_segments(args.segments_json)
    
    all_segments = segments_data['segments']
    original_audio_path = Path(segments_data['audio_path'])
    
    if not original_audio_path.exists():
        raise SystemExit(f"Original audio file not found: {original_audio_path}")
    
    # Validate segment numbers
    max_segment = len(all_segments)
    if args.end_segment > max_segment:
        raise SystemExit(f"end_segment ({args.end_segment}) exceeds available segments ({max_segment})")
    
    # Extract the requested segments (convert to 0-based indexing)
    start_idx = args.start_segment - 1
    end_idx = args.end_segment  # end_segment is inclusive, so we don't subtract 1
    selected_segments = all_segments[start_idx:end_idx]
    
    print(f"Extracting segments {args.start_segment} to {args.end_segment} ({len(selected_segments)} segments)")
    
    # Calculate the time range to extract
    first_segment = selected_segments[0]
    last_segment = selected_segments[-1]
    
    # Use the earliest start time and latest end time
    start_ms = first_segment['main']['start_ms']
    end_ms = last_segment['main']['end_ms']
    
    # Check if any subsegments extend beyond the main segment boundaries
    for segment in selected_segments:
        for sub_seg in segment['subs']:
            start_ms = min(start_ms, sub_seg['start_ms'])
            end_ms = max(end_ms, sub_seg['end_ms'])
    
    print(f"Extracting audio from {start_ms}ms to {end_ms}ms ({(end_ms - start_ms) / 1000:.2f} seconds)")
    
    # Extract the audio
    extract_audio_range(original_audio_path, start_ms, end_ms, args.output_audio)
    print(f"Audio extracted to {args.output_audio}")
    
    # Adjust segment times to start from 0
    adjusted_segments = adjust_segment_times(selected_segments, start_ms)
    
    # Create new segments JSON file
    output_segments_json = Path(str(args.output_audio).replace('.wav', '_segments.json'))
    new_segments_data = {
        'segments': adjusted_segments,
        'audio_path': str(args.output_audio),
        'total_segments': len(adjusted_segments),
        'original_file': str(args.segments_json),
        'original_audio': str(original_audio_path),
        'extracted_range': {
            'start_segment': args.start_segment,
            'end_segment': args.end_segment,
            'start_ms': start_ms,
            'end_ms': end_ms
        }
    }
    
    with output_segments_json.open('w', encoding='utf-8') as f:
        json.dump(new_segments_data, f, indent=2, ensure_ascii=False)
    
    print(f"New segments file created: {output_segments_json}")
    
    # Try to create corresponding raw segments file if original exists
    original_raw_file = Path(str(args.segments_json).replace('_segments.json', '_segments_raw.json'))
    if original_raw_file.exists():
        print(f"Found raw segments file: {original_raw_file}")
        
        # Load raw segments
        raw_segments_data = load_segments(original_raw_file)
        raw_all_segments = raw_segments_data['segments']
        
        # Extract the same range from raw segments
        raw_selected_segments = raw_all_segments[start_idx:end_idx]
        
        # Adjust times for raw segments
        raw_adjusted_segments = adjust_segment_times(raw_selected_segments, start_ms)
        
        # Create new raw segments JSON file
        output_raw_segments_json = Path(str(args.output_audio).replace('.wav', '_segments_raw.json'))
        new_raw_segments_data = {
            'segments': raw_adjusted_segments,
            'audio_path': str(args.output_audio),
            'total_segments': len(raw_adjusted_segments),
            'original_file': str(original_raw_file),
            'original_audio': str(original_audio_path),
            'extracted_range': {
                'start_segment': args.start_segment,
                'end_segment': args.end_segment,
                'start_ms': start_ms,
                'end_ms': end_ms
            }
        }
        
        with output_raw_segments_json.open('w', encoding='utf-8') as f:
            json.dump(new_raw_segments_data, f, indent=2, ensure_ascii=False)
        
        print(f"New raw segments file created: {output_raw_segments_json}")
    else:
        print(f"Raw segments file not found: {original_raw_file}, skipping")
    
    print("Done!")


if __name__ == "__main__":
    main()
