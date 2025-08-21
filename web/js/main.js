// Main application state and functions
class PodcastManager {
    constructor() {
        this.currentProject = null;
        this.init();
    }

    init() {
        // Initialize the application when DOM is loaded
        this.loadProjects();
        this.loadProcessingStatus();
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Global project select event listener
        const globalProjectSelect = document.getElementById('globalProjectSelect');
        if (globalProjectSelect) {
            globalProjectSelect.addEventListener('change', async (e) => {
                this.currentProject = e.target.value;
                this.updateProjectButtons();
                await this.onProjectChange();
            });
        }

        // Data file select event listener - may not exist yet if data viewer component hasn't loaded
        this.setupDataViewerListeners();
    }

    setupDataViewerListeners() {
        const dataFileSelect = document.getElementById('dataFileSelect');
        if (dataFileSelect && !dataFileSelect.hasAttribute('data-listener-attached')) {
            dataFileSelect.addEventListener('change', async (e) => {
                await this.onDataFileChange(e.target.value);
                updateCleanButtonState();
            });
            dataFileSelect.setAttribute('data-listener-attached', 'true');
        }
        
        const dataSplitSelect = document.getElementById('dataSplitSelect');
        if (dataSplitSelect && !dataSplitSelect.hasAttribute('data-listener-attached')) {
            dataSplitSelect.addEventListener('change', () => {
                updateCleanButtonState();
            });
            dataSplitSelect.setAttribute('data-listener-attached', 'true');
        }
    }

