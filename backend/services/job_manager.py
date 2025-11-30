"""
Job management and queue operations.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.models.job import Job, JobStatus, JobCreate
from backend.services.firestore_service import FirestoreService
from backend.services.storage_service import StorageService


logger = logging.getLogger(__name__)


class JobManager:
    """Manager for job lifecycle and state."""
    
    def __init__(self):
        """Initialize job manager with required services."""
        self.firestore = FirestoreService()
        self.storage = StorageService()
    
    def create_job(self, job_create: JobCreate) -> Job:
        """Create a new job."""
        job_id = str(uuid.uuid4())[:8]
        
        now = datetime.utcnow()
        job = Job(
            job_id=job_id,
            status=JobStatus.QUEUED,
            progress=0,
            created_at=now,
            updated_at=now,
            url=str(job_create.url) if job_create.url else None,
            artist=job_create.artist,
            title=job_create.title
        )
        
        self.firestore.create_job(job)
        logger.info(f"Created new job {job_id}")
        
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.firestore.get_job(job_id)
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        **kwargs
    ) -> None:
        """Update job status with timeline tracking."""
        self.firestore.update_job_status(
            job_id=job_id,
            status=status,
            progress=progress,
            message=message,
            **kwargs
        )
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update job with arbitrary fields."""
        self.firestore.update_job(job_id, updates)
    
    def list_jobs(self, status: Optional[JobStatus] = None, limit: int = 100) -> List[Job]:
        """List jobs with optional filtering."""
        return self.firestore.list_jobs(status=status, limit=limit)
    
    def mark_job_error(self, job_id: str, error_message: str) -> None:
        """Mark a job as errored."""
        self.firestore.update_job_status(
            job_id=job_id,
            status=JobStatus.ERROR,
            progress=0,
            message=error_message,
            error_message=error_message
        )
        logger.error(f"Job {job_id} marked as error: {error_message}")
    
    def get_output_urls(self, job_id: str) -> Dict[str, str]:
        """Generate signed URLs for job output files."""
        job = self.get_job(job_id)
        if not job or not job.output_files:
            return {}
        
        urls = {}
        for file_type, gcs_path in job.output_files.items():
            try:
                urls[file_type] = self.storage.generate_signed_url(gcs_path, expiration_minutes=120)
            except Exception as e:
                logger.error(f"Error generating URL for {file_type}: {e}")
        
        return urls
    
    def delete_job(self, job_id: str, delete_files: bool = True) -> None:
        """Delete a job and optionally its files."""
        if delete_files:
            job = self.get_job(job_id)
            if job and job.output_files:
                for gcs_path in job.output_files.values():
                    try:
                        self.storage.delete_file(gcs_path)
                    except Exception as e:
                        logger.error(f"Error deleting file {gcs_path}: {e}")
        
        self.firestore.delete_job(job_id)
        logger.info(f"Deleted job {job_id}")

