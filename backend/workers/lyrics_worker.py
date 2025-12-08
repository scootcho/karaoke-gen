"""
Lyrics transcription and correction worker.

Handles the lyrics processing track of parallel processing:
1. Fetch reference lyrics from multiple sources (Genius, Spotify, Musixmatch, LRCLib)
2. Transcribe audio with AudioShake API (1-2 min)
3. Run automatic correction using LyricsTranscriber
4. Generate corrections JSON for human review
5. Upload all data to GCS
6. Transition to AWAITING_REVIEW state

Re-uses:
- karaoke_gen.lyrics_processor.LyricsProcessor for lyrics fetching and orchestration
- lyrics_transcriber library (submodule) for transcription and correction
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
from backend.config import get_settings
from backend.workers.worker_logging import create_job_logger, setup_job_logging

# Import from karaoke_gen package
from karaoke_gen.lyrics_processor import LyricsProcessor


logger = logging.getLogger(__name__)


# Loggers to capture for lyrics worker (includes LyricsTranscriber internals)
LYRICS_WORKER_LOGGERS = [
    "karaoke_gen.lyrics_processor",
    "lyrics_transcriber",
    "lyrics_transcriber.core.controller",
    "lyrics_transcriber.lyrics",
    "lyrics_transcriber.correction",
    "lyrics_transcriber.transcribers",
]


def create_lyrics_processor(temp_dir: str, style_params_json: Optional[str] = None) -> LyricsProcessor:
    """
    Create a LyricsProcessor instance configured for Cloud Run processing.
    
    This reuses the karaoke_gen LyricsProcessor with settings optimized for Cloud Run:
    - Uses AudioShake API for transcription (via AUDIOSHAKE_API_TOKEN env var)
    - Uses Genius/Spotify/Musixmatch APIs for reference lyrics (via env vars)
    - Skips interactive review (will be handled by separate React UI)
    - Generates corrections JSON for review interface
    
    Args:
        temp_dir: Temporary directory for processing
        style_params_json: Optional path to style parameters JSON file
        
    Returns:
        Configured LyricsProcessor instance
    """
    # Configure logger for LyricsProcessor
    lyrics_logger = logging.getLogger("karaoke_gen.lyrics_processor")
    lyrics_logger.setLevel(logging.INFO)
    
    return LyricsProcessor(
        logger=lyrics_logger,
        style_params_json=style_params_json,
        lyrics_file=None,  # Will fetch from APIs
        skip_transcription=False,  # We want transcription
        skip_transcription_review=True,  # Skip interactive review (use React UI instead)
        render_video=False,  # Skip video generation for now (will be done after review)
        subtitle_offset_ms=0  # No offset by default
    )


async def process_lyrics_transcription(job_id: str) -> bool:
    """
    Process lyrics transcription and correction for a job using karaoke_gen.LyricsProcessor.
    
    This is the main entry point for the lyrics worker.
    Called asynchronously from the job submission endpoint.
    
    Runs in parallel with audio_worker, coordinated via job state.
    
    Workflow:
    1. Download audio from GCS
    2. Create LyricsProcessor instance
    3. Run transcription (calls AudioShake API internally)
    4. Fetch reference lyrics from Genius/Spotify/Musixmatch/LRCLib
    5. Run automatic correction using lyrics_transcriber library
    6. Generate corrections JSON for review interface
    7. Upload results to GCS
    8. Transition to AWAITING_REVIEW state
    
    Args:
        job_id: Job ID to process
        
    Returns:
        True if successful, False otherwise
    """
    job_manager = JobManager()
    storage = StorageService()
    settings = get_settings()
    
    # Create job logger for remote debugging
    job_log = create_job_logger(job_id, "lyrics")
    
    # Set up log capture for LyricsTranscriber and its dependencies
    # This ensures logs from the lyrics_transcriber library are also captured
    log_handler = setup_job_logging(job_id, "lyrics", *LYRICS_WORKER_LOGGERS)
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return False
    
    # Create temporary working directory
    temp_dir = tempfile.mkdtemp(prefix=f"karaoke_lyrics_{job_id}_")
    
    try:
        job_log.info(f"Starting lyrics transcription for {job.artist} - {job.title}")
        job_log.info(f"Log capture enabled for: {', '.join(LYRICS_WORKER_LOGGERS)}")
        logger.info(f"Starting lyrics transcription for job {job_id}")
        
        # Log environment configuration
        job_log.info("Checking API configuration...")
        if os.environ.get("GENIUS_API_TOKEN"):
            job_log.info("  Genius API: configured")
        else:
            job_log.warning("  Genius API: NOT configured")
        if os.environ.get("SPOTIFY_COOKIE_SP_DC"):
            job_log.info("  Spotify: configured")
        else:
            job_log.warning("  Spotify: NOT configured")
        if os.environ.get("RAPIDAPI_KEY"):
            job_log.info("  Musixmatch (RapidAPI): configured")
        else:
            job_log.warning("  Musixmatch (RapidAPI): NOT configured")
        
        # Ensure required environment variables are set
        if not os.environ.get("AUDIOSHAKE_API_TOKEN"):
            job_log.warning("AUDIOSHAKE_API_TOKEN not set - transcription may fail")
            logger.warning("AUDIOSHAKE_API_TOKEN not set - transcription may fail")
        
        # Download audio file from GCS (waits for audio worker if URL job)
        job_log.info("Downloading audio file from GCS...")
        audio_path = await download_audio(job_id, temp_dir, storage, job, job_manager)
        if not audio_path:
            raise Exception("Failed to download audio file")
        job_log.info(f"Audio downloaded: {os.path.basename(audio_path)}")
        
        # Update progress using state_data (don't change status during parallel processing)
        # The status is managed at a higher level - workers just track their progress
        job_manager.update_state_data(job_id, 'lyrics_progress', {
            'stage': 'transcribing',
            'progress': 10,
            'message': 'Starting lyrics transcription via AudioShake'
        })
        
        # Create LyricsProcessor instance (reuses karaoke_gen code)
        job_log.info("Creating LyricsProcessor instance...")
        lyrics_processor = create_lyrics_processor(temp_dir)
        
        # Run transcription + correction
        # This will:
        # 1. Fetch reference lyrics from Genius/Spotify/Musixmatch/LRCLib
        # 2. Transcribe audio via AudioShake API
        # 3. Run automatic correction with lyrics_transcriber
        # 4. Generate corrections JSON (no interactive review)
        # 5. Skip video generation (render_video=False)
        job_log.info("Starting LyricsTranscriber processing...")
        job_log.info(f"  Artist: {job.artist}")
        job_log.info(f"  Title: {job.title}")
        logger.info(f"Job {job_id}: Calling lyrics_processor.transcribe_lyrics()")
        result = lyrics_processor.transcribe_lyrics(
            input_audio_wav=audio_path,
            artist=job.artist,
            title=job.title,
            track_output_dir=temp_dir
        )
        
        job_log.info("Transcription processing complete")
        logger.info(f"Job {job_id}: Transcription complete, uploading results")
        
        # Upload lyrics results to GCS
        job_log.info("Uploading lyrics results to GCS...")
        await upload_lyrics_results(job_id, temp_dir, result, storage, job_manager, job_log)
        
        job_log.info("All lyrics data uploaded successfully")
        logger.info(f"Job {job_id}: All lyrics data uploaded successfully")
        
        # Update progress using state_data (don't change status during parallel processing)
        job_manager.update_state_data(job_id, 'lyrics_progress', {
            'stage': 'lyrics_complete',
            'progress': 45,
            'message': 'Lyrics transcription complete'
        })
        
        # Mark lyrics processing complete
        # This will check if audio is also complete and transition to next stage if so
        job_log.info("Lyrics worker complete, checking if audio is also done...")
        job_manager.mark_lyrics_complete(job_id)
        
        return True
        
    except Exception as e:
        job_log.error(f"Lyrics transcription failed: {str(e)}", exc_info=True)
        logger.error(f"Job {job_id}: Lyrics transcription failed: {e}", exc_info=True)
        job_manager.mark_job_failed(
            job_id=job_id,
            error_message=f"Lyrics transcription failed: {str(e)}",
            error_details={"stage": "lyrics_transcription", "error": str(e)}
        )
        return False
        
    finally:
        # Remove log handler to avoid duplicate logging on future runs
        for logger_name in LYRICS_WORKER_LOGGERS:
            try:
                logging.getLogger(logger_name).removeHandler(log_handler)
            except Exception:
                pass
        
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")


async def download_audio(
    job_id: str,
    temp_dir: str,
    storage: StorageService,
    job,
    job_manager: JobManager,
    max_wait_seconds: int = 300
) -> Optional[str]:
    """
    Download audio file from GCS to local temp directory.
    
    For URL jobs, the audio worker downloads from YouTube first and uploads to GCS.
    We wait for the input_media_gcs_path to be set by the audio worker.
    
    Args:
        job_id: Job ID
        temp_dir: Temporary directory for download
        storage: StorageService instance
        job: Job object
        job_manager: JobManager instance
        max_wait_seconds: Maximum time to wait for audio worker to download
    
    Returns:
        Path to downloaded audio file, or None if failed
    """
    import time
    
    try:
        # If input_media_gcs_path is already set, download directly
        if job.input_media_gcs_path:
            local_path = os.path.join(temp_dir, job.filename or "input.flac")
            storage.download_file(job.input_media_gcs_path, local_path)
            logger.info(f"Job {job_id}: Downloaded audio from {job.input_media_gcs_path} to {local_path}")
            return local_path
        
        # For URL jobs, wait for audio worker to download and upload to GCS
        if job.url:
            logger.info(f"Job {job_id}: Waiting for audio worker to download from URL...")
            
            start_time = time.time()
            poll_interval = 5  # seconds
            
            while time.time() - start_time < max_wait_seconds:
                # Refresh job from Firestore
                updated_job = job_manager.get_job(job_id)
                
                if updated_job and updated_job.input_media_gcs_path:
                    # Audio worker has uploaded the file
                    local_path = os.path.join(temp_dir, "input.flac")
                    storage.download_file(updated_job.input_media_gcs_path, local_path)
                    logger.info(f"Job {job_id}: Downloaded audio from {updated_job.input_media_gcs_path}")
                    return local_path
                
                # Check if audio worker failed
                if updated_job and updated_job.status == JobStatus.FAILED:
                    logger.error(f"Job {job_id}: Audio worker failed, cannot proceed with lyrics")
                    return None
                
                # Wait before next poll
                time.sleep(poll_interval)
            
            logger.error(f"Job {job_id}: Timed out waiting for audio download (waited {max_wait_seconds}s)")
            return None
        
        logger.error(f"Job {job_id}: No input_media_gcs_path found and no URL")
        return None
        
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to download audio: {e}", exc_info=True)
        return None


async def upload_lyrics_results(
    job_id: str,
    temp_dir: str,
    transcription_result: Dict[str, Any],
    storage: StorageService,
    job_manager: JobManager,
    job_log = None
) -> None:
    """
    Upload all lyrics transcription results to GCS.
    
    The transcription_result dict from LyricsProcessor.transcribe_lyrics() contains:
    - lrc_filepath: Path to LRC file (timed lyrics)
    - ass_filepath: Path to ASS file (karaoke subtitles, may be video file)
    
    Additional files in lyrics directory:
    - Corrections JSON (for review interface)
    - Reference lyrics (from Genius/Spotify/Musixmatch/LRCLib)
    - Uncorrected transcription
    
    Args:
        job_id: Job ID
        temp_dir: Temporary directory with results
        transcription_result: Result dict from LyricsProcessor
        storage: StorageService instance
        job_manager: JobManager instance
        job_log: Optional JobLogger for remote debugging
    """
    logger.info(f"Job {job_id}: Uploading lyrics results to GCS")
    
    # Get job object for artist/title
    job = job_manager.get_job(job_id)
    
    lyrics_dir = os.path.join(temp_dir, "lyrics")
    
    # Upload LRC file (timed lyrics)
    if transcription_result.get("lrc_filepath") and os.path.exists(transcription_result["lrc_filepath"]):
        gcs_path = f"jobs/{job_id}/lyrics/karaoke.lrc"
        url = storage.upload_file(transcription_result["lrc_filepath"], gcs_path)
        job_manager.update_file_url(job_id, 'lyrics', 'lrc', url)
        logger.info(f"Job {job_id}: Uploaded LRC file")
    
    # Upload corrections JSON (for review interface)
    # LyricsProcessor saves it as "{artist} - {title} (Lyrics Corrections).json"
    corrections_filename = f"{job.artist} - {job.title} (Lyrics Corrections).json"
    corrections_file = os.path.join(lyrics_dir, corrections_filename)
    
    # Also check for generic corrections.json (fallback)
    if not os.path.exists(corrections_file):
        corrections_file = os.path.join(lyrics_dir, "corrections.json")
    
    if os.path.exists(corrections_file):
        # Always upload as corrections.json for consistent access
        gcs_path = f"jobs/{job_id}/lyrics/corrections.json"
        url = storage.upload_file(corrections_file, gcs_path)
        job_manager.update_file_url(job_id, 'lyrics', 'corrections', url)
        logger.info(f"Job {job_id}: Uploaded corrections JSON from {corrections_file}")
        
        # Load corrections to get metadata
        try:
            with open(corrections_file, 'r', encoding='utf-8') as f:
                corrections_data = json.load(f)
            
            # Store metadata in state_data
            job_manager.update_state_data(job_id, 'lyrics_metadata', {
                'segment_count': len(corrections_data.get('corrected_segments', [])),
                'has_corrections': True,
                'ready_for_review': True
            })
        except Exception as e:
            logger.warning(f"Job {job_id}: Could not parse corrections JSON: {e}")
    else:
        # CRITICAL: corrections.json is required for the review UI
        # If it's missing, the job cannot proceed to review
        error_msg = f"No corrections JSON found at {corrections_file}. Transcription may have produced no lyrics."
        logger.error(f"Job {job_id}: {error_msg}")
        raise Exception(error_msg)
    
    # Upload reference lyrics if available
    # Note: Source names use .title() so "lrclib" -> "Lrclib", "genius" -> "Genius"
    reference_files = [
        (f"{job.artist} - {job.title} (Lyrics Genius).txt", "Genius"),
        (f"{job.artist} - {job.title} (Lyrics Spotify).txt", "Spotify"),
        (f"{job.artist} - {job.title} (Lyrics Musixmatch).txt", "Musixmatch"),
        (f"{job.artist} - {job.title} (Lyrics Lrclib).txt", "LRCLib"),  # Note: source is 'lrclib', .title() = 'Lrclib'
    ]
    
    found_reference = False
    for ref_filename, source_name in reference_files:
        ref_path = os.path.join(lyrics_dir, ref_filename)
        if os.path.exists(ref_path):
            gcs_path = f"jobs/{job_id}/lyrics/{ref_filename}"
            url = storage.upload_file(ref_path, gcs_path)
            if job_log:
                job_log.info(f"Found reference lyrics from {source_name}")
            logger.info(f"Job {job_id}: Uploaded reference lyrics: {ref_filename}")
            found_reference = True
            break  # Only upload first available reference
    
    if not found_reference:
        if job_log:
            job_log.warning("No reference lyrics found from any source (Genius, Spotify, Musixmatch, LRCLib)")
        logger.warning(f"Job {job_id}: No reference lyrics found from any source")
    
    # Upload uncorrected transcription if available
    uncorrected_file = os.path.join(lyrics_dir, f"{job.artist} - {job.title} (Lyrics Uncorrected).txt")
    if os.path.exists(uncorrected_file):
        gcs_path = f"jobs/{job_id}/lyrics/uncorrected.txt"
        url = storage.upload_file(uncorrected_file, gcs_path)
        job_manager.update_file_url(job_id, 'lyrics', 'uncorrected', url)
        logger.info(f"Job {job_id}: Uploaded uncorrected transcription")
    
    logger.info(f"Job {job_id}: All lyrics results uploaded successfully")

