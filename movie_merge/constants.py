"""Constants used in the movie_merge package."""

UNSUPPORTED_VIDEO_EXTENSIONS = [".wmv", ".mts"]  # Windows Media Video  # AVCHD Video

GPU_PRESET_MAP = {
    "fastest": "p1",
    "faster": "p2",
    "fast": "p3",
    "medium": "p4",
    "slow": "p5",
    "slower": "p6",
    "slowet": "p7",
}

VIDEO_EXTENSIONS = {
    ".mp4",  # MPEG-4 Part 14
    ".mkv",  # Matroska Video
    ".avi",  # Audio Video Interleave
    ".mov",  # QuickTime Movie
    ".wmv",  # Windows Media Video
    ".flv",  # Flash Video
    ".mts",  # AVCHD Video
    ".m2ts",  # Blu-ray BDAV Video
    ".ts",  # MPEG Transport Stream
    ".webm",  # WebM Video
    ".m4v",  # iTunes Video
    ".3gp",  # 3GPP Multimedia
    ".mpg",  # MPEG-1 Systems/Video
    ".mpeg",  # MPEG-1 Systems/Video
    ".vob",  # DVD Video Object
    ".asf",  # Advanced Systems Format
    ".rm",  # RealMedia
    ".rmvb",  # RealMedia Variable Bitrate
    ".m2v",  # MPEG-2 Video
    ".ogv",  # Ogg Video
}

IGNORE_FILE = ".mmignore"

METADATA_FILE = "reel.yaml"
