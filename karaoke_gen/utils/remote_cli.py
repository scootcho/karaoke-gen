#!/usr/bin/env python
"""
Remote CLI for karaoke-gen - Submit jobs to a cloud-hosted backend.

This CLI allows users to use karaoke-gen with cloud processing instead of local.
Set KARAOKE_GEN_URL environment variable to your cloud backend URL.

Usage:
    karaoke-gen-remote <filepath> <artist> <title>
    karaoke-gen-remote --resume <job_id>
"""
import argparse
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
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional

import requests


# ANSI color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color


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


def get_color_for_status(status: str) -> str:
    """Get color code for a job status."""
    status_colors = {
        # Yellow for pending/initial states
        "pending": Colors.YELLOW,
        "downloading": Colors.YELLOW,
        # Blue for processing states
        "separating_stage1": Colors.BLUE,
        "separating_stage2": Colors.BLUE,
        "transcribing": Colors.BLUE,
        "correcting": Colors.BLUE,
        "generating_screens": Colors.BLUE,
        "applying_padding": Colors.BLUE,
        "rendering_video": Colors.BLUE,
        "encoding": Colors.BLUE,
        "packaging": Colors.BLUE,
        "generating_video": Colors.BLUE,
        # Cyan for waiting states
        "awaiting_review": Colors.CYAN,
        "in_review": Colors.CYAN,
        "awaiting_instrumental_selection": Colors.CYAN,
        # Green for completion
        "complete": Colors.GREEN,
        "audio_complete": Colors.GREEN,
        "lyrics_complete": Colors.GREEN,
        "review_complete": Colors.GREEN,
        "instrumental_selected": Colors.GREEN,
        # Red for errors
        "failed": Colors.RED,
        "error": Colors.RED,
        "cancelled": Colors.RED,
    }
    return status_colors.get(status, Colors.NC)


def print_status(status: str) -> str:
    """Format status with color."""
    color = get_color_for_status(status)
    return f"{color}{status}{Colors.NC}"


def print_progress_bar(progress: int, width: int = 40) -> str:
    """Create a progress bar string."""
    filled = int(progress * width / 100)
    empty = width - filled
    bar = '█' * filled + '░' * empty
    return f"[{bar}] {progress:3d}%"


def print_header(title: str, char: str = "═") -> None:
    """Print a styled header."""
    line = char * 63
    print(f"{Colors.YELLOW}{line}{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {title}{Colors.NC}")
    print(f"{Colors.YELLOW}{line}{Colors.NC}")
    print()


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}Error: {message}{Colors.NC}", file=sys.stderr)


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.NC}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Colors.CYAN}{message}{Colors.NC}")


