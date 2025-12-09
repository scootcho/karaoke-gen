"""
Render Video Worker

Generates the karaoke video with synchronized lyrics AFTER human review.

This worker:
1. Downloads the corrected lyrics data from GCS
2. Downloads the audio file
3. Downloads style assets from GCS
4. Uses LyricsTranscriber's OutputGenerator to render video
5. Uploads the with_vocals.mkv to GCS
6. Transitions to AWAITING_INSTRUMENTAL_SELECTION

Key insight: We use OutputGenerator from lyrics_transcriber library
WITHOUT using its blocking ReviewServer. This allows async operation
in Cloud Run.
"""
import logging
import os
import tempfile
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass

from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.config import get_settings
from backend.workers.worker_logging import create_job_logger, setup_job_logging

# Import from lyrics_transcriber (submodule)
from lyrics_transcriber.output.generator import OutputGenerator
from lyrics_transcriber.types import CorrectionResult
from lyrics_transcriber.core.config import OutputConfig


logger = logging.getLogger(__name__)


# Loggers to capture for render video worker
RENDER_VIDEO_WORKER_LOGGERS = [
    "lyrics_transcriber.output",
    "lyrics_transcriber.output.generator",
    "lyrics_transcriber.output.video",
    "lyrics_transcriber.output.ass",
]


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
    
    # Create job logger for remote debugging FIRST
    job_log = create_job_logger(job_id, "render_video")
    job_log.info("=== RENDER VIDEO WORKER STARTED ===")
    job_log.info(f"Job ID: {job_id}")
    
    # Set up log capture for OutputGenerator
    log_handler = setup_job_logging(job_id, "render_video", *RENDER_VIDEO_WORKER_LOGGERS)
    job_log.info(f"Log handler attached for {len(RENDER_VIDEO_WORKER_LOGGERS)} loggers")
    
    job = job_manager.get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        job_log.error(f"Job {job_id} not found in Firestore!")
        return False
    
    job_log.info(f"Starting video render for {job.artist} - {job.title}")
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
            job_log.info(f"Created temp directory: {temp_dir}")
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
            
            job_log.info(f"Downloading original corrections from {original_corrections_gcs}")
            logger.info(f"Job {job_id}: Downloading original corrections from {original_corrections_gcs}")
            storage.download_file(original_corrections_gcs, original_corrections_path)
            
            with open(original_corrections_path, 'r', encoding='utf-8') as f:
                original_data = json.load(f)
            
            # 3. Check if there are updated corrections (from review UI)
            # The frontend sends only partial data: {corrections, corrected_segments}
            updated_corrections_gcs = f"jobs/{job_id}/lyrics/corrections_updated.json"
            
            if storage.file_exists(updated_corrections_gcs):
                job_log.info("Found updated corrections from review, merging")
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
                
                job_log.info("Merged user corrections into original data")
                logger.info(f"Job {job_id}: Merged user corrections into original data")
            
            # 4. Convert to CorrectionResult
            correction_result = CorrectionResult.from_dict(original_data)
            job_log.info(f"Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
            logger.info(f"Job {job_id}: Loaded CorrectionResult with {len(correction_result.corrected_segments)} segments")
            
            # 3. Download audio file
            audio_path = os.path.join(temp_dir, "audio.flac")
            audio_gcs_path = job.input_media_gcs_path
            
            if not audio_gcs_path:
                raise FileNotFoundError(f"No input audio path for job {job_id}")
            
            job_log.info(f"Downloading audio from {audio_gcs_path}")
            logger.info(f"Job {job_id}: Downloading audio from {audio_gcs_path}")
            storage.download_file(audio_gcs_path, audio_path)
            job_log.info(f"Audio downloaded: {os.path.getsize(audio_path)} bytes")
            
            # 4. Get or create styles (downloads from GCS if custom styles exist)
            job_log.info("Loading style configuration...")
            job_log.info(f"  job.style_params_gcs_path: {job.style_params_gcs_path}")
            job_log.info(f"  job.style_assets: {list(job.style_assets.keys()) if job.style_assets else 'None'}")
            styles_path = _get_or_create_styles(job, temp_dir, storage, job_log)
            
            # 5. Configure OutputGenerator
            output_dir = os.path.join(temp_dir, "output")
            cache_dir = os.path.join(temp_dir, "cache")
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(cache_dir, exist_ok=True)
            
            job_log.info(f"Using styles from: {styles_path}")
            
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
            
            job_log.info(f"OutputConfig: output_styles_json={config.output_styles_json}, render_video={config.render_video}")
            
            output_generator = OutputGenerator(config, logger)
            
            # 6. Generate outputs (video, LRC, ASS, etc.)
            output_prefix = f"{job.artist or 'Unknown'} - {job.title or 'Unknown'}"
            job_log.info(f"Generating outputs with prefix '{output_prefix}'")
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
                video_size = os.path.getsize(outputs.video)
                job_log.info(f"Video generated: {video_size} bytes")
                video_gcs_path = f"jobs/{job_id}/videos/with_vocals.mkv"
                video_url = storage.upload_file(outputs.video, video_gcs_path)
                job_manager.update_file_url(job_id, 'videos', 'with_vocals', video_url)
                job_log.info(f"Uploaded with_vocals.mkv to GCS")
                logger.info(f"Job {job_id}: Uploaded with_vocals.mkv ({video_size} bytes)")
            else:
                job_log.error("Video generation failed - no output file produced!")
                raise Exception("Video generation failed - no output file produced")
            
            # 8. Upload LRC file
            if outputs.lrc and os.path.exists(outputs.lrc):
                lrc_gcs_path = f"jobs/{job_id}/lyrics/karaoke.lrc"
                lrc_url = storage.upload_file(outputs.lrc, lrc_gcs_path)
                job_manager.update_file_url(job_id, 'lyrics', 'lrc', lrc_url)
                job_log.info("Uploaded karaoke.lrc")
                logger.info(f"Job {job_id}: Uploaded karaoke.lrc")
            
            # 9. Upload ASS subtitle file
            if outputs.ass and os.path.exists(outputs.ass):
                ass_gcs_path = f"jobs/{job_id}/lyrics/karaoke.ass"
                ass_url = storage.upload_file(outputs.ass, ass_gcs_path)
                job_manager.update_file_url(job_id, 'lyrics', 'ass', ass_url)
                job_log.info("Uploaded karaoke.ass")
                logger.info(f"Job {job_id}: Uploaded karaoke.ass")
            
            # 10. Upload corrected text files
            if outputs.corrected_txt and os.path.exists(outputs.corrected_txt):
                txt_gcs_path = f"jobs/{job_id}/lyrics/corrected.txt"
                txt_url = storage.upload_file(outputs.corrected_txt, txt_gcs_path)
                job_manager.update_file_url(job_id, 'lyrics', 'corrected_txt', txt_url)
                job_log.info("Uploaded corrected.txt")
                logger.info(f"Job {job_id}: Uploaded corrected.txt")
            
            # 11. Transition to awaiting instrumental selection
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.AWAITING_INSTRUMENTAL_SELECTION,
                progress=80,
                message="Video rendered - select your instrumental"
            )
            
            job_log.info("=== RENDER VIDEO WORKER COMPLETE ===")
            logger.info(f"Job {job_id}: Video render complete, awaiting instrumental selection")
            return True
            
    except Exception as e:
        job_log.error(f"Video render failed: {e}")
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


