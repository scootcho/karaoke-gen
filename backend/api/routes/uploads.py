"""
File upload routes.
"""
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pathlib import Path

from backend.models.job import JobCreate, JobResponse
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.services.processing_service import ProcessingService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

# Initialize services
job_manager = JobManager()
storage_service = StorageService()
processing_service = ProcessingService()


@router.post("", response_model=JobResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    artist: str = Form(...),
    title: str = Form(...)
) -> JobResponse:
    """Upload an audio file and create a karaoke generation job."""
    try:
        # Validate file type
        allowed_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Create job
        job_create = JobCreate(artist=artist, title=title)
        job = job_manager.create_job(job_create)
        
        # Upload file to GCS
        gcs_path = f"uploads/{job.job_id}/{file.filename}"
        storage_service.upload_fileobj(
            file.file,
            gcs_path,
            content_type=file.content_type
        )
        
        # Update job with filename
        job_manager.update_job(job.job_id, {'filename': file.filename})
        
        # Start processing in background
        background_tasks.add_task(processing_service.process_job, job.job_id)
        
        return JobResponse(
            status="success",
            job_id=job.job_id,
            message="File uploaded and job created successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

