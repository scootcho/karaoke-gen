#!/usr/bin/env python
"""
Remote CLI for karaoke-gen - Submit jobs to a cloud-hosted backend.

This CLI provides the same interface as karaoke-gen but processes jobs on a cloud backend.
Set KARAOKE_GEN_URL environment variable to your cloud backend URL.

Usage:
    karaoke-gen-remote <filepath> <artist> <title>
    karaoke-gen-remote --resume <job_id>
    karaoke-gen-remote --retry <job_id>
    karaoke-gen-remote --list
    karaoke-gen-remote --cancel <job_id>
    karaoke-gen-remote --delete <job_id>
"""
# Suppress SyntaxWarnings from third-party dependencies (pydub, syrics)
# that have invalid escape sequences in regex patterns (not yet fixed for Python 3.12+)
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
warnings.filterwarnings("ignore", category=SyntaxWarning, module="syrics")

import json
import logging
import os
import platform
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from .cli_args import create_parser, process_style_overrides, is_url, is_file


class JobStatus(str, Enum):
    """Job status values (matching backend)."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    SEPARATING_STAGE1 = "separating_stage1"
    SEPARATING_STAGE2 = "separating_stage2"
    AUDIO_COMPLETE = "audio_complete"
    TRANSCRIBING = "transcribing"
    CORRECTING = "correcting"
    LYRICS_COMPLETE = "lyrics_complete"
    GENERATING_SCREENS = "generating_screens"
    APPLYING_PADDING = "applying_padding"
    AWAITING_REVIEW = "awaiting_review"
    IN_REVIEW = "in_review"
    REVIEW_COMPLETE = "review_complete"
    RENDERING_VIDEO = "rendering_video"
    AWAITING_INSTRUMENTAL_SELECTION = "awaiting_instrumental_selection"
    INSTRUMENTAL_SELECTED = "instrumental_selected"
    GENERATING_VIDEO = "generating_video"
    ENCODING = "encoding"
    PACKAGING = "packaging"
    UPLOADING = "uploading"
    NOTIFYING = "notifying"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class Config:
    """Configuration for the remote CLI."""
    service_url: str
    review_ui_url: str
    poll_interval: int
    output_dir: str
    auth_token: Optional[str] = None
    non_interactive: bool = False  # Auto-accept defaults for testing
    # Job tracking metadata (sent as headers for filtering/tracking)
    environment: str = ""  # test/production/development
    client_id: str = ""  # Customer/user identifier


class RemoteKaraokeClient:
    """Client for interacting with the karaoke-gen cloud backend."""
    
    ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'}
    ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    ALLOWED_FONT_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2'}
    
    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = requests.Session()
        self._setup_auth()
    
    def _setup_auth(self) -> None:
        """Set up authentication and tracking headers."""
        if self.config.auth_token:
            self.session.headers['Authorization'] = f'Bearer {self.config.auth_token}'
        
        # Set up job tracking headers (used for filtering and operational management)
        if self.config.environment:
            self.session.headers['X-Environment'] = self.config.environment
        if self.config.client_id:
            self.session.headers['X-Client-ID'] = self.config.client_id
        
        # Always include CLI version as user-agent
        from importlib import metadata
        try:
            version = metadata.version("karaoke-gen")
        except metadata.PackageNotFoundError:
            version = "unknown"
        self.session.headers['User-Agent'] = f'karaoke-gen-remote/{version}'
    
    def _get_auth_token_from_gcloud(self) -> Optional[str]:
        """Get auth token from gcloud CLI."""
        try:
            result = subprocess.run(
                ['gcloud', 'auth', 'print-identity-token'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
        except FileNotFoundError:
            return None
    
    def refresh_auth(self) -> bool:
        """Refresh authentication token."""
        token = self._get_auth_token_from_gcloud()
        if token:
            self.config.auth_token = token
            self.session.headers['Authorization'] = f'Bearer {token}'
            return True
        return False
    
    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request."""
        url = f"{self.config.service_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        return response
    
    def _upload_file_to_signed_url(self, signed_url: str, file_path: str, content_type: str) -> bool:
        """
        Upload a file directly to GCS using a signed URL.
        
        Args:
            signed_url: The signed URL from the backend
            file_path: Local path to the file to upload
            content_type: MIME type for the Content-Type header
            
        Returns:
            True if upload succeeded, False otherwise
        """
        try:
            with open(file_path, 'rb') as f:
                # Use a fresh requests session (not self.session) because
                # signed URLs should not have our auth headers
                response = requests.put(
                    signed_url,
                    data=f,
                    headers={'Content-Type': content_type},
                    timeout=600  # 10 minutes for large files
                )
            
            if response.status_code in (200, 201):
                return True
            else:
                self.logger.error(f"Failed to upload to signed URL: HTTP {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error uploading to signed URL: {e}")
            return False
    
    def _get_content_type(self, file_path: str) -> str:
        """Get the MIME content type for a file based on its extension."""
        ext = Path(file_path).suffix.lower()
        
        content_types = {
            # Audio
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.flac': 'audio/flac',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg',
            '.aac': 'audio/aac',
            # Images
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            # Fonts
            '.ttf': 'font/ttf',
            '.otf': 'font/otf',
            '.woff': 'font/woff',
            '.woff2': 'font/woff2',
            # Other
            '.json': 'application/json',
            '.txt': 'text/plain',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.rtf': 'application/rtf',
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def _parse_style_params(self, style_params_path: str) -> Dict[str, str]:
        """
        Parse style_params.json and extract file paths that need to be uploaded.
        
        Returns a dict mapping asset_key -> local_file_path for files that exist.
        """
        asset_files = {}
        
        try:
            with open(style_params_path, 'r') as f:
                style_params = json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to parse style_params.json: {e}")
            return asset_files
        
        # Map of style param paths to asset keys
        file_mappings = [
            ('intro', 'background_image', 'style_intro_background'),
            ('intro', 'font', 'style_font'),
            ('karaoke', 'background_image', 'style_karaoke_background'),
            ('karaoke', 'font_path', 'style_font'),
            ('end', 'background_image', 'style_end_background'),
            ('end', 'font', 'style_font'),
            ('cdg', 'font_path', 'style_font'),
            ('cdg', 'instrumental_background', 'style_cdg_instrumental_background'),
            ('cdg', 'title_screen_background', 'style_cdg_title_background'),
            ('cdg', 'outro_background', 'style_cdg_outro_background'),
        ]
        
        for section, key, asset_key in file_mappings:
            if section in style_params and key in style_params[section]:
                file_path = style_params[section][key]
                if file_path and os.path.isfile(file_path):
                    # Don't duplicate font uploads
                    if asset_key not in asset_files:
                        asset_files[asset_key] = file_path
                        self.logger.info(f"  Found style asset: {asset_key} -> {file_path}")
        
        return asset_files
    
    def submit_job_from_url(
        self,
        url: str,
        artist: Optional[str] = None,
        title: Optional[str] = None,
        enable_cdg: bool = True,
        enable_txt: bool = True,
        brand_prefix: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        youtube_description: Optional[str] = None,
        organised_dir_rclone_root: Optional[str] = None,
        enable_youtube_upload: bool = False,
        dropbox_path: Optional[str] = None,
        gdrive_folder_id: Optional[str] = None,
        lyrics_artist: Optional[str] = None,
        lyrics_title: Optional[str] = None,
        subtitle_offset_ms: int = 0,
        clean_instrumental_model: Optional[str] = None,
        backing_vocals_models: Optional[list] = None,
        other_stems_models: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Submit a new karaoke generation job from a YouTube/online URL.
        
        The backend will download the audio from the URL and process it.
        Artist and title will be auto-detected from the URL if not provided.
        
        Note: Custom style configuration is not supported for URL-based jobs.
        If you need custom styles, download the audio locally first and use
        the regular file upload flow with submit_job().
        
        Args:
            url: YouTube or other video URL to download audio from
            artist: Artist name (optional - auto-detected if not provided)
            title: Song title (optional - auto-detected if not provided)
            enable_cdg: Generate CDG+MP3 package
            enable_txt: Generate TXT+MP3 package
            brand_prefix: Brand code prefix (e.g., "NOMAD")
            discord_webhook_url: Discord webhook for notifications
            youtube_description: YouTube video description
            organised_dir_rclone_root: Legacy rclone path (deprecated)
            enable_youtube_upload: Enable YouTube upload
            dropbox_path: Dropbox folder path for organized output (native API)
            gdrive_folder_id: Google Drive folder ID for public share (native API)
            lyrics_artist: Override artist name for lyrics search
            lyrics_title: Override title for lyrics search
            subtitle_offset_ms: Subtitle timing offset in milliseconds
            clean_instrumental_model: Model for clean instrumental separation
            backing_vocals_models: List of models for backing vocals separation
            other_stems_models: List of models for other stems (bass, drums, etc.)
        """
        self.logger.info(f"Submitting URL-based job: {url}")
        
        # Build request payload
        create_request = {
            'url': url,
            'enable_cdg': enable_cdg,
            'enable_txt': enable_txt,
        }
        
        if artist:
            create_request['artist'] = artist
        if title:
            create_request['title'] = title
        if brand_prefix:
            create_request['brand_prefix'] = brand_prefix
        if discord_webhook_url:
            create_request['discord_webhook_url'] = discord_webhook_url
        if youtube_description:
            create_request['youtube_description'] = youtube_description
        if enable_youtube_upload:
            create_request['enable_youtube_upload'] = enable_youtube_upload
        if dropbox_path:
            create_request['dropbox_path'] = dropbox_path
        if gdrive_folder_id:
            create_request['gdrive_folder_id'] = gdrive_folder_id
        if organised_dir_rclone_root:
            create_request['organised_dir_rclone_root'] = organised_dir_rclone_root
        if lyrics_artist:
            create_request['lyrics_artist'] = lyrics_artist
        if lyrics_title:
            create_request['lyrics_title'] = lyrics_title
        if subtitle_offset_ms != 0:
            create_request['subtitle_offset_ms'] = subtitle_offset_ms
        if clean_instrumental_model:
            create_request['clean_instrumental_model'] = clean_instrumental_model
        if backing_vocals_models:
            create_request['backing_vocals_models'] = backing_vocals_models
        if other_stems_models:
            create_request['other_stems_models'] = other_stems_models
        
        self.logger.info(f"Creating URL-based job at {self.config.service_url}/api/jobs/create-from-url")
        
        response = self._request('POST', '/api/jobs/create-from-url', json=create_request)
        
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error creating job from URL: {error_detail}")
        
        result = response.json()
        if result.get('status') != 'success':
            raise RuntimeError(f"Error creating job from URL: {result}")
        
        job_id = result['job_id']
        detected_artist = result.get('detected_artist')
        detected_title = result.get('detected_title')
        
        self.logger.info(f"Job {job_id} created from URL")
        if detected_artist:
            self.logger.info(f"  Artist: {detected_artist}")
        if detected_title:
            self.logger.info(f"  Title: {detected_title}")
        
        return result
    
    def submit_job(
        self, 
        filepath: str, 
        artist: str, 
        title: str,
        style_params_path: Optional[str] = None,
        enable_cdg: bool = True,
        enable_txt: bool = True,
        brand_prefix: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        youtube_description: Optional[str] = None,
        organised_dir_rclone_root: Optional[str] = None,
        enable_youtube_upload: bool = False,
        # Native API distribution (uses server-side credentials)
        dropbox_path: Optional[str] = None,
        gdrive_folder_id: Optional[str] = None,
        # Lyrics configuration
        lyrics_artist: Optional[str] = None,
        lyrics_title: Optional[str] = None,
        lyrics_file: Optional[str] = None,
        subtitle_offset_ms: int = 0,
        # Audio separation model configuration
        clean_instrumental_model: Optional[str] = None,
        backing_vocals_models: Optional[list] = None,
        other_stems_models: Optional[list] = None,
        # Existing instrumental (Batch 3)
        existing_instrumental: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a new karaoke generation job with optional style configuration.
        
        Uses signed URL upload flow to bypass Cloud Run's 32MB request body limit:
        1. Create job and get signed upload URLs from backend
        2. Upload files directly to GCS using signed URLs
        3. Notify backend that uploads are complete to start processing
        
        Args:
            filepath: Path to audio file
            artist: Artist name
            title: Song title
            style_params_path: Path to style_params.json (optional)
            enable_cdg: Generate CDG+MP3 package
            enable_txt: Generate TXT+MP3 package
            brand_prefix: Brand code prefix (e.g., "NOMAD")
            discord_webhook_url: Discord webhook for notifications
            youtube_description: YouTube video description
            organised_dir_rclone_root: Legacy rclone path (deprecated)
            enable_youtube_upload: Enable YouTube upload
            dropbox_path: Dropbox folder path for organized output (native API)
            gdrive_folder_id: Google Drive folder ID for public share (native API)
            lyrics_artist: Override artist name for lyrics search
            lyrics_title: Override title for lyrics search
            lyrics_file: Path to user-provided lyrics file
            subtitle_offset_ms: Subtitle timing offset in milliseconds
            clean_instrumental_model: Model for clean instrumental separation
            backing_vocals_models: List of models for backing vocals separation
            other_stems_models: List of models for other stems (bass, drums, etc.)
            existing_instrumental: Path to existing instrumental file to use instead of AI separation
        """
        file_path = Path(filepath)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        ext = file_path.suffix.lower()
        if ext not in self.ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Allowed: {', '.join(self.ALLOWED_AUDIO_EXTENSIONS)}"
            )
        
        # Step 1: Build list of files to upload
        files_info = []
        local_files = {}  # file_type -> local_path
        
        # Main audio file
        audio_content_type = self._get_content_type(filepath)
        files_info.append({
            'filename': file_path.name,
            'content_type': audio_content_type,
            'file_type': 'audio'
        })
        local_files['audio'] = filepath
        self.logger.info(f"Will upload audio: {filepath}")
        
        # Parse style params and find referenced files
        style_assets = {}
        if style_params_path and os.path.isfile(style_params_path):
            self.logger.info(f"Parsing style configuration: {style_params_path}")
            style_assets = self._parse_style_params(style_params_path)
            
            # Add style_params.json
            files_info.append({
                'filename': Path(style_params_path).name,
                'content_type': 'application/json',
                'file_type': 'style_params'
            })
            local_files['style_params'] = style_params_path
            self.logger.info(f"  Will upload style_params.json")
        
        # Add each style asset file
        for asset_key, asset_path in style_assets.items():
            if os.path.isfile(asset_path):
                content_type = self._get_content_type(asset_path)
                files_info.append({
                    'filename': Path(asset_path).name,
                    'content_type': content_type,
                    'file_type': asset_key  # e.g., 'style_intro_background'
                })
                local_files[asset_key] = asset_path
                self.logger.info(f"  Will upload {asset_key}: {asset_path}")
        
        # Add lyrics file if provided
        if lyrics_file and os.path.isfile(lyrics_file):
            content_type = self._get_content_type(lyrics_file)
            files_info.append({
                'filename': Path(lyrics_file).name,
                'content_type': content_type,
                'file_type': 'lyrics_file'
            })
            local_files['lyrics_file'] = lyrics_file
            self.logger.info(f"Will upload lyrics file: {lyrics_file}")
        
        # Add existing instrumental file if provided (Batch 3)
        if existing_instrumental and os.path.isfile(existing_instrumental):
            content_type = self._get_content_type(existing_instrumental)
            files_info.append({
                'filename': Path(existing_instrumental).name,
                'content_type': content_type,
                'file_type': 'existing_instrumental'
            })
            local_files['existing_instrumental'] = existing_instrumental
            self.logger.info(f"Will upload existing instrumental: {existing_instrumental}")
        
        # Step 2: Create job and get signed upload URLs
        self.logger.info(f"Creating job at {self.config.service_url}/api/jobs/create-with-upload-urls")
        
        create_request = {
            'artist': artist,
            'title': title,
            'files': files_info,
            'enable_cdg': enable_cdg,
            'enable_txt': enable_txt,
        }
        
        if brand_prefix:
            create_request['brand_prefix'] = brand_prefix
        if discord_webhook_url:
            create_request['discord_webhook_url'] = discord_webhook_url
        if youtube_description:
            create_request['youtube_description'] = youtube_description
        if enable_youtube_upload:
            create_request['enable_youtube_upload'] = enable_youtube_upload
        if dropbox_path:
            create_request['dropbox_path'] = dropbox_path
        if gdrive_folder_id:
            create_request['gdrive_folder_id'] = gdrive_folder_id
        if organised_dir_rclone_root:
            create_request['organised_dir_rclone_root'] = organised_dir_rclone_root
        if lyrics_artist:
            create_request['lyrics_artist'] = lyrics_artist
        if lyrics_title:
            create_request['lyrics_title'] = lyrics_title
        if subtitle_offset_ms != 0:
            create_request['subtitle_offset_ms'] = subtitle_offset_ms
        if clean_instrumental_model:
            create_request['clean_instrumental_model'] = clean_instrumental_model
        if backing_vocals_models:
            create_request['backing_vocals_models'] = backing_vocals_models
        if other_stems_models:
            create_request['other_stems_models'] = other_stems_models
        
        response = self._request('POST', '/api/jobs/create-with-upload-urls', json=create_request)
        
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error creating job: {error_detail}")
        
        create_result = response.json()
        if create_result.get('status') != 'success':
            raise RuntimeError(f"Error creating job: {create_result}")
        
        job_id = create_result['job_id']
        upload_urls = create_result['upload_urls']
        
        self.logger.info(f"Job {job_id} created. Uploading {len(upload_urls)} files directly to storage...")
        
        # Step 3: Upload each file directly to GCS using signed URLs
        uploaded_files = []
        for url_info in upload_urls:
            file_type = url_info['file_type']
            signed_url = url_info['upload_url']
            content_type = url_info['content_type']
            local_path = local_files.get(file_type)
            
            if not local_path:
                self.logger.warning(f"No local file found for file_type: {file_type}")
                continue
            
            # Calculate file size for logging
            file_size = os.path.getsize(local_path)
            file_size_mb = file_size / (1024 * 1024)
            self.logger.info(f"  Uploading {file_type} ({file_size_mb:.1f} MB)...")
            
            success = self._upload_file_to_signed_url(signed_url, local_path, content_type)
            if not success:
                raise RuntimeError(f"Failed to upload {file_type} to storage")
            
            uploaded_files.append(file_type)
            self.logger.info(f"  ✓ Uploaded {file_type}")
        
        # Step 4: Notify backend that uploads are complete
        self.logger.info(f"Notifying backend that uploads are complete...")
        
        complete_request = {
            'uploaded_files': uploaded_files
        }
        
        response = self._request('POST', f'/api/jobs/{job_id}/uploads-complete', json=complete_request)
        
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error completing uploads: {error_detail}")
        
        result = response.json()
        if result.get('status') != 'success':
            raise RuntimeError(f"Error completing uploads: {result}")
        
        # Log distribution services info if available
        if 'distribution_services' in result:
            dist_services = result['distribution_services']
            self.logger.info("")
            self.logger.info("Distribution Services:")
            
            for service_name, service_info in dist_services.items():
                if service_info.get('enabled'):
                    status = "✓" if service_info.get('credentials_valid', True) else "✗"
                    default_note = " (default)" if service_info.get('using_default') else ""
                    
                    if service_name == 'dropbox':
                        path = service_info.get('path', '')
                        self.logger.info(f"  {status} Dropbox: {path}{default_note}")
                    elif service_name == 'gdrive':
                        folder_id = service_info.get('folder_id', '')
                        self.logger.info(f"  {status} Google Drive: folder {folder_id}{default_note}")
                    elif service_name == 'youtube':
                        self.logger.info(f"  {status} YouTube: enabled")
                    elif service_name == 'discord':
                        self.logger.info(f"  {status} Discord: notifications{default_note}")
        
        return result
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job status and details."""
        response = self._request('GET', f'/api/jobs/{job_id}')
        if response.status_code == 404:
            raise ValueError(f"Job not found: {job_id}")
        if response.status_code != 200:
            raise RuntimeError(f"Error getting job: {response.text}")
        return response.json()
    
    def cancel_job(self, job_id: str, reason: str = "User requested") -> Dict[str, Any]:
        """Cancel a running job. Stops processing but keeps the job record."""
        response = self._request(
            'POST',
            f'/api/jobs/{job_id}/cancel',
            json={'reason': reason}
        )
        if response.status_code == 404:
            raise ValueError(f"Job not found: {job_id}")
        if response.status_code == 400:
            try:
                error_detail = response.json().get('detail', response.text)
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Cannot cancel job: {error_detail}")
        if response.status_code != 200:
            raise RuntimeError(f"Error cancelling job: {response.text}")
        return response.json()
    
    def delete_job(self, job_id: str, delete_files: bool = True) -> Dict[str, Any]:
        """Delete a job and optionally its files. Permanent removal."""
        response = self._request(
            'DELETE',
            f'/api/jobs/{job_id}',
            params={'delete_files': str(delete_files).lower()}
        )
        if response.status_code == 404:
            raise ValueError(f"Job not found: {job_id}")
        if response.status_code != 200:
            raise RuntimeError(f"Error deleting job: {response.text}")
        return response.json()

    def retry_job(self, job_id: str) -> Dict[str, Any]:
        """Retry a failed job from the last successful checkpoint."""
        response = self._request(
            'POST',
            f'/api/jobs/{job_id}/retry'
        )
        if response.status_code == 404:
            raise ValueError(f"Job not found: {job_id}")
        if response.status_code == 400:
            try:
                error_detail = response.json().get('detail', response.text)
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Cannot retry job: {error_detail}")
        if response.status_code != 200:
            raise RuntimeError(f"Error retrying job: {response.text}")
        return response.json()

    def list_jobs(
        self,
        status: Optional[str] = None,
        environment: Optional[str] = None,
        client_id: Optional[str] = None,
        limit: int = 100
    ) -> list:
        """
        List all jobs with optional filters.
        
        Args:
            status: Filter by job status
            environment: Filter by request_metadata.environment
            client_id: Filter by request_metadata.client_id
            limit: Maximum number of jobs to return
        """
        params = {'limit': limit}
        if status:
            params['status'] = status
        if environment:
            params['environment'] = environment
        if client_id:
            params['client_id'] = client_id
        response = self._request('GET', '/api/jobs', params=params)
        if response.status_code != 200:
            raise RuntimeError(f"Error listing jobs: {response.text}")
        return response.json()
    
    def bulk_delete_jobs(
        self,
        environment: Optional[str] = None,
        client_id: Optional[str] = None,
        status: Optional[str] = None,
        confirm: bool = False,
        delete_files: bool = True
    ) -> Dict[str, Any]:
        """
        Delete multiple jobs matching filter criteria.
        
        Args:
            environment: Delete jobs with this environment
            client_id: Delete jobs from this client
            status: Delete jobs with this status
            confirm: Must be True to execute deletion
            delete_files: Also delete GCS files
            
        Returns:
            Dict with deletion results or preview
        """
        params = {
            'confirm': str(confirm).lower(),
            'delete_files': str(delete_files).lower(),
        }
        if environment:
            params['environment'] = environment
        if client_id:
            params['client_id'] = client_id
        if status:
            params['status'] = status
        
        response = self._request('DELETE', '/api/jobs', params=params)
        if response.status_code == 400:
            try:
                error_detail = response.json().get('detail', response.text)
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error: {error_detail}")
        if response.status_code != 200:
            raise RuntimeError(f"Error bulk deleting jobs: {response.text}")
        return response.json()
    
    def get_instrumental_options(self, job_id: str) -> Dict[str, Any]:
        """Get instrumental options for selection."""
        response = self._request('GET', f'/api/jobs/{job_id}/instrumental-options')
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error getting instrumental options: {error_detail}")
        return response.json()
    
    def select_instrumental(self, job_id: str, selection: str) -> Dict[str, Any]:
        """Submit instrumental selection."""
        response = self._request(
            'POST',
            f'/api/jobs/{job_id}/select-instrumental',
            json={'selection': selection}
        )
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error selecting instrumental: {error_detail}")
        return response.json()
    
    def get_download_urls(self, job_id: str) -> Dict[str, Any]:
        """Get signed download URLs for all job output files."""
        response = self._request('GET', f'/api/jobs/{job_id}/download-urls')
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error getting download URLs: {error_detail}")
        return response.json()
    
    def download_file_via_url(self, url: str, local_path: str) -> bool:
        """Download file from a URL via HTTP."""
        try:
            # Handle relative URLs by prepending service URL
            if url.startswith('/'):
                url = f"{self.config.service_url}{url}"
            
            response = requests.get(url, stream=True, timeout=600)
            if response.status_code != 200:
                return False
            
            # Ensure parent directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        except Exception:
            return False
    
    def download_file_via_gsutil(self, gcs_path: str, local_path: str) -> bool:
        """Download file from GCS using gsutil (fallback method)."""
        try:
            bucket_name = os.environ.get('KARAOKE_GEN_BUCKET', 'karaoke-gen-storage-nomadkaraoke')
            gcs_uri = f"gs://{bucket_name}/{gcs_path}"
            
            result = subprocess.run(
                ['gsutil', 'cp', gcs_uri, local_path],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def get_worker_logs(self, job_id: str, since_index: int = 0) -> Dict[str, Any]:
        """
        Get worker logs for debugging.
        
        Args:
            job_id: Job ID
            since_index: Return only logs after this index (for pagination/polling)
            
        Returns:
            {
                "logs": [{"timestamp": "...", "level": "INFO", "worker": "audio", "message": "..."}],
                "next_index": 42,
                "total_logs": 42
            }
        """
        response = self._request(
            'GET',
            f'/api/jobs/{job_id}/logs',
            params={'since_index': since_index}
        )
        if response.status_code != 200:
            return {"logs": [], "next_index": since_index, "total_logs": 0}
        return response.json()
    
    def get_review_data(self, job_id: str) -> Dict[str, Any]:
        """Get the current review/correction data for a job."""
        response = self._request('GET', f'/api/review/{job_id}/correction-data')
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error getting review data: {error_detail}")
        return response.json()
    
    def complete_review(self, job_id: str, updated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit the review completion with corrected data."""
        response = self._request(
            'POST',
            f'/api/review/{job_id}/complete',
            json=updated_data
        )
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error completing review: {error_detail}")
        return response.json()


class JobMonitor:
    """Monitor job progress with verbose logging."""
    
    def __init__(self, client: RemoteKaraokeClient, config: Config, logger: logging.Logger):
        self.client = client
        self.config = config
        self.logger = logger
        self._review_opened = False
        self._instrumental_prompted = False
        self._last_timeline_index = 0
        self._last_log_index = 0
        self._show_worker_logs = True  # Enable worker log display
        self._polls_without_updates = 0  # Track polling activity for heartbeat
        self._heartbeat_interval = 6  # Show heartbeat every N polls without updates (~30s with 5s poll)
    
    # Status descriptions for user-friendly logging
    STATUS_DESCRIPTIONS = {
        'pending': 'Job queued, waiting to start',
        'downloading': 'Downloading and preparing input files',
        'separating_stage1': 'AI audio separation (stage 1 of 2)',
        'separating_stage2': 'AI audio separation (stage 2 of 2)',
        'audio_complete': 'Audio separation complete',
        'transcribing': 'Transcribing lyrics from audio',
        'correcting': 'Auto-correcting lyrics against reference sources',
        'lyrics_complete': 'Lyrics processing complete',
        'generating_screens': 'Creating title and end screens',
        'applying_padding': 'Adding intro/outro padding',
        'awaiting_review': 'Waiting for lyrics review',
        'in_review': 'Lyrics review in progress',
        'review_complete': 'Review complete, preparing video render',
        'rendering_video': 'Rendering karaoke video with lyrics',
        'awaiting_instrumental_selection': 'Waiting for instrumental selection',
        'instrumental_selected': 'Instrumental selected, preparing final encoding',
        'generating_video': 'Downloading files for final video encoding',
        'encoding': 'Encoding final videos (15-20 min, 4 formats)',
        'packaging': 'Creating CDG/TXT packages',
        'uploading': 'Uploading to distribution services',
        'notifying': 'Sending notifications',
        'complete': 'All processing complete',
        'failed': 'Job failed',
        'cancelled': 'Job cancelled',
    }
    
    def _get_status_description(self, status: str) -> str:
        """Get user-friendly description for a status."""
        return self.STATUS_DESCRIPTIONS.get(status, status)
    
    def open_browser(self, url: str) -> None:
        """Open URL in the default browser."""
        system = platform.system()
        try:
            if system == 'Darwin':
                subprocess.run(['open', url], check=True)
            elif system == 'Linux':
                subprocess.run(['xdg-open', url], check=True, stderr=subprocess.DEVNULL)
            else:
                webbrowser.open(url)
        except Exception:
            self.logger.info(f"Please open in browser: {url}")
    
    def open_review_ui(self, job_id: str) -> None:
        """Open the lyrics review UI in browser."""
        # Build the review URL with the API endpoint
        base_api_url = f"{self.config.service_url}/api/review/{job_id}"
        encoded_api_url = urllib.parse.quote(base_api_url, safe='')
        
        # Try to get audio hash from job data
        try:
            job_data = self.client.get_job(job_id)
            audio_hash = job_data.get('audio_hash', '')
        except Exception:
            audio_hash = ''
        
        url = f"{self.config.review_ui_url}/?baseApiUrl={encoded_api_url}"
        if audio_hash:
            url += f"&audioHash={audio_hash}"
        
        self.logger.info(f"Opening lyrics review UI: {url}")
        self.open_browser(url)
    
    def handle_review(self, job_id: str) -> None:
        """Handle the lyrics review interaction."""
        self.logger.info("=" * 60)
        self.logger.info("LYRICS REVIEW NEEDED")
        self.logger.info("=" * 60)
        
        # In non-interactive mode, auto-accept the current corrections
        if self.config.non_interactive:
            self.logger.info("Non-interactive mode: Auto-accepting current corrections")
            try:
                # Get current review data
                review_data = self.client.get_review_data(job_id)
                self.logger.info("Retrieved current correction data")
                
                # Submit as-is to complete the review
                result = self.client.complete_review(job_id, review_data)
                if result.get('status') == 'success':
                    self.logger.info("Review auto-completed successfully")
                    return
                else:
                    self.logger.error(f"Failed to auto-complete review: {result}")
                    # In non-interactive mode, raise exception instead of falling back to manual
                    raise RuntimeError(f"Failed to auto-complete review: {result}")
            except Exception as e:
                self.logger.error(f"Error auto-completing review: {e}")
                # In non-interactive mode, we can't fall back to manual - raise the error
                raise RuntimeError(f"Non-interactive review failed: {e}")
        
        # Interactive mode - open browser and wait
        self.logger.info("The transcription is ready for review.")
        self.logger.info("Please review and correct the lyrics in the browser.")
        
        self.open_review_ui(job_id)
        
        self.logger.info(f"Waiting for review completion (polling every {self.config.poll_interval}s)...")
        
        # Poll until status changes from review states
        while True:
            try:
                job_data = self.client.get_job(job_id)
                current_status = job_data.get('status', 'unknown')
                
                if current_status in ['awaiting_review', 'in_review']:
                    time.sleep(self.config.poll_interval)
                else:
                    self.logger.info(f"Review completed, status: {current_status}")
                    return
            except Exception as e:
                self.logger.warning(f"Error checking review status: {e}")
                time.sleep(self.config.poll_interval)
    
    def handle_instrumental_selection(self, job_id: str) -> None:
        """Handle instrumental selection interaction."""
        self.logger.info("=" * 60)
        self.logger.info("INSTRUMENTAL SELECTION NEEDED")
        self.logger.info("=" * 60)
        
        # In non-interactive mode, auto-select clean instrumental
        if self.config.non_interactive:
            self.logger.info("Non-interactive mode: Auto-selecting clean instrumental")
            selection = 'clean'
        else:
            self.logger.info("")
            self.logger.info("Choose which instrumental track to use for the final video:")
            self.logger.info("")
            self.logger.info("  1) Clean Instrumental (no backing vocals)")
            self.logger.info("     Best for songs where you want ONLY the lead vocal removed")
            self.logger.info("")
            self.logger.info("  2) Instrumental with Backing Vocals")
            self.logger.info("     Best for songs where backing vocals add to the karaoke experience")
            self.logger.info("")
            
            selection = ""
            while not selection:
                try:
                    choice = input("Enter your choice (1 or 2): ").strip()
                    if choice == '1':
                        selection = 'clean'
                    elif choice == '2':
                        selection = 'with_backing'
                    else:
                        self.logger.error("Invalid choice. Please enter 1 or 2.")
                except KeyboardInterrupt:
                    print()
                    raise
        
        self.logger.info(f"Submitting selection: {selection}")
        
        try:
            result = self.client.select_instrumental(job_id, selection)
            if result.get('status') == 'success':
                self.logger.info(f"Selection submitted successfully: {selection}")
            else:
                self.logger.error(f"Error submitting selection: {result}")
        except Exception as e:
            self.logger.error(f"Error submitting selection: {e}")
    
    def download_outputs(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """
        Download all output files for a completed job.
        
        Downloads all files to match local CLI output structure:
        - Final videos (4 formats)
        - CDG/TXT ZIP packages (and extracts individual files)
        - Lyrics files (.ass, .lrc, .txt)
        - Audio stems with descriptive names
        - Title/End screen files (.mov, .jpg, .png)
        - With Vocals intermediate video
        """
        artist = job_data.get('artist', 'Unknown')
        title = job_data.get('title', 'Unknown')
        brand_code = job_data.get('state_data', {}).get('brand_code')
        
        # Use brand code in folder name if available
        if brand_code:
            folder_name = f"{brand_code} - {artist} - {title}"
        else:
            folder_name = f"{artist} - {title}"
        
        # Sanitize folder name
        folder_name = "".join(c for c in folder_name if c.isalnum() or c in " -_").strip()
        
        output_dir = Path(self.config.output_dir) / folder_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Downloading output files to: {output_dir}")
        
        # Get signed download URLs from the API
        try:
            download_data = self.client.get_download_urls(job_id)
            download_urls = download_data.get('download_urls', {})
        except Exception as e:
            self.logger.warning(f"Could not get signed download URLs: {e}")
            self.logger.warning("Falling back to gsutil (requires gcloud auth)")
            download_urls = {}
        
        file_urls = job_data.get('file_urls', {})
        base_name = f"{artist} - {title}"
        
        def download_file(category: str, key: str, local_path: Path, filename: str) -> bool:
            """Helper to download a file using signed URL or gsutil fallback."""
            # Try signed URL first
            signed_url = download_urls.get(category, {}).get(key)
            if signed_url:
                if self.client.download_file_via_url(signed_url, str(local_path)):
                    return True
            
            # Fall back to gsutil
            gcs_path = file_urls.get(category, {}).get(key)
            if gcs_path:
                return self.client.download_file_via_gsutil(gcs_path, str(local_path))
            return False
        
        # Download final videos
        finals = file_urls.get('finals', {})
        if finals:
            self.logger.info("Downloading final videos...")
            for key, blob_path in finals.items():
                if blob_path:
                    # Use descriptive filename
                    if 'lossless_4k_mp4' in key:
                        filename = f"{base_name} (Final Karaoke Lossless 4k).mp4"
                    elif 'lossless_4k_mkv' in key:
                        filename = f"{base_name} (Final Karaoke Lossless 4k).mkv"
                    elif 'lossy_4k' in key:
                        filename = f"{base_name} (Final Karaoke Lossy 4k).mp4"
                    elif 'lossy_720p' in key:
                        filename = f"{base_name} (Final Karaoke Lossy 720p).mp4"
                    else:
                        filename = Path(blob_path).name
                    
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if download_file('finals', key, local_path, filename):
                        self.logger.info(f"    OK: {local_path}")
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
        
        # Download CDG/TXT packages
        packages = file_urls.get('packages', {})
        if packages:
            self.logger.info("Downloading karaoke packages...")
            for key, blob_path in packages.items():
                if blob_path:
                    if 'cdg' in key.lower():
                        filename = f"{base_name} (Final Karaoke CDG).zip"
                    elif 'txt' in key.lower():
                        filename = f"{base_name} (Final Karaoke TXT).zip"
                    else:
                        filename = Path(blob_path).name
                    
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if download_file('packages', key, local_path, filename):
                        self.logger.info(f"    OK: {local_path}")
                        
                        # Extract CDG files to match local CLI (individual .cdg and .mp3 at root)
                        if 'cdg' in key.lower():
                            self._extract_cdg_files(local_path, output_dir, base_name)
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
        
        # Download lyrics files
        lyrics = file_urls.get('lyrics', {})
        if lyrics:
            self.logger.info("Downloading lyrics files...")
            for key in ['ass', 'lrc', 'corrected_txt']:
                blob_path = lyrics.get(key)
                if blob_path:
                    ext = Path(blob_path).suffix
                    filename = f"{base_name} (Karaoke){ext}"
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if download_file('lyrics', key, local_path, filename):
                        self.logger.info(f"    OK: {local_path}")
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
        
        # Download title/end screen files (video + images)
        screens = file_urls.get('screens', {})
        if screens:
            self.logger.info("Downloading title/end screens...")
            screen_mappings = {
                'title': f"{base_name} (Title).mov",
                'title_jpg': f"{base_name} (Title).jpg",
                'title_png': f"{base_name} (Title).png",
                'end': f"{base_name} (End).mov",
                'end_jpg': f"{base_name} (End).jpg",
                'end_png': f"{base_name} (End).png",
            }
            for key, filename in screen_mappings.items():
                blob_path = screens.get(key)
                if blob_path:
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if download_file('screens', key, local_path, filename):
                        self.logger.info(f"    OK: {local_path}")
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
        
        # Download with_vocals intermediate video
        videos = file_urls.get('videos', {})
        if videos:
            self.logger.info("Downloading intermediate videos...")
            if videos.get('with_vocals'):
                filename = f"{base_name} (With Vocals).mkv"
                local_path = output_dir / filename
                self.logger.info(f"  Downloading {filename}...")
                if download_file('videos', 'with_vocals', local_path, filename):
                    self.logger.info(f"    OK: {local_path}")
                else:
                    self.logger.warning(f"    FAILED: {filename}")
        
        # Download stems with descriptive names
        stems = file_urls.get('stems', {})
        if stems:
            stems_dir = output_dir / 'stems'
            stems_dir.mkdir(exist_ok=True)
            self.logger.info("Downloading audio stems...")
            
            # Map backend stem names to local CLI naming convention
            stem_name_mappings = {
                'instrumental_clean': f"{base_name} (Instrumental model_bs_roformer_ep_317_sdr_12.9755.ckpt).flac",
                'instrumental_with_backing': f"{base_name} (Instrumental +BV mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac",
                'vocals_clean': f"{base_name} (Vocals model_bs_roformer_ep_317_sdr_12.9755.ckpt).flac",
                'lead_vocals': f"{base_name} (Lead Vocals mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac",
                'backing_vocals': f"{base_name} (Backing Vocals mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt).flac",
                'bass': f"{base_name} (Bass htdemucs_6s.yaml).flac",
                'drums': f"{base_name} (Drums htdemucs_6s.yaml).flac",
                'guitar': f"{base_name} (Guitar htdemucs_6s.yaml).flac",
                'piano': f"{base_name} (Piano htdemucs_6s.yaml).flac",
                'other': f"{base_name} (Other htdemucs_6s.yaml).flac",
                'vocals': f"{base_name} (Vocals htdemucs_6s.yaml).flac",
            }
            
            for key, blob_path in stems.items():
                if blob_path:
                    # Use descriptive filename if available, otherwise use GCS filename
                    filename = stem_name_mappings.get(key, Path(blob_path).name)
                    local_path = stems_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if download_file('stems', key, local_path, filename):
                        self.logger.info(f"    OK: {local_path}")
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
            
            # Also copy instrumental files to root directory (matching local CLI)
            for src_key, dest_suffix in [
                ('instrumental_clean', 'Instrumental model_bs_roformer_ep_317_sdr_12.9755.ckpt'),
                ('instrumental_with_backing', 'Instrumental +BV mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt'),
            ]:
                if stems.get(src_key):
                    stem_file = stems_dir / stem_name_mappings.get(src_key, '')
                    if stem_file.exists():
                        dest_file = output_dir / f"{base_name} ({dest_suffix}).flac"
                        try:
                            import shutil
                            shutil.copy2(stem_file, dest_file)
                            self.logger.info(f"  Copied to root: {dest_file.name}")
                        except Exception as e:
                            self.logger.warning(f"  Failed to copy {dest_file.name}: {e}")
        
        self.logger.info("")
        self.logger.info(f"All files downloaded to: {output_dir}")
        
        # Show summary
        state_data = job_data.get('state_data', {})
        if brand_code:
            self.logger.info(f"Brand Code: {brand_code}")
        
        youtube_url = state_data.get('youtube_url')
        if youtube_url:
            self.logger.info(f"YouTube URL: {youtube_url}")
        
        # List downloaded files with sizes
        self.logger.info("")
        self.logger.info("Downloaded files:")
        total_size = 0
        for file_path in sorted(output_dir.rglob('*')):
            if file_path.is_file():
                size = file_path.stat().st_size
                total_size += size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                rel_path = file_path.relative_to(output_dir)
                self.logger.info(f"  {rel_path} ({size_str})")
        
        if total_size > 1024 * 1024 * 1024:
            total_str = f"{total_size / (1024 * 1024 * 1024):.2f} GB"
        elif total_size > 1024 * 1024:
            total_str = f"{total_size / (1024 * 1024):.1f} MB"
        else:
            total_str = f"{total_size / 1024:.1f} KB"
        self.logger.info(f"Total: {total_str}")
    
    def _extract_cdg_files(self, zip_path: Path, output_dir: Path, base_name: str) -> None:
        """
        Extract individual .cdg and .mp3 files from CDG ZIP to match local CLI output.
        
        Local CLI produces both:
        - Artist - Title (Final Karaoke CDG).zip (containing .cdg + .mp3)
        - Artist - Title (Karaoke).cdg (individual file at root)
        - Artist - Title (Karaoke).mp3 (individual file at root)
        
        Args:
            zip_path: Path to the CDG ZIP file
            output_dir: Output directory for extracted files
            base_name: Base name for output files (Artist - Title)
        """
        import zipfile
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for member in zf.namelist():
                    ext = Path(member).suffix.lower()
                    if ext in ['.cdg', '.mp3']:
                        # Extract with correct naming
                        filename = f"{base_name} (Karaoke){ext}"
                        extract_path = output_dir / filename
                        
                        # Read from zip and write to destination
                        with zf.open(member) as src:
                            with open(extract_path, 'wb') as dst:
                                dst.write(src.read())
                        
                        self.logger.info(f"    Extracted: {filename}")
        except Exception as e:
            self.logger.warning(f"  Failed to extract CDG files: {e}")
    
    def log_timeline_updates(self, job_data: Dict[str, Any]) -> None:
        """Log any new timeline events."""
        timeline = job_data.get('timeline', [])
        
        # Log any new events since last check
        for i, event in enumerate(timeline):
            if i >= self._last_timeline_index:
                timestamp = event.get('timestamp', '')
                status = event.get('status', '')
                message = event.get('message', '')
                progress = event.get('progress', '')
                
                # Format timestamp if present
                if timestamp:
                    # Truncate to just time portion if it's a full ISO timestamp
                    if 'T' in timestamp:
                        timestamp = timestamp.split('T')[1][:8]
                
                log_parts = []
                if timestamp:
                    log_parts.append(f"[{timestamp}]")
                if status:
                    log_parts.append(f"[{status}]")
                if progress:
                    log_parts.append(f"[{progress}%]")
                if message:
                    log_parts.append(message)
                
                if log_parts:
                    self.logger.info(" ".join(log_parts))
        
        self._last_timeline_index = len(timeline)
    
    def log_worker_logs(self, job_id: str) -> None:
        """Fetch and display any new worker logs."""
        if not self._show_worker_logs:
            return
        
        try:
            result = self.client.get_worker_logs(job_id, since_index=self._last_log_index)
            logs = result.get('logs', [])
            
            for log_entry in logs:
                timestamp = log_entry.get('timestamp', '')
                level = log_entry.get('level', 'INFO')
                worker = log_entry.get('worker', 'worker')
                message = log_entry.get('message', '')
                
                # Format timestamp (just time portion)
                if timestamp and 'T' in timestamp:
                    timestamp = timestamp.split('T')[1][:8]
                
                # Color-code by level (using ASCII codes for terminal)
                if level == 'ERROR':
                    level_prefix = f"\033[91m{level}\033[0m"  # Red
                elif level == 'WARNING':
                    level_prefix = f"\033[93m{level}\033[0m"  # Yellow
                else:
                    level_prefix = level
                
                # Format: [HH:MM:SS] [worker:level] message
                log_line = f"  [{timestamp}] [{worker}:{level_prefix}] {message}"
                
                # Use appropriate log level
                if level == 'ERROR':
                    self.logger.error(log_line)
                elif level == 'WARNING':
                    self.logger.warning(log_line)
                else:
                    self.logger.info(log_line)
            
            # Update index for next poll
            self._last_log_index = result.get('next_index', self._last_log_index)
            
        except Exception as e:
            # Log the error but don't fail
            self.logger.debug(f"Error fetching worker logs: {e}")
    
    def monitor(self, job_id: str) -> int:
        """Monitor job progress until completion."""
        last_status = ""
        
        self.logger.info(f"Monitoring job: {job_id}")
        self.logger.info(f"Service URL: {self.config.service_url}")
        self.logger.info(f"Polling every {self.config.poll_interval} seconds...")
        self.logger.info("")
        
        while True:
            try:
                job_data = self.client.get_job(job_id)
                
                status = job_data.get('status', 'unknown')
                artist = job_data.get('artist', '')
                title = job_data.get('title', '')
                
                # Track whether we got any new updates this poll
                had_updates = False
                prev_timeline_index = self._last_timeline_index
                prev_log_index = self._last_log_index
                
                # Log timeline updates (shows status changes and progress)
                self.log_timeline_updates(job_data)
                if self._last_timeline_index > prev_timeline_index:
                    had_updates = True
                
                # Log worker logs (shows detailed worker output for debugging)
                self.log_worker_logs(job_id)
                if self._last_log_index > prev_log_index:
                    had_updates = True
                
                # Log status changes with user-friendly descriptions
                if status != last_status:
                    description = self._get_status_description(status)
                    if last_status:
                        self.logger.info(f"Status: {status} - {description}")
                    else:
                        self.logger.info(f"Current status: {status} - {description}")
                    last_status = status
                    had_updates = True
                
                # Heartbeat: if no updates for a while, show we're still alive
                if had_updates:
                    self._polls_without_updates = 0
                else:
                    self._polls_without_updates += 1
                    if self._polls_without_updates >= self._heartbeat_interval:
                        description = self._get_status_description(status)
                        self.logger.info(f"  [Still processing: {description}]")
                        self._polls_without_updates = 0
                
                # Handle human interaction points
                if status in ['awaiting_review', 'in_review']:
                    if not self._review_opened:
                        self.logger.info("")
                        self.handle_review(job_id)
                        self._review_opened = True
                        self._last_timeline_index = 0  # Reset to catch any events during review
                        # Refresh auth token after potentially long review
                        self.client.refresh_auth()
                
                elif status == 'awaiting_instrumental_selection':
                    if not self._instrumental_prompted:
                        self.logger.info("")
                        self.handle_instrumental_selection(job_id)
                        self._instrumental_prompted = True
                
                elif status == 'complete':
                    self.logger.info("")
                    self.logger.info("=" * 60)
                    self.logger.info("JOB COMPLETE!")
                    self.logger.info("=" * 60)
                    self.logger.info(f"Track: {artist} - {title}")
                    self.logger.info("")
                    self.download_outputs(job_id, job_data)
                    return 0
                
                elif status in ['failed', 'error']:
                    self.logger.info("")
                    self.logger.error("=" * 60)
                    self.logger.error("JOB FAILED")
                    self.logger.error("=" * 60)
                    error_message = job_data.get('error_message', 'Unknown error')
                    self.logger.error(f"Error: {error_message}")
                    error_details = job_data.get('error_details')
                    if error_details:
                        self.logger.error(f"Details: {json.dumps(error_details, indent=2)}")
                    return 1
                
                elif status == 'cancelled':
                    self.logger.info("")
                    self.logger.warning("Job was cancelled")
                    return 1
                
                time.sleep(self.config.poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("")
                self.logger.warning(f"Monitoring interrupted. Job ID: {job_id}")
                self.logger.info(f"Resume with: karaoke-gen-remote --resume {job_id}")
                return 130
            except Exception as e:
                self.logger.warning(f"Error polling job status: {e}")
                time.sleep(self.config.poll_interval)


def check_prerequisites(logger: logging.Logger) -> bool:
    """Check that required tools are available."""
    # Check for gcloud
    try:
        subprocess.run(['gcloud', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("gcloud CLI not found. Authentication may be limited.")
    
    # Check for gsutil
    try:
        subprocess.run(['gsutil', 'version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("gsutil not found. File downloads may fail. Install with: pip install gsutil")
    
    return True


def get_auth_token(logger: logging.Logger) -> Optional[str]:
    """Get authentication token from environment or gcloud."""
    # Check environment variable first
    token = os.environ.get('KARAOKE_GEN_AUTH_TOKEN')
    if token:
        return token
    
    # Try gcloud
    try:
        result = subprocess.run(
            ['gcloud', 'auth', 'print-identity-token'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main():
    """Main entry point for the remote CLI."""
    # Set up logging - same format as gen_cli.py
    logger = logging.getLogger(__name__)
    log_handler = logging.StreamHandler()
    log_formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(module)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)
    
    # Use shared CLI parser
    parser = create_parser(prog="karaoke-gen-remote")
    args = parser.parse_args()
    
    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)
    
    # Check for KARAOKE_GEN_URL - this is REQUIRED for remote mode
    if not args.service_url:
        logger.error("KARAOKE_GEN_URL environment variable is required for karaoke-gen-remote")
        logger.error("")
        logger.error("Please set it to your cloud backend URL:")
        logger.error("  export KARAOKE_GEN_URL=https://your-backend.run.app")
        logger.error("")
        logger.error("Or pass it via command line:")
        logger.error("  karaoke-gen-remote --service-url https://your-backend.run.app ...")
        return 1
    
    # Check prerequisites
    check_prerequisites(logger)
    
    # Get auth token from environment variable
    auth_token = get_auth_token(logger)
    
    # Create config
    config = Config(
        service_url=args.service_url.rstrip('/'),
        review_ui_url=args.review_ui_url.rstrip('/'),
        poll_interval=args.poll_interval,
        output_dir=args.output_dir,
        auth_token=auth_token,
        non_interactive=getattr(args, 'yes', False),  # -y / --yes flag
        # Job tracking metadata
        environment=getattr(args, 'environment', ''),
        client_id=getattr(args, 'client_id', ''),
    )
    
    # Create client
    client = RemoteKaraokeClient(config, logger)
    monitor = JobMonitor(client, config, logger)
    
    # Handle resume mode
    if args.resume:
        logger.info("=" * 60)
        logger.info("Karaoke Generator (Remote) - Resume Job")
        logger.info("=" * 60)
        logger.info(f"Job ID: {args.resume}")
        
        try:
            # Verify job exists
            job_data = client.get_job(args.resume)
            artist = job_data.get('artist', 'Unknown')
            title = job_data.get('title', 'Unknown')
            status = job_data.get('status', 'unknown')
            
            logger.info(f"Artist: {artist}")
            logger.info(f"Title: {title}")
            logger.info(f"Current status: {status}")
            logger.info("")
            
            return monitor.monitor(args.resume)
        except ValueError as e:
            logger.error(str(e))
            return 1
        except Exception as e:
            logger.error(f"Error resuming job: {e}")
            return 1
    
    # Handle bulk delete mode
    if getattr(args, 'bulk_delete', False):
        filter_env = getattr(args, 'filter_environment', None)
        filter_client = getattr(args, 'filter_client_id', None)
        
        if not filter_env and not filter_client:
            logger.error("Bulk delete requires at least one filter: --filter-environment or --filter-client-id")
            return 1
        
        logger.info("=" * 60)
        logger.info("Karaoke Generator (Remote) - Bulk Delete Jobs")
        logger.info("=" * 60)
        if filter_env:
            logger.info(f"Environment filter: {filter_env}")
        if filter_client:
            logger.info(f"Client ID filter: {filter_client}")
        logger.info("")
        
        try:
            # First get preview
            result = client.bulk_delete_jobs(
                environment=filter_env,
                client_id=filter_client,
                confirm=False
            )
            
            jobs_to_delete = result.get('jobs_to_delete', 0)
            sample_jobs = result.get('sample_jobs', [])
            
            if jobs_to_delete == 0:
                logger.info("No jobs match the specified filters.")
                return 0
            
            logger.info(f"Found {jobs_to_delete} jobs matching filters:")
            logger.info("")
            
            # Show sample
            for job in sample_jobs:
                logger.info(f"  {job.get('job_id', 'unknown')[:10]}: {job.get('artist', 'Unknown')} - {job.get('title', 'Unknown')} ({job.get('status', 'unknown')})")
            
            if len(sample_jobs) < jobs_to_delete:
                logger.info(f"  ... and {jobs_to_delete - len(sample_jobs)} more")
            
            logger.info("")
            
            # Confirm unless -y flag is set
            if not config.non_interactive:
                confirm = input(f"Are you sure you want to delete {jobs_to_delete} jobs and all their files? [y/N]: ")
                if confirm.lower() != 'y':
                    logger.info("Bulk deletion cancelled.")
                    return 0
            
            # Execute deletion
            result = client.bulk_delete_jobs(
                environment=filter_env,
                client_id=filter_client,
                confirm=True
            )
            
            logger.info(f"✓ Deleted {result.get('jobs_deleted', 0)} jobs")
            if result.get('files_deleted'):
                logger.info(f"✓ Cleaned up files from {result.get('files_deleted', 0)} jobs")
            return 0
            
        except Exception as e:
            logger.error(f"Error bulk deleting jobs: {e}")
            return 1
    
    # Handle list jobs mode
    if getattr(args, 'list_jobs', False):
        filter_env = getattr(args, 'filter_environment', None)
        filter_client = getattr(args, 'filter_client_id', None)
        
        logger.info("=" * 60)
        logger.info("Karaoke Generator (Remote) - List Jobs")
        logger.info("=" * 60)
        if filter_env:
            logger.info(f"Environment filter: {filter_env}")
        if filter_client:
            logger.info(f"Client ID filter: {filter_client}")
        logger.info("")
        
        try:
            jobs = client.list_jobs(
                environment=filter_env,
                client_id=filter_client,
                limit=100
            )
            
            if not jobs:
                logger.info("No jobs found.")
                return 0
            
            # Print header - include environment/client if available
            logger.info(f"{'JOB ID':<12} {'STATUS':<25} {'ENV':<8} {'ARTIST':<18} {'TITLE':<25}")
            logger.info("-" * 92)
            
            # Print each job
            for job in jobs:
                # Use 'or' to handle None values (not just missing keys)
                job_id = (job.get('job_id') or 'unknown')[:10]
                status = (job.get('status') or 'unknown')[:23]
                artist = (job.get('artist') or 'Unknown')[:16]
                title = (job.get('title') or 'Unknown')[:23]
                # Get environment from request_metadata
                req_metadata = job.get('request_metadata') or {}
                env = (req_metadata.get('environment') or '-')[:6]
                logger.info(f"{job_id:<12} {status:<25} {env:<8} {artist:<18} {title:<25}")
            
            logger.info("")
            logger.info(f"Total: {len(jobs)} jobs")
            logger.info("")
            logger.info("To retry a failed job: karaoke-gen-remote --retry <JOB_ID>")
            logger.info("To delete a job: karaoke-gen-remote --delete <JOB_ID>")
            logger.info("To bulk delete: karaoke-gen-remote --bulk-delete --filter-environment=test")
            logger.info("To cancel a job: karaoke-gen-remote --cancel <JOB_ID>")
            return 0
            
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return 1
    
    # Handle cancel job mode
    if args.cancel:
        logger.info("=" * 60)
        logger.info("Karaoke Generator (Remote) - Cancel Job")
        logger.info("=" * 60)
        logger.info(f"Job ID: {args.cancel}")

        try:
            # Get job info first
            job_data = client.get_job(args.cancel)
            artist = job_data.get('artist', 'Unknown')
            title = job_data.get('title', 'Unknown')
            status = job_data.get('status', 'unknown')

            logger.info(f"Artist: {artist}")
            logger.info(f"Title: {title}")
            logger.info(f"Current status: {status}")
            logger.info("")

            # Cancel the job
            result = client.cancel_job(args.cancel)
            logger.info(f"✓ Job cancelled successfully")
            return 0

        except ValueError as e:
            logger.error(str(e))
            return 1
        except RuntimeError as e:
            logger.error(str(e))
            return 1
        except Exception as e:
            logger.error(f"Error cancelling job: {e}")
            return 1

    # Handle retry job mode
    if args.retry:
        logger.info("=" * 60)
        logger.info("Karaoke Generator (Remote) - Retry Failed Job")
        logger.info("=" * 60)
        logger.info(f"Job ID: {args.retry}")

        try:
            # Get job info first
            job_data = client.get_job(args.retry)
            artist = job_data.get('artist', 'Unknown')
            title = job_data.get('title', 'Unknown')
            status = job_data.get('status', 'unknown')
            error_message = job_data.get('error_message', 'No error message')

            logger.info(f"Artist: {artist}")
            logger.info(f"Title: {title}")
            logger.info(f"Current status: {status}")
            if status == 'failed':
                logger.info(f"Error: {error_message}")
            logger.info("")

            if status != 'failed':
                logger.error(f"Only failed jobs can be retried (current status: {status})")
                return 1

            # Retry the job
            result = client.retry_job(args.retry)
            retry_stage = result.get('retry_stage', 'unknown')
            logger.info(f"✓ Job retry started from stage: {retry_stage}")
            logger.info("")
            logger.info(f"Monitoring job progress...")
            logger.info("")

            # Monitor the retried job
            return monitor.monitor(args.retry)

        except ValueError as e:
            logger.error(str(e))
            return 1
        except RuntimeError as e:
            logger.error(str(e))
            return 1
        except Exception as e:
            logger.error(f"Error retrying job: {e}")
            return 1

    # Handle delete job mode
    if args.delete:
        logger.info("=" * 60)
        logger.info("Karaoke Generator (Remote) - Delete Job")
        logger.info("=" * 60)
        logger.info(f"Job ID: {args.delete}")
        
        try:
            # Get job info first
            job_data = client.get_job(args.delete)
            artist = job_data.get('artist', 'Unknown')
            title = job_data.get('title', 'Unknown')
            status = job_data.get('status', 'unknown')
            
            logger.info(f"Artist: {artist}")
            logger.info(f"Title: {title}")
            logger.info(f"Status: {status}")
            logger.info("")
            
            # Confirm deletion unless -y flag is set
            if not config.non_interactive:
                confirm = input("Are you sure you want to delete this job and all its files? [y/N]: ")
                if confirm.lower() != 'y':
                    logger.info("Deletion cancelled.")
                    return 0
            
            # Delete the job
            result = client.delete_job(args.delete, delete_files=True)
            logger.info(f"✓ Job deleted successfully (including all files)")
            return 0
            
        except ValueError as e:
            logger.error(str(e))
            return 1
        except Exception as e:
            logger.error(f"Error deleting job: {e}")
            return 1
    
    # Warn about unsupported features
    if args.finalise_only:
        logger.error("--finalise-only is not supported in remote mode")
        return 1
    
    if args.edit_lyrics:
        logger.error("--edit-lyrics is not yet supported in remote mode")
        return 1
    
    if args.test_email_template:
        logger.error("--test_email_template is not supported in remote mode")
        return 1
    
    # Warn about features that are not yet supported in remote mode
    ignored_features = []
    if args.prep_only:
        ignored_features.append("--prep-only")
    if args.skip_separation:
        ignored_features.append("--skip-separation")
    if args.skip_transcription:
        ignored_features.append("--skip-transcription")
    if args.lyrics_only:
        ignored_features.append("--lyrics-only")
    if args.background_video:
        ignored_features.append("--background_video")
    if getattr(args, 'auto_download', False):
        ignored_features.append("--auto-download (audio search not yet supported)")
    # These are now supported but server-side handling may be partial
    if args.organised_dir:
        ignored_features.append("--organised_dir (local-only)")
    # organised_dir_rclone_root is now supported in remote mode
    if args.public_share_dir:
        ignored_features.append("--public_share_dir (local-only)")
    if args.youtube_client_secrets_file:
        ignored_features.append("--youtube_client_secrets_file (not yet implemented)")
    if args.rclone_destination:
        ignored_features.append("--rclone_destination (local-only)")
    if args.email_template_file:
        ignored_features.append("--email_template_file (not yet implemented)")
    
    if ignored_features:
        logger.warning(f"The following options are not yet supported in remote mode and will be ignored:")
        for feature in ignored_features:
            logger.warning(f"  - {feature}")
    
    # Handle new job submission - parse input arguments same as gen_cli
    input_media, artist, title, filename_pattern = None, None, None, None
    is_url_input = False
    
    if not args.args:
        parser.print_help()
        return 1
    
    # Allow 3 forms of positional arguments:
    # 1. URL or Media File only
    # 2. Artist and Title only
    # 3. URL/File, Artist, and Title
    if args.args and (is_url(args.args[0]) or is_file(args.args[0])):
        input_media = args.args[0]
        is_url_input = is_url(args.args[0])
        if len(args.args) > 2:
            artist = args.args[1]
            title = args.args[2]
        elif len(args.args) > 1:
            artist = args.args[1]
        else:
            # For URLs, artist/title can be auto-detected
            if is_url_input:
                logger.info("URL provided without Artist and Title - will be auto-detected from video metadata")
            else:
                logger.error("Input media provided without Artist and Title")
                return 1
    elif os.path.isdir(args.args[0]):
        logger.error("Folder processing is not yet supported in remote mode")
        return 1
    elif len(args.args) > 1:
        artist = args.args[0]
        title = args.args[1]
        logger.error("Audio search (artist+title) is not yet supported in remote mode.")
        logger.error("Please provide a local audio file path or YouTube URL instead.")
        logger.error("")
        logger.error("For local flacfetch search, use karaoke-gen instead:")
        logger.error(f"  karaoke-gen \"{artist}\" \"{title}\"")
        return 1
    else:
        parser.print_help()
        return 1
    
    # Validate input
    if not input_media:
        logger.error("No input media or URL provided")
        return 1
    
    # For file input, validate file exists and artist/title are provided
    if not is_url_input:
        if not os.path.isfile(input_media):
            logger.error(f"File not found: {input_media}")
            logger.error("Please provide a valid path to an audio file (mp3, wav, flac, m4a, ogg, aac)")
            return 1
        
        if not artist or not title:
            logger.error("Artist and Title are required for file uploads")
            parser.print_help()
            return 1
    
    logger.info("=" * 60)
    logger.info("Karaoke Generator (Remote) - Job Submission")
    logger.info("=" * 60)
    if is_url_input:
        logger.info(f"URL: {input_media}")
    else:
        logger.info(f"File: {input_media}")
    if artist:
        logger.info(f"Artist: {artist}")
    if title:
        logger.info(f"Title: {title}")
    if not artist and not title and is_url_input:
        logger.info(f"Artist/Title: (will be auto-detected from URL)")
    if args.style_params_json:
        logger.info(f"Style: {args.style_params_json}")
    logger.info(f"CDG: {args.enable_cdg}, TXT: {args.enable_txt}")
    if args.brand_prefix:
        logger.info(f"Brand: {args.brand_prefix}")
    if getattr(args, 'enable_youtube_upload', False):
        logger.info(f"YouTube Upload: enabled (server-side)")
    # Native API distribution (preferred for remote CLI)
    if getattr(args, 'dropbox_path', None):
        logger.info(f"Dropbox (native): {args.dropbox_path}")
    if getattr(args, 'gdrive_folder_id', None):
        logger.info(f"Google Drive (native): {args.gdrive_folder_id}")
    # Legacy rclone distribution
    if args.organised_dir_rclone_root:
        logger.info(f"Dropbox (rclone): {args.organised_dir_rclone_root}")
    if args.discord_webhook_url:
        logger.info(f"Discord: enabled")
    # Lyrics configuration
    if getattr(args, 'lyrics_artist', None):
        logger.info(f"Lyrics Artist Override: {args.lyrics_artist}")
    if getattr(args, 'lyrics_title', None):
        logger.info(f"Lyrics Title Override: {args.lyrics_title}")
    if getattr(args, 'lyrics_file', None):
        logger.info(f"Lyrics File: {args.lyrics_file}")
    if getattr(args, 'subtitle_offset_ms', 0):
        logger.info(f"Subtitle Offset: {args.subtitle_offset_ms}ms")
    # Audio model configuration
    if getattr(args, 'clean_instrumental_model', None):
        logger.info(f"Clean Instrumental Model: {args.clean_instrumental_model}")
    if getattr(args, 'backing_vocals_models', None):
        logger.info(f"Backing Vocals Models: {args.backing_vocals_models}")
    if getattr(args, 'other_stems_models', None):
        logger.info(f"Other Stems Models: {args.other_stems_models}")
    if getattr(args, 'existing_instrumental', None):
        logger.info(f"Existing Instrumental: {args.existing_instrumental}")
    logger.info(f"Service URL: {config.service_url}")
    logger.info(f"Review UI: {config.review_ui_url}")
    if config.non_interactive:
        logger.info(f"Non-interactive mode: enabled (will auto-accept defaults)")
    logger.info("")
    
    # Read youtube description from file if provided
    youtube_description = None
    if args.youtube_description_file and os.path.isfile(args.youtube_description_file):
        try:
            with open(args.youtube_description_file, 'r') as f:
                youtube_description = f.read()
            logger.info(f"Loaded YouTube description from: {args.youtube_description_file}")
        except Exception as e:
            logger.warning(f"Failed to read YouTube description file: {e}")
    
    try:
        # Submit job - different endpoint for URL vs file
        if is_url_input:
            # URL-based job submission
            # Note: style_params_path is not supported for URL-based jobs
            # If custom styles are needed, download the audio locally first
            if args.style_params_json:
                logger.warning("Custom styles (--style_params_json) are not supported for URL-based jobs. "
                             "Download the audio locally first and use file upload for custom styles.")
            
            result = client.submit_job_from_url(
                url=input_media,
                artist=artist,
                title=title,
                enable_cdg=args.enable_cdg,
                enable_txt=args.enable_txt,
                brand_prefix=args.brand_prefix,
                discord_webhook_url=args.discord_webhook_url,
                youtube_description=youtube_description,
                organised_dir_rclone_root=args.organised_dir_rclone_root,
                enable_youtube_upload=getattr(args, 'enable_youtube_upload', False),
                # Native API distribution (preferred for remote CLI)
                dropbox_path=getattr(args, 'dropbox_path', None),
                gdrive_folder_id=getattr(args, 'gdrive_folder_id', None),
                # Lyrics configuration
                lyrics_artist=getattr(args, 'lyrics_artist', None),
                lyrics_title=getattr(args, 'lyrics_title', None),
                subtitle_offset_ms=getattr(args, 'subtitle_offset_ms', 0) or 0,
                # Audio separation model configuration
                clean_instrumental_model=getattr(args, 'clean_instrumental_model', None),
                backing_vocals_models=getattr(args, 'backing_vocals_models', None),
                other_stems_models=getattr(args, 'other_stems_models', None),
            )
        else:
            # File-based job submission
            result = client.submit_job(
                filepath=input_media,
                artist=artist,
                title=title,
                style_params_path=args.style_params_json,
                enable_cdg=args.enable_cdg,
                enable_txt=args.enable_txt,
                brand_prefix=args.brand_prefix,
                discord_webhook_url=args.discord_webhook_url,
                youtube_description=youtube_description,
                organised_dir_rclone_root=args.organised_dir_rclone_root,
                enable_youtube_upload=getattr(args, 'enable_youtube_upload', False),
                # Native API distribution (preferred for remote CLI)
                dropbox_path=getattr(args, 'dropbox_path', None),
                gdrive_folder_id=getattr(args, 'gdrive_folder_id', None),
                # Lyrics configuration
                lyrics_artist=getattr(args, 'lyrics_artist', None),
                lyrics_title=getattr(args, 'lyrics_title', None),
                lyrics_file=getattr(args, 'lyrics_file', None),
                subtitle_offset_ms=getattr(args, 'subtitle_offset_ms', 0) or 0,
                # Audio separation model configuration
                clean_instrumental_model=getattr(args, 'clean_instrumental_model', None),
                backing_vocals_models=getattr(args, 'backing_vocals_models', None),
                other_stems_models=getattr(args, 'other_stems_models', None),
                # Existing instrumental (Batch 3)
                existing_instrumental=getattr(args, 'existing_instrumental', None),
            )
        job_id = result.get('job_id')
        style_assets = result.get('style_assets_uploaded', [])
        server_version = result.get('server_version', 'unknown')
        
        logger.info(f"Job submitted successfully: {job_id}")
        logger.info(f"Server version: {server_version}")
        if style_assets:
            logger.info(f"Style assets uploaded: {', '.join(style_assets)}")
        logger.info("")
        
        # Monitor job
        return monitor.monitor(job_id)
        
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except ValueError as e:
        logger.error(str(e))
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.exception("Full error details:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
