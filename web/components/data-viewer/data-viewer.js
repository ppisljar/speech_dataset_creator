// Data Viewer Component JavaScript
class DataViewer {
    constructor() {
        this.waveformData = {
            audioData: null,
            audioBuffer: null,
            silences: [],
            transcriptions: [],
            pyannote: [],
            wespeaker: [],
            '3dspeaker': [],
            segments: [],
            rawSegments: [], // Raw segments before alignment/transformation
            duration: 0,
            sampleRate: 44100,
            zoom: 1000, // milliseconds per pixel
            viewStart: 0, // start time in seconds
            canvasWidth: 1200,
            mouseX: -1 // Mouse X position for hover indicator
        };

        // Audio context for decoding audio files
        this.audioContext = null;
        this.audioSource = null;
        this.isPlaying = false;
        this.playStartTime = 0;
        this.audioStartOffset = 0;
        this.animationId = null;

        // Initialize controllers
        this.audioController = new AudioController(this);
        this.segmentsManager = new SegmentsManager(this);
    }

    async loadData() {
        const project = podcastManager.currentProject;
        const filename = document.getElementById('dataFileSelect').value;
        const splitname = document.getElementById('dataSplitSelect').value;
        
        if (!project) {
            podcastManager.showMessage('Please select a project', true);
            return;
        }
        
        if (!filename) {
            podcastManager.showMessage('Please select a file', true);
            return;
        }

        if (!splitname) {
            podcastManager.showMessage('Please select a split', true);
            return;
        }

        try {
            podcastManager.showMessage('Loading audio data and annotations...');
            
            // Load all data types using the selected split name
            const [silencesRes, transcriptionsRes, pyannoteRes, wespeakerRes, threeDSpeakerRes, segmentsRes, rawSegmentsRes, audioRes] = await Promise.all([
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_silences.json`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_transcription.json`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_pyannote.csv`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_wespeaker.csv`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_3dspeaker.csv`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_segments.json`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}_segments_raw.json`).catch(() => ({ok: false})),
                fetch(`/api/projects/${project}/splits/${filename}/${splitname}`).catch(() => ({ok: false}))
            ]);

            // Parse responses
            if (silencesRes.ok) {
                const rawSilences = await silencesRes.json();
                // Convert array of [start, end] arrays to objects with start/end properties
                // Times are in milliseconds, convert to seconds for consistency
                this.waveformData.silences = rawSilences.map(silence => ({
                    start: silence[0] / 1000, // Convert ms to seconds
                    end: silence[1] / 1000     // Convert ms to seconds
                }));
            }
            if (transcriptionsRes.ok) {
                const rawTranscriptions = await transcriptionsRes.json();
                // Convert transcription tokens to expected format
                // Times are in milliseconds, convert to seconds for consistency
                if (rawTranscriptions.tokens) {
                    this.waveformData.transcriptions = rawTranscriptions.tokens.map(token => ({
                        start: token.start_ms / 1000, // Convert ms to seconds
                        end: token.end_ms / 1000,     // Convert ms to seconds
                        speaker: token.speaker,
                        text: token.text,
                        confidence: token.confidence
                    }));
                } else {
                    this.waveformData.transcriptions = [];
                }
            }
            if (pyannoteRes.ok) {
                const pyannoteText = await pyannoteRes.text();
                this.waveformData.pyannote = this.parsePyannoteCSV(pyannoteText);
            }
            if (wespeakerRes.ok) {
                const wespeakerText = await wespeakerRes.text();
                this.waveformData.wespeaker = this.parsePyannoteCSV(wespeakerText);
            }
            if (threeDSpeakerRes.ok) {
                const threeDSpeakerText = await threeDSpeakerRes.text();
                this.waveformData['3dspeaker'] = this.parsePyannoteCSV(threeDSpeakerText);
            }
            if (segmentsRes.ok) {
                const rawSegments = await segmentsRes.json();
                // Convert segments to expected format
                // Times are in milliseconds, convert to seconds for consistency
                if (rawSegments.segments) {
                    this.waveformData.segments = rawSegments.segments.map(segment => ({
                        start: segment.main.start_ms / 1000, // Convert ms to seconds
                        end: segment.main.end_ms / 1000,     // Convert ms to seconds
                        speaker: segment.main.speaker,
                        text: segment.main.text,
                        confidence: segment.main.min_conf,
                        seg_idx: segment.seg_idx,
                        // Preserve padding fields
                        pad_start_ms: segment.main.pad_start_ms || 0,
                        pad_end_ms: segment.main.pad_end_ms || 0,
                        // Also include subsegments for detailed view
                        subs: segment.subs.map(sub => ({
                            start: sub.start_ms / 1000,
                            end: sub.end_ms / 1000,
                            speaker: sub.speaker,
                            text: sub.text,
                            confidence: sub.min_conf,
                            // Preserve padding fields for subsegments
                            pad_start_ms: sub.pad_start_ms || 0,
                            pad_end_ms: sub.pad_end_ms || 0
                        }))
                    }));
                } else {
                    this.waveformData.segments = [];
                }
            }
            if (rawSegmentsRes.ok) {
                const rawSegments = await rawSegmentsRes.json();
                // Convert raw segments to expected format
                // Times are in milliseconds, convert to seconds for consistency
                if (rawSegments.segments) {
                    this.waveformData.rawSegments = rawSegments.segments.map(segment => ({
                        start: segment.main.start_ms / 1000, // Convert ms to seconds
                        end: segment.main.end_ms / 1000,     // Convert ms to seconds
                        speaker: segment.main.speaker,
                        text: segment.main.text,
                        confidence: segment.main.min_conf,
                        seg_idx: segment.seg_idx,
                        // Preserve padding fields
                        pad_start_ms: segment.main.pad_start_ms || 0,
                        pad_end_ms: segment.main.pad_end_ms || 0,
                        // Also include subsegments for detailed view
                        subs: segment.subs.map(sub => ({
                            start: sub.start_ms / 1000,
                            end: sub.end_ms / 1000,
                            speaker: sub.speaker,
                            text: sub.text,
                            confidence: sub.min_conf,
                            // Preserve padding fields for subsegments
                            pad_start_ms: sub.pad_start_ms || 0,
                            pad_end_ms: sub.pad_end_ms || 0
                        }))
                    }));
                } else {
                    this.waveformData.rawSegments = [];
                }
            }

            // Load and decode actual audio data
            if (audioRes.ok) {
                const audioBlob = await audioRes.blob();
                await this.decodeAudioData(audioBlob);
            } else {
                // Fallback: estimate duration from annotations and create placeholder
                this.estimateDurationFromAnnotations();
                await this.generatePlaceholderWaveform(this.waveformData.duration * 44100);
            }

            // Show waveform container and initialize
            document.getElementById('waveformContainer').style.display = 'block';
            this.initializeWaveformViewer();
            this.drawWaveform();
            
            // Display segments table in data viewer
            this.displaySegmentsTable();
            
            podcastManager.showMessage('Audio data loaded successfully!');
            
        } catch (error) {
            podcastManager.showMessage('Error loading data: ' + error.message, true);
        }
    }

    parsePyannoteCSV(csvText) {
        const lines = csvText.split('\n').filter(line => line.trim());
        return lines.slice(1).map(line => { // Skip header
            const parts = line.split(',');
            return {
                speaker: parts[0] || 'unknown',
                start: parseFloat(parts[1]),
                end: parseFloat(parts[2])
            };
        }).filter(item => !isNaN(item.start) && !isNaN(item.end));
    }

    async initializeAudioContext() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        // Resume context if suspended (required by some browsers)
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
    }

    async decodeAudioData(audioBlob) {
        try {
            await this.initializeAudioContext();
            
            const arrayBuffer = await audioBlob.arrayBuffer();
            this.waveformData.audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            
            // Extract mono channel data for visualization
            const channelData = this.waveformData.audioBuffer.getChannelData(0);
            this.waveformData.duration = this.waveformData.audioBuffer.duration;
            this.waveformData.sampleRate = this.waveformData.audioBuffer.sampleRate;
            
            // Downsample for visualization (1 sample per 10ms = 100 samples per second)
            const targetSampleRate = 100; // samples per second for visualization
            const downsampleRatio = this.waveformData.sampleRate / targetSampleRate;
            const outputLength = Math.floor(channelData.length / downsampleRatio);
            
            this.waveformData.audioData = new Float32Array(outputLength);
            
            // Downsample using RMS for better visualization
            for (let i = 0; i < outputLength; i++) {
                const start = Math.floor(i * downsampleRatio);
                const end = Math.min(start + downsampleRatio, channelData.length);
                
                let sum = 0;
                let count = 0;
                for (let j = start; j < end; j++) {
                    sum += channelData[j] * channelData[j];
                    count++;
                }
                
                // RMS value for better amplitude representation
                this.waveformData.audioData[i] = Math.sqrt(sum / count) * Math.sign(channelData[Math.floor((start + end) / 2)]);
            }
            
            console.log(`Decoded audio: ${this.waveformData.duration.toFixed(2)}s, ${this.waveformData.sampleRate}Hz, ${outputLength} visualization samples`);
            
            // Enable audio controls
            document.getElementById('playBtn').disabled = false;
            document.getElementById('stopBtn').disabled = false;
            
        } catch (error) {
            console.error('Error decoding audio:', error);
            podcastManager.showMessage('Failed to decode audio file. Using placeholder waveform.', true);
            await this.generatePlaceholderWaveform(this.waveformData.duration * 44100);
        }
    }

    async generatePlaceholderWaveform(estimatedSamples) {
        // Generate a placeholder waveform when audio decoding fails
        const duration = estimatedSamples / this.waveformData.sampleRate;
        this.waveformData.duration = duration;
        this.waveformData.audioData = new Float32Array(Math.floor(duration * 100)); // 100 samples per second for visualization
        
        for (let i = 0; i < this.waveformData.audioData.length; i++) {
            // Create a more subtle placeholder pattern
            const t = i / 100;
            this.waveformData.audioData[i] = 
                (Math.sin(t * 2 * Math.PI * 0.5) * 0.1 + // Slow sine wave
                 (Math.random() - 0.5) * 0.05) *        // Light noise
                Math.exp(-t * 0.01);                     // Very slow decay
        }
        
        console.log(`Generated placeholder waveform: ${duration.toFixed(2)}s`);
    }

    estimateDurationFromAnnotations() {
        let maxTime = 0;
        
        // Check all annotation types for maximum time
        [...this.waveformData.silences, ...this.waveformData.transcriptions, 
         ...this.waveformData.pyannote, ...this.waveformData.wespeaker, 
         ...this.waveformData['3dspeaker'], ...this.waveformData.segments, 
         ...this.waveformData.rawSegments].forEach(item => {
            if (item.end && item.end > maxTime) maxTime = item.end;
            if (item.start && item.start > maxTime) maxTime = item.start;
        });
        
        this.waveformData.duration = Math.max(maxTime, 60); // At least 1 minute
    }

    initializeWaveformViewer() {
        const canvas = document.getElementById('waveformCanvas');
        const container = canvas.parentElement;
        
        // Set canvas size to container width
        this.waveformData.canvasWidth = container.clientWidth;
        canvas.width = this.waveformData.canvasWidth;
        canvas.height = 560; // Increased from 520 to accommodate two new tracks
        document.getElementById('annotationsCanvas').width = this.waveformData.canvasWidth;
        document.getElementById('annotationsCanvas').height = 560;
        
        // Initialize timeline scrollbar
        this.initializeTimelineScrollbar();
        
        // Add canvas click handler for seeking
        canvas.addEventListener('click', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const timeOffset = (x / this.waveformData.canvasWidth) * viewDuration;
            const newTime = this.waveformData.viewStart + timeOffset;
            
            if (newTime >= 0 && newTime <= this.waveformData.duration) {
                this.seekToTime(newTime);
                podcastManager.showMessage(`Seeked to time: ${this.formatTime(newTime)}`);
            }
        });
        
        // Add mouse wheel handler for horizontal scrolling
        const waveformContainer = document.getElementById('waveformContainer');
        waveformContainer.addEventListener('wheel', (e) => {
            // Prevent default vertical scrolling
            e.preventDefault();
            
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const scrollDirection = e.deltaY > 0 ? 1 : -1;
            
            // Scale scroll sensitivity based on zoom level
            // At high zoom (small values), scroll less; at low zoom (large values), scroll more
            const scrollSensitivity = this.waveformData.zoom / 1000; // Convert ms to seconds
            const scrollAmount = scrollDirection * scrollSensitivity * 20; // Multiply by 20 for 10x faster speed
            
            const newViewStart = Math.max(0, Math.min(
                this.waveformData.viewStart + scrollAmount,
                this.waveformData.duration - viewDuration
            ));
            
            if (newViewStart !== this.waveformData.viewStart) {
                this.waveformData.viewStart = newViewStart;
                this.drawWaveform();
                this.updateTimeDisplay();
            }
        }, { passive: false });
        
        // Add mouse move handler for hover indicator
        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            
            if (x >= 0 && x <= this.waveformData.canvasWidth) {
                this.waveformData.mouseX = x;
                this.drawWaveform(); // Redraw to show hover line
                this.updateTimeDisplays(); // Update time displays
            } else {
                this.waveformData.mouseX = -1;
                this.drawWaveform();
                this.updateTimeDisplays(); // Update time displays
            }
        });
        
        // Add mouse leave handler to hide hover indicator
        canvas.addEventListener('mouseleave', () => {
            this.waveformData.mouseX = -1;
            this.drawWaveform(); // Redraw to hide hover line
            this.updateTimeDisplays(); // Update time displays
        });
        
        this.updateTimeDisplay();
        this.setZoom(this.waveformData.zoom);
        this.updateTimeDisplays(); // Initialize the new time displays
    }

    initializeTimelineScrollbar() {
        const scrollbarContainer = document.getElementById('timelineScrollbar');
        const thumb = document.getElementById('timelineThumb');
        let isDragging = false;
        let dragStartX = 0;
        let dragStartViewStart = 0;

        // Helper function to update thumb position and size
        const updateThumb = () => {
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const maxViewStart = Math.max(0, this.waveformData.duration - viewDuration);
            const scrollbarWidth = scrollbarContainer.clientWidth;
            
            // Calculate thumb width as percentage of total timeline
            const thumbWidthPercent = Math.min(1, viewDuration / this.waveformData.duration);
            const thumbWidth = Math.max(20, scrollbarWidth * thumbWidthPercent); // Minimum 20px
            
            // Calculate thumb position
            const thumbPositionPercent = maxViewStart > 0 ? (this.waveformData.viewStart / maxViewStart) : 0;
            const thumbPosition = thumbPositionPercent * (scrollbarWidth - thumbWidth);
            
            thumb.style.width = thumbWidth + 'px';
            thumb.style.left = thumbPosition + 'px';
        };

        // Mouse down on thumb - start dragging
        thumb.addEventListener('mousedown', (e) => {
            e.preventDefault();
            isDragging = true;
            dragStartX = e.clientX;
            dragStartViewStart = this.waveformData.viewStart;
            document.body.style.cursor = 'grabbing';
        });

        // Mouse down on scrollbar (not thumb) - jump to position
        scrollbarContainer.addEventListener('mousedown', (e) => {
            if (e.target === thumb) return; // Don't handle if clicking on thumb
            
            const rect = scrollbarContainer.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const scrollbarWidth = scrollbarContainer.clientWidth;
            const thumbWidth = thumb.clientWidth;
            
            // Calculate desired thumb center position
            const desiredThumbCenter = clickX;
            const newThumbLeft = Math.max(0, Math.min(scrollbarWidth - thumbWidth, desiredThumbCenter - thumbWidth / 2));
            
            // Convert to viewStart
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const maxViewStart = Math.max(0, this.waveformData.duration - viewDuration);
            const newViewStart = (newThumbLeft / (scrollbarWidth - thumbWidth)) * maxViewStart;
            
            this.waveformData.viewStart = Math.max(0, Math.min(newViewStart, maxViewStart));
            this.drawWaveform();
            this.updateTimeDisplay();
        });

        // Global mouse move - handle dragging
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            e.preventDefault();
            const deltaX = e.clientX - dragStartX;
            const scrollbarWidth = scrollbarContainer.clientWidth;
            const thumbWidth = thumb.clientWidth;
            
            // Convert pixel movement to time movement
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const maxViewStart = Math.max(0, this.waveformData.duration - viewDuration);
            const pixelsToTime = maxViewStart / (scrollbarWidth - thumbWidth);
            const timeDelta = deltaX * pixelsToTime;
            
            const newViewStart = Math.max(0, Math.min(dragStartViewStart + timeDelta, maxViewStart));
            
            if (newViewStart !== this.waveformData.viewStart) {
                this.waveformData.viewStart = newViewStart;
                this.drawWaveform();
                this.updateTimeDisplay();
            }
        });

        // Global mouse up - stop dragging
        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                document.body.style.cursor = '';
            }
        });

        // Initial thumb update
        updateThumb();
        
        // Store update function for external calls
        this.updateTimelineThumb = updateThumb;
    }

    setZoom(millisecondsPerPixel) {
        this.waveformData.zoom = millisecondsPerPixel;
        document.getElementById('currentZoom').textContent = `(${millisecondsPerPixel}ms/px)`;
        this.drawWaveform();
        this.updateTimeDisplay();
    }

    drawWaveform() {
        const canvas = document.getElementById('waveformCanvas');
        const annotationsCanvas = document.getElementById('annotationsCanvas');
        const ctx = canvas.getContext('2d');
        const annotationsCtx = annotationsCanvas.getContext('2d');
        
        // Clear canvases
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        annotationsCtx.clearRect(0, 0, annotationsCanvas.width, annotationsCanvas.height);
        
        if (!this.waveformData.audioData) return;
        
        // Calculate visible time range
        const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000; // in seconds
        const viewEnd = this.waveformData.viewStart + viewDuration;
        
        // Draw waveform (use only top 400px, leave bottom 80px for annotation tracks)
        const waveformHeight = 400;
        const centerY = waveformHeight / 2;
        
        // Draw waveform as filled areas for better visualization
        ctx.fillStyle = '#4A90E2';
        ctx.strokeStyle = '#2E5F8A';
        ctx.lineWidth = 1;
        
        // Calculate how many audio samples we need to average per pixel
        const samplesPerPixel = (viewDuration * 100) / this.waveformData.canvasWidth; // audioData is 100 samples/sec
        
        for (let x = 0; x < this.waveformData.canvasWidth; x++) {
            const timeAtPixel = this.waveformData.viewStart + (x / this.waveformData.canvasWidth) * viewDuration;
            const startSample = Math.floor(timeAtPixel * 100);
            const endSample = Math.floor((timeAtPixel + viewDuration / this.waveformData.canvasWidth) * 100);
            
            // Calculate min/max for this pixel to show amplitude range
            let minAmp = 0, maxAmp = 0;
            let sampleCount = 0;
            
            for (let i = startSample; i <= endSample && i < this.waveformData.audioData.length; i++) {
                if (i >= 0) {
                    const amp = this.waveformData.audioData[i];
                    minAmp = Math.min(minAmp, amp);
                    maxAmp = Math.max(maxAmp, amp);
                    sampleCount++;
                }
            }
            
            if (sampleCount > 0) {
                // Scale amplitude to fit in waveform area
                const scale = (waveformHeight * 0.4); // Use 80% of available height
                const minY = centerY - (minAmp * scale);
                const maxY = centerY - (maxAmp * scale);
                
                // Draw vertical line from min to max amplitude
                if (Math.abs(maxY - minY) > 1) {
                    ctx.beginPath();
                    ctx.moveTo(x, minY);
                    ctx.lineTo(x, maxY);
                    ctx.stroke();
                } else {
                    // For very quiet sections, draw a thin line
                    ctx.fillRect(x, centerY - 0.5, 1, 1);
                }
            }
        }
        
        // Draw center line
        ctx.strokeStyle = '#E0E0E0';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        ctx.lineTo(this.waveformData.canvasWidth, centerY);
        ctx.stroke();
        
        // Draw current playback position (full height)
        const currentTime = this.getCurrentPlaybackTime();
        if (currentTime >= this.waveformData.viewStart && currentTime <= viewEnd) {
            const positionX = ((currentTime - this.waveformData.viewStart) / viewDuration) * this.waveformData.canvasWidth;
            ctx.strokeStyle = '#FF0000';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(positionX, 0);
            ctx.lineTo(positionX, canvas.height); // Full canvas height
            ctx.stroke();
            
            // Draw playhead indicator at top
            ctx.fillStyle = '#FF0000';
            ctx.beginPath();
            ctx.moveTo(positionX - 5, 0);
            ctx.lineTo(positionX + 5, 0);
            ctx.lineTo(positionX, 10);
            ctx.closePath();
            ctx.fill();
        }
        
        // Draw mouse hover indicator (full height, dashed line)
        if (this.waveformData.mouseX >= 0) {
            ctx.strokeStyle = '#888888';
            ctx.lineWidth = 1;
            ctx.setLineDash([5, 5]); // Dashed line pattern
            ctx.beginPath();
            ctx.moveTo(this.waveformData.mouseX, 0);
            ctx.lineTo(this.waveformData.mouseX, canvas.height); // Full canvas height
            ctx.stroke();
            ctx.setLineDash([]); // Reset line dash
        }
        
        // Draw annotations
        this.drawAnnotations(annotationsCtx, viewDuration);
    }

    drawAnnotations(ctx, viewDuration) {
        const canvasHeight = ctx.canvas.height;
        const waveformHeight = 400;
        const trackHeight = 20;
        const viewEnd = this.waveformData.viewStart + viewDuration;
        
        // Helper function to convert time to x coordinate (supports times outside view)
        const timeToX = (time) => {
            return ((time - this.waveformData.viewStart) / viewDuration) * this.waveformData.canvasWidth;
        };
        
        // Helper function to check if an annotation overlaps with the current view
        const overlapsView = (startTime, endTime) => {
            return startTime < viewEnd && endTime > this.waveformData.viewStart;
        };
        
        // Define track positions (Y coordinates for each annotation type)
        const tracks = {
            silences: waveformHeight - 20,      // First track: 380-400px
            pyannote: waveformHeight,           // Second track: 400-420px  
            wespeaker: waveformHeight + 20,     // Third track: 420-440px
            '3dspeaker': waveformHeight + 40,   // Fourth track: 440-460px
            rawSegments: waveformHeight + 60,   // Fifth track: 460-480px (NEW)
            segments: waveformHeight + 80,      // Sixth track: 480-500px (MOVED DOWN)
            rawSubsegments: waveformHeight + 100, // Seventh track: 500-520px (NEW)
            subsegments: waveformHeight + 120,  // Eighth track: 520-540px (MOVED DOWN)
            transcriptions: waveformHeight + 140 // Ninth track: 540-560px (MOVED DOWN)
        };
        
        // Draw track labels on the left
        ctx.font = '12px Arial';
        ctx.textAlign = 'left';
        ctx.fillStyle = '#333';
        ctx.fillText('Silences', 2, tracks.silences + 14);
        ctx.fillText('Pyannote', 2, tracks.pyannote + 14);
        ctx.fillText('WeSpeaker', 2, tracks.wespeaker + 14);
        ctx.fillText('3DSpeaker', 2, tracks['3dspeaker'] + 14);
        ctx.fillText('Raw Segments', 2, tracks.rawSegments + 14);
        ctx.fillText('Segments', 2, tracks.segments + 14);
        ctx.fillText('Raw Subsegments', 2, tracks.rawSubsegments + 14);
        ctx.fillText('Subsegments', 2, tracks.subsegments + 14);
        ctx.fillText('Transcriptions', 2, tracks.transcriptions + 14);
        
        // Draw silences (blue boxes) in first track
        ctx.strokeStyle = 'blue';
        ctx.fillStyle = 'rgba(0, 0, 255, 0.3)';
        ctx.lineWidth = 1;
        this.waveformData.silences.forEach(silence => {
            if (overlapsView(silence.start, silence.end)) {
                const startX = timeToX(silence.start);
                const endX = timeToX(silence.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    ctx.fillRect(x, tracks.silences, width, trackHeight);
                    ctx.strokeRect(x, tracks.silences, width, trackHeight);
                }
            }
        });
        
        // Draw pyannote (green boxes) in second track
        ctx.strokeStyle = 'green';
        ctx.fillStyle = 'rgba(0, 255, 0, 0.3)';
        this.waveformData.pyannote.forEach(item => {
            if (overlapsView(item.start, item.end)) {
                const startX = timeToX(item.start);
                const endX = timeToX(item.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    ctx.fillRect(x, tracks.pyannote, width, trackHeight);
                    ctx.strokeRect(x, tracks.pyannote, width, trackHeight);
                }
            }
        });
        
        // Draw wespeaker (teal boxes) in third track
        ctx.strokeStyle = 'teal';
        ctx.fillStyle = 'rgba(0, 128, 128, 0.3)';
        this.waveformData.wespeaker.forEach(item => {
            if (overlapsView(item.start, item.end)) {
                const startX = timeToX(item.start);
                const endX = timeToX(item.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    ctx.fillRect(x, tracks.wespeaker, width, trackHeight);
                    ctx.strokeRect(x, tracks.wespeaker, width, trackHeight);
                }
            }
        });
        
        // Draw 3dspeaker (dark blue boxes) in fourth track
        ctx.strokeStyle = 'darkblue';
        ctx.fillStyle = 'rgba(0, 0, 139, 0.3)';
        this.waveformData['3dspeaker'].forEach(item => {
            if (overlapsView(item.start, item.end)) {
                const startX = timeToX(item.start);
                const endX = timeToX(item.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    ctx.fillRect(x, tracks['3dspeaker'], width, trackHeight);
                    ctx.strokeRect(x, tracks['3dspeaker'], width, trackHeight);
                }
            }
        });
        
        // Draw raw segments (orange boxes) in fifth track
        ctx.strokeStyle = 'orange';
        ctx.fillStyle = 'rgba(255, 165, 0, 0.3)';
        ctx.font = '10px Arial';
        this.waveformData.rawSegments.forEach((segment, index) => {
            if (overlapsView(segment.start, segment.end)) {
                const startX = timeToX(segment.start);
                const endX = timeToX(segment.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    ctx.fillRect(x, tracks.rawSegments, width, trackHeight);
                    ctx.strokeRect(x, tracks.rawSegments, width, trackHeight);
                    
                    // Add segment number label if there's enough space
                    if (width > 20) {
                        ctx.fillStyle = 'orange';
                        ctx.fillText(`R${index + 1}`, x + 2, tracks.rawSegments + 12);
                        ctx.fillStyle = 'rgba(255, 165, 0, 0.3)';
                    }
                }
            }
        });
        
        // Draw segments (red boxes) in sixth track
        ctx.strokeStyle = 'red';
        ctx.fillStyle = 'rgba(255, 0, 0, 0.3)';
        ctx.font = '10px Arial';
        this.waveformData.segments.forEach((segment, index) => {
            if (overlapsView(segment.start, segment.end)) {
                const startX = timeToX(segment.start);
                const endX = timeToX(segment.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    ctx.fillRect(x, tracks.segments, width, trackHeight);
                    ctx.strokeRect(x, tracks.segments, width, trackHeight);
                    
                    // Add segment number label if there's enough space
                    if (width > 20) {
                        ctx.fillStyle = 'red';
                        ctx.fillText(`S${index + 1}`, x + 2, tracks.segments + 12);
                        ctx.fillStyle = 'rgba(255, 0, 0, 0.3)';
                    }
                }
            }
        });
        
        // Draw raw subsegments (light blue boxes) in seventh track
        ctx.strokeStyle = 'cyan';
        ctx.fillStyle = 'rgba(0, 255, 255, 0.3)';
        ctx.font = '8px Arial';
        this.waveformData.rawSegments.forEach((segment, segmentIndex) => {
            if (segment.subs && Array.isArray(segment.subs)) {
                segment.subs.forEach((subsegment, subIndex) => {
                    if (overlapsView(subsegment.start, subsegment.end)) {
                        const startX = timeToX(subsegment.start);
                        const endX = timeToX(subsegment.end);
                        const x = Math.max(0, startX);
                        const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                        if (width > 0) {
                            ctx.fillRect(x, tracks.rawSubsegments, width, trackHeight);
                            ctx.strokeRect(x, tracks.rawSubsegments, width, trackHeight);
                            
                            // Add subsegment label if there's enough space
                            if (width > 15) {
                                ctx.fillStyle = 'cyan';
                                ctx.fillText(`R${segmentIndex + 1}.${subIndex + 1}`, x + 2, tracks.rawSubsegments + 10);
                                ctx.fillStyle = 'rgba(0, 255, 255, 0.3)';
                            }
                        }
                    }
                });
            }
        });
        
        // Draw subsegments (purple boxes) in eighth track
        ctx.strokeStyle = 'purple';
        ctx.fillStyle = 'rgba(128, 0, 128, 0.3)';
        ctx.font = '8px Arial';
        this.waveformData.segments.forEach((segment, segmentIndex) => {
            if (segment.subs && Array.isArray(segment.subs)) {
                segment.subs.forEach((subsegment, subIndex) => {
                    if (overlapsView(subsegment.start, subsegment.end)) {
                        const startX = timeToX(subsegment.start);
                        const endX = timeToX(subsegment.end);
                        const x = Math.max(0, startX);
                        const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                        if (width > 0) {
                            ctx.fillRect(x, tracks.subsegments, width, trackHeight);
                            ctx.strokeRect(x, tracks.subsegments, width, trackHeight);
                            
                            // Add subsegment label if there's enough space
                            if (width > 15) {
                                ctx.fillStyle = 'purple';
                                ctx.fillText(`${segmentIndex + 1}.${subIndex + 1}`, x + 2, tracks.subsegments + 10);
                                ctx.fillStyle = 'rgba(128, 0, 128, 0.3)';
                            }
                        }
                    }
                });
            }
        });
        
        // Draw transcriptions (golden boxes) in ninth track with punctuation-based border styles
        ctx.fillStyle = 'rgba(255, 215, 0, 0.3)'; // Changed from orange to gold
        this.waveformData.transcriptions.forEach(trans => {
            if (overlapsView(trans.start, trans.end)) {
                const startX = timeToX(trans.start);
                const endX = timeToX(trans.end);
                const x = Math.max(0, startX);
                const width = Math.min(this.waveformData.canvasWidth, endX) - x;
                if (width > 0) {
                    // Determine border color based on punctuation in text
                    let borderColor = 'gold'; // default
                    let borderWidth = 1;
                    
                    if (trans.text) {
                        if (trans.text.includes('?') || trans.text.includes('!') || trans.text.includes('.')) {
                            // Darker shade for sentence endings
                            borderColor = '#DAA520'; // darker gold
                            borderWidth = 2;
                        } else if (trans.text.includes(',')) {
                            // Black border for commas (better visibility)
                            borderColor = 'black';
                            borderWidth = 1;
                        }
                    }
                    
                    ctx.strokeStyle = borderColor;
                    ctx.lineWidth = borderWidth;
                    ctx.fillRect(x, tracks.transcriptions, width, trackHeight);
                    ctx.strokeRect(x, tracks.transcriptions, width, trackHeight);
                }
            }
        });
    }

    updateTimeDisplay() {
        const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
        const viewEnd = Math.min(this.waveformData.viewStart + viewDuration, this.waveformData.duration);
        
        document.getElementById('startTime').textContent = this.formatTime(this.waveformData.viewStart);
        document.getElementById('endTime').textContent = this.formatTime(this.waveformData.duration);
        document.getElementById('currentPosition').textContent = this.formatTime(this.waveformData.viewStart + viewDuration / 2);
        
        // Update timeline thumb position and size
        if (this.updateTimelineThumb) {
            this.updateTimelineThumb();
        }
        
        // Update the new time displays
        this.updateTimeDisplays();
    }

    updateTimeDisplays() {
        // Update audio position in milliseconds
        const currentTime = this.getCurrentPlaybackTime();
        const audioPositionMs = Math.round(currentTime * 1000);
        document.getElementById('audioPositionMs').textContent = audioPositionMs;
        
        // Update mouse position in milliseconds
        let mousePositionMs = 0;
        if (this.waveformData.mouseX >= 0) {
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const timeOffset = (this.waveformData.mouseX / this.waveformData.canvasWidth) * viewDuration;
            const mouseTime = this.waveformData.viewStart + timeOffset;
            mousePositionMs = Math.round(mouseTime * 1000);
        }
        document.getElementById('mousePositionMs').textContent = mousePositionMs;
        
        // Update difference in milliseconds
        const timeDifferenceMs = mousePositionMs - audioPositionMs;
        document.getElementById('timeDifferenceMs').textContent = timeDifferenceMs;
    }

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    getCurrentPlaybackTime() {
        if (!this.isPlaying || !this.audioContext) {
            return this.audioStartOffset;
        }
        
        const elapsed = this.audioContext.currentTime - this.playStartTime;
        return this.audioStartOffset + elapsed;
    }

    checkSegmentOverlaps(segment, currentIndex) {
        // Check if this segment overlaps with any other segment
        for (let i = 0; i < this.waveformData.segments.length; i++) {
            if (i === currentIndex) continue; // Skip checking against itself
            
            const otherSegment = this.waveformData.segments[i];
            
            // Check for overlap: segments overlap if one starts before the other ends
            // and the other starts before the first one ends
            const segmentStart = segment.start;
            const segmentEnd = segment.end;
            const otherStart = otherSegment.start;
            const otherEnd = otherSegment.end;
            
            // Two segments overlap if:
            // segment.start < other.end AND other.start < segment.end
            if (segmentStart < otherEnd && otherStart < segmentEnd) {
                return true; // Found an overlap
            }
        }
        return false; // No overlaps found
    }

    checkSubsegmentOverlaps(parentSegment, currentSubIndex) {
        // Check if this subsegment overlaps with any other subsegment within the same segment
        if (!parentSegment.subs || !Array.isArray(parentSegment.subs)) {
            return false;
        }
        
        const currentSubsegment = parentSegment.subs[currentSubIndex];
        
        for (let i = 0; i < parentSegment.subs.length; i++) {
            if (i === currentSubIndex) continue; // Skip checking against itself
            
            const otherSubsegment = parentSegment.subs[i];
            
            // Check for overlap
            const subStart = currentSubsegment.start;
            const subEnd = currentSubsegment.end;
            const otherStart = otherSubsegment.start;
            const otherEnd = otherSubsegment.end;
            
            // Two subsegments overlap if:
            // subsegment.start < other.end AND other.start < subsegment.end
            if (subStart < otherEnd && otherStart < subEnd) {
                return true; // Found an overlap
            }
        }
        return false; // No overlaps found
    }

    displaySegmentsTable() {
        const dataViewer = document.getElementById('dataViewer');
        
        if (!this.waveformData.segments || this.waveformData.segments.length === 0) {
            dataViewer.innerHTML = '<p>No segments data available.</p>';
            return;
        }

        const subSegmentCount = this.waveformData.segments.reduce((acc, segment) => {
            return acc + (segment.subs && segment.subs.length > 1 ? segment.subs.length : 0);
        }, 0);

        // total length of audio in main segments
        const mainSegmentLength = this.waveformData.segments.reduce((acc, segment) => {
            return acc + (segment.end - segment.start);
        }, 0);

        const subSegmentLength = this.waveformData.segments.reduce((acc, segment) => {
            return acc + (segment.subs && segment.subs.length > 1 ? segment.subs.reduce((subAcc, sub) => {
                return subAcc + (sub.end - sub.start);
            }, 0) : 0);
        }, 0);

        // Calculate total length of good segments (main segments with status 'good')
        const goodMainSegmentLength = this.waveformData.segments.reduce((acc, segment) => {
            const status = segment.status !== undefined ? segment.status : (segment.confidence > 0.6 ? 'good' : 'bad');
            return acc + (status === 'good' ? (segment.end - segment.start) : 0);
        }, 0);

        // Calculate total length of good subsegments
        const goodSubSegmentLength = this.waveformData.segments.reduce((acc, segment) => {
            return acc + (segment.subs && segment.subs.length > 1 ? segment.subs.reduce((subAcc, sub) => {
                const status = sub.status !== undefined ? sub.status : (sub.confidence > 0.6 ? 'good' : 'bad');
                return subAcc + (status === 'good' ? (sub.end - sub.start) : 0);
            }, 0) : 0);
        }, 0);

        let html = `
            <h3>Segments (${this.waveformData.segments.length}) Subsegments (${subSegmentCount})</h3>
            <h5>Main Segment Length: ${(mainSegmentLength/60).toFixed(2)} min</h5>
            <h5>Sub Segment Length: ${(subSegmentLength/60).toFixed(2)} min</h5>
            <h5>Good Main Segment Length: ${(goodMainSegmentLength/60).toFixed(2)} min</h5>
            <h5>Good Sub Segment Length: ${(goodSubSegmentLength/60).toFixed(2)} min</h5>
            <div class="segments-actions">
                <div>
                    <button onclick="dataViewer.saveSegments()">Save Changes</button>
                    <button onclick="dataViewer.markAllGood()">Mark All Good</button>
                    <button onclick="dataViewer.markAllBad()">Mark All Bad</button>
                </div>
                <div>
                    <button onclick="buildSplits()" style="background-color: #28a745; color: white;">Build</button>
                </div>
            </div>
            <div class="segments-filters" style="margin: 10px 0; padding: 10px; background-color: #f8f9fa; border-radius: 5px;">
                <h4 style="margin: 0 0 10px 0;">Filters</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
                    <div>
                        <label>Status:</label>
                        <select id="filterStatus" onchange="dataViewer.applyFilters()">
                            <option value="">All</option>
                            <option value="good">Good</option>
                            <option value="bad">Bad</option>
                        </select>
                    </div>
                    <div>
                        <label>Speaker:</label>
                        <select id="filterSpeaker" onchange="dataViewer.applyFilters()">
                            <option value="">All</option>
                        </select>
                    </div>
                    <div>
                        <label>Text contains:</label>
                        <input type="text" id="filterText" placeholder="Search text..." onkeyup="dataViewer.applyFilters()" style="width: 150px;">
                    </div>
                    <div>
                        <label>Duration (ms):</label>
                        <input type="number" id="filterDurationMin" placeholder="Min" onchange="dataViewer.applyFilters()" style="width: 80px;">
                        <span> - </span>
                        <input type="number" id="filterDurationMax" placeholder="Max" onchange="dataViewer.applyFilters()" style="width: 80px;">
                    </div>
                    <div>
                        <label>Confidence (%):</label>
                        <input type="number" id="filterConfidenceMin" placeholder="Min" min="0" max="100" onchange="dataViewer.applyFilters()" style="width: 60px;">
                        <span> - </span>
                        <input type="number" id="filterConfidenceMax" placeholder="Max" min="0" max="100" onchange="dataViewer.applyFilters()" style="width: 60px;">
                    </div>
                    <div>
                        <button onclick="dataViewer.clearFilters()" style="background-color: #6c757d; color: white; border: none; padding: 5px 10px; border-radius: 3px;">Clear Filters</button>
                    </div>
                </div>
            </div>
            <div class="segments-table-container" id="segmentsTableContainer">
                <table class="segments-table">
                    <thead>
                        <tr style="background-color: #f0f0f0;">
                            <th>ID</th>
                            <th>Status</th>
                            <th>Speaker</th>
                            <th>Text</th>
                            <th>Start (ms)</th>
                            <th>End (ms)</th>
                            <th>Duration</th>
                            <th>Confidence</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="segmentsTableBody">
        `;

        this.waveformData.segments.forEach((segment, index) => {
            const startMs = Math.round(segment.start * 1000);
            const endMs = Math.round(segment.end * 1000);
            const duration = endMs - startMs;
            
            // Determine status based on confidence (default good if > 0.6)
            if (segment.status === undefined) {
                segment.status = segment.confidence > 0.6 ? 'good' : 'bad';
                
                // Check if segment overlaps with any other segment and mark as bad if it does
                const hasOverlap = this.checkSegmentOverlaps(segment, index);
                if (hasOverlap) {
                    segment.status = 'bad';
                }
            }
            
            const statusColor = segment.status === 'good' ? 'green' : 'red';
            const confidenceColor = segment.confidence > 0.6 ? 'green' : 'orange';
            const rowClass = segment.status === 'good' ? 'good' : 'bad';
            
            // Main segment row
            html += `
                <tr id="segment-row-${index}" class="segment-row ${rowClass}">
                    <td style="text-align: center; font-weight: bold;">${segment.seg_idx || index + 1}</td>
                    <td style="text-align: center;">
                        <select onchange="dataViewer.updateSegmentStatus(${index}, this.value)" class="status-${segment.status}">
                            <option value="good" ${segment.status === 'good' ? 'selected' : ''}>Good</option>
                            <option value="bad" ${segment.status === 'bad' ? 'selected' : ''}>Bad</option>
                        </select>
                    </td>
                    <td>
                        <input type="text" value="${segment.speaker || ''}" 
                               onchange="dataViewer.updateSegmentField(${index}, 'speaker', this.value)">
                    </td>
                    <td>
                        <textarea onchange="dataViewer.updateSegmentField(${index}, 'text', this.value)">${segment.text || ''}</textarea>
                    </td>
                    <td>
                        <input type="number" value="${startMs}" 
                               onchange="dataViewer.updateSegmentTime(${index}, 'start', this.value)">
                    </td>
                    <td>
                        <input type="number" value="${endMs}" 
                               onchange="dataViewer.updateSegmentTime(${index}, 'end', this.value)">
                    </td>
                    <td style="text-align: center;">${duration}ms</td>
                    <td style="text-align: center;" class="confidence-${segment.confidence > 0.6 ? 'good' : 'bad'}">
                        ${(segment.confidence * 100).toFixed(1)}%
                    </td>
                    <td style="text-align: center;">
                        <div class="action-buttons">
                            <button onclick="dataViewer.playSegment(${index})" class="play-button">▶</button>
                            <button onclick="dataViewer.seekToSegment(${index})" class="seek-button">↗</button>
                            <button onclick="dataViewer.deleteSegment(${index})" class="delete-button">✖</button>
                        </div>
                    </td>
                </tr>
            `;

            // Add subsegments if they exist
            if (segment.subs && Array.isArray(segment.subs) && segment.subs.length > 1) {
                segment.subs.forEach((subsegment, subIndex) => {
                    const subStartMs = Math.round(subsegment.start * 1000);
                    const subEndMs = Math.round(subsegment.end * 1000);
                    const subDuration = subEndMs - subStartMs;
                    
                    // Determine status for subsegment
                    if (subsegment.status === undefined) {
                        subsegment.status = subsegment.confidence > 0.6 ? 'good' : 'bad';
                        
                        // Check if subsegment overlaps with other subsegments in the same segment
                        const hasOverlap = this.checkSubsegmentOverlaps(segment, subIndex);
                        if (hasOverlap) {
                            subsegment.status = 'bad';
                        }
                    }
                    
                    const subStatusColor = subsegment.status === 'good' ? 'green' : 'red';
                    const subConfidenceColor = subsegment.confidence > 0.6 ? 'green' : 'orange';
                    const subRowClass = subsegment.status === 'good' ? 'good' : 'bad';
                    
                    html += `
                        <tr id="subsegment-row-${index}-${subIndex}" class="subsegment-row ${subRowClass}">
                            <td style="text-align: center; font-size: 10px; color: #666;">${segment.seg_idx || index + 1}.${subIndex + 1}</td>
                            <td style="text-align: center;">
                                <select onchange="dataViewer.updateSubsegmentStatus(${index}, ${subIndex}, this.value)" class="status-${subsegment.status}">
                                    <option value="good" ${subsegment.status === 'good' ? 'selected' : ''}>Good</option>
                                    <option value="bad" ${subsegment.status === 'bad' ? 'selected' : ''}>Bad</option>
                                </select>
                            </td>
                            <td>
                                <input type="text" value="${subsegment.speaker || ''}" 
                                       onchange="dataViewer.updateSubsegmentField(${index}, ${subIndex}, 'speaker', this.value)">
                            </td>
                            <td>
                                <textarea onchange="dataViewer.updateSubsegmentField(${index}, ${subIndex}, 'text', this.value)">${subsegment.text || ''}</textarea>
                            </td>
                            <td>
                                <input type="number" value="${subStartMs}" 
                                       onchange="dataViewer.updateSubsegmentTime(${index}, ${subIndex}, 'start', this.value)">
                            </td>
                            <td>
                                <input type="number" value="${subEndMs}" 
                                       onchange="dataViewer.updateSubsegmentTime(${index}, ${subIndex}, 'end', this.value)">
                            </td>
                            <td style="text-align: center; font-size: 11px; color: #555;">${subDuration}ms</td>
                            <td style="text-align: center;" class="confidence-${subsegment.confidence > 0.6 ? 'good' : 'bad'}">
                                ${(subsegment.confidence * 100).toFixed(1)}%
                            </td>
                            <td style="text-align: center;">
                                <div class="action-buttons">
                                    <button onclick="dataViewer.playSubsegment(${index}, ${subIndex})" class="play-button">▶</button>
                                    <button onclick="dataViewer.seekToSubsegment(${index}, ${subIndex})" class="seek-button">↗</button>
                                    <button onclick="dataViewer.deleteSubsegment(${index}, ${subIndex})" class="delete-button">✖</button>
                                </div>
                            </td>
                        </tr>
                    `;
                });
            }
        });

        html += `
                </tbody>
            </table>
            </div>
            <div class="segments-legend">
                <p><strong>Legend:</strong> ▶ = Play segment/subsegment, ↗ = Seek to segment/subsegment, ✖ = Delete segment</p>
                <p><strong>Status:</strong> Good segments will be included in final dataset, Bad segments will be excluded</p>
                <p><strong>Types:</strong> Segment = Main segment, Sub = Subsegment (part of main segment)</p>
            </div>
        `;

        dataViewer.innerHTML = html;
        
        // Setup scroll synchronization after the table is rendered
        this.setupScrollSynchronization();
        
        // Populate speaker dropdown with unique speakers
        this.populateSpeakerFilter();
        
        // Render the table content
        this.renderSegmentsTable();
    }

    populateSpeakerFilter() {
        const speakerSelect = document.getElementById('filterSpeaker');
        if (!speakerSelect) return;
        
        // Get unique speakers from segments and subsegments
        const speakers = new Set();
        this.waveformData.segments.forEach(segment => {
            if (segment.speaker) speakers.add(segment.speaker);
            if (segment.subs) {
                segment.subs.forEach(sub => {
                    if (sub.speaker) speakers.add(sub.speaker);
                });
            }
        });
        
        // Clear existing options except "All"
        speakerSelect.innerHTML = '<option value="">All</option>';
        
        // Add unique speakers
        Array.from(speakers).sort().forEach(speaker => {
            const option = document.createElement('option');
            option.value = speaker;
            option.textContent = speaker;
            speakerSelect.appendChild(option);
        });
    }

    renderSegmentsTable() {
        const tableBody = document.getElementById('segmentsTableBody');
        if (!tableBody) return;
        
        let tableHtml = '';
        
        this.waveformData.segments.forEach((segment, index) => {
            const startMs = Math.round(segment.start * 1000);
            const endMs = Math.round(segment.end * 1000);
            const duration = endMs - startMs;
            
            // Determine status based on confidence (default good if > 0.6)
            if (segment.status === undefined) {
                segment.status = segment.confidence > 0.6 ? 'good' : 'bad';
                
                // Check if segment overlaps with any other segment and mark as bad if it does
                const hasOverlap = this.checkSegmentOverlaps(segment, index);
                if (hasOverlap) {
                    segment.status = 'bad';
                }
            }
            
            // Apply filters
            if (!this.passesFilters(segment, startMs, endMs, duration)) {
                return; // Skip this segment if it doesn't pass filters
            }
            
            const statusColor = segment.status === 'good' ? 'green' : 'red';
            const confidenceColor = segment.confidence > 0.6 ? 'green' : 'orange';
            const rowClass = segment.status === 'good' ? 'good' : 'bad';
            
            // Main segment row
            tableHtml += `
                <tr id="segment-row-${index}" class="segment-row ${rowClass}">
                    <td style="text-align: center; font-weight: bold;">${segment.seg_idx || index + 1}</td>
                    <td style="text-align: center;">
                        <select onchange="dataViewer.updateSegmentStatus(${index}, this.value)" class="status-${segment.status}">
                            <option value="good" ${segment.status === 'good' ? 'selected' : ''}>Good</option>
                            <option value="bad" ${segment.status === 'bad' ? 'selected' : ''}>Bad</option>
                        </select>
                    </td>
                    <td>
                        <input type="text" value="${segment.speaker || ''}" 
                               onchange="dataViewer.updateSegmentField(${index}, 'speaker', this.value)">
                    </td>
                    <td>
                        <textarea onchange="dataViewer.updateSegmentField(${index}, 'text', this.value)">${segment.text || ''}</textarea>
                    </td>
                    <td>
                        <input type="number" value="${startMs}" 
                               onchange="dataViewer.updateSegmentTime(${index}, 'start', this.value)">
                    </td>
                    <td>
                        <input type="number" value="${endMs}" 
                               onchange="dataViewer.updateSegmentTime(${index}, 'end', this.value)">
                    </td>
                    <td style="text-align: center;">${duration}ms</td>
                    <td style="text-align: center;" class="confidence-${segment.confidence > 0.6 ? 'good' : 'bad'}">
                        ${(segment.confidence * 100).toFixed(1)}%
                    </td>
                    <td style="text-align: center;">
                        <div class="action-buttons">
                            <button onclick="dataViewer.playSegment(${index})" class="play-button">▶</button>
                            <button onclick="dataViewer.seekToSegment(${index})" class="seek-button">↗</button>
                            <button onclick="dataViewer.deleteSegment(${index})" class="delete-button">✖</button>
                        </div>
                    </td>
                </tr>
            `;

            // Add subsegments if they exist
            if (segment.subs && Array.isArray(segment.subs) && segment.subs.length > 1) {
                segment.subs.forEach((subsegment, subIndex) => {
                    const subStartMs = Math.round(subsegment.start * 1000);
                    const subEndMs = Math.round(subsegment.end * 1000);
                    const subDuration = subEndMs - subStartMs;
                    
                    // Determine status for subsegment
                    if (subsegment.status === undefined) {
                        subsegment.status = subsegment.confidence > 0.6 ? 'good' : 'bad';
                        
                        // Check if subsegment overlaps with other subsegments in the same segment
                        const hasOverlap = this.checkSubsegmentOverlaps(segment, subIndex);
                        if (hasOverlap) {
                            subsegment.status = 'bad';
                        }
                    }
                    
                    // Apply filters to subsegments
                    if (!this.passesFilters(subsegment, subStartMs, subEndMs, subDuration)) {
                        return; // Skip this subsegment if it doesn't pass filters
                    }
                    
                    const subStatusColor = subsegment.status === 'good' ? 'green' : 'red';
                    const subConfidenceColor = subsegment.confidence > 0.6 ? 'green' : 'orange';
                    const subRowClass = subsegment.status === 'good' ? 'good' : 'bad';
                    
                    tableHtml += `
                        <tr id="subsegment-row-${index}-${subIndex}" class="subsegment-row ${subRowClass}">
                            <td style="text-align: center; font-size: 10px; color: #666;">${segment.seg_idx || index + 1}.${subIndex + 1}</td>
                            <td style="text-align: center;">
                                <select onchange="dataViewer.updateSubsegmentStatus(${index}, ${subIndex}, this.value)" class="status-${subsegment.status}">
                                    <option value="good" ${subsegment.status === 'good' ? 'selected' : ''}>Good</option>
                                    <option value="bad" ${subsegment.status === 'bad' ? 'selected' : ''}>Bad</option>
                                </select>
                            </td>
                            <td>
                                <input type="text" value="${subsegment.speaker || ''}" 
                                       onchange="dataViewer.updateSubsegmentField(${index}, ${subIndex}, 'speaker', this.value)">
                            </td>
                            <td>
                                <textarea onchange="dataViewer.updateSubsegmentField(${index}, ${subIndex}, 'text', this.value)">${subsegment.text || ''}</textarea>
                            </td>
                            <td>
                                <input type="number" value="${subStartMs}" 
                                       onchange="dataViewer.updateSubsegmentTime(${index}, ${subIndex}, 'start', this.value)">
                            </td>
                            <td>
                                <input type="number" value="${subEndMs}" 
                                       onchange="dataViewer.updateSubsegmentTime(${index}, ${subIndex}, 'end', this.value)">
                            </td>
                            <td style="text-align: center; font-size: 11px; color: #555;">${subDuration}ms</td>
                            <td style="text-align: center;" class="confidence-${subsegment.confidence > 0.6 ? 'good' : 'bad'}">
                                ${(subsegment.confidence * 100).toFixed(1)}%
                            </td>
                            <td style="text-align: center;">
                                <div class="action-buttons">
                                    <button onclick="dataViewer.playSubsegment(${index}, ${subIndex})" class="play-button">▶</button>
                                    <button onclick="dataViewer.seekToSubsegment(${index}, ${subIndex})" class="seek-button">↗</button>
                                    <button onclick="dataViewer.deleteSubsegment(${index}, ${subIndex})" class="delete-button">✖</button>
                                </div>
                            </td>
                        </tr>
                    `;
                });
            }
        });

        tableBody.innerHTML = tableHtml;
        
        // Re-setup scroll synchronization after table content changes
        setTimeout(() => {
            this.syncTableFromWaveform();
        }, 100);
    }

    passesFilters(item, startMs, endMs, duration) {
        // Get filter values
        const statusFilter = document.getElementById('filterStatus')?.value || '';
        const speakerFilter = document.getElementById('filterSpeaker')?.value || '';
        const textFilter = document.getElementById('filterText')?.value.toLowerCase() || '';
        const durationMin = parseInt(document.getElementById('filterDurationMin')?.value) || 0;
        const durationMax = parseInt(document.getElementById('filterDurationMax')?.value) || Infinity;
        const confidenceMin = parseFloat(document.getElementById('filterConfidenceMin')?.value) / 100 || 0;
        const confidenceMax = parseFloat(document.getElementById('filterConfidenceMax')?.value) / 100 || 1;
        
        // Apply filters
        if (statusFilter && item.status !== statusFilter) return false;
        if (speakerFilter && item.speaker !== speakerFilter) return false;
        if (textFilter && !item.text?.toLowerCase().includes(textFilter)) return false;
        if (duration < durationMin || duration > durationMax) return false;
        if (item.confidence < confidenceMin || item.confidence > confidenceMax) return false;
        
        return true;
    }

    applyFilters() {
        this.renderSegmentsTable();
    }

    clearFilters() {
        // Clear all filter inputs
        document.getElementById('filterStatus').value = '';
        document.getElementById('filterSpeaker').value = '';
        document.getElementById('filterText').value = '';
        document.getElementById('filterDurationMin').value = '';
        document.getElementById('filterDurationMax').value = '';
        document.getElementById('filterConfidenceMin').value = '';
        document.getElementById('filterConfidenceMax').value = '';
        
        // Re-render table
        this.renderSegmentsTable();
    }

    // Segment manipulation methods
    updateSegmentStatus(index, status) {
        this.waveformData.segments[index].status = status;
        
        // Update row background color
        const row = document.getElementById(`segment-row-${index}`);
        row.className = `segment-row ${status}`;
        
        // Update select color
        const select = row.querySelector('select');
        select.className = `status-${status}`;
    }

    updateSegmentField(index, field, value) {
        this.waveformData.segments[index][field] = value;
    }

    updateSegmentTime(index, timeType, valueMs) {
        const timeInSeconds = parseFloat(valueMs) / 1000;
        
        if (timeType === 'start') {
            this.waveformData.segments[index].start = timeInSeconds;
        } else if (timeType === 'end') {
            this.waveformData.segments[index].end = timeInSeconds;
        }
        
        // Update duration display
        const row = document.getElementById(`segment-row-${index}`);
        const startMs = Math.round(this.waveformData.segments[index].start * 1000);
        const endMs = Math.round(this.waveformData.segments[index].end * 1000);
        const duration = endMs - startMs;
        
        const durationCell = row.cells[6]; // Duration column
        durationCell.textContent = duration + 'ms';
        
        // Redraw waveform to show updated segment boundaries
        this.drawWaveform();
    }

    updateSubsegmentStatus(segmentIndex, subsegmentIndex, status) {
        this.waveformData.segments[segmentIndex].subs[subsegmentIndex].status = status;
        
        // Update row background color
        const row = document.getElementById(`subsegment-row-${segmentIndex}-${subsegmentIndex}`);
        row.className = `subsegment-row ${status}`;
        
        // Update select color
        const select = row.querySelector('select');
        select.className = `status-${status}`;
    }

    updateSubsegmentField(segmentIndex, subsegmentIndex, field, value) {
        this.waveformData.segments[segmentIndex].subs[subsegmentIndex][field] = value;
    }

    updateSubsegmentTime(segmentIndex, subsegmentIndex, timeType, valueMs) {
        const timeInSeconds = parseFloat(valueMs) / 1000;
        const subsegment = this.waveformData.segments[segmentIndex].subs[subsegmentIndex];
        
        if (timeType === 'start') {
            subsegment.start = timeInSeconds;
        } else if (timeType === 'end') {
            subsegment.end = timeInSeconds;
        }
        
        // Update duration display
        const row = document.getElementById(`subsegment-row-${segmentIndex}-${subsegmentIndex}`);
        const startMs = Math.round(subsegment.start * 1000);
        const endMs = Math.round(subsegment.end * 1000);
        const duration = endMs - startMs;
        
        const durationCell = row.cells[6]; // Duration column
        durationCell.textContent = duration + 'ms';
        
        // Redraw waveform to show updated subsegment boundaries
        this.drawWaveform();
    }

    seekToTime(timeInSeconds) {
        this.audioController.seekToTime(timeInSeconds);
    }

    // Audio control methods - delegate to audio controller
    playSegment(index) {
        this.audioController.playSegment(index);
    }

    seekToSegment(index) {
        this.audioController.seekToSegment(index);
    }

    playSubsegment(segmentIndex, subsegmentIndex) {
        this.audioController.playSubsegment(segmentIndex, subsegmentIndex);
    }

    seekToSubsegment(segmentIndex, subsegmentIndex) {
        this.audioController.seekToSubsegment(segmentIndex, subsegmentIndex);
    }

    // Segments management methods - delegate to segments manager
    deleteSegment(index) {
        this.segmentsManager.deleteSegment(index);
    }

    deleteSubsegment(segmentIndex, subsegmentIndex) {
        this.segmentsManager.deleteSubsegment(segmentIndex, subsegmentIndex);
    }

    markAllGood() {
        this.segmentsManager.markAllGood();
    }

    markAllBad() {
        this.segmentsManager.markAllBad();
    }

    saveSegments() {
        this.segmentsManager.saveSegments();
    }

    // Scroll synchronization methods
    setupScrollSynchronization() {
        const tableContainer = document.getElementById('segmentsTableContainer');
        if (!tableContainer) return;

        // Add scroll listener to the table container
        tableContainer.addEventListener('scroll', () => {
            this.syncWaveformFromTable();
        });

        // Also sync when waveform view changes - but only wrap once
        if (!this.originalDrawWaveform) {
            this.originalDrawWaveform = this.drawWaveform;
            this.drawWaveform = () => {
                this.originalDrawWaveform();
                this.syncTableFromWaveform();
            };
        }
    }

    syncWaveformFromTable() {
        const tableContainer = document.getElementById('segmentsTableContainer');
        if (!tableContainer) return;

        // Get the middle visible segment in the table
        const containerRect = tableContainer.getBoundingClientRect();
        const containerMiddleY = containerRect.top + containerRect.height / 2;
        
        // Find all segment rows that are currently visible
        const segmentRows = tableContainer.querySelectorAll('.segment-row');
        let middleSegmentIndex = -1;
        let middleSegmentTime = 0;

        for (let i = 0; i < segmentRows.length; i++) {
            const row = segmentRows[i];
            const rowRect = row.getBoundingClientRect();
            
            // Check if this row is near the middle of the visible area
            if (rowRect.top <= containerMiddleY && rowRect.bottom >= containerMiddleY) {
                // Extract segment index from row ID
                const rowId = row.id; // format: "segment-row-{index}"
                const match = rowId.match(/segment-row-(\d+)/);
                if (match) {
                    middleSegmentIndex = parseInt(match[1]);
                    break;
                }
            }
        }

        // If we found a middle segment, center the waveform on it
        if (middleSegmentIndex >= 0 && middleSegmentIndex < this.waveformData.segments.length) {
            const segment = this.waveformData.segments[middleSegmentIndex];
            const segmentMiddleTime = (segment.start + segment.end) / 2;
            
            // Calculate the view duration and center on the segment
            const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
            const newViewStart = Math.max(0, Math.min(
                segmentMiddleTime - viewDuration / 2,
                this.waveformData.duration - viewDuration
            ));
            
            // Only update if there's a significant change to avoid infinite loops
            if (Math.abs(newViewStart - this.waveformData.viewStart) > 0.1) {
                this.waveformData.viewStart = newViewStart;
                this.originalDrawWaveform(); // Use original to avoid recursion
                this.updateTimeDisplay();
            }
        }
    }

    syncTableFromWaveform() {
        const tableContainer = document.getElementById('segmentsTableContainer');
        if (!tableContainer) return;

        // Get the current waveform view center time
        const viewDuration = (this.waveformData.canvasWidth * this.waveformData.zoom) / 1000;
        const waveformCenterTime = this.waveformData.viewStart + viewDuration / 2;

        // Find the segment that contains or is closest to the waveform center
        let targetSegmentIndex = -1;
        let minDistance = Infinity;

        for (let i = 0; i < this.waveformData.segments.length; i++) {
            const segment = this.waveformData.segments[i];
            const segmentMiddleTime = (segment.start + segment.end) / 2;
            const distance = Math.abs(segmentMiddleTime - waveformCenterTime);
            
            if (distance < minDistance) {
                minDistance = distance;
                targetSegmentIndex = i;
            }
        }

        // Scroll the table to center the target segment
        if (targetSegmentIndex >= 0) {
            const targetRow = document.getElementById(`segment-row-${targetSegmentIndex}`);
            if (targetRow) {
                const containerRect = tableContainer.getBoundingClientRect();
                const rowRect = targetRow.getBoundingClientRect();
                const rowOffsetInContainer = targetRow.offsetTop - tableContainer.scrollTop;
                
                // Calculate the scroll position to center the row
                const targetScrollTop = targetRow.offsetTop - (containerRect.height / 2) + (rowRect.height / 2);
                
                // Only scroll if the row is not already roughly centered
                const currentRowCenter = rowOffsetInContainer + rowRect.height / 2;
                const containerCenter = containerRect.height / 2;
                
                if (Math.abs(currentRowCenter - containerCenter) > 50) { // 50px tolerance
                    tableContainer.scrollTop = Math.max(0, targetScrollTop);
                }
            }
        }
    }
}

// Create global instance
let dataViewer = new DataViewer();

// Global functions for backward compatibility
function loadData() {
    dataViewer.loadData();
}

function setZoom(millisecondsPerPixel) {
    dataViewer.setZoom(millisecondsPerPixel);
}
