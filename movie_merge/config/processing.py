"""Configuration classes for video processing."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..enums import AudioCodec, VideoCodec, VideoTune


@dataclass
class EncodingConfig:
    """Configuration for video encoding."""

    video_codec: Union[str, VideoCodec] = VideoCodec.H264
    audio_codec: Union[str, AudioCodec] = AudioCodec.AAC
    use_gpu: bool = False
    crf: int = 20  # Constant Rate Factor
    preset: str = "medium"  # Encoding speed

    def __post_init__(self):
        """Convert string codecs to enum values if needed."""
        if isinstance(self.video_codec, str):
            try:
                self.video_codec = VideoCodec(self.video_codec)
            except ValueError:
                raise ValueError(f"Invalid video codec: {self.video_codec}")

        if isinstance(self.audio_codec, str):
            try:
                self.audio_codec = AudioCodec(self.audio_codec)
            except ValueError:
                raise ValueError(f"Invalid audio codec: {self.audio_codec}")

        # Validate GPU quality
        if self.use_gpu and not 0 <= self.crf <= 51:
            raise ValueError("GPU quality must be between 0 and 51")

        if self.use_gpu and self.video_codec not in VideoCodec.get_gpu_codecs():
            raise ValueError("Selected codec does not support GPU acceleration")

        if not self.use_gpu and self.video_codec in VideoCodec.get_gpu_codecs():
            raise ValueError(
                "GPU codec specified but use_gpu is False. Either enable GPU or use a CPU codec"
            )

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "video_codec": self.video_codec.value,
            "audio_codec": self.audio_codec.value,
            "use_gpu": self.use_gpu,
            "crf": self.crf,
            "preset": self.preset,
        }

    def get_encoding_options(self) -> Dict[str, str]:
        """Get encoding options for video and audio codecs."""
        video_options = self.video_codec.get_encoding_options(
            quality=self.crf,
            preset=self.preset,
            tune=VideoTune.FILM,
        )
        audio_options = self.audio_codec.get_encoding_options()
        return {**video_options, **audio_options}


@dataclass
class ProcessingOptions:
    """General processing options."""

    threads: int = 2
    max_concurrent_movies: int = 1  # Number of movies to process simultaneously
    target_resolution: Tuple[int, int] = (1920, 1080)
    temp_dir: Optional[Path] = None
    chunk_size: int = 1024 * 1024  # 1MB chunks for file operations
    dry_run: bool = False
    log_level: str = "DEBUG"
    overwrite: bool = False  # Whether to overwrite existing output files

    def __post_init__(self):
        """Validate processing options."""
        if self.threads < 1:
            raise ValueError("Thread count must be at least 1")

        if self.max_concurrent_movies < 1:
            raise ValueError("Max concurrent movies must be at least 1")

        if not all(x > 0 for x in self.target_resolution):
            raise ValueError("Resolution dimensions must be positive")

    def to_dict(self) -> dict:
        """Convert options to dictionary."""
        return {
            "threads": self.threads,
            "max_concurrent_movies": self.max_concurrent_movies,
            "target_resolution": self.target_resolution,
            "temp_dir": str(self.temp_dir) if self.temp_dir else None,
            "chunk_size": self.chunk_size,
            "dry_run": self.dry_run,
            "log_level": self.log_level,
            "overwrite": self.overwrite,
        }


@dataclass
class ProcessingConfig:
    """Main processing configuration."""

    input_path: Path
    output_path: Path
    years: List[str]
    encoding: EncodingConfig = None
    options: ProcessingOptions = None

    def __post_init__(self):
        """Initialize and validate configuration."""
        # Convert string paths to Path objects
        self.input_path = Path(self.input_path)
        self.output_path = Path(self.output_path)

        # Set default configurations if not provided
        if self.encoding is None:
            self.encoding = EncodingConfig()
        if self.options is None:
            self.options = ProcessingOptions()

        # Validate paths
        if not self.input_path.exists():
            raise ValueError(f"Input directory does not exist: {self.input_path}")

        # Create output directory if it doesn't exist
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Validate years
        if not self.years:
            raise ValueError("No years specified for processing")

        # Set up temp directory if not specified
        if self.options.temp_dir is None:
            self.options.temp_dir = self.output_path / "temp"

        # Create temp directory
        self.options.temp_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "input_dir": str(self.input_path),
            "output_dir": str(self.output_path),
            "years": self.years,
            "encoding": self.encoding.to_dict(),
            "options": self.options.to_dict(),
        }
