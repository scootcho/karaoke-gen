"""
Instrumental Review Module - Shared core for both local and remote CLI.

This module provides audio analysis and editing functionality for instrumental
selection in karaoke generation. It's designed to be:
- Pure Python with no cloud dependencies (GCS, etc.)
- Reusable by both local CLI (karaoke-gen) and remote backend (Cloud Run)
- Easy to test without mocking cloud services

Classes:
    AudioAnalyzer: Analyzes backing vocals audio for audible content
    AudioEditor: Creates custom instrumentals by muting regions
    WaveformGenerator: Generates waveform visualization images
    InstrumentalReviewServer: Local HTTP server for browser-based review

Models:
    AnalysisResult: Result of audio analysis
    AudibleSegment: A detected segment of audible content
    MuteRegion: A region to mute in the backing vocals
    RecommendedSelection: Enum of selection recommendations
"""

from .models import (
    AnalysisResult,
    AudibleSegment,
    MuteRegion,
    RecommendedSelection,
)
from .analyzer import AudioAnalyzer
from .editor import AudioEditor
from .waveform import WaveformGenerator
from .server import InstrumentalReviewServer

__all__ = [
    # Models
    "AnalysisResult",
    "AudibleSegment",
    "MuteRegion",
    "RecommendedSelection",
    # Classes
    "AudioAnalyzer",
    "AudioEditor",
    "WaveformGenerator",
    "InstrumentalReviewServer",
]
