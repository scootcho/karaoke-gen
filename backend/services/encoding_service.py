"""
GCE Encoding Worker Service.

This service dispatches video encoding jobs to a dedicated high-performance
GCE instance (C4-standard with Intel Granite Rapids CPU) for faster encoding.

The GCE worker provides:
- 3.9 GHz all-core frequency (vs 3.7 GHz on Cloud Run)
- Dedicated vCPUs (no contention)
- 2-3x faster FFmpeg libx264 encoding

Usage:
    encoding_service = get_encoding_service()
    if encoding_service.is_configured:
        result = await encoding_service.encode_videos(job_id, input_gcs_path, config)
"""

import asyncio
import logging
from typing import Optional, Dict, Any

import aiohttp

from backend.config import get_settings

logger = logging.getLogger(__name__)


class EncodingService:
    """Service for dispatching encoding jobs to GCE worker."""

    def __init__(self):
        self.settings = get_settings()
        self._url = None
        self._api_key = None
        self._initialized = False

    def _load_credentials(self):
        """Load encoding worker URL and API key from config/secrets."""
        if self._initialized:
            return

        # Try environment variables first, then Secret Manager
        self._url = self.settings.encoding_worker_url
        self._api_key = self.settings.encoding_worker_api_key

        # Fall back to Secret Manager
        if not self._url:
            self._url = self.settings.get_secret("encoding-worker-url")
        if not self._api_key:
            self._api_key = self.settings.get_secret("encoding-worker-api-key")

        self._initialized = True

    @property
    def is_configured(self) -> bool:
        """Check if encoding service is configured with URL and API key."""
        self._load_credentials()
        return bool(self._url and self._api_key)

    @property
    def is_enabled(self) -> bool:
        """Check if GCE encoding is enabled and configured."""
        return self.settings.use_gce_encoding and self.is_configured

    async def submit_encoding_job(
        self,
        job_id: str,
        input_gcs_path: str,
        output_gcs_path: str,
        encoding_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Submit an encoding job to the GCE worker.

        Args:
            job_id: Unique job identifier
            input_gcs_path: GCS path to input files (gs://bucket/path/)
            output_gcs_path: GCS path for output files (gs://bucket/path/)
            encoding_config: Configuration for encoding (formats, quality, etc.)

        Returns:
            Response from the encoding worker

        Raises:
            Exception: If submission fails
        """
        self._load_credentials()

        if not self.is_configured:
            raise RuntimeError("Encoding service not configured")

        url = f"{self._url}/encode"
        headers = {"X-API-Key": self._api_key, "Content-Type": "application/json"}
        payload = {
            "job_id": job_id,
            "input_gcs_path": input_gcs_path,
            "output_gcs_path": output_gcs_path,
            "encoding_config": encoding_config,
        }

        logger.info(f"[job:{job_id}] Submitting encoding job to GCE worker: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as resp:
                if resp.status == 401:
                    raise RuntimeError("Invalid API key for encoding worker")
                if resp.status == 409:
                    raise RuntimeError(f"Encoding job {job_id} already exists")
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Failed to submit encoding job: {resp.status} - {text}")

                return await resp.json()

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of an encoding job.

        Args:
            job_id: Job identifier

        Returns:
            Job status including: status, progress, error, output_files
        """
        self._load_credentials()

        if not self.is_configured:
            raise RuntimeError("Encoding service not configured")

        url = f"{self._url}/status/{job_id}"
        headers = {"X-API-Key": self._api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=30) as resp:
                if resp.status == 401:
                    raise RuntimeError("Invalid API key for encoding worker")
                if resp.status == 404:
                    raise RuntimeError(f"Encoding job {job_id} not found")
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Failed to get job status: {resp.status} - {text}")

                return await resp.json()

    async def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = 10.0,
        timeout: float = 3600.0,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Poll for encoding job completion.

        Args:
            job_id: Job identifier
            poll_interval: Seconds between status checks
            timeout: Maximum time to wait (default 1 hour)
            progress_callback: Optional callback(progress: int) for progress updates

        Returns:
            Final job status with output files

        Raises:
            TimeoutError: If job doesn't complete within timeout
            RuntimeError: If job fails
        """
        logger.info(f"[job:{job_id}] Waiting for GCE encoding to complete...")

        start_time = asyncio.get_event_loop().time()
        last_progress = 0

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Encoding job {job_id} timed out after {timeout}s")

            status = await self.get_job_status(job_id)

            # Handle case where GCE worker returns a list instead of dict
            if isinstance(status, list):
                logger.warning(f"[job:{job_id}] GCE returned list instead of dict: {status}")
                status = status[0] if status and isinstance(status[0], dict) else {}
            if not isinstance(status, dict):
                logger.error(f"[job:{job_id}] Unexpected status type: {type(status)}")
                status = {}

            job_status = status.get("status", "unknown")
            progress = status.get("progress", 0)

            # Report progress
            if progress != last_progress:
                logger.info(f"[job:{job_id}] Encoding progress: {progress}%")
                last_progress = progress
                if progress_callback:
                    try:
                        progress_callback(progress)
                    except Exception as e:
                        logger.warning(f"Progress callback failed: {e}")

            if job_status == "complete":
                logger.info(f"[job:{job_id}] GCE encoding complete in {elapsed:.1f}s")
                return status

            if job_status == "failed":
                error = status.get("error", "Unknown error")
                raise RuntimeError(f"Encoding job {job_id} failed: {error}")

            await asyncio.sleep(poll_interval)

    async def encode_videos(
        self,
        job_id: str,
        input_gcs_path: str,
        output_gcs_path: str,
        encoding_config: Optional[Dict[str, Any]] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Submit encoding job and wait for completion.

        This is a convenience method that combines submit + wait.

        Args:
            job_id: Unique job identifier
            input_gcs_path: GCS path to input files
            output_gcs_path: GCS path for output files
            encoding_config: Optional encoding configuration
            progress_callback: Optional callback for progress updates

        Returns:
            Final job status with output files
        """
        config = encoding_config or {"formats": ["mp4_4k", "mp4_720p"]}

        # Submit the job
        await self.submit_encoding_job(job_id, input_gcs_path, output_gcs_path, config)

        # Wait for completion
        return await self.wait_for_completion(
            job_id, progress_callback=progress_callback
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the encoding worker.

        Returns:
            Health status including active jobs and FFmpeg version
        """
        self._load_credentials()

        if not self.is_configured:
            return {"status": "not_configured"}

        url = f"{self._url}/health"
        headers = {"X-API-Key": self._api_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {"status": "error", "code": resp.status}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Singleton instance
_encoding_service: Optional[EncodingService] = None


def get_encoding_service() -> EncodingService:
    """Get the singleton encoding service instance."""
    global _encoding_service
    if _encoding_service is None:
        _encoding_service = EncodingService()
    return _encoding_service
