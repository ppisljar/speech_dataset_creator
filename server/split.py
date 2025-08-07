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
    
    @split_bp.route('/api/projects/<project_name>/splits/<filename>', methods=['GET'])
    def get_splits(project_name, filename):
        """List all mp3/wav files under projects/$project/splits/$filename/"""
        try:
            splits_path = os.path.join(projects_dir, project_name, 'splits', filename)
            splits = []
            
            if os.path.exists(splits_path):
                for item in os.listdir(splits_path):
                    if item.lower().endswith(('.mp3', '.wav')):
                        splits.append(item)
            
            return jsonify(splits)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @split_bp.route('/api/projects/<project_name>/splits/<filename>/refresh', methods=['POST'])
    def refresh_split_file(project_name, filename):
        """Refresh a split file by reprocessing it"""
        try:
            # Look for the file in the raw directory
            raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{filename}")
            if not os.path.exists(raw_file_path):
                # Try with .wav extension
                raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{filename}.wav")
                if not os.path.exists(raw_file_path):
                    return jsonify({'error': 'Source file not found in raw directory'}), 404

            # Check if already processing
            process_key = f"{project_name}_{filename}"
            if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                return jsonify({'error': 'File is already being processed'}), 409

            # Start background processing
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, filename, raw_file_path, projects_dir, processing_status)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Processing started for {filename}',
                'processing_key': process_key
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @split_bp.route('/api/projects/<project_name>/splits/<filename>/build', methods=['POST'])
    def build_split_file(project_name, filename):
        """Build splits"""
        try:
            # Look for the file in the raw directory
            raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{filename}")
            if not os.path.exists(raw_file_path):
                # Try with .wav extension
                raw_file_path = os.path.join(projects_dir, project_name, 'raw', f"{filename}.wav")
                if not os.path.exists(raw_file_path):
                    return jsonify({'error': 'Source file not found in raw directory'}), 404

            # Check if already processing
            process_key = f"{project_name}_{filename}"
            if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                return jsonify({'error': 'File is already being processed'}), 409

            # Start background processing
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, filename, raw_file_path, projects_dir, processing_status, False, True)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Processing started for {filename}',
                'processing_key': process_key
            }), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @split_bp.route('/api/projects/<project_name>/splits/<splitnam>/<filename>', methods=['GET', 'PUT'])
    def get_split_file(project_name, splitnam, filename):
        """Get or update a specific split file"""
        try:
            split_file_path = os.path.join(projects_dir, project_name, 'splits', splitnam, filename)
            
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
