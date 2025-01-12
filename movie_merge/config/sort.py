""" Configuration for sorting videos. """

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class SortMethod(Enum):
    """Video sorting methods."""

    DATETIME = "datetime"
    FILENAME = "filename"
    CUSTOM = "custom"


@dataclass
class SortConfig:
    """Configuration for sorting videos."""

    method: SortMethod = SortMethod.DATETIME
    reverse: bool = False
    custom_order: Optional[Dict[str, int]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "method": self.method.value,
            "reverse": self.reverse,
            "custom_order": self.custom_order,
        }
