# Single stage build with NVIDIA CUDA runtime
FROM nvidia/cuda:12.9.0-runtime-ubuntu24.04

# Set timezone (can be overridden with build arg)
ARG TZ=Europe/Stockholm
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Python 3.13 and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    software-properties-common \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
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
    libimage-exiftool-perl \
    fonts-ubuntu \
    && rm -rf /var/lib/apt/lists/*

# Download and install Python 3.13
RUN cd /tmp && \
    wget https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz && \
    tar -xf Python-3.13.0.tgz && \
    cd Python-3.13.0 && \
    ./configure --enable-optimizations && \
    make -j$(nproc) && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.13.0 Python-3.13.0.tgz && \
    ln -sf /usr/local/bin/python3.13 /usr/local/bin/python3 && \
    ln -sf /usr/local/bin/pip3.13 /usr/local/bin/pip3

# Verify ffmpeg installation
RUN ffmpeg -version

# Configure ImageMagick policy to allow operations
# Note: Path may be different in Ubuntu 24.04 if ImageMagick was updated
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
    sed -i 's/<policy domain="path" rights="none" pattern="@\*"\/>/<!-- <policy domain="path" rights="none" pattern="@\*"\/> -->/' /etc/ImageMagick-6/policy.xml; \
    elif [ -f /etc/ImageMagick/policy.xml ]; then \
    sed -i 's/<policy domain="path" rights="none" pattern="@\*"\/>/<!-- <policy domain="path" rights="none" pattern="@\*"\/> -->/' /etc/ImageMagick/policy.xml; \
    fi

# Copy source files and install package
WORKDIR /app
COPY pyproject.toml README.md ./
COPY movie_merge ./movie_merge

# Install the package directly
RUN pip3.13 install --upgrade pip && \
    pip3.13 install --no-cache-dir .

# Use existing user with UID 1000 and set permissions
RUN chown -R 1000:1000 /app

# Create and set permissions for input/output/temp directories
RUN mkdir -p /input /output /temp && \
    chown -R 1000:1000 /input /output /temp

# Add NVIDIA runtime support
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,video,utility

# Create a custom font directory in user's home
RUN mkdir -p /home/ubuntu/.fonts && \
    cp /usr/share/fonts/truetype/ubuntu/Ubuntu-M.ttf /home/ubuntu/.fonts/ && \
    chown -R 1000:1000 /home/ubuntu/.fonts

# Set font configuration
ENV FONTCONFIG_PATH=/etc/fonts
RUN fc-cache -fv

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ffmpeg -version && exiftool -ver && python3.13 -V || exit 1

# Switch to non-root user
USER 1000:1000

# Set entrypoint to use the installed package
ENTRYPOINT ["python3.13", "-m", "movie_merge.cli.main"]

# Default command if no args provided
CMD ["--help"]