def _get_or_create_styles(job, temp_dir: str, storage: StorageService, job_log=None) -> str:
    """
    Get styles JSON for video generation.
    
    Downloads custom styles from job.style_params_gcs_path and job.style_assets,
    updates paths in the JSON to point to downloaded local files, otherwise uses defaults.
    
    Args:
        job: Job object
        temp_dir: Temporary directory for writing styles file
        storage: Storage service for downloading files
        job_log: Optional job logger for remote debugging
        
    Returns:
        Path to styles JSON file
    """
    style_dir = os.path.join(temp_dir, "style")
    os.makedirs(style_dir, exist_ok=True)
    styles_path = os.path.join(style_dir, "styles.json")
    
    def log_info(msg):
        if job_log:
            job_log.info(msg)
        logger.info(msg)
    
    def log_warning(msg):
        if job_log:
            job_log.warning(msg)
        logger.warning(msg)
    
    # Check if job has custom style_params.json (the correct location!)
    if job.style_params_gcs_path:
        try:
            log_info(f"Downloading custom styles from {job.style_params_gcs_path}")
            storage.download_file(job.style_params_gcs_path, styles_path)
            
            # Load the styles to update asset paths
            with open(styles_path, 'r') as f:
                style_data = json.load(f)
            
            log_info(f"Loaded style sections: {list(style_data.keys())}")
            
            # Download and update paths for style assets
            local_assets = {}
            if job.style_assets:
                log_info(f"Downloading {len(job.style_assets)} style assets...")
                for asset_key, gcs_path in job.style_assets.items():
                    if asset_key == 'style_params':
                        continue  # Already downloaded
                    try:
                        # Determine local filename from asset key
                        ext = os.path.splitext(gcs_path)[1] or '.png'
                        local_path = os.path.join(style_dir, f"{asset_key}{ext}")
                        storage.download_file(gcs_path, local_path)
                        local_assets[asset_key] = local_path
                        log_info(f"  Downloaded {asset_key}: {local_path}")
                    except Exception as e:
                        log_warning(f"  Failed to download {asset_key}: {e}")
            
            # Update paths in style_data to point to local files
            updates_made = False
            
            # Map asset keys to style JSON paths
            asset_mapping = {
                'intro_background': ('intro', 'background_image'),
                'karaoke_background': ('karaoke', 'background_image'),
                'end_background': ('end', 'background_image'),
                'font': [('intro', 'font'), ('karaoke', 'font_path'), ('end', 'font')],
            }
            
            for asset_key, local_path in local_assets.items():
                if asset_key in asset_mapping:
                    mappings = asset_mapping[asset_key]
                    # Handle single or multiple mappings
                    if isinstance(mappings[0], str):
                        mappings = [mappings]
                    
                    for section, field in mappings:
                        if section in style_data and isinstance(style_data[section], dict):
                            old_value = style_data[section].get(field, 'NOT SET')
                            style_data[section][field] = local_path
                            log_info(f"  Updated {section}.{field}: {old_value} -> {local_path}")
                            updates_made = True
            
            # Save updated styles
            if updates_made:
                with open(styles_path, 'w') as f:
                    json.dump(style_data, f, indent=2)
                log_info(f"Saved updated styles with local asset paths")
            
            # Log final karaoke style for debugging
            if 'karaoke' in style_data:
                k = style_data['karaoke']
                log_info(f"Final karaoke style: background_image={k.get('background_image', 'NOT SET')}, font_path={k.get('font_path', 'NOT SET')}")
            
            return styles_path
            
        except Exception as e:
            log_warning(f"Failed to download custom styles: {e}, using defaults")
    else:
        log_info("No custom style_params_gcs_path found on job")
    
    # Use default styles
    with open(styles_path, 'w') as f:
        json.dump(DEFAULT_STYLES, f, indent=2)
    
    log_info("Using default styles for video generation")
    return styles_path


# For compatibility with worker service
render_video_worker = process_render_video
