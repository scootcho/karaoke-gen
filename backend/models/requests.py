"""
API request models for karaoke generation endpoints.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, HttpUrl, validator


class URLSubmissionRequest(BaseModel):
    """Request to submit a job from a URL (YouTube, etc.)."""
    url: HttpUrl
    artist: Optional[str] = None  # Auto-detected if not provided
    title: Optional[str] = None   # Auto-detected if not provided
    
    # Optional preferences
    enable_cdg: bool = True
    enable_txt: bool = True
    enable_youtube_upload: bool = False
    youtube_description: Optional[str] = None
    webhook_url: Optional[str] = None
    user_email: Optional[str] = None


class UploadSubmissionRequest(BaseModel):
    """Request to submit a job from an uploaded file."""
    artist: str
    title: str
    
    # Optional preferences
    enable_cdg: bool = True
    enable_txt: bool = True
    enable_youtube_upload: bool = False
    youtube_description: Optional[str] = None
    webhook_url: Optional[str] = None
    user_email: Optional[str] = None


class CorrectionsSubmission(BaseModel):
    """
    Request to submit corrected lyrics after human review.
    
    This is the critical human-in-the-loop interaction point.
    The corrections data comes from the lyrics-transcriber review interface.
    """
    corrections: Dict[str, Any]  # Full corrections JSON from frontend
    user_notes: Optional[str] = None  # Optional notes from reviewer
    
    @validator('corrections')
    def validate_corrections_format(cls, v):
        """Validate corrections has required fields."""
        required_fields = ['lines', 'metadata']
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Corrections must include '{field}' field")
        return v


class InstrumentalSelection(BaseModel):
    """
    Request to select instrumental audio option.
    
    This is the second critical human-in-the-loop interaction point.
    User chooses between clean instrumental or instrumental with backing vocals.
    """
    selection: str  # "clean" or "with_backing"
    
    @validator('selection')
    def validate_selection(cls, v):
        """Validate selection is a valid option."""
        valid_options = ['clean', 'with_backing']
        if v not in valid_options:
            raise ValueError(f"Selection must be one of: {valid_options}")
        return v


class StartReviewRequest(BaseModel):
    """Request to mark job as in-review (user opened interface)."""
    pass  # No body needed, just triggers state transition


class CancelJobRequest(BaseModel):
    """Request to cancel a job."""
    reason: Optional[str] = None


class RetryJobRequest(BaseModel):
    """Request to retry a failed job."""
    from_stage: Optional[str] = None  # Optional: restart from specific stage

