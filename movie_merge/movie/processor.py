"""Movie compilation and management."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from movie_merge.constants import VIDEO_EXTENSIONS

from ..clip.processor import Clip
from ..config.directory import DirectoryConfig
from ..config.processing import ProcessingConfig
from ..config.sort import SortMethod
from ..ffmepg.wrapper import FFmpegWrapper

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """Represents a chapter with metadata and video files."""

    title: str
    description: Optional[str] = None
    directory: Path = None
    is_default: bool = False
    clips: List[Clip] = field(default_factory=list)

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "directory": str(self.directory) if self.directory else None,
            "is_default": self.is_default,
            "clips": [clip.to_dict() for clip in self.clips],
        }


class Movie:
    """Handles movie processing and compilation."""

    def __init__(self, directory: Path, proc_config: ProcessingConfig, dir_config: DirectoryConfig):
        """Initialize movie processor.

        Args:
            directory: Movie directory path
            proc_config: Processing configuration
            dir_config: Directory configuration
        """
        self._ffmpeg: FFmpegWrapper = FFmpegWrapper()
        self.proc_config = proc_config
        self.dir_config = dir_config
        self.chapters: List[Chapter] = []
        self.clips: List[Clip] = []

        self.title: str = dir_config.title
        self.description: Optional[str] = dir_config.description
        self.directory = directory
        self.metadata = self.dir_config.metadata
        self.sort_config = dir_config.sort_config

    def to_dict(self) -> dict:
        """Convert movie to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "directory": str(self.directory),
            "metadata": self.metadata.to_dict(),
            "target_resolution": self.proc_config.options.target_resolution,
            "sort_config": self.sort_config.to_dict(),
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }

    def _sort_clips(self, clips: List[Clip]) -> List[Clip]:
        """Sort clips according to directory configuration."""
        if self.sort_config.method == SortMethod.DATETIME:
            return sorted(
                clips, key=lambda x: x.metadata.creation_date, reverse=self.sort_config.reverse
            )
        elif self.sort_config.method == SortMethod.FILENAME:
            return sorted(clips, key=lambda x: x.path.name, reverse=self.sort_config.reverse)
        elif self.sort_config.method == SortMethod.CUSTOM and self.sort_config.custom_order:
            return sorted(
                clips,
                key=lambda x: self.sort_config.custom_order.get(x.path.name, float("inf")),
                reverse=self.sort_config.reverse,
            )
        else:
            return sorted(
                clips, key=lambda x: x.metadata.creation_date, reverse=self.sort_config.reverse
            )

    def _process_clips_in_directory(self, directory: Path) -> List[Clip]:
        """Process all video files in a directory."""
        clips = []
        for ext in VIDEO_EXTENSIONS:
            pattern = f"*{ext}"
            for video_file in directory.glob(pattern, case_sensitive=False):
                if video_file.parent.name != "original":
                    video_file_path = Path(video_file)
                    logger.debug(f"Processing clip: {video_file.name}")
                    try:
                        clip = Clip(video_file_path, self.proc_config, self.dir_config)
                        logger.debug(
                            f"Clip metadata: {json.dumps(clip.to_dict(), indent=2, ensure_ascii=False)}"
                        )

                        # Add clip to list
                        clips.append(clip)
                        logger.debug(f"Successfully processed clip: {video_file}")
                    except Exception as e:
                        logger.error(f"Failed to process clip {video_file}: {e}")
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.exception("Detailed error:")
                        continue

        # Sort clips based on configuration
        sorted_clips = self._sort_clips(clips) if clips else []

        # Make first clip the title clip
        if sorted_clips:
            sorted_clips[0].is_title = True

        return sorted_clips

    def scan_directory(self) -> None:
        """Scan directory for video files and organize them into chapters."""
        logger.debug(f"Scanning directory: {self.directory}")

        # First, process root directory clips into default chapter
        root_clips = self._process_clips_in_directory(self.directory)
        if root_clips:
            # Create default chapter
            default_chapter = Chapter(
                title=self.title,
                description=self.description,
                directory=self.directory,
                clips=root_clips,
                is_default=True,
            )
            # Sort clips based on configuration
            default_chapter.clips = (
                self._sort_clips(default_chapter.clips) if default_chapter.clips else []
            )

            # Add default chapter to chapters list
            self.chapters.append(default_chapter)
            logger.info(f"Added default chapter with {len(root_clips)} clips")

        # Then process subdirectories as additional chapters
        for chapter_dir in self.directory.iterdir():
            if chapter_dir.is_dir() and chapter_dir.name != "original":
                logger.debug(f"Processing chapter directory: {chapter_dir}")
                try:
                    chapter_clips = self._process_clips_in_directory(chapter_dir)
                    chapter = Chapter(
                        title=chapter_dir.name,
                        description=None,
                        directory=chapter_dir,
                        clips=chapter_clips,
                        is_default=False,
                    )
                    # Sort clips based on configuration
                    chapter.clips = self._sort_clips(chapter.clips) if chapter.clips else []

                    # Add chapter to list
                    self.chapters.append(chapter)
                    logger.info(f"Added chapter: {chapter.title} with {len(chapter_clips)} clips")
                except Exception as e:
                    logger.error(f"Failed to process chapter {chapter_dir}: {e}")
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.exception("Detailed error:")
                    continue

        if not self.chapters:
            logger.warning("No chapters or clips found in directory")
            return

        logger.info(f"Found {len(self.chapters)} chapters in total")
        logger.debug("Chapters: " + ", ".join(chapter.title for chapter in self.chapters))

    def process(self):
        """Process movie clips and chapters."""

        # Scan directory for clips and organize into chapters
        self.scan_directory()

        # Process each chapter
        logger.info("Processing chapters.")
        for chapter in self.chapters:
            for clip in chapter.clips:
                # Convert video to MP4 format
                clip.convert_to_mp4()

                # Create title card for the first clip in each chapter
                if clip.is_title:
                    # replace the first clip with a title clip
                    title_clip = clip.create_title(chapter.title, chapter.description)
                    chapter.clips[0] = title_clip

        # Flatten all clips into single list
        for chapter in self.chapters:
            self.clips.extend(chapter.clips)

        logger.info(f"Processed {len(self.clips)} clips in total")
        logger.debug(f"Movie title: {self.title}")
        logger.debug(f"Movie description: {self.description}")
        # minimal_movie_configuration = {
        #         "title": self.title,
        #         "description": self.description,
        #         "directory": str(self.directory),
        #         "metadata": self.metadata.to_dict(),
        #         "target_resolution": self.proc_config.options.target_resolution,
        #         "sort_config": self.sort_config.to_dict(),
        #         "chapters": [{
        #             "title": chapter.title,
        #             "description": chapter.description,
        #             "directory": str(chapter.directory),
        #             "is_default": chapter.is_default,
        #             "clips": [{
        #                 "path": str(clip.path),
        #                 "is_title": clip.is_title,
        #         } for clip in chapter.clips]
        #         } for chapter in self.chapters],
        #         "all_clips": [{
        #             "path": str(clip.path),
        #             "is_title": clip.is_title,
        #         } for clip in self.clips]
        # }
        # logger.debug(f"Movie configuration: {json.dumps(minimal_movie_configuration, indent=2, ensure_ascii=False)}")

    def make(self, output_file: Path):
        """Compile movie clips into a single video file.

        Args:
            output_file: Path to output video file
        """
        if not self.clips:
            logger.warning("No clips to process")
            return

        logger.info(f"Compiling {len(self.clips)} clips into movie: {output_file}")

        # Create intermediate file list
        concat_file = self.proc_config.options.temp_dir / "concat_list.txt"
        with open(concat_file, "w", encoding="utf-8") as f:
            for clip in self.clips:
                f.write(f"file '{clip.path.absolute()}'\n")

        try:
            # Build ffmpeg command for concatenation
            cmd = [
                self._ffmpeg.ffmpeg_path,
                "-y",  # Overwrite output file
                "-f",
                "concat",  # Use concat demuxer
                "-safe",
                "0",  # Don't restrict paths
                "-i",
                str(concat_file),  # Input file list
                "-c",
                "copy",  # Copy streams without re-encoding
            ]

            # Add video encoding options if needed
            if any(clip.needs_processing for clip in self.clips):
                # Get encoding options from config
                video_options = self.proc_config.encoding.video_codec.get_encoding_options(
                    quality=self.proc_config.encoding.crf, preset=self.proc_config.encoding.preset
                )

                # Add video codec
                cmd.extend(["-c:v", self.proc_config.encoding.video_codec.value])

                # Add encoding options
                for key, value in video_options.items():
                    if value is not None:
                        cmd.extend([f"-{key}", str(value)])

                # Add scaling if needed
                width, height = self.proc_config.options.target_resolution
                if width and height:
                    cmd.extend(
                        ["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease"]
                    )

            # Add output file
            cmd.append(str(output_file))

            # Create output directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if not self.proc_config.options.dry_run:
                logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
                self._ffmpeg._run_command(cmd)
                logger.info(f"Successfully created movie: {output_file}")
            else:
                logger.info(f"Would create movie: {output_file}")

        except Exception as e:
            logger.error(f"Failed to create movie: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            raise RuntimeError(f"Failed to create movie: {e}")
        finally:
            # Clean up concat file
            if concat_file.exists():
                concat_file.unlink()
