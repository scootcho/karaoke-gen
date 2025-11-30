"""
Job data models for karaoke generation.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    READY_FOR_FINALIZATION = "ready_for_finalization"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


class TimelineEvent(BaseModel):
    """Timeline event for job progress tracking."""
    status: str
    timestamp: str
    progress: Optional[int] = None
    message: Optional[str] = None


class Job(BaseModel):
    """Job data model."""
    job_id: str
    status: JobStatus
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    
    # Input
    url: Optional[str] = None
    artist: Optional[str] = None
    title: Optional[str] = None
    filename: Optional[str] = None
    
    # Processing state
    track_output_dir: Optional[str] = None
    audio_hash: Optional[str] = None
    
    # Timeline tracking
    timeline: List[TimelineEvent] = Field(default_factory=list)
    
    # Results
    output_files: Dict[str, str] = Field(default_factory=dict)
    download_urls: Dict[str, str] = Field(default_factory=dict)
    
    # Error handling
    error_message: Optional[str] = None
    
    class Config:
        use_enum_values = True


class JobCreate(BaseModel):
    """Job creation request."""
    url: Optional[str] = None
    artist: Optional[str] = None
    title: Optional[str] = None


class JobResponse(BaseModel):
    """Job response model."""
    status: str
    job_id: str
    message: str

