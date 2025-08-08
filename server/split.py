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

split_bp = Blueprint('split', __name__)

def process_file_background(project_name, filename, file_path, projects_dir, processing_status, override=False, segment=False):
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
        
        # Call the custom processing function
        success = process_file(file_path, file_path.replace('/raw', '/splits') + '/', override, segment)
        
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
                for item in os.listdir(splits_path):
                    if item.lower().endswith(('.mp3', '.wav')):
                        splits.append(item)
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

            # Start background processing
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, decoded_filename, raw_file_path, projects_dir, processing_status)
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

            # Start background processing
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, decoded_filename, raw_file_path, projects_dir, processing_status, False, True)
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
        """Run processing on all files in the project's raw directory"""
        try:
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

            # Start background processing for all files
            processing_keys = []
            for filename in audio_files:
                raw_file_path = os.path.join(raw_dir_path, filename)
                process_key = f"{project_name}_{filename}"
                processing_keys.append(process_key)
                
                thread = threading.Thread(
                    target=process_file_background,
                    args=(project_name, filename, raw_file_path, projects_dir, processing_status)
                )
                thread.daemon = True
                thread.start()

            return jsonify({
                'message': f'Processing started for {len(audio_files)} files in project {project_name}',
                'files': audio_files,
                'processing_keys': processing_keys
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
    
    return split_bp
