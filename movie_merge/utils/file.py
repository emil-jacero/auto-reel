import logging
import os
from pathlib import Path
from typing import List, Union

from movie_merge.constants import IGNORE_FILE, VIDEO_EXTENSIONS

from .exceptions import FileError

logger = logging.getLogger(__name__)


def should_ignore_directory(directory: Path) -> bool:
    """
    Check if a directory should be ignored based on presence of .mmignore file.

    Args:
        directory: Directory to check

    Returns:
        True if directory should be ignored
    """
    ignore_file = directory / IGNORE_FILE
    return ignore_file.exists()


def validate_path(
    path: Union[str, Path],
    must_exist: bool = True,
    create_dir: bool = False,
    is_file: bool = False,
    is_dir: bool = False,
    writable: bool = False,
) -> Path:
    """
    Validate a path with configurable requirements.

    Args:
        path: Path to validate (string or Path object)
        must_exist: If True, path must already exist
        create_dir: If True and path is a directory, create it if it doesn't exist
        is_file: If True, path must be a file
        is_dir: If True, path must be a directory
        writable: If True, path must be writable

    Returns:
        Validated Path object

    Raises:
        FileError: If path doesn't meet specified requirements
    """
    try:
        path_obj = Path(path)

        # Handle directory creation first if requested
        if create_dir and not path_obj.exists() and (is_dir or not is_file):
            try:
                path_obj.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise FileError(f"Failed to create directory {path}: {str(e)}")

        # Existence check
        if must_exist and not path_obj.exists():
            raise FileError(f"Path does not exist: {path}")

        # File/Directory type validation
        if path_obj.exists():
            if is_file and not path_obj.is_file():
                raise FileError(f"Path is not a file: {path}")
            if is_dir and not path_obj.is_dir():
                raise FileError(f"Path is not a directory: {path}")

        # Write permission check
        if writable:
            if path_obj.exists():
                if not os.access(path_obj, os.W_OK):
                    raise FileError(f"Path is not writable: {path}")
            else:
                # Check if parent directory is writable
                parent = path_obj.parent
                if not os.access(parent, os.W_OK):
                    raise FileError(f"Parent directory is not writable: {parent}")

        return path_obj

    except Exception as e:
        if isinstance(e, FileError):
            raise
        raise FileError(f"Path validation failed for {path}: {str(e)}")


def get_file_extension(path: Union[str, Path]) -> str:
    """
    Get lowercase file extension including dot.

    Args:
        path: File path

    Returns:
        Lowercase extension with dot
    """
    return Path(path).suffix.lower()


def is_video_file(path: Union[str, Path]) -> bool:
    """
    Check if file has video extension.

    Args:
        path: File path

    Returns:
        True if file has video extension
    """
    return get_file_extension(path) in VIDEO_EXTENSIONS


def list_video_files(directory: Union[str, Path], recursive: bool = False) -> List[Path]:
    """
    List all video files in directory, excluding files in 'original' subdirectories.

    Args:
        directory: Directory to search
        recursive: Whether to search subdirectories

    Returns:
        List of paths to video files

    Raises:
        FileError: If directory is invalid or inaccessible
    """
    directory = validate_path(directory, must_exist=True, is_dir=True)
    video_files = []

    try:
        if recursive:
            for root, dirs, files in os.walk(directory):
                # Skip 'original' directories
                if "original" in dirs:
                    dirs.remove("original")

                for file in files:
                    path = Path(root) / file
                    if is_video_file(path):
                        video_files.append(path)
        else:
            video_files = [
                f
                for f in directory.iterdir()
                if f.is_file() and is_video_file(f) and f.parent.name != "original"
            ]

        return sorted(video_files)
    except Exception as e:
        raise FileError(f"Failed to list video files in {directory}: {str(e)}") from e


