""" Handles operations on individual video files. """

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
from .title import TitleCardGenerator

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

    def _extract_datetime_from_exiftool(self) -> Optional[datetime]:

        logger.debug(f"Extracting datetime from exiftool: {self.path}")
        try:
            result = subprocess.run(
                ["exiftool", "-DateTimeOriginal", "-d", "%Y-%m-%d %H:%M:%S%z", str(self.path)],
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

    def _extract_metadata(self) -> ClipMetadata:
        """Extract metadata from video file.

        Returns:
            ClipMetadata: Extracted metadata

        Raises:
            RuntimeError: If metadata extraction fails
        """
        try:
            probe_data = self._ffmpeg.probe(input_file=self.path)

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
            creation_date = self._extract_datetime_from_exiftool() or datetime.fromtimestamp(
                self.path.stat().st_mtime
            )

            return ClipMetadata(
                creation_date=creation_date,
                name=self.path.stem,
                extension=str(self.path.suffix).lower(),
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
            logger.error(f"Failed to extract metadata from {self.path}: {e}")
            raise RuntimeError(f"Failed to extract metadata: {e}")

    @property
    def needs_processing(self) -> bool:
        """Check if clip needs processing."""
        return self.path.suffix.lower() in UNSUPPORTED_VIDEO_EXTENSIONS

    def convert_to_mp4(self) -> "Clip":
        """Convert video file to MP4 format."""
        if not self.needs_processing:
            return self
        try:
            # Create 'original' directory if needed
            original_dir = self.path.parent / "original"
            original_dir.mkdir(exist_ok=True)

            # Setup output path with .mp4 extension
            output_file = self.path.with_suffix(".mp4")
            original_file = original_dir / self.path.name

            if not self.proc_config.options.dry_run:
                # Convert using FFmpeg wrapper
                self._ffmpeg.convert(
                    input_file=self.path,
                    output_file=output_file,
                    encoding_config=self.proc_config.encoding,
                    options=self.proc_config.options,
                    progress_callback=lambda p: logger.debug(f"Conversion progress: {p:.1f}%"),
                )

                # Move original file to original directory
                self.path.rename(original_file)

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

    def create_title(self, title: str, description: Optional[str] = None) -> "Clip":
        generator = TitleCardGenerator(Path("/path/to/fonts"))
        image = generator.generate(
            width=self.proc_config.options.target_resolution[0],
            height=self.proc_config.options.target_resolution[1],
            title=title,
            description=description,
            config=self.dir_config,
        )
        # Save to temp file and process with FFmpeg
        temp_path = self.proc_config.options.temp_dir / f"{self.metadata.name}_title.png"
        image.save(temp_path)
        return self
