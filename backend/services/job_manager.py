"""
Job management and queue operations.

This module handles the complete job lifecycle including:
- Job creation and initialization
- State transitions and validation
- Worker coordination (parallel audio + lyrics processing)
- Progress tracking and timeline events
- Error handling and retries
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from backend.models.job import Job, JobStatus, JobCreate, STATE_TRANSITIONS
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
        """
        Create a new job with initial state PENDING.
        
        Jobs start in PENDING state and transition to DOWNLOADING
        when a worker picks them up.
        """
        job_id = str(uuid.uuid4())[:8]
        
        now = datetime.utcnow()
        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,  # New state machine starts with PENDING
            progress=0,
            created_at=now,
            updated_at=now,
            url=str(job_create.url) if job_create.url else None,
            artist=job_create.artist,
            title=job_create.title,
            # User preferences
            enable_cdg=job_create.enable_cdg,
            enable_txt=job_create.enable_txt,
            enable_youtube_upload=job_create.enable_youtube_upload,
            youtube_description=job_create.youtube_description,
            webhook_url=job_create.webhook_url,
            user_email=job_create.user_email,
        )
        
        self.firestore.create_job(job)
        logger.info(f"Created new job {job_id} with status PENDING")
        
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
    
    def validate_state_transition(self, job_id: str, new_status: JobStatus) -> bool:
        """
        Validate that a state transition is legal.
        
        Returns:
            True if transition is valid, False otherwise
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return False
        
        current_status = job.status
        valid_transitions = STATE_TRANSITIONS.get(current_status, [])
        
        if new_status not in valid_transitions:
            logger.error(
                f"Invalid state transition for job {job_id}: "
                f"{current_status} -> {new_status}. "
                f"Valid transitions: {valid_transitions}"
            )
            return False
        
        return True
    
    def transition_to_state(
        self,
        job_id: str,
        new_status: JobStatus,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        state_data_updates: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Transition job to new state with validation.
        
        Args:
            job_id: Job ID
            new_status: Target state
            progress: Progress percentage (0-100)
            message: Timeline message
            state_data_updates: Updates to state_data field
        
        Returns:
            True if transition succeeded, False otherwise
        """
        if not self.validate_state_transition(job_id, new_status):
            return False
        
        updates = {
            'status': new_status,
            'updated_at': datetime.utcnow()
        }
        
        if progress is not None:
            updates['progress'] = progress
        
        if state_data_updates:
            job = self.get_job(job_id)
            if job:
                updated_state_data = {**job.state_data, **state_data_updates}
                updates['state_data'] = updated_state_data
        
        self.update_job_status(
            job_id=job_id,
            status=new_status,
            progress=progress,
            message=message
        )
        
        logger.info(f"Job {job_id} transitioned to {new_status}")
        return True
    
    def update_state_data(self, job_id: str, key: str, value: Any) -> None:
        """
        Update a specific key in the job's state_data field.
        
        This is used by workers to store stage-specific metadata.
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        state_data = job.state_data.copy()
        state_data[key] = value
        
        self.update_job(job_id, {'state_data': state_data})
        logger.debug(f"Job {job_id} state_data updated: {key} = {value}")
    
    def update_file_url(self, job_id: str, category: str, file_type: str, url: str) -> None:
        """
        Update a file URL in the job's file_urls structure.
        
        Args:
            job_id: Job ID
            category: Category (e.g., "stems", "lyrics", "finals")
            file_type: File type within category (e.g., "clean", "lrc", "lossless_4k_mp4")
            url: GCS URL
        """
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        file_urls = job.file_urls.copy()
        if category not in file_urls:
            file_urls[category] = {}
        
        file_urls[category][file_type] = url
        
        self.update_job(job_id, {'file_urls': file_urls})
        logger.debug(f"Job {job_id} file URL updated: {category}.{file_type}")
    
    def check_parallel_processing_complete(self, job_id: str) -> bool:
        """
        Check if both parallel tracks (audio + lyrics) are complete.
        
        This is called after audio_complete or lyrics_complete to determine
        if we can proceed to screen generation.
        
        Returns:
            True if both tracks complete, False otherwise
        """
        job = self.get_job(job_id)
        if not job:
            return False
        
        audio_complete = job.state_data.get('audio_complete', False)
        lyrics_complete = job.state_data.get('lyrics_complete', False)
        
        return audio_complete and lyrics_complete
    
    def mark_audio_complete(self, job_id: str) -> None:
        """
        Mark audio processing as complete and check if can proceed.
        
        If lyrics are also complete, automatically triggers screens worker.
        """
        self.update_state_data(job_id, 'audio_complete', True)
        
        if self.check_parallel_processing_complete(job_id):
            logger.info(f"Job {job_id}: Both audio and lyrics complete, triggering screens worker")
            # Transition happens in screens worker
            # We just trigger it here
            self._trigger_screens_worker(job_id)
    
    def mark_lyrics_complete(self, job_id: str) -> None:
        """
        Mark lyrics processing as complete and check if can proceed.
        
        If audio is also complete, automatically triggers screens worker.
        """
        self.update_state_data(job_id, 'lyrics_complete', True)
        
        if self.check_parallel_processing_complete(job_id):
            logger.info(f"Job {job_id}: Both audio and lyrics complete, triggering screens worker")
            # Transition happens in screens worker
            # We just trigger it here
            self._trigger_screens_worker(job_id)
    
    def _trigger_screens_worker(self, job_id: str) -> None:
        """
        Trigger screens generation worker.
        
        Uses WorkerService to make HTTP call to internal API.
        This must be async, so we use asyncio to create a task.
        """
        import asyncio
        from backend.services.worker_service import get_worker_service
        
        logger.info(f"Job {job_id}: Triggering screens worker")
        
        # Create async task to trigger worker
        # This allows us to call async code from sync context
        async def _trigger():
            worker_service = get_worker_service()
            await worker_service.trigger_screens_worker(job_id)
        
        # Create task in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create task
                asyncio.create_task(_trigger())
            else:
                # If no loop, run directly
                asyncio.run(_trigger())
        except RuntimeError:
            # Fallback: just log
            logger.warning(f"Job {job_id}: Could not trigger screens worker (no event loop)")
            # TODO: In production, use message queue instead
    
    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> bool:
        """
        Cancel a job.
        
        Only jobs in non-terminal states can be cancelled.
        """
        job = self.get_job(job_id)
        if not job:
            return False
        
        terminal_states = [JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED]
        if job.status in terminal_states:
            logger.warning(f"Cannot cancel job {job_id} in terminal state {job.status}")
            return False
        
        message = f"Job cancelled{f': {reason}' if reason else ''}"
        
        self.update_job_status(
            job_id=job_id,
            status=JobStatus.CANCELLED,
            message=message
        )
        
        logger.info(f"Job {job_id} cancelled")
        return True
    
    def mark_job_failed(
        self,
        job_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a job as failed with error details.
        
        This replaces mark_job_error() with better error tracking.
        """
        updates = {
            'error_message': error_message
        }
        
        if error_details:
            updates['error_details'] = error_details
        
        self.firestore.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            progress=0,
            message=f"Failed: {error_message}",
            **updates
        )
        logger.error(f"Job {job_id} failed: {error_message}")
    
    def increment_retry_count(self, job_id: str) -> int:
        """
        Increment retry count for a job.
        
        Returns:
            New retry count
        """
        job = self.get_job(job_id)
        if not job:
            return 0
        
        new_count = job.retry_count + 1
        self.update_job(job_id, {'retry_count': new_count})
        return new_count

