"""
Audio search API routes for artist+title search mode.

This module provides endpoints for:
1. Creating a job with audio search (artist+title without file)
2. Getting search results for a job
3. Selecting an audio source to download

The flow is:
1. POST /api/audio-search/search - Create job and search for audio
2. GET /api/audio-search/{job_id}/results - Get search results
3. POST /api/audio-search/{job_id}/select - Select audio source
"""
import asyncio
import logging
import os
import tempfile
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field

from backend.models.job import JobCreate, JobStatus
from backend.services.job_manager import JobManager
from backend.services.storage_service import StorageService
from backend.services.worker_service import get_worker_service
from backend.services.credential_manager import get_credential_manager, CredentialStatus
from backend.services.audio_search_service import (
    get_audio_search_service,
    AudioSearchResult,
    AudioSearchError,
    NoResultsError,
    DownloadError,
)
from backend.config import get_settings
from backend.version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audio-search"])

# Initialize services
job_manager = JobManager()
storage_service = StorageService()
worker_service = get_worker_service()


# ============================================================================
# Pydantic models
# ============================================================================

class AudioSearchRequest(BaseModel):
    """Request to search for audio by artist and title."""
    artist: str = Field(..., description="Artist name to search for")
    title: str = Field(..., description="Song title to search for")
    
    # Auto-download mode
    auto_download: bool = Field(False, description="Automatically select best result and download")
    
    # Processing options
    enable_cdg: bool = Field(True, description="Generate CDG+MP3 package")
    enable_txt: bool = Field(True, description="Generate TXT+MP3 package")
    
    # Finalisation options
    brand_prefix: Optional[str] = Field(None, description="Brand code prefix (e.g., NOMAD)")
    enable_youtube_upload: bool = Field(False, description="Upload to YouTube")
    youtube_description: Optional[str] = Field(None, description="YouTube video description text")
    discord_webhook_url: Optional[str] = Field(None, description="Discord webhook URL for notifications")
    
    # Distribution options
    dropbox_path: Optional[str] = Field(None, description="Dropbox folder path for organized output")
    gdrive_folder_id: Optional[str] = Field(None, description="Google Drive folder ID for public share uploads")
    
    # Lyrics configuration
    lyrics_artist: Optional[str] = Field(None, description="Override artist name for lyrics search")
    lyrics_title: Optional[str] = Field(None, description="Override title for lyrics search")
    subtitle_offset_ms: int = Field(0, description="Subtitle timing offset in milliseconds")
    
    # Audio separation model configuration
    clean_instrumental_model: Optional[str] = Field(None, description="Model for clean instrumental separation")
    backing_vocals_models: Optional[List[str]] = Field(None, description="Models for backing vocals separation")
    other_stems_models: Optional[List[str]] = Field(None, description="Models for other stems")


class AudioSearchResultResponse(BaseModel):
    """A single audio search result.
    
    Contains all fields needed for rich display using flacfetch's
    shared formatting functions.
    """
    index: int
    title: str
    artist: str
    provider: str  # Maps to source_name in Release
    url: Optional[str] = None  # Maps to download_url in Release (may be None for remote)
    duration: Optional[int] = None  # Maps to duration_seconds in Release
    quality: Optional[str] = None  # Stringified quality
    source_id: Optional[str] = None  # Maps to info_hash in Release
    seeders: Optional[int] = None
    target_file: Optional[str] = None
    # Additional fields for rich display (from Release.to_dict())
    year: Optional[int] = None
    label: Optional[str] = None
    edition_info: Optional[str] = None
    release_type: Optional[str] = None
    channel: Optional[str] = None  # For YouTube
    view_count: Optional[int] = None  # For YouTube
    size_bytes: Optional[int] = None
    target_file_size: Optional[int] = None
    track_pattern: Optional[str] = None
    match_score: Optional[float] = None
    # Pre-computed display fields
    formatted_size: Optional[str] = None
    formatted_duration: Optional[str] = None
    formatted_views: Optional[str] = None
    is_lossless: Optional[bool] = None
    quality_str: Optional[str] = None
    # Full quality object for Release.from_dict()
    quality_data: Optional[Dict[str, Any]] = None


class AudioSearchResponse(BaseModel):
    """Response from audio search."""
    status: str
    job_id: str
    message: str
    results: Optional[List[AudioSearchResultResponse]] = None
    results_count: int = 0
    auto_download: bool = False
    server_version: str


class AudioSelectRequest(BaseModel):
    """Request to select an audio source."""
    selection_index: int = Field(..., description="Index of the selected audio source from search results")


class AudioSelectResponse(BaseModel):
    """Response from audio source selection."""
    status: str
    job_id: str
    message: str
    selected_index: int
    selected_title: str
    selected_artist: str
    selected_provider: str


