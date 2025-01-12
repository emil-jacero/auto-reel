from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont


@dataclass
class TitleConfig:
    """Configuration for title card appearance."""

    font: str = "Arial"  # Font name. Overrides the TitleCardConfig font.
    font_size: int = 70  # Font size for title text.
    font_color: str = "white"  # Font color for title text.
    font_shadow: bool = True  # Add shadow to text

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "font": self.font,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "font_shadow": self.font_shadow,
        }


@dataclass
class DescriptionConfig:
    """Configuration for description card appearance."""

    font: str = "Arial"  # Font name. Overrides the TitleCardConfig font.
    font_size: int = 40  # Font size for description text.
    font_color: str = "white"  # Font color for description text.
    offset: int = 50  # Y offset from title position
    font_shadow: bool = True  # Add shadow to text

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "font": self.font,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "offset": self.offset,
            "font_shadow": self.font_shadow,
        }


@dataclass
class TitleCardConfig:
    """Configuration for title card appearance."""

    title: TitleConfig = field(default_factory=TitleConfig)
    description: DescriptionConfig = field(default_factory=DescriptionConfig)
    fade_duration: float = 2.0  # Duration of fade in seconds
    duration: float = 7.0  # Total duration of title card
    position: Tuple[str, str] = ("center", "center")
    fps: int = 30  # Frames per second for fade effect

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title.to_dict(),
            "description": self.description.to_dict(),
            "fade_duration": self.fade_duration,
            "duration": self.duration,
            "position": self.position,
            "fps": self.fps,
        }


class TitleCardGenerator:
    def __init__(self):
        self._cache = {}

    def _get_font(self, size: int) -> ImageFont.FreeTypeFont:
        if size not in self._cache:
            try:
                self._cache[size] = ImageFont.load_default()
            except Exception:
                self._cache[size] = ImageFont.load_default()
        return self._cache[size]

    def _add_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        text_color: str = "white",
        shadow_color: str = "black",
        shadow_offset: int = 3,
        alpha: int = 255,
    ) -> None:
        shadow_color = (*ImageColor.getrgb(shadow_color), alpha)
        text_color = (*ImageColor.getrgb(text_color), alpha)

        shadow_position = (position[0] + shadow_offset, position[1] + shadow_offset)
        draw.text(shadow_position, text, font=font, fill=shadow_color)
        draw.text(position, text, font=font, fill=text_color)

    def generate_frame(
        self,
        width: int,
        height: int,
        title: str,
        opacity: float = 1.0,
        description: Optional[str] = None,
        config: Optional[TitleCardConfig] = None,
    ) -> Image.Image:
        if config is None:
            config = TitleCardConfig()

        # Create a transparent background (all alpha values set to 0)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        # Create a drawing context
        draw = ImageDraw.Draw(image, "RGBA")

        title_font = self._get_font(config.title.font_size)
        desc_font = self._get_font(config.description.font_size)

        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]

        title_x = (width - title_width) // 2
        title_y = (height - title_height) // 2

        # Calculate alpha for fade effect
        alpha = max(0, min(255, int(255 * opacity)))

        if description:
            desc_bbox = draw.textbbox((0, 0), description, font=desc_font)
            desc_width = desc_bbox[2] - desc_bbox[0]
            desc_height = desc_bbox[3] - desc_bbox[1]

            title_y -= (desc_height + config.description.offset) // 2
            desc_x = (width - desc_width) // 2
            desc_y = title_y + title_height + config.description.offset

            if config.description.font_shadow:
                # Use transparent shadow for description
                self._add_text_with_shadow(
                    draw,
                    (desc_x, desc_y),
                    description,
                    desc_font,
                    config.description.font_color,
                    shadow_color="black",
                    shadow_offset=3,
                    alpha=alpha,
                )
            else:
                text_color = ImageColor.getrgb(config.description.font_color)
                draw.text((desc_x, desc_y), description, font=desc_font, fill=(*text_color, alpha))

        if config.title.font_shadow:
            # Use transparent shadow for title
            self._add_text_with_shadow(
                draw,
                (title_x, title_y),
                title,
                title_font,
                config.title.font_color,
                shadow_color="black",
                shadow_offset=3,
                alpha=alpha,
            )
        else:
            text_color = ImageColor.getrgb(config.title.font_color)
            draw.text((title_x, title_y), title, title_font, fill=(*text_color, alpha))

        return image

    def generate_fade_sequence(
        self,
        width: int,
        height: int,
        title: str,
        description: Optional[str] = None,
        config: Optional[TitleCardConfig] = None,
    ) -> List[Image.Image]:
        if config is None:
            config = TitleCardConfig()

        frames = []
        num_fade_frames = int(config.fade_duration * config.fps)

        for i in range(num_fade_frames):
            opacity = i / num_fade_frames
            frame = self.generate_frame(
                width, height, title, opacity=opacity, description=description, config=config
            )
            frames.append(frame)

        return frames
