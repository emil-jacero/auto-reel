"""Simple stdout logging configuration."""

# movie_merge/utils/logging.py
import logging
import sys
from typing import Union


class ColorFormatter(logging.Formatter):
    """Formatter adding colors to log output."""

    COLORS = {
        "DEBUG": "\033[0;36m",  # Cyan
        "INFO": "\033[0;32m",  # Green
        "WARNING": "\033[0;33m",  # Yellow
        "ERROR": "\033[0;31m",  # Red
        "CRITICAL": "\033[0;35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}" f"{record.levelname:8}" f"{self.RESET}"
            )

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
    formatter = ColorFormatter(
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


def log_exception(logger: logging.Logger, exc: Exception, context: str = "") -> None:
    """Log an exception with context."""
    error_msg = str(exc)
    if context:
        error_msg = f"{context}: {error_msg}"

    logger.error(error_msg)
    if logger.isEnabledFor(logging.DEBUG):
        import traceback

        logger.debug("Traceback:\n%s", "".join(traceback.format_tb(exc.__traceback__)))
