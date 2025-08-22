from flask import Blueprint, Response, jsonify, request, send_from_directory, send_file
import os
import json
import shutil
import subprocess
import threading
import time
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path
from run import process_file
import urllib.parse
import tempfile
from typing import List, Dict, Any

split_bp = Blueprint('split', __name__)

def load_project_settings(projects_dir, project_name):
    """Load project settings from settings.json file"""
    settings_file = os.path.join(projects_dir, project_name, 'settings.json')
    settings = {}
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            print(f"Loaded settings from {settings_file}")
        except json.JSONDecodeError as e:
            print(f"Warning: Error parsing settings.json: {e}")
            print("Using default settings")
        except Exception as e:
            print(f"Warning: Error reading settings.json: {e}")
            print("Using default settings")
    else:
        print(f"No settings.json found in project directory, using default settings")
    
    return settings

def run_all_background(project_name, options, projects_dir, processing_status):
    """Background function to run the full run_all.py pipeline with options"""
    run_all_key = f"{project_name}_run_all"
    
    try:
        processing_status[run_all_key] = {
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Starting run_all processing...'
        }
        
        # Build command arguments for run_all.py
        cmd = ['python', 'run_all.py', project_name]
        
        if options.get('override'):
            cmd.append('--override')
        if options.get('segment'):
            cmd.append('--segment')
        if options.get('validate'):
            cmd.append('--validate')
        if options.get('clean'):
            cmd.append('--clean')
        if options.get('meta'):
            cmd.append('--meta')
        if options.get('copy'):
            cmd.append('--copy')
        if options.get('skip'):
            cmd.append('--skip')
        
        processing_status[run_all_key]['progress'] = 10
        processing_status[run_all_key]['message'] = f'Running: {" ".join(cmd)}'
        
        # Execute run_all.py script
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        processing_status[run_all_key]['progress'] = 90
        processing_status[run_all_key]['message'] = 'Finalizing run_all processing...'
        
        if result.returncode == 0:
            processing_status[run_all_key] = {
                'status': 'completed',
                'started_at': processing_status[run_all_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'message': 'Run all completed successfully',
                'output': result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout  # Last 1000 chars
            }
        else:
            processing_status[run_all_key] = {
                'status': 'failed',
                'started_at': processing_status[run_all_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 0,
                'message': f'Run all failed: {result.stderr[-500:] if result.stderr else "Unknown error"}',
                'output': result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout
            }
            
    except Exception as e:
        processing_status[run_all_key] = {
            'status': 'failed',
            'started_at': processing_status.get(run_all_key, {}).get('started_at', datetime.now().isoformat()),
            'completed_at': datetime.now().isoformat(),
            'progress': 0,
            'message': f'Run all error: {str(e)}'
        }

def process_file_background(project_name, filename, file_path, projects_dir, processing_status, override=False, segment=False, settings=None):
    """Background function to process a file through the pipeline"""
    process_key = f"{project_name}_{filename}"
    
    try:
        processing_status[process_key] = {
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Starting processing...'
        }
        
        # Create output directory structure
        output_dir = os.path.join(projects_dir, project_name, 'splits', filename)
        os.makedirs(output_dir, exist_ok=True)
        
        # Import and use the processing functions
        # Note: We'll need to adapt the _run.py process_file function
        processing_status[process_key]['progress'] = 10
        processing_status[process_key]['message'] = 'Cleaning audio...'
        
        # Load project settings if not provided
        if settings is None:
            settings = load_project_settings(projects_dir, project_name)
        
        # Call the custom processing function
        success = process_file(file_path, file_path.replace('/raw', '/splits') + '/', override, segment, settings)
        
        if success:
            processing_status[process_key] = {
                'status': 'completed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'message': 'Processing completed successfully'
            }
        else:
            processing_status[process_key] = {
                'status': 'failed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 0,
                'message': 'Processing failed'
            }
            
    except Exception as e:
        processing_status[process_key] = {
            'status': 'failed',
            'started_at': processing_status.get(process_key, {}).get('started_at', datetime.now().isoformat()),
            'completed_at': datetime.now().isoformat(),
            'progress': 0,
            'message': f'Error: {str(e)}'
        }

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
        return 0, 0
    
    start_times = []
    end_times = []
    
    for seg in segments:
        main_data = seg.get('main', {})
        start_times.append(main_data.get('start_ms', 0))
        end_times.append(main_data.get('end_ms', 0))
    
    return min(start_times), max(end_times)

def filter_silences_in_range(silences_data: List[Dict[str, Any]], start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
    """Filter silence intervals to only those within the given time range."""
    filtered = []
    for silence in silences_data:
        silence_start = silence.get('start', 0)
        silence_end = silence.get('end', 0)
        # Include silence if it overlaps with the time range
        if silence_start < end_ms and silence_end > start_ms:
            filtered.append(silence)
    return filtered

def filter_transcription_tokens(transcription_data: List[Dict[str, Any]], start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
    """Filter transcription tokens to only those within the given time range."""
    filtered = []
    for token in transcription_data:
        token_start = token.get('start', 0) * 1000  # Convert to ms
        token_end = token.get('end', 0) * 1000  # Convert to ms
        # Include token if it overlaps with the time range
        if token_start < end_ms and token_end > start_ms:
            filtered.append(token)
    return filtered

def create_split_routes(projects_dir, processing_status):
    """Create and return the split blueprint with injected dependencies"""
    
    @split_bp.route('/api/projects/<project_name>/splits/', defaults={'filename': None}, methods=['GET'])
    @split_bp.route('/api/projects/<project_name>/splits/<path:filename>', methods=['GET'])
    def get_splits(project_name, filename):
        """List all mp3/wav files under projects/$project/splits/$filename/"""
        try:
            print(f"DEBUG: Raw filename received: {filename}")
            
            if filename is None:
                return jsonify({'error': 'Filename is required'}), 400
            
            # URL decode the filename to handle encoded characters like %2F
            decoded_filename = urllib.parse.unquote(filename)
            print(f"DEBUG: URL-decoded filename: {decoded_filename}")
            
            splits_path = os.path.join(projects_dir, project_name, 'splits', decoded_filename)
            print(f"DEBUG: Looking for splits in: {splits_path}")
            print(f"DEBUG: Path exists: {os.path.exists(splits_path)}")
            
            splits = []
            
            if os.path.exists(splits_path):
                print(f"DEBUG: Directory contents: {os.listdir(splits_path)}")
                all_audio_files = []
                for item in os.listdir(splits_path):
                    if item.lower().endswith(('.mp3', '.wav')):
                        all_audio_files.append(item)
                
                # Filter logic: if there are multiple wav files and one ends with _cleaned_audio.wav,
                # exclude the _cleaned_audio.wav file from the dropdown
                cleaned_audio_files = [f for f in all_audio_files if f.endswith('_cleaned_audio.wav')]
                other_wav_files = [f for f in all_audio_files if f.endswith('.wav') and not f.endswith('_cleaned_audio.wav')]
                mp3_files = [f for f in all_audio_files if f.endswith('.mp3')]
                
                # If there are other wav files besides _cleaned_audio.wav, exclude _cleaned_audio.wav
                if other_wav_files or mp3_files:
                    splits = other_wav_files + mp3_files
                else:
                    # If only _cleaned_audio.wav exists, include it
                    splits = cleaned_audio_files
            else:
                print(f"DEBUG: Directory does not exist: {splits_path}")
            
            print(f"DEBUG: Found splits: {splits}")
            return jsonify(splits)
        except Exception as e:
            print(f"DEBUG: Exception occurred: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/splits/<path:filename>/refresh', methods=['POST'])
    def refresh_split_file(project_name, filename):
        """Refresh a split file by reprocessing it"""
        try:
            # URL decode the filename to handle encoded characters like %2F
            decoded_filename = urllib.parse.unquote(filename)
            # Look for the file in the raw directory
            raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{decoded_filename}")
            if not os.path.exists(raw_file_path):
                # Try with .wav extension
                raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{decoded_filename}.wav")
                if not os.path.exists(raw_file_path):
                    return jsonify({'error': 'Source file not found in raw directory'}), 404

            # Check if already processing
            process_key = f"{project_name}_{decoded_filename}"
            if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                return jsonify({'error': 'File is already being processed'}), 409

            # Load project settings
            settings = load_project_settings(projects_dir, project_name)

            # Start background processing
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, decoded_filename, raw_file_path, projects_dir, processing_status, False, False, settings)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Processing started for {decoded_filename}',
                'processing_key': process_key
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @split_bp.route('/api/projects/<project_name>/splits/<path:filename>/build', methods=['POST'])
    def build_split_file(project_name, filename):
        """Build splits"""
        try:
            # URL decode the filename to handle encoded characters like %2F
            decoded_filename = urllib.parse.unquote(filename)
            # Look for the file in the raw directory
            raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{decoded_filename}")
            if not os.path.exists(raw_file_path):
                # Try with .wav extension
                raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{decoded_filename}.wav")
                if not os.path.exists(raw_file_path):
                    return jsonify({'error': 'Source file not found in raw directory'}), 404

            # Check if already processing
            process_key = f"{project_name}_{decoded_filename}"
            if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                return jsonify({'error': 'File is already being processed'}), 409

            # Load project settings
            settings = load_project_settings(projects_dir, project_name)

            # Start background processing
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, decoded_filename, raw_file_path, projects_dir, processing_status, False, True, settings)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Processing started for {decoded_filename}',
                'processing_key': process_key
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/run', methods=['POST'])
    def run_all_files(project_name):
        """Run processing on all files in the project's raw directory with advanced options"""
        try:
            # Get options from request body
            data = request.get_json() or {}
            options = {
                'override': data.get('override', False),
                'segment': data.get('segment', False), 
                'validate': data.get('validate', False),
                'clean': data.get('clean', False),
                'meta': data.get('meta', False),
                'copy': data.get('copy', False),
                'skip': data.get('skip', False)
            }

            # Get the raw directory path
            raw_dir_path = os.path.join(projects_dir, project_name, 'raw')
            if not os.path.exists(raw_dir_path):
                return jsonify({'error': 'Raw directory not found for project'}), 404

            # Get all audio files in the raw directory
            audio_files = []
            for item in os.listdir(raw_dir_path):
                if item.lower().endswith(('.mp3', '.wav', '.m4a', '.flac', '.ogg')):
                    audio_files.append(item)

            if not audio_files:
                return jsonify({'error': 'No audio files found in raw directory'}), 404

            # Check if any files are already being processed
            already_processing = []
            for filename in audio_files:
                process_key = f"{project_name}_{filename}"
                if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                    already_processing.append(filename)

            if already_processing:
                return jsonify({
                    'error': f'Some files are already being processed: {", ".join(already_processing)}'
                }), 409

            # Check if run_all processing is already running
            run_all_key = f"{project_name}_run_all"
            if run_all_key in processing_status and processing_status[run_all_key]['status'] == 'processing':
                return jsonify({'error': 'Run all is already in progress for this project'}), 409

            # Start background run_all processing
            thread = threading.Thread(
                target=run_all_background,
                args=(project_name, options, projects_dir, processing_status)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Run all started for project {project_name} with {len(audio_files)} files',
                'files': audio_files,
                'processing_key': run_all_key,
                'options': options
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @split_bp.route('/api/projects/<project_name>/splits/<path:splitnam>/<filename>', methods=['GET', 'PUT'])
    def get_split_file(project_name, splitnam, filename):
        """Get or update a specific split file"""
        try:
            # URL decode the splitnam to handle encoded characters like %2F
            decoded_splitnam = urllib.parse.unquote(splitnam)
            split_file_path = os.path.join(projects_dir, project_name, 'splits', decoded_splitnam, filename)
            
            if request.method == 'GET':
                if not os.path.exists(split_file_path):
                    return jsonify({'error': 'Split file not found'}), 404
                
                # if filetype is json return as json
                if filename.endswith('.json'):
                    with open(split_file_path, 'r') as f:
                        data = json.load(f)
                    return jsonify(data)
                # if filetype is csv return as csv
                elif filename.endswith('.csv'):
                    with open(split_file_path, 'r') as f:
                        data = f.read()
                    return Response(data, mimetype='text/csv')
                
                return send_file(split_file_path, mimetype='application/octet-stream')
            
            elif request.method == 'PUT':
                # Handle updating files (mainly for JSON files like segments)
                if not filename.endswith('.json'):
                    return jsonify({'error': 'Only JSON files can be updated via PUT'}), 400
                
                try:
                    data = request.get_json()
                    if data is None:
                        return jsonify({'error': 'Invalid JSON data'}), 400
                    
                    # Ensure the directory exists
                    os.makedirs(os.path.dirname(split_file_path), exist_ok=True)
                    
                    # Write the updated data to the file
                    with open(split_file_path, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    return jsonify({'message': f'File {filename} updated successfully'}), 200
                    
                except json.JSONDecodeError:
                    return jsonify({'error': 'Invalid JSON format'}), 400
                except Exception as e:
                    return jsonify({'error': f'Failed to save file: {str(e)}'}), 500
                    
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/splits/<path:splitnam>/<split_file>/cleanable', methods=['GET'])
    def get_cleanable_files(project_name, splitnam, split_file):
        """Get list of processing files that can be cleaned for a specific split"""
        try:
            # URL decode the splitnam to handle encoded characters like %2F
            decoded_splitnam = urllib.parse.unquote(splitnam)
            decoded_split_file = urllib.parse.unquote(split_file)
            
            split_dir = os.path.join(projects_dir, project_name, 'splits', decoded_splitnam)
            
            if not os.path.exists(split_dir):
                return jsonify([]), 200
            
            # Define processing file patterns based on the split file name
            base_name = decoded_split_file  # Keep the full filename including .wav
            
            # List of potential processing files
            processing_patterns = [
                f"{base_name}_silences.json",
                f"{base_name}_transcription.json", 
                f"{base_name}_pyannote.csv",
                f"{base_name}_pyannote.rttm",
                f"{base_name}_3dspeaker.csv",
                f"{base_name}_3dspeaker.rttm", 
                f"{base_name}_wespeaker.csv",
                f"{base_name}_wespeaker.rttm",
                f"{base_name}_segments.json",
                f"{base_name}_segments_raw.json"
                # Note: speaker_db.npy is now project-level, not per-split
            ]
            
            cleanable_files = []
            for pattern in processing_patterns:
                file_path = os.path.join(split_dir, pattern)
                if os.path.exists(file_path):
                    file_stats = os.stat(file_path)
                    cleanable_files.append({
                        'name': pattern,
                        'size': file_stats.st_size,
                        'modified': file_stats.st_mtime
                    })
            
            return jsonify(cleanable_files), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/splits/<path:splitnam>/<split_file>/clean', methods=['DELETE'])
    def clean_processing_file(project_name, splitnam, split_file):
        """Delete a specific processing file"""
        try:
            # URL decode the splitnam to handle encoded characters like %2F
            decoded_splitnam = urllib.parse.unquote(splitnam)
            decoded_split_file = urllib.parse.unquote(split_file)
            
            data = request.get_json()
            if not data or 'filename' not in data:
                return jsonify({'error': 'Filename is required'}), 400
            
            filename_to_delete = data['filename']
            
            # Security check: ensure the filename is a valid processing file
            base_name = decoded_split_file  # Keep the full filename including .wav
            valid_patterns = [
                f"{base_name}_silences.json",
                f"{base_name}_transcription.json", 
                f"{base_name}_pyannote.csv",
                f"{base_name}_pyannote.rttm",
                f"{base_name}_3dspeaker.csv",
                f"{base_name}_3dspeaker.rttm", 
                f"{base_name}_wespeaker.csv",
                f"{base_name}_wespeaker.rttm",
                f"{base_name}_segments.json"
                # Note: speaker_db.npy is now project-level, not per-split
            ]
            
            if filename_to_delete not in valid_patterns:
                return jsonify({'error': 'Invalid file for deletion'}), 400
            
            split_dir = os.path.join(projects_dir, project_name, 'splits', decoded_splitnam)
            file_path = os.path.join(split_dir, filename_to_delete)
            
            if not os.path.exists(file_path):
                return jsonify({'error': 'File not found'}), 404
            
            # Delete the file
            os.remove(file_path)
            
            return jsonify({'message': f'Successfully deleted {filename_to_delete}'}), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/run_all', methods=['POST'])
    def run_all_with_options(project_name):
        """Run all processing with specific options"""
        try:
            data = request.get_json()
            options = data.get('options', {}) if data else {}
            
            # Get list of audio files in project
            audio_dir = os.path.join(projects_dir, project_name, 'audio')
            if not os.path.exists(audio_dir):
                return jsonify({'error': 'Project audio directory not found'}), 404
            
            audio_files = [f for f in os.listdir(audio_dir) 
                          if f.lower().endswith(('.wav', '.mp3', '.m4a'))]
            
            if not audio_files:
                return jsonify({'error': 'No audio files found in project'}), 404

            # Check if any files are already being processed
            already_processing = []
            for filename in audio_files:
                process_key = f"{project_name}_{filename}"
                if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                    already_processing.append(filename)

            if already_processing:
                return jsonify({
                    'error': f'Some files are already being processed: {", ".join(already_processing)}'
                }), 409

            # Check if run_all processing is already running
            run_all_key = f"{project_name}_run_all"
            if run_all_key in processing_status and processing_status[run_all_key]['status'] == 'processing':
                return jsonify({'error': 'Run all is already in progress for this project'}), 409

            # Start background run_all processing
            thread = threading.Thread(
                target=run_all_background,
                args=(project_name, options, projects_dir, processing_status)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Run all started for project {project_name} with {len(audio_files)} files',
                'files': audio_files,
                'processing_key': run_all_key,
                'options': options
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/clean_granular', methods=['POST'])
    def clean_granular(project_name):
        """Clean specific directories and file types"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Request body is required'}), 400
            
            options = data.get('options', {})
            project_path = os.path.join(projects_dir, project_name)
            
            if not os.path.exists(project_path):
                return jsonify({'error': 'Project not found'}), 404

            deleted_items = []

            # Clean directories
            directories = options.get('directories', {})
            for dir_name, should_clean in directories.items():
                if should_clean:
                    dir_path = os.path.join(project_path, dir_name)
                    if os.path.exists(dir_path):
                        if dir_name == 'output':
                            # For output, only clean files related to this project
                            output_dir = os.path.join(os.path.dirname(projects_dir), 'output')
                            project_files = [f for f in os.listdir(output_dir) 
                                           if f.startswith(project_name)]
                            for file in project_files:
                                file_path = os.path.join(output_dir, file)
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                                    deleted_items.append(f"output/{file}")
                                elif os.path.isdir(file_path):
                                    shutil.rmtree(file_path)
                                    deleted_items.append(f"output/{file}/")
                        else:
                            # Clean entire directory
                            for item in os.listdir(dir_path):
                                item_path = os.path.join(dir_path, item)
                                if os.path.isfile(item_path):
                                    os.remove(item_path)
                                    deleted_items.append(f"{dir_name}/{item}")
                                elif os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                    deleted_items.append(f"{dir_name}/{item}/")

            # Clean specific file types
            file_types = options.get('file_types', {})
            splits_dir = os.path.join(project_path, 'splits')
            if os.path.exists(splits_dir):
                for split_folder in os.listdir(splits_dir):
                    split_path = os.path.join(splits_dir, split_folder)
                    if os.path.isdir(split_path):
                        for file_type, should_clean in file_types.items():
                            if should_clean:
                                pattern_map = {
                                    'transcriptions': '*_transcription.json',
                                    'speakers': '*_pyannote.*',
                                    'segments': '*_segments.json',
                                    'silences': '*_silences.json',
                                    'wespeaker': '*_wespeaker.*',
                                    '3dspeaker': '*_3dspeaker.*'
                                    # Note: speaker_db removed from split-level patterns
                                }
                                
                                if file_type in pattern_map:
                                    pattern = pattern_map[file_type]
                                    import glob
                                    files_to_delete = glob.glob(os.path.join(split_path, pattern))
                                    for file_path in files_to_delete:
                                        os.remove(file_path)
                                        deleted_items.append(f"splits/{split_folder}/{os.path.basename(file_path)}")

            # Handle project-level speaker database cleaning
            if file_types.get('speakerdb', False):
                speaker_db_path = os.path.join(project_path, 'speaker_db.npy')
                if os.path.exists(speaker_db_path):
                    os.remove(speaker_db_path)
                    deleted_items.append('speaker_db.npy')

            return jsonify({
                'message': f'Successfully cleaned {len(deleted_items)} items',
                'deleted_items': deleted_items
            }), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/splits/<path:splitnam>/<filename>/export-visible-segments', methods=['POST'])
    def export_visible_segments(project_name, splitnam, filename):
        """Export visible segments as JSON file for download"""
        try:
            data = request.get_json()
            start_segment = data.get('start_segment')
            end_segment = data.get('end_segment')
            
            if not start_segment or not end_segment:
                return jsonify({'error': 'start_segment and end_segment are required'}), 400
                
            if start_segment < 1:
                return jsonify({'error': 'start_segment must be >= 1'}), 400
                
            if end_segment < start_segment:
                return jsonify({'error': 'end_segment must be >= start_segment'}), 400
            
            # Construct the segments file path
            segments_file = os.path.join(projects_dir, project_name, 'splits', splitnam, f"{filename}_segments.json")
            segments_path = Path(segments_file)
            
            if not segments_path.exists():
                return jsonify({'error': f'Segments file not found: {segments_file}'}), 404
            
            # Load segments data
            segments_data = load_json_file(segments_path)
            if not segments_data:
                return jsonify({'error': f'Could not load segments file: {segments_file}'}), 400
            
            all_segments = segments_data['segments']
            original_audio_path = segments_data.get('audio_path', '')
            
            # Validate segment numbers - check available seg_idx values
            available_seg_ids = [seg['seg_idx'] for seg in all_segments]
            min_seg_id = min(available_seg_ids) if available_seg_ids else 1
            max_seg_id = max(available_seg_ids) if available_seg_ids else 0
            
            if start_segment < min_seg_id or start_segment > max_seg_id:
                return jsonify({'error': f'start_segment ({start_segment}) not found. Available seg_idx range: {min_seg_id}-{max_seg_id}'}), 400
            
            if end_segment < min_seg_id or end_segment > max_seg_id:
                return jsonify({'error': f'end_segment ({end_segment}) not found. Available seg_idx range: {min_seg_id}-{max_seg_id}'}), 400
            
            # Extract the requested segments by seg_idx (not array position)
            selected_segments = []
            for segment in all_segments:
                seg_idx = segment['seg_idx']
                if start_segment <= seg_idx <= end_segment:
                    selected_segments.append(segment)
            
            if not selected_segments:
                return jsonify({'error': f'No segments found with seg_idx between {start_segment} and {end_segment}'}), 400
            
            # Get time range for the selected segments
            start_ms, end_ms = get_time_range_from_segments(selected_segments)
            
            # Load raw segments if available
            raw_segments = []
            original_raw_file = Path(str(segments_path).replace('_segments.json', '_segments_raw.json'))
            if original_raw_file.exists():
                raw_segments_data = load_json_file(original_raw_file)
                if raw_segments_data:
                    raw_all_segments = raw_segments_data['segments']
                    # Extract the same range from raw segments by seg_idx
                    for segment in raw_all_segments:
                        seg_idx = segment['seg_idx']
                        if start_segment <= seg_idx <= end_segment:
                            raw_segments.append(segment)
            
            # Load silences
            silences = []
            silences_file = Path(str(segments_path).replace('_segments.json', '_silences.json'))
            if silences_file.exists():
                silences_data = load_json_file(silences_file)
                if silences_data:
                    # Filter silences to the time range of selected segments
                    silences = filter_silences_in_range(silences_data, start_ms, end_ms)
            
            # Load transcription
            transcription_tokens = []
            transcription_file = Path(str(segments_path).replace('_segments.json', '_transcription.json'))
            if transcription_file.exists():
                transcription_data = load_json_file(transcription_file)
                if transcription_data:
                    # Filter transcription tokens to the time range of selected segments
                    transcription_tokens = filter_transcription_tokens(transcription_data, start_ms, end_ms)
            
            # Create comprehensive output data (same format as m6_get_segment.py)
            output_data = {
                'metadata': {
                    'extraction_info': {
                        'start_segment_id': start_segment,
                        'end_segment_id': end_segment,
                        'time_range_ms': [start_ms, end_ms],
                        'extracted_at': datetime.now().isoformat()
                    },
                    'source_info': {
                        'segments_file': str(segments_path),
                        'extracted_segments_count': len(selected_segments),
                        'audio_path': original_audio_path,
                        'files_included': {
                            'segments': True,
                            'raw_segments': len(raw_segments) > 0,
                            'silences': len(silences) > 0,
                            'transcriptions': len(transcription_tokens) > 0
                        }
                    }
                },
                'segments': selected_segments,
                'raw_segments': raw_segments,
                'silences': silences,
                'transcription_tokens': transcription_tokens
            }
            
            # Generate filename for download
            download_filename = f"visible_segments_{start_segment}_{end_segment}.json"
            
            # Create response with JSON data
            response_json = json.dumps(output_data, indent=2, ensure_ascii=False)
            response = Response(
                response_json,
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="{download_filename}"'
                }
            )
            
            return response
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return split_bp
