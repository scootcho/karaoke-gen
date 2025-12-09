"""
Video generation and finalization worker.

This worker uses KaraokeFinalise from the karaoke_gen package to handle:
1. Video encoding (4 formats)
2. CDG/TXT package generation
3. Discord notifications
4. Brand code generation
5. All other finalisation features

The worker's job is simply to:
1. Download files from GCS and set up the directory structure KaraokeFinalise expects
2. Instantiate KaraokeFinalise with parameters from the job
3. Call process()
4. Upload results back to GCS

This reuses 100% of the existing karaoke_gen functionality.
"""
import logging
import os
import shutil
import tempfile
import json
from typing import Optional, Dict, Any
from pathlib import Path

from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.services.rclone_service import get_rclone_service
from backend.services.youtube_service import get_youtube_service
from backend.config import get_settings
from backend.workers.style_helper import load_style_config
from backend.workers.worker_logging import create_job_logger, setup_job_logging

# Import from karaoke_gen package - reuse existing implementation
from karaoke_gen.karaoke_finalise.karaoke_finalise import KaraokeFinalise


logger = logging.getLogger(__name__)


# Loggers to capture for video worker
VIDEO_WORKER_LOGGERS = [
    "karaoke_gen.karaoke_finalise",
]


async def generate_video(job_id: str) -> bool:
    """
    Generate final karaoke videos using KaraokeFinalise.
    
    This sets up the directory structure and calls KaraokeFinalise.process()
    which handles all encoding, packaging, and notifications.
    
    Args:
        job_id: Job ID to process
        
    Returns:
        True if successful, False otherwise
    """
    job_manager = JobManager()
    storage = StorageService()
    settings = get_settings()
    
    # Create job logger for remote debugging
    job_log = create_job_logger(job_id, "video")
    
    # Set up log capture for KaraokeFinalise
    log_handler = setup_job_logging(job_id, "video", *VIDEO_WORKER_LOGGERS)
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return False
    
    # Validate prerequisites
    if not _validate_prerequisites(job):
        logger.error(f"Job {job_id}: Prerequisites not met for video generation")
        return False
    
    # Create temporary working directory
    temp_dir = tempfile.mkdtemp(prefix=f"karaoke_video_{job_id}_")
    original_cwd = os.getcwd()
    
    # Set up rclone config if needed for Dropbox upload
    rclone_service = None
    if getattr(job, 'organised_dir_rclone_root', None):
        rclone_service = get_rclone_service()
        if rclone_service.setup_rclone_config():
            job_log.info("Rclone config loaded for Dropbox upload")
        else:
            job_log.warning("Rclone config not available - Dropbox upload will be skipped")
    
    # Load YouTube credentials if needed
    youtube_credentials = None
    if getattr(job, 'enable_youtube_upload', False):
        youtube_service = get_youtube_service()
        if youtube_service.is_configured:
            youtube_credentials = youtube_service.get_credentials_dict()
            job_log.info("YouTube credentials loaded for video upload")
        else:
            job_log.warning("YouTube credentials not available - upload will be skipped")
    
    try:
        job_log.info(f"Starting video finalization for {job.artist} - {job.title}")
        logger.info(f"Starting video generation for job {job_id}")
        
        # Transition to GENERATING_VIDEO state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.GENERATING_VIDEO,
            progress=70,
            message="Preparing files for video generation"
        )
        
        # Download and set up files in the format KaraokeFinalise expects
        base_name = f"{job.artist} - {job.title}"
        job_log.info("Downloading files from GCS...")
        await _setup_working_directory(job_id, job, storage, temp_dir, base_name)
        job_log.info("Files downloaded successfully")
        
        # Load style config for CDG styles
        job_log.info("Loading CDG style configuration...")
        style_config = await load_style_config(job, storage, temp_dir)
        cdg_styles = style_config.get_cdg_styles()
        if cdg_styles:
            job_log.info("CDG styles loaded from custom configuration")
        else:
            job_log.info("Using default CDG styles")
        
        # Change to working directory (KaraokeFinalise works in cwd)
        os.chdir(temp_dir)
        
        # Get the selected instrumental file path
        instrumental_selection = job.state_data['instrumental_selection']
        instrumental_suffix = "Clean" if instrumental_selection == 'clean' else "Backing"
        instrumental_file = os.path.join(temp_dir, f"{base_name} (Instrumental {instrumental_suffix}).flac")
        
        # Transition to encoding state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.ENCODING,
            progress=75,
            message="Encoding videos (15-20 min)"
        )
        
        # Log finalization parameters
        job_log.info("Creating KaraokeFinalise with parameters:")
        job_log.info(f"  enable_cdg: {getattr(job, 'enable_cdg', False)}")
        job_log.info(f"  enable_txt: {getattr(job, 'enable_txt', False)}")
        job_log.info(f"  brand_prefix: {getattr(job, 'brand_prefix', None)}")
        job_log.info(f"  discord_webhook: {'configured' if getattr(job, 'discord_webhook_url', None) else 'not configured'}")
        job_log.info(f"  instrumental: {instrumental_selection}")
        
        # Create KaraokeFinalise with ALL the parameters from the job
        # This reuses all existing functionality!
        
        # Set up YouTube description file if template is provided
        youtube_desc_path = None
        if youtube_credentials and getattr(job, 'youtube_description_template', None):
            youtube_desc_path = os.path.join(temp_dir, "youtube_description.txt")
            with open(youtube_desc_path, 'w') as f:
                f.write(job.youtube_description_template)
            job_log.info("YouTube description template written to temp file")
        
        finalise = KaraokeFinalise(
            logger=logger,
            log_level=logging.INFO,
            dry_run=False,
            instrumental_format="flac",
            # CDG/TXT generation
            enable_cdg=getattr(job, 'enable_cdg', False),
            enable_txt=getattr(job, 'enable_txt', False),
            cdg_styles=cdg_styles,
            # Brand code and organization (server-side mode uses rclone)
            brand_prefix=getattr(job, 'brand_prefix', None),
            organised_dir=None,  # Not used in cloud - files stay in GCS
            organised_dir_rclone_root=getattr(job, 'organised_dir_rclone_root', None),
            public_share_dir=None,  # Not used in cloud
            # Notifications
            discord_webhook_url=getattr(job, 'discord_webhook_url', None),
            # YouTube upload (server-side with pre-loaded credentials)
            youtube_client_secrets_file=None,  # Not used with pre-stored credentials
            youtube_description_file=youtube_desc_path,
            user_youtube_credentials=youtube_credentials,  # Pre-loaded from Secret Manager
            rclone_destination=None,
            email_template_file=None,
            # Server-side optimizations
            non_interactive=True,
            server_side_mode=True,
            selected_instrumental_file=instrumental_file,
        )
        
        # Call process() - this does ALL the work:
        # - Encodes to 4 video formats
        # - Generates CDG/TXT packages if enabled
        # - Posts Discord notification if configured
        # - Handles brand code generation
        job_log.info("Starting KaraokeFinalise.process() - this may take 15-20 minutes...")
        logger.info(f"Job {job_id}: Starting KaraokeFinalise.process()")
        result = finalise.process()
        
        job_log.info("KaraokeFinalise.process() complete!")
        if result.get('brand_code'):
            job_log.info(f"Brand code: {result.get('brand_code')}")
        logger.info(f"Job {job_id}: KaraokeFinalise.process() complete")
        logger.info(f"Job {job_id}: Brand code: {result.get('brand_code')}")
        
        # Upload generated files to GCS
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.PACKAGING,
            progress=95,
            message="Uploading final files"
        )
        
        await _upload_results(job_id, job_manager, storage, temp_dir, result)
        
        # Mark job as complete
        logger.info(f"Job {job_id}: Video generation complete")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.COMPLETE,
            progress=100,
            message="Karaoke generation complete!"
        )
        
        # Store result metadata in job
        job_manager.update_job(job_id, {
            'state_data': {
                **job.state_data,
                'brand_code': result.get('brand_code'),
                'youtube_url': result.get('youtube_url'),
            }
        })
        
        return True
        
    except Exception as e:
        logger.error(f"Job {job_id}: Video generation failed: {e}", exc_info=True)
        job_manager.mark_job_failed(
            job_id=job_id,
            error_message=f"Video generation failed: {str(e)}",
            error_details={"stage": "video_generation", "error": str(e)}
        )
        return False
        
    finally:
        # Restore original working directory
        os.chdir(original_cwd)
        
        # Remove log handler to avoid duplicate logging on future runs
        for logger_name in VIDEO_WORKER_LOGGERS:
            try:
                logging.getLogger(logger_name).removeHandler(log_handler)
            except Exception:
                pass
        
        # Cleanup rclone config file
        if rclone_service:
            rclone_service.cleanup()
        
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")


