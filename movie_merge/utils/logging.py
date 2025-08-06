"""Enhanced logging configuration with contextual information for parallel processing."""

# movie_merge/utils/logging.py
import logging
import sys
import threading
from contextvars import ContextVar
from typing import Optional, Union

# Context variables for tracking processing context
movie_context: ContextVar[Optional[str]] = ContextVar("movie_context", default=None)
clip_context: ContextVar[Optional[str]] = ContextVar("clip_context", default=None)
thread_context: ContextVar[Optional[str]] = ContextVar("thread_context", default=None)


class ContextualColorFormatter(logging.Formatter):
    """Formatter adding colors and contextual information to log output."""

    COLORS = {
        "DEBUG": "\033[0;36m",  # Cyan
        "INFO": "\033[0;32m",  # Green
        "WARNING": "\033[0;33m",  # Yellow
        "ERROR": "\033[0;31m",  # Red
        "CRITICAL": "\033[0;35m",  # Magenta
    }
    RESET = "\033[0m"

    # Context colors
    MOVIE_COLOR = "\033[1;34m"  # Bold Blue
    CLIP_COLOR = "\033[0;37m"  # White
    THREAD_COLOR = "\033[0;90m"  # Dark Gray

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and context."""
        # Add color to level name
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}" f"{record.levelname:8}" f"{self.RESET}"
            )

        # Build context string
        context_parts = []

        # Add movie context
        movie = movie_context.get()
        if movie:
            context_parts.append(f"{self.MOVIE_COLOR}🎬 {movie}{self.RESET}")

        # Add clip context
        clip = clip_context.get()
        if clip:
            context_parts.append(f"{self.CLIP_COLOR}📹 {clip}{self.RESET}")

        # Add thread context for parallel processing
        thread = thread_context.get()
        if thread:
            context_parts.append(f"{self.THREAD_COLOR}⚙️ {thread}{self.RESET}")

        # Add context to record if any exists
        if context_parts:
            context_str = " ".join(context_parts)
            # Inject context into the record
            original_msg = record.getMessage()
            record.msg = f"[{context_str}] {original_msg}"
            record.args = ()  # Clear args since we've already formatted the message

        return super().format(record)


def configure_logging(level: Union[str, int] = logging.INFO) -> None:
    """
    Configure root logger with colored output to stdout.
    Should be called once from main.py

    Args:
        level: Logging level
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter = ContextualColorFormatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Add formatter to handler
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Set PIL logging level to WARNING to suppress debug messages
    logging.getLogger("PIL").setLevel(logging.WARNING)

    # Also suppress PngImagePlugin debug messages
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)


def set_movie_context(movie_name: str) -> None:
    """Set the current movie context for logging."""
    movie_context.set(movie_name)


def set_clip_context(clip_name: str) -> None:
    """Set the current clip context for logging."""
    clip_context.set(clip_name)


def set_thread_context(thread_name: str) -> None:
    """Set the current thread context for logging."""
    thread_context.set(thread_name)


def clear_movie_context() -> None:
    """Clear the movie context."""
    movie_context.set(None)


def clear_clip_context() -> None:
    """Clear the clip context."""
    clip_context.set(None)


def clear_thread_context() -> None:
    """Clear the thread context."""
    thread_context.set(None)


def clear_all_context() -> None:
    """Clear all logging contexts."""
    movie_context.set(None)
    clip_context.set(None)
    thread_context.set(None)


class LoggingContext:
    """Context manager for setting logging context."""

    def __init__(
        self, movie: Optional[str] = None, clip: Optional[str] = None, thread: Optional[str] = None
    ):
        self.movie = movie
        self.clip = clip
        self.thread = thread
        self.previous_movie: Optional[str] = None
        self.previous_clip: Optional[str] = None
        self.previous_thread: Optional[str] = None

    def __enter__(self) -> "LoggingContext":
        # Store previous contexts
        self.previous_movie = movie_context.get()
        self.previous_clip = clip_context.get()
        self.previous_thread = thread_context.get()

        # Set new contexts
        if self.movie is not None:
            movie_context.set(self.movie)
        if self.clip is not None:
            clip_context.set(self.clip)
        if self.thread is not None:
            thread_context.set(self.thread)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Restore previous contexts
        movie_context.set(self.previous_movie)
        clip_context.set(self.previous_clip)
        thread_context.set(self.previous_thread)


def log_exception(logger: logging.Logger, exc: Exception, context: str = "") -> None:
    """Log an exception with context."""
    error_msg = str(exc)
    if context:
        error_msg = f"{context}: {error_msg}"

    logger.error(error_msg)
    if logger.isEnabledFor(logging.DEBUG):
        import traceback

        logger.debug("Traceback:\n%s", "".join(traceback.format_tb(exc.__traceback__)))
