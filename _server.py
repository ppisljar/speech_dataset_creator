from flask import Flask, Response, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
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

app = Flask(__name__)
CORS(app)

# Base directory for projects
PROJECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')

# Global dictionary to track processing status
processing_status = {}

# Ensure projects directory exists
os.makedirs(PROJECTS_DIR, exist_ok=True)

def process_file_background(project_name, filename, file_path):
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
        output_dir = os.path.join(PROJECTS_DIR, project_name, 'splits', filename)
        os.makedirs(output_dir, exist_ok=True)
        
        # Import and use the processing functions
        # Note: We'll need to adapt the _run.py process_file function
        processing_status[process_key]['progress'] = 10
        processing_status[process_key]['message'] = 'Cleaning audio...'
        
        # Call the custom processing function
        success = process_file(file_path, file_path.replace('/raw', '/splits') + '/')
        
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


# Serve static files from web directory
@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/web/<path:filename>')
def serve_web_files(filename):
    return send_from_directory(WEB_DIR, filename)

# Projects endpoints
@app.route('/api/projects', methods=['GET'])
def get_projects():
    """List all project folders"""
    try:
        projects = []
        if os.path.exists(PROJECTS_DIR):
            for item in os.listdir(PROJECTS_DIR):
                project_path = os.path.join(PROJECTS_DIR, item)
                if os.path.isdir(project_path):
                    projects.append(item)
        return jsonify(projects)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project folder"""
    try:
        data = request.get_json()
        project_name = data.get('name')
        settings = data.get('settings', {})
        
        if not project_name:
            return jsonify({'error': 'Project name is required'}), 400
        
        project_name = secure_filename(project_name)
        project_path = os.path.join(PROJECTS_DIR, project_name)
        
        if os.path.exists(project_path):
            return jsonify({'error': 'Project already exists'}), 409
        
        os.makedirs(project_path, exist_ok=True)
        # Create subdirectories
        for subdir in ['splits', 'audio', 'raw']:
            os.makedirs(os.path.join(project_path, subdir), exist_ok=True)
        
        # Save settings if provided
        if settings:
            settings_path = os.path.join(project_path, 'settings.json')
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
        
        return jsonify({'message': f'Project {project_name} created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>', methods=['PUT'])
def rename_project(project_name):
    """Rename a project folder and update settings"""
    try:
        data = request.get_json()
        new_name = data.get('name')
        settings = data.get('settings')
        
        if not new_name:
            return jsonify({'error': 'New project name is required'}), 400
        
        new_name = secure_filename(new_name)
        old_path = os.path.join(PROJECTS_DIR, project_name)
        new_path = os.path.join(PROJECTS_DIR, new_name)
        
        if not os.path.exists(old_path):
            return jsonify({'error': 'Project not found'}), 404
        
        if new_name != project_name and os.path.exists(new_path):
            return jsonify({'error': 'Project with new name already exists'}), 409
        
        # Update settings if provided
        if settings:
            settings_path = os.path.join(old_path, 'settings.json')
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
        
        # Rename project folder if name changed
        if new_name != project_name:
            os.rename(old_path, new_path)
            return jsonify({'message': f'Project renamed from {project_name} to {new_name}'}), 200
        else:
            return jsonify({'message': f'Project {project_name} updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>', methods=['DELETE'])
def delete_project(project_name):
    """Delete a project folder"""
    try:
        project_path = os.path.join(PROJECTS_DIR, project_name)
        
        if not os.path.exists(project_path):
            return jsonify({'error': 'Project not found'}), 404
        
        shutil.rmtree(project_path)
        return jsonify({'message': f'Project {project_name} deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Files endpoints
@app.route('/api/projects/<project_name>/files/<filetype>', methods=['GET'])
def get_files(project_name, filetype):
    """List files in a project's filetype directory"""
    try:
        if filetype == "split": 
            filetype = "splits"
        files_path = os.path.join(PROJECTS_DIR, project_name, filetype)
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

