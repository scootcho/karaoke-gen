"""
Worker coordination service.

Handles triggering and coordinating background workers.
Supports two modes:
- Cloud Tasks (production): Guaranteed delivery, automatic retries, horizontal scaling
- Direct HTTP (development): Faster iteration, simpler debugging

SOLID Principles:
- Single Responsibility: Only handles worker coordination
- Dependency Inversion: Depends on HTTP abstraction, not implementation
- Open/Closed: Can add new workers without modifying existing code
"""
import logging
import os
import json
from typing import Optional
import httpx

from backend.config import get_settings


logger = logging.getLogger(__name__)


# Mapping of worker types to their Cloud Tasks queue names
# These queues are created by Pulumi in infrastructure/__main__.py
WORKER_QUEUES = {
    "audio": "audio-worker-queue",
    "lyrics": "lyrics-worker-queue",
    "screens": "screens-worker-queue",
    "render-video": "render-worker-queue",
    "video": "video-worker-queue",
}


class WorkerService:
    """
    Service for coordinating background workers.
    
    Supports two execution modes controlled by ENABLE_CLOUD_TASKS env var:
    
    1. Cloud Tasks mode (production, ENABLE_CLOUD_TASKS=true):
       - Tasks enqueued to Cloud Tasks for guaranteed delivery
       - Automatic retries on failure
       - Each task runs in dedicated Cloud Run instance
       - Rate limiting to protect external APIs (Modal, AudioShake)
       
    2. Direct HTTP mode (development, ENABLE_CLOUD_TASKS=false):
       - Direct HTTP POST to internal worker endpoints
       - Worker runs as FastAPI BackgroundTask
       - Faster iteration for local development
       - No retry guarantees
    """
    
    def __init__(self):
        """Initialize worker service."""
        self.settings = get_settings()
        self._base_url = self._get_base_url()
        self._admin_token = self._get_admin_token()
        self._use_cloud_tasks = self._should_use_cloud_tasks()
        self._tasks_client = None
        
        if self._use_cloud_tasks:
            logger.info("WorkerService initialized with Cloud Tasks mode")
        else:
            logger.info("WorkerService initialized with direct HTTP mode")
    
    def _should_use_cloud_tasks(self) -> bool:
        """
        Check if Cloud Tasks should be used for worker coordination.
        
        Controlled by ENABLE_CLOUD_TASKS environment variable.
        Default is false (direct HTTP mode) for backward compatibility.
        
        Returns:
            True if Cloud Tasks should be used, False for direct HTTP
        """
        enable_flag = os.getenv("ENABLE_CLOUD_TASKS", "false").lower()
        return enable_flag in ("true", "1", "yes")
    
    @property
    def tasks_client(self):
        """
        Lazy-initialize Cloud Tasks client.
        
        Only created when needed to avoid import overhead in development mode.
        """
        if self._tasks_client is None and self._use_cloud_tasks:
            try:
                from google.cloud import tasks_v2
                self._tasks_client = tasks_v2.CloudTasksClient()
            except ImportError:
                logger.error(
                    "google-cloud-tasks not installed. "
                    "Install with: pip install google-cloud-tasks"
                )
                raise
        return self._tasks_client
    
    def _get_admin_token(self) -> Optional[str]:
        """
        Get admin token for internal API authentication.
        
        Returns the first admin token from ADMIN_TOKENS env var.
        """
        admin_tokens_str = self.settings.admin_tokens or ""
        tokens = [t.strip() for t in admin_tokens_str.split(",") if t.strip()]
        if tokens:
            return tokens[0]
        return None
    
    def _get_base_url(self) -> str:
        """
        Get base URL for internal API calls.
        
        Priority:
        1. TEST_SERVER_URL env var (for tests)
        2. CLOUD_RUN_SERVICE_URL env var (for Cloud Tasks to call back)
        3. localhost with PORT env var (for development)
        
        Returns:
            Base URL for API calls
        """
        # Check for test environment override
        test_url = os.getenv("TEST_SERVER_URL")
        if test_url:
            return test_url
        
        # Production: Cloud Run service URL
        # This must be the publicly accessible URL for Cloud Tasks to call
        service_url = os.getenv("CLOUD_RUN_SERVICE_URL")
        if service_url:
            return service_url
        
        # Development mode: use localhost with PORT env var
        port = os.getenv("PORT", "8000")
        return f"http://localhost:{port}"
    
    async def trigger_worker(
        self,
        worker_type: str,
        job_id: str,
        timeout_seconds: int = 30
    ) -> bool:
        """
        Trigger a background worker for a job.
        
        In production (ENABLE_CLOUD_TASKS=true):
          - Enqueues task to Cloud Tasks queue
          - Cloud Tasks delivers HTTP request to internal endpoint
          - Automatic retries on failure with exponential backoff
          - Rate limiting protects external APIs
          
        In development (ENABLE_CLOUD_TASKS=false):
          - Direct HTTP POST to internal endpoint
          - Faster iteration, but no retry guarantees
          - Worker runs in same container as API
        
        Args:
            worker_type: Worker type ("audio", "lyrics", "screens", "render-video", "video")
            job_id: Job ID to process
            timeout_seconds: Request timeout (for direct HTTP mode)
            
        Returns:
            True if trigger successful (or task enqueued), False otherwise
        """
        if self._use_cloud_tasks:
            return await self._enqueue_cloud_task(worker_type, job_id)
        else:
            return await self._trigger_http(worker_type, job_id, timeout_seconds)
    
    async def _enqueue_cloud_task(self, worker_type: str, job_id: str) -> bool:
        """
        Enqueue task to Cloud Tasks for guaranteed delivery.
        
        The task will be delivered as an HTTP POST to the internal worker endpoint.
        Cloud Tasks handles:
        - Retry on failure (with exponential backoff)
        - Rate limiting (max dispatches per second)
        - Deduplication (via task name if needed)
        - OIDC authentication for Cloud Run
        
        Args:
            worker_type: Worker type
            job_id: Job ID to process
            
        Returns:
            True if task enqueued successfully, False otherwise
        """
        try:
            from google.cloud import tasks_v2
            
            queue_name = WORKER_QUEUES.get(worker_type)
            if not queue_name:
                logger.error(f"Unknown worker type: {worker_type}")
                return False
            
            project = self.settings.google_cloud_project
            if not project:
                logger.error("GOOGLE_CLOUD_PROJECT not set, cannot enqueue Cloud Task")
                return False
                
            location = "us-central1"  # Must match queue location
            
            # Build queue path
            parent = self.tasks_client.queue_path(project, location, queue_name)
            
            # Build task payload
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{self._base_url}/api/internal/workers/{worker_type}",
                    "headers": {
                        "Content-Type": "application/json",
                    },
                    "body": json.dumps({"job_id": job_id}).encode(),
                    # Use OIDC token for Cloud Run authentication
                    # This allows Cloud Tasks to invoke the Cloud Run service
                    "oidc_token": {
                        "service_account_email": f"karaoke-backend@{project}.iam.gserviceaccount.com",
                    },
                },
            }
            
            # Add admin auth header if available
            # This is needed for the internal endpoint's require_admin dependency
            if self._admin_token:
                task["http_request"]["headers"]["Authorization"] = f"Bearer {self._admin_token}"
            
            # Create task
            # Note: We don't set a task name, allowing Cloud Tasks to generate one
            # This prevents duplicate task errors on retries
            response = self.tasks_client.create_task(parent=parent, task=task)
            logger.info(
                f"Created Cloud Task for {worker_type} worker, job {job_id}: {response.name}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to enqueue Cloud Task for {worker_type}/{job_id}: {e}",
                exc_info=True
            )
            return False
    
    async def _trigger_http(
        self,
        worker_type: str,
        job_id: str,
        timeout_seconds: int = 30
    ) -> bool:
        """
        Trigger worker via direct HTTP call (development mode).
        
        This is the original implementation - direct HTTP POST to internal endpoint.
        The endpoint adds the worker function to FastAPI BackgroundTasks.
        
        Args:
            worker_type: Worker type
            job_id: Job ID to process
            timeout_seconds: Request timeout
            
        Returns:
            True if trigger successful, False otherwise
        """
        try:
            # Build headers with admin auth token
            headers = {}
            if self._admin_token:
                headers["Authorization"] = f"Bearer {self._admin_token}"
            
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                url = f"{self._base_url}/api/internal/workers/{worker_type}"
                
                response = await client.post(
                    url,
                    json={"job_id": job_id},
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully triggered {worker_type} worker for job {job_id}")
                    return True
                else:
                    logger.error(
                        f"Failed to trigger {worker_type} worker for job {job_id}: "
                        f"HTTP {response.status_code} - {response.text}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout triggering {worker_type} worker for job {job_id}")
            return False
            
        except Exception as e:
            logger.error(
                f"Error triggering {worker_type} worker for job {job_id}: {e}",
                exc_info=True
            )
            return False
    
    # Convenience methods for specific workers
    # These provide a cleaner API and better IDE autocomplete
    
    async def trigger_audio_worker(self, job_id: str) -> bool:
        """Trigger audio separation worker."""
        return await self.trigger_worker("audio", job_id)
    
    async def trigger_lyrics_worker(self, job_id: str) -> bool:
        """Trigger lyrics transcription worker."""
        return await self.trigger_worker("lyrics", job_id)
    
    async def trigger_screens_worker(self, job_id: str) -> bool:
        """Trigger screen generation worker."""
        return await self.trigger_worker("screens", job_id)
    
    async def trigger_video_worker(self, job_id: str) -> bool:
        """Trigger video generation worker."""
        return await self.trigger_worker("video", job_id)
    
    async def trigger_render_video_worker(self, job_id: str) -> bool:
        """Trigger render video worker (post-review)."""
        return await self.trigger_worker("render-video", job_id)


# Global worker service instance
_worker_service: Optional[WorkerService] = None


def get_worker_service() -> WorkerService:
    """
    Get global worker service instance.
    
    Singleton pattern to reuse HTTP client pool.
    
    Returns:
        WorkerService instance
    """
    global _worker_service
    if _worker_service is None:
        _worker_service = WorkerService()
    return _worker_service


def reset_worker_service() -> None:
    """
    Reset the global worker service instance.
    
    Used in tests to ensure clean state between test cases.
    """
    global _worker_service
    _worker_service = None
