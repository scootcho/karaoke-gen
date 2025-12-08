"""
Job management routes.

Handles job lifecycle endpoints including:
- Job creation and submission
- Status polling
- Human-in-the-loop interactions (lyrics review, instrumental selection)
- Job deletion and cancellation
"""
import logging
import httpx
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any

from backend.models.job import Job, JobCreate, JobResponse, JobStatus
from backend.models.requests import (
    URLSubmissionRequest,
    CorrectionsSubmission,
    InstrumentalSelection,
    StartReviewRequest,
    CancelJobRequest
)
from backend.services.job_manager import JobManager
from backend.services.worker_service import get_worker_service
from backend.config import get_settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Initialize services
job_manager = JobManager()
worker_service = get_worker_service()
settings = get_settings()


@router.post("", response_model=JobResponse)
async def create_job(
    request: URLSubmissionRequest,
    background_tasks: BackgroundTasks
) -> JobResponse:
    """
    Create a new karaoke generation job from a URL.
    
    This triggers the complete workflow:
    1. Job created in PENDING state
    2. Audio and lyrics workers triggered in parallel
    3. Both workers update job state as they progress
    4. When both complete, job transitions to AWAITING_REVIEW
    """
    try:
        # Create job with all preferences
        job_create = JobCreate(
            url=str(request.url),
            artist=request.artist,
            title=request.title,
            enable_cdg=request.enable_cdg,
            enable_txt=request.enable_txt,
            enable_youtube_upload=request.enable_youtube_upload,
            youtube_description=request.youtube_description,
            webhook_url=request.webhook_url,
            user_email=request.user_email
        )
        job = job_manager.create_job(job_create)
        
        # Trigger both workers in parallel using worker service
        # They run independently and coordinate via job state
        background_tasks.add_task(worker_service.trigger_audio_worker, job.job_id)
        background_tasks.add_task(worker_service.trigger_lyrics_worker, job.job_id)
        
        logger.info(f"Job {job.job_id} created, workers triggered")
        
        return JobResponse(
            status="success",
            job_id=job.job_id,
            message="Job created successfully. Processing started."
        )
    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Worker triggering is now handled by WorkerService
# See backend/services/worker_service.py


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str) -> Job:
    """Get job status and details."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # If job is complete, include download URLs
    if job.status == JobStatus.COMPLETE:
        job.download_urls = job_manager.get_output_urls(job_id)
    
    return job


@router.get("", response_model=List[Job])
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = 100
) -> List[Job]:
    """List jobs with optional status filter."""
    try:
        jobs = job_manager.list_jobs(status=status, limit=limit)
        return jobs
    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_job(job_id: str, delete_files: bool = True) -> dict:
    """Delete a job and optionally its output files."""
    try:
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_manager.delete_job(job_id, delete_files=delete_files)
        
        return {"status": "success", "message": f"Job {job_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Human-in-the-Loop Interaction Endpoints
# ============================================================================

@router.get("/{job_id}/review-data")
async def get_review_data(job_id: str) -> Dict[str, Any]:
    """
    Get data needed for lyrics review interface.
    
    Returns corrections JSON URL and audio URL.
    Frontend loads these to render the review UI.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.AWAITING_REVIEW, JobStatus.IN_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready for review (current status: {job.status})"
        )
    
    # Get URLs from file_urls
    corrections_url = job.file_urls.get('lyrics', {}).get('corrections')
    audio_url = job.file_urls.get('lyrics', {}).get('audio')
    
    if not corrections_url or not audio_url:
        raise HTTPException(
            status_code=500,
            detail="Review data not available"
        )
    
    # Generate signed URLs for direct access
    from backend.services.storage_service import StorageService
    storage = StorageService()
    
    return {
        "corrections_url": storage.generate_signed_url(corrections_url, expiration_minutes=120),
        "audio_url": storage.generate_signed_url(audio_url, expiration_minutes=120),
        "status": job.status,
        "artist": job.artist,
        "title": job.title
    }


@router.post("/{job_id}/start-review")
async def start_review(job_id: str, request: StartReviewRequest) -> dict:
    """
    Mark job as IN_REVIEW (user opened review interface).
    
    This helps track that the user is actively working on the review.
    """
    success = job_manager.transition_to_state(
        job_id=job_id,
        new_status=JobStatus.IN_REVIEW,
        message="User started reviewing lyrics"
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Cannot start review")
    
    return {"status": "success", "job_status": "in_review"}


@router.post("/{job_id}/corrections")
async def submit_corrections(
    job_id: str,
    submission: CorrectionsSubmission,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Save corrected lyrics during human review.
    
    This endpoint saves review progress but does NOT complete the review.
    Call POST /{job_id}/complete-review to finish and trigger video rendering.
    
    Can be called multiple times to save progress.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.AWAITING_REVIEW, JobStatus.IN_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Job not in review state (current status: {job.status})"
        )
    
    try:
        # Store corrected lyrics in state_data
        job_manager.update_state_data(job_id, 'corrected_lyrics', submission.corrections)
        if submission.user_notes:
            job_manager.update_state_data(job_id, 'review_notes', submission.user_notes)
        
        # Transition to IN_REVIEW if not already
        if job.status == JobStatus.AWAITING_REVIEW:
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.IN_REVIEW,
                message="User is reviewing lyrics"
            )
        
        # Save updated corrections to GCS for the render worker
        from backend.services.storage_service import StorageService
        storage = StorageService()
        
        corrections_gcs_path = f"jobs/{job_id}/lyrics/corrections_updated.json"
        storage.upload_json(corrections_gcs_path, submission.corrections)
        job_manager.update_file_url(job_id, 'lyrics', 'corrections_updated', corrections_gcs_path)
        
        logger.info(f"Job {job_id}: Corrections saved (review in progress)")
        
        return {
            "status": "success",
            "job_status": "in_review",
            "message": "Corrections saved. Call /complete-review when done."
        }
        
    except Exception as e:
        logger.error(f"Error saving corrections for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/complete-review")
