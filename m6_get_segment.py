#!/usr/bin/env python3
"""
Extract specific segments from a _segments.json file for debugging purposes.

Usage:
    python m6_get_segment.py segments.json start_seg_id end_seg_id output_prefix

This script:
1. Loads a _segments.json file
2. Extracts segments with seg_idx from start_seg_id to end_seg_id (inclusive)
3. Creates a new _segments.json file with only the selected segments
4. Creates a corresponding _segments_raw.json file with raw subsegments (if available)

Arguments:
    segments_json: Path to the input _segments.json file
    start_segment: First segment ID (seg_idx) to extract
    end_segment: Last segment ID (seg_idx) to extract
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
    parser.add_argument("start_segment", type=int, help="First segment ID (seg_idx) to extract")
    parser.add_argument("end_segment", type=int, help="Last segment ID (seg_idx) to extract")
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
            'original_total_segments': len(all_segments)
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
        
        # Extract the same range from raw segments by seg_idx
        raw_selected_segments = []
        for segment in raw_all_segments:
            seg_idx = segment['seg_idx']
            if args.start_segment <= seg_idx <= args.end_segment:
                raw_selected_segments.append(segment)
        
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
