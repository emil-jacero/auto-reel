"""Directory configuration and parsing."""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml

from movie_merge.constants import METADATA_FILE

from ..clip.title import DescriptionConfig, TitleCardConfig, TitleConfig
from .exceptions import DirectoryParseError
from .sort import SortConfig, SortMethod

logger = logging.getLogger(__name__)


@dataclass
class Metadata:
    """Movie metadata."""

    title: Optional[str] = None  # Required: Stores the raw title part without date
    date: Optional[datetime] = None  # Required: From yaml or folder name
    location: Optional[str] = None  # Optional: From yaml or folder name

    @property
    def year(self) -> str:
        """Get the year as a string."""
        return str(self.date.year) if self.date else ""

    def to_dict(self) -> dict:
        """Convert to dictionary with JSON-serializable values."""
        return {
            "title": self.title,
            "date": self.date.isoformat() if self.date else None,
            "location": self.location,
            "year": self.year,
        }


@dataclass
class DirectoryConfig:
    """Configuration for directory processing."""

    title: Optional[str] = None  # Title of the movie. Overrides auto-parsed title.
    description: Optional[
        str
    ] = None  # Description of the movie. Overrides auto-parsed description.
    metadata: Metadata = field(
        default_factory=Metadata
    )  # Metadata for the movie. Usually parsed from folder name.
    sort_config: SortConfig = field(default_factory=SortConfig)
    title_config: TitleCardConfig = field(default_factory=TitleCardConfig)
    root_dir: Optional[Path] = None  # Root directory path

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "metadata": self.metadata.to_dict(),
            "sort_config": self.sort_config.to_dict(),
            "title_config": self.title_config.to_dict(),
            "root_dir": str(self.root_dir) if self.root_dir else None,
        }


def parse_folder_name(folder_name: str) -> Tuple[datetime, str, Optional[str]]:
    """Parse folder name with format 'YYYY-MM-DD - Title [- Location]'."""
    date_pattern = r"^(\d{4}-\d{2}-\d{2})"
    match = re.match(date_pattern, folder_name)

    if not match:
        raise DirectoryParseError(
            f"Could not find required date (YYYY-MM-DD) in folder name: {folder_name}"
        )

    try:
        date = datetime.strptime(match.group(1), "%Y-%m-%d")
    except ValueError as e:
        raise DirectoryParseError(f"Invalid date format in folder name: {folder_name}") from e

    remaining = folder_name[len(match.group(1)) :].strip(" -")

    if not remaining:
        raise DirectoryParseError(f"Could not find required title in folder name: {folder_name}")

    parts = remaining.rsplit(" - ", 1)
    title = parts[0].strip()
    location = parts[1].strip() if len(parts) == 2 else None

    return date, title, location


def parse_directory_config(directory: Path) -> DirectoryConfig:
    """Parse directory configuration from metadata.yaml or folder name."""
    config = DirectoryConfig()
    metadata_path = directory / METADATA_FILE

    # Initialize metadata from folder name first
    try:
        date, title, location = parse_folder_name(directory.name)
        config.metadata = Metadata(title=title, date=date, location=location)
    except DirectoryParseError as e:
        logger.debug(f"Could not parse metadata from folder name: {e}")
        config.metadata = Metadata()  # Create empty metadata if folder parsing fails

    # Try to parse from metadata.yaml to override/supplement folder metadata
    if metadata_path.exists():
        logger.debug(f"Found metadata file: {metadata_path}")
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)

            if isinstance(yaml_data, dict):
                # Parse metadata section
                if metadata_config := yaml_data.get("metadata", {}):
                    logger.debug(f"Parsing metadata section: {metadata_config}")
                    if yaml_title := metadata_config.get("title"):
                        config.metadata.title = yaml_title
                    if yaml_date := _parse_date(metadata_config.get("date")):
                        config.metadata.date = yaml_date
                    if yaml_location := metadata_config.get("location"):
                        config.metadata.location = yaml_location

                # Parse other sections
                config.title = yaml_data.get("title")
                config.description = yaml_data.get("description")

                if sort_config := yaml_data.get("sort"):
                    config.sort_config = _parse_sort_config(sort_config)

                if title_config := yaml_data.get("title_card"):
                    config.title_config = _parse_title_config(title_config)

        except Exception as e:
            logger.warning(f"Failed to parse metadata.yaml: {e}")

    # Verify we have required metadata
    if not (config.metadata.title and config.metadata.date):
        raise DirectoryParseError(
            f"Could not find required metadata (title and date) in either metadata.yaml "
            f"or folder name for directory: {directory}"
        )

    # Set description from location if not explicitly set
    if not config.description and config.metadata.location:
        config.description = f"Filmed in {config.metadata.location}"

    # Generate movie title if not set
    if not config.title:
        config.title = f"{config.metadata.date.strftime('%Y-%m-%d')} - " f"{config.metadata.title}"

    config.root_dir = directory

    logger.debug(
        f"Parsed directory config: {json.dumps(config.to_dict(), indent=2, ensure_ascii=False)}"
    )
    return config


def _parse_date(date_value: Optional[str]) -> Optional[datetime]:
    """Parse date from various formats."""
    if not date_value:
        return None

    if isinstance(date_value, datetime):
        return date_value

    try:
        return datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        logger.warning(f"Invalid date format: {date_value}")
        return None


def _parse_sort_config(config: dict) -> SortConfig:
    """Parse sort configuration from dictionary."""
    try:
        method = SortMethod(config.get("method", "datetime").lower())
    except ValueError:
        logger.warning(f"Invalid sort method: {config.get('method')}")
        method = SortMethod.DATETIME

    return SortConfig(
        method=method,
        reverse=config.get("reverse", False),
        custom_order=config.get("custom_order"),
    )


def _parse_title_config(config: dict) -> TitleCardConfig:
    """Parse title configuration from dictionary."""
    return TitleCardConfig(
        title=TitleConfig(
            font=config.get("title", {}).get("font", "Arial"),
            font_size=config.get("title", {}).get("font_size", 200),
            font_color=config.get("title", {}).get("font_color", "white"),
            font_shadow=config.get("title", {}).get("font_shadow", True),
        ),
        description=DescriptionConfig(
            font=config.get("description", {}).get("font", "Arial"),
            font_size=config.get("description", {}).get("font_size", 150),
            font_color=config.get("description", {}).get("font_color", "white"),
            offset=config.get("description", {}).get("offset", 50),
            font_shadow=config.get("description", {}).get("font_shadow", True),
        ),
        fade_duration=config.get("fade_duration", 2.0),
        duration=config.get("duration", 7.0),
        position=config.get("position", ("center", "center")),
    )
