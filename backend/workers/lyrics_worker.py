"""
Lyrics transcription and correction worker.

Handles the lyrics processing track of parallel processing:
1. Fetch reference lyrics from multiple sources (Genius, Spotify, Musixmatch)
2. Transcribe audio with AudioShake API (1-2 min)
3. Run automatic correction using LyricsTranscriber
4. Generate corrections JSON for human review
5. Upload all data to GCS
6. Transition to AWAITING_REVIEW state

Integrates with:
- karaoke_gen.lyrics_processor.LyricsProcessor for lyrics fetching
- lyrics_transcriber library for transcription and correction
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

# Import from karaoke_gen package
from karaoke_gen.lyrics_processor import LyricsProcessor


logger = logging.getLogger(__name__)


async def process_lyrics_transcription(job_id: str) -> bool:
    """
    Process lyrics transcription and correction for a job.
    
    This is the main entry point for the lyrics worker.
    Called asynchronously from the job submission endpoint.
    
    Runs in parallel with audio_worker, coordinated via job state.
    
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
    temp_dir = tempfile.mkdtemp(prefix=f"karaoke_lyrics_{job_id}_")
    
    try:
        logger.info(f"Starting lyrics transcription for job {job_id}")
        
        # Download audio file from GCS
        audio_path = await download_audio(job_id, temp_dir, storage, job)
        if not audio_path:
            raise Exception("Failed to download audio file")
        
        # Validate we have artist and title
        if not job.artist or not job.title:
            raise Exception("Artist and title are required for lyrics processing")
        
        # Initialize lyrics processor
        lyrics_processor = LyricsProcessor(
            logger=logger,
            artist=job.artist,
            title=job.title,
            audio_filepath=audio_path,
            output_dir=temp_dir
        )
        
        # Set API keys from Secret Manager
        await configure_api_keys(settings)
        
        # Stage 1: Fetch reference lyrics
        logger.info(f"Job {job_id}: Fetching reference lyrics")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.TRANSCRIBING,
            progress=25,
            message="Fetching lyrics from Genius/Spotify"
        )
        
        reference_lyrics = await fetch_reference_lyrics(
            job_id=job_id,
            lyrics_processor=lyrics_processor,
            job_manager=job_manager,
            storage=storage,
            temp_dir=temp_dir
        )
        
        # Stage 2: Transcribe audio with AudioShake
        logger.info(f"Job {job_id}: Transcribing audio with AudioShake")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.TRANSCRIBING,
            progress=30,
            message="Transcribing audio (AudioShake API, 1-2 min)"
        )
        
        transcription = await transcribe_audio(
            job_id=job_id,
            lyrics_processor=lyrics_processor
        )
        
        if not transcription:
            raise Exception("Audio transcription failed")
        
        # Stage 3: Automatic correction
        logger.info(f"Job {job_id}: Running automatic lyrics correction")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.CORRECTING,
            progress=40,
            message="Correcting lyrics automatically"
        )
        
        corrections = await generate_corrections(
            job_id=job_id,
            lyrics_processor=lyrics_processor,
            transcription=transcription,
            reference_lyrics=reference_lyrics
        )
        
        if not corrections:
            raise Exception("Lyrics correction failed")
        
        # Stage 4: Upload corrections and audio for review
        logger.info(f"Job {job_id}: Uploading corrections for human review")
        await upload_review_data(
            job_id=job_id,
            job_manager=job_manager,
            storage=storage,
            temp_dir=temp_dir,
            corrections=corrections,
            audio_path=audio_path,
            reference_lyrics=reference_lyrics
        )
        
        # Mark lyrics processing complete
        logger.info(f"Job {job_id}: Lyrics processing complete")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.LYRICS_COMPLETE,
            progress=45,
            message="Lyrics ready for review"
        )
        
        # Check if audio is also complete and transition to next stage if so
        job_manager.mark_lyrics_complete(job_id)
        
        # If both audio and lyrics are complete, job will auto-transition to GENERATING_SCREENS
        # Otherwise, it waits for audio to complete
        
        return True
        
    except Exception as e:
        logger.error(f"Job {job_id}: Lyrics transcription failed: {e}", exc_info=True)
        job_manager.mark_job_failed(
            job_id=job_id,
            error_message=f"Lyrics transcription failed: {str(e)}",
            error_details={"stage": "lyrics_transcription", "error": str(e)}
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
        # Download uploaded file from GCS using input_media_gcs_path
        if not job.input_media_gcs_path:
            logger.error(f"Job {job_id}: No input_media_gcs_path found")
            return None
        
        # Download from GCS
        local_path = os.path.join(temp_dir, job.filename or "input.flac")
        storage.download_file(job.input_media_gcs_path, local_path)
        
        logger.info(f"Job {job_id}: Downloaded audio from {job.input_media_gcs_path} to {local_path}")
        return local_path
        
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to download audio: {e}")
        return None


async def configure_api_keys(settings) -> None:
    """
    Configure API keys from Secret Manager.
    
    Sets environment variables that lyrics_processor expects:
    - AUDIOSHAKE_API_TOKEN
    - GENIUS_API_TOKEN
    - SPOTIFY_COOKIE_SP_DC
    - RAPIDAPI_KEY
    """
    # AudioShake (required for transcription)
    audioshake_key = settings.get_secret("audioshake-api-key")
    if audioshake_key:
        os.environ["AUDIOSHAKE_API_TOKEN"] = audioshake_key
        logger.info("AudioShake API key configured")
    else:
        logger.warning("No AudioShake API key found - transcription will fail")
    
    # Genius (optional - lyrics source)
    genius_key = settings.get_secret("genius-api-key")
    if genius_key:
        os.environ["GENIUS_API_TOKEN"] = genius_key
        logger.info("Genius API key configured")
    
    # Spotify (optional - lyrics source)
    spotify_cookie = settings.get_secret("spotify-cookie")
    if spotify_cookie:
        os.environ["SPOTIFY_COOKIE_SP_DC"] = spotify_cookie
        logger.info("Spotify cookie configured")
    
    # RapidAPI (optional - Musixmatch access)
    rapidapi_key = settings.get_secret("rapidapi-key")
    if rapidapi_key:
        os.environ["RAPIDAPI_KEY"] = rapidapi_key
        logger.info("RapidAPI key configured")


async def fetch_reference_lyrics(
    job_id: str,
    lyrics_processor: LyricsProcessor,
    job_manager: JobManager,
    storage: StorageService,
    temp_dir: str
) -> Optional[str]:
    """
    Fetch reference lyrics from multiple sources.
    
    Tries in order:
    1. Genius API
    2. Spotify API (via RapidAPI)
    3. Musixmatch API (via RapidAPI)
    
    Returns:
        Best available lyrics text, or None if all sources fail
    """
    try:
        # LyricsProcessor.fetch_lyrics() tries multiple sources automatically
        reference_lyrics = await lyrics_processor.fetch_lyrics()
        
        if reference_lyrics:
            # Save reference lyrics to file
            lyrics_file = os.path.join(temp_dir, "reference_lyrics.txt")
            with open(lyrics_file, 'w', encoding='utf-8') as f:
                f.write(reference_lyrics)
            
            logger.info(f"Job {job_id}: Reference lyrics fetched successfully")
            return reference_lyrics
        else:
            logger.warning(f"Job {job_id}: No reference lyrics found from any source")
            return None
            
    except Exception as e:
        logger.warning(f"Job {job_id}: Error fetching reference lyrics: {e}")
        return None


async def transcribe_audio(
    job_id: str,
    lyrics_processor: LyricsProcessor
) -> Optional[Dict[str, Any]]:
    """
    Transcribe audio using AudioShake API.
    
    Returns word-level timestamps and confidence scores.
    
    Returns:
        Transcription data dict, or None if failed
    """
    try:
        # LyricsProcessor.transcribe_audio() handles AudioShake API
        # Returns dict with word-level data
        transcription = await lyrics_processor.transcribe_audio()
        
        if transcription and 'words' in transcription:
            word_count = len(transcription['words'])
            logger.info(f"Job {job_id}: Transcription complete ({word_count} words)")
            return transcription
        else:
            logger.error(f"Job {job_id}: Transcription returned no words")
            return None
            
    except Exception as e:
        logger.error(f"Job {job_id}: Transcription error: {e}", exc_info=True)
        return None


async def generate_corrections(
    job_id: str,
    lyrics_processor: LyricsProcessor,
    transcription: Dict[str, Any],
    reference_lyrics: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Generate corrected lyrics using LyricsTranscriber algorithms.
    
    Uses:
    - ExtendAnchorHandler: Extends known-good word sequences
    - SyllablesMatchHandler: Matches by syllable count
    - Confidence-based correction
    
    Returns:
        Corrections JSON suitable for review interface, or None if failed
    """
    try:
        # LyricsProcessor.generate_corrections() uses LyricsTranscriber
        # Returns corrections JSON with:
        # - lines: Array of corrected lines with timestamps
        # - metadata: Song info, timestamps, etc.
        corrections = await lyrics_processor.generate_corrections(
            transcription=transcription,
            reference_lyrics=reference_lyrics
        )
        
        if corrections and 'lines' in corrections:
            line_count = len(corrections['lines'])
            logger.info(f"Job {job_id}: Corrections generated ({line_count} lines)")
            return corrections
        else:
            logger.error(f"Job {job_id}: Corrections generation returned no lines")
            return None
            
    except Exception as e:
        logger.error(f"Job {job_id}: Correction error: {e}", exc_info=True)
        return None


async def upload_review_data(
    job_id: str,
    job_manager: JobManager,
    storage: StorageService,
    temp_dir: str,
    corrections: Dict[str, Any],
    audio_path: str,
    reference_lyrics: Optional[str]
) -> None:
    """
    Upload all data needed for human review interface.
    
    Uploads:
    1. corrections.json - For review interface
    2. audio.flac - For playback in review interface
    3. reference_lyrics.txt - For comparison
    """
    # Upload corrections JSON
    corrections_file = os.path.join(temp_dir, "corrections.json")
    with open(corrections_file, 'w', encoding='utf-8') as f:
        json.dump(corrections, f, indent=2)
    
    corrections_gcs_path = f"jobs/{job_id}/lyrics/corrections.json"
    corrections_url = storage.upload_file(corrections_file, corrections_gcs_path)
    job_manager.update_file_url(job_id, 'lyrics', 'corrections', corrections_url)
    logger.info(f"Job {job_id}: Uploaded corrections JSON")
    
    # Upload audio for review playback
    audio_gcs_path = f"jobs/{job_id}/lyrics/audio.flac"
    audio_url = storage.upload_file(audio_path, audio_gcs_path)
    job_manager.update_file_url(job_id, 'lyrics', 'audio', audio_url)
    logger.info(f"Job {job_id}: Uploaded audio for review")
    
    # Upload reference lyrics if available
    if reference_lyrics:
        reference_file = os.path.join(temp_dir, "reference_lyrics.txt")
        with open(reference_file, 'w', encoding='utf-8') as f:
            f.write(reference_lyrics)
        
        reference_gcs_path = f"jobs/{job_id}/lyrics/reference.txt"
        reference_url = storage.upload_file(reference_file, reference_gcs_path)
        job_manager.update_file_url(job_id, 'lyrics', 'reference', reference_url)
        logger.info(f"Job {job_id}: Uploaded reference lyrics")
    
    # Store metadata in state_data
    job_manager.update_state_data(job_id, 'lyrics_metadata', {
        'line_count': len(corrections.get('lines', [])),
        'has_reference': reference_lyrics is not None,
        'ready_for_review': True
    })

