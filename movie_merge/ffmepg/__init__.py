""" FFmpeg wrapper module. """

from .wrapper import FFmpegWrapper
from .exceptions import FFmpegError

__all__ = [
    "FFmpegWrapper",
    "FFmpegError",
]
