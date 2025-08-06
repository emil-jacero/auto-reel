import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from ..config.processing import EncodingConfig, ProcessingConfig, ProcessingOptions
from ..enums import AudioCodec, VideoCodec
from ..project.processor import Project
from ..utils.logging import configure_logging

# Setup module logger
logger = logging.getLogger(__name__)


def create_codec_help(codec_enum, descriptions):
    """Create formatted help text for codec choices."""
    help_lines = ["Available codecs:"]
    # Calculate the longest codec name for padding
    max_name_length = max(len(codec.name) for codec in codec_enum)

    for codec in codec_enum:
        desc = descriptions.get(codec.name, "No description available")
        # Format with consistent padding and indentation
        help_lines.append(f"  {codec.name:<{max_name_length}}  -  {desc}")

    return "\n".join(help_lines)


def _get_codec_descriptions():
    """Get descriptions for codec choices."""
    VIDEO_CODEC_DESCRIPTIONS = {
        "H264": "Standard H.264/AVC (libx264). Good compression, widely compatible",
        "H265": "High Efficiency HEVC (libx265). Better compression, newer devices",
        "VP9": "Google VP9. Free, good quality, slower encoding",
        "AV1": "AV1. Excellent compression, very slow encoding",
        "H264_NVENC": "NVIDIA GPU H.264. Fast, good quality",
        "H265_NVENC": "NVIDIA GPU H.265. Fast, better compression",
    }

    AUDIO_CODEC_DESCRIPTIONS = {
        "AAC": "Advanced Audio Coding. Standard high-quality audio",
        "MP3": "MP3 audio. Widely compatible, good compression",
        "OPUS": "Opus audio. Excellent quality, modern codec",
        "VORBIS": "Vorbis audio. Free format, good quality",
    }

    return VIDEO_CODEC_DESCRIPTIONS, AUDIO_CODEC_DESCRIPTIONS


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Merge and process video files with chapters and titles",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-i", "--input-dir", required=True, help="Input directory containing video files"
    )

    parser.add_argument(
        "-o", "--output-dir", required=True, help="Output directory for processed videos"
    )

    parser.add_argument(
        "-y", "--years", required=True, help="Comma separated list of years to process"
    )

    parser.add_argument(
        "-t", "--threads", type=int, default=1, help="Number of threads to use (default: 1)"
    )

    parser.add_argument(
        "--max-concurrent-movies",
        type=int,
        default=1,
        help="Number of movies to process simultaneously (default: 1)",
    )

    parser.add_argument(
        "-l",
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )

    parser.add_argument("--dry-run", action="store_true", help="Run without making changes")

    parser.add_argument("--temp-dir", help="Directory for temporary files")

    parser.add_argument(
        "--target-resolution",
        default="1920x1080",
        help="Target resolution in format WIDTHxHEIGHT (default: 1920x1080)",
    )

    parser.add_argument(
        "--use-gpu", action="store_true", help="Enable NVIDIA GPU acceleration if available"
    )

    parser.add_argument(
        "--gpu-quality",
        type=int,
        default=20,
        choices=range(0, 51),
        metavar="[0-51]",
        help="GPU encoding quality (0-51, lower is better, default: 20)",
    )

    video_descs, audio_descs = _get_codec_descriptions()

    parser.add_argument(
        "--video-codec",
        choices=[codec.name for codec in VideoCodec],
        default="H264",
        help=create_codec_help(VideoCodec, video_descs),
        metavar="CODEC",
    )

    parser.add_argument(
        "--audio-codec",
        choices=[codec.name for codec in AudioCodec],
        default="AAC",
        help=create_codec_help(AudioCodec, audio_descs),
        metavar="CODEC",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files if they exist (default: False)",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    """Validate command line arguments."""
    # Check input directory
    input_path = Path(args.input_dir)
    if not input_path.exists():
        raise ValueError(f"Input directory does not exist: {input_path}")

    # Validate years
    years = [y.strip() for y in args.years.split(",")]
    if not years:
        raise ValueError("No years specified")
    for year in years:
        if not year.isdigit() or len(year) != 4:
            raise ValueError(f"Invalid year: {year}")

    # Check thread count
    if args.threads < 1:
        raise ValueError(f"Invalid thread count: {args.threads}")

    # Check max concurrent movies
    if args.max_concurrent_movies < 1:
        raise ValueError(f"Invalid max concurrent movies: {args.max_concurrent_movies}")

    # Validate target resolution
    try:
        width, height = map(int, args.target_resolution.split("x"))
        if width <= 0 or height <= 0:
            raise ValueError
    except ValueError:
        raise ValueError(
            f"Invalid target resolution format: {args.target_resolution}. "
            "Must be in format WIDTHxHEIGHT (e.g., 1920x1080)"
        )


def process_videos_by_years(args: argparse.Namespace) -> None:
    """Process videos according to arguments."""
    # Parse target resolution
    width, height = map(int, args.target_resolution.split("x"))

    # Create processing configuration
    config = ProcessingConfig(
        input_path=Path(args.input_dir),
        output_path=Path(args.output_dir),
        years=[y.strip() for y in args.years.split(",")],
        encoding=EncodingConfig(
            video_codec=VideoCodec[args.video_codec],
            audio_codec=AudioCodec[args.audio_codec],
            use_gpu=args.use_gpu,
            crf=args.gpu_quality,
            preset="medium",
        ),
        options=ProcessingOptions(
            threads=args.threads,
            max_concurrent_movies=args.max_concurrent_movies,
            target_resolution=(width, height),
            temp_dir=Path(args.temp_dir) if args.temp_dir else Path(args.output_dir) / "temp",
            dry_run=args.dry_run,
            log_level=args.log_level,
            overwrite=args.overwrite,
        ),
    )

    # Create temp directory
    logger.debug(f"Using temp directory: {config.options.temp_dir}")
    if not config.options.temp_dir.exists():
        config.options.temp_dir.mkdir(parents=True)

    # Initialize video processor
    project_processor = Project(config)

    for year in config.years:
        project_processor.process(year)


def main() -> int:
    """Main entry point."""
    try:
        # Parse arguments
        args = parse_args()

        # Configure logging
        configure_logging(args.log_level)

        logger.info("Starting movie-merge processing")
        logger.debug("Parsed arguments: %s", vars(args))

        # Validate arguments
        validate_args(args)

        if args.dry_run:
            logger.info("Running in dry-run mode - no changes will be made")

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if args.log_level == "DEBUG":
            logger.exception("Traceback:")
        return 1

    # Process videos by year
    try:
        process_videos_by_years(args)
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if args.log_level == "DEBUG":
            logger.exception("Traceback:")
        return 1

    logger.info("Processing completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
