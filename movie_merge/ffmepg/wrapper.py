""" Wrapper for FFmpeg operations. """

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..config.processing import EncodingConfig, ProcessingOptions
from .exceptions import FFmpegError, FFprobeError


class FFmpegWrapper:
    """Wrapper for FFmpeg operations."""

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize FFmpeg wrapper.

        Args:
            ffmpeg_path: Path to ffmpeg executable. If None, searches in PATH.
            ffprobe_path: Path to ffprobe executable. If None, searches in PATH.
            logger: Logger instance. If None, creates a new one.

        Raises:
            FFmpegError: If ffmpeg or ffprobe executables are not found
        """
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg")
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe")

        if not self.ffmpeg_path:
            raise FFmpegError("ffmpeg executable not found in PATH")
        if not self.ffprobe_path:
            raise FFmpegError("ffprobe executable not found in PATH")

        self.logger = logger or logging.getLogger(__name__)

    def _run_command(
        self, cmd: List[str], capture_output: bool = True, check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a command and handle errors.

        Args:
            cmd: Command list to execute
            capture_output: Whether to capture command output
            check: Whether to check return code

        Returns:
            CompletedProcess instance

        Raises:
            FFmpegError: If command execution fails
        """
        try:
            self.logger.debug(f"Running command: {' '.join(cmd)}")
            return subprocess.run(cmd, capture_output=capture_output, text=True, check=check)
        except subprocess.CalledProcessError as e:
            raise FFmpegError(f"Command failed: {e.stderr}")
        except Exception as e:
            raise FFmpegError(f"Error running command: {str(e)}")

    def probe(self, input_file: Union[str, Path]) -> Dict[str, Any]:
        """Get media file information using ffprobe.

        Args:
            input_file: Path to input media file

        Returns:
            Dictionary containing file information

        Raises:
            FFprobeError: If ffprobe command fails or output is invalid
        """
        cmd = [
            self.ffprobe_path,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(input_file),
        ]

        try:
            result = self._run_command(cmd)
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise FFprobeError(f"Failed to parse ffprobe output: {e}")
        except Exception as e:
            raise FFprobeError(f"Probe failed: {str(e)}")

    def get_video_info(self, input_file: Union[str, Path]) -> Dict[str, Any]:
        """Extract relevant video information.

        Args:
            input_file: Path to input video file

        Returns:
            Dictionary containing video information

        Raises:
            FFprobeError: If video stream is not found or info extraction fails
        """
        try:
            probe_data = self.probe(input_file)

            # Find video stream
            video_stream = next(
                (s for s in probe_data["streams"] if s["codec_type"] == "video"), None
            )

            if not video_stream:
                raise FFprobeError("No video stream found")

            # Extract frame rate
            fps = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = map(int, fps.split("/"))
                fps = num / den if den != 0 else 0
            except (ValueError, ZeroDivisionError):
                fps = 0

            return {
                "codec": video_stream.get("codec_name"),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "duration": float(probe_data["format"].get("duration", 0)),
                "bitrate": int(probe_data["format"].get("bit_rate", 0)),
                "fps": fps,
                "pix_fmt": video_stream.get("pix_fmt"),
                "profile": video_stream.get("profile"),
                "is_hdr": "color_transfer" in video_stream
                and "smpte2084" in video_stream["color_transfer"].lower(),
            }

        except Exception as e:
            raise FFprobeError(f"Failed to get video info: {str(e)}")

    def build_conversion_command(
        self,
        input_file: Union[str, Path],
        output_file: Union[str, Path],
        encoding_config: EncodingConfig,
        options: ProcessingOptions,
    ) -> List[str]:
        """Build ffmpeg conversion command.

        Args:
            input_file: Path to input file
            output_file: Path to output file
            encoding_config: Encoding configuration
            options: Processing options

        Returns:
            List of command arguments
        """
        cmd = [self.ffmpeg_path, "-y"]  # Overwrite output files

        # Input options
        if options.threads > 1:
            cmd.extend(["-threads", str(options.threads)])

        # Input file
        cmd.extend(["-i", str(input_file)])

        # Video codec options
        video_options = encoding_config.video_codec.get_encoding_options(
            quality=encoding_config.crf, preset=encoding_config.preset
        )

        # Video codec
        cmd.extend(["-c:v", encoding_config.video_codec.value])

        # Add encoding options
        for key, value in video_options.items():
            if value is not None:
                cmd.extend([f"-{key}", str(value)])

        # Scale video if needed
        if options.target_resolution != (0, 0):
            width, height = options.target_resolution
            cmd.extend(["-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease"])

        # Audio codec
        cmd.extend(["-c:a", encoding_config.audio_codec.value])

        # Add audio options
        audio_options = encoding_config.audio_codec.get_encoding_options()
        for key, value in audio_options.items():
            if value is not None:
                cmd.extend([f"-{key}", str(value)])

        # Add output file
        cmd.append(str(output_file))

        return cmd

    def convert(
        self,
        input_file: Union[str, Path],
        output_file: Union[str, Path],
        encoding_config: EncodingConfig,
        options: ProcessingOptions,
        progress_callback: Optional[callable] = None,
    ) -> None:
        """Convert video file using FFmpeg.

        Args:
            input_file: Path to input file
            output_file: Path to output file
            encoding_config: Encoding configuration
            options: Processing options
            progress_callback: Optional callback function for progress updates

        Raises:
            FFmpegError: If conversion fails
        """
        cmd = self.build_conversion_command(input_file, output_file, encoding_config, options)

        self.logger.info(f"Starting conversion: {input_file} -> {output_file}")
        self.logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        if options.dry_run:
            self.logger.info("Dry run - skipping conversion")
            return

        try:
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
            )

            duration = self.get_video_info(input_file)["duration"]

            # Process output in real-time
            while True:
                if process.stderr is None:
                    break

                output = process.stderr.readline()

                if output == "" and process.poll() is not None:
                    break

                if output:
                    self.logger.debug(output.strip())

                    # Parse progress if callback provided
                    if progress_callback and "time=" in output:
                        try:
                            time_str = output.split("time=")[1].split()[0]
                            hours, minutes, seconds = map(float, time_str.split(":"))
                            current_time = hours * 3600 + minutes * 60 + seconds
                            progress = min(current_time / duration * 100, 100)
                            progress_callback(progress)
                        except Exception as e:
                            self.logger.debug(f"Failed to parse progress: {e}")

            if process.returncode != 0:
                raise FFmpegError(f"FFmpeg conversion failed with return code {process.returncode}")

            self.logger.info("Conversion completed successfully")

        except Exception as e:
            raise FFmpegError(f"Conversion failed: {str(e)}")

    def create_overlay(
        self,
        input_file: Path,
        frames_dir: Path,
        overlay_file: Path,
        fps: int = 30,
        duration: float = 7.0,
    ) -> None:
        """Create overlay video from PNG frames."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "frame_%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuva420p",  # Required for alpha transparency
            "-t",
            str(duration),
            "-shortest",
            str(overlay_file),
        ]
        self._run_command(cmd)

    def overlay_video(
        self,
        input_file: Path,
        overlay_file: Path,
        output_file: Path,
        options: ProcessingOptions,
    ) -> None:
        """Apply overlay video to input video."""
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            str(input_file),
            "-i",
            str(overlay_file),
            "-filter_complex",
            "[1:v]format=yuva420p[overlay];[0:v][overlay]overlay=0:0",
            "-c:a",
            "copy",
            str(output_file),
        ]
        self._run_command(cmd)
