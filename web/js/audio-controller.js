// Audio playback functionality for the data viewer
class AudioController {
    constructor(dataViewer) {
        this.dataViewer = dataViewer;
    }

    async playAudio() {
        if (!this.dataViewer.waveformData.audioBuffer) {
            podcastManager.showMessage('No audio loaded', true);
            return;
        }

        try {
            await this.dataViewer.initializeAudioContext();
            
            if (this.dataViewer.audioSource) {
                this.dataViewer.audioSource.stop();
            }

            // Create a new audio source
            this.dataViewer.audioSource = this.dataViewer.audioContext.createBufferSource();
            this.dataViewer.audioSource.buffer = this.dataViewer.waveformData.audioBuffer;
            
            // Connect to volume control
            const gainNode = this.dataViewer.audioContext.createGain();
            gainNode.gain.value = document.getElementById('volumeSlider').value / 100;
            this.dataViewer.audioSource.connect(gainNode);
            gainNode.connect(this.dataViewer.audioContext.destination);
            
            // Start playing from current position (audioStartOffset), not from view start
            this.dataViewer.audioSource.start(0, this.dataViewer.audioStartOffset);
            
            this.dataViewer.playStartTime = this.dataViewer.audioContext.currentTime;
            this.dataViewer.isPlaying = true;
            
            // Update button states - hide play, show pause
            document.getElementById('playBtn').style.display = 'none';
            document.getElementById('pauseBtn').style.display = 'inline-block';
            document.getElementById('pauseBtn').disabled = false;
            document.getElementById('stopBtn').disabled = false;
            
            // Start position animation
            this.startPositionTracking();
            
            // Handle audio end
            this.dataViewer.audioSource.onended = () => {
                if (this.dataViewer.isPlaying) {
                    this.stopAudio();
                }
            };
            
            podcastManager.showMessage('Audio playback started');
            
        } catch (error) {
            console.error('Error playing audio:', error);
            podcastManager.showMessage('Error starting playback: ' + error.message, true);
        }
    }

    pauseAudio() {
        if (this.dataViewer.audioSource && this.dataViewer.isPlaying) {
            this.dataViewer.audioSource.stop();
            this.dataViewer.isPlaying = false;
            
            // Calculate current position for resume
            const elapsed = this.dataViewer.audioContext.currentTime - this.dataViewer.playStartTime;
            this.dataViewer.audioStartOffset += elapsed;
            
            // Update button states - show play, hide pause
            document.getElementById('playBtn').style.display = 'inline-block';
            document.getElementById('pauseBtn').style.display = 'none';
            
            this.stopPositionTracking();
            podcastManager.showMessage('Audio paused');
            this.dataViewer.updateTimeDisplays(); // Update the new time displays
        }
    }

    stopAudio() {
        if (this.dataViewer.audioSource) {
            this.dataViewer.audioSource.stop();
            this.dataViewer.audioSource = null;
        }
        
        this.dataViewer.isPlaying = false;
        this.dataViewer.audioStartOffset = this.dataViewer.waveformData.viewStart; // Reset to current view start
        
        // Reset button states - show play, hide pause
        document.getElementById('playBtn').style.display = 'inline-block';
        document.getElementById('pauseBtn').style.display = 'none';
        document.getElementById('stopBtn').disabled = true;
        
        this.stopPositionTracking();
        this.updateAudioTimeDisplay();
        this.dataViewer.updateTimeDisplays(); // Update the new time displays
        this.dataViewer.drawWaveform(); // Redraw to remove position line
        podcastManager.showMessage('Audio stopped');
    }

    seekToTime(timeInSeconds) {
        const wasPlaying = this.dataViewer.isPlaying;
        
        // Stop current audio without changing button states if we're going to resume
        if (this.dataViewer.isPlaying) {
            if (this.dataViewer.audioSource) {
                this.dataViewer.audioSource.stop();
                this.dataViewer.audioSource = null;
            }
            this.dataViewer.isPlaying = false; // Set this to false immediately to prevent state issues
            this.stopPositionTracking();
        }
        
        this.dataViewer.audioStartOffset = Math.max(0, Math.min(timeInSeconds, this.dataViewer.waveformData.duration));
        
        // Update view if seeking outside current view
        const viewDuration = (this.dataViewer.waveformData.canvasWidth * this.dataViewer.waveformData.zoom) / 1000;
        if (this.dataViewer.audioStartOffset < this.dataViewer.waveformData.viewStart || 
            this.dataViewer.audioStartOffset > this.dataViewer.waveformData.viewStart + viewDuration) {
            this.dataViewer.waveformData.viewStart = Math.max(0, this.dataViewer.audioStartOffset - viewDuration / 2);
            this.dataViewer.updateTimeDisplay();
        }
        
        this.updateAudioTimeDisplay();
        this.dataViewer.updateTimeDisplays(); // Update the new time displays
        this.dataViewer.drawWaveform();
        
        // Resume playback if it was playing before seeking
        if (wasPlaying) {
            // Wait a brief moment to ensure clean audio restart
            setTimeout(() => {
                if (!this.dataViewer.isPlaying) { // Only restart if we're not already playing
                    this.playAudio();
                }
            }, 20);
        }
    }

