"""
Internal API routes for worker coordination.

These endpoints are for internal use only (backend → workers).
They should be protected from external access via authentication or network rules.
"""
import logging
import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.workers.audio_worker import process_audio_separation
from backend.workers.lyrics_worker import process_lyrics_transcription
from backend.workers.screens_worker import generate_screens


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal", tags=["internal"])


class WorkerRequest(BaseModel):
    """Request to trigger a worker."""
    job_id: str


class WorkerResponse(BaseModel):
    """Response from worker trigger."""
    status: str
    job_id: str
    message: str


@router.post("/workers/audio", response_model=WorkerResponse)
async def trigger_audio_worker(
    request: WorkerRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger audio separation worker for a job.
    
    This endpoint is called internally after job creation to start
    the audio processing track (parallel with lyrics processing).
    
    The worker runs in the background and updates job state as it progresses.
    """
    job_id = request.job_id
    logger.info(f"Triggering audio worker for job {job_id}")
    
    # Add task to background tasks
    # This allows the HTTP response to return immediately
    # while the worker continues processing
    background_tasks.add_task(process_audio_separation, job_id)
    
    return WorkerResponse(
        status="started",
        job_id=job_id,
        message="Audio separation worker started"
    )


@router.post("/workers/lyrics", response_model=WorkerResponse)
async def trigger_lyrics_worker(
    request: WorkerRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger lyrics transcription worker for a job.
    
    This endpoint is called internally after job creation to start
    the lyrics processing track (parallel with audio processing).
    
    The worker runs in the background and updates job state as it progresses.
    """
    job_id = request.job_id
    logger.info(f"Triggering lyrics worker for job {job_id}")
    
    # Add task to background tasks
    background_tasks.add_task(process_lyrics_transcription, job_id)
    
    return WorkerResponse(
        status="started",
        job_id=job_id,
        message="Lyrics transcription worker started"
    )


@router.post("/workers/screens", response_model=WorkerResponse)
async def trigger_screens_worker(
    request: WorkerRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger title/end screen generation worker.
    
    This is called automatically when both audio and lyrics are complete.
    """
    job_id = request.job_id
    logger.info(f"Triggering screens worker for job {job_id}")
    
    # Add task to background tasks
    background_tasks.add_task(generate_screens, job_id)
    
    return WorkerResponse(
        status="started",
        job_id=job_id,
        message="Screens generation worker started"
    )


@router.get("/health")
async def internal_health():
    """
    Internal health check endpoint.
    
    Used to verify the internal API is responsive.
    """
    return {"status": "healthy", "service": "karaoke-backend-internal"}