@app.route('/api/projects/<project_name>/files/<filetype>', methods=['POST'])
def upload_file(project_name, filetype):
    """Upload a file to project's filetype directory"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        files_path = os.path.join(PROJECTS_DIR, project_name, filetype)
        os.makedirs(files_path, exist_ok=True)
        
        file_path = os.path.join(files_path, filename)
        file.save(file_path)
        
        # If uploaded to raw directory, automatically trigger processing
        if filetype == 'raw':
            base_filename = os.path.splitext(filename)[0]
            thread = threading.Thread(
                target=process_file_background,
                args=(project_name, base_filename, file_path)
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

@app.route('/api/projects/<project_name>/files/<filetype>/<filename>', methods=['PUT'])
def rename_file(project_name, filetype, filename):
    """Rename a file"""
    try:
        data = request.get_json()
        new_filename = data.get('name')
        if not new_filename:
            return jsonify({'error': 'New filename is required'}), 400
        
        new_filename = secure_filename(new_filename)
        files_path = os.path.join(PROJECTS_DIR, project_name, filetype)
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

@app.route('/api/projects/<project_name>/files/<filetype>/<filename>', methods=['DELETE'])
def delete_file(project_name, filetype, filename):
    """Delete a file"""
    try:
        file_path = os.path.join(PROJECTS_DIR, project_name, filetype, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        os.remove(file_path)
        return jsonify({'message': f'File {filename} deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Project settings endpoints
@app.route('/api/projects/<project_name>/settings', methods=['GET'])
def get_project_settings(project_name):
    """Get project settings from settings.json"""
    try:
        settings_path = os.path.join(PROJECTS_DIR, project_name, 'settings.json')
        
        if not os.path.exists(settings_path):
            # Return default settings if file doesn't exist
            default_settings = {
                'silenceThreshold': -40,
                'minSilenceLength': 500
            }
            return jsonify(default_settings)
        
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        return jsonify(settings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>/settings', methods=['PUT'])
def save_project_settings(project_name):
    """Save project settings to settings.json"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Settings data is required'}), 400
        
        project_path = os.path.join(PROJECTS_DIR, project_name)
        if not os.path.exists(project_path):
            return jsonify({'error': 'Project not found'}), 404
        
        settings_path = os.path.join(project_path, 'settings.json')
        
        with open(settings_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return jsonify({'message': 'Settings saved successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Splits endpoint
@app.route('/api/projects/<project_name>/splits/<filename>', methods=['GET'])
def get_splits(project_name, filename):
    """List all mp3/wav files under projects/$project/splits/$filename/"""
    try:
        splits_path = os.path.join(PROJECTS_DIR, project_name, 'splits', filename)
        splits = []
        
        if os.path.exists(splits_path):
            for item in os.listdir(splits_path):
                if item.lower().endswith(('.mp3', '.wav')):
                    splits.append(item)
        
        return jsonify(splits)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/projects/<project_name>/splits/<filename>/refresh', methods=['POST'])
def refresh_split_file(project_name, filename):
    """Refresh a split file by reprocessing it"""
    try:
        # Look for the file in the raw directory
        raw_file_path = os.path.join(PROJECTS_DIR, project_name, 'raw', f"{filename}")
        if not os.path.exists(raw_file_path):
            # Try with .wav extension
            raw_file_path = os.path.join(PROJECTS_DIR, project_name, 'raw', f"{filename}.wav")
            if not os.path.exists(raw_file_path):
                return jsonify({'error': 'Source file not found in raw directory'}), 404

        # Check if already processing
        process_key = f"{project_name}_{filename}"
        if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
            return jsonify({'error': 'File is already being processed'}), 409

        # Start background processing
        thread = threading.Thread(
            target=process_file_background,
            args=(project_name, filename, raw_file_path)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'message': f'Processing started for {filename}',
            'processing_key': process_key
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Processing status endpoint
@app.route('/api/projects/<project_name>/processing/<filename>/status', methods=['GET'])
def get_processing_status(project_name, filename):
    """Get the processing status of a file"""
    try:
        process_key = f"{project_name}_{filename}"
        
        if process_key not in processing_status:
            return jsonify({'error': 'No processing record found'}), 404
        
        return jsonify(processing_status[process_key])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# List all processing statuses
@app.route('/api/processing/status', methods=['GET'])
def get_all_processing_status():
    """Get all processing statuses"""
    return jsonify(processing_status)

@app.route('/api/projects/<project_name>/splits/<splitnam>/<filename>', methods=['GET', 'PUT'])
def get_split_file(project_name, splitnam, filename):
    """Get or update a specific split file"""
    try:
        split_file_path = os.path.join(PROJECTS_DIR, project_name, 'splits', splitnam, filename)
        
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

# JSON data endpoints
@app.route('/api/projects/<project_name>/silences/<filename>', methods=['GET'])
def get_silences(project_name, filename):
    """Return silences.json for a file"""
    try:
        silences_path = os.path.join(PROJECTS_DIR, project_name, 'splits', filename, 'silences.json')
        
        if not os.path.exists(silences_path):
            return jsonify({'error': 'Silences file not found'}), 404
        
        with open(silences_path, 'r') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>/transcriptions/<filename>', methods=['GET'])
def get_transcriptions(project_name, filename):
    """Return transcription.json for a file"""
    try:
        transcription_path = os.path.join(PROJECTS_DIR, project_name, 'splits', filename, 'transcription.json')
        
        if not os.path.exists(transcription_path):
            return jsonify({'error': 'Transcription file not found'}), 404
        
        with open(transcription_path, 'r') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>/pyannote/<filename>', methods=['GET'])
def get_pyannote(project_name, filename):
    """Return pyannote.json for a file"""
    try:
        pyannote_path = os.path.join(PROJECTS_DIR, project_name, 'splits', filename, 'pyannote.json')
        
        if not os.path.exists(pyannote_path):
            return jsonify({'error': 'Pyannote file not found'}), 404
        
        with open(pyannote_path, 'r') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_name>/segments/<filename>', methods=['GET'])
def get_segments(project_name, filename):
    """Return segments.json for a file"""
    try:
        segments_path = os.path.join(PROJECTS_DIR, project_name, 'splits', filename, 'segments.json')
        
        if not os.path.exists(segments_path):
            return jsonify({'error': 'Segments file not found'}), 404
        
        with open(segments_path, 'r') as f:
            data = json.load(f)
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/projects/<project_name>/audio/<filename>', methods=['GET'])
def get_audio(project_name, filename):
    """Return audio.wav for a file"""
    try:
        audio_path = os.path.join(PROJECTS_DIR, project_name, 'audio', filename)
        
        if not os.path.exists(audio_path):
            return jsonify({'error': 'Audio file not found'}), 404
        
        return send_file(audio_path, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


