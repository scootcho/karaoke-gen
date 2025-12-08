"""
Worker coordination service.

Handles triggering and coordinating background workers.
Implements proper HTTP-based triggers for production use.

SOLID Principles:
- Single Responsibility: Only handles worker coordination
- Dependency Inversion: Depends on HTTP abstraction, not implementation
- Open/Closed: Can add new workers without modifying existing code
"""
import logging
import os
import httpx
from typing import Optional
from backend.config import get_settings


logger = logging.getLogger(__name__)


class WorkerService:
    """
    Service for coordinating background workers.
    
    Handles triggering workers via internal HTTP API.
    In production, workers run as separate Cloud Run requests or Cloud Tasks.
    """
    
    def __init__(self):
        """Initialize worker service."""
        self.settings = get_settings()
        self._base_url = self._get_base_url()
    
    def _get_base_url(self) -> str:
        """
        Get base URL for internal API calls.
        
        In production: Cloud Run service URL
        In test: TEST_SERVER_URL
        In development: localhost
        
        Returns:
            Base URL for API calls
        """
        # Check for test environment override
        test_url = os.getenv("TEST_SERVER_URL")
        if test_url:
            return test_url
        
        # Check if running in Cloud Run
        cloud_run_url = self.settings.google_cloud_project
        if cloud_run_url and self.settings.environment == "production":
            # TODO: Get actual Cloud Run service URL
            # For now, use environment variable
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
        Trigger a background worker via internal API.
        
        Args:
            worker_type: Worker type ("audio", "lyrics", "screens", "video")
            job_id: Job ID to process
            timeout_seconds: Request timeout
            
        Returns:
            True if trigger successful, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                url = f"{self._base_url}/api/internal/workers/{worker_type}"
                
                response = await client.post(
                    url,
                    json={"job_id": job_id}
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

