"""
Job data models for karaoke generation.

This module defines the complete state machine for karaoke generation jobs,
mirroring the 8-stage CLI workflow with human-in-the-loop interaction points.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class JobStatus(str, Enum):
    """
    Job status enumeration - Complete state machine.
    
    The workflow has 8 main stages with 2 human interaction points:
    1. Input & Setup
    2. Parallel Processing (audio + lyrics)
    3. Title/End Screen Generation
    4. Countdown Padding Synchronization
    5. Human Review (BLOCKING)
    6. Instrumental Selection (BLOCKING)
    7. Video Finalization
    8. Distribution
    """
    # Initial states
    PENDING = "pending"                           # Job created, queued for processing
    DOWNLOADING = "downloading"                   # Downloading from URL or processing upload
    
    # Stage 2a: Audio separation (parallel track 1)
    SEPARATING_STAGE1 = "separating_stage1"      # Clean instrumental separation (Modal API)
    SEPARATING_STAGE2 = "separating_stage2"      # Backing vocals separation (Modal API)
    AUDIO_COMPLETE = "audio_complete"            # All audio stems ready
    
    # Stage 2b: Lyrics processing (parallel track 2)
    TRANSCRIBING = "transcribing"                # AudioShake API transcription
    CORRECTING = "correcting"                     # Automatic lyrics correction
    LYRICS_COMPLETE = "lyrics_complete"           # Corrections JSON ready
    
    # Stage 3: Title/End screens
    GENERATING_SCREENS = "generating_screens"     # Creating title and end screen videos
    
    # Stage 4: Countdown padding (automatic)
    APPLYING_PADDING = "applying_padding"         # Synchronizing countdown padding
    
    # Stage 5: Human review (BLOCKING)
    AWAITING_REVIEW = "awaiting_review"          # ⚠️ WAITING FOR USER - lyrics review needed
    IN_REVIEW = "in_review"                      # User is actively reviewing lyrics
    REVIEW_COMPLETE = "review_complete"          # User submitted corrected lyrics
    
    # Stage 6: Instrumental selection (BLOCKING)
    AWAITING_INSTRUMENTAL_SELECTION = "awaiting_instrumental_selection"  # ⚠️ WAITING FOR USER
    INSTRUMENTAL_SELECTED = "instrumental_selected"  # User made selection
    
    # Stage 7: Video generation and finalization
    GENERATING_VIDEO = "generating_video"        # Creating initial karaoke video
    ENCODING = "encoding"                        # Multi-format video encoding (Cloud Build)
    PACKAGING = "packaging"                      # CDG/TXT ZIP generation
    
    # Stage 8: Distribution (optional)
    UPLOADING = "uploading"                      # YouTube/Dropbox upload
    NOTIFYING = "notifying"                      # Discord/Email notifications
    
    # Terminal states
    COMPLETE = "complete"                        # All processing finished successfully
    FAILED = "failed"                           # Unrecoverable error occurred
    CANCELLED = "cancelled"                      # User cancelled the job
    
    # Legacy compatibility (will be removed)
    QUEUED = "queued"                           # Deprecated: use PENDING
    PROCESSING = "processing"                    # Deprecated: use specific states
    READY_FOR_FINALIZATION = "ready_for_finalization"  # Deprecated
    FINALIZING = "finalizing"                    # Deprecated: use ENCODING/PACKAGING
    ERROR = "error"                             # Deprecated: use FAILED


# Valid state transitions
STATE_TRANSITIONS = {
    JobStatus.PENDING: [JobStatus.DOWNLOADING, JobStatus.FAILED, JobStatus.CANCELLED],
    JobStatus.DOWNLOADING: [JobStatus.SEPARATING_STAGE1, JobStatus.TRANSCRIBING, JobStatus.FAILED],
    
    # Audio separation flow
    JobStatus.SEPARATING_STAGE1: [JobStatus.SEPARATING_STAGE2, JobStatus.FAILED],
    JobStatus.SEPARATING_STAGE2: [JobStatus.AUDIO_COMPLETE, JobStatus.FAILED],
    JobStatus.AUDIO_COMPLETE: [JobStatus.GENERATING_SCREENS, JobStatus.FAILED],
    
    # Lyrics flow
    JobStatus.TRANSCRIBING: [JobStatus.CORRECTING, JobStatus.FAILED],
    JobStatus.CORRECTING: [JobStatus.LYRICS_COMPLETE, JobStatus.FAILED],
    JobStatus.LYRICS_COMPLETE: [JobStatus.GENERATING_SCREENS, JobStatus.FAILED],
    
    # Post-parallel processing
    JobStatus.GENERATING_SCREENS: [JobStatus.APPLYING_PADDING, JobStatus.AWAITING_REVIEW, JobStatus.FAILED],
    JobStatus.APPLYING_PADDING: [JobStatus.AWAITING_REVIEW, JobStatus.FAILED],
    
    # Human review flow
    JobStatus.AWAITING_REVIEW: [JobStatus.IN_REVIEW, JobStatus.FAILED, JobStatus.CANCELLED],
    JobStatus.IN_REVIEW: [JobStatus.REVIEW_COMPLETE, JobStatus.AWAITING_REVIEW, JobStatus.FAILED],
    JobStatus.REVIEW_COMPLETE: [JobStatus.AWAITING_INSTRUMENTAL_SELECTION, JobStatus.FAILED],
    
    # Instrumental selection flow
    JobStatus.AWAITING_INSTRUMENTAL_SELECTION: [JobStatus.INSTRUMENTAL_SELECTED, JobStatus.FAILED, JobStatus.CANCELLED],
    JobStatus.INSTRUMENTAL_SELECTED: [JobStatus.GENERATING_VIDEO, JobStatus.FAILED],
    
    # Video generation flow
    JobStatus.GENERATING_VIDEO: [JobStatus.ENCODING, JobStatus.FAILED],
    JobStatus.ENCODING: [JobStatus.PACKAGING, JobStatus.COMPLETE, JobStatus.FAILED],
    JobStatus.PACKAGING: [JobStatus.UPLOADING, JobStatus.COMPLETE, JobStatus.FAILED],
    
    # Distribution flow
    JobStatus.UPLOADING: [JobStatus.NOTIFYING, JobStatus.COMPLETE, JobStatus.FAILED],
    JobStatus.NOTIFYING: [JobStatus.COMPLETE, JobStatus.FAILED],
    
    # Terminal states have no transitions
    JobStatus.COMPLETE: [],
    JobStatus.FAILED: [],
    JobStatus.CANCELLED: [],
    
    # Legacy states (for backward compatibility)
    JobStatus.QUEUED: [JobStatus.PENDING],
    JobStatus.PROCESSING: [JobStatus.SEPARATING_STAGE1, JobStatus.TRANSCRIBING],
    JobStatus.READY_FOR_FINALIZATION: [JobStatus.GENERATING_VIDEO],
    JobStatus.FINALIZING: [JobStatus.ENCODING],
    JobStatus.ERROR: [JobStatus.FAILED],
}


class TimelineEvent(BaseModel):
    """Timeline event for job progress tracking."""
    status: str
    timestamp: str
    progress: Optional[int] = None
    message: Optional[str] = None


class Job(BaseModel):
    """
    Complete job data model.
    
    Tracks the full lifecycle of a karaoke generation job from submission
    through all 8 stages to completion or failure.
    """
    job_id: str
    status: JobStatus
    progress: int = 0  # 0-100 percentage for UI display
    created_at: datetime
    updated_at: datetime
    
    # Input data
    url: Optional[str] = None                    # YouTube URL (if provided)
    artist: Optional[str] = None
    title: Optional[str] = None
    filename: Optional[str] = None               # Original uploaded filename
    input_media_gcs_path: Optional[str] = None   # GCS path to uploaded file
    
    # User preferences
    enable_cdg: bool = True                      # Generate CDG+MP3 package
    enable_txt: bool = True                      # Generate TXT+MP3 package
    enable_youtube_upload: bool = False          # Upload to YouTube
    youtube_description: Optional[str] = None    # YouTube video description
    webhook_url: Optional[str] = None            # Webhook for notifications
    user_email: Optional[str] = None             # Email for notifications
    
    # Processing state
    track_output_dir: Optional[str] = None       # Local output directory (temp)
    audio_hash: Optional[str] = None             # Hash for deduplication
    
    # State-specific data (JSON field for stage-specific metadata)
    state_data: Dict[str, Any] = Field(default_factory=dict)
    """
    Stage-specific metadata. Examples:
    - audio_complete: {"stems": {"clean": "gs://...", "backing": "gs://..."}}
    - lyrics_complete: {"corrections_url": "gs://...", "audio_url": "gs://..."}
    - review_complete: {"corrected_lyrics": {...}}
    - instrumental_selected: {"selection": "clean" | "with_backing"}
    - encoding: {"build_id": "...", "progress": 45}
    """
    
    # Timeline tracking
    timeline: List[TimelineEvent] = Field(default_factory=list)
    
    # File URLs (GCS storage)
    file_urls: Dict[str, str] = Field(default_factory=dict)
    """
    File storage URLs. Structure:
    {
        "input": "gs://bucket/jobs/{job_id}/input.flac",
        "stems": {
            "instrumental_clean": "gs://...",
            "instrumental_with_backing": "gs://...",
            "vocals": "gs://...",
            "backing_vocals": "gs://...",
            "lead_vocals": "gs://...",
            "bass": "gs://...",
            "drums": "gs://...",
            "guitar": "gs://...",
            "piano": "gs://...",
            "other": "gs://..."
        },
        "lyrics": {
            "corrections": "gs://bucket/jobs/{job_id}/lyrics/corrections.json",
            "audio": "gs://bucket/jobs/{job_id}/lyrics/audio.flac",
            "lrc": "gs://...",
            "ass": "gs://..."
        },
        "screens": {
            "title": "gs://bucket/jobs/{job_id}/screens/title.mov",
            "end": "gs://bucket/jobs/{job_id}/screens/end.mov"
        },
        "videos": {
            "with_vocals": "gs://bucket/jobs/{job_id}/videos/with_vocals.mkv"
        },
        "finals": {
            "lossless_4k_mp4": "gs://...",
            "lossless_4k_mkv": "gs://...",
            "lossy_4k_mp4": "gs://...",
            "lossy_720p_mp4": "gs://..."
        },
        "packages": {
            "cdg_zip": "gs://...",
            "txt_zip": "gs://..."
        },
        "youtube": {
            "url": "https://youtube.com/watch?v=...",
            "video_id": "..."
        }
    }
    """
    
    # Results (for backward compatibility, will be deprecated)
    output_files: Dict[str, str] = Field(default_factory=dict)
    download_urls: Dict[str, str] = Field(default_factory=dict)
    
    # Error handling
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None  # Structured error information
    retry_count: int = 0                            # Number of retry attempts
    
    # Worker tracking
    worker_ids: Dict[str, str] = Field(default_factory=dict)
    """
    IDs of background workers/jobs:
    {
        "audio_worker": "cloud-run-request-id",
        "lyrics_worker": "cloud-run-request-id",
        "video_encoder": "cloud-build-id",
        "distribution": "cloud-run-request-id"
    }
    """
    
    @validator('status')
    def validate_status_transition(cls, v, values):
        """Validate state transitions are legal."""
        # Skip validation during initial creation
        if 'status' not in values:
            return v
        
        old_status = values.get('status')
        if old_status and old_status != v:
            valid_transitions = STATE_TRANSITIONS.get(old_status, [])
            if v not in valid_transitions:
                raise ValueError(
                    f"Invalid state transition from {old_status} to {v}. "
                    f"Valid transitions: {valid_transitions}"
                )
        return v
    
    class Config:
        use_enum_values = True


class JobCreate(BaseModel):
    """
    Job creation request.
    
    Either `url` OR file upload is required (file upload handled separately).
    Artist and title are optional - will be auto-detected from YouTube if not provided.
    """
    url: Optional[str] = None
    artist: Optional[str] = None
    title: Optional[str] = None
    
    # Optional preferences
    enable_cdg: bool = True
    enable_txt: bool = True
    enable_youtube_upload: bool = False
    youtube_description: Optional[str] = None
    webhook_url: Optional[str] = None
    user_email: Optional[str] = None
    
    @validator('url', 'artist', 'title')
    def validate_inputs(cls, v):
        """Validate string inputs are not empty."""
        if v is not None and isinstance(v, str) and not v.strip():
            raise ValueError("Field cannot be empty string")
        return v.strip() if isinstance(v, str) else v


class JobResponse(BaseModel):
    """Job response model."""
    status: str
    job_id: str
    message: str