class RemoteKaraokeClient:
    """Client for interacting with the karaoke-gen cloud backend."""
    
    ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'}
    
    def __init__(self, config: Config):
        self.config = config
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
    
    def submit_job(self, filepath: str, artist: str, title: str) -> Dict[str, Any]:
        """Submit a new karaoke generation job."""
        file_path = Path(filepath)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        ext = file_path.suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
        
        print(f"{Colors.BOLD}Uploading file...{Colors.NC}")
        
        with open(filepath, 'rb') as f:
            files = {'file': (file_path.name, f)}
            data = {'artist': artist, 'title': title}
            response = self._request('POST', '/api/jobs/upload', files=files, data=data)
        
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
    """Monitor job progress with interactive elements."""
    
    def __init__(self, client: RemoteKaraokeClient, config: Config):
        self.client = client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._review_opened = False
        self._instrumental_prompted = False
    
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
            print(f"Please open: {url}")
    
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
        
        print_info("Opening lyrics review UI in browser...")
        print(f"URL: {Colors.BOLD}{url}{Colors.NC}")
        print()
        
        self.open_browser(url)
    
    def handle_review(self, job_id: str) -> None:
        """Handle the lyrics review interaction."""
        print_header("LYRICS REVIEW NEEDED")
        
        print("The transcription is ready for review.")
        print("Please review and correct the lyrics in the browser.")
        print()
        
        self.open_review_ui(job_id)
        
        print(f"{Colors.YELLOW}Waiting for review to be completed in the browser...{Colors.NC}")
        print(f"{Colors.CYAN}(Polling for status change every {self.config.poll_interval}s){Colors.NC}")
        print()
        
        # Poll until status changes from review states
        while True:
            try:
                job_data = self.client.get_job(job_id)
                current_status = job_data.get('status', 'unknown')
                
                if current_status in ['awaiting_review', 'in_review']:
                    # Still in review, keep waiting
                    print(f"\r\033[K  Status: {current_status} - still waiting for review completion...", end='', flush=True)
                    time.sleep(self.config.poll_interval)
                else:
                    # Status changed, review is complete
                    print(f"\r\033[K")
                    print_success(f"Review completed (status: {current_status})")
                    print()
                    return
            except Exception as e:
                self.logger.warning(f"Error checking review status: {e}")
                time.sleep(self.config.poll_interval)
    
    def handle_instrumental_selection(self, job_id: str) -> None:
        """Handle instrumental selection interaction."""
        print_header("INSTRUMENTAL SELECTION NEEDED")
        
        print("Choose which instrumental track to use for the final video:")
        print()
        print(f"  {Colors.BOLD}1){Colors.NC} Clean Instrumental (no backing vocals)")
        print("     Best for songs where you want ONLY the lead vocal removed")
        print()
        print(f"  {Colors.BOLD}2){Colors.NC} Instrumental with Backing Vocals")
        print("     Best for songs where backing vocals add to the karaoke experience")
        print()
        
        # Try to get audio URLs for preview hint
        try:
            options = self.client.get_instrumental_options(job_id)
            if options.get('options'):
                print(f"{Colors.CYAN}Tip: You can preview the audio files:{Colors.NC}")
                for opt in options['options']:
                    label = opt.get('label', opt.get('id', ''))
                    audio_url = opt.get('audio_url', '')
                    if audio_url:
                        print(f"  {label}: {audio_url}")
                print()
        except Exception:
            pass
        
        selection = ""
        while not selection:
            try:
                choice = input("Enter your choice (1 or 2): ").strip()
                if choice == '1':
                    selection = 'clean'
                elif choice == '2':
                    selection = 'with_backing'
                else:
                    print_error("Invalid choice. Please enter 1 or 2.")
            except KeyboardInterrupt:
                print()
                raise
        
        print()
        print(f"Submitting selection: {Colors.BOLD}{selection}{Colors.NC}...")
        
        try:
            result = self.client.select_instrumental(job_id, selection)
            if result.get('status') == 'success':
                print_success(f"Selection submitted: {selection}")
            else:
                print_error(f"Error submitting selection: {result}")
        except Exception as e:
            print_error(f"Error submitting selection: {e}")
        
        print()
    
    def download_outputs(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """Download all output files for a completed job."""
        artist = job_data.get('artist', 'Unknown').replace(' ', '_')
        title = job_data.get('title', 'Unknown').replace(' ', '_')
        
        output_dir = Path(self.config.output_dir) / f"{artist}-{title}-{job_id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"{Colors.BOLD}Downloading output files to: {Colors.CYAN}{output_dir}{Colors.NC}")
        print()
        
        file_urls = job_data.get('file_urls', {})
        
        # Download final videos (most important)
        finals = file_urls.get('finals', {})
        if finals:
            print(f"  {Colors.BOLD}Final Videos:{Colors.NC}")
            for key, blob_path in finals.items():
                if blob_path:
                    filename = Path(blob_path).name
                    local_path = output_dir / filename
                    print(f"    Downloading {filename}... ", end='', flush=True)
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
                        print(f"{Colors.GREEN}✓{Colors.NC}")
                    else:
                        print(f"{Colors.RED}✗{Colors.NC}")
            print()
        
        # Download lyrics files
        lyrics = file_urls.get('lyrics', {})
        if lyrics:
            lyrics_dir = output_dir / 'lyrics'
            lyrics_dir.mkdir(exist_ok=True)
            print(f"  {Colors.BOLD}Lyrics:{Colors.NC}")
            for key in ['ass', 'lrc', 'corrected_txt']:
                blob_path = lyrics.get(key)
                if blob_path:
                    filename = Path(blob_path).name
                    local_path = lyrics_dir / filename
                    print(f"    Downloading {filename}... ", end='', flush=True)
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
                        print(f"{Colors.GREEN}✓{Colors.NC}")
                    else:
                        print(f"{Colors.RED}✗{Colors.NC}")
            print()
        
        # Download stems (optional - can be large)
        stems = file_urls.get('stems', {})
        if stems:
            stems_dir = output_dir / 'stems'
            stems_dir.mkdir(exist_ok=True)
            print(f"  {Colors.BOLD}Audio Stems:{Colors.NC}")
            for key, blob_path in stems.items():
                if blob_path:
                    filename = Path(blob_path).name
                    local_path = stems_dir / filename
                    print(f"    Downloading {filename}... ", end='', flush=True)
                    if self.client.download_file_via_gsutil(blob_path, str(local_path)):
                        print(f"{Colors.GREEN}✓{Colors.NC}")
                    else:
                        print(f"{Colors.RED}✗{Colors.NC}")
            print()
        
        print_success(f"All files downloaded to: {Colors.BOLD}{output_dir}{Colors.NC}")
        print()
        
        # List downloaded files
        print(f"{Colors.BOLD}Downloaded files:{Colors.NC}")
        for file_path in output_dir.rglob('*'):
            if file_path.is_file():
                size = file_path.stat().st_size
                if size > 1024 * 1024:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                print(f"  {file_path} ({size_str})")
        print()
    
    def show_completion_info(self, job_id: str, job_data: Dict[str, Any]) -> None:
        """Display job completion info and download files."""
        print(f"{Colors.GREEN}{'═' * 63}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.GREEN}  JOB COMPLETE!{Colors.NC}")
        print(f"{Colors.GREEN}{'═' * 63}{Colors.NC}")
        print()
        
        self.download_outputs(job_id, job_data)
    
    def show_error_info(self, job_data: Dict[str, Any]) -> None:
        """Display error info for failed jobs."""
        print(f"{Colors.RED}{'═' * 63}{Colors.NC}")
        print(f"{Colors.BOLD}{Colors.RED}  JOB FAILED{Colors.NC}")
        print(f"{Colors.RED}{'═' * 63}{Colors.NC}")
        print()
        
        error_message = job_data.get('error_message', 'Unknown error')
        print(f"{Colors.RED}Error: {error_message}{Colors.NC}")
        
        error_details = job_data.get('error_details')
        if error_details:
            print()
            print(f"{Colors.BOLD}Details:{Colors.NC}")
            if isinstance(error_details, dict):
                print(json.dumps(error_details, indent=2))
            else:
                print(error_details)
        print()
    
    def monitor(self, job_id: str) -> int:
        """Monitor job progress until completion."""
        last_status = ""
        last_message = ""
        
        print(f"{Colors.BOLD}Monitoring job: {job_id}{Colors.NC}")
        print(f"Service: {self.config.service_url}")
        print()
        
        while True:
            try:
                job_data = self.client.get_job(job_id)
                
                status = job_data.get('status', 'unknown')
                progress = job_data.get('progress', 0)
                timeline = job_data.get('timeline', [])
                message = timeline[-1].get('message', '') if timeline else ''
                artist = job_data.get('artist', '')
                title = job_data.get('title', '')
                
                # Update display if something changed
                if status != last_status or message != last_message:
                    # Clear line and print status
                    print(f"\r\033[K{print_status(status)} | {print_progress_bar(progress)} | {message}")
                    last_status = status
                    last_message = message
                
                # Handle human interaction points
                if status in ['awaiting_review', 'in_review']:
                    if not self._review_opened:
                        print()
                        self.handle_review(job_id)
                        self._review_opened = True
                        # Refresh auth token after potentially long review
                        self.client.refresh_auth()
                
                elif status == 'awaiting_instrumental_selection':
                    if not self._instrumental_prompted:
                        print()
                        self.handle_instrumental_selection(job_id)
                        self._instrumental_prompted = True
                
                elif status == 'complete':
                    print()
                    self.show_completion_info(job_id, job_data)
                    return 0
                
                elif status in ['failed', 'error']:
                    print()
                    self.show_error_info(job_data)
                    return 1
                
                elif status == 'cancelled':
                    print()
                    print(f"{Colors.YELLOW}Job was cancelled{Colors.NC}")
                    return 1
                
                time.sleep(self.config.poll_interval)
                
            except KeyboardInterrupt:
                print()
                print(f"{Colors.YELLOW}Monitoring interrupted. Job ID: {job_id}{Colors.NC}")
                print(f"Resume with: karaoke-gen-remote --resume {job_id}")
                return 130
            except Exception as e:
                self.logger.warning(f"Error polling job status: {e}")
                time.sleep(self.config.poll_interval)


def check_prerequisites() -> bool:
    """Check that required tools are available."""
    # Check for gcloud (optional but recommended)
    try:
        subprocess.run(['gcloud', '--version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{Colors.YELLOW}Warning: gcloud CLI not found. Authentication may be limited.{Colors.NC}")
    
    # Check for gsutil (required for downloads)
    try:
        subprocess.run(['gsutil', 'version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{Colors.YELLOW}Warning: gsutil not found. File downloads may fail.{Colors.NC}")
        print("Install with: pip install gsutil")
    
    return True


def get_auth_token() -> Optional[str]:
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
    logger = logging.getLogger(__name__)
    log_handler = logging.StreamHandler()
    log_formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(module)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)
    
    # Get version
    try:
        package_version = metadata.version("karaoke-gen")
    except metadata.PackageNotFoundError:
        package_version = "unknown"
    
    parser = argparse.ArgumentParser(
        description="Submit karaoke generation jobs to a cloud-hosted backend.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  karaoke-gen-remote ./song.mp3 "ABBA" "Waterloo"
  karaoke-gen-remote --resume abc12345

Environment variables:
  KARAOKE_GEN_URL       Backend URL (required, or set via --service-url)
  REVIEW_UI_URL         Lyrics review UI URL (default: http://localhost:5173)
  POLL_INTERVAL         Seconds between status polls (default: 5)
  KARAOKE_GEN_BUCKET    GCS bucket name (default: karaoke-gen-storage-nomadkaraoke)
  KARAOKE_GEN_AUTH_TOKEN  Override auth token (optional, uses gcloud by default)
        """
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {package_version}"
    )
    
    parser.add_argument(
        "args",
        nargs="*",
        help="<filepath> <artist> <title> for new jobs"
    )
    
    parser.add_argument(
        "--resume", "-r",
        metavar="JOB_ID",
        help="Resume monitoring an existing job"
    )
    
    parser.add_argument(
        "--service-url",
        default=os.environ.get('KARAOKE_GEN_URL', 'http://localhost:8000'),
        help="Backend service URL (or set KARAOKE_GEN_URL env var)"
    )
    
    parser.add_argument(
        "--review-ui-url",
        default=os.environ.get('REVIEW_UI_URL', 'http://localhost:5173'),
        help="Lyrics review UI URL (default: http://localhost:5173)"
    )
    
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=int(os.environ.get('POLL_INTERVAL', '5')),
        help="Seconds between status polls (default: 5)"
    )
    
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to save output files (default: output)"
    )
    
    parser.add_argument(
        "--log-level",
        default="warning",
        choices=['debug', 'info', 'warning', 'error'],
        help="Logging level (default: warning)"
    )
    
    args = parser.parse_args()
    
    # Set log level
    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)
    
    # Check prerequisites
    check_prerequisites()
    
    # Get auth token
    print("Authenticating...")
    auth_token = get_auth_token()
    if auth_token:
        print_success("Authenticated")
    else:
        print(f"{Colors.YELLOW}Warning: No authentication token found. Requests may fail.{Colors.NC}")
        print("Run: gcloud auth login")
    print()
    
    # Create config
    config = Config(
        service_url=args.service_url.rstrip('/'),
        review_ui_url=args.review_ui_url.rstrip('/'),
        poll_interval=args.poll_interval,
        output_dir=args.output_dir,
        auth_token=auth_token
    )
    
    # Create client
    client = RemoteKaraokeClient(config)
    monitor = JobMonitor(client, config)
    
    # Handle resume mode
    if args.resume:
        print_header("Karaoke Generator - Resume Job")
        print(f"  Job ID: {Colors.CYAN}{args.resume}{Colors.NC}")
        print()
        
        try:
            # Verify job exists
            job_data = client.get_job(args.resume)
            artist = job_data.get('artist', 'Unknown')
            title = job_data.get('title', 'Unknown')
            status = job_data.get('status', 'unknown')
            
            print(f"  Artist: {Colors.CYAN}{artist}{Colors.NC}")
            print(f"  Title:  {Colors.CYAN}{title}{Colors.NC}")
            print(f"  Status: {print_status(status)}")
            print()
            
            return monitor.monitor(args.resume)
        except ValueError as e:
            print_error(str(e))
            return 1
        except Exception as e:
            print_error(f"Error resuming job: {e}")
            return 1
    
    # Handle new job submission
    if len(args.args) < 3:
        parser.print_help()
        return 1
    
    filepath = args.args[0]
    artist = args.args[1]
    title = args.args[2]
    
    # Validate file exists
    if not os.path.isfile(filepath):
        print_error(f"File not found: {filepath}")
        return 1
    
    print_header("Karaoke Generator - Job Submission")
    print(f"  File:   {Colors.CYAN}{filepath}{Colors.NC}")
    print(f"  Artist: {Colors.CYAN}{artist}{Colors.NC}")
    print(f"  Title:  {Colors.CYAN}{title}{Colors.NC}")
    print()
    
    try:
        # Submit job
        result = client.submit_job(filepath, artist, title)
        job_id = result.get('job_id')
        
        print_success(f"Job submitted: {Colors.BOLD}{job_id}{Colors.NC}")
        print()
        
        # Monitor job
        return monitor.monitor(job_id)
        
    except FileNotFoundError as e:
        print_error(str(e))
        return 1
    except ValueError as e:
        print_error(str(e))
        return 1
    except Exception as e:
        print_error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