    showMessage(message, isError = false) {
        const messagesDiv = document.getElementById('messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = isError ? 'error' : 'success';
        messageDiv.textContent = message;
        messagesDiv.appendChild(messageDiv);
        setTimeout(() => messageDiv.remove(), 5000);
    }

    async loadProjects() {
        try {
            const response = await fetch('/api/projects');
            const projects = await response.json();
            
            const globalProjectSelect = document.getElementById('globalProjectSelect');
            const currentSelection = globalProjectSelect.value;
            
            globalProjectSelect.innerHTML = '<option value="">Select Project</option>';
            
            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project;
                option.textContent = project;
                globalProjectSelect.appendChild(option);
            });
            
            // Restore selection if it still exists
            if (currentSelection && projects.includes(currentSelection)) {
                globalProjectSelect.value = currentSelection;
                this.currentProject = currentSelection;
            } else {
                this.currentProject = null;
            }
            
            this.updateProjectButtons();

        } catch (error) {
            this.showMessage('Error loading projects: ' + error.message, true);
        }
    }

    async onProjectChange() {
        // Reset dependent dropdowns
        const dataFileSelect = document.getElementById('dataFileSelect');
        const dataSplitSelect = document.getElementById('dataSplitSelect');
        
        if (dataFileSelect) {
            dataFileSelect.innerHTML = '<option value="">Select File</option>';
        }
        if (dataSplitSelect) {
            dataSplitSelect.innerHTML = '<option value="">Select Split</option>';
        }
        
        // Ensure data viewer listeners are set up
        this.setupDataViewerListeners();
        
        if (!this.currentProject) return;

        try {
            const response = await fetch(`/api/projects/${this.currentProject}/files/raw`);
            const files = await response.json();
            
            if (response.ok && dataFileSelect) {
                files.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file;
                    option.textContent = file;
                    dataFileSelect.appendChild(option);
                });
            } else if (!response.ok) {
                this.showMessage('Error loading files: ' + files.error, true);
            }
        } catch (error) {
            this.showMessage('Error loading files: ' + error.message, true);
        }
    }

    async onDataFileChange(filename) {
        const dataSplitSelect = document.getElementById('dataSplitSelect');
        if (dataSplitSelect) {
            dataSplitSelect.innerHTML = '<option value="">Select Split</option>';
        }
        
        updateCleanButtonState(); // Update after clearing splits
        
        if (!this.currentProject || !filename) return;

        try {
            const response = await fetch(`/api/projects/${this.currentProject}/splits/${filename}`);
            const splits = await response.json();
            
            if (response.ok && dataSplitSelect) {
                splits.forEach(split => {
                    const option = document.createElement('option');
                    option.value = split;
                    option.textContent = split;
                    dataSplitSelect.appendChild(option);
                });
            } else if (!response.ok) {
                this.showMessage('Error loading splits: ' + splits.error, true);
            }
        } catch (error) {
            this.showMessage('Error loading splits: ' + error.message, true);
        }
        
        updateCleanButtonState(); // Update after loading splits
    }

    updateProjectButtons() {
        const deleteBtn = document.getElementById('deleteProjectBtn');
        const editBtn = document.getElementById('editProjectBtn');
        const runAllBtn = document.getElementById('runAllBtn');
        const cleanBtn = document.getElementById('cleanProjectBtn');
        const exportBtn = document.getElementById('exportProjectBtn');
        
        if (this.currentProject) {
            deleteBtn.disabled = false;
            editBtn.disabled = false;
            runAllBtn.disabled = false;
            cleanBtn.disabled = false;
            exportBtn.disabled = false;
        } else {
            deleteBtn.disabled = true;
            editBtn.disabled = true;
            runAllBtn.disabled = true;
            cleanBtn.disabled = true;
            exportBtn.disabled = true;
        }
    }

    async loadProcessingStatus() {
        try {
            const response = await fetch('/api/processing/status');
            const statuses = await response.json();
            
            const statusDiv = document.getElementById('statusTooltipContent');
            if (Object.keys(statuses).length === 0) {
                statusDiv.innerHTML = 'No processing activities found.';
                return;
            }

            let html = '<table style="width: 100%; border-collapse: collapse; font-size: 12px;">';
            html += '<tr><th style="border: 1px solid #ddd; padding: 4px; font-size: 11px;">File</th><th style="border: 1px solid #ddd; padding: 4px; font-size: 11px;">Status</th><th style="border: 1px solid #ddd; padding: 4px; font-size: 11px;">Progress</th></tr>';
            
            for (const [key, status] of Object.entries(statuses)) {
                const progressColor = status.status === 'completed' ? 'green' : 
                                    status.status === 'failed' ? 'red' : 'blue';
                const fileName = key.length > 30 ? key.substring(0, 30) + '...' : key;
                html += `<tr>
                    <td style="border: 1px solid #ddd; padding: 4px; font-size: 11px;" title="${key}">${fileName}</td>
                    <td style="border: 1px solid #ddd; padding: 4px; color: ${progressColor}; font-size: 11px;">${status.status}</td>
                    <td style="border: 1px solid #ddd; padding: 4px; font-size: 11px;">${status.progress}%</td>
                </tr>`;
            }
            html += '</table>';
            
            statusDiv.innerHTML = html;
        } catch (error) {
            const statusDiv = document.getElementById('statusTooltipContent');
            statusDiv.innerHTML = 'Error loading status: ' + error.message;
        }
    }
}

// Global functions for backward compatibility
let podcastManager;

window.onload = function() {
    podcastManager = new PodcastManager();
};

// Modal functions
function showAddProjectModal() {
    document.getElementById('modalProjectName').value = '';
    document.getElementById('modalSilenceThreshold').value = '-40';
    document.getElementById('modalMinSilenceLength').value = '500';
    document.getElementById('modalMaxSpeakers').value = '0';
    document.getElementById('modalSilencePad').value = '50';
    document.getElementById('modalLanguage').value = 'sl';
    document.getElementById('modalBuildSubsegments').checked = true;
    document.getElementById('modalJoinSubsegments').checked = false;
    document.getElementById('addProjectModal').style.display = 'block';
}

