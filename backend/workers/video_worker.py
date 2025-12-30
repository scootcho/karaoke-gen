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

Observability:
- All operations wrapped in tracing spans for Cloud Trace visibility
- Logs include [job:ID] prefix for easy filtering in Cloud Logging
- Worker start/end timing logged with WORKER_START/WORKER_END markers
"""
import logging
import os
import shutil
import tempfile
import time
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
from backend.workers.worker_logging import create_job_logger, setup_job_logging, job_logging_context
from backend.services.tracing import job_span, add_span_event, add_span_attribute

# Import from karaoke_gen package - reuse existing implementation
from karaoke_gen.karaoke_finalise.karaoke_finalise import KaraokeFinalise


logger = logging.getLogger(__name__)


# Loggers to capture for video worker
# Include the full module path to properly capture KaraokeFinalise logs
VIDEO_WORKER_LOGGERS = [
    "karaoke_gen.karaoke_finalise",
    "karaoke_gen.karaoke_finalise.karaoke_finalise",  # The actual logger name from __name__
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
    start_time = time.time()
    job_manager = JobManager()
    storage = StorageService()
    settings = get_settings()
    
    # Create job logger for remote debugging
    job_log = create_job_logger(job_id, "video")
    
    # Log with structured markers for easy Cloud Logging queries
    logger.info(f"[job:{job_id}] WORKER_START worker=video")
    
    # Set up log capture for KaraokeFinalise
    log_handler = setup_job_logging(job_id, "video", *VIDEO_WORKER_LOGGERS)
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"[job:{job_id}] Job not found")
        return False
    
    # Validate prerequisites
    if not _validate_prerequisites(job):
        logger.error(f"[job:{job_id}] Prerequisites not met for video generation")
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
        # Wrap entire worker in a tracing span
        with job_span("video-worker", job_id, {"artist": job.artist, "title": job.title}) as root_span:
            # Use job_logging_context for proper log isolation when multiple jobs run concurrently
            # This ensures logs from third-party libraries (karaoke_gen.karaoke_finalise) are only
            # captured by this job's handler, not handlers from other concurrent jobs
            with job_logging_context(job_id):
                job_log.info(f"Starting video finalization for {job.artist} - {job.title}")
                logger.info(f"[job:{job_id}] Starting video generation for {job.artist} - {job.title}")
            
            # Transition to GENERATING_VIDEO state
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.GENERATING_VIDEO,
                progress=70,
                message="Preparing files for video generation"
            )
            
            # Download and set up files in the format KaraokeFinalise expects
            base_name = f"{job.artist} - {job.title}"
            with job_span("download-files", job_id):
                job_log.info("Downloading files from GCS (this may take a few minutes for large files)...")
                await _setup_working_directory(job_id, job, storage, temp_dir, base_name, job_log)
                job_log.info("All files downloaded successfully")
            
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
            # Batch 3: If user provided existing instrumental, use that; otherwise use AI-separated
            instrumental_selection = job.state_data['instrumental_selection']
            existing_instrumental_path = getattr(job, 'existing_instrumental_gcs_path', None)
            
            if existing_instrumental_path:
                # User provided existing instrumental
                ext = Path(existing_instrumental_path).suffix.lower()
                instrumental_file = os.path.join(temp_dir, f"{base_name} (Instrumental User){ext}")
                instrumental_source = "user-provided"
            else:
                # Use AI-separated instrumental
                instrumental_suffix = "Clean" if instrumental_selection == 'clean' else "Backing"
                instrumental_file = os.path.join(temp_dir, f"{base_name} (Instrumental {instrumental_suffix}).flac")
                instrumental_source = instrumental_selection
            
            # Transition to encoding state
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.ENCODING,
                progress=75,
                message="Encoding videos (15-20 min)"
            )
            
            # Get countdown padding info from lyrics metadata
            # This ensures instrumental is padded to match vocals if countdown was added
            lyrics_metadata = job.state_data.get('lyrics_metadata', {})
            countdown_padding_seconds = None
            if lyrics_metadata.get('has_countdown_padding'):
                countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)
                job_log.info(f"Countdown padding detected: {countdown_padding_seconds}s - instrumental will be padded if needed")
            
            # Log finalization parameters
            job_log.info("Creating KaraokeFinalise with parameters:")
            job_log.info(f"  enable_cdg: {getattr(job, 'enable_cdg', False)}")
            job_log.info(f"  enable_txt: {getattr(job, 'enable_txt', False)}")
            job_log.info(f"  brand_prefix: {getattr(job, 'brand_prefix', None)}")
            job_log.info(f"  discord_webhook: {'configured' if getattr(job, 'discord_webhook_url', None) else 'not configured'}")
            job_log.info(f"  instrumental source: {instrumental_source}")
            job_log.info(f"  countdown_padding_seconds: {countdown_padding_seconds}")
            if existing_instrumental_path:
                job_log.info(f"  using user-provided instrumental (selection was: {instrumental_selection})")
            
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
                # Audio synchronization - ensure instrumental matches vocal padding
                countdown_padding_seconds=countdown_padding_seconds,
            )
            
            # Call process() - this does ALL the work:
            # - Encodes to 4 video formats
            # - Generates CDG/TXT packages if enabled
            # - Posts Discord notification if configured
            # - Handles brand code generation
            with job_span("karaoke-finalise", job_id) as finalise_span:
                finalise_start = time.time()
                job_log.info("Starting KaraokeFinalise.process() - this may take 15-20 minutes...")
                logger.info(f"[job:{job_id}] Starting KaraokeFinalise.process()")
                add_span_event("finalise_started")
                
                result = finalise.process()
                
                finalise_duration = time.time() - finalise_start
                finalise_span.set_attribute("duration_seconds", finalise_duration)
                add_span_event("finalise_completed", {"duration_seconds": finalise_duration})
            
            job_log.info("KaraokeFinalise.process() complete!")
            if result.get('brand_code'):
                job_log.info(f"Brand code: {result.get('brand_code')}")
            logger.info(f"[job:{job_id}] KaraokeFinalise.process() complete in {finalise_duration:.1f}s")
            logger.info(f"[job:{job_id}] Brand code: {result.get('brand_code')}")
            
            # Native API distribution uploads (used by remote CLI instead of rclone)
            with job_span("distribution", job_id):
                await _handle_native_distribution(
                    job_id=job_id,
                    job=job,
                    job_log=job_log,
                    job_manager=job_manager,
                    temp_dir=temp_dir,
                    result=result,
                    storage=storage,
                )
            
            # Upload generated files to GCS
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.PACKAGING,
                progress=95,
                message="Uploading final files"
            )
            
            with job_span("upload-results", job_id):
                await _upload_results(job_id, job_manager, storage, temp_dir, result)
            
            # Mark job as complete
            logger.info(f"[job:{job_id}] Video generation complete")
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.COMPLETE,
                progress=100,
                message="Karaoke generation complete!"
            )
            
            # Store result metadata in job
            # NOTE: Must include dropbox_link and gdrive_files from result, since
            # _handle_native_distribution already saved them but job.state_data
            # is stale (fetched before distribution ran)
            job_manager.update_job(job_id, {
                'state_data': {
                    **job.state_data,
                    'brand_code': result.get('brand_code'),
                    'youtube_url': result.get('youtube_url'),
                    'dropbox_link': result.get('dropbox_link'),
                    'gdrive_files': result.get('gdrive_files'),
                }
            })
            
            duration = time.time() - start_time
            root_span.set_attribute("duration_seconds", duration)
            root_span.set_attribute("brand_code", result.get('brand_code', ''))
            logger.info(f"[job:{job_id}] WORKER_END worker=video status=success duration={duration:.1f}s")
            return True
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[job:{job_id}] WORKER_END worker=video status=error duration={duration:.1f}s error={e}")
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


async def _handle_native_distribution(
    job_id: str,
    job,
    job_log,
    job_manager: JobManager,
    temp_dir: str,
    result: Dict[str, Any],
    storage: StorageService = None,
) -> None:
    """
    Handle distribution uploads using native APIs (Dropbox SDK, Google Drive API).

    This is used by the remote CLI instead of rclone-based uploads.
    The native APIs provide:
    - Better error handling and retry logic
    - No need for rclone binary in container
    - Credentials managed via Secret Manager

    Args:
        job_id: Job ID
        job: Job object with dropbox_path and gdrive_folder_id fields
        job_log: Job-specific logger
        job_manager: Job manager for updating job state
        temp_dir: Temporary directory with output files
        result: Result dict from KaraokeFinalise.process()
        storage: StorageService instance for downloading stems/lyrics
    """
    brand_code = result.get('brand_code')
    base_name = f"{job.artist} - {job.title}"
    
    # Check if we should preserve existing brand code (Batch 6: --keep-brand-code)
    keep_brand_code = getattr(job, 'keep_brand_code', None)
    if keep_brand_code:
        brand_code = keep_brand_code
        result['brand_code'] = brand_code
        job_log.info(f"Using preserved brand code: {brand_code}")
    
    # Upload to Dropbox using native SDK
    dropbox_path = getattr(job, 'dropbox_path', None)
    brand_prefix = getattr(job, 'brand_prefix', None)
    
    if dropbox_path and brand_prefix:
        try:
            from backend.services.dropbox_service import get_dropbox_service
            
            dropbox = get_dropbox_service()
            
            if not dropbox.is_configured:
                job_log.warning("Dropbox credentials not configured - skipping upload")
            else:
                job_log.info(f"Starting native Dropbox upload to {dropbox_path}")
                
                # Calculate brand code from existing folders (if not already generated)
                if not brand_code:
                    brand_code = dropbox.get_next_brand_code(dropbox_path, brand_prefix)
                    result['brand_code'] = brand_code
                    job_log.info(f"Generated brand code: {brand_code}")
                
                # Prepare full distribution directory with stems/ and lyrics/ subfolders
                # This must be done before upload to ensure complete output structure
                if storage:
                    await _prepare_distribution_directory(
                        job_id=job_id,
                        job=job,
                        storage=storage,
                        temp_dir=temp_dir,
                        base_name=base_name,
                        job_log=job_log,
                    )

                # Create folder name and upload files
                folder_name = f"{brand_code} - {base_name}"
                remote_folder = f"{dropbox_path}/{folder_name}"

                job_log.info(f"Uploading to Dropbox folder: {remote_folder}")
                dropbox.upload_folder(temp_dir, remote_folder)
                
                # Create sharing link
                try:
                    sharing_link = dropbox.create_shared_link(remote_folder)
                    result['dropbox_link'] = sharing_link
                    job_log.info(f"Dropbox sharing link: {sharing_link}")
                except Exception as e:
                    job_log.warning(f"Failed to create Dropbox sharing link: {e}")
                
                job_log.info("Native Dropbox upload complete")
                
        except ImportError as e:
            job_log.warning(f"Dropbox SDK not installed: {e}")
        except Exception as e:
            job_log.error(f"Native Dropbox upload failed: {e}", exc_info=True)
            # Don't fail the job - distribution is optional
    
    # Upload to Google Drive using native API
    gdrive_folder_id = getattr(job, 'gdrive_folder_id', None)
    
    if gdrive_folder_id:
        try:
            from backend.services.gdrive_service import get_gdrive_service
            
            gdrive = get_gdrive_service()
            
            if not gdrive.is_configured:
                job_log.warning("Google Drive credentials not configured - skipping upload")
            else:
                job_log.info(f"Starting native Google Drive upload to folder {gdrive_folder_id}")
                
                # Use brand code from Dropbox or generate placeholder
                upload_brand_code = brand_code or f"{brand_prefix or 'TRACK'}-0000"
                
                # Map result keys to expected keys for upload_to_public_share
                output_files = {
                    'final_karaoke_lossy_mp4': result.get('final_video_lossy'),
                    'final_karaoke_lossy_720p_mp4': result.get('final_video_720p'),
                    'final_karaoke_cdg_zip': result.get('final_karaoke_cdg_zip'),
                }
                
                uploaded = gdrive.upload_to_public_share(
                    root_folder_id=gdrive_folder_id,
                    brand_code=upload_brand_code,
                    base_name=base_name,
                    output_files=output_files,
                )
                
                result['gdrive_files'] = uploaded
                job_log.info(f"Google Drive upload complete: {len(uploaded)} files uploaded")
                
        except ImportError as e:
            job_log.warning(f"Google API packages not installed: {e}")
        except Exception as e:
            job_log.error(f"Native Google Drive upload failed: {e}", exc_info=True)
            # Don't fail the job - distribution is optional
    
    # Update job state_data with brand code and links
    if brand_code or result.get('dropbox_link') or result.get('gdrive_files'):
        try:
            job_manager.update_job(job_id, {
                'state_data': {
                    **job.state_data,
                    'brand_code': brand_code,
                    'dropbox_link': result.get('dropbox_link'),
                    'gdrive_files': result.get('gdrive_files'),
                }
            })
        except Exception as e:
            job_log.warning(f"Failed to update job state_data: {e}")


def _validate_prerequisites(job) -> bool:
    """Validate that all prerequisites are met for video generation."""
    # Check instrumental selection
    instrumental_selection = job.state_data.get('instrumental_selection')
    if not instrumental_selection:
        logger.error(f"Job {job.job_id}: No instrumental selected")
        return False
    
    # 'custom' is valid when user provided existing_instrumental
    if instrumental_selection not in ['clean', 'with_backing', 'custom']:
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
    
    # Check instrumental exists - for 'custom', check existing_instrumental_gcs_path instead of stems
    if instrumental_selection == 'custom':
        existing_instrumental_path = getattr(job, 'existing_instrumental_gcs_path', None)
        if not existing_instrumental_path:
            logger.error(f"Job {job.job_id}: Custom instrumental selected but no existing_instrumental_gcs_path")
            return False
        return True  # Other stem checks not needed for custom instrumental
    
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
    base_name: str,
    job_log=None
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
    def log_progress(message: str):
        """Log to both module logger and job logger if available."""
        logger.info(f"Job {job_id}: {message}")
        if job_log:
            job_log.info(message)
    
    log_progress("Setting up working directory")
    
    # Download title screen
    log_progress("Downloading title screen...")
    title_url = job.file_urls['screens']['title']
    title_path = os.path.join(temp_dir, f"{base_name} (Title).mov")
    storage.download_file(title_url, title_path)
    log_progress("Downloaded title screen")
    
    # Download end screen
    log_progress("Downloading end screen...")
    end_url = job.file_urls['screens']['end']
    end_path = os.path.join(temp_dir, f"{base_name} (End).mov")
    storage.download_file(end_url, end_path)
    log_progress("Downloaded end screen")
    
    # Download lyrics video (with vocals) - this is the largest file, ~1-2GB
    log_progress("Downloading karaoke video (largest file, may take 1-2 minutes)...")
    lyrics_video_url = job.file_urls['videos']['with_vocals']
    lyrics_video_path = os.path.join(temp_dir, f"{base_name} (With Vocals).mov")
    storage.download_file(lyrics_video_url, lyrics_video_path)
    log_progress("Downloaded karaoke video")
    
    # Download instrumental - either user-provided existing instrumental or AI-separated
    existing_instrumental_path = getattr(job, 'existing_instrumental_gcs_path', None)
    instrumental_selection = job.state_data['instrumental_selection']
    
    if existing_instrumental_path:
        # Batch 3: Use user-provided existing instrumental
        ext = Path(existing_instrumental_path).suffix.lower()
        instrumental_path = os.path.join(temp_dir, f"{base_name} (Instrumental User){ext}")
        log_progress(f"Downloading user-provided existing instrumental...")
        storage.download_file(existing_instrumental_path, instrumental_path)
        log_progress("Downloaded user-provided instrumental")
    else:
        # Use AI-separated instrumental based on selection
        instrumental_key = 'instrumental_clean' if instrumental_selection == 'clean' else 'instrumental_with_backing'
        instrumental_url = job.file_urls['stems'][instrumental_key]
        instrumental_suffix = "Clean" if instrumental_selection == 'clean' else "Backing"
        instrumental_path = os.path.join(temp_dir, f"{base_name} (Instrumental {instrumental_suffix}).flac")
        log_progress(f"Downloading {instrumental_selection} instrumental audio...")
        storage.download_file(instrumental_url, instrumental_path)
        log_progress(f"Downloaded instrumental ({instrumental_selection})")
    
    # Download LRC file if available (needed for CDG/TXT)
    lyrics_urls = job.file_urls.get('lyrics', {})
    if 'lrc' in lyrics_urls:
        lrc_url = lyrics_urls['lrc']
        lrc_path = os.path.join(temp_dir, f"{base_name} (Karaoke).lrc")
        storage.download_file(lrc_url, lrc_path)
        log_progress("Downloaded LRC file")
    
    # Download title/end JPG files (used for YouTube thumbnail)
    screens = job.file_urls.get('screens', {})
    if screens.get('title_jpg'):
        title_jpg_path = os.path.join(temp_dir, f"{base_name} (Title).jpg")
        storage.download_file(screens['title_jpg'], title_jpg_path)
        log_progress("Downloaded title JPG for thumbnail")
    
    if screens.get('end_jpg'):
        end_jpg_path = os.path.join(temp_dir, f"{base_name} (End).jpg")
        storage.download_file(screens['end_jpg'], end_jpg_path)
        log_progress("Downloaded end JPG")


async def _prepare_distribution_directory(
    job_id: str,
    job,
    storage: StorageService,
    temp_dir: str,
    base_name: str,
    job_log=None
) -> None:
    """
    Prepare the full distribution directory structure matching local CLI output.

    Creates:
    - stems/ subfolder with all audio stems (proper model names)
    - lyrics/ subfolder with intermediate lyrics files
    - Root-level instrumentals with proper model names

    This ensures the Dropbox upload contains the complete output structure.
    """
    def log_progress(message: str):
        """Log to both module logger and job logger if available."""
        logger.info(f"Job {job_id}: {message}")
        if job_log:
            job_log.info(message)

    log_progress("Preparing full distribution directory structure")

    # Get model names from state_data (stored by audio_worker)
    model_names = job.state_data.get('model_names', {})
    clean_model = model_names.get('clean_instrumental_model', 'model_bs_roformer_ep_317_sdr_12.9755.ckpt')
    backing_models = model_names.get('backing_vocals_models', ['mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt'])
    other_models = model_names.get('other_stems_models', ['htdemucs_6s.yaml'])
    backing_model = backing_models[0] if backing_models else 'mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt'
    other_model = other_models[0] if other_models else 'htdemucs_6s.yaml'

    # Create stems subdirectory
    stems_dir = os.path.join(temp_dir, "stems")
    os.makedirs(stems_dir, exist_ok=True)

    # Create lyrics subdirectory
    lyrics_dir = os.path.join(temp_dir, "lyrics")
    os.makedirs(lyrics_dir, exist_ok=True)

    stems = job.file_urls.get('stems', {})
    lyrics = job.file_urls.get('lyrics', {})

    # --- Download stems to stems/ subfolder with proper model names ---

    # Clean up simplified-named instrumentals from _setup_working_directory
    # These were needed for KaraokeFinalise but shouldn't go to distribution
    simplified_instrumental_patterns = [
        f"{base_name} (Instrumental Clean).flac",
        f"{base_name} (Instrumental Backing).flac",
    ]
    for pattern in simplified_instrumental_patterns:
        simplified_path = os.path.join(temp_dir, pattern)
        if os.path.exists(simplified_path):
            os.remove(simplified_path)
            log_progress(f"Removed simplified instrumental: {pattern}")

    # Clean instrumental (from clean_instrumental_model)
    if stems.get('instrumental_clean'):
        dest_path = os.path.join(stems_dir, f"{base_name} (Instrumental {clean_model}).flac")
        storage.download_file(stems['instrumental_clean'], dest_path)
        log_progress(f"Downloaded clean instrumental to stems/")

        # Also copy to root level for distribution
        root_path = os.path.join(temp_dir, f"{base_name} (Instrumental {clean_model}).flac")
        shutil.copy2(dest_path, root_path)

    # Clean vocals (from clean_instrumental_model)
    if stems.get('vocals_clean'):
        dest_path = os.path.join(stems_dir, f"{base_name} (Vocals {clean_model}).flac")
        storage.download_file(stems['vocals_clean'], dest_path)
        log_progress(f"Downloaded clean vocals to stems/")

    # Instrumental with backing vocals (from backing_vocals_model)
    if stems.get('instrumental_with_backing'):
        dest_path = os.path.join(stems_dir, f"{base_name} (Instrumental +BV {backing_model}).flac")
        storage.download_file(stems['instrumental_with_backing'], dest_path)
        log_progress(f"Downloaded instrumental+BV to stems/")

        # Also copy to root level for distribution
        root_path = os.path.join(temp_dir, f"{base_name} (Instrumental +BV {backing_model}).flac")
        shutil.copy2(dest_path, root_path)

    # Lead vocals (from backing_vocals_model)
    if stems.get('lead_vocals'):
        dest_path = os.path.join(stems_dir, f"{base_name} (Lead Vocals {backing_model}).flac")
        storage.download_file(stems['lead_vocals'], dest_path)
        log_progress(f"Downloaded lead vocals to stems/")

    # Backing vocals (from backing_vocals_model)
    if stems.get('backing_vocals'):
        dest_path = os.path.join(stems_dir, f"{base_name} (Backing Vocals {backing_model}).flac")
        storage.download_file(stems['backing_vocals'], dest_path)
        log_progress(f"Downloaded backing vocals to stems/")

    # Other stems (from other_stems_model - typically htdemucs_6s)
    other_stem_keys = ['bass', 'drums', 'guitar', 'piano', 'other']
    for stem_key in other_stem_keys:
        if stems.get(stem_key):
            stem_name = stem_key.capitalize()
            dest_path = os.path.join(stems_dir, f"{base_name} ({stem_name} {other_model}).flac")
            storage.download_file(stems[stem_key], dest_path)
            log_progress(f"Downloaded {stem_key} to stems/")

    # --- Download lyrics files to lyrics/ subfolder ---

    # Common lyrics file types
    lyrics_file_keys = ['lrc', 'ass', 'srt', 'txt', 'json', 'original_json', 'corrected_json']
    for lyrics_key in lyrics_file_keys:
        if lyrics.get(lyrics_key):
            # Determine proper extension
            ext_map = {
                'lrc': '.lrc',
                'ass': '.ass',
                'srt': '.srt',
                'txt': '.txt',
                'json': '.json',
                'original_json': '_original.json',
                'corrected_json': '_corrected.json',
            }
            ext = ext_map.get(lyrics_key, f'.{lyrics_key}')
            dest_path = os.path.join(lyrics_dir, f"{base_name} (Karaoke){ext}")
            try:
                storage.download_file(lyrics[lyrics_key], dest_path)
                log_progress(f"Downloaded {lyrics_key} to lyrics/")
            except Exception as e:
                log_progress(f"Could not download {lyrics_key}: {e}")

    log_progress(f"Distribution directory prepared with stems/ and lyrics/ subfolders")


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


# ==================== CLI Entry Point for Cloud Run Jobs ====================
# This allows the video worker to be run as a standalone Cloud Run Job.
# Usage: python -m backend.workers.video_worker --job-id <job_id>

def main():
    """
    CLI entry point for running video worker as a Cloud Run Job.
    
    This is used when video encoding needs more than 30 minutes
    (the Cloud Tasks timeout limit). Cloud Run Jobs support up to 24 hours.
    
    Usage:
        python -m backend.workers.video_worker --job-id abc123
    
    Environment Variables:
        GOOGLE_CLOUD_PROJECT: GCP project ID (required)
        GCS_BUCKET_NAME: Storage bucket name (required)
    """
    import argparse
    import asyncio
    import sys
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Video encoding worker for karaoke generation"
    )
    parser.add_argument(
        "--job-id",
        required=True,
        help="Job ID to process"
    )
    
    args = parser.parse_args()
    job_id = args.job_id
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info(f"Starting video worker CLI for job {job_id}")
    
    # Run the async worker function
    try:
        success = asyncio.run(generate_video(job_id))
        if success:
            logger.info(f"Video generation completed successfully for job {job_id}")
            sys.exit(0)
        else:
            logger.error(f"Video generation failed for job {job_id}")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Video worker crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
