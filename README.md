# Speech Dataset Creator

A comprehensive pipeline for processing podcast audio files to create high-quality speech datasets for text-to-speech (TTS) training. This tool automates the entire process from raw audio to segmented, transcribed, and phonetically aligned speech data.

## Features

- **Audio Enhancement**: Remove background noise, echo, and reverb using ClearVoice MossFormer2
- **Speaker Diarization**: Identify and separate different speakers using pyannote.audio
- **Speech-to-Text Transcription**: Automatic transcription of audio content
- **Silence Detection**: Identify and mark silent segments in audio
- **Audio Segmentation**: Split audio into manageable chunks
- **Validation**: Quality checks for transcriptions and alignments
- **Metadata Generation**: Create comprehensive metadata for the dataset
- **Web Interface**: User-friendly web interface for project management
- **Docker Support**: Easy deployment with Docker and Docker Compose

## Project Structure

```
├── _server.py              # Flask web server
├── run.py                  # Main pipeline script
├── m0_get.py              # Download podcasts from websites
├── m1_clean.py            # Audio enhancement and noise removal
├── m2_silences.py         # Silence detection
├── m3_split.py            # Audio splitting
├── m4_transcribe_file.py  # Speech-to-text transcription
├── m5_pyannote.py         # Speaker diarization
├── m6_segment.py          # Audio segmentation
├── m7_validate.py         # Validation of transcriptions
├── m8_meta.py             # Metadata generation
├── m9_align_and_phonetize.py # Phonetic alignment
├── m10_archive.py         # Dataset archiving
├── web/                   # Web interface files
├── server/                # Flask server modules
├── projects/              # Project workspaces
├── output/                # Processing output
├── raw/                   # Raw audio files
└── checkpoints/           # Model checkpoints
```

## Installation

### Prerequisites

- Python 3.8+
- FFmpeg
- CUDA-compatible GPU (recommended for faster processing)

### Local Installation

1. Clone the repository:
```bash
git clone <repository_url>
cd speech_dataset_creator
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate     # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your configuration:
```bash
# Add any required API keys or configuration
HF_TOKEN=your_huggingface_token_here
```

## Usage

### Method 1: Web Interface (Recommended)

Start the web server for an intuitive graphical interface:

```bash
python _server.py
```

The web interface will be available at `http://localhost:5000`. This provides:
- Project management
- File upload and processing
- Real-time status monitoring
- Visual data exploration

### Method 2: Command Line Pipeline

Process a single audio file through the complete pipeline:

```bash
python run.py <audio_file_path> [output_directory] [--override] [--segment]
```

**Arguments:**
- `audio_file_path`: Path to your input audio file (required)
- `output_directory`: Directory for outputs (optional, defaults to `./output`)
- `--override`: Overwrite existing files (optional)
- `--segment`: Enable audio segmentation (optional)

**Example:**
```bash
python run.py ./raw/podcast.mp3 ./output --override --segment
```

### Method 3: Individual Module Scripts

Run specific processing steps individually:

#### m0_get.py - Download Podcasts
```bash
python m0_get.py --podcast <podcast_name> --pages <num_pages> --output <output_dir>
```

#### m1_clean.py - Audio Enhancement
```bash
python m1_clean.py <input_audio> <output_audio>
```

#### m2_silences.py - Silence Detection
```bash
python m2_silences.py <audio_file> <output_json>
```

#### m3_split.py - Audio Splitting
```bash
python m3_split.py <audio_file> <output_directory>
```

#### m4_transcribe_file.py - Transcription
```bash
python m4_transcribe_file.py <audio_file> <output_json>
```

#### m5_pyannote.py - Speaker Diarization
```bash
python m5_pyannote.py <audio_file> <output_prefix>
```

#### m6_segment.py - Audio Segmentation
```bash
python m6_segment.py <audio_file> <transcription_file> <segments_file>
```

