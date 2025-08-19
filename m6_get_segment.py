#!/usr/bin/env python3
"""
Extract specific segments from a _segments.json file and combine with related data.

Usage:
    python m6_get_segment.py segments.json start_seg_id end_seg_id output_file

This script:
1. Loads a _segments.json file
2. Extracts segments with seg_idx from start_seg_id to end_seg_id (inclusive)
3. Loads corresponding raw segments, silences, and transcription data
4. Creates a single comprehensive JSON file with all related data for the selected segments

Arguments:
    segments_json: Path to the input _segments.json file
    start_segment: First segment ID (seg_idx) to extract
    end_segment: Last segment ID (seg_idx) to extract
    output_file: Path for the output JSON file

The script will create a single JSON file containing:
    - segments: Selected segments with their main and subsegment data
    - raw_segments: Raw segments (if available) for the same range
    - silences: All silence intervals from the original audio
    - transcriptions: Token-level transcription data within the time range of selected segments
    - metadata: Information about the extraction and original files

This is useful for debugging by having all related data for a segment range in one file.
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load JSON data from file."""
    if not file_path.exists():
        return None
    try:
        with file_path.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"Warning: Could not load {file_path}: {e}")
        return None


def get_time_range_from_segments(segments: List[Dict[str, Any]]) -> tuple:
    """Get the overall time range (start_ms, end_ms) from a list of segments."""
    if not segments:
        return (0, 0)
    
    start_times = []
    end_times = []
    
    for segment in segments:
        if 'main' in segment:
            start_times.append(segment['main']['start_ms'])
            end_times.append(segment['main']['end_ms'])
        
        # Also check subsegments for more precise timing
        if 'subs' in segment:
            for sub in segment['subs']:
                start_times.append(sub['start_ms'])
                end_times.append(sub['end_ms'])
    
    return (min(start_times), max(end_times)) if start_times and end_times else (0, 0)


