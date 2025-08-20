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
    nano \
    build-essential \
    libsndfile1 \
    libsox-fmt-all \
    sox libsox-dev \
    portaudio19-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
RUN git clone https://github.com/ppisljar/speech_dataset_creator.git /workspace/sdc

# Create startup script for vast.ai
RUN echo '#!/bin/bash' > /workspace/start.sh \
    && echo '' >> /workspace/start.sh \
    && echo '# Pull fresh code from GitHub' >> /workspace/start.sh \
    && echo 'echo "Pulling fresh code from GitHub..."' >> /workspace/start.sh \
    && echo 'cd /workspace/sdc' >> /workspace/start.sh \
    && echo 'git fetch origin' >> /workspace/start.sh \
    && echo 'git reset --hard origin/main' >> /workspace/start.sh \
    && echo 'git clean -fd' >> /workspace/start.sh \
    && echo '' >> /workspace/start.sh \
    && echo '# Check and install any missing/updated Python dependencies' >> /workspace/start.sh \
    && echo 'echo "Checking for updated dependencies..."' >> /workspace/start.sh \
    && echo 'pip install --no-cache-dir -r requirements.txt --upgrade' >> /workspace/start.sh \
    && echo '' >> /workspace/start.sh \
    && echo '# Start the Flask server' >> /workspace/start.sh \
    && echo 'echo "Starting Speech Dataset Creator..."' >> /workspace/start.sh \
    && echo 'echo "Web interface will be available at http://localhost:${FLASK_PORT:-5000}"' >> /workspace/start.sh \
    && echo 'python _server.py' >> /workspace/start.sh \
    && chmod +x /workspace/start.sh

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