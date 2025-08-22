# Projects endpoints
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

project_bp = Blueprint('project', __name__)

def export_project_background(project_name, processing_status):
    """Background function to export/archive a project"""
    process_key = f"{project_name}_export"
    
    try:
        processing_status[process_key] = {
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Starting export process...'
        }
        
        # Import the archive function from m10_archive
        from m10_archive import archive_dataset
        
        processing_status[process_key]['progress'] = 50
        processing_status[process_key]['message'] = 'Archiving dataset...'
        
        success = archive_dataset(project_name)
        
        if success:
            processing_status[process_key] = {
                'status': 'completed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'message': 'Export completed successfully'
            }
        else:
            processing_status[process_key] = {
                'status': 'failed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 0,
                'message': 'Export failed'
            }
            
    except Exception as e:
        processing_status[process_key] = {
            'status': 'failed',
            'started_at': processing_status.get(process_key, {}).get('started_at', datetime.now().isoformat()),
            'completed_at': datetime.now().isoformat(),
            'progress': 0,
            'message': f'Export error: {str(e)}'
        }

# Projects endpoints
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

project_bp = Blueprint('project', __name__)

def export_project_background(project_name, processing_status):
    """Background function to export/archive a project"""
    process_key = f"{project_name}_export"
    
    try:
        processing_status[process_key] = {
            'status': 'processing',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'message': 'Starting export process...'
        }
        
        # Import the archive function from m10_archive
        from m10_archive import archive_dataset
        
        processing_status[process_key]['progress'] = 50
        processing_status[process_key]['message'] = 'Archiving dataset...'
        
        success = archive_dataset(project_name)
        
        if success:
            processing_status[process_key] = {
                'status': 'completed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 100,
                'message': 'Export completed successfully'
            }
        else:
            processing_status[process_key] = {
                'status': 'failed',
                'started_at': processing_status[process_key]['started_at'],
                'completed_at': datetime.now().isoformat(),
                'progress': 0,
                'message': 'Export failed'
            }
            
    except Exception as e:
        processing_status[process_key] = {
            'status': 'failed',
            'started_at': processing_status.get(process_key, {}).get('started_at', datetime.now().isoformat()),
            'completed_at': datetime.now().isoformat(),
            'progress': 0,
            'message': f'Export error: {str(e)}'
        }

