"""
Render Video Worker

Generates the karaoke video with synchronized lyrics AFTER human review.

This worker:
1. Downloads the corrected lyrics data from GCS
2. Downloads the audio file
3. Uses LyricsTranscriber's OutputGenerator to render video
4. Uploads the with_vocals.mkv to GCS
5. Transitions to AWAITING_INSTRUMENTAL_SELECTION

Key insight: We use OutputGenerator from lyrics_transcriber library
WITHOUT using its blocking ReviewServer. This allows async operation
in Cloud Run.
"""
import logging
import os
import tempfile
import json
from typing import Optional
from dataclasses import dataclass

from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.config import get_settings

# Import from lyrics_transcriber (submodule)
from lyrics_transcriber.output.generator import OutputGenerator
from lyrics_transcriber.types import CorrectionResult
from lyrics_transcriber.core.config import OutputConfig


logger = logging.getLogger(__name__)


# Default styles for video generation
# All karaoke fields are required by the ASS subtitle generator
DEFAULT_STYLES = {
    "karaoke": {
        # Required for video background
        "background_color": "#000000",
        # Font settings - font_path must be string (empty OK), ass_name required
        "font": "Arial",
        "font_path": "",  # Must be string, not None
        "ass_name": "Default",  # Required for ASS style name
        # Colors in "R, G, B, A" format (required)
        "primary_color": "112, 112, 247, 255",
        "secondary_color": "255, 255, 255, 255",
        "outline_color": "26, 58, 235, 255",
        "back_color": "0, 0, 0, 0",
        # Boolean style options
        "bold": False,
        "italic": False,
        "underline": False,
        "strike_out": False,
        # Numeric style options (all required for ASS)
        "scale_x": 100,
        "scale_y": 100,
        "spacing": 0,
        "angle": 0.0,
        "border_style": 1,
        "outline": 1,
        "shadow": 0,
        "margin_l": 0,
        "margin_r": 0,
        "margin_v": 0,
        "encoding": 0,
        # Additional layout settings
        "max_line_length": 40,
        "top_padding": 200,
        "font_size": 100
    }
}


