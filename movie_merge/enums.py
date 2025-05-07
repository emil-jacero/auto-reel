"""Enumerations for video and audio codecs."""

from enum import Enum
from typing import Dict, List

from .constants import GPU_PRESET_MAP


class VideoTune(Enum):
    """Tune options for encoding."""

    FILM = "film"
    ANIMATION = "animation"
    GRAIN = "grain"
    PSNR = "psnr"
    SSIM = "ssim"
    FAST_DECODE = "fastdecode"
    ZERO_LATENCY = "zerolatency"


class VideoCodec(Enum):
    """Video codec options."""

    H264 = "h264"
    H265 = "hevc"
    VP9 = "vp9"
    AV1 = "av1"
    H264_NVENC = "h264_nvenc"
    H265_NVENC = "hevc_nvenc"

    @classmethod
    def get_gpu_codecs(cls) -> List["VideoCodec"]:
        """Get list of GPU-accelerated codecs."""
        return [cls.H264_NVENC, cls.H265_NVENC]

    @property
    def is_gpu_codec(self) -> bool:
        """Check if this codec supports GPU acceleration."""
        return self in self.get_gpu_codecs()

    def get_encoding_options(
        self, quality: int = 20, preset: str = "medium", tune: VideoTune = None
    ) -> Dict[str, str]:
        """
        Get encoding options for this codec.

        Args:
            quality: Quality level (CRF or QP)
            preset: Encoding speed
            tune: Tune options for NVENC

        Returns:
            Dictionary of encoding options
        """
        if self.is_gpu_codec:
            preset = GPU_PRESET_MAP.get(preset, "p4")  # fallback to "p4" if not found
            rc = "vbr_hq"  # Recommended rate control for quality-based encoding
            return {
                "preset": preset,
                "rc": rc,
                "cq": str(quality),
                "tune": tune.value if tune else None,
            }
        else:
            return {
                "preset": preset,
                "crf": str(quality),  # Use quality parameter directly for CRF
                "tune": tune.value if tune else None,
            }


class AudioCodec(Enum):
    """Audio codec options."""

    AAC = "aac"
    MP3 = "mp3"
    OPUS = "opus"
    VORBIS = "vorbis"

    def get_encoding_options(self, bitrate: str = "192k") -> Dict[str, str]:
        """Get PyAV encoding options for this codec."""
        return {"b:a": bitrate}
