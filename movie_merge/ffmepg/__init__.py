"""FFmpeg wrapper module."""

from .exceptions import FFmpegError
from .wrapper import FFmpegWrapper

__all__ = [
    "FFmpegWrapper",
    "FFmpegError",
]