async function showEditProjectModal() {
    if (!podcastManager.currentProject) {
        podcastManager.showMessage('Please select a project to edit', true);
        return;
    }
    
    document.getElementById('editProjectName').value = podcastManager.currentProject;
    
    try {
        // Load existing project settings
        const response = await fetch(`/api/projects/${podcastManager.currentProject}/settings`);
        const settings = await response.json();
        
        if (response.ok) {
            document.getElementById('editSilenceThreshold').value = settings.silenceThreshold || -40;
            document.getElementById('editMinSilenceLength').value = settings.minSilenceLength || 500;
            document.getElementById('editMaxSpeakers').value = settings.maxSpeakers || 0;
            document.getElementById('editSilencePad').value = settings.silencePad || 50;
            document.getElementById('editLanguage').value = settings.language || 'sl';
            document.getElementById('editBuildSubsegments').checked = settings.buildSubsegments !== undefined ? settings.buildSubsegments : true;
            document.getElementById('editJoinSubsegments').checked = settings.joinSubsegments !== undefined ? settings.joinSubsegments : false;
        } else {
            // Use defaults if settings not found
            document.getElementById('editSilenceThreshold').value = '-40';
            document.getElementById('editMinSilenceLength').value = '500';
            document.getElementById('editMaxSpeakers').value = '0';
            document.getElementById('editSilencePad').value = '50';
            document.getElementById('editLanguage').value = 'sl';
            document.getElementById('editBuildSubsegments').checked = true;
            document.getElementById('editJoinSubsegments').checked = false;
        }
    } catch (error) {
        // Use defaults if error loading settings
        document.getElementById('editSilenceThreshold').value = '-40';
        document.getElementById('editMinSilenceLength').value = '500';
        document.getElementById('editMaxSpeakers').value = '0';
        document.getElementById('editSilencePad').value = '50';
        document.getElementById('editLanguage').value = 'sl';
        document.getElementById('editBuildSubsegments').checked = true;
        document.getElementById('editJoinSubsegments').checked = false;
        podcastManager.showMessage('Could not load project settings, using defaults', true);
    }
    
    document.getElementById('editProjectModal').style.display = 'block';
}

function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

// Close modal when clicking outside of it
window.onclick = function(event) {
    const addModal = document.getElementById('addProjectModal');
    const editModal = document.getElementById('editProjectModal');
    if (event.target == addModal) {
        addModal.style.display = 'none';
    }
    if (event.target == editModal) {
        editModal.style.display = 'none';
    }
}

async function createProjectWithSettings() {
    const name = document.getElementById('modalProjectName').value.trim();
    const silenceThreshold = document.getElementById('modalSilenceThreshold').value;
    const minSilenceLength = document.getElementById('modalMinSilenceLength').value;
    const maxSpeakers = document.getElementById('modalMaxSpeakers').value;
    const silencePad = document.getElementById('modalSilencePad').value;
    const language = document.getElementById('modalLanguage').value;
    const buildSubsegments = document.getElementById('modalBuildSubsegments').checked;
    const joinSubsegments = document.getElementById('modalJoinSubsegments').checked;
    
    if (!name) {
        podcastManager.showMessage('Please enter a project name', true);
        return;
    }

    try {
        const response = await fetch('/api/projects', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                name: name,
                settings: {
                    silenceThreshold: parseFloat(silenceThreshold),
                    minSilenceLength: parseInt(minSilenceLength),
                    maxSpeakers: parseInt(maxSpeakers),
                    silencePad: parseInt(silencePad),
                    language: language,
                    buildSubsegments: buildSubsegments,
                    joinSubsegments: joinSubsegments
                }
            })
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            closeModal('addProjectModal');
            await podcastManager.loadProjects();
            // Select the newly created project
            document.getElementById('globalProjectSelect').value = name;
            podcastManager.currentProject = name;
            podcastManager.updateProjectButtons();
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error creating project: ' + error.message, true);
    }
}

