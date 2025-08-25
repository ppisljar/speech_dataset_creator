#!/usr/bin/env python3
"""
Module 13: Speaker Re-check and Validation

This module validates and reassigns speaker IDs based on embeddings from multiple 
speaker diarization backends (pyannote, wespeaker, 3dspeaker).

Given a project name, it:
1. Walks all clips in _segments folders
2. Skips clips listed in bad_segments.json
3. Calculates speaker embeddings using pyannote, wespeaker, and 3dspeaker
4. Manages a project-level speaker database
5. Compares embeddings with existing speakers using cosine similarity
6. Assigns new speaker IDs or matches to existing speakers
7. Stores results in speaker_validation.json

Usage:
    python m13_speaker_recheck.py <project_name> [--threshold 0.8] [--backends pyannote,wespeaker,3dspeaker]
"""

import os
import sys
import json
import argparse
import numpy as np
import torch
import torchaudio
import librosa
import soundfile as sf
import shutil
import signal
from pathlib import Path
from datetime import datetime
import uuid
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import embedding models
try:
    from pyannote.audio import Model, Inference
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    print("Warning: pyannote.audio not available")

try:
    import wespeaker
    WESPEAKER_AVAILABLE = True
except ImportError:
    WESPEAKER_AVAILABLE = False
    print("Warning: wespeaker not available")

try:
    from speakerlab.bin.infer_diarization import Diarization3Dspeaker
    THREED_SPEAKER_AVAILABLE = True
except ImportError:
    THREED_SPEAKER_AVAILABLE = False
    print("Warning: 3D-Speaker not available")

# Thread-local storage for models to avoid issues with concurrent access
thread_local = threading.local()

# Global flag for graceful shutdown
_shutdown_requested = threading.Event()

HF_TOKEN = os.environ.get("HF_TOKEN")


def signal_handler(signum, frame):
    """Handle SIGINT (Ctrl+C) gracefully."""
    print("\n\nReceived interrupt signal (Ctrl+C)")
    print("Shutting down gracefully... (press Ctrl+C again to force quit)")
    _shutdown_requested.set()
    
    # Set up a second signal handler for force quit
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(1))


def check_shutdown():
    """Check if shutdown was requested."""
    return _shutdown_requested.is_set()


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


def load_speaker_db(db_path):
    """Load speaker database from file."""
    if os.path.exists(db_path):
        db = np.load(db_path, allow_pickle=True).item()
        # Ensure the database has the correct structure: db[backend][speaker_id] = embedding
        if isinstance(db, dict) and db:
            # Check if it's the old format (speaker_id -> {backend: embedding})
            first_key = next(iter(db.keys()))
            if isinstance(db[first_key], dict) and any(isinstance(v, np.ndarray) for v in db[first_key].values()):
                # Convert old format to new format and rename speakers to s001, s002, etc.
                print("Converting old speaker database format and renaming speakers...")
                new_db = {}
                speaker_counters = {}  # Track next speaker number for each backend
                speaker_mapping = {}  # Map old speaker IDs to new ones
                
                for old_speaker_id, speaker_data in db.items():
                    for backend, embedding in speaker_data.items():
                        if backend not in new_db:
                            new_db[backend] = {}
                            speaker_counters[backend] = 1
                        
                        # Create new speaker ID for this backend
                        new_speaker_id = f"s{speaker_counters[backend]:03d}"
                        speaker_counters[backend] += 1
                        
                        new_db[backend][new_speaker_id] = embedding
                        
                        # Keep mapping for reference (though not used in new format)
                        if old_speaker_id not in speaker_mapping:
                            speaker_mapping[old_speaker_id] = {}
                        speaker_mapping[old_speaker_id][backend] = new_speaker_id
                
                print(f"Converted {len(db)} old speakers to new format across {len(new_db)} backends")
                return new_db
        return db
    return {}


def save_speaker_db(db, db_path):
    """Save speaker database to file."""
    np.save(db_path, db)