def filter_transcription_tokens(transcription_data: Dict[str, Any], start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
    """Filter transcription tokens to only include those within the specified time range."""
    if not transcription_data or 'tokens' not in transcription_data:
        return []
    
    filtered_tokens = []
    for token in transcription_data['tokens']:
        token_start = token.get('start_ms', 0)
        token_end = token.get('end_ms', 0)
        
        # Include token if it overlaps with the time range
        if (token_start <= end_ms and token_end >= start_ms):
            filtered_tokens.append(token)
    
    return filtered_tokens


def filter_silences_in_range(silences: List[List[float]], start_ms: int, end_ms: int) -> List[List[float]]:
    """Filter silences to only include those that overlap with the specified time range."""
    if not silences:
        return []
    
    filtered_silences = []
    for silence in silences:
        silence_start = silence[0]
        silence_end = silence[1]
        
        # Include silence if it overlaps with the time range
        if (silence_start <= end_ms and silence_end >= start_ms):
            filtered_silences.append(silence)
    
    return filtered_silences


def main():
    parser = argparse.ArgumentParser(
        description="Extract specific segments and combine with related data into a single JSON file."
    )
    parser.add_argument("segments_json", type=Path, help="Path to the input _segments.json file")
    parser.add_argument("start_segment", type=int, help="First segment ID (seg_idx) to extract")
    parser.add_argument("end_segment", type=int, help="Last segment ID (seg_idx) to extract")
    parser.add_argument("output_file", type=str, help="Path for the output JSON file")
    
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
    segments_data = load_json_file(args.segments_json)
    if not segments_data:
        raise SystemExit(f"Could not load segments file: {args.segments_json}")
    
    all_segments = segments_data['segments']
    original_audio_path = segments_data.get('audio_path', '')
    
    # Validate segment numbers - check available seg_idx values
    available_seg_ids = [seg['seg_idx'] for seg in all_segments]
    min_seg_id = min(available_seg_ids) if available_seg_ids else 1
    max_seg_id = max(available_seg_ids) if available_seg_ids else 0
    
    if args.start_segment < min_seg_id or args.start_segment > max_seg_id:
        raise SystemExit(f"start_segment ({args.start_segment}) not found. Available seg_idx range: {min_seg_id}-{max_seg_id}")
    
    if args.end_segment < min_seg_id or args.end_segment > max_seg_id:
        raise SystemExit(f"end_segment ({args.end_segment}) not found. Available seg_idx range: {min_seg_id}-{max_seg_id}")
    
    # Extract the requested segments by seg_idx (not array position)
    selected_segments = []
    for segment in all_segments:
        seg_idx = segment['seg_idx']
        if args.start_segment <= seg_idx <= args.end_segment:
            selected_segments.append(segment)
    
    if not selected_segments:
        raise SystemExit(f"No segments found with seg_idx between {args.start_segment} and {args.end_segment}")
    
    print(f"Extracting segments with seg_idx {args.start_segment} to {args.end_segment} ({len(selected_segments)} segments)")
    
    # Get time range for the selected segments
    start_ms, end_ms = get_time_range_from_segments(selected_segments)
    print(f"Time range: {start_ms}ms - {end_ms}ms")
    
    # Load raw segments if available
    raw_segments = []
    original_raw_file = Path(str(args.segments_json).replace('_segments.json', '_segments_raw.json'))
    if original_raw_file.exists():
        print(f"Loading raw segments from {original_raw_file}")
        raw_segments_data = load_json_file(original_raw_file)
        if raw_segments_data:
            raw_all_segments = raw_segments_data['segments']
            # Extract the same range from raw segments by seg_idx
            for segment in raw_all_segments:
                seg_idx = segment['seg_idx']
                if args.start_segment <= seg_idx <= args.end_segment:
                    raw_segments.append(segment)
            print(f"Found {len(raw_segments)} raw segments")
    else:
        print(f"Raw segments file not found: {original_raw_file}")
    
    # Load silences
    silences = []
    silences_file = Path(str(args.segments_json).replace('_segments.json', '_silences.json'))
    if silences_file.exists():
        print(f"Loading silences from {silences_file}")
        silences_data = load_json_file(silences_file)
        if silences_data:
            # Filter silences to the time range of selected segments
            silences = filter_silences_in_range(silences_data, start_ms, end_ms)
            print(f"Found {len(silences)} silences in range")
    else:
        print(f"Silences file not found: {silences_file}")
    
    # Load transcription
    transcription_tokens = []
    transcription_file = Path(str(args.segments_json).replace('_segments.json', '_transcription.json'))
    if transcription_file.exists():
        print(f"Loading transcription from {transcription_file}")
        transcription_data = load_json_file(transcription_file)
        if transcription_data:
            # Filter transcription tokens to the time range of selected segments
            transcription_tokens = filter_transcription_tokens(transcription_data, start_ms, end_ms)
            print(f"Found {len(transcription_tokens)} transcription tokens in range")
    else:
        print(f"Transcription file not found: {transcription_file}")
    
    # Create comprehensive output data
    output_data = {
        'metadata': {
            'original_segments_file': str(args.segments_json),
            'extracted_range': {
                'start_segment_id': args.start_segment,
                'end_segment_id': args.end_segment,
                'start_ms': start_ms,
                'end_ms': end_ms,
                'duration_ms': end_ms - start_ms
            },
            'original_total_segments': len(all_segments),
            'extracted_segments_count': len(selected_segments),
            'audio_path': original_audio_path,
            'files_included': {
                'segments': True,
                'raw_segments': len(raw_segments) > 0,
                'silences': len(silences) > 0,
                'transcriptions': len(transcription_tokens) > 0
            }
        },
        'segments': selected_segments,
        'raw_segments': raw_segments,
        'silences': silences,
        'transcription_tokens': transcription_tokens
    }
    
    # Write the comprehensive output file
    output_path = Path(args.output_file)
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Comprehensive data file created: {output_path}")
    print("Done!")


if __name__ == "__main__":
    main()
