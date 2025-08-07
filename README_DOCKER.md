# Speech Dataset Creator - Docker Setup

This project includes Docker support for easy deployment, especially on vast.ai and other cloud GPU platforms.

## Quick Start

### 1. Environment Setup

Copy the environment template and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and set your Hugging Face token (required for pyannote.audio models):

```bash
HF_TOKEN=your_huggingface_token_here
```

### 2. Build and Run

#### Using Docker Compose (Recommended)

```bash
# Build and start the service
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

#### Using Docker directly

```bash
# Build the image
docker build -t speech-dataset-creator .

# Run the container
docker run -d \
  --name speech-dataset-creator \
  --gpus all \
  -p 5000:5000 \
  -v $(pwd)/projects:/workspace/projects \
  -v $(pwd)/output:/workspace/output \
  -v $(pwd)/raw:/workspace/raw \
  -v $(pwd)/.env:/workspace/.env \
  speech-dataset-creator
```

### 3. Access the Application

Open your browser to: http://localhost:5000

## Vast.ai Deployment

### Method 1: Using Docker Image

1. Build and push your image to Docker Hub:

```bash
docker build -t yourusername/speech-dataset-creator .
docker push yourusername/speech-dataset-creator
```

2. On vast.ai, use the image: `yourusername/speech-dataset-creator`

3. Set environment variables in vast.ai interface:
   - `HF_TOKEN`: Your Hugging Face token
   - `CUDA_VISIBLE_DEVICES`: 0
   - Any other variables from `.env.example`

### Method 2: Using Repository

1. On vast.ai, use base image: `pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime`

2. Add this to the startup script:

```bash
cd /workspace
git clone https://github.com/yourusername/speech_dataset_creator.git .
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values or use environment variable injection
./inject_env.sh HF_TOKEN your_token_here
./start.sh
```

## Environment Variable Injection

The Docker image includes a script for dynamic environment variable injection:

```bash
# Inject a single variable
docker exec speech-dataset-creator ./inject_env.sh HF_TOKEN your_token_here

# Inject multiple variables
docker exec speech-dataset-creator ./inject_env.sh FLASK_PORT 8080
docker exec speech-dataset-creator ./inject_env.sh CUDA_VISIBLE_DEVICES 0,1
```

## Processing Audio Files

### Using the Web Interface

1. Access http://localhost:5000
2. Upload audio files through the web interface
3. Monitor processing status

### Using Command Line

```bash
# Process a single file
docker exec speech-dataset-creator python run.py /workspace/data/audio.mp3

# Process with custom output directory
docker exec speech-dataset-creator python run.py /workspace/data/audio.mp3 /workspace/custom_output

# Process with options
docker exec speech-dataset-creator python run.py /workspace/data/audio.mp3 --override --segment
```

## Volume Mounts

The following directories are mounted as volumes:

- `./projects` → `/workspace/projects` - Project data
- `./output` → `/workspace/output` - Processing output
- `./raw` → `/workspace/raw` - Raw audio files
- `./checkpoints` → `/workspace/checkpoints` - Model checkpoints
- `./.env` → `/workspace/.env` - Environment configuration

## GPU Support

The Docker setup includes NVIDIA GPU support. Make sure you have:

1. NVIDIA Docker runtime installed
2. GPU drivers installed on the host
3. Use `--gpus all` flag or docker-compose with GPU configuration

## Troubleshooting

### Common Issues

1. **Permission Issues**: Make sure the mounted volumes have correct permissions
2. **GPU Not Available**: Check NVIDIA Docker setup and drivers
3. **Model Download Fails**: Verify HF_TOKEN is set correctly
4. **Port Already in Use**: Change FLASK_PORT in .env file

### Logs

```bash
# View container logs
docker logs speech-dataset-creator

# Follow logs in real-time
docker logs -f speech-dataset-creator

# Docker compose logs
docker-compose logs -f
```

### Debug Mode

Enable debug mode by setting in `.env`:

```
FLASK_DEBUG=true
```

## Production Deployment

For production deployment:

1. Set `FLASK_DEBUG=false` in `.env`
2. Use a reverse proxy (nginx) for SSL termination
3. Set up proper logging and monitoring
4. Consider using Docker Swarm or Kubernetes for scaling
