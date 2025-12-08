"""
Title and end screen generation worker.

Handles screen generation after parallel processing completes:
1. Generate title screen with artist/song info
2. Generate end screen ("Thank you for singing!")
3. Upload both screens to GCS
4. Transition to AWAITING_REVIEW (human must review lyrics)

After review:
5. Render video worker generates with_vocals.mkv
6. Then AWAITING_INSTRUMENTAL_SELECTION

This worker is triggered automatically when both audio and lyrics
processing complete (via mark_audio_complete/mark_lyrics_complete coordination).

Integrates with karaoke_gen.video_generator.VideoGenerator.

SOLID Principles:
- Single Responsibility: Only generates title/end screens
- Open/Closed: Extensible for different screen styles
- Liskov Substitution: Can swap different video generators
- Interface Segregation: Focused interface for screen generation
- Dependency Inversion: Depends on abstractions (VideoGenerator interface)
"""
import logging
import os
import shutil
import tempfile
from typing import Optional, Dict, Any
from pathlib import Path

from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.config import get_settings

# Import from karaoke_gen package
from karaoke_gen.video_generator import VideoGenerator


logger = logging.getLogger(__name__)


async def generate_screens(job_id: str) -> bool:
    """
    Generate title and end screen videos for a job.
    
    This is the main entry point for the screens worker.
    Called automatically when both audio and lyrics processing complete.
    
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
    
    # Validate both audio and lyrics are complete
    if not _validate_prerequisites(job):
        logger.error(f"Job {job_id}: Prerequisites not met for screen generation")
        return False
    
    # Create temporary working directory
    temp_dir = tempfile.mkdtemp(prefix=f"karaoke_screens_{job_id}_")
    
    try:
        logger.info(f"Starting screen generation for job {job_id}")
        
        # Transition to GENERATING_SCREENS state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.GENERATING_SCREENS,
            progress=50,
            message="Generating title and end screens"
        )
        
        # Initialize video generator
        video_generator = _create_video_generator(temp_dir)
        
        # Generate title screen
        title_screen_path = await _generate_title_screen(
            job_id=job_id,
            job=job,
            video_generator=video_generator,
            temp_dir=temp_dir
        )
        
        if not title_screen_path:
            raise Exception("Title screen generation failed")
        
        # Generate end screen
        end_screen_path = await _generate_end_screen(
            job_id=job_id,
            job=job,
            video_generator=video_generator,
            temp_dir=temp_dir
        )
        
        if not end_screen_path:
            raise Exception("End screen generation failed")
        
        # Upload screens to GCS
        await _upload_screens(
            job_id=job_id,
            job_manager=job_manager,
            storage=storage,
            title_screen_path=title_screen_path,
            end_screen_path=end_screen_path
        )
        
        # Apply countdown padding if needed
        # (This is handled automatically by checking lyrics metadata)
        await _apply_countdown_padding_if_needed(job_id, job_manager, job)
        
        # Transition to AWAITING_REVIEW
        # Human must review lyrics before video can be rendered
        logger.info(f"Job {job_id}: Screens generated, awaiting lyrics review")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.AWAITING_REVIEW,
            progress=55,
            message="Ready for lyrics review. Please review and correct lyrics."
        )
        
        # TODO: Send notification to user that selection is needed
        # await notify_user(job_id, "instrumental_selection_ready")
        
        return True
        
    except Exception as e:
        logger.error(f"Job {job_id}: Screen generation failed: {e}", exc_info=True)
        job_manager.mark_job_failed(
            job_id=job_id,
            error_message=f"Screen generation failed: {str(e)}",
            error_details={"stage": "screen_generation", "error": str(e)}
        )
        return False
        
    finally:
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")


def _validate_prerequisites(job) -> bool:
    """
    Validate that both audio and lyrics processing are complete.
    
    Single Responsibility: Validation logic separated from main flow.
    
    Args:
        job: Job object
        
    Returns:
        True if prerequisites met, False otherwise
    """
    audio_complete = job.state_data.get('audio_complete', False)
    lyrics_complete = job.state_data.get('lyrics_complete', False)
    
    if not audio_complete:
        logger.error(f"Job {job.job_id}: Audio processing not complete")
        return False
    
    if not lyrics_complete:
        logger.error(f"Job {job.job_id}: Lyrics processing not complete")
        return False
    
    if not job.artist or not job.title:
        logger.error(f"Job {job.job_id}: Missing artist or title")
        return False
    
    return True


def _create_video_generator(temp_dir: str) -> VideoGenerator:
    """
    Create video generator with appropriate parameters.
    
    Dependency Inversion: Depends on VideoGenerator abstraction.
    
    Args:
        temp_dir: Temporary directory for output
        
    Returns:
        Configured VideoGenerator instance
    """
    # FFmpeg base command (same as in audio_worker)
    ffmpeg_base_command = "ffmpeg -hide_banner -loglevel error -nostats -y"
    
    return VideoGenerator(
        logger=logger,
        ffmpeg_base_command=ffmpeg_base_command,
        render_bounding_boxes=False,
        output_png=True,
        output_jpg=True
    )


def _get_title_format() -> Dict[str, Any]:
    """
    Get title screen format parameters.
    
    Single Responsibility: Style configuration separated.
    Uses the same defaults as karaoke_gen.config.setup_title_format().
    
    Returns:
        Title format dict
    """
    return {
        "background_color": "#000000",
        "background_image": None,
        "font": None,  # Will use default font
        "title_region": "200,700,3440,400",  # x,y,width,height
        "title_color": "#FFFFFF",
        "title_gradient": None,
        "title_text_transform": "none",
        "artist_region": "200,1100,3440,300",
        "artist_color": "#CCCCCC",
        "artist_gradient": None,
        "artist_text_transform": "none",
        "extra_text": None,
        "extra_text_region": None,
        "extra_text_color": "#FFFFFF",
        "extra_text_gradient": None,
    }


def _get_end_format() -> Dict[str, Any]:
    """
    Get end screen format parameters.
    
    Single Responsibility: Style configuration separated.
    Uses the same defaults as karaoke_gen.config.setup_end_format().
    
    Returns:
        End format dict
    """
    return {
        "background_color": "#000000",
        "background_image": None,
        "font": None,  # Will use default font
        "title_region": "200,900,3440,400",  # Centered on screen
        "title_color": "#FFFFFF",
        "title_gradient": None,
        "title_text_transform": "none",
        "artist_region": None,  # No artist on end screen by default
        "artist_color": "#CCCCCC",
        "artist_gradient": None,
        "artist_text_transform": "none",
        "extra_text": "Thank you for singing!",
        "extra_text_region": "200,1300,3440,200",
        "extra_text_color": "#AAAAAA",
        "extra_text_gradient": None,
    }


async def _generate_title_screen(
    job_id: str,
    job,
    video_generator: VideoGenerator,
    temp_dir: str
) -> Optional[str]:
    """
    Generate title screen video.
    
    Single Responsibility: Only handles title screen generation.
    
    Args:
        job_id: Job ID
        job: Job object with artist/title
        video_generator: Video generator instance
        temp_dir: Temporary directory
        
    Returns:
        Path to generated title screen, or None if failed
    """
    try:
        logger.info(f"Job {job_id}: Generating title screen")
        
        # Set up output paths
        artist_title = f"{job.artist} - {job.title}"
        output_image_filepath_noext = os.path.join(temp_dir, f"{artist_title} (Title)")
        output_video_filepath = os.path.join(temp_dir, f"{artist_title} (Title).mov")
        
        # Get title format settings
        title_format = _get_title_format()
        
        # Generate title screen (synchronous method)
        video_generator.create_title_video(
            artist=job.artist,
            title=job.title,
            format=title_format,
            output_image_filepath_noext=output_image_filepath_noext,
            output_video_filepath=output_video_filepath,
            existing_title_image=None,
            intro_video_duration=5  # 5 second intro
        )
        
        if os.path.exists(output_video_filepath):
            logger.info(f"Job {job_id}: Title screen generated at {output_video_filepath}")
            return output_video_filepath
        else:
            logger.error(f"Job {job_id}: Title screen generation returned no file")
            return None
            
    except Exception as e:
        logger.error(f"Job {job_id}: Title screen generation error: {e}", exc_info=True)
        return None


async def _generate_end_screen(
    job_id: str,
    job,
    video_generator: VideoGenerator,
    temp_dir: str
) -> Optional[str]:
    """
    Generate end screen video.
    
    Single Responsibility: Only handles end screen generation.
    
    Args:
        job_id: Job ID
        job: Job object with artist/title
        video_generator: Video generator instance
        temp_dir: Temporary directory
        
    Returns:
        Path to generated end screen, or None if failed
    """
    try:
        logger.info(f"Job {job_id}: Generating end screen")
        
        # Set up output paths
        artist_title = f"{job.artist} - {job.title}"
        output_image_filepath_noext = os.path.join(temp_dir, f"{artist_title} (End)")
        output_video_filepath = os.path.join(temp_dir, f"{artist_title} (End).mov")
        
        # Get end format settings
        end_format = _get_end_format()
        
        # Generate end screen (synchronous method)
        video_generator.create_end_video(
            artist=job.artist,
            title=job.title,
            format=end_format,
            output_image_filepath_noext=output_image_filepath_noext,
            output_video_filepath=output_video_filepath,
            existing_end_image=None,
            end_video_duration=5  # 5 second outro
        )
        
        if os.path.exists(output_video_filepath):
            logger.info(f"Job {job_id}: End screen generated at {output_video_filepath}")
            return output_video_filepath
        else:
            logger.error(f"Job {job_id}: End screen generation returned no file")
            return None
            
    except Exception as e:
        logger.error(f"Job {job_id}: End screen generation error: {e}", exc_info=True)
        return None


async def _upload_screens(
    job_id: str,
    job_manager: JobManager,
    storage: StorageService,
    title_screen_path: str,
    end_screen_path: str
) -> None:
    """
    Upload title and end screens to GCS.
    
    Single Responsibility: Only handles uploads.
    
    Args:
        job_id: Job ID
        job_manager: Job manager instance
        storage: Storage service instance
        title_screen_path: Path to title screen
        end_screen_path: Path to end screen
    """
    # Upload title screen
    title_gcs_path = f"jobs/{job_id}/screens/title.mov"
    title_url = storage.upload_file(title_screen_path, title_gcs_path)
    job_manager.update_file_url(job_id, 'screens', 'title', title_url)
    logger.info(f"Job {job_id}: Uploaded title screen")
    
    # Upload end screen
    end_gcs_path = f"jobs/{job_id}/screens/end.mov"
    end_url = storage.upload_file(end_screen_path, end_gcs_path)
    job_manager.update_file_url(job_id, 'screens', 'end', end_url)
    logger.info(f"Job {job_id}: Uploaded end screen")
    
    # Also generate JPG thumbnails for both
    # TODO: Extract frames from MOV files for thumbnails
    # This is useful for preview in UI


async def _apply_countdown_padding_if_needed(
    job_id: str,
    job_manager: JobManager,
    job
) -> None:
    """
    Apply countdown padding to instrumentals if needed.
    
    If lyrics start very early (within 3 seconds), LyricsTranscriber
    adds a countdown intro ("3... 2... 1...") to the vocal audio.
    We need to pad the instrumentals to match.
    
    Single Responsibility: Only handles padding logic.
    
    Args:
        job_id: Job ID
        job_manager: Job manager instance
        job: Job object with lyrics metadata
    """
    # Check if countdown padding was added
    lyrics_metadata = job.state_data.get('lyrics_metadata', {})
    has_countdown = lyrics_metadata.get('has_countdown_padding', False)
    
    if has_countdown:
        logger.info(f"Job {job_id}: Countdown padding detected, applying to instrumentals")
        
        # Transition to APPLYING_PADDING state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.APPLYING_PADDING,
            progress=52,
            message="Synchronizing countdown padding"
        )
        
        # TODO: Implement padding application
        # This requires:
        # 1. Download instrumental stems from GCS
        # 2. Add silence to beginning
        # 3. Re-upload padded versions
        # For now, we'll skip this and just transition back
        
        logger.info(f"Job {job_id}: Padding applied (TODO: implement actual padding)")
    else:
        logger.info(f"Job {job_id}: No countdown padding needed")