def extract_request_metadata(request: Request, created_from: str = "audio_search") -> Dict[str, Any]:
    """Extract metadata from request for job tracking."""
    headers = dict(request.headers)
    
    client_ip = headers.get('x-forwarded-for', '').split(',')[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host
    
    user_agent = headers.get('user-agent', '')
    environment = headers.get('x-environment', '')
    client_id = headers.get('x-client-id', '')
    
    custom_headers = {}
    for key, value in headers.items():
        if key.lower().startswith('x-') and key.lower() not in ('x-forwarded-for', 'x-forwarded-proto', 'x-forwarded-host'):
            custom_headers[key] = value
    
    return {
        'client_ip': client_ip,
        'user_agent': user_agent,
        'environment': environment,
        'client_id': client_id,
        'server_version': VERSION,
        'created_from': created_from,
        'custom_headers': custom_headers,
    }


async def _trigger_workers_parallel(job_id: str) -> None:
    """Trigger both audio and lyrics workers in parallel."""
    await asyncio.gather(
        worker_service.trigger_audio_worker(job_id),
        worker_service.trigger_lyrics_worker(job_id)
    )


async def _download_and_start_processing(
    job_id: str,
    selection_index: int,
    audio_search_service,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Download selected audio and start job processing.
    
    This is called either:
    - Immediately after search if auto_download=True
    - When user calls the select endpoint
    
    For remote flacfetch downloads (torrent sources), the file is downloaded
    on the flacfetch VM and uploaded directly to GCS. For local downloads
    (YouTube), the file is downloaded locally and then uploaded to GCS.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Get search results from state_data
    search_results = job.state_data.get('audio_search_results', [])
    if not search_results:
        raise HTTPException(status_code=400, detail="No search results available")
    
    if selection_index < 0 or selection_index >= len(search_results):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid selection index {selection_index}. Valid range: 0-{len(search_results)-1}"
        )
    
    selected = search_results[selection_index]
    
    # Transition to downloading state
    job_manager.transition_to_state(
        job_id=job_id,
        new_status=JobStatus.DOWNLOADING_AUDIO,
        progress=10,
        message=f"Downloading from {selected['provider']}: {selected['artist']} - {selected['title']}",
        state_data_updates={
            'selected_audio_index': selection_index,
            'selected_audio_provider': selected['provider'],
        }
    )
    
    try:
        # Determine if this is a remote torrent download
        is_torrent_source = selected.get('provider') in ['Redacted', 'OPS']
        is_remote_enabled = audio_search_service.is_remote_enabled()
        
        # For remote torrent downloads, have flacfetch VM upload directly to GCS
        if is_torrent_source and is_remote_enabled:
            # Generate GCS path for remote upload
            gcs_destination = f"uploads/{job_id}/audio/"
            
            logger.info(f"Using remote download with GCS upload to: {gcs_destination}")
            
            result = audio_search_service.download(
                result_index=selection_index,
                output_dir="",  # Not used for remote
                gcs_path=gcs_destination,
            )
            
            # For remote downloads, filepath is already the GCS path
            if result.filepath.startswith("gs://"):
                # Extract the path portion after the bucket name
                # Format: gs://bucket/uploads/job_id/audio/filename.flac
                parts = result.filepath.replace("gs://", "").split("/", 1)
                if len(parts) == 2:
                    audio_gcs_path = parts[1]
                else:
                    audio_gcs_path = result.filepath
                filename = os.path.basename(result.filepath)
            else:
                # Fallback: treat as local path (shouldn't happen for remote)
                filename = os.path.basename(result.filepath)
                audio_gcs_path = f"uploads/{job_id}/audio/{filename}"
                
                logger.warning(f"Remote download returned local path: {result.filepath}, uploading manually")
                with open(result.filepath, 'rb') as f:
                    storage_service.upload_fileobj(f, audio_gcs_path, content_type='audio/flac')
            
            logger.info(f"Remote download complete, GCS path: {audio_gcs_path}")
        else:
            # Local download (YouTube or fallback)
            temp_dir = tempfile.mkdtemp(prefix=f"audio_download_{job_id}_")
            
            result = audio_search_service.download(
                result_index=selection_index,
                output_dir=temp_dir,
            )
            
            # Upload to GCS
            filename = os.path.basename(result.filepath)
            audio_gcs_path = f"uploads/{job_id}/audio/{filename}"
            
            with open(result.filepath, 'rb') as f:
                storage_service.upload_fileobj(
                    f,
                    audio_gcs_path,
                    content_type='audio/flac'  # flacfetch typically returns FLAC
                )
            
            logger.info(f"Uploaded audio to GCS: {audio_gcs_path}")
            
            # Clean up temp file
            try:
                os.remove(result.filepath)
                os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to clean up temp files: {e}")
        
        # Update job with GCS path and transition to DOWNLOADING
        job_manager.update_job(job_id, {
            'input_media_gcs_path': audio_gcs_path,
            'filename': filename,
        })
        
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.DOWNLOADING,
            progress=15,
            message="Audio downloaded, starting processing"
        )
        
        # Trigger workers
        background_tasks.add_task(_trigger_workers_parallel, job_id)
        
        return {
            'selected_index': selection_index,
            'selected_title': selected['title'],
            'selected_artist': selected['artist'],
            'selected_provider': selected['provider'],
        }
        
    except DownloadError as e:
        job_manager.fail_job(job_id, f"Audio download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")
    except Exception as e:
        job_manager.fail_job(job_id, f"Audio download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")


