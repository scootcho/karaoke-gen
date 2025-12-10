"""
Internal API routes for worker coordination.

These endpoints are for internal use only (backend → workers).
They are protected by admin authentication.
"""
import logging
import asyncio
from typing import Tuple
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel

from backend.workers.audio_worker import process_audio_separation
from backend.workers.lyrics_worker import process_lyrics_transcription
from backend.workers.screens_worker import generate_screens
from backend.workers.video_worker import generate_video
from backend.workers.render_video_worker import process_render_video
from backend.api.dependencies import require_admin
from backend.services.auth_service import UserType


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
    background_tasks: BackgroundTasks,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
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
    background_tasks: BackgroundTasks,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
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
    background_tasks: BackgroundTasks,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
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


@router.post("/workers/video", response_model=WorkerResponse)
async def trigger_video_worker(
    request: WorkerRequest,
    background_tasks: BackgroundTasks,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
):
    """
    Trigger final video generation and encoding worker.
    
    This is called after user selects their preferred instrumental.
    This is the longest-running stage (15-20 minutes).
    """
    job_id = request.job_id
    logger.info(f"Triggering video worker for job {job_id}")
    
    # Add task to background tasks
    background_tasks.add_task(generate_video, job_id)
    
    return WorkerResponse(
        status="started",
        job_id=job_id,
        message="Video generation worker started"
    )


@router.post("/workers/render-video", response_model=WorkerResponse)
async def trigger_render_video_worker(
    request: WorkerRequest,
    background_tasks: BackgroundTasks,
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
):
    """
    Trigger render video worker (post-review).
    
    This is called after human review is complete.
    Uses OutputGenerator from LyricsTranscriber to generate the karaoke video
    with the corrected lyrics.
    
    Output: with_vocals.mkv in GCS
    Next state: AWAITING_INSTRUMENTAL_SELECTION
    """
    job_id = request.job_id
    logger.info(f"Triggering render-video worker for job {job_id}")
    
    # Add task to background tasks
    background_tasks.add_task(process_render_video, job_id)
    
    return WorkerResponse(
        status="started",
        job_id=job_id,
        message="Render video worker started (post-review)"
    )


@router.get("/health")
async def internal_health(
    auth_data: Tuple[str, UserType, int] = Depends(require_admin)
):
    """
    Internal health check endpoint.
    
    Used to verify the internal API is responsive.
    Requires admin authentication.
    """
    return {"status": "healthy", "service": "karaoke-backend-internal"}

