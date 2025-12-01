"""
Job management routes.
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional

from backend.models.job import Job, JobCreate, JobResponse, JobStatus
from backend.models.requests import URLSubmissionRequest
from backend.services.job_manager import JobManager
from backend.services.processing_service import ProcessingService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

# Initialize services
job_manager = JobManager()
processing_service = ProcessingService()


@router.post("", response_model=JobResponse)
async def create_job(
    request: URLSubmissionRequest,
    background_tasks: BackgroundTasks
) -> JobResponse:
    """Create a new karaoke generation job from a URL."""
    try:
        # Create job
        job_create = JobCreate(url=str(request.url))
        job = job_manager.create_job(job_create)
        
        # Start processing in background
        background_tasks.add_task(processing_service.process_job, job.job_id)
        
        return JobResponse(
            status="success",
            job_id=job.job_id,
            message="Job created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

