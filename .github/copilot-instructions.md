# Speech Dataset Creator

A comprehensive AI-powered pipeline for processing podcast audio files to create high-quality speech datasets for text-to-speech (TTS) training. This tool automates the entire process from raw audio to segmented, transcribed, and phonetically aligned speech data.

**ALWAYS follow these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### Prerequisites and System Setup
- Install system dependencies first:
  ```bash
  # For Ubuntu/Debian systems
  sudo apt-get update
  sudo apt-get install -y ffmpeg git wget curl nano build-essential libsndfile1 libsox-fmt-all sox libsox-dev portaudio19-dev python3-dev
  ```
- **Required:** Hugging Face token for pyannote.audio models - get from https://huggingface.co/settings/tokens
- **Recommended:** CUDA-compatible GPU for faster processing

### Local Development Setup
- **ALWAYS** set up the environment in this exact order:
  ```bash
  # 1. Clone and navigate to repository
  git clone <repository_url>
  cd speech_dataset_creator
  
  # 2. Create and activate virtual environment
  python3 -m venv venv
  source venv/bin/activate  # On macOS/Linux
  # venv\Scripts\activate   # On Windows
  
  # 3. Upgrade pip first
  pip install --upgrade pip
  
  # 4. Install Python dependencies - takes 5-10 minutes. NEVER CANCEL.
  pip install -r requirements.txt
  ```
  **TIMEOUT WARNING:** Set timeout to 15+ minutes for `pip install`. NEVER CANCEL dependency installation.

- **ALWAYS** create environment configuration:
  ```bash
  # 5. Copy environment template
  cp .env.example .env
  
  # 6. Edit .env file and set your Hugging Face token
  # REQUIRED: Set HF_TOKEN=your_huggingface_token_here
  ```

### Docker Setup (Recommended for Production)
- **Method 1 - Docker Compose (Recommended):**
  ```bash
  # Ensure .env file exists with HF_TOKEN
  cp .env.example .env
  # Edit .env and set HF_TOKEN=your_token_here
  
  # Build and start - takes 15-30 minutes. NEVER CANCEL.
  docker compose up --build
  ```
  **TIMEOUT WARNING:** Set timeout to 45+ minutes for Docker build. NEVER CANCEL Docker operations.

- **Method 2 - Direct Docker:**
  ```bash
  # Build image - takes 15-30 minutes. NEVER CANCEL.
  docker build -t speech-dataset-creator .
  
  # Run with GPU support
  docker run --gpus all -p 5000:5000 \
    -v ./projects:/workspace/projects \
    -v ./output:/workspace/output \
    -v ./raw:/workspace/raw \
    -v ./.env:/workspace/.env:ro \
    speech-dataset-creator
  ```

### Running the Application

#### Web Interface (Recommended)
- **Start the Flask server:**
  ```bash
  # Local development
  source venv/bin/activate
  python _server.py
  ```
- **Access:** Open browser to http://localhost:5000
- **First-time model downloads:** 10-60 minutes depending on models. NEVER CANCEL.

#### Command Line Pipeline
- **Single file processing:**
  ```bash
  source venv/bin/activate
  python run.py path/to/audio.mp3
  ```
- **Processing time:** Varies by file size and content (10 minutes to several hours for long podcasts)

#### Individual Module Scripts
- **Audio cleaning:** `python m1_clean.py <input> <output>`
- **Silence detection:** `python m2_silences.py <input>`
- **Audio splitting:** `python m3_split.py <input> <output_dir>`
- **Transcription:** `python m4_transcribe_file.py <input>`
- **Speaker diarization:** `python m5_pyannote.py <input>` (or m5_wespeaker.py, m5_3dspeaker.py)
- **Audio segmentation:** `python m6_segment.py <audio> <transcription> <segments>`
- **Validation:** `python m7_validate.py <project_directory>`
- **Metadata generation:** `python m8_meta.py <project_directory> <output>`
- **Phonetic alignment:** `python m9_align_and_phonetize.py <project_directory>`
- **Dataset archiving:** `python m10_archive.py <project_directory> <archive_output>`

## Project Structure and Key Locations

### Repository Layout
```
├── _server.py              # Flask web server entry point
├── run.py                  # CLI pipeline entry point
├── run_all.py             # Batch processing script
├── m0_get.py              # Module 0: Podcast download
├── m1_clean.py            # Module 1: Audio cleaning
├── m2_silences.py         # Module 2: Silence detection
├── m3_split.py            # Module 3: Audio splitting
├── m4_transcribe_file.py  # Module 4: Transcription
├── m5_*.py                # Module 5: Speaker diarization (3 backends)
├── m6_segment.py          # Module 6: Audio segmentation
├── m7_validate.py         # Module 7: Validation
├── m8_meta.py             # Module 8: Metadata generation
├── m9_align_and_phonetize.py # Module 9: Phonetic alignment
├── m10_archive.py         # Module 10: Dataset archiving
├── web/                   # Web interface files
├── server/                # Flask server modules
├── projects/              # Project workspaces (created at runtime)
├── output/                # Processing output (created at runtime)
├── raw/                   # Raw audio files (created at runtime)
├── checkpoints/           # Model checkpoints (created at runtime)
└── requirements.txt       # Python dependencies
```

