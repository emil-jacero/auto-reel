from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from ..config.directory import TitleCardConfig


class TitleCardGenerator:
    def __init__(self, font_dir: Path):
        self.font_dir = font_dir
        self._cache = {}

    def _get_font(self, font_name: str, size: int) -> ImageFont.FreeTypeFont:
        cache_key = (font_name, size)
        if cache_key not in self._cache:
            try:
                font_path = self.font_dir / f"{font_name}.ttf"
                self._cache[cache_key] = ImageFont.truetype(str(font_path), size)
            except Exception as e:
                # Fallback to default font
                self._cache[cache_key] = ImageFont.load_default()
        return self._cache[cache_key]

    def _add_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        position: Tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
        text_color: str = "white",
        shadow_color: str = "black",
        shadow_offset: int = 3,
    ) -> None:
        # Draw shadow
        shadow_position = (position[0] + shadow_offset, position[1] + shadow_offset)
        draw.text(shadow_position, text, font=font, fill=shadow_color)
        # Draw text
        draw.text(position, text, font=font, fill=text_color)

    def generate(
        self,
        width: int,
        height: int,
        title: str,
        description: Optional[str] = None,
        config: TitleCardConfig = None,
        background_color: str = "black",
    ) -> Image.Image:
        if config is None:
            config = TitleCardConfig()

        # Create image
        image = Image.new("RGB", (width, height), background_color)
        draw = ImageDraw.Draw(image)

        # Load fonts
        title_font = self._get_font(config.title.font, config.title.font_size)
        desc_font = self._get_font(config.description.font, config.description.font_size)

        # Calculate text sizes
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_height = title_bbox[3] - title_bbox[1]

        # Calculate positions
        title_x = (width - title_width) // 2
        title_y = (height - title_height) // 2

        if description:
            desc_bbox = draw.textbbox((0, 0), description, font=desc_font)
            desc_width = desc_bbox[2] - desc_bbox[0]
            desc_height = desc_bbox[3] - desc_bbox[1]

            # Adjust positions for both texts
            title_y -= (desc_height + config.description.offset) // 2
            desc_x = (width - desc_width) // 2
            desc_y = title_y + title_height + config.description.offset

            # Draw description
            if config.description.font_shadow:
                self._add_text_with_shadow(
                    draw, (desc_x, desc_y), description, desc_font, config.description.font_color
                )
            else:
                draw.text(
                    (desc_x, desc_y),
                    description,
                    font=desc_font,
                    fill=config.description.font_color,
                )

        # Draw title
        if config.title.font_shadow:
            self._add_text_with_shadow(
                draw, (title_x, title_y), title, title_font, config.title.font_color
            )
        else:
            draw.text((title_x, title_y), title, font=title_font, fill=config.title.font_color)

        return image
