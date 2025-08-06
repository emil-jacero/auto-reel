"""Title card generation functionality using MoviePy."""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.video.fx.CrossFadeIn import CrossFadeIn
from moviepy.video.fx.CrossFadeOut import CrossFadeOut
from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import ColorClip, TextClip

logger = logging.getLogger(__name__)


@dataclass
class TitleConfig:
    """Configuration for title card appearance.

    Attributes:
        font: Font name (e.g., "Arial", "/usr/share/fonts/ubuntu-family/Ubuntu-M.ttf")
        font_size: Font size in pixels
        font_color: Font color (e.g., "white", "black", "#FF0000")
        font_shadow: Whether to add shadow effect
        kerning: Letter spacing (positive=wider, negative=tighter)
        interline: Line spacing (positive=wider, negative=tighter)
    """

    font: str = "/usr/share/fonts/ubuntu-family/Ubuntu-M.ttf"
    font_size: int = 70
    font_color: str = "white"
    font_shadow: bool = True
    kerning: Optional[int] = None
    interline: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "font": self.font,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "font_shadow": self.font_shadow,
            "kerning": self.kerning,
            "interline": self.interline,
        }


@dataclass
class DescriptionConfig:
    """Configuration for description card appearance.

    Attributes:
        font: Font name (e.g., "Arial", "/usr/share/fonts/ubuntu-family/Ubuntu-M.ttf")
        font_size: Font size in pixels
        font_color: Font color (e.g., "white", "black", "#FF0000")
        offset: Vertical offset from title in pixels (deprecated, use relative_offset)
        relative_offset: Relative offset from center as fraction of video height (0.0 to 1.0)
        font_shadow: Whether to add shadow effect
        kerning: Letter spacing (positive=wider, negative=tighter)
        interline: Line spacing (positive=wider, negative=tighter)
        max_width_ratio: Maximum text width as fraction of video width (0.0 to 1.0)
    """

    font: str = "/usr/share/fonts/ubuntu-family/Ubuntu-M.ttf"
    font_size: int = 50
    font_color: str = "white"
    offset: int = 50  # Deprecated, kept for backward compatibility
    relative_offset: float = 0.15  # 15% below center
    font_shadow: bool = True
    kerning: Optional[int] = None
    interline: Optional[int] = None
    max_width_ratio: float = 0.8  # 80% of video width

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "font": self.font,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "offset": self.offset,
            "relative_offset": self.relative_offset,
            "font_shadow": self.font_shadow,
            "kerning": self.kerning,
            "interline": self.interline,
            "max_width_ratio": self.max_width_ratio,
        }


@dataclass
class TitleCardConfig:
    """Configuration for title card appearance.

    Attributes:
        title: Title text configuration
        description: Description text configuration
        fade_duration: Duration of fade-in effect in seconds
        duration: Total duration of title card in seconds
        position: Position of the title card ("center", "center")
        background_opacity: Opacity of the background (0.0 to 1.0). Set to 0 to disable.
        fps: Target framerate for title card rendering
    """

    title: TitleConfig = field(default_factory=TitleConfig)
    description: DescriptionConfig = field(default_factory=DescriptionConfig)
    fade_duration: float = 2.0
    duration: float = 7.0
    position: Tuple[str, str] = ("center", "center")
    background_opacity: float = 0
    fps: float = 25.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title.to_dict(),
            "description": self.description.to_dict(),
            "fade_duration": self.fade_duration,
            "duration": self.duration,
            "position": self.position,
            "background_opacity": self.background_opacity,
            "fps": self.fps,
        }


