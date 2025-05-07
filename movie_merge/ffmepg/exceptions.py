"""Custom exceptions for FFmpeg-related errors."""


class FFmpegError(Exception):
    """Base exception for FFmpeg-related errors."""

    pass


class FFprobeError(FFmpegError):
    """Exception raised for FFprobe errors."""

    pass