async def complete_review(
    job_id: str,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Complete the human review and trigger video rendering.
    
    This is the FIRST critical human-in-the-loop completion point.
    After this:
    1. Job transitions to REVIEW_COMPLETE
    2. Render video worker is triggered
    3. Worker uses OutputGenerator to create with_vocals.mkv
    4. Job transitions to AWAITING_INSTRUMENTAL_SELECTION
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.AWAITING_REVIEW, JobStatus.IN_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=f"Job not in review state (current status: {job.status})"
        )
    
    try:
        # Transition to REVIEW_COMPLETE
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.REVIEW_COMPLETE,
            progress=70,
            message="Review complete, rendering video with corrected lyrics"
        )
        
        # Trigger render video worker
        background_tasks.add_task(worker_service.trigger_render_video_worker, job_id)
        
        logger.info(f"Job {job_id}: Review complete, triggering render video worker")
        
        return {
            "status": "success",
            "job_status": "review_complete",
            "message": "Review complete. Video rendering started."
        }
        
    except Exception as e:
        logger.error(f"Error completing review for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/instrumental-options")
async def get_instrumental_options(job_id: str) -> Dict[str, Any]:
    """
    Get instrumental audio options for user selection.
    
    Returns signed URLs for both options:
    1. Clean instrumental (no backing vocals)
    2. Instrumental with backing vocals
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.AWAITING_INSTRUMENTAL_SELECTION:
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready for instrumental selection (current status: {job.status})"
        )
    
    # Get stem URLs
    stems = job.file_urls.get('stems', {})
    clean_url = stems.get('instrumental_clean')
    backing_url = stems.get('instrumental_with_backing')
    
    if not clean_url or not backing_url:
        raise HTTPException(
            status_code=500,
            detail="Instrumental options not available"
        )
    
    # Generate signed URLs
    from backend.services.storage_service import StorageService
    storage = StorageService()
    
    return {
        "options": [
            {
                "id": "clean",
                "label": "Clean Instrumental (no backing vocals)",
                "audio_url": storage.generate_signed_url(clean_url, expiration_minutes=120),
                "duration_seconds": None  # TODO: Extract from audio file
            },
            {
                "id": "with_backing",
                "label": "Instrumental with Backing Vocals",
                "audio_url": storage.generate_signed_url(backing_url, expiration_minutes=120),
                "duration_seconds": None  # TODO: Extract from audio file
            }
        ],
        "status": job.status,
        "artist": job.artist,
        "title": job.title
    }


@router.post("/{job_id}/select-instrumental")
async def select_instrumental(
    job_id: str,
    selection: InstrumentalSelection,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Submit instrumental selection.
    
    This is the SECOND critical human-in-the-loop interaction point.
    After selection, the job proceeds to video generation.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.AWAITING_INSTRUMENTAL_SELECTION:
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready for instrumental selection (current status: {job.status})"
        )
    
    try:
        # Store selection in state_data
        job_manager.update_state_data(job_id, 'instrumental_selection', selection.selection)
        
        # Transition to INSTRUMENTAL_SELECTED
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.INSTRUMENTAL_SELECTED,
            progress=65,
            message=f"Instrumental selected: {selection.selection}"
        )
        
        # Trigger video generation worker
        background_tasks.add_task(worker_service.trigger_video_worker, job_id)
        
        logger.info(f"Job {job_id}: Instrumental selected ({selection.selection}), triggering video generation")
        
        return {
            "status": "success",
            "job_status": "instrumental_selected",
            "selection": selection.selection,
            "message": "Selection accepted, starting video generation"
        }
        
    except Exception as e:
        logger.error(f"Error selecting instrumental for job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, request: CancelJobRequest) -> dict:
    """
    Cancel a job.
    
    Jobs can be cancelled at any stage before completion.
    """
    success = job_manager.cancel_job(job_id, reason=request.reason)
    
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel job")
    
    return {
        "status": "success",
        "job_status": "cancelled",
        "message": "Job cancelled successfully"
    }


@router.get("/{job_id}/logs")
async def get_worker_logs(
    job_id: str,
    since_index: int = 0,
    worker: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get worker logs for debugging.
    
    This endpoint returns worker logs stored in Firestore.
    Use `since_index` for efficient polling (returns only new logs).
    
    Args:
        job_id: Job ID
        since_index: Return only logs after this index (for pagination/polling)
        worker: Filter by worker name (audio, lyrics, screens, video, render)
    
    Returns:
        {
            "logs": [{"timestamp": "...", "level": "INFO", "worker": "audio", "message": "..."}],
            "next_index": 42,  # Use this for next poll
            "total_logs": 42
        }
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = job_manager.get_worker_logs(job_id, since_index=since_index, worker=worker)
    total = len(job.worker_logs) if job.worker_logs else 0
    
    return {
        "logs": logs,
        "next_index": total,
        "total_logs": total
    }