def create_project_routes(projects_dir, processing_status):
    """Create and return the project blueprint with injected dependencies"""
    
    @project_bp.route('/api/projects', methods=['GET'])
    def get_projects():
        """List all project folders"""
        try:
            projects = []
            if os.path.exists(projects_dir):
                for item in os.listdir(projects_dir):
                    project_path = os.path.join(projects_dir, item)
                    if os.path.isdir(project_path):
                        projects.append(item)
            return jsonify(projects)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @project_bp.route('/api/projects', methods=['POST'])
    def create_project():
        """Create a new project folder"""
        try:
            data = request.get_json()
            project_name = data.get('name')
            settings = data.get('settings', {})
            
            if not project_name:
                return jsonify({'error': 'Project name is required'}), 400
            
            project_name = secure_filename(project_name)
            project_path = os.path.join(projects_dir, project_name)
            
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

    @project_bp.route('/api/projects/<project_name>', methods=['PUT'])
    def rename_project(project_name):
        """Rename a project folder and update settings"""
        try:
            data = request.get_json()
            new_name = data.get('name')
            settings = data.get('settings')
            
            if not new_name:
                return jsonify({'error': 'New project name is required'}), 400
            
            new_name = secure_filename(new_name)
            old_path = os.path.join(projects_dir, project_name)
            new_path = os.path.join(projects_dir, new_name)
            
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

    @project_bp.route('/api/projects/<project_name>', methods=['DELETE'])
    def delete_project(project_name):
        """Delete a project folder"""
        try:
            project_path = os.path.join(projects_dir, project_name)
            
            if not os.path.exists(project_path):
                return jsonify({'error': 'Project not found'}), 404
            
            shutil.rmtree(project_path)
            return jsonify({'message': f'Project {project_name} deleted successfully'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Project settings endpoints
    @project_bp.route('/api/projects/<project_name>/settings', methods=['GET'])
    def get_project_settings(project_name):
        """Get project settings from settings.json"""
        try:
            settings_path = os.path.join(projects_dir, project_name, 'settings.json')
            
            if not os.path.exists(settings_path):
                # Return default settings if file doesn't exist
                default_settings = {
                    'silenceThreshold': -40,
                    'minSilenceLength': 500,
                    'maxSpeakers': 0,
                    'silencePad': 50,
                    'language': 'sl',
                    'buildSubsegments': True,
                    'joinSubsegments': False
                }
                return jsonify(default_settings)
            
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            
            return jsonify(settings)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @project_bp.route('/api/projects/<project_name>/settings', methods=['PUT'])
    def save_project_settings(project_name):
        """Save project settings to settings.json"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Settings data is required'}), 400
            
            project_path = os.path.join(projects_dir, project_name)
            if not os.path.exists(project_path):
                return jsonify({'error': 'Project not found'}), 404
            
            settings_path = os.path.join(project_path, 'settings.json')
            
            with open(settings_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            return jsonify({'message': 'Settings saved successfully'}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # Clean and Export endpoints
    @project_bp.route('/api/projects/<project_name>/clean', methods=['POST'])
    def clean_project(project_name):
        """Clean a project with granular options"""
        try:
            data = request.get_json() or {}
            
            # Granular directory cleaning options
            clean_splits = data.get('splits', False)
            clean_audio = data.get('audio', False) 
            clean_raw = data.get('raw', False)
            clean_output = data.get('output', False)
            
            # Granular file type cleaning options
            clean_transcriptions = data.get('transcriptions', False)
            clean_speakers = data.get('speakers', False)
            clean_segments = data.get('segments', False)
            clean_raw_segments = data.get('raw_segments', False)
            clean_silences = data.get('silences', False)
            clean_other = data.get('other', False)
            
            project_path = os.path.join(projects_dir, project_name)
            if not os.path.exists(project_path):
                return jsonify({'error': 'Project not found'}), 404
            
            # Track what was cleaned
            cleaned_items = []
            
            # Directory-level cleaning
            if clean_splits:
                splits_dir = os.path.join(project_path, 'splits')
                if os.path.exists(splits_dir):
                    shutil.rmtree(splits_dir)
                    os.makedirs(splits_dir, exist_ok=True)
                    cleaned_items.append('splits directory')
                    
            if clean_audio:
                audio_dir = os.path.join(project_path, 'audio')
                if os.path.exists(audio_dir):
                    shutil.rmtree(audio_dir)
                    os.makedirs(audio_dir, exist_ok=True)
                    cleaned_items.append('audio directory')
                    
            if clean_raw:
                raw_dir = os.path.join(project_path, 'raw')
                if os.path.exists(raw_dir):
                    shutil.rmtree(raw_dir)
                    os.makedirs(raw_dir, exist_ok=True)
                    cleaned_items.append('raw directory')
                    
            if clean_output:
                output_dir = os.path.join(project_path, 'output')
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
                    os.makedirs(output_dir, exist_ok=True)
                    cleaned_items.append('output directory')
            
            # File type-level cleaning (only in splits directory)
            splits_dir = os.path.join(project_path, 'splits')
            if os.path.exists(splits_dir):
                file_patterns = []
                
                if clean_transcriptions:
                    file_patterns.extend(['*_transcription.json'])
                if clean_speakers:
                    file_patterns.extend(['*_pyannote.csv', '*_pyannote.rttm', '*_3dspeaker.csv', '*_3dspeaker.rttm', '*_wespeaker.csv', '*_wespeaker.rttm'])
                    # Note: speaker_db.npy is now project-level, handled separately below
                if clean_segments:
                    file_patterns.extend(['*_segments.json'])
                if clean_raw_segments:
                    file_patterns.extend(['*_segments_raw.json'])
                if clean_silences:
                    file_patterns.extend(['*_silences.json'])
                if clean_other:
                    file_patterns.extend(['*.txt', '*.log', '*.tmp'])
                    
                # Remove matching files
                removed_count = 0
                for root, dirs, files in os.walk(splits_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        for pattern in file_patterns:
                            import fnmatch
                            if fnmatch.fnmatch(file, pattern):
                                try:
                                    os.remove(file_path)
                                    removed_count += 1
                                except OSError:
                                    pass  # Ignore errors
                
                if removed_count > 0:
                    cleaned_items.append(f'{removed_count} processing files')
            
            # Handle project-level speaker database cleaning
            if clean_speakers:
                speaker_db_path = os.path.join(project_path, 'speaker_db.npy')
                if os.path.exists(speaker_db_path):
                    try:
                        os.remove(speaker_db_path)
                        cleaned_items.append('project speaker database')
                    except OSError:
                        pass  # Ignore errors
            
            if not cleaned_items:
                return jsonify({'message': 'No items were selected for cleaning'}), 200
            
            return jsonify({
                'message': f'Project {project_name} cleaned successfully',
                'cleaned': cleaned_items
            }), 200
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @project_bp.route('/api/projects/<project_name>/export', methods=['POST'])
    def export_project(project_name):
        """Export/archive a project (run in background)"""
        try:
            # Check if already processing
            process_key = f"{project_name}_export"
            if process_key in processing_status and processing_status[process_key]['status'] == 'processing':
                return jsonify({'error': 'Export is already in progress for this project'}), 409

            # Start background processing
            thread = threading.Thread(
                target=export_project_background,
                args=(project_name, processing_status)
            )
            thread.daemon = True
            thread.start()

            return jsonify({
                'message': f'Export started for project {project_name}',
                'processing_key': process_key
            }), 200
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return project_bp
