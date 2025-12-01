"""
Video generation and finalization worker.

Handles the final stage of karaoke generation:
1. Download all assets (lyrics video, instrumental, screens)
2. Remux lyrics video with selected instrumental
3. Concatenate with title and end screens
4. Encode to multiple formats (Cloud Build for parallel processing)
5. Generate CDG and TXT packages
6. Upload final outputs to GCS
7. Transition to COMPLETE

This is the longest-running worker (15-20 minutes for encoding).
Uses Cloud Build for CPU-intensive video encoding to avoid blocking Cloud Run.

Integrates with karaoke_gen.karaoke_finalise.KaraokeFinalise.

SOLID Principles:
- Single Responsibility: Only final video generation and packaging
- Open/Closed: Extensible for new formats without modification
- Dependency Inversion: Depends on KaraokeFinalise abstraction
- Interface Segregation: Focused on finalization only
"""
import logging
import os
import shutil
import tempfile
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

from backend.models.job import JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.config import get_settings

# Import from karaoke_gen package
from karaoke_gen.karaoke_finalise.karaoke_finalise import KaraokeFinalise


logger = logging.getLogger(__name__)


async def generate_video(job_id: str) -> bool:
    """
    Generate final karaoke videos in multiple formats.
    
    This is the main entry point for the video worker.
    Called after user selects instrumental audio.
    
    This is the longest-running stage (15-20 minutes).
    For production, encoding should use Cloud Build for better performance.
    
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
    
    # Validate prerequisites
    if not _validate_prerequisites(job):
        logger.error(f"Job {job_id}: Prerequisites not met for video generation")
        return False
    
    # Create temporary working directory
    temp_dir = tempfile.mkdtemp(prefix=f"karaoke_video_{job_id}_")
    
    try:
        logger.info(f"Starting video generation for job {job_id}")
        
        # Transition to GENERATING_VIDEO state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.GENERATING_VIDEO,
            progress=70,
            message="Generating karaoke video"
        )
        
        # Download all required assets
        assets = await _download_assets(job_id, job, temp_dir, storage)
        if not assets:
            raise Exception("Failed to download required assets")
        
        # Initialize KaraokeFinalise
        finalise = _create_finalise_instance(job, temp_dir)
        
        # Remux lyrics video with selected instrumental
        karaoke_video = await _remux_video_with_instrumental(
            job_id=job_id,
            job=job,
            finalise=finalise,
            assets=assets,
            temp_dir=temp_dir
        )
        
        if not karaoke_video:
            raise Exception("Video remux failed")
        
        # Concatenate with screens AND encode to multiple formats
        # This is done in one step by KaraokeFinalise.remux_and_encode_output_video_files
        # For MVP: encode locally (15-20 minutes)
        # For production: use Cloud Build for parallel encoding
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.ENCODING,
            progress=75,
            message="Concatenating and encoding (15-20 min)"
        )
        
        encoded_videos = await _concatenate_with_screens(
            job_id=job_id,
            finalise=finalise,
            karaoke_video=karaoke_video,
            assets=assets,
            temp_dir=temp_dir
        )
        
        if not encoded_videos:
            raise Exception("Video encoding failed")
        
        # Upload encoded videos
        await _upload_videos(
            job_id=job_id,
            job_manager=job_manager,
            storage=storage,
            encoded_videos=encoded_videos
        )
        
        # Generate CDG and TXT packages if enabled
        if job.enable_cdg or job.enable_txt:
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.PACKAGING,
                progress=95,
                message="Generating CDG/TXT packages"
            )
            
            packages = await _generate_packages(
                job_id=job_id,
                job=job,
                finalise=finalise,
                assets=assets,
                temp_dir=temp_dir
            )
            
            if packages:
                await _upload_packages(
                    job_id=job_id,
                    job_manager=job_manager,
                    storage=storage,
                    packages=packages
                )
        
        # Mark job as complete
        logger.info(f"Job {job_id}: Video generation complete")
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.COMPLETE,
            progress=100,
            message="Karaoke generation complete!"
        )
        
        # TODO: Trigger distribution worker if YouTube upload or notifications enabled
        # if job.enable_youtube_upload or job.webhook_url or job.user_email:
        #     await trigger_distribution_worker(job_id)
        
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
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.debug(f"Cleaned up temp directory: {temp_dir}")


def _validate_prerequisites(job) -> bool:
    """
    Validate that all prerequisites are met for video generation.
    
    Required:
    - Screens generated (title + end)
    - Lyrics reviewed and corrected
    - Instrumental selected
    - Lyrics video exists
    
    Args:
        job: Job object
        
    Returns:
        True if prerequisites met, False otherwise
    """
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


async def _download_assets(
    job_id: str,
    job,
    temp_dir: str,
    storage: StorageService
) -> Optional[Dict[str, str]]:
    """
    Download all required assets from GCS.
    
    Args:
        job_id: Job ID
        job: Job object
        temp_dir: Temporary directory
        storage: Storage service
        
    Returns:
        Dict of asset paths, or None if failed
    """
    try:
        assets = {}
        
        # Download lyrics video
        lyrics_video_url = job.file_urls['videos']['with_vocals']
        lyrics_video_path = os.path.join(temp_dir, "with_vocals.mkv")
        storage.download_file(lyrics_video_url, lyrics_video_path)
        assets['lyrics_video'] = lyrics_video_path
        logger.info(f"Job {job_id}: Downloaded lyrics video")
        
        # Download selected instrumental
        instrumental_selection = job.state_data['instrumental_selection']
        instrumental_key = 'instrumental_clean' if instrumental_selection == 'clean' else 'instrumental_with_backing'
        instrumental_url = job.file_urls['stems'][instrumental_key]
        instrumental_path = os.path.join(temp_dir, f"instrumental_{instrumental_selection}.flac")
        storage.download_file(instrumental_url, instrumental_path)
        assets['instrumental'] = instrumental_path
        logger.info(f"Job {job_id}: Downloaded instrumental ({instrumental_selection})")
        
        # Download title screen
        title_url = job.file_urls['screens']['title']
        title_path = os.path.join(temp_dir, "title.mov")
        storage.download_file(title_url, title_path)
        assets['title'] = title_path
        logger.info(f"Job {job_id}: Downloaded title screen")
        
        # Download end screen
        end_url = job.file_urls['screens']['end']
        end_path = os.path.join(temp_dir, "end.mov")
        storage.download_file(end_url, end_path)
        assets['end'] = end_path
        logger.info(f"Job {job_id}: Downloaded end screen")
        
        # Download corrected lyrics if available
        lyrics_urls = job.file_urls.get('lyrics', {})
        if 'lrc' in lyrics_urls:
            lrc_url = lyrics_urls['lrc']
            lrc_path = os.path.join(temp_dir, "lyrics.lrc")
            storage.download_file(lrc_url, lrc_path)
            assets['lrc'] = lrc_path
            logger.info(f"Job {job_id}: Downloaded LRC file")
        
        return assets
        
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to download assets: {e}", exc_info=True)
        return None


def _create_finalise_instance(job, temp_dir: str) -> KaraokeFinalise:
    """
    Create KaraokeFinalise instance with server-side mode enabled.
    
    Args:
        job: Job object
        temp_dir: Temporary directory
        
    Returns:
        KaraokeFinalise instance configured for cloud deployment
    """
    return KaraokeFinalise(
        logger=logger,
        log_level=logging.INFO,
        dry_run=False,
        instrumental_format="flac",
        enable_cdg=job.enable_cdg if hasattr(job, 'enable_cdg') else False,
        enable_txt=job.enable_txt if hasattr(job, 'enable_txt') else False,
        non_interactive=True,  # Critical for server-side operation
        server_side_mode=True,  # Enable server-side optimizations
    )


async def _remux_video_with_instrumental(
    job_id: str,
    job,
    finalise: KaraokeFinalise,
    assets: Dict[str, str],
    temp_dir: str
) -> Optional[str]:
    """
    Remux lyrics video with selected instrumental.
    
    Replaces the original audio track with the instrumental.
    
    Args:
        job_id: Job ID
        job: Job object
        finalise: KaraokeFinalise instance
        assets: Dict of asset paths
        temp_dir: Temporary directory
        
    Returns:
        Path to remuxed video, or None if failed
    """
    try:
        logger.info(f"Job {job_id}: Remuxing video with instrumental")
        
        # Output karaoke video path
        karaoke_video = os.path.join(temp_dir, "karaoke.mp4")
        
        # Use KaraokeFinalise to remux
        finalise.remux_with_instrumental(
            with_vocals_file=assets['lyrics_video'],
            instrumental_audio=assets['instrumental'],
            output_file=karaoke_video
        )
        
        if os.path.exists(karaoke_video):
            logger.info(f"Job {job_id}: Video remuxed successfully")
            return karaoke_video
        else:
            logger.error(f"Job {job_id}: Remux returned no file")
            return None
            
    except Exception as e:
        logger.error(f"Job {job_id}: Remux error: {e}", exc_info=True)
        return None


async def _concatenate_with_screens(
    job_id: str,
    finalise: KaraokeFinalise,
    karaoke_video: str,
    assets: Dict[str, str],
    temp_dir: str
) -> Optional[Dict[str, str]]:
    """
    Concatenate karaoke video with title and end screens.
    
    Uses KaraokeFinalise's remux_and_encode_output_video_files which:
    1. Remuxes karaoke video with instrumental (already done)
    2. Concatenates with title and end screens
    3. Encodes to all formats in one go
    
    Final structure: Title (5s) + Karaoke + End (5s)
    
    Args:
        job_id: Job ID
        finalise: KaraokeFinalise instance
        karaoke_video: Path to karaoke video
        assets: Dict of asset paths
        temp_dir: Temporary directory
        
    Returns:
        Dict of format → path for all encoded videos, or None if failed
    """
    try:
        logger.info(f"Job {job_id}: Preparing input/output files for encoding")
        
        # Prepare input files dict for KaraokeFinalise
        input_files = {
            "title_mov": assets['title'],
            "end_mov": assets['end'],
            "instrumental_audio": assets['instrumental'],
        }
        
        # Prepare output files dict
        output_files = {
            "karaoke_mp4": karaoke_video,  # Already created by remux
            "with_vocals_mp4": os.path.join(temp_dir, "with_vocals.mp4"),
            "final_karaoke_lossless_mp4": os.path.join(temp_dir, "lossless_4k.mp4"),
            "final_karaoke_lossless_mkv": os.path.join(temp_dir, "lossless_4k.mkv"),
            "final_karaoke_lossy_mp4": os.path.join(temp_dir, "lossy_4k.mp4"),
            "final_karaoke_lossy_720p_mp4": os.path.join(temp_dir, "lossy_720p.mp4"),
        }
        
        logger.info(f"Job {job_id}: Starting concatenation and encoding (this will take 15-20 minutes)")
        
        # This method does:
        # 1. Concatenates title + karaoke + end
        # 2. Encodes to all 4 formats
        finalise.remux_and_encode_output_video_files(
            with_vocals_file=assets['lyrics_video'],
            input_files=input_files,
            output_files=output_files
        )
        
        # Check that all outputs were created
        encoded_videos = {}
        for format_key in ["final_karaoke_lossless_mp4", "final_karaoke_lossless_mkv", 
                          "final_karaoke_lossy_mp4", "final_karaoke_lossy_720p_mp4"]:
            if os.path.exists(output_files[format_key]):
                # Map to simpler format names
                simple_name = format_key.replace("final_karaoke_", "")
                encoded_videos[simple_name] = output_files[format_key]
                logger.info(f"Job {job_id}: Format {simple_name} encoded successfully")
            else:
                logger.warning(f"Job {job_id}: Format {format_key} not created")
        
        if encoded_videos:
            logger.info(f"Job {job_id}: Encoding complete ({len(encoded_videos)} formats)")
            return encoded_videos
        else:
            logger.error(f"Job {job_id}: No formats encoded successfully")
            return None
            
    except Exception as e:
        logger.error(f"Job {job_id}: Concatenation/encoding error: {e}", exc_info=True)
        return None


async def _upload_videos(
    job_id: str,
    job_manager: JobManager,
    storage: StorageService,
    encoded_videos: Dict[str, str]
) -> None:
    """
    Upload all encoded videos to GCS.
    
    Args:
        job_id: Job ID
        job_manager: Job manager
        storage: Storage service
        encoded_videos: Dict of format → path
    """
    for format_name, local_path in encoded_videos.items():
        try:
            gcs_path = f"jobs/{job_id}/finals/{format_name}.{_get_extension(format_name)}"
            url = storage.upload_file(local_path, gcs_path)
            job_manager.update_file_url(job_id, 'finals', format_name, url)
            logger.info(f"Job {job_id}: Uploaded {format_name}")
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to upload {format_name}: {e}")


def _get_extension(format_name: str) -> str:
    """Get file extension for format name."""
    if 'mkv' in format_name:
        return 'mkv'
    return 'mp4'


async def _generate_packages(
    job_id: str,
    job,
    finalise: KaraokeFinalise,
    assets: Dict[str, str],
    temp_dir: str
) -> Optional[Dict[str, str]]:
    """
    Generate CDG and TXT packages using KaraokeFinalise.
    
    Args:
        job_id: Job ID
        job: Job object
        finalise: KaraokeFinalise instance
        assets: Dict of asset paths
        temp_dir: Temporary directory
        
    Returns:
        Dict of package type → path, or None if failed
    """
    try:
        packages = {}
        
        # Prepare input/output files for package generation
        input_files = {
            "karaoke_lrc": assets.get('lrc'),
            "instrumental_audio": assets['instrumental'],
        }
        
        # Generate CDG package if enabled
        if job.enable_cdg and input_files["karaoke_lrc"]:
            logger.info(f"Job {job_id}: Generating CDG package")
            
            output_files = {
                "final_karaoke_cdg_zip": os.path.join(temp_dir, "karaoke_cdg.zip"),
                "karaoke_mp3": os.path.join(temp_dir, "karaoke.mp3"),
                "karaoke_cdg": os.path.join(temp_dir, "karaoke.cdg"),
            }
            
            finalise.create_cdg_zip_file(
                input_files=input_files,
                output_files=output_files,
                artist=job.artist,
                title=job.title
            )
            
            if os.path.exists(output_files["final_karaoke_cdg_zip"]):
                packages['cdg'] = output_files["final_karaoke_cdg_zip"]
                logger.info(f"Job {job_id}: CDG package generated")
            else:
                logger.warning(f"Job {job_id}: CDG package creation failed")
        
        # Generate TXT package if enabled
        if job.enable_txt and input_files["karaoke_lrc"]:
            logger.info(f"Job {job_id}: Generating TXT package")
            
            output_files = {
                "final_karaoke_txt_zip": os.path.join(temp_dir, "karaoke_txt.zip"),
                "karaoke_txt": os.path.join(temp_dir, "karaoke.txt"),
            }
            # Note: TXT also needs the MP3 from CDG generation
            if 'cdg' in packages:
                output_files["karaoke_mp3"] = os.path.join(temp_dir, "karaoke.mp3")
            
            finalise.create_txt_zip_file(
                input_files=input_files,
                output_files=output_files
            )
            
            if os.path.exists(output_files["final_karaoke_txt_zip"]):
                packages['txt'] = output_files["final_karaoke_txt_zip"]
                logger.info(f"Job {job_id}: TXT package generated")
            else:
                logger.warning(f"Job {job_id}: TXT package creation failed")
        
        return packages if packages else None
        
    except Exception as e:
        logger.error(f"Job {job_id}: Package generation error: {e}", exc_info=True)
        return None


async def _upload_packages(
    job_id: str,
    job_manager: JobManager,
    storage: StorageService,
    packages: Dict[str, str]
) -> None:
    """
    Upload package files to GCS.
    
    Args:
        job_id: Job ID
        job_manager: Job manager
        storage: Storage service
        packages: Dict of package type → path
    """
    for package_type, local_path in packages.items():
        try:
            gcs_path = f"jobs/{job_id}/packages/{package_type}.zip"
            url = storage.upload_file(local_path, gcs_path)
            job_manager.update_file_url(job_id, 'packages', f'{package_type}_zip', url)
            logger.info(f"Job {job_id}: Uploaded {package_type} package")
        except Exception as e:
            logger.error(f"Job {job_id}: Failed to upload {package_type} package: {e}")

