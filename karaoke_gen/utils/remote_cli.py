#!/usr/bin/env python
"""
Remote CLI for karaoke-gen - Submit jobs to a cloud-hosted backend.

This CLI provides the same interface as karaoke-gen but processes jobs on a cloud backend.
Set KARAOKE_GEN_URL environment variable to your cloud backend URL.

Usage:
    karaoke-gen-remote <filepath> <artist> <title>
    karaoke-gen-remote --resume <job_id>
"""
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
        """Set up authentication headers."""
        if self.config.auth_token:
            self.session.headers['Authorization'] = f'Bearer {self.config.auth_token}'
    
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
    ) -> Dict[str, Any]:
        """
        Submit a new karaoke generation job with optional style configuration.
        
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
        
        self.logger.info(f"Uploading audio file: {filepath}")
        
        # Prepare files dict for multipart upload
        files_to_upload = {}
        files_to_close = []
        
        try:
            # Main audio file
            audio_file = open(filepath, 'rb')
            files_to_close.append(audio_file)
            files_to_upload['file'] = (file_path.name, audio_file)
            
            # Parse style params and find referenced files
            style_assets = {}
            if style_params_path and os.path.isfile(style_params_path):
                self.logger.info(f"Parsing style configuration: {style_params_path}")
                style_assets = self._parse_style_params(style_params_path)
                
                # Upload style_params.json
                style_file = open(style_params_path, 'rb')
                files_to_close.append(style_file)
                files_to_upload['style_params'] = (Path(style_params_path).name, style_file, 'application/json')
                self.logger.info(f"  Will upload style_params.json")
            
            # Upload each style asset file
            for asset_key, asset_path in style_assets.items():
                if os.path.isfile(asset_path):
                    asset_file = open(asset_path, 'rb')
                    files_to_close.append(asset_file)
                    # Determine content type
                    ext = Path(asset_path).suffix.lower()
                    if ext in self.ALLOWED_IMAGE_EXTENSIONS:
                        content_type = f'image/{ext[1:]}'
                    elif ext in self.ALLOWED_FONT_EXTENSIONS:
                        content_type = 'font/ttf'
                    else:
                        content_type = 'application/octet-stream'
                    files_to_upload[asset_key] = (Path(asset_path).name, asset_file, content_type)
                    self.logger.info(f"  Will upload {asset_key}: {asset_path}")
            
            # Prepare form data
            data = {
                'artist': artist,
                'title': title,
                'enable_cdg': str(enable_cdg).lower(),
                'enable_txt': str(enable_txt).lower(),
            }
            
            if brand_prefix:
                data['brand_prefix'] = brand_prefix
            if discord_webhook_url:
                data['discord_webhook_url'] = discord_webhook_url
            if youtube_description:
                data['youtube_description'] = youtube_description
            
            self.logger.info(f"Submitting job to {self.config.service_url}/api/jobs/upload")
            
            response = self._request('POST', '/api/jobs/upload', files=files_to_upload, data=data)
            
        finally:
            # Close all opened files
            for f in files_to_close:
                try:
                    f.close()
                except:
                    pass
        
        if response.status_code != 200:
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            raise RuntimeError(f"Error submitting job: {error_detail}")
        
        result = response.json()
        if result.get('status') != 'success':
            raise RuntimeError(f"Error submitting job: {result}")
        
        return result
    
    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job status and details."""
        response = self._request('GET', f'/api/jobs/{job_id}')
        if response.status_code == 404:
            raise ValueError(f"Job not found: {job_id}")
        if response.status_code != 200:
            raise RuntimeError(f"Error getting job: {response.text}")
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
    
    def download_file_via_gsutil(self, gcs_path: str, local_path: str) -> bool:
        """Download file from GCS using gsutil."""
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


