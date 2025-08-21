// Segments management functionality
class SegmentsManager {
    constructor(dataViewer) {
        this.dataViewer = dataViewer;
    }

    deleteSegment(index) {
        const segment = this.dataViewer.waveformData.segments[index];
        if (confirm(`Delete segment ${segment.seg_idx || index + 1}: "${segment.text}"?`)) {
            this.dataViewer.waveformData.segments.splice(index, 1);
            this.dataViewer.displaySegmentsTable();
            this.dataViewer.drawWaveform();
            podcastManager.showMessage(`Deleted segment ${segment.seg_idx || index + 1}`);
        }
    }

    deleteSubsegment(segmentIndex, subsegmentIndex) {
        const subsegment = this.dataViewer.waveformData.segments[segmentIndex].subs[subsegmentIndex];
        if (confirm(`Delete subsegment ${segmentIndex + 1}.${subsegmentIndex + 1}: "${subsegment.text}"?`)) {
            this.dataViewer.waveformData.segments[segmentIndex].subs.splice(subsegmentIndex, 1);
            this.dataViewer.displaySegmentsTable();
            this.dataViewer.drawWaveform();
            podcastManager.showMessage(`Deleted subsegment ${segmentIndex + 1}.${subsegmentIndex + 1}`);
        }
    }

    markAllGood() {
        this.dataViewer.waveformData.segments.forEach(segment => {
            segment.status = 'good';
            if (segment.subs) {
                segment.subs.forEach(sub => {
                    sub.status = 'good';
                });
            }
        });
        this.dataViewer.displaySegmentsTable();
        podcastManager.showMessage('Marked all segments as good');
    }

    markAllBad() {
        this.dataViewer.waveformData.segments.forEach(segment => {
            segment.status = 'bad';
            if (segment.subs) {
                segment.subs.forEach(sub => {
                    sub.status = 'bad';
                });
            }
        });
        this.dataViewer.displaySegmentsTable();
        podcastManager.showMessage('Marked all segments as bad');
    }

    async saveSegments() {
        const project = podcastManager.currentProject;
        const filename = document.getElementById('dataFileSelect').value;
        const splitname = document.getElementById('dataSplitSelect').value;
        
        if (!project || !filename || !splitname) {
            podcastManager.showMessage('Please select project, file, and split', true);
            return;
        }

        try {
            // Convert segments back to the original format with times in milliseconds
            const segmentsData = {
                segments: this.dataViewer.waveformData.segments.map((segment, index) => ({
                    seg_idx: segment.seg_idx || index + 1,
                    main: {
                        start_ms: Math.round(segment.start * 1000),
                        end_ms: Math.round(segment.end * 1000),
                        speaker: segment.speaker,
                        text: segment.text,
                        min_conf: segment.confidence,
                        // Preserve padding fields
                        pad_start_ms: segment.pad_start_ms || 0,
                        pad_end_ms: segment.pad_end_ms || 0
                    },
                    subs: (segment.subs || []).map(sub => ({
                        start_ms: Math.round(sub.start * 1000),
                        end_ms: Math.round(sub.end * 1000),
                        speaker: sub.speaker,
                        text: sub.text,
                        min_conf: sub.confidence,
                        status: sub.status,
                        // Preserve padding fields for subsegments
                        pad_start_ms: sub.pad_start_ms || 0,
                        pad_end_ms: sub.pad_end_ms || 0
                    })),
                    status: segment.status
                }))
            };

            const response = await fetch(`/api/projects/${project}/splits/${filename}/${splitname}_segments.json`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(segmentsData)
            });

            if (response.ok) {
                podcastManager.showMessage('Segments saved successfully!');
            } else {
                const error = await response.json();
                podcastManager.showMessage('Error saving segments: ' + (error.error || 'Unknown error'), true);
            }
        } catch (error) {
            podcastManager.showMessage('Error saving segments: ' + error.message, true);
        }
    }

    async exportVisibleSegments() {
        const project = podcastManager.currentProject;
        const filename = document.getElementById('dataFileSelect').value;
        const splitname = document.getElementById('dataSplitSelect').value;
        
        if (!project || !filename || !splitname) {
            podcastManager.showMessage('Please select project, file, and split', true);
            return;
        }

        if (!this.dataViewer.waveformData.segments || this.dataViewer.waveformData.segments.length === 0) {
            podcastManager.showMessage('No segments loaded', true);
            return;
        }

        // Calculate visible time range
        const viewDuration = (this.dataViewer.waveformData.canvasWidth * this.dataViewer.waveformData.zoom) / 1000; // in seconds
        const viewStartTime = this.dataViewer.waveformData.viewStart; // in seconds
        const viewEndTime = viewStartTime + viewDuration; // in seconds

        // Find segments that are visible (overlap with viewport)
        const visibleSegments = this.dataViewer.waveformData.segments.filter(segment => {
            const segmentStart = segment.start; // in seconds
            const segmentEnd = segment.end; // in seconds
            
            // Check if segment overlaps with visible time range
            return segmentStart < viewEndTime && segmentEnd > viewStartTime;
        });

        if (visibleSegments.length === 0) {
            podcastManager.showMessage('No segments visible in current viewport', true);
            return;
        }

        // Get the segment ID range for visible segments
        const visibleSegIds = visibleSegments.map(seg => seg.seg_idx || 0).filter(id => id > 0);
        if (visibleSegIds.length === 0) {
            podcastManager.showMessage('Visible segments have no valid segment IDs', true);
            return;
        }

        const minSegId = Math.min(...visibleSegIds);
        const maxSegId = Math.max(...visibleSegIds);

        try {
            podcastManager.showMessage(`Exporting ${visibleSegments.length} visible segments (${minSegId}-${maxSegId})...`);
            
            const response = await fetch(`/api/projects/${project}/splits/${filename}/${splitname}/export-visible-segments`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    start_segment: minSegId,
                    end_segment: maxSegId
                })
            });

            if (response.ok) {
                // Get the filename from the response headers or construct it
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = 'visible_segments.json';
                if (contentDisposition) {
                    const match = contentDisposition.match(/filename="(.+)"/);
                    if (match) filename = match[1];
                }

                // Download the file
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                podcastManager.showMessage(`Exported ${visibleSegments.length} visible segments successfully!`);
            } else {
                const error = await response.json();
                podcastManager.showMessage('Error exporting visible segments: ' + (error.error || 'Unknown error'), true);
            }
        } catch (error) {
            podcastManager.showMessage('Error exporting visible segments: ' + error.message, true);
        }
    }
}

async function buildSplits() {
    const project = podcastManager.currentProject;
    const filename = document.getElementById('dataFileSelect').value;
    
    if (!project || !filename) {
        podcastManager.showMessage('Please select a project and a file to build.', true);
        return;
    }

    if (!confirm(`Are you sure you want to build splits for "${filename}"? This will create the final audio files based on the current segments.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/projects/${project}/splits/${filename}/build`, {
            method: 'POST'
        });

        const result = await response.json();
        if (response.ok) {
            podcastManager.showMessage(result.message);
            if (result.processing_key) {
                monitorProcessing(project, filename);
            }
        } else {
            podcastManager.showMessage(result.error, true);
        }
    } catch (error) {
        podcastManager.showMessage('Error starting build process: ' + error.message, true);
    }
}

async function exportVisibleSegments() {
    if (!dataViewer.segmentsManager) {
        podcastManager.showMessage('Segments manager not available', true);
        return;
    }
    await dataViewer.segmentsManager.exportVisibleSegments();
}
