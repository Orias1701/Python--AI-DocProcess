# ---- Base image (CUDA-enabled; works on GPU runners). For CPU, Hugging Face will still run it. ----
FROM pytorch/pytorch:2.3.1-cuda11.8-cudnn8-runtime

# Avoid interactive tzdata prompts
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps (faiss-cpu works; for faiss-gpu you may switch below)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git git-lfs build-essential poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Enable Git LFS (Spaces uses it automatically, but good to ensure)
RUN git lfs install

# Workdir
WORKDIR /app

# Copy only requirement files first to leverage Docker layer caching
COPY requirements.txt ./

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest
COPY . .

# Expose the port set by Spaces via $PORT
ENV HOST=0.0.0.0
ENV PORT=7860

# Optional envs (override in Space Secrets)
ENV HF_TOKEN=""
ENV API_SECRET=""

# Start the server
CMD ["/bin/bash", "start.sh"]