### Key Configuration Files
- **.env:** Environment variables including HF_TOKEN (required)
- **docker-compose.yml:** Complete Docker stack configuration
- **dockerfile:** Docker image build instructions
- **requirements.txt:** Python package dependencies

## Processing Pipeline Overview
The system processes audio through a 10-module pipeline:
1. **m0:** Download podcasts (optional)
2. **m1:** Clean and enhance audio quality
3. **m2:** Detect silence regions for optimal splitting
4. **m3:** Split audio into manageable segments
5. **m4:** Transcribe speech to text
6. **m5:** Identify and separate speakers (diarization)
7. **m6:** Segment audio based on speaker and timing
8. **m7:** Validate transcription quality
9. **m8:** Generate metadata for the dataset
10. **m9:** Align text with phonemes for TTS training
11. **m10:** Archive the final dataset

## Validation and Testing

### Manual Validation Requirements
**ALWAYS** validate your changes by running through complete user scenarios:

#### Web Interface Validation
1. **Start the server:** `python _server.py`
2. **Access:** http://localhost:5000
3. **Test project creation:** Create a new project with custom settings
4. **Test file upload:** Upload a small audio file (.wav or .mp3)
5. **Test processing:** Run the pipeline on the uploaded file
6. **Verify output:** Check that processed files appear in projects directory

#### CLI Validation  
1. **Create test audio:** Use a short (30-60 second) audio file
2. **Run pipeline:** `python run.py test_audio.mp3`
3. **Verify processing:** Check output directory for:
   - Cleaned audio files
   - Transcription files
   - Speaker segmentation
   - Validation reports

#### Docker Validation
1. **Build container:** `docker compose up --build`
2. **Access web interface:** http://localhost:5000
3. **Test complete workflow:** Upload file and process through pipeline

### Expected Timing and Timeout Values
- **Initial pip install:** 5-10 minutes - **TIMEOUT: 15+ minutes**
- **Docker build:** 15-30 minutes - **TIMEOUT: 45+ minutes**
- **First model downloads:** 10-60 minutes - **TIMEOUT: 90+ minutes**
- **Audio processing (small file):** 2-10 minutes
- **Audio processing (podcast episode):** 30 minutes to 3+ hours
- **Full pipeline (1-hour podcast):** 1-4 hours depending on hardware

**CRITICAL:** NEVER CANCEL long-running operations. Models downloads and processing can take substantial time.

## Common Development Tasks

### Debugging Failed Processing
- **Check logs:** Processing status visible in web interface or terminal output
- **Validate environment:** Ensure HF_TOKEN is set correctly
- **Check disk space:** Processing creates temporary files that can be large
- **GPU issues:** Reduce batch size or use CPU processing if CUDA errors occur

### Adding New Speaker Diarization Backends
- **Current backends:** pyannote (m5_pyannote.py), wespeaker (m5_wespeaker.py), 3dspeaker (m5_3dspeaker.py)
- **Integration:** Follow existing module pattern for consistent API

### Working with Project Settings
- **Default settings:** Defined in web interface and .env.example
- **Customization:** Each project can have unique silence thresholds, language settings, speaker limits
- **Location:** Project settings stored in `projects/<project_name>/settings.json`

### Model Management
- **Cache locations:** Models downloaded to ./torch_cache, ./hf_cache, ./transformers_cache
- **Checkpoints:** Place pre-trained models in ./checkpoints/ directory
- **Required models:** Download happens automatically on first use

## Troubleshooting

### Common Issues and Solutions
1. **CUDA out of memory:** Reduce batch size or use CPU processing
2. **Model download failures:** Check internet connection and HF_TOKEN validity
3. **Audio format errors:** Ensure FFmpeg is properly installed
4. **Permission errors:** Check file permissions and Docker volume mounts
5. **Import errors:** Verify virtual environment is activated and dependencies installed

### Environment Debugging
```bash
# Enable verbose logging
export PYTHONPATH=$PYTHONPATH:$(pwd)
export CUDA_LAUNCH_BLOCKING=1  # For CUDA debugging

# Verify FFmpeg installation
ffmpeg -version

# Test Python imports
python -c "import soundfile; print('soundfile OK')"
python -c "import flask; print('flask OK')"
```

### Docker Troubleshooting
- **Build failures:** Check internet connectivity for package downloads
- **Permission issues:** Ensure Docker has access to mounted directories
- **GPU not detected:** Verify nvidia-docker runtime is installed

## Performance Tips
- **Use GPU acceleration** when available for faster processing
- **Process smaller batches** if memory constraints occur
- **Monitor disk space** as temporary files can be large
- **Use Docker for consistent environments** across different systems

## Notes for AI-Generated Code
- **This codebase is fully AI-generated** as noted in README.md
- **Consistent patterns:** All modules follow similar structure and error handling
- **Configuration-driven:** Most behavior controlled via environment variables and project settings
- **Modular design:** Each processing step is independent and can be run individually