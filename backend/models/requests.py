"""
API request models.
"""
from typing import Optional
from pydantic import BaseModel, HttpUrl


class URLSubmissionRequest(BaseModel):
    """Request to submit a job from a URL (YouTube, etc.)."""
    url: HttpUrl


class UploadSubmissionRequest(BaseModel):
    """Request to submit a job from an uploaded file."""
    artist: str
    title: str