def safe_filename(filename: str) -> str:
    """
    Convert string to safe filename while preserving date prefixes and special characters.
    Only removes/replaces characters that are problematic for filesystems.
    Preserves date format YYYY-MM-DD if present at start of filename.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename that is safe for all operating systems
    """
    # Check if filename starts with a date pattern (YYYY-MM-DD)
    date_prefix = None
    date_pattern = r"^(\d{4}-\d{2}-\d{2})"
    import re

    date_match = re.match(date_pattern, filename)
    if date_match:
        date_prefix = date_match.group(1)
        # Remove the date prefix for processing the rest of the filename
        filename = filename[len(date_prefix) :].lstrip(" -")

    # Replace specific illegal characters for Windows/Linux
    illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
    filename = re.sub(illegal_chars, "", filename)

    # Replace spaces and consecutive dashes with single underscore
    filename = re.sub(r"[\s\-]+", "_", filename)

    # Remove Windows reserved names (case-insensitive)
    if re.match(r"^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\.|$)", filename.upper()):
        filename = f"_{filename}"

    # Ensure filename doesn't start/end with dots or spaces
    filename = filename.strip(". ")

    # Provide fallback for empty filename
    if not filename:
        filename = "unnamed_file"

    # Reconstruct filename with date prefix if it existed
    if date_prefix:
        filename = f"{date_prefix}_{filename}"

    return filename


def format_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string (e.g., "1.23 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"


def copy_with_progress(
    src: Path, dst: Path, chunk_size: int = 1024 * 1024, overwrite: bool = False
) -> None:
    """
    Copy file with progress reporting.

    Args:
        src: Source path
        dst: Destination path
        chunk_size: Size of chunks to copy in bytes
        overwrite: Whether to overwrite existing destination file

    Raises:
        FileError: If copy operation fails
    """
    try:
        # Validate source and destination
        src = validate_path(src, must_exist=True, is_file=True)
        dst_dir = validate_path(dst.parent, must_exist=False, create_dir=True, writable=True)

        # Check if destination exists
        if dst.exists() and not overwrite:
            raise FileError(f"Destination file already exists: {dst}")

        total_size = os.path.getsize(src)
        copied = 0

        logger.info(f"Copying {src.name} to {dst} ({format_size(total_size)})")

        with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)
                progress = (copied / total_size) * 100
                logger.debug(
                    f"Progress: {progress:.1f}% ({format_size(copied)}/{format_size(total_size)})"
                )

        logger.info(f"Successfully copied {src.name} to {dst}")

    except Exception as e:
        # Clean up partial file if copy failed
        if dst.exists():
            try:
                dst.unlink()
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up partial file {dst}: {cleanup_error}")

        raise FileError(f"Failed to copy {src} to {dst}: {str(e)}") from e


def move_with_progress(src: Path, dst: Path, overwrite: bool = False) -> None:
    """
    Move file with progress reporting.

    Args:
        src: Source path
        dst: Destination path
        overwrite: Whether to overwrite existing destination file

    Raises:
        FileError: If move operation fails
    """
    try:
        # First try a simple move/rename operation
        try:
            if overwrite and dst.exists():
                dst.unlink()
            src.rename(dst)
            logger.info(f"Moved {src.name} to {dst}")
            return
        except OSError:
            # If simple move fails (e.g., across devices), fall back to copy and delete
            pass

        # Copy with progress
        copy_with_progress(src, dst, overwrite=overwrite)

        # Remove source file after successful copy
        try:
            src.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove source file {src} after move: {e}")

    except Exception as e:
        raise FileError(f"Failed to move {src} to {dst}: {str(e)}") from e


def verify_writeable_directory(path: Union[str, Path], create: bool = False) -> Path:
    """
    Verify a directory exists and is writeable.

    Args:
        path: Directory path
        create: Whether to create the directory if it doesn't exist

    Returns:
        Path object for verified directory

    Raises:
        FileError: If directory is invalid or not writeable
    """
    return validate_path(path, must_exist=not create, create_dir=create, is_dir=True, writable=True)
