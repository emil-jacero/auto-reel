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
        self.target_fps: Optional[float] = None  # Store target FPS from first clip

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

    def _get_target_fps(self, clips: List[Clip]) -> float:
        """Get target FPS from first clip."""
        if not clips:
            return 30.0  # Default fallback

        first_clip = clips[0]
        fps = first_clip.metadata.frame_rate

        if fps <= 0 or fps > 120:  # Sanity check
            logger.warning(f"Invalid FPS detected in first clip: {fps}, using 30 FPS")
            return 30.0

        return fps

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
        """Process movie clips and create title cards."""
        # Scan directory for clips and organize into chapters
        self.scan_directory()

        # Get target FPS from first clip in first chapter
        for chapter in self.chapters:
            if chapter.clips:
                self.target_fps = self._get_target_fps(chapter.clips)
                break

        if not self.target_fps:
            self.target_fps = 30.0  # Fallback if no clips found

        logger.info(f"Using target framerate: {self.target_fps} FPS")

        # Process each chapter
        logger.info("Processing chapters.")
        for chapter in self.chapters:
            for clip in chapter.clips:
                # Convert video to MP4 format
                clip.convert_to_mp4(target_fps=self.target_fps)

                # Create title card for the first clip in each chapter
                if clip.is_title:
                    # Update title card config with target FPS
                    chapter_title_config = self.dir_config.title_config
                    chapter_title_config.fps = self.target_fps

                    # Create title with matching FPS, using short segment
                    title_clip = clip.create_title(
                        chapter.title,
                        chapter.description,
                        title_config=chapter_title_config,
                        use_segment=True,
                    )
                    chapter.clips[0] = title_clip
                    # Mark the clip as a title clip
                    chapter.clips[0].is_title_clip = True

        # Flatten all clips into single list
        for chapter in self.chapters:
            self.clips.extend(chapter.clips)

        logger.info(f"Processed {len(self.clips)} clips in total using {self.target_fps} FPS")

    def make(self, output_file: Path):
        """Compile movie clips into a single video file."""
        if not self.clips:
            logger.warning("No clips to process")
            return

        logger.info(f"Compiling {len(self.clips)} clips into movie: {output_file}")
        logger.info(f"Using target framerate: {self.target_fps} FPS")

        try:
            # Prepare clips for merging
            final_clips = []
            temp_files = []

            for clip in self.clips:
                # For title clips, we need to handle them differently
                if (
                    hasattr(clip, "is_title_clip")
                    and clip.is_title_clip
                    and hasattr(clip, "original_path")
                ):
                    # Add the title segment
                    final_clips.append(clip.path)
                    temp_files.append(clip.path)

                    original_clip = clip.original_path
                    original_metadata = clip._extract_metadata(original_clip)

                    # Get the actual duration used in the title sequence (which contains video content)
                    # We need to get this from the title segment itself, not from the configuration
                    used_duration = clip.metadata.duration

                    if original_metadata and original_metadata.duration > used_duration:
                        # Create temporary clip with the remainder, starting exactly where the title clip ends
                        temp_remainder = (
                            self.proc_config.options.temp_dir / f"remainder_{original_clip.name}"
                        )

                        cmd = [
                            self._ffmpeg.ffmpeg_path,
                            "-y",
                            "-ss",
                            str(used_duration),
                            "-i",
                            str(original_clip),
                            "-c:v",
                            self.proc_config.encoding.video_codec.value,
                            "-c:a",
                            self.proc_config.encoding.audio_codec.value,
                            str(temp_remainder),
                        ]

                        if not self.proc_config.options.dry_run:
                            self._ffmpeg._run_command(cmd)
                            final_clips.append(temp_remainder)
                            temp_files.append(temp_remainder)
                else:
                    # For regular clips, use them as is
                    final_clips.append(clip.path)

            # Build ffmpeg command with complex filter for concatenation
            cmd = [self._ffmpeg.ffmpeg_path, "-y"]

            # Add input files
            for path in final_clips:
                cmd.extend(["-i", str(path)])

            # Build filter complex string for proper concatenation
            filter_complex = []

            # Process each input stream
            for i in range(len(final_clips)):
                # Scale and set framerate for video
                width, height = self.proc_config.options.target_resolution
                filter_complex.append(
                    f"[{i}:v]fps={self.target_fps},"
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease[v{i}]"
                )
                # Format audio
                filter_complex.append(
                    f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a{i}]"
                )

            # Collect all normalized streams for concat
            video_streams = "".join(f"[v{i}]" for i in range(len(final_clips)))
            audio_streams = "".join(f"[a{i}]" for i in range(len(final_clips)))

            # Add concat filters
            filter_complex.append(f"{video_streams}concat=n={len(final_clips)}:v=1:a=0[vout]")
            filter_complex.append(f"{audio_streams}concat=n={len(final_clips)}:v=0:a=1[aout]")

            # Add the complete filter complex to the command
            cmd.extend(["-filter_complex", ";".join(filter_complex)])

            # Map output streams
            cmd.extend(["-map", "[vout]", "-map", "[aout]"])

            # Video codec settings
            if self.proc_config.encoding.video_codec.is_gpu_codec:
                # NVENC specific settings
                cmd.extend(
                    [
                        "-c:v",
                        self.proc_config.encoding.video_codec.value,
                        "-rc:v",
                        "vbr",  # Variable bitrate mode
                        "-cq:v",
                        str(self.proc_config.encoding.crf),
                        "-b:v",
                        "0",  # Let VBR mode handle bitrate
                        "-maxrate:v",
                        "100M",
                        "-profile:v",
                        "high",
                        "-tune",
                        "hq",  # High quality tuning
                        "-preset",
                        "p1",  # Adjust preset as needed
                    ]
                )
            else:
                # CPU encoding settings
                cmd.extend(
                    [
                        "-c:v",
                        self.proc_config.encoding.video_codec.value,
                        "-crf",
                        str(self.proc_config.encoding.crf),
                        "-preset",
                        self.proc_config.encoding.preset,
                    ]
                )

            # Audio codec settings
            cmd.extend(
                [
                    "-c:a",
                    self.proc_config.encoding.audio_codec.value,
                    "-b:a",
                    "192k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                ]
            )

            # Add output file
            cmd.append(str(output_file))

            # Create output directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if not self.proc_config.options.dry_run:
                logger.debug(f"Running ffmpeg command: {' '.join(cmd)}")
                self._ffmpeg._run_command(cmd)
                logger.info(f"Successfully created movie: {output_file}")

                # Clean up temporary files
                for temp_file in temp_files:
                    try:
                        Path(temp_file).unlink()
                        logger.debug(f"Removed temporary file: {temp_file}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {temp_file}: {e}")
            else:
                logger.info(f"Would create movie: {output_file}")

        except Exception as e:
            logger.error(f"Failed to create movie: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            raise RuntimeError(f"Failed to create movie: {e}")
