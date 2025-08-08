from flask import Blueprint, Response, jsonify, request, send_from_directory, send_file
import os
import json

status_bp = Blueprint('status', __name__)

def create_status_routes(projects_dir, processing_status):
    """Create and return the status blueprint with injected dependencies"""
    
    @status_bp.route('/api/projects/<project_name>/segments/<path:filename>', methods=['GET'])
    def get_segments(project_name, filename):
        """Return segments.json for a file"""
        try:
            segments_path = os.path.join(projects_dir, project_name, 'splits', filename, 'segments.json')
            
            if not os.path.exists(segments_path):
                return jsonify({'error': 'Segments file not found'}), 404
            
            with open(segments_path, 'r') as f:
                data = json.load(f)
            
            return jsonify(data)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    @status_bp.route('/api/projects/<project_name>/audio/<path:filename>', methods=['GET'])
    def get_audio(project_name, filename):
        """Return audio.wav for a file"""
        try:
            audio_path = os.path.join(projects_dir, project_name, 'audio', filename)
            
            if not os.path.exists(audio_path):
                return jsonify({'error': 'Audio file not found'}), 404
            
            return send_file(audio_path, mimetype='audio/wav')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @status_bp.route('/api/projects/<project_name>/processing/<path:filename>/status', methods=['GET'])
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
    @status_bp.route('/api/processing/status', methods=['GET'])
    def get_all_processing_status():
        """Get all processing statuses"""
        return jsonify(processing_status)
    
    return status_bp
