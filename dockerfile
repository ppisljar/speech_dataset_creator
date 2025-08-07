# Use official PyTorch image with CUDA support for vast.ai compatibility
FROM pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime

# Set environment variables for vast.ai compatibility
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV TORCH_HOME=/workspace/torch_cache
ENV HF_HOME=/workspace/hf_cache
ENV TRANSFORMERS_CACHE=/workspace/transformers_cache

# Create workspace directory (vast.ai standard)
WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    wget \
    curl \
    build-essential \
    libsndfile1 \
    libsox-fmt-all \
    sox \
    portaudio19-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies that might be needed
RUN pip install --no-cache-dir \
    python-dotenv \
    torch \
    torchaudio \
    librosa \
    soundfile \
    scipy \
    numpy \
    pandas

# Copy the application code
COPY . .

# Create necessary directories
RUN mkdir -p /workspace/projects \
    && mkdir -p /workspace/output \
    && mkdir -p /workspace/raw \
    && mkdir -p /workspace/checkpoints \
    && mkdir -p /workspace/torch_cache \
    && mkdir -p /workspace/hf_cache \
    && mkdir -p /workspace/transformers_cache

# Create .env file template for vast.ai environment variable injection
RUN echo "# Environment variables for Speech Dataset Creator" > .env.template \
    && echo "# Copy this file to .env and set your values" >> .env.template \
    && echo "" >> .env.template \
    && echo "# Hugging Face Token for pyannote.audio models" >> .env.template \
    && echo "HF_TOKEN=" >> .env.template \
    && echo "" >> .env.template \
    && echo "# Flask Configuration" >> .env.template \
    && echo "FLASK_HOST=0.0.0.0" >> .env.template \
    && echo "FLASK_PORT=5000" >> .env.template \
    && echo "FLASK_DEBUG=False" >> .env.template \
    && echo "" >> .env.template \
    && echo "# Audio Processing Settings" >> .env.template \
    && echo "AUDIO_SAMPLE_RATE=16000" >> .env.template \
    && echo "SILENCE_THRESHOLD=-40" >> .env.template \
    && echo "MIN_SILENCE_DURATION=0.5" >> .env.template \
    && echo "" >> .env.template \
    && echo "# Processing Directories" >> .env.template \
    && echo "PROJECTS_DIR=/workspace/projects" >> .env.template \
    && echo "OUTPUT_DIR=/workspace/output" >> .env.template \
    && echo "RAW_DIR=/workspace/raw" >> .env.template \
    && echo "CHECKPOINTS_DIR=/workspace/checkpoints" >> .env.template \
    && echo "" >> .env.template \
    && echo "# Torch/CUDA Settings" >> .env.template \
    && echo "CUDA_VISIBLE_DEVICES=0" >> .env.template \
    && echo "TORCH_DEVICE=cuda" >> .env.template

# Create startup script for vast.ai
RUN echo '#!/bin/bash' > /workspace/start.sh \
    && echo '' >> /workspace/start.sh \
    && echo '# Load environment variables from .env file if it exists' >> /workspace/start.sh \
    && echo 'if [ -f /workspace/.env ]; then' >> /workspace/start.sh \
    && echo '    export $(cat /workspace/.env | grep -v "^#" | xargs)' >> /workspace/start.sh \
    && echo 'fi' >> /workspace/start.sh \
    && echo '' >> /workspace/start.sh \
    && echo '# Create .env from template if it does not exist' >> /workspace/start.sh \
    && echo 'if [ ! -f /workspace/.env ]; then' >> /workspace/start.sh \
    && echo '    cp /workspace/.env.template /workspace/.env' >> /workspace/start.sh \
    && echo '    echo "Created .env file from template. Please edit with your values."' >> /workspace/start.sh \
    && echo 'fi' >> /workspace/start.sh \
    && echo '' >> /workspace/start.sh \
    && echo '# Start the Flask server' >> /workspace/start.sh \
    && echo 'echo "Starting Speech Dataset Creator..."' >> /workspace/start.sh \
    && echo 'echo "Web interface will be available at http://localhost:${FLASK_PORT:-5000}"' >> /workspace/start.sh \
    && echo 'python _server.py' >> /workspace/start.sh \
    && chmod +x /workspace/start.sh

# Create a script for environment variable injection (vast.ai compatible)
RUN echo '#!/bin/bash' > /workspace/inject_env.sh \
    && echo '# Script to inject environment variables into .env file' >> /workspace/inject_env.sh \
    && echo '# Usage: ./inject_env.sh VAR_NAME VAR_VALUE' >> /workspace/inject_env.sh \
    && echo '' >> /workspace/inject_env.sh \
    && echo 'if [ $# -ne 2 ]; then' >> /workspace/inject_env.sh \
    && echo '    echo "Usage: $0 VARIABLE_NAME VARIABLE_VALUE"' >> /workspace/inject_env.sh \
    && echo '    exit 1' >> /workspace/inject_env.sh \
    && echo 'fi' >> /workspace/inject_env.sh \
    && echo '' >> /workspace/inject_env.sh \
    && echo 'VAR_NAME=$1' >> /workspace/inject_env.sh \
    && echo 'VAR_VALUE=$2' >> /workspace/inject_env.sh \
    && echo '' >> /workspace/inject_env.sh \
    && echo '# Create .env if it does not exist' >> /workspace/inject_env.sh \
    && echo 'if [ ! -f /workspace/.env ]; then' >> /workspace/inject_env.sh \
    && echo '    cp /workspace/.env.template /workspace/.env' >> /workspace/inject_env.sh \
    && echo 'fi' >> /workspace/inject_env.sh \
    && echo '' >> /workspace/inject_env.sh \
    && echo '# Update or add the variable' >> /workspace/inject_env.sh \
    && echo 'if grep -q "^${VAR_NAME}=" /workspace/.env; then' >> /workspace/inject_env.sh \
    && echo '    sed -i "s/^${VAR_NAME}=.*/${VAR_NAME}=${VAR_VALUE}/" /workspace/.env' >> /workspace/inject_env.sh \
    && echo 'else' >> /workspace/inject_env.sh \
    && echo '    echo "${VAR_NAME}=${VAR_VALUE}" >> /workspace/.env' >> /workspace/inject_env.sh \
    && echo 'fi' >> /workspace/inject_env.sh \
    && echo '' >> /workspace/inject_env.sh \
    && echo 'echo "Set ${VAR_NAME} in .env file"' >> /workspace/inject_env.sh \
    && chmod +x /workspace/inject_env.sh

# Set proper permissions
RUN chmod -R 755 /workspace

# Expose port for Flask server
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Default command - start the Flask server
CMD ["/workspace/start.sh"]

# Alternative commands for vast.ai users:
# To inject environment variables: docker run -it --rm speech-dataset-creator /workspace/inject_env.sh HF_TOKEN your_token_here
# To run processing pipeline: docker run -it --rm -v /path/to/data:/workspace/data speech-dataset-creator python run.py /workspace/data/audio.mp3
# To start with custom .env: docker run -it --rm -v /path/to/.env:/workspace/.env speech-dataset-creator