def _validate_prerequisites(job) -> bool:
    """Validate that all prerequisites are met for video generation."""
    # Check instrumental selection
    instrumental_selection = job.state_data.get('instrumental_selection')
    if not instrumental_selection:
        logger.error(f"Job {job.job_id}: No instrumental selected")
        return False
    
    if instrumental_selection not in ['clean', 'with_backing']:
        logger.error(f"Job {job.job_id}: Invalid instrumental selection: {instrumental_selection}")
        return False
    
    # Check screens exist
    screens = job.file_urls.get('screens', {})
    if not screens.get('title') or not screens.get('end'):
        logger.error(f"Job {job.job_id}: Missing title or end screen")
        return False
    
    # Check lyrics video exists
    videos = job.file_urls.get('videos', {})
    if not videos.get('with_vocals'):
        logger.error(f"Job {job.job_id}: Missing lyrics video")
        return False
    
    # Check instrumental exists
    stems = job.file_urls.get('stems', {})
    instrumental_key = 'instrumental_clean' if instrumental_selection == 'clean' else 'instrumental_with_backing'
    if not stems.get(instrumental_key):
        logger.error(f"Job {job.job_id}: Missing instrumental: {instrumental_key}")
        return False
    
    return True


async def _setup_working_directory(
    job_id: str,
    job,
    storage: StorageService,
    temp_dir: str,
    base_name: str
) -> None:
    """
    Download files from GCS and set up the directory structure KaraokeFinalise expects.
    
    KaraokeFinalise.process() looks for files with specific naming conventions:
    - {base_name} (Title).mov
    - {base_name} (End).mov  
    - {base_name} (With Vocals).mov
    - {base_name} (Karaoke).lrc
    - Instrumental audio file
    """
    logger.info(f"Job {job_id}: Setting up working directory")
    
    # Download title screen
    title_url = job.file_urls['screens']['title']
    title_path = os.path.join(temp_dir, f"{base_name} (Title).mov")
    storage.download_file(title_url, title_path)
    logger.info(f"Job {job_id}: Downloaded title screen")
    
    # Download end screen
    end_url = job.file_urls['screens']['end']
    end_path = os.path.join(temp_dir, f"{base_name} (End).mov")
    storage.download_file(end_url, end_path)
    logger.info(f"Job {job_id}: Downloaded end screen")
    
    # Download lyrics video (with vocals)
    lyrics_video_url = job.file_urls['videos']['with_vocals']
    lyrics_video_path = os.path.join(temp_dir, f"{base_name} (With Vocals).mov")
    storage.download_file(lyrics_video_url, lyrics_video_path)
    logger.info(f"Job {job_id}: Downloaded lyrics video")
    
    # Download selected instrumental
    instrumental_selection = job.state_data['instrumental_selection']
    instrumental_key = 'instrumental_clean' if instrumental_selection == 'clean' else 'instrumental_with_backing'
    instrumental_url = job.file_urls['stems'][instrumental_key]
    instrumental_suffix = "Clean" if instrumental_selection == 'clean' else "Backing"
    instrumental_path = os.path.join(temp_dir, f"{base_name} (Instrumental {instrumental_suffix}).flac")
    storage.download_file(instrumental_url, instrumental_path)
    logger.info(f"Job {job_id}: Downloaded instrumental ({instrumental_selection})")
    
    # Download LRC file if available (needed for CDG/TXT)
    lyrics_urls = job.file_urls.get('lyrics', {})
    if 'lrc' in lyrics_urls:
        lrc_url = lyrics_urls['lrc']
        lrc_path = os.path.join(temp_dir, f"{base_name} (Karaoke).lrc")
        storage.download_file(lrc_url, lrc_path)
        logger.info(f"Job {job_id}: Downloaded LRC file")
    
    # Also create title/end JPG files if needed (KaraokeFinalise checks for these)
    # For now, we'll create placeholder files - the actual MOV files are what matter
    title_jpg_path = os.path.join(temp_dir, f"{base_name} (Title).jpg")
    end_jpg_path = os.path.join(temp_dir, f"{base_name} (End).jpg")
    Path(title_jpg_path).touch()
    Path(end_jpg_path).touch()


