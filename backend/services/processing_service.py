"""
Core karaoke processing service.

This service integrates the existing karaoke_gen CLI modules to perform
the actual karaoke generation processing.
"""
import logging
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from karaoke_gen import KaraokePrep

from backend.config import settings
from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService


logger = logging.getLogger(__name__)


class ProcessingService:
    """Service for karaoke generation processing."""
    
    def __init__(self):
        """Initialize processing service."""
        self.job_manager = JobManager()
        self.storage = StorageService()
    
    async def process_job(self, job_id: str) -> None:
        """Process a karaoke generation job."""
        try:
            job = self.job_manager.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            # Update status to processing
            self.job_manager.update_job_status(
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress=10,
                message="Starting karaoke generation"
            )
            
            # Create temporary working directory
            work_dir = Path(settings.temp_dir) / job_id
            work_dir.mkdir(parents=True, exist_ok=True)
            
            try:
                if job.url:
                    # Process from URL (YouTube, etc.)
                    await self._process_from_url(job_id, job.url, str(work_dir))
                elif job.filename:
                    # Process from uploaded file
                    await self._process_from_upload(job_id, str(work_dir))
                else:
                    raise ValueError("Job has neither URL nor uploaded file")
                
                # Mark as complete
                self.job_manager.update_job_status(
                    job_id=job_id,
                    status=JobStatus.COMPLETE,
                    progress=100,
                    message="Karaoke generation complete"
                )
                
            finally:
                # Cleanup temporary files
                await self._cleanup_temp_files(work_dir)
        
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
            self.job_manager.mark_job_error(job_id, str(e))
    
    async def _process_from_url(self, job_id: str, url: str, work_dir: str) -> None:
        """Process karaoke generation from a URL."""
        logger.info(f"Processing job {job_id} from URL: {url}")
        
        # Set up environment for remote audio separation
        if settings.audio_separator_api_url:
            os.environ['AUDIO_SEPARATOR_API_URL'] = settings.audio_separator_api_url
        
        # Set up AudioShake and Genius API keys
        if settings.audioshake_api_key:
            os.environ['AUDIOSHAKE_API_KEY'] = settings.audioshake_api_key
        if settings.genius_api_key:
            os.environ['GENIUS_API_KEY'] = settings.genius_api_key
        
        # Create KaraokePrep instance (using existing CLI code)
        karaoke = KaraokePrep(
            input_media=url,
            output_dir=work_dir,
            create_track_subfolders=True,
            log_level=logging.INFO,
            skip_transcription_review=True,  # For MVP, skip manual review
            render_video=True
        )
        
        # Run the processing in a thread pool (karaoke processing is CPU-bound)
        await asyncio.to_thread(karaoke.prep_single_track)
        
        # Upload results to GCS
        await self._upload_results(job_id, work_dir)
    
    async def _process_from_upload(self, job_id: str, work_dir: str) -> None:
        """Process karaoke generation from an uploaded file."""
        logger.info(f"Processing job {job_id} from uploaded file")
        
        job = self.job_manager.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Download the uploaded file from GCS
        upload_path = f"uploads/{job_id}/{job.filename}"
        local_file = Path(work_dir) / job.filename
        self.storage.download_file(upload_path, str(local_file))
        
        # Set up environment
        if settings.audio_separator_api_url:
            os.environ['AUDIO_SEPARATOR_API_URL'] = settings.audio_separator_api_url
        if settings.audioshake_api_key:
            os.environ['AUDIOSHAKE_API_KEY'] = settings.audioshake_api_key
        if settings.genius_api_key:
            os.environ['GENIUS_API_KEY'] = settings.genius_api_key
        
        # Create KaraokePrep instance
        karaoke = KaraokePrep(
            input_media=str(local_file),
            artist=job.artist,
            title=job.title,
            output_dir=work_dir,
            create_track_subfolders=True,
            log_level=logging.INFO,
            skip_transcription_review=True,
            render_video=True
        )
        
        # Run the processing
        await asyncio.to_thread(karaoke.prep_single_track)
        
        # Upload results to GCS
        await self._upload_results(job_id, work_dir)
    
    async def _upload_results(self, job_id: str, work_dir: str) -> None:
        """Upload processing results to GCS."""
        logger.info(f"Uploading results for job {job_id}")
        
        work_path = Path(work_dir)
        output_files = {}
        
        # Find and upload the main output files
        for file_path in work_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Determine file type and upload
            if file_path.suffix.lower() in ['.mp4', '.mkv', '.mov']:
                # Video file
                file_type = f"video_{file_path.stem}"
                gcs_path = f"outputs/{job_id}/{file_path.name}"
                await asyncio.to_thread(self.storage.upload_file, str(file_path), gcs_path)
                output_files[file_type] = gcs_path
            
            elif file_path.suffix.lower() in ['.lrc', '.ass', '.srt']:
                # Lyrics file
                file_type = f"lyrics_{file_path.suffix[1:]}"
                gcs_path = f"outputs/{job_id}/{file_path.name}"
                await asyncio.to_thread(self.storage.upload_file, str(file_path), gcs_path)
                output_files[file_type] = gcs_path
            
            elif file_path.suffix.lower() in ['.flac', '.wav', '.mp3']:
                # Audio file
                if 'instrumental' in file_path.stem.lower():
                    file_type = "audio_instrumental"
                    gcs_path = f"outputs/{job_id}/{file_path.name}"
                    await asyncio.to_thread(self.storage.upload_file, str(file_path), gcs_path)
                    output_files[file_type] = gcs_path
        
        # Update job with output file paths
        self.job_manager.update_job(job_id, {'output_files': output_files})
        logger.info(f"Uploaded {len(output_files)} files for job {job_id}")
    
    async def _cleanup_temp_files(self, work_dir: Path) -> None:
        """Clean up temporary processing files."""
        try:
            import shutil
            if work_dir.exists():
                await asyncio.to_thread(shutil.rmtree, work_dir)
                logger.info(f"Cleaned up temporary directory: {work_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up {work_dir}: {e}")

