"""Main project processing functionality."""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from ..config.directory import DirectoryConfig, parse_directory_config
from ..config.exceptions import DirectoryParseError
from ..config.processing import ProcessingConfig
from ..movie.processor import Movie
from ..utils.file import should_ignore_directory, verify_writeable_directory
from .exceptions import ProcessingError

logger = logging.getLogger(__name__)


class Project:
    """Handles high-level project processing and directory scanning."""

    def __init__(self, config: ProcessingConfig):
        """Initialize project processor."""
        self.config = config

        if not self.config.input_path.exists():
            raise DirectoryParseError(f"Root directory does not exist: {self.config.input_path}")

        # Verify/create output directory
        verify_writeable_directory(config.output_path, create=True)

        # Verify/create temp directory
        if config.options.temp_dir:
            verify_writeable_directory(config.options.temp_dir, create=True)

    def scan_year(self, year: str) -> Generator[Tuple[Path, DirectoryConfig], None, None]:
        """Scan a specific year directory for event folders."""
        year_dir = self.config.input_path / year
        if not year_dir.exists():
            logger.warning(f"Year directory does not exist: {year_dir}")
            return

        for event_dir in sorted(year_dir.iterdir()):
            if not event_dir.is_dir() or should_ignore_directory(event_dir):
                continue

            try:
                config = parse_directory_config(event_dir)
                yield event_dir, config
            except DirectoryParseError as e:
                logger.error(f"Failed to parse directory {event_dir}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error processing directory {event_dir}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception("Traceback:")
                continue

    def process(self, year: str) -> None:
        """Process all events for a specific year sequentially."""
        logger.info(f"Processing year: {year}")

        # Create year output directory
        year_output = self.config.output_path / year
        year_output.mkdir(parents=True, exist_ok=True)

        # Process each directory in sequence
        for directory, dir_config in self.scan_year(year):
            try:
                self._process_directory(directory, dir_config)
            except Exception as e:
                logger.error(f"Failed to process directory {directory}: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception("Traceback:")

    def _process_directory(self, directory: Path, dir_config: DirectoryConfig) -> None:
        """Process a single event directory."""
        logger.info(f"Processing directory: {directory}")

        if self.config.options.dry_run:
            logger.info(f"Dry run - would process {directory}")
            return

        try:
            # Create movie processor
            movie = Movie(directory, self.config, dir_config)

            # Determine the output file path
            output_file = self.config.output_path / str(movie.metadata.year) / f"{movie.title}.mp4"

            # Check if the output file already exists
            if output_file.exists() and not self.config.options.overwrite:
                logger.info(f"Output file already exists and overwrite is disabled: {output_file}")
                logger.info(f"Skipping processing of {directory}")
                return

            # Create output directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if self.config.options.dry_run:
                logger.info(f"Dry run - would process {directory}")
                if output_file.exists():
                    logger.info(f"Would overwrite existing file: {output_file}")
                return

            # Scan for video files and process
            movie.process()

            if not movie.clips and not movie.chapters:
                logger.warning(f"No video files found in {directory}")
                return

            # Compile movie
            movie.make(output_file)

        except Exception as e:
            raise ProcessingError(f"Failed to process directory {directory}: {str(e)}") from e

    def cleanup(self) -> None:
        """Clean up temporary files."""
        if self.config.options.temp_dir and self.config.options.temp_dir.exists():
            try:
                shutil.rmtree(self.config.options.temp_dir)
                logger.debug(f"Cleaned up temporary directory: {self.config.options.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory: {e}")