async function updateProjectWithSettings() {
    const oldName = podcastManager.currentProject;
    const newName = document.getElementById('editProjectName').value.trim();
    const silenceThreshold = document.getElementById('editSilenceThreshold').value;
    const minSilenceLength = document.getElementById('editMinSilenceLength').value;
    const maxSpeakers = document.getElementById('editMaxSpeakers').value;
    const silencePad = document.getElementById('editSilencePad').value;
    const language = document.getElementById('editLanguage').value;
    const buildSubsegments = document.getElementById('editBuildSubsegments').checked;
    const joinSubsegments = document.getElementById('editJoinSubsegments').checked;
    
    if (!newName) {
        podcastManager.showMessage('Please enter a project name', true);
        return;
    }

    try {
        const response = await fetch(`/api/projects/${oldName}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                name: newName,
                settings: {
                    silenceThreshold: parseFloat(silenceThreshold),
                    minSilenceLength: parseInt(minSilenceLength),
                    maxSpeakers: parseInt(maxSpeakers),
                    silencePad: parseInt(silencePad),
                    language: language,
                    buildSubsegments: buildSubsegments,
                    joinSubsegments: joinSubsegments
                }
            })
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            closeModal('editProjectModal');
            await podcastManager.loadProjects();
            // Select the updated project
            document.getElementById('globalProjectSelect').value = newName;
            podcastManager.currentProject = newName;
            podcastManager.updateProjectButtons();
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error updating project: ' + error.message, true);
    }
}

async function deleteSelectedProject() {
    if (!podcastManager.currentProject) {
        podcastManager.showMessage('Please select a project to delete', true);
        return;
    }

    if (!confirm(`Are you sure you want to delete project "${podcastManager.currentProject}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/projects/${podcastManager.currentProject}`, {
            method: 'DELETE'
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            podcastManager.currentProject = null;
            await podcastManager.loadProjects();
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error deleting project: ' + error.message, true);
    }
}

async function uploadFile() {
    const project = podcastManager.currentProject;
    const fileInput = document.getElementById('fileUpload');
    
    if (!project) {
        podcastManager.showMessage('Please select a project', true);
        return;
    }
    
    if (!fileInput.files[0]) {
        podcastManager.showMessage('Please select a file', true);
        return;
    }

    try {
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);

        const response = await fetch(`/api/projects/${project}/files/raw`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            fileInput.value = '';
            // Refresh the file list if it's loaded
            const globalProjectSelect = document.getElementById('globalProjectSelect');
            if (globalProjectSelect.value) {
                globalProjectSelect.dispatchEvent(new Event('change'));
            }
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error uploading file: ' + error.message, true);
    }
}

async function runAllFiles() {
    if (!podcastManager.currentProject) {
        podcastManager.showMessage('Please select a project to run', true);
        return;
    }

    if (!confirm(`Run processing on all files in project "${podcastManager.currentProject}"?\n\nThis will process all audio files in the raw directory through the complete pipeline.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/projects/${podcastManager.currentProject}/run`, {
            method: 'POST'
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            if (result.processing_keys && result.processing_keys.length > 0) {
                // Start monitoring the processing for all files
                monitorMultipleProcessing(podcastManager.currentProject, result.files);
            }
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error starting processing: ' + error.message, true);
    }
}

async function monitorMultipleProcessing(project, filenames) {
    const processKeys = filenames.map(filename => `${project}_${filename}`);
    
    const checkStatuses = async () => {
        try {
            const response = await fetch('/api/processing/status');
            const statuses = await response.json();
            
            if (response.ok) {
                let completedCount = 0;
                let failedCount = 0;
                let processingCount = 0;
                
                for (const processKey of processKeys) {
                    if (statuses[processKey]) {
                        const status = statuses[processKey];
                        if (status.status === 'completed') {
                            completedCount++;
                        } else if (status.status === 'failed') {
                            failedCount++;
                        } else if (status.status === 'processing') {
                            processingCount++;
                        }
                    }
                }
                
                if (processingCount > 0) {
                    podcastManager.showMessage(`Processing ${project}: ${completedCount}/${processKeys.length} completed, ${processingCount} in progress`);
                    // Check again in 3 seconds
                    setTimeout(checkStatuses, 3000);
                } else {
                    // All processing finished
                    if (failedCount > 0) {
                        podcastManager.showMessage(`Processing completed for ${project}: ${completedCount} successful, ${failedCount} failed. Check processing status for details.`, failedCount > completedCount);
                    } else {
                        podcastManager.showMessage(`All files processed successfully for ${project}!`);
                    }
                    podcastManager.loadProcessingStatus();
                }
            }
        } catch (error) {
            console.error('Error checking processing statuses:', error);
        }
    };
    
    checkStatuses();
}

async function cleanProject() {
    if (!podcastManager.currentProject) {
        podcastManager.showMessage('Please select a project to clean', true);
        return;
    }

    const cleanRaw = confirm(`Clean project "${podcastManager.currentProject}"?\n\nThis will remove all processed files from the splits directory.\n\nClick "OK" to clean only splits, or "Cancel" to abort.\n\nTo also clean raw files, hold Shift and click OK.`);
    
    if (!cleanRaw) {
        return;
    }

    const includeRaw = window.event && window.event.shiftKey;
    
    if (includeRaw) {
        const confirmRaw = confirm(`WARNING: This will also delete all raw files!\n\nAre you absolutely sure you want to clean both splits AND raw files?`);
        if (!confirmRaw) {
            return;
        }
    }

    try {
        const response = await fetch(`/api/projects/${podcastManager.currentProject}/clean`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ raw: includeRaw })
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            // Refresh the file lists
            const globalProjectSelect = document.getElementById('globalProjectSelect');
            if (globalProjectSelect.value) {
                globalProjectSelect.dispatchEvent(new Event('change'));
            }
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error cleaning project: ' + error.message, true);
    }
}

async function exportProject() {
    if (!podcastManager.currentProject) {
        podcastManager.showMessage('Please select a project to export', true);
        return;
    }

    if (!confirm(`Export project "${podcastManager.currentProject}"?\n\nThis will create an archived dataset in the output directory with organized audio files and metadata.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/projects/${podcastManager.currentProject}/export`, {
            method: 'POST'
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            if (result.processing_key) {
                // Start monitoring the export process
                monitorExportProcessing(podcastManager.currentProject);
            }
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error starting export: ' + error.message, true);
    }
}

async function monitorExportProcessing(project) {
    const processKey = `${project}_export`;
    
    const checkStatus = async () => {
        try {
            const response = await fetch('/api/processing/status');
            const statuses = await response.json();
            
            if (response.ok && statuses[processKey]) {
                const status = statuses[processKey];
                
                if (status.status === 'processing') {
                    podcastManager.showMessage(`Exporting ${project}: ${status.progress}% - ${status.message}`);
                    // Check again in 2 seconds
                    setTimeout(checkStatus, 2000);
                } else if (status.status === 'completed') {
                    podcastManager.showMessage(`Export completed for ${project}! Check the output directory.`);
                    podcastManager.loadProcessingStatus();
                } else if (status.status === 'failed') {
                    podcastManager.showMessage(`Export failed for ${project}: ${status.message}`, true);
                    podcastManager.loadProcessingStatus();
                }
            }
        } catch (error) {
            console.error('Error checking export status:', error);
        }
    };
    
    checkStatus();
}

async function refreshFile() {
    const project = podcastManager.currentProject;
    const filename = document.getElementById('dataFileSelect').value;
    
    if (!project) {
        podcastManager.showMessage('Please select a project', true);
        return;
    }
    
    if (!filename) {
        podcastManager.showMessage('Please select a file', true);
        return;
    }

    try {
        const response = await fetch(`/api/projects/${project}/splits/${filename}/refresh`, {
            method: 'POST'
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            if (result.processing_key) {
                // Start monitoring the processing status
                monitorProcessing(project, filename);
            }
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error refreshing file: ' + error.message, true);
    }
}

async function monitorProcessing(project, filename) {
    const checkStatus = async () => {
        try {
            const response = await fetch(`/api/projects/${project}/processing/${filename}/status`);
            const status = await response.json();
            
            if (response.ok) {
                if (status.status === 'processing') {
                    podcastManager.showMessage(`Processing ${filename}: ${status.progress}% - ${status.message}`);
                    // Check again in 2 seconds
                    setTimeout(checkStatus, 2000);
                } else if (status.status === 'completed') {
                    podcastManager.showMessage(`Processing completed for ${filename}!`);
                    podcastManager.loadProcessingStatus();
                } else if (status.status === 'failed') {
                    podcastManager.showMessage(`Processing failed for ${filename}: ${status.message}`, true);
                    podcastManager.loadProcessingStatus();
                }
            }
        } catch (error) {
            console.error('Error checking status:', error);
        }
    };
    
    checkStatus();
}

function loadProcessingStatus() {
    podcastManager.loadProcessingStatus();
}

function refreshProcessingStatus() {
    podcastManager.loadProcessingStatus();
}

// Clean functions
async function toggleCleanDropdown() {
    const dropdown = document.getElementById('cleanDropdownContent');
    const isVisible = dropdown.classList.contains('show');
    
    if (isVisible) {
        dropdown.classList.remove('show');
    } else {
        await loadCleanableFiles();
        dropdown.classList.add('show');
    }
}

async function loadCleanableFiles() {
    const project = podcastManager.currentProject;
    const filename = document.getElementById('dataFileSelect').value;
    const splitName = document.getElementById('dataSplitSelect').value;
    
    const filesList = document.getElementById('cleanFilesList');
    
    if (!project || !filename || !splitName) {
        filesList.innerHTML = '<div class="clean-placeholder">Select a file and split to see cleanable files</div>';
        return;
    }
    
    try {
        const response = await fetch(`/api/projects/${project}/splits/${encodeURIComponent(filename)}/${encodeURIComponent(splitName)}/cleanable`);
        
        if (response.ok) {
            const cleanableFiles = await response.json();
            
            if (cleanableFiles.length === 0) {
                filesList.innerHTML = '<div class="clean-placeholder">No processing files found to clean</div>';
                return;
            }
            
            let html = '';
            cleanableFiles.forEach(file => {
                const fileType = getFileType(file.name);
                html += `
                    <div class="clean-file-item">
                        <span class="clean-file-name">${file.name}</span>
                        <span class="clean-file-type">${fileType}</span>
                        <button class="clean-delete-btn" onclick="deleteCleanFile('${file.name}')">Delete</button>
                    </div>
                `;
            });
            
            filesList.innerHTML = html;
        } else {
            filesList.innerHTML = '<div class="clean-placeholder">Error loading cleanable files</div>';
        }
    } catch (error) {
        console.error('Error loading cleanable files:', error);
        filesList.innerHTML = '<div class="clean-placeholder">Error loading cleanable files</div>';
    }
}

function getFileType(filename) {
    if (filename.includes('silences')) return 'Silences';
    if (filename.includes('transcription')) return 'Transcription';
    if (filename.includes('pyannote')) return 'Pyannote';
    if (filename.includes('3dspeaker')) return '3DSpeaker';
    if (filename.includes('wespeaker')) return 'WeSpeaker';
    if (filename.includes('segments')) return 'Segments';
    if (filename.includes('speaker_db')) return 'Speaker DB';
    return 'Other';
}

async function deleteCleanFile(filename) {
    const project = podcastManager.currentProject;
    const file = document.getElementById('dataFileSelect').value;
    const splitName = document.getElementById('dataSplitSelect').value;
    
    if (!confirm(`Are you sure you want to delete ${filename}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/projects/${project}/splits/${encodeURIComponent(file)}/${encodeURIComponent(splitName)}/clean`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filename: filename })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            podcastManager.showMessage(`Successfully deleted ${filename}`);
            // Refresh the cleanable files list
            await loadCleanableFiles();
        } else {
            podcastManager.showMessage(result.error || 'Error deleting file', true);
        }
    } catch (error) {
        console.error('Error deleting file:', error);
        podcastManager.showMessage('Error deleting file: ' + error.message, true);
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const dropdown = document.getElementById('cleanDropdownContent');
    const cleanBtn = document.getElementById('cleanBtn');
    
    if (dropdown && !cleanBtn.contains(event.target) && !dropdown.contains(event.target)) {
        dropdown.classList.remove('show');
    }
});

// Enable/disable clean button based on selections
function updateCleanButtonState() {
    const filename = document.getElementById('dataFileSelect').value;
    const splitName = document.getElementById('dataSplitSelect').value;
    const cleanBtn = document.getElementById('cleanBtn');
    
    if (cleanBtn) {
        cleanBtn.disabled = !filename || !splitName;
    }
}