class TitleCardGenerator:
    """Generates title cards using MoviePy."""

    def __init__(self) -> None:
        """Initialize the title card generator."""
        logger.debug("Initializing TitleCardGenerator")
        self._video: Optional[VideoFileClip] = None
        self._final: Optional[CompositeVideoClip] = None

    def _build_text_args(self, text: str, config_section: Any) -> Dict[str, Any]:
        """Build text clip arguments from configuration."""
        video_size = self._video.size if self._video else (1920, 1080)

        # Calculate maximum text width based on configuration
        if hasattr(config_section, "max_width_ratio"):
            max_width = int(video_size[0] * config_section.max_width_ratio)
        else:
            max_width = int(video_size[0] * 0.8)  # Default to 80% of video width

        args = {
            "text": text,
            "font_size": config_section.font_size,
            "color": config_section.font_color,
            "font": "/usr/share/fonts/ubuntu-family/Ubuntu-M.ttf",
            "size": (max_width, None),  # Set width constraint, let height adjust
        }
        return args

    def _create_background(self, config: Any) -> ColorClip:
        """Create semi-transparent background clip.

        Args:
            config: Title card configuration

        Returns:
            ColorClip with fade effects
        """
        # First make a ColorClip with the size & color you want.
        video_size = self._video.size if self._video else (1920, 1080)
        bg = ColorClip(size=video_size, color=(0, 0, 0))
        # Then set its total duration.
        bg = bg.with_duration(config.duration)
        # Then apply a standard fade in/out if you want color-based fading:
        bg = FadeIn(config.fade_duration).apply(bg)
        bg = FadeOut(config.fade_duration).apply(bg)

        # Finally, set its opacity. (You can do this earlier, but this is a clear place.)
        # “with_opacity()” is the new method for setting alpha in MoviePy 2.x
        bg = bg.with_opacity(config.background_opacity)

        return bg

    def _create_text_clip(
        self, text: str, config_section: Any, config: Any, y_position: Optional[int] = None
    ) -> TextClip:
        """Create and return a text clip with fade effects."""
        text_args = self._build_text_args(text, config_section)
        clip = TextClip(**text_args)

        video_size = self._video.size if self._video else (1920, 1080)
        video_width, video_height = video_size

        # Calculate position with bounds checking
        position: Union[str, Tuple[str, int]]
        if y_position is None:
            # This is the title - center it
            position = "center"
            logger.debug(f"Title '{text[:30]}...' positioned at: center")
        else:
            # This is description or location - use relative positioning
            center_y = video_height // 2

            # Use relative offset if available, fallback to absolute offset
            if hasattr(config_section, "relative_offset"):
                relative_offset_pixels = int(video_height * config_section.relative_offset)
                adjusted_y = center_y + relative_offset_pixels
                logger.debug(
                    f"Using relative offset: {config_section.relative_offset} ({relative_offset_pixels}px)"
                )
            else:
                # Fallback to legacy absolute offset
                adjusted_y = center_y + config_section.offset
                logger.debug(f"Using absolute offset: {config_section.offset}px")

            # Get text clip dimensions for bounds checking
            # We need to create a temporary clip to get its size
            temp_clip = TextClip(**text_args)
            text_height = (
                temp_clip.size[1]
                if (temp_clip.size and len(temp_clip.size) > 1)
                else config_section.font_size
            )
            temp_clip.close()

            # Ensure text doesn't go below the bottom of the video
            max_y = video_height - text_height - 20  # 20px margin from bottom
            if adjusted_y > max_y:
                adjusted_y = max_y
                logger.warning(
                    f"Text '{text[:30]}...' position clamped to {adjusted_y} (was going to be off-screen)"
                )

            # Ensure text doesn't go above the center (to avoid overlapping title)
            min_y = center_y + 10  # 10px margin from center
            if adjusted_y < min_y:
                adjusted_y = min_y
                logger.warning(
                    f"Text '{text[:30]}...' position clamped to {adjusted_y} (was overlapping title)"
                )

            position = ("center", adjusted_y)
            logger.debug(
                f"Text '{text[:30]}...' - Video size: {video_size}, Center Y: {center_y}, Final position: {position}, Text height: {text_height}"
            )

        # 1) Set duration
        clip = clip.with_duration(config.duration)
        # 2) Set position
        clip = clip.with_position(position)
        # 3) Apply crossfade in/out
        clip = CrossFadeIn(config.fade_duration).apply(clip)
        clip = CrossFadeOut(config.fade_duration).apply(clip)

        return clip

    def _cleanup(self, clips: list) -> None:
        """Clean up video clips.

        Args:
            clips: List of clips to close
        """
        logger.debug("Cleaning up resources")
        for clip in clips:
            if clip:
                try:
                    clip.close()
                except Exception as e:
                    logger.warning(f"Error closing clip: {e}")

    def extract_title_segment(
        self,
        input_file: Path,
        output_file: Path,
        duration: float,
        threads: int = 4,
        encoding_preset: str = "medium",
    ) -> None:
        """Extract a segment from the beginning of a video for title overlay.

        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            duration: Duration in seconds to extract
            threads: Number of threads to use for processing
        """
        try:
            logger.info(f"Extracting {duration}s segment from: {input_file}")

            # Use ffmpeg to extract the segment
            cmd = [
                self._ffmpeg.ffmpeg_path if hasattr(self, "_ffmpeg") else "ffmpeg",
                "-y",
                "-i",
                str(input_file),
                "-ss",
                "0",
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-preset",
                encoding_preset,
                "-threads",
                str(threads),
                str(output_file),
            ]

            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Successfully extracted title segment to {output_file}")

        except Exception as e:
            logger.error(f"Failed to extract title segment: {str(e)}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            raise RuntimeError(f"Failed to extract title segment: {str(e)}") from e

    def generate_title_sequence(
        self,
        input_file: Path,
        output_file: Path,
        title: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        config: Optional[TitleCardConfig] = None,
        threads: int = 4,
        fps: float = 30.0,
        use_segment: bool = True,
        encoding_preset: str = "medium",
    ) -> None:
        """Generate a title sequence for a video."""
        clips_to_close = []
        temp_segment_file = None

        try:
            if config is None:
                config = TitleCardConfig()

            logger.info(f"Generating title sequence for: {title}")

            # Use a short segment if requested
            working_input = input_file
            if use_segment:
                # Create temporary file for the segment
                temp_segment_file = output_file.with_name(f"temp_segment_{output_file.name}")
                self.extract_title_segment(
                    input_file=input_file,
                    output_file=temp_segment_file,
                    duration=config.duration,
                    threads=threads,
                    encoding_preset=encoding_preset,
                )
                working_input = temp_segment_file

            # Load the video (either full or segment)
            self._video = VideoFileClip(str(working_input))
            clips_to_close.append(self._video)

            # Create clips list starting with video
            clips = [self._video]

            # Add semi-transparent background if enabled
            if config.background_opacity > 0:
                bg = self._create_background(config)
                clips_to_close.append(bg)
                clips.append(bg)

            # Create title clip with fade effects
            logger.debug(f"Adding title: {title}")
            title_clip = self._create_text_clip(title, config.title, config)
            clips_to_close.append(title_clip)
            clips.append(title_clip)

            # Add description and/or location text
            if description:
                logger.debug(f"Adding description: {description}")

                # If both description and location exist, add location first (above description)
                if location:
                    logger.debug(f"Adding location above description: {location}")
                    # Create a custom config for location with smaller offset
                    location_config = DescriptionConfig(
                        font=config.description.font,
                        font_size=int(
                            config.description.font_size * 0.8
                        ),  # Slightly smaller than description
                        font_color=config.description.font_color,
                        offset=int(
                            config.description.offset * 0.6
                        ),  # Legacy: position between title and description
                        relative_offset=config.description.relative_offset
                        * 0.5,  # Half the description offset
                        font_shadow=config.description.font_shadow,
                        kerning=config.description.kerning,
                        interline=config.description.interline,
                        max_width_ratio=config.description.max_width_ratio,
                    )
                    location_clip = self._create_text_clip(
                        location,
                        location_config,
                        config,
                        y_position=1,  # Any non-None value will trigger positioning logic
                    )
                    clips_to_close.append(location_clip)
                    clips.append(location_clip)

                    # Create description config with larger offset to make room for location
                    desc_config = DescriptionConfig(
                        font=config.description.font,
                        font_size=config.description.font_size,
                        font_color=config.description.font_color,
                        offset=config.description.offset
                        + int(config.description.offset * 0.8),  # Legacy: push down further
                        relative_offset=config.description.relative_offset
                        * 1.5,  # Push down further with relative positioning
                        font_shadow=config.description.font_shadow,
                        kerning=config.description.kerning,
                        interline=config.description.interline,
                        max_width_ratio=config.description.max_width_ratio,
                    )
                else:
                    # No location, use normal description config
                    desc_config = config.description

                # Add the description clip
                desc_clip = self._create_text_clip(
                    description,
                    desc_config,
                    config,
                    y_position=1,  # Any non-None value will trigger positioning logic
                )
                clips_to_close.append(desc_clip)
                clips.append(desc_clip)

            elif location:
                # No description, but location exists - show formatted location as the main text
                formatted_location = f"Plats: {location}"
                logger.debug(
                    f"Adding formatted location as main text (no description): {formatted_location}"
                )
                location_clip = self._create_text_clip(
                    formatted_location,
                    config.description,  # Use normal description config for positioning
                    config,
                    y_position=1,  # Any non-None value will trigger positioning logic
                )
                clips_to_close.append(location_clip)
                clips.append(location_clip)

            # Combine all clips
            logger.debug("Compositing video clips")
            self._final = CompositeVideoClip(clips)
            clips_to_close.append(self._final)

            logger.debug(f"Threads: {threads}, FPS: {fps}")

            # Write to file
            logger.info(f"Writing title sequence to: {output_file}")
            self._final.write_videofile(
                str(output_file),
                fps=fps,
                codec="libx264",
                audio_codec="aac",
                preset=encoding_preset,
                threads=threads,
                logger=None,  # Disable moviepy's internal logging
            )

            logger.info("Successfully generated title sequence")

        except Exception as e:
            logger.error(f"Failed to generate title sequence: {str(e)}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception("Traceback:")
            raise RuntimeError(f"Failed to generate title sequence: {str(e)}") from e

        finally:
            # Clean up resources
            self._cleanup(clips_to_close)

            # Remove temporary segment if created
            if temp_segment_file and Path(temp_segment_file).exists():
                try:
                    Path(temp_segment_file).unlink()
                    logger.debug(f"Removed temporary segment file: {temp_segment_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary segment file: {e}")
