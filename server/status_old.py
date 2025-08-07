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
# Processing status endpoint
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