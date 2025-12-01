"""
Audio separation worker.

Handles the audio processing track of parallel processing:
1. Stage 1: Clean instrumental separation (Modal API, 3-5 min)
2. Stage 2: Backing vocals separation (Modal API, 2-3 min)
3. Post-processing: Combine instrumentals, normalize, generate Audacity LOF

Integrates with karaoke_gen.audio_processor.AudioProcessor for remote GPU separation.
"""
import logging
import os
import shutil
import tempfile
from typing import Optional
from pathlib import Path

from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.config import get_settings

# Import from karaoke_gen package
from karaoke_gen.audio_processor import AudioProcessor
from karaoke_gen.file_handler import FileHandler


logger = logging.getLogger(__name__)


async def process_audio_separation(job_id: str) -> bool:
    """
    Process audio separation for a job.
    
    This is the main entry point for the audio worker.
    Called asynchronously from the job submission endpoint.
    
    Args:
        job_id: Job ID to process
        
    Returns:
        True if successful, False otherwise
    """
    job_manager = JobManager()
    storage = StorageService()
    settings = get_settings()
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return False
    
    # Create temporary working directory
    temp_dir = tempfile.mkdtemp(prefix=f"karaoke_{job_id}_")
    
    try:
        logger.info(f"Starting audio separation for job {job_id}")
        
        # Download audio file from GCS
        audio_path = await download_audio(job_id, temp_dir, storage, job)
        if not audio_path:
            raise Exception("Failed to download audio file")
        
        # Initialize karaoke_gen components
        artist_title = f"{job.artist} - {job.title}" if job.artist and job.title else f"job_{job_id}"
        
        file_handler = FileHandler(
            input_media=audio_path,
            song_dir=temp_dir,
            artist_title=artist_title
        )
        
        audio_processor = AudioProcessor(
            logger=logger,
            model_file_dir=None,  # Not needed for remote API
            output_dir=temp_dir
        )
        
        # Set environment for remote processing
        audio_separator_url = await settings.get_secret("audio-separator-api-url")
        if audio_separator_url:
            os.environ["AUDIO_SEPARATOR_API_URL"] = audio_separator_url
            logger.info("Using remote audio separator API")
        else:
            logger.warning("No audio separator URL configured, will use local processing (slow!)")
        
        # Stage 1: Clean instrumental separation
        logger.info(f"Job {job_id}: Starting separation stage 1 (clean instrumental)")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.SEPARATING_STAGE1,
            progress=20,
            message="Separating audio (Stage 1/2): Clean instrumental"
        )
        
        await audio_processor.process_separation_stage_1(
            audio_path=file_handler.input_media_path
        )
        
        # Upload Stage 1 stems to GCS
        await upload_stage1_stems(job_id, temp_dir, job_manager, storage, audio_processor)
        
        # Stage 2: Backing vocals separation
        logger.info(f"Job {job_id}: Starting separation stage 2 (backing vocals)")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.SEPARATING_STAGE2,
            progress=35,
            message="Separating audio (Stage 2/2): Backing vocals"
        )
        
        await audio_processor.process_separation_stage_2(
            vocals_path=audio_processor.vocals_path
        )
        
        # Upload Stage 2 stems to GCS
        await upload_stage2_stems(job_id, temp_dir, job_manager, storage, audio_processor)
        
        # Post-processing: Generate combined instrumentals
        logger.info(f"Job {job_id}: Post-processing audio")
        await audio_processor.post_process_stems()
        
        # Upload final instrumentals
        await upload_final_instrumentals(job_id, job_manager, storage, audio_processor)
        
        # Mark audio processing complete
        logger.info(f"Job {job_id}: Audio separation complete")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.AUDIO_COMPLETE,
            progress=45,
            message="Audio separation complete"
        )
        
        # This will check if lyrics are also complete and transition to next stage if so
        job_manager.mark_audio_complete(job_id)
        
        return True
        
    except Exception as e:
        logger.error(f"Job {job_id}: Audio separation failed: {e}", exc_info=True)
        job_manager.mark_job_failed(
            job_id=job_id,
            error_message=f"Audio separation failed: {str(e)}",
            error_details={"stage": "audio_separation", "error": str(e)}
        )
        return False
        
    finally:
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")


async def download_audio(
    job_id: str,
    temp_dir: str,
    storage: StorageService,
    job
) -> Optional[str]:
    """
    Download audio file from GCS to local temp directory.
    
    Returns:
        Path to downloaded audio file, or None if failed
    """
    try:
        # Get input file URL from job
        input_url = job.file_urls.get('input')
        if not input_url:
            logger.error(f"Job {job_id}: No input file URL found")
            return None
        
        # Download from GCS
        local_path = os.path.join(temp_dir, "input.flac")
        storage.download_file(input_url, local_path)
        
        logger.info(f"Job {job_id}: Downloaded audio to {local_path}")
        return local_path
        
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to download audio: {e}")
        return None


async def upload_stage1_stems(
    job_id: str,
    temp_dir: str,
    job_manager: JobManager,
    storage: StorageService,
    audio_processor: AudioProcessor
) -> None:
    """Upload Stage 1 separation results to GCS."""
    stems_to_upload = {
        'instrumental_clean': audio_processor.instrumental_path,
        'vocals': audio_processor.vocals_path,
    }
    
    # Also upload 6-stem separation results if available
    if hasattr(audio_processor, 'stems') and audio_processor.stems:
        for stem_name in ['bass', 'drums', 'guitar', 'piano', 'other']:
            stem_path = audio_processor.stems.get(stem_name)
            if stem_path and os.path.exists(stem_path):
                stems_to_upload[stem_name] = stem_path
    
    for stem_type, local_path in stems_to_upload.items():
        if local_path and os.path.exists(local_path):
            gcs_path = f"jobs/{job_id}/stems/{stem_type}.flac"
            url = storage.upload_file(local_path, gcs_path)
            job_manager.update_file_url(job_id, 'stems', stem_type, url)
            logger.info(f"Job {job_id}: Uploaded {stem_type} stem")


async def upload_stage2_stems(
    job_id: str,
    temp_dir: str,
    job_manager: JobManager,
    storage: StorageService,
    audio_processor: AudioProcessor
) -> None:
    """Upload Stage 2 separation results to GCS."""
    stems_to_upload = {
        'backing_vocals': audio_processor.backing_vocals_path,
        'lead_vocals': audio_processor.lead_vocals_path,
    }
    
    for stem_type, local_path in stems_to_upload.items():
        if local_path and os.path.exists(local_path):
            gcs_path = f"jobs/{job_id}/stems/{stem_type}.flac"
            url = storage.upload_file(local_path, gcs_path)
            job_manager.update_file_url(job_id, 'stems', stem_type, url)
            logger.info(f"Job {job_id}: Uploaded {stem_type} stem")


async def upload_final_instrumentals(
    job_id: str,
    job_manager: JobManager,
    storage: StorageService,
    audio_processor: AudioProcessor
) -> None:
    """Upload combined instrumental tracks to GCS."""
    # Upload instrumental with backing vocals
    if hasattr(audio_processor, 'instrumental_with_backing_path') and audio_processor.instrumental_with_backing_path:
        if os.path.exists(audio_processor.instrumental_with_backing_path):
            gcs_path = f"jobs/{job_id}/stems/instrumental_with_backing.flac"
            url = storage.upload_file(audio_processor.instrumental_with_backing_path, gcs_path)
            job_manager.update_file_url(job_id, 'stems', 'instrumental_with_backing', url)
            logger.info(f"Job {job_id}: Uploaded instrumental with backing vocals")

