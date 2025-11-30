"""
Firestore database operations for job management.
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from backend.config import settings
from backend.models.job import Job, JobStatus, TimelineEvent


logger = logging.getLogger(__name__)


class FirestoreService:
    """Service for Firestore database operations."""
    
    def __init__(self):
        """Initialize Firestore client."""
        self.db = firestore.Client(project=settings.google_cloud_project)
        self.collection = settings.firestore_collection
        
    def create_job(self, job: Job) -> None:
        """Create a new job in Firestore."""
        try:
            doc_ref = self.db.collection(self.collection).document(job.job_id)
            doc_ref.set(job.model_dump(mode='json'))
            logger.info(f"Created job {job.job_id} in Firestore")
        except Exception as e:
            logger.error(f"Error creating job {job.job_id}: {e}")
            raise
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        try:
            doc_ref = self.db.collection(self.collection).document(job_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            return Job(**data)
        except Exception as e:
            logger.error(f"Error getting job {job_id}: {e}")
            raise
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> None:
        """Update a job with partial data."""
        try:
            doc_ref = self.db.collection(self.collection).document(job_id)
            
            # Add updated_at timestamp
            updates['updated_at'] = datetime.utcnow()
            
            doc_ref.update(updates)
            logger.info(f"Updated job {job_id} in Firestore")
        except Exception as e:
            logger.error(f"Error updating job {job_id}: {e}")
            raise
    
    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        **additional_fields
    ) -> None:
        """Update job status and add timeline event."""
        try:
            doc_ref = self.db.collection(self.collection).document(job_id)
            
            # Create timeline event
            timeline_event = TimelineEvent(
                status=status.value,
                timestamp=datetime.utcnow().isoformat(),
                progress=progress,
                message=message
            )
            
            # Prepare updates
            updates = {
                'status': status.value,
                'updated_at': datetime.utcnow(),
                'timeline': firestore.ArrayUnion([timeline_event.model_dump(mode='json')])
            }
            
            if progress is not None:
                updates['progress'] = progress
            
            # Add any additional fields
            updates.update(additional_fields)
            
            doc_ref.update(updates)
            logger.info(f"Updated job {job_id} status to {status.value}")
        except Exception as e:
            logger.error(f"Error updating job status {job_id}: {e}")
            raise
    
    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        limit: int = 100
    ) -> List[Job]:
        """List jobs with optional status filter."""
        try:
            query = self.db.collection(self.collection)
            
            if status:
                query = query.where(filter=FieldFilter('status', '==', status.value))
            
            query = query.order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
            
            docs = query.stream()
            jobs = [Job(**doc.to_dict()) for doc in docs]
            
            return jobs
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            raise
    
    def delete_job(self, job_id: str) -> None:
        """Delete a job from Firestore."""
        try:
            doc_ref = self.db.collection(self.collection).document(job_id)
            doc_ref.delete()
            logger.info(f"Deleted job {job_id} from Firestore")
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            raise

