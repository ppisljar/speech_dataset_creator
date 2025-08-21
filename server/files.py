# Files endpoints
from flask import Blueprint, Response, jsonify, request, send_from_directory, send_file
import os
import json
import shutil
import subprocess
import threading
import time
import asyncio
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path
from run import process_file
from m0_get import download_urls

files_bp = Blueprint('files', __name__)

def download_urls_background(project_name, urls, projects_dir, processing_status):
    """Background function to download URLs to project raw folder"""
    process_key = f"{project_name}_url_download"
    
    try:
        processing_status[process_key] = {
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'message': f'Starting download of {len(urls)} URLs...'
        }
        
        # Prepare output directory
        output_dir = os.path.join(projects_dir, project_name, 'raw')
        os.makedirs(output_dir, exist_ok=True)
        
        # Run the download function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        processing_status[process_key]['progress'] = 20
        processing_status[process_key]['message'] = 'Downloading files...'
        
        result = loop.run_until_complete(download_urls(urls, output_dir, override=False))
        loop.close()
        
        # Update status based on results
        downloaded_count = len(result['downloaded'])
        failed_count = len(result['failed'])
        total_count = result['total']
        
        if failed_count == 0:
            processing_status[process_key] = {
                'status': 'completed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'message': f'Successfully downloaded {downloaded_count}/{total_count} files'
            }
        elif downloaded_count > 0:
            processing_status[process_key] = {
                'status': 'completed_with_errors',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'message': f'Downloaded {downloaded_count}/{total_count} files ({failed_count} failed)'
            }
        else:
            processing_status[process_key] = {
                'status': 'failed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 0,
                'message': f'All downloads failed'
            }
            
    except Exception as e:
        processing_status[process_key] = {
            'status': 'failed',
            'started_at': processing_status.get(process_key, {}).get('started_at', datetime.now().isoformat()),
            'completed_at': datetime.now().isoformat(),
            'progress': 0,
            'message': f'Error: {str(e)}'
        }

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

    @files_bp.route('/api/projects/<project_name>/download-urls', methods=['POST'])
    def download_urls_endpoint(project_name):
        """Download audio files from URLs"""
        try:
            data = request.get_json()
            urls_text = data.get('urls', '')
            
            if not urls_text:
                return jsonify({'error': 'No URLs provided'}), 400
            
            # Parse URLs from text (one per line)
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
            
            if not urls:
                return jsonify({'error': 'No valid URLs found'}), 400
            
            # Check if project exists
            project_path = os.path.join(projects_dir, project_name)
            if not os.path.exists(project_path):
                return jsonify({'error': 'Project not found'}), 404
            
            # Start background download process
            thread = threading.Thread(
                target=download_urls_background,
                args=(project_name, urls, projects_dir, processing_status)
            )
            thread.daemon = True
            thread.start()
            
            return jsonify({
                'message': f'Started download of {len(urls)} URLs',
                'processing_key': f"{project_name}_url_download",
                'urls_count': len(urls)
            }), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return files_bp