async def process_render_video(job_id: str) -> bool:
    """
    Render karaoke video with corrected lyrics.
    
    Called after human review is complete (REVIEW_COMPLETE state).
    Uses OutputGenerator from lyrics_transcriber to generate the video.
    
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
    
    logger.info(f"Job {job_id}: Starting video render (post-review)")
    
    try:
        # Transition to RENDERING_VIDEO
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.RENDERING_VIDEO,
            progress=75,
            message="Rendering karaoke video with corrected lyrics"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. Download corrected corrections data
            corrections_path = os.path.join(temp_dir, "corrections.json")
            
            # Try updated corrections first (from human review), fall back to original
            corrections_gcs_updated = f"jobs/{job_id}/lyrics/corrections_updated.json"
            corrections_gcs_original = f"jobs/{job_id}/lyrics/corrections.json"
            
            # Get GCS path from file_urls
            corrections_url = job.file_urls.get('lyrics', {}).get('corrections_updated')
            if not corrections_url:
                corrections_url = job.file_urls.get('lyrics', {}).get('corrections')
            
            if not corrections_url:
                # Try direct GCS paths
                if storage.file_exists(corrections_gcs_updated):
                    corrections_gcs = corrections_gcs_updated
                elif storage.file_exists(corrections_gcs_original):
                    corrections_gcs = corrections_gcs_original
                else:
                    raise FileNotFoundError(f"No corrections file found for job {job_id}")
            else:
                # Extract GCS path from URL
                corrections_gcs = _extract_gcs_path(corrections_url)
            
            # 2. Load the ORIGINAL corrections (has full structure)
            original_corrections_gcs = f"jobs/{job_id}/lyrics/corrections.json"
            original_corrections_path = os.path.join(temp_dir, "corrections_original.json")
            
            logger.info(f"Job {job_id}: Downloading original corrections from {original_corrections_gcs}")
            storage.download_file(original_corrections_gcs, original_corrections_path)
            
            with open(original_corrections_path, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
            
            # 3. Check if there are updated corrections (from review UI)
            # The frontend sends only partial data: {corrections, corrected_segments}
            updated_corrections_gcs = f"jobs/{job_id}/lyrics/corrections_updated.json"
            
            if storage.file_exists(updated_corrections_gcs):
                logger.info(f"Job {job_id}: Found updated corrections, merging")
                updated_path = os.path.join(temp_dir, "corrections_updated.json")
                storage.download_file(updated_corrections_gcs, updated_path)
                
                with open(updated_path, 'r', encoding='utf-8') as f:
                    updated_data = json.load(f)
                
                # Merge: update the original with the user's corrections
                if 'corrections' in updated_data:
                    original_data['corrections'] = updated_data['corrections']
                if 'corrected_segments' in updated_data:
                    original_data['corrected_segments'] = updated_data['corrected_segments']
                
                logger.info(f"Job {job_id}: Merged user corrections into original data")
            
            # 4. Convert to CorrectionResult
            correction_result = CorrectionResult.from_dict(original_data)
            logger.info(f"Job {job_id}: Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
            
            # 3. Download audio file
            audio_path = os.path.join(temp_dir, "audio.flac")
            audio_gcs_path = job.input_media_gcs_path
            
            if not audio_gcs_path:
                raise FileNotFoundError(f"No input audio path for job {job_id}")
            
            logger.info(f"Job {job_id}: Downloading audio from {audio_gcs_path}")
            storage.download_file(audio_gcs_path, audio_path)
            
            # 4. Get or create styles
            styles_path = _get_or_create_styles(job, temp_dir, storage)
            
            # 5. Configure OutputGenerator
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(cache_dir, exist_ok=True)
            
            config = OutputConfig(
                output_dir=output_dir,
                cache_dir=cache_dir,
                output_styles_json=styles_path,
                render_video=True,
                generate_cdg=False,  # CDG optional, generated separately
                generate_plain_text=True,
                generate_lrc=True,
                video_resolution="4k",
                subtitle_offset_ms=0
            )
            
            output_generator = OutputGenerator(config, logger)
            
            # 6. Generate outputs (video, LRC, ASS, etc.)
            output_prefix = f"{job.artist or 'Unknown'} - {job.title or 'Unknown'}"
            logger.info(f"Job {job_id}: Generating outputs with prefix '{output_prefix}'")
            
            outputs = output_generator.generate_outputs(
                transcription_corrected=correction_result,
                lyrics_results={},  # Reference lyrics already in correction_result
                output_prefix=output_prefix,
                audio_filepath=audio_path,
                artist=job.artist,
                title=job.title
            )
            
            # 7. Upload video to GCS
            if outputs.video and os.path.exists(outputs.video):
                video_gcs_path = f"jobs/{job_id}/videos/with_vocals.mkv"
                video_url = storage.upload_file(outputs.video, video_gcs_path)
                job_manager.update_file_url(job_id, 'videos', 'with_vocals', video_url)
                logger.info(f"Job {job_id}: Uploaded with_vocals.mkv ({os.path.getsize(outputs.video)} bytes)")
            else:
                raise Exception("Video generation failed - no output file produced")
            
            # 8. Upload LRC file
            if outputs.lrc and os.path.exists(outputs.lrc):
                lrc_gcs_path = f"jobs/{job_id}/lyrics/karaoke.lrc"
                lrc_url = storage.upload_file(outputs.lrc, lrc_gcs_path)
                job_manager.update_file_url(job_id, 'lyrics', 'lrc', lrc_url)
                logger.info(f"Job {job_id}: Uploaded karaoke.lrc")
            
            # 9. Upload ASS subtitle file
            if outputs.ass and os.path.exists(outputs.ass):
                ass_gcs_path = f"jobs/{job_id}/lyrics/karaoke.ass"
                ass_url = storage.upload_file(outputs.ass, ass_gcs_path)
                job_manager.update_file_url(job_id, 'lyrics', 'ass', ass_url)
                logger.info(f"Job {job_id}: Uploaded karaoke.ass")
            
            # 10. Upload corrected text files
            if outputs.corrected_txt and os.path.exists(outputs.corrected_txt):
                txt_gcs_path = f"jobs/{job_id}/lyrics/corrected.txt"
                txt_url = storage.upload_file(outputs.corrected_txt, txt_gcs_path)
                job_manager.update_file_url(job_id, 'lyrics', 'corrected_txt', txt_url)
                logger.info(f"Job {job_id}: Uploaded corrected.txt")
            
            # 11. Transition to awaiting instrumental selection
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.AWAITING_INSTRUMENTAL_SELECTION,
                progress=80,
                message="Video rendered - select your instrumental"
            )
            
            logger.info(f"Job {job_id}: Video render complete, awaiting instrumental selection")
            return True
            
    except Exception as e:
        logger.error(f"Job {job_id}: Video render failed: {e}", exc_info=True)
        job_manager.fail_job(job_id, f"Video render failed: {str(e)}")
        return False


def _extract_gcs_path(url: str) -> str:
    """Extract GCS path from a URL or return as-is if already a path."""
    if url.startswith('gs://'):
        # Already a GCS path
        return url.replace('gs://', '').split('/', 1)[1] if '/' in url else url
    if url.startswith('https://storage.googleapis.com/'):
        # Signed URL - extract path
        path = url.replace('https://storage.googleapis.com/', '')
        # Remove query params
        if '?' in path:
            path = path.split('?')[0]
        # Skip bucket name
        parts = path.split('/', 1)
        return parts[1] if len(parts) > 1 else path
    return url


def _get_or_create_styles(job, temp_dir: str, storage: StorageService) -> str:
    """
    Get styles JSON for video generation.
    
    Checks for custom styles in job state_data, otherwise uses defaults.
    
    Args:
        job: Job object
        temp_dir: Temporary directory for writing styles file
        storage: Storage service for downloading files
        
    Returns:
        Path to styles JSON file
    """
    styles_path = os.path.join(temp_dir, "styles.json")
    
    # Check if job has custom styles
    if job.state_data and job.state_data.get('styles_gcs_path'):
        try:
            storage.download_file(job.state_data['styles_gcs_path'], styles_path)
            logger.info(f"Using custom styles from {job.state_data['styles_gcs_path']}")
            return styles_path
        except Exception as e:
            logger.warning(f"Failed to download custom styles: {e}, using defaults")
    
    # Use default styles
    with open(styles_path, 'w') as f:
        json.dump(DEFAULT_STYLES, f, indent=2)
    
    logger.info("Using default styles for video generation")
    return styles_path


# For compatibility with worker service
render_video_worker = process_render_video