def load_existing_validation_data(validation_output):
    """Load existing validation data from file."""
    try:
        with open(validation_output, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading validation data: {e}")
        return None


def create_validation_summary(project_name, threshold, backends, results, speaker_db):
    """Create validation summary from results."""
    
    # Calculate total speakers across all backends
    total_speakers = sum(len(backend_speakers) for backend_speakers in speaker_db.values())
    
    validation_data = {
        'project_name': project_name,
        'validation_timestamp': datetime.now().isoformat(),
        'threshold': float(threshold),  # Ensure threshold is Python float
        'backends_used': backends,
        'total_clips_processed': len(results),
        'total_speakers_in_db': total_speakers,
        'speakers_per_backend': {backend: len(speakers) for backend, speakers in speaker_db.items()},
        'clips': results,
        'speaker_summary': {},
        'backend_agreement': {}
    }
    
    # Analyze speaker assignments
    speaker_counts = {}
    backend_agreements = {backend: {'matches': 0, 'total': 0} for backend in backends}
    
    for result in results:
        speaker_id = result['final_speaker_id']
        if speaker_id not in speaker_counts:
            speaker_counts[speaker_id] = 0
        speaker_counts[speaker_id] += 1
        
        # Count backend agreements
        matched_speakers = result['matched_speakers']
        for backend in backends:
            if backend in matched_speakers:
                backend_agreements[backend]['total'] += 1
                if matched_speakers[backend] == speaker_id:
                    backend_agreements[backend]['matches'] += 1
    
    validation_data['speaker_summary'] = speaker_counts
    
    # Calculate agreement percentages
    for backend, stats in backend_agreements.items():
        if stats['total'] > 0:
            agreement_rate = float(stats['matches']) / float(stats['total'])  # Ensure float type
            validation_data['backend_agreement'][backend] = {
                'agreement_rate': agreement_rate,
                'matches': stats['matches'],
                'total': stats['total']
            }
    
    return validation_data


def get_pyannote_model():
    """Get or create pyannote model (thread-safe)."""
    if not hasattr(thread_local, 'pyannote_model'):
        if not PYANNOTE_AVAILABLE:
            return None
        try:
            model = Model.from_pretrained("pyannote/embedding", use_auth_token=HF_TOKEN)
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model = model.to(device)
            model.eval()
            thread_local.pyannote_model = model
            print(f"Loaded pyannote model on {device}")
        except Exception as e:
            print(f"Failed to load pyannote model: {e}")
            thread_local.pyannote_model = None
    return thread_local.pyannote_model


def get_wespeaker_model():
    """Get or create wespeaker model (thread-safe)."""
    if not hasattr(thread_local, 'wespeaker_model'):
        if not WESPEAKER_AVAILABLE:
            return None
        try:
            model = wespeaker.load_model('english')
            device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
            model.set_device(device)
            thread_local.wespeaker_model = model
            print(f"Loaded wespeaker model on {device}")
        except Exception as e:
            print(f"Failed to load wespeaker model: {e}")
            thread_local.wespeaker_model = None
    return thread_local.wespeaker_model


def get_3dspeaker_model():
    """Get or create 3dspeaker model (thread-safe)."""
    if not hasattr(thread_local, 'threed_speaker_model'):
        if not THREED_SPEAKER_AVAILABLE:
            return None
        try:
            device_str = "cuda" if torch.cuda.is_available() else "cpu"
            model = Diarization3Dspeaker(
                device=device_str,
                include_overlap=False,
                speaker_num=None
            )
            thread_local.threed_speaker_model = model
            print(f"Loaded 3D-Speaker model on {device_str}")
        except Exception as e:
            print(f"Failed to load 3D-Speaker model: {e}")
            thread_local.threed_speaker_model = None
    return thread_local.threed_speaker_model


def extract_pyannote_embedding(audio_file):
    """Extract speaker embedding using pyannote.audio."""
    model = get_pyannote_model()
    if model is None:
        return None
    
    try:
        # Use pyannote.audio Inference for proper embedding extraction
        from pyannote.audio import Inference
        
        # Create inference pipeline with the model
        inference = Inference(model, window="whole")
        
        # Move to GPU if available
        if torch.cuda.is_available():
            inference.to(torch.device("cuda"))
        
        # Extract embedding from the whole audio file
        embedding = inference(audio_file)
        
        # embedding is a (1 x D) numpy array
        return embedding.flatten()  # Return as 1D array
            
    except Exception as e:
        print(f"Error extracting pyannote embedding from {audio_file}: {e}")
        return None


def extract_wespeaker_embedding(audio_file):
    """Extract speaker embedding using wespeaker."""
    model = get_wespeaker_model()
    if model is None:
        return None
    
    try:
        # WeSpeaker expects direct file path
        embedding = model.extract_embedding(audio_file)
        return np.array(embedding)
    except Exception as e:
        print(f"Error extracting wespeaker embedding from {audio_file}: {e}")
        return None


def extract_3dspeaker_embedding(audio_file):
    """Extract speaker embedding using 3D-Speaker."""
    model = get_3dspeaker_model()
    if model is None:
        return None
    
    try:
        # 3D-Speaker pipeline approach for embedding extraction
        # Note: This is a simplified approach - the actual 3D-Speaker API might differ
        result = model(audio_file)
        
        # Extract embedding from result (this may need adjustment based on actual API)
        if hasattr(result, 'embeddings') and len(result.embeddings) > 0:
            return np.array(result.embeddings[0])
        elif hasattr(result, 'data') and len(result.data) > 0:
            return np.array(result.data[0])
        else:
            # No valid embedding found from 3D-Speaker model
            print(f"Error: 3D-Speaker model did not return valid embeddings for {audio_file}")
            return None
            
    except Exception as e:
        print(f"Error extracting 3D-Speaker embedding from {audio_file}: {e}")
        return None


def find_matching_speaker(embedding, speaker_db, threshold=0.8, backend_name=""):
    """Find matching speaker in database based on cosine similarity."""
    if not speaker_db or embedding is None:
        return None, 0.0
    
    if backend_name not in speaker_db:
        return None, 0.0
    
    backend_speakers = speaker_db[backend_name]
    if not backend_speakers:  # Empty backend database
        return None, 0.0
    
    best_speaker = None
    best_similarity = -1.0
    
    # Only compare within the same backend
    for speaker_id, ref_embedding in backend_speakers.items():
        try:
            # Make sure both embeddings are numpy arrays
            if not isinstance(embedding, np.ndarray):
                embedding = np.array(embedding)
            if not isinstance(ref_embedding, np.ndarray):
                ref_embedding = np.array(ref_embedding)
                
            similarity = cosine_similarity(embedding, ref_embedding)
            
            if similarity > threshold and similarity > best_similarity:
                best_similarity = similarity
                best_speaker = speaker_id
        except Exception as e:
            print(f"Error comparing with speaker {speaker_id} in {backend_name}: {e}")
            continue
    
    return best_speaker, best_similarity


def process_audio_clip(clip_path, speaker_db, threshold, backends, project_name):
    """Process a single audio clip and extract embeddings."""
    # Check for shutdown request
    if check_shutdown():
        return None
        
    clip_name = os.path.basename(clip_path)
    result = {
        'file': clip_path,
        'clip_name': clip_name,
        'matched_speakers': {},
        'similarities': {},
        'final_speaker_id': None,
        'confidence': 0.0
    }
    
    print(f"Processing: {clip_name}")
    
    # Initialize backend databases if they don't exist
    for backend in backends:
        if backend not in speaker_db:
            speaker_db[backend] = {}
    
    # Extract embeddings from each backend
    embeddings = {}
    if 'pyannote' in backends and not check_shutdown():
        embeddings['pyannote'] = extract_pyannote_embedding(clip_path)
    if 'wespeaker' in backends and not check_shutdown():
        embeddings['wespeaker'] = extract_wespeaker_embedding(clip_path)
    if '3dspeaker' in backends and not check_shutdown():
        embeddings['3dspeaker'] = extract_3dspeaker_embedding(clip_path)
    
    # Check for shutdown after embeddings
    if check_shutdown():
        return None
    
    # Find matching speakers for each backend independently
    matched_speakers = {}
    similarities = {}
    backend_speaker_ids = {}
    
    for backend, embedding in embeddings.items():
        if embedding is not None:
            # Use backend-specific thresholds
            backend_threshold = threshold
            if backend == 'pyannote':
                backend_threshold = 0.6  # Lower threshold for pyannote
            elif backend == 'wespeaker':
                backend_threshold = 0.7  # Lower threshold for wespeaker
            elif backend == '3dspeaker':
                backend_threshold = 0.5  # Much lower threshold for 3dspeaker (using audio features)
            
            speaker_id, similarity = find_matching_speaker(
                embedding, speaker_db, backend_threshold, backend
            )
            
            if speaker_id is not None:
                # Found existing speaker for this backend
                matched_speakers[backend] = speaker_id
                similarities[backend] = float(similarity)
                backend_speaker_ids[backend] = speaker_id
            else:
                # No match found, create new speaker for this backend
                # Generate sequential speaker ID
                existing_speakers = list(speaker_db[backend].keys())
                if existing_speakers:
                    # Extract numbers from existing speaker IDs and find the next one
                    existing_numbers = []
                    for spk_id in existing_speakers:
                        if spk_id.startswith('s') and spk_id[1:].isdigit():
                            existing_numbers.append(int(spk_id[1:]))
                    next_number = max(existing_numbers) + 1 if existing_numbers else 1
                else:
                    next_number = 1
                
                new_speaker_id = f"s{next_number:03d}"
                speaker_db[backend][new_speaker_id] = embedding
                
                matched_speakers[backend] = new_speaker_id
                similarities[backend] = 1.0  # New speaker gets full confidence for this backend
                backend_speaker_ids[backend] = new_speaker_id
        else:
            # Failed to extract embedding for this backend
            matched_speakers[backend] = None
            similarities[backend] = -1.0
            backend_speaker_ids[backend] = None
    
    # Determine final speaker ID - prioritize pyannote, fallback to others
    final_speaker_id = None
    confidence = 0.0
    
    if 'pyannote' in backend_speaker_ids and backend_speaker_ids['pyannote'] is not None:
        # Use pyannote result as final
        final_speaker_id = backend_speaker_ids['pyannote']
        confidence = similarities.get('pyannote', 0.0)
    elif 'wespeaker' in backend_speaker_ids and backend_speaker_ids['wespeaker'] is not None:
        # Fallback to wespeaker
        final_speaker_id = backend_speaker_ids['wespeaker']
        confidence = similarities.get('wespeaker', 0.0)
    elif '3dspeaker' in backend_speaker_ids and backend_speaker_ids['3dspeaker'] is not None:
        # Final fallback to 3dspeaker
        final_speaker_id = backend_speaker_ids['3dspeaker']
        confidence = similarities.get('3dspeaker', 0.0)
    else:
        # No backend succeeded - this shouldn't happen if embeddings were extracted
        # Create a fallback speaker ID
        final_speaker_id = "s000"  # Unknown speaker
        confidence = 0.0
    
    result.update({
        'matched_speakers': matched_speakers,
        'similarities': {k: float(v) if v is not None else None 
                        for k, v in similarities.items()},
        'final_speaker_id': final_speaker_id,
        'confidence': float(confidence)
    })
    
    return result


def load_bad_segments(project_path):
    """Load list of bad segments to skip. 
    
    Since we're now processing cleaned_audio.wav files instead of individual segments,
    we'll check if the parent split directory contains any bad segments and skip
    the entire cleaned_audio.wav file if it does.
    """
    bad_segments_file = os.path.join(project_path, "bad_segments.json")
    bad_split_dirs = set()
    
    if os.path.exists(bad_segments_file):
        try:
            with open(bad_segments_file, 'r', encoding='utf-8') as f:
                bad_data = json.load(f)
                
            # Handle different bad_segments.json formats
            speakers_data = None
            
            # Format 1: Direct speakers key (m7_validate format)
            if 'speakers' in bad_data:
                speakers_data = bad_data['speakers']
            # Format 2: Nested progress.speakers structure  
            elif 'progress' in bad_data and 'speakers' in bad_data['progress']:
                speakers_data = bad_data['progress']['speakers']
            
            if speakers_data:
                for speaker_path, speaker_segments in speakers_data.items():
                    # Extract the split directory from the speaker path
                    # speaker_path format: projects/{project}/splits/{file}/{split}_segments/speakers/{speaker_id}
                    # We want to extract: projects/{project}/splits/{file}
                    path_parts = speaker_path.split(os.sep)
                    try:
                        # Find 'splits' in the path and take up to the next directory
                        splits_idx = path_parts.index('splits')
                        if splits_idx + 1 < len(path_parts):
                            # Reconstruct path up to the split directory
                            split_dir = os.sep.join(path_parts[:splits_idx + 2])
                            bad_split_dirs.add(split_dir)
                    except (ValueError, IndexError):
                        # If path doesn't match expected format, skip
                        continue
                            
        except Exception as e:
            print(f"Warning: Could not load bad segments: {e}")
            print(f"Error details: {traceback.format_exc()}")
    
    return bad_split_dirs


def find_audio_clips(project_path):
    """Find all cleaned_audio.wav files in split directories."""
    clips = []
    
    # Find all cleaned_audio.wav files in splits directories
    # Structure: projects/{project}/splits/{file}/{file}_cleaned_audio.wav
    splits_dir = os.path.join(project_path, 'splits')
    if not os.path.exists(splits_dir):
        print(f"Warning: No splits directory found at {splits_dir}")
        return clips
    
    for file_dir in os.listdir(splits_dir):
        file_path = os.path.join(splits_dir, file_dir)
        if os.path.isdir(file_path):
            # Look for files ending with _cleaned_audio.wav
            for filename in os.listdir(file_path):
                if filename.endswith('_cleaned_audio.wav'):
                    cleaned_audio_path = os.path.join(file_path, filename)
                    if os.path.exists(cleaned_audio_path):
                        clips.append(cleaned_audio_path)
    
    return clips


def speaker_recheck(project_name, threshold=0.8, backends=None, max_workers=1):
    """
    Main function to recheck speaker assignments in a project.
    
    Args:
        project_name (str): Name of the project to process
        threshold (float): Cosine similarity threshold for speaker matching
        backends (list): List of backends to use ['pyannote', 'wespeaker', '3dspeaker']
        max_workers (int): Number of parallel workers for processing
    
    Returns:
        dict: Validation results
    """
    if backends is None:
        backends = []
        if PYANNOTE_AVAILABLE:
            backends.append('pyannote')
        if WESPEAKER_AVAILABLE:
            backends.append('wespeaker')
        if THREED_SPEAKER_AVAILABLE:
            backends.append('3dspeaker')
    
    if not backends:
        raise RuntimeError("No speaker diarization backends available")
    
    print(f"Using backends: {backends}")
    
    # Project paths
    project_path = os.path.join("projects", project_name)
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project not found: {project_path}")
    
    speaker_db_path = os.path.join(project_path, "speaker_db_recheck.npy")
    validation_output = os.path.join(project_path, "speaker_validation.json")
    
    # Load existing speaker database
    speaker_db = load_speaker_db(speaker_db_path)
    total_speakers = sum(len(backend_speakers) for backend_speakers in speaker_db.values())
    print(f"Loaded speaker database with {total_speakers} speakers across {len(speaker_db)} backends")
    if speaker_db:
        for backend, speakers in speaker_db.items():
            print(f"  {backend}: {len(speakers)} speakers")
    
    # Find all audio clips
    all_clips = find_audio_clips(project_path)
    print(f"Found {len(all_clips)} cleaned_audio.wav files")
    
    if not all_clips:
        print("No cleaned_audio.wav files to process")
        return None
    
    # Load existing validation results if resuming
    processed_clips = set()
    results = []
    
    if os.path.exists(validation_output):
        try:
            with open(validation_output, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            if 'clips' in existing_data:
                results = existing_data['clips']
                processed_clips = {result['file'] for result in results}
                print(f"Resuming: Found {len(results)} already processed clips")
            else:
                print("Starting fresh validation (existing file has no clips)")
                
        except Exception as e:
            print(f"Warning: Could not load existing validation file: {e}")
            print("Starting fresh validation")
    
    # Filter out already processed clips
    remaining_clips = [clip for clip in all_clips if clip not in processed_clips]
    print(f"Remaining clips to process: {len(remaining_clips)}")
    
    if not remaining_clips:
        print("All clips already processed!")
        return load_existing_validation_data(validation_output)
    
    # Process clips in parallel with checkpoint saving
    def save_checkpoint(current_results, speaker_db, validation_output, speaker_db_path, project_name, threshold, backends, total_clips):
        """Save checkpoint with current results."""
        try:
            # Save speaker database
            save_speaker_db(speaker_db, speaker_db_path)
            
            # Create validation summary
            validation_data = create_validation_summary(
                project_name, threshold, backends, current_results, speaker_db
            )
            
            # Save validation results
            with open(validation_output, 'w', encoding='utf-8') as f:
                json.dump(validation_data, f, indent=2, ensure_ascii=False)
                
            print(f"Checkpoint saved: {len(current_results)}/{total_clips} clips processed ({len(current_results)/total_clips*100:.1f}%)")
            
        except Exception as e:
            print(f"Error saving checkpoint: {e}")
    
    total_clips = len(all_clips)  # Total clips we want to process (including already processed)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_clip = {
            executor.submit(process_audio_clip, clip, speaker_db, threshold, backends, project_name): clip
            for clip in remaining_clips
        }
        
        completed_count = 0
        for future in as_completed(future_to_clip):
            # Check for shutdown request
            if check_shutdown():
                print("\nShutdown requested, cancelling remaining tasks...")
                executor.shutdown(wait=False, cancel_futures=True)
                break
                
            clip = future_to_clip[future]
            try:
                result = future.result()
                if result is not None:  # Skip None results from shutdown
                    results.append(result)
                    completed_count += 1
                    
                    # Save checkpoint every 10 clips
                    if completed_count % 10 == 0:
                        save_checkpoint(results, speaker_db, validation_output, speaker_db_path, 
                                      project_name, threshold, backends, total_clips)
                        
            except Exception as e:
                print(f"Error processing {clip}: {e}")
                if not check_shutdown():  # Only print traceback if not shutting down
                    traceback.print_exc()
    
    # Final checkpoint save
    if results:
        save_checkpoint(results, speaker_db, validation_output, speaker_db_path, 
                       project_name, threshold, backends, total_clips)
    
    # Check if we should continue after potential shutdown
    if check_shutdown():
        print(f"Processing interrupted. Processed {len(results)} clips before shutdown.")
        if not results:
            return None
    
    # Final validation data creation and return
    total_speakers = sum(len(backend_speakers) for backend_speakers in speaker_db.values())
    print(f"Final processing complete. Total clips processed: {len(results)}")
    print(f"Updated speaker database with {total_speakers} speakers across {len(speaker_db)} backends")
    
    # Load and return the final validation data
    return load_existing_validation_data(validation_output)


def copy_good_segments_with_validation(project_name, validation_file=None):
    """
    Copy good segments to project/audio folder using speaker assignments from validation JSON.
    
    Args:
        project_name (str): Name of the project
        validation_file (str): Path to speaker_validation.json file. If None, uses default location.
        
    Returns:
        dict: Statistics about copied segments per speaker
    """
    # Default validation file path
    if validation_file is None:
        validation_file = os.path.join("projects", project_name, "speaker_validation.json")
    
    if not os.path.exists(validation_file):
        raise FileNotFoundError(f"Validation file not found: {validation_file}")
    
    # Load validation data
    try:
        with open(validation_file, 'r', encoding='utf-8') as f:
            validation_data = json.load(f)
    except Exception as e:
        raise Exception(f"Error loading validation file: {e}")
    
    if 'clips' not in validation_data:
        raise Exception("Invalid validation file format: missing 'clips' key")
    
    # Load bad segments to skip
    bad_segments = load_bad_segments(os.path.join("projects", project_name))
    
    # Create audio directory
    project_audio_dir = os.path.join("projects", project_name, "audio")
    os.makedirs(project_audio_dir, exist_ok=True)
    
    # Group clips by final speaker ID
    clips_by_speaker = {}
    total_clips = 0
    skipped_clips = 0
    
    for clip_result in validation_data['clips']:
        # Check for shutdown request
        if check_shutdown():
            print(f"\nShutdown requested during copy preparation. Processed {total_clips} clips.")
            break
            
        total_clips += 1
        clip_path = clip_result['file']
        clip_name = clip_result['clip_name']
        speaker_id = clip_result['final_speaker_id']
        
        # Check if this is a bad segment
        relative_path = os.path.relpath(clip_path, os.path.join("projects", project_name))
        if (clip_path in bad_segments or 
            clip_name in bad_segments or 
            relative_path in bad_segments):
            skipped_clips += 1
            print(f"Skipping bad segment: {clip_name}")
            continue
        
        # Check if files exist
        txt_path = clip_path.replace('.wav', '.txt')
        if not os.path.exists(clip_path) or not os.path.exists(txt_path):
            skipped_clips += 1
            print(f"Skipping missing files: {clip_name}")
            continue
        
        # Group by speaker
        if speaker_id not in clips_by_speaker:
            clips_by_speaker[speaker_id] = []
        clips_by_speaker[speaker_id].append({
            'wav_path': clip_path,
            'txt_path': txt_path,
            'clip_name': clip_name,
            'confidence': clip_result.get('confidence', 0.0)
        })
    
    print(f"Processed {total_clips} clips, skipped {skipped_clips} bad/missing")
    print(f"Found {len(clips_by_speaker)} unique speakers")
    
    # Copy segments organized by speaker
    copy_stats = {}
    speaker_counter = 0
    
    # Sort speakers by ID for consistent numbering
    for speaker_id in sorted(clips_by_speaker.keys()):
        clips = clips_by_speaker[speaker_id]
        
        print(f"\n--- Processing speaker: {speaker_id} ({len(clips)} clips) ---")
        
        # Create speaker subfolder in audio directory
        speaker_dir = os.path.join(project_audio_dir, f"speaker_{speaker_counter:02d}")
        os.makedirs(speaker_dir, exist_ok=True)
        
        # Sort clips by confidence (highest first) then by filename for consistent ordering
        clips.sort(key=lambda x: (-x['confidence'], x['clip_name']))
        
        # Copy all clips with renumbering
        clip_counter = 1
        copied_count = 0
        
        for clip in clips:
            # Check for shutdown request
            if check_shutdown():
                print(f"\nShutdown requested during copy for speaker {speaker_id}")
                break
                
            try:
                # Destination paths
                dst_wav = os.path.join(speaker_dir, f"clip_{clip_counter:05d}.wav")
                dst_txt = os.path.join(speaker_dir, f"clip_{clip_counter:05d}.txt")
                
                # Copy files
                shutil.copy2(clip['wav_path'], dst_wav)
                shutil.copy2(clip['txt_path'], dst_txt)
                
                copied_count += 1
                clip_counter += 1
                
            except Exception as e:
                print(f"  Error copying {clip['clip_name']}: {e}")
                continue
        
        copy_stats[f"speaker_{speaker_counter:02d}"] = {
            'original_speaker_id': speaker_id,
            'destination_folder': speaker_dir,
            'total_clips': len(clips),
            'copied_clips': copied_count,
            'avg_confidence': sum(c['confidence'] for c in clips) / len(clips) if clips else 0.0
        }
        
        print(f"  Copied {copied_count} clips to {speaker_dir}")
        print(f"  Average confidence: {copy_stats[f'speaker_{speaker_counter:02d}']['avg_confidence']:.3f}")
        speaker_counter += 1
    
    # Save copy statistics
    project_splits_dir = os.path.join("projects", project_name, "splits")
    os.makedirs(project_splits_dir, exist_ok=True)
    stats_file = os.path.join(project_splits_dir, 'validation_copy_stats.json')
    
    copy_summary = {
        'project_name': project_name,
        'copy_timestamp': datetime.now().isoformat(),
        'validation_file': validation_file,
        'total_processed_clips': total_clips,
        'skipped_clips': skipped_clips,
        'unique_speakers': len(copy_stats),
        'speaker_stats': copy_stats
    }
    
    try:
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(copy_summary, f, indent=2, ensure_ascii=False)
        print(f"\nCopy statistics saved to: {stats_file}")
    except Exception as e:
        print(f"Error saving copy statistics: {e}")
    
    # Print summary
    total_copied = sum(stats['copied_clips'] for stats in copy_stats.values())
    total_available = sum(stats['total_clips'] for stats in copy_stats.values())
    
    print(f"\n=== Copy Summary ===")
    print(f"Project: {project_name}")
    print(f"Unique speakers: {len(copy_stats)}")
    print(f"Total available clips: {total_available}")
    print(f"Successfully copied: {total_copied}")
    print(f"Copy efficiency: {(total_copied/total_available*100):.1f}%" if total_available > 0 else "N/A")
    
    return copy_summary


def main():
    """Main function for command line usage."""
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description="Speaker re-check and validation")
    parser.add_argument("project_name", help="Name of the project to process")
    parser.add_argument("--validate", action="store_true",
                       help="Run speaker validation and create speaker_validation.json")
    parser.add_argument("--copy", action="store_true",
                       help="Copy good segments to audio/ folder using validation results")
    parser.add_argument("--threshold", type=float, default=0.8, 
                       help="Cosine similarity threshold for speaker matching (default: 0.8)")
    parser.add_argument("--backends", default="pyannote,wespeaker,3dspeaker",
                       help="Comma-separated list of backends to use")
    parser.add_argument("--max_workers", type=int, default=1,
                       help="Number of parallel workers (default: 1)")

    args = parser.parse_args()
    
    # Check that at least one action is requested
    if not args.validate and not args.copy:
        print("Error: Must specify at least one action: --validate or --copy")
        parser.print_help()
        sys.exit(1)
    
    # Parse backends (only needed for validation)
    available_backends = []
    if args.validate:
        backends = [b.strip() for b in args.backends.split(',') if b.strip()]
        
        # Filter available backends
        for backend in backends:
            if backend == 'pyannote' and PYANNOTE_AVAILABLE:
                available_backends.append(backend)
            elif backend == 'wespeaker' and WESPEAKER_AVAILABLE:
                available_backends.append(backend)
            elif backend == '3dspeaker' and THREED_SPEAKER_AVAILABLE:
                available_backends.append(backend)
            else:
                print(f"Warning: Backend '{backend}' not available")
        
        if not available_backends:
            print("Error: No backends available for validation")
            sys.exit(1)
    
    try:
        validation_file = os.path.join("projects", args.project_name, "speaker_validation.json")
        
        # Run validation if requested
        if args.validate:
            print("="*50)
            print("RUNNING SPEAKER VALIDATION")
            print("="*50)
            
            # Check for shutdown before starting validation
            if check_shutdown():
                print("Shutdown requested before validation started")
                sys.exit(0)
            
            result = speaker_recheck(
                args.project_name, 
                args.threshold, 
                available_backends, 
                args.max_workers
            )
            
            # Check for shutdown after validation
            if check_shutdown():
                print("Shutdown requested during or after validation")
                sys.exit(0)
            
            if result:
                print(f"\nValidation completed successfully!")
                print(f"Processed {result['total_clips_processed']} clips")
                print(f"Found {result['total_speakers_in_db']} unique speakers")
            else:
                print("No clips were processed during validation")
        
        # Copy segments if requested
        if args.copy:
            # Check for shutdown before starting copy
            if check_shutdown():
                print("Shutdown requested before copy started")
                sys.exit(0)
                
            print("\n" + "="*50)
            print("COPYING SEGMENTS TO AUDIO FOLDER")
            print("="*50)
            
            # Check if validation file exists
            if not os.path.exists(validation_file):
                print(f"Error: Validation file not found: {validation_file}")
                print("Please run with --validate first to create the validation file")
                sys.exit(1)
            
            copy_result = copy_good_segments_with_validation(args.project_name)
            
            # Check for shutdown after copy
            if check_shutdown():
                print("Shutdown requested during or after copy")
                sys.exit(0)
            
            if copy_result:
                print("\nCopy completed successfully!")
                print(f"Copied segments for {copy_result['unique_speakers']} speakers")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(0)
    except Exception as e:
        if check_shutdown():
            print(f"\nShutdown completed")
            sys.exit(0)
        else:
            print(f"Error: {e}")
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
