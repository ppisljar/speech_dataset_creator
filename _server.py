from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
import os

# Import our modular blueprints
from server.files import create_files_routes
from server.project import create_project_routes
from server.split import create_split_routes  
from server.status import create_status_routes

app = Flask(__name__)
CORS(app)

# Base directory for projects
PROJECTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')

# Global dictionary to track processing status
processing_status = {}

# Ensure projects directory exists
os.makedirs(PROJECTS_DIR, exist_ok=True)

# Serve static files from web directory
@app.route('/')
def index():
    return send_from_directory(WEB_DIR, 'index.html')

@app.route('/web/<path:filename>')
def serve_web_files(filename):
    return send_from_directory(WEB_DIR, filename)

# Register blueprints with dependency injection
files_bp = create_files_routes(PROJECTS_DIR, processing_status)
project_bp = create_project_routes(PROJECTS_DIR, processing_status)
split_bp = create_split_routes(PROJECTS_DIR, processing_status)
status_bp = create_status_routes(PROJECTS_DIR, processing_status)

app.register_blueprint(files_bp)
app.register_blueprint(project_bp)
app.register_blueprint(split_bp)
app.register_blueprint(status_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)


