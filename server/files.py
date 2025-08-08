# Files endpoints
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

files_bp = Blueprint('files', __name__)

def process_file_background(project_name, base_filename, file_path, projects_dir, processing_status):
    """Background function to process a file through the pipeline"""
    process_key = f"{project_name}_{base_filename}"
    
    try:
        processing_status[process_key] = {
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Starting processing...'
        }
        
        # Create output directory structure
        output_dir = os.path.join(projects_dir, project_name, 'splits', base_filename)
        os.makedirs(output_dir, exist_ok=True)
        
        processing_status[process_key]['progress'] = 10
        processing_status[process_key]['message'] = 'Cleaning audio...'
        
        # Call the custom processing function
        success = process_file(file_path, output_dir, False, False)
        
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

def create_files_routes(projects_dir, processing_status):
    """Create and return the files blueprint with injected dependencies"""
    
    @files_bp.route('/api/projects/<project_name>/files/<filetype>', methods=['GET'])
    def get_files(project_name, filetype):
        """List files in a project's filetype directory"""
        try:
            if filetype == "split": 
                filetype = "splits"
            files_path = os.path.join(projects_dir, project_name, filetype)
            files = []
            
            if os.path.exists(files_path):
                for item in os.listdir(files_path):
                    file_path = os.path.join(files_path, item)
                    if filetype != 'splits' and os.path.isfile(file_path):
                        files.append(item)
                    elif filetype == 'splits' and not os.path.isfile(file_path):
                        files.append(item)
            return jsonify(files)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @files_bp.route('/api/projects/<project_name>/files/<filetype>', methods=['POST'])
    def upload_file(project_name, filetype):
        """Upload a file to project's filetype directory"""
        try:
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            filename = secure_filename(file.filename)
            files_path = os.path.join(projects_dir, project_name, filetype)
            os.makedirs(files_path, exist_ok=True)
            
            file_path = os.path.join(files_path, filename)
            file.save(file_path)
            
            # If uploaded to raw directory, automatically trigger processing
            if filetype == 'raw':
                base_filename = os.path.splitext(filename)[0]
                thread = threading.Thread(
                    target=process_file_background,
                    args=(project_name, base_filename, file_path, projects_dir, processing_status)
                )
                thread.daemon = True
                thread.start()
                
                return jsonify({
                    'message': f'File {filename} uploaded successfully and processing started',
                    'processing_key': f"{project_name}_{base_filename}"
                }), 201
            
            return jsonify({'message': f'File {filename} uploaded successfully'}), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @files_bp.route('/api/projects/<project_name>/files/<filetype>/<path:filename>', methods=['PUT'])
    def rename_file(project_name, filetype, filename):
        """Rename a file"""
        try:
            data = request.get_json()
            new_filename = data.get('name')
            if not new_filename:
                return jsonify({'error': 'New filename is required'}), 400
            
            new_filename = secure_filename(new_filename)
            files_path = os.path.join(projects_dir, project_name, filetype)
            old_file_path = os.path.join(files_path, filename)
            new_file_path = os.path.join(files_path, new_filename)
            
            if not os.path.exists(old_file_path):
                return jsonify({'error': 'File not found'}), 404
            
            if os.path.exists(new_file_path):
                return jsonify({'error': 'File with new name already exists'}), 409
            
            os.rename(old_file_path, new_file_path)
            return jsonify({'message': f'File renamed from {filename} to {new_filename}'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @files_bp.route('/api/projects/<project_name>/files/<filetype>/<path:filename>', methods=['DELETE'])
    def delete_file(project_name, filetype, filename):
        """Delete a file"""
        try:
            file_path = os.path.join(projects_dir, project_name, filetype, filename)
            
            if not os.path.exists(file_path):
                return jsonify({'error': 'File not found'}), 404
            
            os.remove(file_path)
            return jsonify({'message': f'File {filename} deleted successfully'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return files_bp

