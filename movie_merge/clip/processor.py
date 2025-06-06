"""Handles operations on individual video files."""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from movie_merge.constants import UNSUPPORTED_VIDEO_EXTENSIONS

from ..config.directory import DirectoryConfig
from ..config.processing import ProcessingConfig
from ..ffmepg.wrapper import FFmpegWrapper
from .title import TitleCardConfig, TitleCardGenerator

logger = logging.getLogger(__name__)


@dataclass
class ClipMetadata:
    """Container for clip metadata."""

    # Required fields (no defaults) first
    creation_date: datetime
    duration: float
    frame_rate: float
    video_codec: str
    width: int
    height: int
    video_bitrate: int
    audio_codec: str
    audio_channels: int
    audio_bitrate: int
    audio_sample_rate: int
    file_size: int
    format: str

    # Optional fields (with defaults) last
    name: Optional[str] = None
    extension: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert metadata to dictionary."""
        return {
            "creation_date": self.creation_date.isoformat(),
            "name": self.name,
            "extension": self.extension,
            "duration": self.duration,
            "frame_rate": self.frame_rate,
            "video_codec": self.video_codec,
            "width": self.width,
            "height": self.height,
            "video_bitrate": self.video_bitrate,
            "audio_codec": self.audio_codec,
            "audio_channels": self.audio_channels,
            "audio_bitrate": self.audio_bitrate,
            "audio_sample_rate": self.audio_sample_rate,
            "file_size": self.file_size,
            "format": self.format,
        }


class Clip:
    """Handles operations on individual video files."""

    def __init__(
        self,
        input_file: Path,
        proc_config: ProcessingConfig,
        dir_config: DirectoryConfig,
        is_title: bool = False,
    ):
        """Initialize clip processor.

        Args:
            input_file: Path to video file
            config: Processing configuration
        """
        self._ffmpeg: FFmpegWrapper = FFmpegWrapper()
        self.path: Path = input_file
        self.is_title: bool = is_title
        self.proc_config: ProcessingConfig = proc_config
        self.dir_config: DirectoryConfig = dir_config
        self.metadata: ClipMetadata = self._extract_metadata()

        if not self.path.exists():
            raise FileNotFoundError(f"Video file not found: {self.path}")

    def to_dict(self) -> dict:
        """Convert clip to dictionary."""
        return {
            "path": str(self.path),
            "is_title": self.is_title,
            "processing_config": self.proc_config.to_dict(),
            "metadata": self.metadata.to_dict(),
        }

    def _extract_datetime_from_exiftool(self, path: Optional[Path] = None) -> Optional[datetime]:
        file_path = path or self.path
        logger.debug(f"Extracting datetime from exiftool: {file_path}")
        try:
            result = subprocess.run(
                ["exiftool", "-DateTimeOriginal", "-d", "%Y-%m-%d %H:%M:%S%z", str(file_path)],
                capture_output=True,
                text=True,
                check=True,
            )

            if "Date/Time Original" in result.stdout:
                # Expected format: "Date/Time Original: 2017:08:17 20:55:57-1000"
                dt_str = result.stdout.split(": ")[1].strip()
                logger.debug(f"Extracted datetime: {dt_str}")
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S%z")

        except Exception as e:
            logger.debug(f"Failed to extract exiftool datetime: {e}")
        return None

    def _extract_metadata(self, path: Optional[Path] = None) -> ClipMetadata:
        """Extract metadata from video file.

        Args:
            path: Path to video file (defaults to self.path if None)

        Returns:
            ClipMetadata: Extracted metadata

        Raises:
            RuntimeError: If metadata extraction fails
        """
        file_path = path or self.path

        try:
            # Check if file exists and has non-zero size
            if not file_path.exists():
                raise RuntimeError(f"File does not exist: {file_path}")

            if file_path.stat().st_size == 0:
                raise RuntimeError(f"File is empty: {file_path}")

            # Add a small delay to ensure file is fully written/closed
            import time
            time.sleep(1)

            # Try to probe the file
            try:
                probe_data = self._ffmpeg.probe(input_file=file_path)
            except Exception as e:
                logger.warning(f"Failed to probe file with ffprobe: {e}")
                # Fall back to basic metadata
                stats = file_path.stat()
                return ClipMetadata(
                    creation_date=datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
                    name=file_path.stem,
                    extension=str(file_path.suffix).lower(),
                    duration=0.0,
                    frame_rate=25.0,  # Assume standard rate
                    video_codec="unknown",
                    width=1920,  # Assume HD
                    height=1080,
                    video_bitrate=0,
                    audio_codec="unknown",
                    audio_channels=2,
                    audio_bitrate=0,
                    audio_sample_rate=44100,
                    file_size=stats.st_size,
                    format="unknown"
                )

            video_stream = next(
                (s for s in probe_data["streams"] if s["codec_type"] == "video"), None
            )
            audio_stream = next(
                (s for s in probe_data["streams"] if s["codec_type"] == "audio"), None
            )

            if not video_stream:
                raise RuntimeError("No video stream found")

            # Calculate frame rate
            fps = 0
            # Try average frame rate first as it's typically more accurate
            if "avg_frame_rate" in video_stream:
                try:
                    num, den = map(int, video_stream["avg_frame_rate"].split("/"))
                    fps = num / den if den != 0 else 0
                except (ValueError, ZeroDivisionError):
                    pass

            # Fall back to real base frame rate if average is not available or invalid
            if fps == 0 and "r_frame_rate" in video_stream:
                try:
                    num, den = map(int, video_stream["r_frame_rate"].split("/"))
                    fps = num / den if den != 0 else 0
                except (ValueError, ZeroDivisionError):
                    pass

            # Extract creation time
            creation_date = self._extract_datetime_from_exiftool(
                file_path
            ) or datetime.fromtimestamp(file_path.stat().st_mtime)

            return ClipMetadata(
                creation_date=creation_date,
                name=file_path.stem,
                extension=str(file_path.suffix).lower(),
                duration=float(probe_data["format"].get("duration", 0)),
                frame_rate=fps,
                video_codec=video_stream.get("codec_name", "unknown"),
                width=int(video_stream.get("width", 0)),
                height=int(video_stream.get("height", 0)),
                video_bitrate=int(video_stream.get("bit_rate", 0)),
                audio_codec=audio_stream.get("codec_name", "none") if audio_stream else "none",
                audio_channels=int(audio_stream.get("channels", 0)) if audio_stream else 0,
                audio_bitrate=int(audio_stream.get("bit_rate", 0)) if audio_stream else 0,
                audio_sample_rate=int(audio_stream.get("sample_rate", 0)) if audio_stream else 0,
                file_size=int(probe_data["format"].get("size", 0)),
                format=probe_data["format"].get("format_name", "unknown"),
            )

        except Exception as e:
            logger.error(f"Failed to extract metadata from {file_path}: {e}")
            raise RuntimeError(f"Failed to extract metadata: {e}")

    @property
    def needs_processing(self) -> bool:
        """Check if clip needs processing."""
        return self.path.suffix.lower() in UNSUPPORTED_VIDEO_EXTENSIONS

    def convert_to_mp4(self, target_fps: Optional[float] = None) -> "Clip":
        """Convert video file to MP4 format with optional framerate adjustment."""
        # Skip if no processing needed and no framerate change
        if not self.needs_processing and not target_fps:
            logger.debug(f"Clip {self.path} does not need conversion")
            return self

        # Skip if already MP4 with correct framerate
        needs_framerate_adjustment = (
            target_fps and abs(self.metadata.frame_rate - target_fps) > 0.01
        )
        is_already_mp4 = self.path.suffix.lower() == ".mp4"

        if is_already_mp4 and not needs_framerate_adjustment:
            logger.debug(f"Clip {self.path} already in MP4 format with correct framerate")
            return self

        try:
            logger.debug(f"Converting {self.path} to MP4")
            # Create 'original' directory if needed
            original_dir = self.path.parent / "original"
            original_dir.mkdir(exist_ok=True)

            # Setup output path with .mp4 extension
            output_file = self.path.with_suffix(".mp4")
            original_file = original_dir / self.path.name

            # Create a temporary output file with different name to avoid in-place editing
            temp_output = self.proc_config.options.temp_dir / f"temp_{self.path.name}.mp4"

            if not self.proc_config.options.dry_run:
                # Build conversion command
                cmd = [self._ffmpeg.ffmpeg_path, "-y", "-i", str(self.path)]

                # Add framerate adjustment if needed
                if target_fps and abs(self.metadata.frame_rate - target_fps) > 0.01:
                    logger.info(
                        f"Adjusting framerate from {self.metadata.frame_rate} to {target_fps}"
                    )
                    cmd.extend(["-r", str(target_fps)])

                # Add encoding options
                video_options = self.proc_config.encoding.video_codec.get_encoding_options(
                    quality=self.proc_config.encoding.crf, preset=self.proc_config.encoding.preset
                )

                cmd.extend(["-c:v", self.proc_config.encoding.video_codec.value])
                for key, value in video_options.items():
                    if value is not None:
                        cmd.extend([f"-{key}", str(value)])

                # Add output file (temporary)
                cmd.append(str(temp_output))

                # Run conversion
                self._ffmpeg._run_command(cmd)

                # Move original file to original directory
                self.path.rename(original_file)

                # Move temp file to final destination
                import shutil

                shutil.move(str(temp_output), str(output_file))

                # Update clip path and metadata
                self.path = output_file
                self.metadata = self._extract_metadata()

                logger.info(f"Converted {original_file.name} -> {output_file.name}")
            else:
                logger.info(f"Would convert {self.path} -> {output_file}")

            return self

        except Exception as e:
            logger.error(f"Failed to convert {self.path}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            raise RuntimeError(f"Failed to convert video: {e}")

    def create_title(
        self,
        title: str,
        description: Optional[str] = None,
        title_config: Optional[TitleCardConfig] = None,
        use_segment: bool = True,
    ) -> "Clip":
        """Create title overlay for clip."""
        try:
            logger.info(f"Creating title sequence for clip: {self.path.name}")

            # Store original path for later use
            self.original_path = self.path
            self.is_title_clip = True

            # Use provided title config or default from directory config
            if title_config is None:
                title_config = self.dir_config.title_config

            generator = TitleCardGenerator()
            output_file = (
                self.proc_config.options.temp_dir
                / f"{self.metadata.name}_with_title{self.path.suffix}"
            )

            # Generate the title sequence using the specified framerate
            generator.generate_title_sequence(
                input_file=self.path,
                output_file=output_file,
                title=title,
                description=description,
                config=title_config,
                threads=self.proc_config.options.threads,
                fps=self.metadata.frame_rate,
                use_segment=use_segment,
                encoding_preset=self.proc_config.encoding.preset,
            )

            # Update clip path to point to new video with title
            self.path = output_file
            # Update metadata for the new clip
            self.metadata = self._extract_metadata()

            # Save title duration for later use
            self.title_duration = title_config.duration + 2 * title_config.fade_duration

            logger.info(f"Successfully created title sequence: {output_file}")
            return self

        except Exception as e:
            logger.error(f"Failed to create title for clip {self.path}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            raise RuntimeError(f"Failed to create title: {e}")
