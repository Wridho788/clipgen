# Multi-stage build untuk minimize image size

# Stage 1: Build
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install system dependencies untuk build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libavcodec-dev \
    libavdevice-dev \
    libavfilter-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim-bookworm

WORKDIR /app

# Keep Deno at or above yt-dlp's documented minimum supported version.
ARG DENO_VERSION=2.3.0

# Install runtime dependencies (ffmpeg, ffprobe, Deno untuk challenge YouTube, dll)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ca-certificates \
    curl \
    unzip \
    && case "$(dpkg --print-architecture)" in \
        amd64) deno_arch="x86_64-unknown-linux-gnu" ;; \
        arm64) deno_arch="aarch64-unknown-linux-gnu" ;; \
        *) echo "Unsupported Deno architecture: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/denoland/deno/releases/download/v${DENO_VERSION}/deno-${deno_arch}.zip" -o /tmp/deno.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && deno --version \
    && rm -rf /tmp/deno.zip /var/lib/apt/lists/*

# Copy Python packages dari builder
COPY --from=builder /root/.local /root/.local

# Copy app code
COPY app ./app

# Create runtime directories
RUN mkdir -p storage/uploads storage/clips storage/temp logs

# Set PATH untuk user packages
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"

# Run server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
