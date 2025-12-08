"""
File upload route for local file submission.
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pathlib import Path

from backend.models.job import JobCreate
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.services.worker_service import get_worker_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"])

# Initialize services
job_manager = JobManager()
storage_service = StorageService()
worker_service = get_worker_service()


@router.post("/jobs/upload")
async def upload_and_create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    artist: str = Form(...),
    title: str = Form(...)
):
    """
    Upload an audio file and create a karaoke generation job.
    
    This endpoint:
    1. Uploads the file to GCS
    2. Creates a job in Firestore with the GCS path
    3. Triggers the audio and lyrics workers
    
    The job will go through the full worker pipeline including human interaction points.
    """
    try:
        # Validate file type
        allowed_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Create job first to get job_id
        job_create = JobCreate(
            artist=artist,
            title=title,
            filename=file.filename
        )
        job = job_manager.create_job(job_create)
        
        # Upload file to GCS
        gcs_path = f"uploads/{job.job_id}/{file.filename}"
        logger.info(f"Uploading {file.filename} to GCS: {gcs_path}")
        
        storage_service.upload_fileobj(
            file.file,
            gcs_path,
            content_type=file.content_type or 'audio/flac'
        )
        
        # Update job with GCS path BEFORE triggering workers
        job_manager.update_job(job.job_id, {
            'input_media_gcs_path': gcs_path,
            'filename': file.filename
        })
        
        # Verify the update by refetching the job
        updated_job = job_manager.get_job(job.job_id)
        if not hasattr(updated_job, 'input_media_gcs_path') or not updated_job.input_media_gcs_path:
            # Wait a moment for Firestore consistency
            import asyncio
            await asyncio.sleep(0.5)
            updated_job = job_manager.get_job(job.job_id)
            if not hasattr(updated_job, 'input_media_gcs_path') or not updated_job.input_media_gcs_path:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to update job with GCS path"
                )
        
        logger.info(f"File uploaded successfully for job {job.job_id}, GCS path: {gcs_path}")
        
        # Transition job to DOWNLOADING state before triggering workers
        # This is required by the state machine: PENDING -> DOWNLOADING -> SEPARATING_STAGE1/TRANSCRIBING
        from backend.models.job import JobStatus
        job_manager.transition_to_state(
            job_id=job.job_id,
            new_status=JobStatus.DOWNLOADING,
            progress=5,
            message="File uploaded, preparing to process"
        )
        
        # Trigger both workers in parallel using background tasks
        # They run independently and coordinate via job state
        background_tasks.add_task(worker_service.trigger_audio_worker, job.job_id)
        background_tasks.add_task(worker_service.trigger_lyrics_worker, job.job_id)
        
        return {
            "status": "success",
            "job_id": job.job_id,
            "message": "File uploaded successfully. Processing started.",
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