#### m7_validate.py - Validation
```bash
python m7_validate.py <project_directory>
```

#### m8_meta.py - Metadata Generation
```bash
python m8_meta.py <project_directory> <metadata_output>
```

#### m9_align_and_phonetize.py - Phonetic Alignment
```bash
python m9_align_and_phonetize.py <project_directory>
```

#### m10_archive.py - Dataset Archiving
```bash
python m10_archive.py <project_directory> <archive_output>
```

## Docker Usage

### Method 1: Docker Compose (Recommended)

1. Start the complete stack:
```bash
docker-compose up -d
```

2. Access the web interface at `http://localhost:5000`

3. Stop the stack:
```bash
docker-compose down
```

### Method 2: Docker Build and Run

1. Build the Docker image:
```bash
docker build -t speech-dataset-creator .
```

2. Run the web server:
```bash
docker run -p 5000:5000 \
  -v ./projects:/workspace/projects \
  -v ./output:/workspace/output \
  -v ./raw:/workspace/raw \
  -v ./.env:/workspace/.env:ro \
  speech-dataset-creator
```

3. Run the pipeline directly:
```bash
docker run -it --rm \
  -v ./data:/workspace/data \
  -v ./output:/workspace/output \
  speech-dataset-creator \
  python run.py /workspace/data/audio.mp3
```

### GPU Support

For GPU acceleration, use the nvidia runtime:
```bash
docker run --gpus all -p 5000:5000 \
  -v ./projects:/workspace/projects \
  -v ./output:/workspace/output \
  speech-dataset-creator
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Hugging Face token for model downloads
HF_TOKEN=your_huggingface_token

# CUDA settings
CUDA_VISIBLE_DEVICES=0

# Model cache directories
TORCH_HOME=./torch_cache
HF_HOME=./hf_cache
TRANSFORMERS_CACHE=./transformers_cache
```

### Model Checkpoints

Place pre-trained model checkpoints in the `checkpoints/` directory:
- `checkpoints/MossFormer2_SE_48K/` - Audio enhancement model

## Output Structure

After processing, your output directory will contain:

```
output/
├── <filename>_cleaned_audio.wav      # Enhanced audio
└── <filename>/                       # Processing artifacts
    ├── <filename>_01.wav             # Split audio segments
    ├── <filename>_01.wav_silences.json
    ├── <filename>_01.wav_transcription.json
    ├── <filename>_01.wav_pyannote.csv
    ├── <filename>_01.wav_segments.json
    └── <filename>_01.wav_segments/    # Individual segments
        └── speakers/                  # Speaker-separated audio
```

## API Endpoints

When running the web server, the following API endpoints are available:

- `GET /` - Web interface
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `GET /api/files/<project>` - List project files
- `POST /api/upload/<project>` - Upload files to project
- `GET /api/status/<project>` - Get processing status

## Performance Tips

1. **GPU Acceleration**: Use CUDA-compatible GPU for faster processing
2. **Batch Processing**: Process multiple files simultaneously when possible
3. **Storage**: Use SSD storage for better I/O performance
4. **Memory**: Ensure adequate RAM (8GB+ recommended)

## Troubleshooting

### Common Issues

1. **CUDA out of memory**: Reduce batch size or use CPU processing
2. **Model download failures**: Check internet connection and HF_TOKEN
3. **Audio format errors**: Ensure FFmpeg is properly installed
4. **Permission errors**: Check file permissions and Docker volume mounts

### Logging

Enable verbose logging by setting:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
export CUDA_LAUNCH_BLOCKING=1  # For CUDA debugging
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Acknowledgments

- [ClearVoice](https://github.com/modelscope/ClearerVoice-Studio) for audio enhancement
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) for speaker diarization
- [OpenAI Whisper](https://github.com/openai/whisper) for speech recognition (if used)

## Support

For issues and questions:
1. Check the troubleshooting section
2. Search existing issues
3. Create a new issue with detailed information
