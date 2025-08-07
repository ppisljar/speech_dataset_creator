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
                        min_conf: segment.confidence
                    },
                    subs: (segment.subs || []).map(sub => ({
                        start_ms: Math.round(sub.start * 1000),
                        end_ms: Math.round(sub.end * 1000),
                        speaker: sub.speaker,
                        text: sub.text,
                        min_conf: sub.confidence,
                        status: sub.status
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