class JobMonitor:
    """Monitor job progress with verbose logging."""
    
    def __init__(self, client: RemoteKaraokeClient, config: Config, logger: logging.Logger):
        self.client = client
        self.config = config
        self.logger = logger
        self._review_opened = False
        self._instrumental_prompted = False
        self._last_timeline_index = 0
    
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
        """Download all output files for a completed job."""
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
        
        file_urls = job_data.get('file_urls', {})
        
        # Download final videos
        finals = file_urls.get('finals', {})
        if finals:
            self.logger.info("Downloading final videos...")
            for key, blob_path in finals.items():
                if blob_path:
                    # Use descriptive filename
                    ext = Path(blob_path).suffix
                    if 'lossless_4k_mp4' in key:
                        filename = f"{artist} - {title} (Final Karaoke Lossless 4k).mp4"
                    elif 'lossless_4k_mkv' in key:
                        filename = f"{artist} - {title} (Final Karaoke Lossless 4k).mkv"
                    elif 'lossy_4k' in key:
                        filename = f"{artist} - {title} (Final Karaoke Lossy 4k).mp4"
                    elif 'lossy_720p' in key:
                        filename = f"{artist} - {title} (Final Karaoke Lossy 720p).mp4"
                    else:
                        filename = Path(blob_path).name
                    
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
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
                        filename = f"{artist} - {title} (Final Karaoke CDG).zip"
                    elif 'txt' in key.lower():
                        filename = f"{artist} - {title} (Final Karaoke TXT).zip"
                    else:
                        filename = Path(blob_path).name
                    
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
                        self.logger.info(f"    OK: {local_path}")
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
                    filename = f"{artist} - {title} (Karaoke){ext}"
                    local_path = output_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
                        self.logger.info(f"    OK: {local_path}")
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
        
        # Download stems (optional - in subfolder)
        stems = file_urls.get('stems', {})
        if stems:
            stems_dir = output_dir / 'stems'
            stems_dir.mkdir(exist_ok=True)
            self.logger.info("Downloading audio stems...")
            for key, blob_path in stems.items():
                if blob_path:
                    filename = Path(blob_path).name
                    local_path = stems_dir / filename
                    self.logger.info(f"  Downloading {filename}...")
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
                        self.logger.info(f"    OK: {local_path}")
                    else:
                        self.logger.warning(f"    FAILED: {filename}")
        
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
    
    def monitor(self, job_id: str) -> int:
        """Monitor job progress until completion."""
        last_status = ""
        
        self.logger.info(f"Monitoring job: {job_id}")
        self.logger.info(f"Service URL: {self.config.service_url}")
        self.logger.info("")
        
        while True:
            try:
                job_data = self.client.get_job(job_id)
                
                status = job_data.get('status', 'unknown')
                artist = job_data.get('artist', '')
                title = job_data.get('title', '')
                
                # Log timeline updates (shows worker progress)
                self.log_timeline_updates(job_data)
                
                # Log status changes
                if status != last_status:
                    self.logger.info(f"Status changed: {last_status} -> {status}")
                    last_status = status
                
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
    
    # Get auth token
    logger.info("Authenticating with GCP...")
    auth_token = get_auth_token(logger)
    if auth_token:
        logger.info("Authenticated successfully")
    else:
        logger.warning("No authentication token found. Requests may fail.")
        logger.warning("Run: gcloud auth login")
    
    # Create config
    config = Config(
        service_url=args.service_url.rstrip('/'),
        review_ui_url=args.review_ui_url.rstrip('/'),
        poll_interval=args.poll_interval,
        output_dir=args.output_dir,
        auth_token=auth_token
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
    if args.existing_instrumental:
        ignored_features.append("--existing_instrumental")
    if args.background_video:
        ignored_features.append("--background_video")
    if getattr(args, 'auto_download', False):
        ignored_features.append("--auto-download (audio search not yet supported)")
    # These are now supported but server-side handling may be partial
    if args.organised_dir:
        ignored_features.append("--organised_dir (local-only)")
    if args.organised_dir_rclone_root:
        ignored_features.append("--organised_dir_rclone_root (local-only)")
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
    
    if not args.args:
        parser.print_help()
        return 1
    
    # Allow 3 forms of positional arguments:
    # 1. URL or Media File only
    # 2. Artist and Title only
    # 3. URL, Artist, and Title
    if args.args and (is_url(args.args[0]) or is_file(args.args[0])):
        input_media = args.args[0]
        if len(args.args) > 2:
            artist = args.args[1]
            title = args.args[2]
        elif len(args.args) > 1:
            artist = args.args[1]
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
        logger.error("Please provide a local audio file path instead.")
        logger.error("")
        logger.error("For local flacfetch search, use karaoke-gen instead:")
        logger.error(f"  karaoke-gen \"{artist}\" \"{title}\"")
        return 1
    else:
        parser.print_help()
        return 1
    
    # For now, remote mode only supports file uploads
    if not input_media or not os.path.isfile(input_media):
        logger.error("Remote mode currently only supports local file uploads")
        logger.error("Please provide a path to an audio file (mp3, wav, flac, m4a, ogg, aac)")
        return 1
    
    # Validate artist and title are provided
    if not artist or not title:
        logger.error("Artist and Title are required")
        parser.print_help()
        return 1
    
    logger.info("=" * 60)
    logger.info("Karaoke Generator (Remote) - Job Submission")
    logger.info("=" * 60)
    logger.info(f"File: {input_media}")
    logger.info(f"Artist: {artist}")
    logger.info(f"Title: {title}")
    if args.style_params_json:
        logger.info(f"Style: {args.style_params_json}")
    logger.info(f"CDG: {args.enable_cdg}, TXT: {args.enable_txt}")
    if args.brand_prefix:
        logger.info(f"Brand: {args.brand_prefix}")
    if args.discord_webhook_url:
        logger.info(f"Discord: enabled")
    logger.info(f"Service URL: {config.service_url}")
    logger.info(f"Review UI: {config.review_ui_url}")
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
        # Submit job with all options
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
        )
        job_id = result.get('job_id')
        style_assets = result.get('style_assets_uploaded', [])
        
        logger.info(f"Job submitted successfully: {job_id}")
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