async def _upload_results(
    job_id: str,
    job_manager: JobManager,
    storage: StorageService,
    temp_dir: str,
    result: Dict[str, Any]
) -> None:
    """Upload generated files to GCS."""
    
    # Map of result keys to GCS paths
    file_mappings = [
        ('final_video', 'finals', 'lossless_4k_mp4'),
        ('final_video_mkv', 'finals', 'lossless_4k_mkv'),
        ('final_video_lossy', 'finals', 'lossy_4k_mp4'),
        ('final_video_720p', 'finals', 'lossy_720p_mp4'),
        ('final_karaoke_cdg_zip', 'packages', 'cdg_zip'),
        ('final_karaoke_txt_zip', 'packages', 'txt_zip'),
    ]
    
    for result_key, category, file_key in file_mappings:
        if result_key in result and result[result_key]:
            local_path = result[result_key]
            if os.path.exists(local_path):
                ext = Path(local_path).suffix
                gcs_path = f"jobs/{job_id}/{category}/{file_key}{ext}"
                try:
                    url = storage.upload_file(local_path, gcs_path)
                    job_manager.update_file_url(job_id, category, file_key, url)
                    logger.info(f"Job {job_id}: Uploaded {file_key}")
                except Exception as e:
                    logger.error(f"Job {job_id}: Failed to upload {file_key}: {e}")
