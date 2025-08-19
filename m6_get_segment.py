#!/usr/bin/env python3
"""
Extract specific segments from a _segments.json file for debugging purposes.

Usage:
    python m6_get_segment.py segments.json start_segment end_segment output_prefix

This script:
1. Loads a _segments.json file
2. Extracts segments from start_segment to end_segment (inclusive)
3. Creates a new _segments.json file with only the selected segments
4. Creates a corresponding _segments_raw.json file with raw subsegments (if available)

Arguments:
    segments_json: Path to the input _segments.json file
    start_segment: First segment number to extract (1-based)
    end_segment: Last segment number to extract (1-based)
    output_prefix: Prefix for the output files

The script will create:
    - {output_prefix}_segments.json: New segments file with selected segments
    - {output_prefix}_segments_raw.json: Raw segments file (if original raw file exists)

This is useful for debugging by extracting a smaller subset of segments to analyze.
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any


def load_segments(segments_json_path: Path) -> Dict[str, Any]:
    """Load segments from JSON file."""
    with segments_json_path.open('r', encoding='utf-8') as f:
        return json.load(f)


def renumber_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Renumber segments starting from 1."""
    renumbered_segments = []
    
    for i, segment in enumerate(segments, 1):
        # Copy the segment and update the seg_idx
        renumbered_segment = segment.copy()
        renumbered_segment['seg_idx'] = i
        renumbered_segments.append(renumbered_segment)
    
    return renumbered_segments


def main():
    parser = argparse.ArgumentParser(
        description="Extract specific segments from a _segments.json file for debugging purposes."
    )
    parser.add_argument("segments_json", type=Path, help="Path to the input _segments.json file")
    parser.add_argument("start_segment", type=int, help="First segment number to extract (1-based)")
    parser.add_argument("end_segment", type=int, help="Last segment number to extract (1-based)")
    parser.add_argument("output_prefix", type=str, help="Prefix for the output files")
    
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
    original_audio_path = segments_data.get('audio_path', '')
    
    # Validate segment numbers
    max_segment = len(all_segments)
    if args.end_segment > max_segment:
        raise SystemExit(f"end_segment ({args.end_segment}) exceeds available segments ({max_segment})")
    
    # Extract the requested segments (convert to 0-based indexing)
    start_idx = args.start_segment - 1
    end_idx = args.end_segment  # end_segment is inclusive, so we don't subtract 1
    selected_segments = all_segments[start_idx:end_idx]
    
    print(f"Extracting segments {args.start_segment} to {args.end_segment} ({len(selected_segments)} segments)")
    
    # Renumber the selected segments
    renumbered_segments = renumber_segments(selected_segments)
    
    # Create new segments JSON file
    output_segments_json = Path(f"{args.output_prefix}_segments.json")
    new_segments_data = {
        'segments': renumbered_segments,
        'audio_path': original_audio_path,
        'total_segments': len(renumbered_segments),
        'original_file': str(args.segments_json),
        'extracted_range': {
            'start_segment': args.start_segment,
            'end_segment': args.end_segment,
            'original_total_segments': max_segment
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
        
        # Renumber the raw segments
        raw_renumbered_segments = renumber_segments(raw_selected_segments)
        
        # Create new raw segments JSON file
        output_raw_segments_json = Path(f"{args.output_prefix}_segments_raw.json")
        new_raw_segments_data = {
            'segments': raw_renumbered_segments,
            'audio_path': original_audio_path,
            'total_segments': len(raw_renumbered_segments),
            'original_file': str(original_raw_file),
            'extracted_range': {
                'start_segment': args.start_segment,
                'end_segment': args.end_segment,
                'original_total_segments': len(raw_all_segments)
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
