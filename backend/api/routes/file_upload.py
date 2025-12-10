"""
File upload route for local file submission with style configuration support.
"""
import asyncio
import json
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.models.job import JobCreate, JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.services.worker_service import get_worker_service
from backend.services.credential_manager import get_credential_manager, CredentialStatus
from backend.config import get_settings
from backend.version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter(tags=["jobs"])

# Initialize services
job_manager = JobManager()
storage_service = StorageService()
worker_service = get_worker_service()


# File extension validation
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
ALLOWED_FONT_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2'}


async def _trigger_workers_parallel(job_id: str) -> None:
    """
    Trigger both audio and lyrics workers in parallel.
    
    FastAPI's BackgroundTasks runs async tasks sequentially, so we use
    asyncio.gather to ensure both workers start at the same time.
    """
    await asyncio.gather(
        worker_service.trigger_audio_worker(job_id),
        worker_service.trigger_lyrics_worker(job_id)
    )


@router.post("/jobs/upload")
async def upload_and_create_job(
    background_tasks: BackgroundTasks,
    # Required fields
    file: UploadFile = File(..., description="Audio file to process"),
    artist: str = Form(..., description="Artist name"),
    title: str = Form(..., description="Song title"),
    # Style configuration files (optional)
    style_params: Optional[UploadFile] = File(None, description="Style parameters JSON file"),
    style_intro_background: Optional[UploadFile] = File(None, description="Intro/title screen background image"),
    style_karaoke_background: Optional[UploadFile] = File(None, description="Karaoke video background image"),
    style_end_background: Optional[UploadFile] = File(None, description="End screen background image"),
    style_font: Optional[UploadFile] = File(None, description="Font file (TTF/OTF)"),
    style_cdg_instrumental_background: Optional[UploadFile] = File(None, description="CDG instrumental background"),
    style_cdg_title_background: Optional[UploadFile] = File(None, description="CDG title screen background"),
    style_cdg_outro_background: Optional[UploadFile] = File(None, description="CDG outro screen background"),
    # Processing options
    enable_cdg: bool = Form(True, description="Generate CDG+MP3 package"),
    enable_txt: bool = Form(True, description="Generate TXT+MP3 package"),
    # Finalisation options
    brand_prefix: Optional[str] = Form(None, description="Brand code prefix (e.g., NOMAD)"),
    enable_youtube_upload: bool = Form(False, description="Upload to YouTube"),
    youtube_description: Optional[str] = Form(None, description="YouTube video description text"),
    discord_webhook_url: Optional[str] = Form(None, description="Discord webhook URL for notifications"),
    webhook_url: Optional[str] = Form(None, description="Generic webhook URL"),
    user_email: Optional[str] = Form(None, description="User email for notifications"),
    # Distribution options (native API - preferred for remote CLI)
    dropbox_path: Optional[str] = Form(None, description="Dropbox folder path for organized output (e.g., /Karaoke/Tracks-Organized)"),
    gdrive_folder_id: Optional[str] = Form(None, description="Google Drive folder ID for public share uploads"),
    # Legacy distribution options (rclone - deprecated)
    organised_dir_rclone_root: Optional[str] = Form(None, description="[Deprecated] rclone remote path for Dropbox upload"),
):
    """
    Upload an audio file and create a karaoke generation job with full style configuration.
    
    This endpoint:
    1. Validates all uploaded files
    2. Creates a job in Firestore
    3. Uploads all files to GCS (audio, style JSON, images, fonts)
    4. Updates job with GCS paths
    5. Triggers the audio and lyrics workers
    
    Style Configuration:
    - style_params: JSON file with style configuration (fonts, colors, regions)
    - style_*_background: Background images for various screens
    - style_font: Custom font file
    
    The style_params JSON can reference the uploaded images/fonts by their original
    filenames, and the backend will update the paths to GCS locations.
    """
    try:
        # Validate main audio file type
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audio file type '{file_ext}'. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
            )
        
        # Validate style files if provided
        if style_params and not style_params.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Style params must be a JSON file")
        
        for img_file, name in [
            (style_intro_background, "intro_background"),
            (style_karaoke_background, "karaoke_background"),
            (style_end_background, "end_background"),
            (style_cdg_instrumental_background, "cdg_instrumental_background"),
            (style_cdg_title_background, "cdg_title_background"),
            (style_cdg_outro_background, "cdg_outro_background"),
        ]:
            if img_file:
                ext = Path(img_file.filename).suffix.lower()
                if ext not in ALLOWED_IMAGE_EXTENSIONS:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid image file type '{ext}' for {name}. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
                    )
        
        if style_font:
            ext = Path(style_font.filename).suffix.lower()
            if ext not in ALLOWED_FONT_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid font file type '{ext}'. Allowed: {', '.join(ALLOWED_FONT_EXTENSIONS)}"
                )
        
        # Apply default distribution settings from environment if not provided
        settings = get_settings()
        effective_dropbox_path = dropbox_path or settings.default_dropbox_path
        effective_gdrive_folder_id = gdrive_folder_id or settings.default_gdrive_folder_id
        effective_discord_webhook_url = discord_webhook_url or settings.default_discord_webhook_url
        
        if effective_dropbox_path and not dropbox_path:
            logger.info(f"Using default dropbox_path: {effective_dropbox_path}")
        if effective_gdrive_folder_id and not gdrive_folder_id:
            logger.info(f"Using default gdrive_folder_id: {effective_gdrive_folder_id}")
        if effective_discord_webhook_url and not discord_webhook_url:
            logger.info(f"Using default discord_webhook_url (from env)")
        
        # Validate credentials for requested distribution services (including defaults)
        # This prevents accepting jobs that will fail later due to missing credentials
        invalid_services = []
        credential_manager = get_credential_manager()
        
        if enable_youtube_upload:
            result = credential_manager.check_youtube_credentials()
            if result.status != CredentialStatus.VALID:
                invalid_services.append(f"youtube ({result.message})")
        
        if effective_dropbox_path:
            result = credential_manager.check_dropbox_credentials()
            if result.status != CredentialStatus.VALID:
                invalid_services.append(f"dropbox ({result.message})")
        
        if effective_gdrive_folder_id:
            result = credential_manager.check_gdrive_credentials()
            if result.status != CredentialStatus.VALID:
                invalid_services.append(f"gdrive ({result.message})")
        
        if invalid_services:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "credentials_invalid",
                    "message": f"The following distribution services need re-authorization: {', '.join(invalid_services)}",
                    "invalid_services": invalid_services,
                    "auth_url": "/api/auth/status"
                }
            )
        
        # Create job first to get job_id
        job_create = JobCreate(
            artist=artist,
            title=title,
            filename=file.filename,
            enable_cdg=enable_cdg,
            enable_txt=enable_txt,
            brand_prefix=brand_prefix,
            enable_youtube_upload=enable_youtube_upload,
            youtube_description=youtube_description,
            discord_webhook_url=effective_discord_webhook_url,
            webhook_url=webhook_url,
            user_email=user_email,
            # Native API distribution (preferred for remote CLI)
            dropbox_path=effective_dropbox_path,
            gdrive_folder_id=effective_gdrive_folder_id,
            # Legacy rclone distribution (deprecated)
            organised_dir_rclone_root=organised_dir_rclone_root,
        )
        job = job_manager.create_job(job_create)
        job_id = job.job_id
        
        logger.info(f"Created job {job_id} for {artist} - {title}")
        
        # Upload main audio file to GCS
        audio_gcs_path = f"uploads/{job_id}/audio/{file.filename}"
        logger.info(f"Uploading audio to GCS: {audio_gcs_path}")
        storage_service.upload_fileobj(
            file.file,
            audio_gcs_path,
            content_type=file.content_type or 'audio/flac'
        )
        
        # Track style assets
        style_assets = {}
        
        # Upload style files if provided
        if style_params:
            style_gcs_path = f"uploads/{job_id}/style/style_params.json"
            logger.info(f"Uploading style params to GCS: {style_gcs_path}")
            storage_service.upload_fileobj(
                style_params.file,
                style_gcs_path,
                content_type='application/json'
            )
            style_assets['style_params'] = style_gcs_path
        
        # Upload background images
        for img_file, asset_key in [
            (style_intro_background, "intro_background"),
            (style_karaoke_background, "karaoke_background"),
            (style_end_background, "end_background"),
            (style_cdg_instrumental_background, "cdg_instrumental_background"),
            (style_cdg_title_background, "cdg_title_background"),
            (style_cdg_outro_background, "cdg_outro_background"),
        ]:
            if img_file:
                gcs_path = f"uploads/{job_id}/style/{asset_key}{Path(img_file.filename).suffix.lower()}"
                logger.info(f"Uploading {asset_key} to GCS: {gcs_path}")
                storage_service.upload_fileobj(
                    img_file.file,
                    gcs_path,
                    content_type=img_file.content_type or 'image/png'
                )
                style_assets[asset_key] = gcs_path
        
        # Upload font file
        if style_font:
            font_gcs_path = f"uploads/{job_id}/style/font{Path(style_font.filename).suffix.lower()}"
            logger.info(f"Uploading font to GCS: {font_gcs_path}")
            storage_service.upload_fileobj(
                style_font.file,
                font_gcs_path,
                content_type='font/ttf'
            )
            style_assets['font'] = font_gcs_path
        
        # Update job with all GCS paths
        update_data = {
            'input_media_gcs_path': audio_gcs_path,
            'filename': file.filename,
            'enable_cdg': enable_cdg,
            'enable_txt': enable_txt,
        }
        
        if style_assets:
            update_data['style_assets'] = style_assets
            if 'style_params' in style_assets:
                update_data['style_params_gcs_path'] = style_assets['style_params']
        
        if brand_prefix:
            update_data['brand_prefix'] = brand_prefix
        if discord_webhook_url:
            update_data['discord_webhook_url'] = discord_webhook_url
        if youtube_description:
            update_data['youtube_description_template'] = youtube_description
        
        # Native API distribution (preferred for remote CLI)
        if dropbox_path:
            update_data['dropbox_path'] = dropbox_path
        if gdrive_folder_id:
            update_data['gdrive_folder_id'] = gdrive_folder_id
        
        # Legacy rclone distribution (deprecated)
        if organised_dir_rclone_root:
            update_data['organised_dir_rclone_root'] = organised_dir_rclone_root
        
        job_manager.update_job(job_id, update_data)
        
        # Verify the update
        updated_job = job_manager.get_job(job_id)
        if not hasattr(updated_job, 'input_media_gcs_path') or not updated_job.input_media_gcs_path:
            import asyncio
            await asyncio.sleep(0.5)
            updated_job = job_manager.get_job(job_id)
            if not hasattr(updated_job, 'input_media_gcs_path') or not updated_job.input_media_gcs_path:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to update job with GCS paths"
                )
        
        logger.info(f"All files uploaded for job {job_id}")
        if style_assets:
            logger.info(f"Style assets: {list(style_assets.keys())}")
        
        # Transition job to DOWNLOADING state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.DOWNLOADING,
            progress=5,
            message="Files uploaded, preparing to process"
        )
        
        # Trigger workers in parallel using asyncio.gather
        # (FastAPI's BackgroundTasks runs async tasks sequentially)
        background_tasks.add_task(_trigger_workers_parallel, job_id)
        
        # Build distribution services info for response
        distribution_services: Dict[str, Any] = {}
        
        if effective_dropbox_path:
            dropbox_result = credential_manager.check_dropbox_credentials()
            distribution_services["dropbox"] = {
                "enabled": True,
                "path": effective_dropbox_path,
                "credentials_valid": dropbox_result.status == CredentialStatus.VALID,
                "using_default": dropbox_path is None,
            }
        
        if effective_gdrive_folder_id:
            gdrive_result = credential_manager.check_gdrive_credentials()
            distribution_services["gdrive"] = {
                "enabled": True,
                "folder_id": effective_gdrive_folder_id,
                "credentials_valid": gdrive_result.status == CredentialStatus.VALID,
                "using_default": gdrive_folder_id is None,
            }
        
        if enable_youtube_upload:
            youtube_result = credential_manager.check_youtube_credentials()
            distribution_services["youtube"] = {
                "enabled": True,
                "credentials_valid": youtube_result.status == CredentialStatus.VALID,
            }
        
        if effective_discord_webhook_url:
            distribution_services["discord"] = {
                "enabled": True,
                "using_default": discord_webhook_url is None,
            }
        
        return {
            "status": "success",
            "job_id": job_id,
            "message": "Files uploaded successfully. Processing started.",
            "filename": file.filename,
            "style_assets_uploaded": list(style_assets.keys()) if style_assets else [],
            "server_version": VERSION,
            "distribution_services": distribution_services,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