    startPositionTracking() {
        const updatePosition = () => {
            if (this.dataViewer.isPlaying) {
                this.updateAudioTimeDisplay();
                this.dataViewer.updateTimeDisplays(); // Update the new time displays
                this.dataViewer.drawWaveform(); // Redraw to update position line
                this.dataViewer.animationId = requestAnimationFrame(updatePosition);
            }
        };
        updatePosition();
    }

    stopPositionTracking() {
        if (this.dataViewer.animationId) {
            cancelAnimationFrame(this.dataViewer.animationId);
            this.dataViewer.animationId = null;
        }
    }

    updateAudioTimeDisplay() {
        const currentTime = this.dataViewer.getCurrentPlaybackTime();
        const totalTime = this.dataViewer.waveformData.duration;
        
        document.getElementById('audioTime').textContent = 
            `${this.dataViewer.formatTime(currentTime)} / ${this.dataViewer.formatTime(totalTime)}`;
    }

    playSegment(index) {
        const segment = this.dataViewer.waveformData.segments[index];
        
        // Stop current playback
        if (this.dataViewer.isPlaying) {
            this.stopAudio();
        }
        
        // Seek to segment start and play
        this.seekToTime(segment.start);
        
        // Start playback
        setTimeout(() => {
            this.playAudio();
            
            // Stop playback at segment end
            const segmentDuration = (segment.end - segment.start) * 1000; // Convert to ms
            setTimeout(() => {
                if (this.dataViewer.isPlaying) {
                    this.pauseAudio();
                }
            }, segmentDuration);
        }, 100); // Small delay to ensure seek completes
        
        podcastManager.showMessage(`Playing segment ${segment.seg_idx || index + 1}: "${segment.text}"`);
    }

    seekToSegment(index) {
        const segment = this.dataViewer.waveformData.segments[index];
        this.seekToTime(segment.start);
        
        // Center the segment in view
        const viewDuration = (this.dataViewer.waveformData.canvasWidth * this.dataViewer.waveformData.zoom) / 1000;
        const segmentMiddle = (segment.start + segment.end) / 2;
        this.dataViewer.waveformData.viewStart = Math.max(0, segmentMiddle - viewDuration / 2);
        
        this.dataViewer.updateTimeDisplay();
        this.dataViewer.drawWaveform();
        
        podcastManager.showMessage(`Seeked to segment ${segment.seg_idx || index + 1}`);
    }

    playSubsegment(segmentIndex, subsegmentIndex) {
        const segment = this.dataViewer.waveformData.segments[segmentIndex];
        const subsegment = segment.subs[subsegmentIndex];
        
        // Stop current playback
        if (this.dataViewer.isPlaying) {
            this.stopAudio();
        }
        
        // Seek to subsegment start and play
        this.seekToTime(subsegment.start);
        
        // Start playback
        setTimeout(() => {
            this.playAudio();
            
            // Stop playback at subsegment end
            const subsegmentDuration = (subsegment.end - subsegment.start) * 1000; // Convert to ms
            setTimeout(() => {
                if (this.dataViewer.isPlaying) {
                    this.pauseAudio();
                }
            }, subsegmentDuration);
        }, 100); // Small delay to ensure seek completes
        
        podcastManager.showMessage(`Playing subsegment ${segment.seg_idx || segmentIndex + 1}.${subsegmentIndex + 1}: "${subsegment.text}"`);
    }

    seekToSubsegment(segmentIndex, subsegmentIndex) {
        const segment = this.dataViewer.waveformData.segments[segmentIndex];
        const subsegment = segment.subs[subsegmentIndex];
        this.seekToTime(subsegment.start);
        
        // Center the subsegment in view
        const viewDuration = (this.dataViewer.waveformData.canvasWidth * this.dataViewer.waveformData.zoom) / 1000;
        const subsegmentMiddle = (subsegment.start + subsegment.end) / 2;
        this.dataViewer.waveformData.viewStart = Math.max(0, subsegmentMiddle - viewDuration / 2);
        
        this.dataViewer.updateTimeDisplay();
        this.dataViewer.drawWaveform();
        
        podcastManager.showMessage(`Seeked to subsegment ${segment.seg_idx || segmentIndex + 1}.${subsegmentIndex + 1}`);
    }
}

// Global functions for backward compatibility
function playAudio() {
    dataViewer.audioController.playAudio();
}

function pauseAudio() {
    dataViewer.audioController.pauseAudio();
}

function stopAudio() {
    dataViewer.audioController.stopAudio();
}
