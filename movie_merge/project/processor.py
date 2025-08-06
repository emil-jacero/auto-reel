"""Main project processing functionality."""

import json
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple

from ..config.directory import DirectoryConfig, parse_directory_config
from ..config.exceptions import DirectoryParseError
from ..config.processing import ProcessingConfig
from ..movie.processor import Movie
from ..utils.file import should_ignore_directory, verify_writeable_directory
from ..utils.logging import LoggingContext, set_thread_context, clear_all_context
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
            if not event_dir.is_dir():
                continue

            if should_ignore_directory(event_dir):
                logger.info(f"Ignoring directory (found .reelignore): {event_dir}")
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
        """Process all events for a specific year."""
        logger.info(f"Processing year: {year}")

        # Create year output directory
        year_output = self.config.output_path / year
        year_output.mkdir(parents=True, exist_ok=True)

        # Collect all directories to process
        directories_to_process = list(self.scan_year(year))

        if not directories_to_process:
            logger.info(f"No directories found to process for year {year}")
            return

        # Determine processing mode
        max_concurrent = self.config.options.max_concurrent_movies

        if max_concurrent == 1:
            # Sequential processing (original behavior)
            logger.info(f"Processing {len(directories_to_process)} movies sequentially")
            for directory, dir_config in directories_to_process:
                try:
                    self._process_directory(directory, dir_config)
                except Exception as e:
                    logger.error(f"Failed to process directory {directory}: {e}")
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception("Traceback:")
        else:
            # Parallel processing
            self._process_directories_parallel(directories_to_process, max_concurrent)

    def _process_directories_parallel(
        self, directories: List[Tuple[Path, DirectoryConfig]], max_concurrent: int
    ) -> None:
        """Process directories in parallel."""
        logger.info(
            f"Processing {len(directories)} movies with up to {max_concurrent} concurrent workers"
        )

        successful_count = 0
        failed_count = 0

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            # Submit all directories for processing with unique thread identifiers
            future_to_dir = {}
            for i, (directory, dir_config) in enumerate(directories):
                thread_id = f"T{i+1:02d}"
                future = executor.submit(
                    self._process_directory_with_context, directory, dir_config, thread_id
                )
                future_to_dir[future] = (directory, dir_config, thread_id)

            # Collect results as they complete
            for future in as_completed(future_to_dir):
                directory, dir_config, thread_id = future_to_dir[future]
                try:
                    success = future.result()
                    if success:
                        successful_count += 1
                        logger.info(f"✓ Successfully processed: {directory.name}")
                    else:
                        failed_count += 1
                        logger.error(f"✗ Failed to process: {directory.name}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"✗ Unexpected error processing {directory}: {e}")
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception("Traceback:")

        logger.info(
            f"Parallel processing complete: {successful_count} successful, {failed_count} failed"
        )

    def _process_directory_with_context(
        self, directory: Path, dir_config: DirectoryConfig, thread_id: str
    ) -> bool:
        """Process a directory with logging context (for parallel execution)."""
        movie_name = directory.name
        with LoggingContext(movie=movie_name, thread=thread_id):
            try:
                logger.info(f"Starting processing")
                self._process_directory(directory, dir_config)
                logger.info(f"Completed processing successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to process: {e}")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.exception("Traceback:")
                return False

    def _process_directory_safe(self, directory: Path, dir_config: DirectoryConfig) -> bool:
        """Safely process a directory (for parallel execution)."""
        try:
            self._process_directory(directory, dir_config)
            return True
        except Exception as e:
            logger.error(f"Failed to process directory {directory}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            return False

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
            # Include location in filename if available
            if movie.metadata.location:
                filename = f"{movie.title} - {movie.metadata.location}.mp4"
            else:
                filename = f"{movie.title}.mp4"
            output_file = self.config.output_path / str(movie.metadata.year) / filename

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
