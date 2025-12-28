import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TranscriberConfig:
    """Configuration for transcription services."""

    audioshake_api_token: Optional[str] = None
    runpod_api_key: Optional[str] = None
    whisper_runpod_id: Optional[str] = None

    # Local Whisper configuration
    enable_local_whisper: bool = True  # Enabled by default as fallback
    local_whisper_model_size: str = "medium"  # tiny, base, small, medium, large
    local_whisper_device: Optional[str] = None  # None for auto-detect, or cpu/cuda/mps
    local_whisper_cache_dir: Optional[str] = None  # Custom model download location
    local_whisper_language: Optional[str] = None  # None for auto-detect


@dataclass
class LyricsConfig:
    """Configuration for lyrics services."""

    genius_api_token: Optional[str] = None
    rapidapi_key: Optional[str] = None
    spotify_cookie: Optional[str] = None
    lyrics_file: Optional[str] = None

@dataclass
class OutputConfig:
    """Configuration for output generation."""

    output_styles_json: str
    default_max_line_length: int = 36
    styles: Dict[str, Any] = field(default_factory=dict)
    output_dir: Optional[str] = os.getcwd()
    cache_dir: str = os.getenv(
        "LYRICS_TRANSCRIBER_CACHE_DIR",
        os.path.join(os.path.expanduser("~"), "lyrics-transcriber-cache")
    )

    fetch_lyrics: bool = True
    run_transcription: bool = True
    run_correction: bool = True
    enable_review: bool = True

    generate_plain_text: bool = True
    generate_lrc: bool = True
    generate_cdg: bool = True
    render_video: bool = True
    video_resolution: str = "360p"
    subtitle_offset_ms: int = 0
    
    # Countdown feature for songs that start too quickly
    add_countdown: bool = True