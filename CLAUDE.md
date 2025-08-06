# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Development Setup

```bash
task setup                    # Setup development environment (venv, deps, pre-commit)
task setup-nvidia            # Setup NVIDIA GPU development (if available)
```

### Building and Running

```bash
task run                     # Run movie-merge CLI with default settings
task run USE_GPU=true        # Run with GPU acceleration enabled
task run INPUT_DIR=./input OUTPUT_DIR=./output YEAR=2024  # Custom directories and year
```

### Testing and Quality

```bash
task test                    # Run tests with pytest
task test-cov               # Run tests with coverage report
task lint:format            # Format code with black and isort
task lint:check             # Check code with mypy, pylint, and black
task lint:fix               # Fix linting issues automatically
```

### Docker

```bash
task build:docker          # Build Docker image
task docker:run             # Run in container with NVIDIA GPU support
```

## Architecture Overview

This is a Python video processing tool that automatically merges video clips into complete movies with title cards and chapters.

### Core Components

- **`movie_merge/cli/main.py`** - Main CLI entry point with argument parsing and codec configuration
- **`movie_merge/project/processor.py`** - High-level project processing orchestration
- **`movie_merge/movie/processor.py`** - Individual movie processing logic
- **`movie_merge/clip/processor.py`** - Video clip processing and manipulation
- **`movie_merge/ffmepg/wrapper.py`** - FFmpeg command execution wrapper
- **`movie_merge/config/`** - Configuration handling for processing options, directories, and sorting

### Key Features

- GPU-accelerated video encoding (NVIDIA NVENC support)
- Multiple video/audio codec support (H.264, H.265, VP9, AV1, AAC, MP3, etc.)
- Automatic title card generation and insertion
- Chapter support for organized video navigation
- YAML-based per-movie configuration via `reel.yaml` files
- Dry-run capability for testing without actual processing

### Configuration

The tool uses **Task** (Taskfile.yaml) for build automation with modular task files in `.tasks/`:

- Python 3.13 virtual environment management
- Development dependencies managed via pyproject.toml with optional `[dev]` and `[docs]` groups
- Code quality tools: black, isort, mypy, pylint, pytest with coverage
- Pre-commit hooks for automated quality checks

### Input Structure

The tool expects input videos organized by year in directories like:

```shell
input/
├── 2018/
│   └── 2018-01-01 - Event Name - Location/
│       ├── 00400.mp4
│       ├── 00401.mp4
│       └── reel.yaml (optional config)
└── 2019/
    └── ...
```

### Processing Flow

1. Project processor scans input directories by year
2. Movie processor handles individual movie compilation
3. Clip processor manages video transcoding and title insertion
4. FFmpeg wrapper executes encoding with GPU acceleration when available
5. Output movies generated with chapters and consistent formatting
