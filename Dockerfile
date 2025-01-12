FROM python:3.13-slim-bullseye AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Create app directory
WORKDIR /app

# Copy only the files needed for installation first
COPY pyproject.toml README.md ./

# Copy the package source
COPY movie_merge ./movie_merge

# Install the package
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -e .

# Runtime stage with minimal dependencies
FROM nvidia/cuda:12.3.1-runtime-ubuntu22.04

# Install Python and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3-pip \
    python3-venv \
    ffmpeg \
    imagemagick \
    python3-av \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

RUN ffmpeg -version

# Configure ImageMagick policy to allow operations
RUN sed -i 's/<policy domain="path" rights="none" pattern="@\*"\/>/<!-- <policy domain="path" rights="none" pattern="@\*"\/> -->/' /etc/ImageMagick-6/policy.xml

# Set timezone
ENV TZ=Europe/Stockholm
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy virtual environment from builder
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

# Create app directory and user
RUN useradd -m -u 1000 movie_merge && \
    mkdir -p /app && \
    chown -R movie_merge:movie_merge /app

# Set working directory
WORKDIR /app

# Copy the installed package from builder
COPY --from=builder /app /app
RUN chown -R movie_merge:movie_merge /app

# Create and set permissions for input/output/temp directories
RUN mkdir -p /input /output /temp && \
    chown -R movie_merge:movie_merge /input /output /temp

# Add NVIDIA runtime support
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,video,utility

# Switch to non-root user
USER movie_merge

# Set entrypoint to use the installed package
ENTRYPOINT ["movie-merge"]