@router.post("/audio-search/search", response_model=AudioSearchResponse)
async def search_audio(
    request: Request,
    background_tasks: BackgroundTasks,
    body: AudioSearchRequest,
):
    """
    Search for audio by artist and title, creating a new job.
    
    This endpoint:
    1. Creates a job in PENDING state
    2. Searches for audio using flacfetch
    3. Either returns search results for user selection, or
    4. If auto_download=True, automatically selects best and starts processing
    
    Use cases:
    - Interactive mode (default): Returns results, user calls /select endpoint
    - Auto mode (auto_download=True): Automatically selects and downloads best
    """
    try:
        # Apply default distribution settings
        settings = get_settings()
        effective_dropbox_path = body.dropbox_path or settings.default_dropbox_path
        effective_gdrive_folder_id = body.gdrive_folder_id or settings.default_gdrive_folder_id
        effective_discord_webhook_url = body.discord_webhook_url or settings.default_discord_webhook_url
        
        # Validate credentials if distribution services are requested
        invalid_services = []
        credential_manager = get_credential_manager()
        
        if body.enable_youtube_upload:
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
                    "message": f"Distribution services need re-authorization: {', '.join(invalid_services)}",
                    "invalid_services": invalid_services,
                }
            )
        
        # Extract request metadata
        request_metadata = extract_request_metadata(request, created_from="audio_search")
        
        # Create job
        job_create = JobCreate(
            artist=body.artist,
            title=body.title,
            enable_cdg=body.enable_cdg,
            enable_txt=body.enable_txt,
            brand_prefix=body.brand_prefix,
            enable_youtube_upload=body.enable_youtube_upload,
            youtube_description=body.youtube_description,
            discord_webhook_url=effective_discord_webhook_url,
            dropbox_path=effective_dropbox_path,
            gdrive_folder_id=effective_gdrive_folder_id,
            lyrics_artist=body.lyrics_artist,
            lyrics_title=body.lyrics_title,
            subtitle_offset_ms=body.subtitle_offset_ms,
            clean_instrumental_model=body.clean_instrumental_model,
            backing_vocals_models=body.backing_vocals_models,
            other_stems_models=body.other_stems_models,
            audio_search_artist=body.artist,
            audio_search_title=body.title,
            auto_download=body.auto_download,
            request_metadata=request_metadata,
        )
        job = job_manager.create_job(job_create)
        job_id = job.job_id
        
        logger.info(f"Created job {job_id} for audio search: {body.artist} - {body.title}")
        
        # Update job with audio search fields
        job_manager.update_job(job_id, {
            'audio_search_artist': body.artist,
            'audio_search_title': body.title,
            'auto_download': body.auto_download,
        })
        
        # Transition to searching state
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.SEARCHING_AUDIO,
            progress=5,
            message=f"Searching for: {body.artist} - {body.title}"
        )
        
        # Perform search
        audio_search_service = get_audio_search_service()
        
        try:
            search_results = audio_search_service.search(body.artist, body.title)
        except NoResultsError as e:
            job_manager.fail_job(job_id, f"No audio sources found for: {body.artist} - {body.title}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "no_results",
                    "message": str(e),
                    "job_id": job_id,
                }
            )
        except AudioSearchError as e:
            job_manager.fail_job(job_id, f"Audio search failed: {e}")
            raise HTTPException(status_code=500, detail=f"Search failed: {e}")
        
        # Store results in job state_data
        results_dicts = [r.to_dict() for r in search_results]
        job_manager.update_job(job_id, {
            'state_data': {
                'audio_search_results': results_dicts,
                'audio_search_count': len(results_dicts),
            }
        })
        
        # If auto_download, select best and start processing
        if body.auto_download:
            best_index = audio_search_service.select_best(search_results)
            
            logger.info(f"Auto-download enabled, selecting result {best_index}")
            
            selection_info = await _download_and_start_processing(
                job_id=job_id,
                selection_index=best_index,
                audio_search_service=audio_search_service,
                background_tasks=background_tasks,
            )
            
            return AudioSearchResponse(
                status="success",
                job_id=job_id,
                message=f"Audio found and download started: {selection_info['selected_artist']} - {selection_info['selected_title']} ({selection_info['selected_provider']})",
                results=None,  # Don't return results in auto mode
                results_count=len(search_results),
                auto_download=True,
                server_version=VERSION,
            )
        
        # Interactive mode: return results for user selection
        job_manager.transition_to_state(
            job_id=job_id,
            new_status=JobStatus.AWAITING_AUDIO_SELECTION,
            progress=10,
            message=f"Found {len(search_results)} audio sources. Waiting for selection."
        )
        
        # Convert to response format with full Release data for rich display
        result_responses = []
        for r in search_results:
            # Get full serialized data from raw_result if available
            raw_dict = {}
            if r.raw_result:
                try:
                    raw_dict = r.raw_result.to_dict()
                except AttributeError:
                    pass  # Not a Release object
            
            result_responses.append(
                AudioSearchResultResponse(
                    index=r.index,
                    title=r.title,
                    artist=r.artist,
                    provider=r.provider,
                    url=r.url,
                    duration=r.duration,
                    quality=r.quality,
                    source_id=r.source_id,
                    seeders=raw_dict.get('seeders') or r.seeders,
                    target_file=raw_dict.get('target_file') or r.target_file,
                    # Additional fields for rich display
                    year=raw_dict.get('year'),
                    label=raw_dict.get('label'),
                    edition_info=raw_dict.get('edition_info'),
                    release_type=raw_dict.get('release_type'),
                    channel=raw_dict.get('channel'),
                    view_count=raw_dict.get('view_count'),
                    size_bytes=raw_dict.get('size_bytes'),
                    target_file_size=raw_dict.get('target_file_size'),
                    track_pattern=raw_dict.get('track_pattern'),
                    match_score=raw_dict.get('match_score'),
                    # Pre-computed display fields
                    formatted_size=raw_dict.get('formatted_size'),
                    formatted_duration=raw_dict.get('formatted_duration'),
                    formatted_views=raw_dict.get('formatted_views'),
                    is_lossless=raw_dict.get('is_lossless'),
                    quality_str=raw_dict.get('quality_str'),
                    # Full quality object for Release.from_dict()
                    quality_data=raw_dict.get('quality'),
                )
            )
        
        return AudioSearchResponse(
            status="awaiting_selection",
            job_id=job_id,
            message=f"Found {len(search_results)} audio sources. Call /api/audio-search/{job_id}/select to choose one.",
            results=result_responses,
            results_count=len(search_results),
            auto_download=False,
            server_version=VERSION,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in audio search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio-search/{job_id}/results")
async def get_audio_search_results(job_id: str):
    """
    Get audio search results for a job.
    
    Returns the cached search results so user can select one.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    search_results = job.state_data.get('audio_search_results', [])
    
    if not search_results:
        raise HTTPException(
            status_code=400,
            detail="No search results available for this job"
        )
    
    return {
        "status": "success",
        "job_id": job_id,
        "job_status": job.status,
        "artist": job.audio_search_artist or job.artist,
        "title": job.audio_search_title or job.title,
        "results": search_results,
        "results_count": len(search_results),
    }


@router.post("/audio-search/{job_id}/select", response_model=AudioSelectResponse)
async def select_audio_source(
    job_id: str,
    background_tasks: BackgroundTasks,
    body: AudioSelectRequest,
):
    """
    Select an audio source and start job processing.
    
    This endpoint:
    1. Validates the job is awaiting selection
    2. Downloads the selected audio
    3. Uploads to GCS
    4. Triggers audio and lyrics workers
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Verify job is awaiting selection
    if job.status != JobStatus.AWAITING_AUDIO_SELECTION:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not awaiting audio selection (status: {job.status})"
        )
    
    # Re-instantiate the audio search service (it caches raw results from search)
    # For production, we'd need to re-search or store raw results differently
    audio_search_service = get_audio_search_service()
    
    # Re-run search to populate the cache
    # This is necessary because the service caches raw results in memory
    search_results = job.state_data.get('audio_search_results', [])
    if not search_results:
        raise HTTPException(status_code=400, detail="No search results cached for this job")
    
    artist = job.audio_search_artist or job.artist
    title = job.audio_search_title or job.title
    
    try:
        # Re-search to populate cache
        audio_search_service.search(artist, title)
    except Exception as e:
        logger.warning(f"Re-search failed, trying direct download: {e}")
    
    selection_info = await _download_and_start_processing(
        job_id=job_id,
        selection_index=body.selection_index,
        audio_search_service=audio_search_service,
        background_tasks=background_tasks,
    )
    
    return AudioSelectResponse(
        status="success",
        job_id=job_id,
        message="Audio selected and download started",
        selected_index=selection_info['selected_index'],
        selected_title=selection_info['selected_title'],
        selected_artist=selection_info['selected_artist'],
        selected_provider=selection_info['selected_provider'],
    )


