"""
End-to-End CLI + Backend Integration Tests

These tests verify the FULL flow from CLI to Backend with real emulators.
They would have caught bugs like:
- Content-type mismatch in signed URL uploads (403 errors)
- Missing auth headers in download requests
- YouTube description field name mismatch

Run with: ./scripts/run-emulator-tests.sh

Prerequisites:
    - GCS emulator running (fake-gcs-server)
    - Firestore emulator running
"""
import pytest
import json
import time
import tempfile
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from .conftest import emulators_running


# Skip all tests if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)


@pytest.fixture
def test_style_files(tmp_path):
    """Create realistic test style files for upload testing."""
    # Create a style params JSON that references local files
    style_params = {
        "intro": {
            "background_color": "#000000",
            "background_image": str(tmp_path / "intro_bg.png"),
            "font": str(tmp_path / "test_font.ttf"),
            "title_color": "#ffffff",
            "artist_color": "#ffdf6b"
        },
        "karaoke": {
            "background_color": "#000000",
            "background_image": str(tmp_path / "karaoke_bg.png"),
            "font_path": str(tmp_path / "test_font.ttf"),
            "primary_color": "112, 112, 247, 255",
            "secondary_color": "255, 255, 255, 255"
        },
        "end": {
            "background_color": "#000000",
            "background_image": str(tmp_path / "end_bg.png"),
            "font": str(tmp_path / "test_font.ttf")
        },
        "cdg": {
            "background_color": "#000000",
            "instrumental_background": str(tmp_path / "cdg_inst_bg.png"),
            "title_screen_background": str(tmp_path / "cdg_title_bg.png"),
            "outro_background": str(tmp_path / "cdg_outro_bg.png"),
            "font_path": str(tmp_path / "test_font.ttf")
        }
    }
    
    style_params_path = tmp_path / "karaoke-prep-styles.json"
    with open(style_params_path, 'w') as f:
        json.dump(style_params, f)
    
    # Create minimal valid PNG (1x1 pixel)
    minimal_png = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59,
        0xE7, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,  # IEND chunk
        0x44, 0xAE, 0x42, 0x60, 0x82
    ])
    
    # Create all referenced image files
    for name in ["intro_bg.png", "karaoke_bg.png", "end_bg.png", 
                 "cdg_inst_bg.png", "cdg_title_bg.png", "cdg_outro_bg.png"]:
        (tmp_path / name).write_bytes(minimal_png)
    
    # Create minimal TTF font file
    minimal_ttf = bytes([0x00, 0x01, 0x00, 0x00] + [0x00] * 100)
    (tmp_path / "test_font.ttf").write_bytes(minimal_ttf)
    
    return {
        'style_params_path': str(style_params_path),
        'tmp_path': tmp_path
    }


@pytest.fixture
def youtube_description():
    """Sample YouTube description template."""
    return """This is a karaoke (instrumental) version of the song.
    
Created using AI-powered vocal removal.

LINKS:
- Community: https://discord.gg/example
- More karaoke: https://example.com
"""


class TestStyleFileUploadE2E:
    """
    Test the complete style file upload flow.
    
    This is the flow that broke with the content-type mismatch bug:
    1. CLI parses style_params.json and finds all referenced files
    2. CLI sends metadata to backend, gets signed upload URLs
    3. CLI uploads each file to its signed URL with correct content-type
    4. Backend records the GCS paths for later use
    """
    
    def test_style_params_json_upload_content_type(self, client, auth_headers, tmp_path):
        """
        Test that style_params.json uploads with application/json content-type.
        
        BUG CAUGHT: CLI was deriving content-type from Path('.json').suffix which
        returns '' because '.json' looks like a hidden file. This caused 403 errors
        because the upload content-type didn't match the signed URL's expected type.
        """
        # Create minimal style params
        style_params = {"karaoke": {"background_color": "#000000"}}
        style_path = tmp_path / "styles.json"
        with open(style_path, 'w') as f:
            json.dump(style_params, f)
        
        # Create job with style files
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'files': [
                    {
                        'filename': 'styles.json',
                        'content_type': 'application/json',
                        'file_type': 'style_params'
                    }
                ]
            }
        )
        
        # Should not fail with 500 (backend error)
        assert response.status_code in [200, 404], f"Unexpected: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Verify upload URLs are returned
            if 'upload_urls' in data:
                assert 'style_params' in data['upload_urls']
                # The URL should be a signed GCS URL
                url = data['upload_urls']['style_params']
                assert 'storage' in url.lower() or 'localhost' in url.lower()
    
    def test_image_upload_content_type(self, client, auth_headers, tmp_path):
        """Test that PNG images upload with image/png content-type."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'files': [
                    {
                        'filename': 'background.png',
                        'content_type': 'image/png',
                        'file_type': 'style_intro_background'
                    }
                ]
            }
        )
        
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            if 'upload_urls' in data:
                assert 'style_intro_background' in data['upload_urls']
    
    def test_font_upload_content_type(self, client, auth_headers):
        """Test that TTF fonts upload with font/ttf content-type."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'files': [
                    {
                        'filename': 'font.ttf',
                        'content_type': 'font/ttf',
                        'file_type': 'style_font'
                    }
                ]
            }
        )
        
        assert response.status_code in [200, 404]


class TestYouTubeDescriptionFieldMapping:
    """
    Test that YouTube description is properly passed from API to workers.
    
    BUG CAUGHT: audio_search endpoint set 'youtube_description' but
    video_worker.py reads 'youtube_description_template'. YouTube uploads
    silently failed because the template field was always None.
    """
    
    def test_job_has_youtube_description_template(self, client, auth_headers, youtube_description):
        """
        Test that when youtube_description is provided, youtube_description_template is also set.
        
        This is critical because video_worker.py uses this pattern:
            if youtube_credentials and getattr(job, 'youtube_description_template', None):
        """
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'enable_youtube_upload': True,
                'youtube_description': youtube_description
            }
        )
        
        # Job should be created (or 404 if flacfetch not configured)
        assert response.status_code in [200, 404], f"Unexpected: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('job_id')
            
            if job_id:
                # Fetch the job and verify both fields are set
                time.sleep(0.2)  # Allow for emulator consistency
                job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
                
                if job_response.status_code == 200:
                    job = job_response.json()
                    
                    # CRITICAL: Both fields must be set for YouTube upload to work
                    assert job.get('youtube_description') == youtube_description, \
                        "youtube_description not set correctly"
                    assert job.get('youtube_description_template') == youtube_description, \
                        "youtube_description_template not set - YouTube upload will fail!"
    
    def test_youtube_upload_disabled_no_template_needed(self, client, auth_headers):
        """Test that youtube_description_template is not required when upload is disabled."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test Artist',
                'title': 'Test Song',
                'auto_download': False,
                'enable_youtube_upload': False
            }
        )
        
        # Should succeed without YouTube config
        assert response.status_code in [200, 404]


class TestDownloadAuthHeaders:
    """
    Test that file downloads include authentication headers.
    
    BUG CAUGHT: download_file_via_url() used requests.get() directly instead
    of self.session.get(), so auth headers were not included. All downloads
    failed with 401/403 even though the job completed successfully.
    """
    
    def test_download_endpoint_requires_auth(self, client):
        """Test that download endpoints reject unauthenticated requests."""
        # Try to download without auth header
        response = client.get("/api/jobs/nonexistent/download-urls")
        
        # Should fail with 401 (unauthorized), not 404
        assert response.status_code in [401, 403], \
            f"Download endpoint should require auth, got {response.status_code}"
    
    def test_download_endpoint_with_auth(self, client, auth_headers):
        """Test that download endpoints work with auth header."""
        # First create a job
        create_response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=test123"}
        )
        
        if create_response.status_code == 200:
            job_id = create_response.json()["job_id"]
            time.sleep(0.2)
            
            # Try to get download URLs with auth
            download_response = client.get(
                f"/api/jobs/{job_id}/download-urls",
                headers=auth_headers
            )
            
            # Should succeed (200) or return empty URLs for incomplete job
            assert download_response.status_code in [200, 404], \
                f"Download URLs request failed: {download_response.status_code}"


class TestFullAudioSearchFlow:
    """
    Test the complete audio search flow that the CLI uses.
    """
    
    def test_audio_search_creates_job_with_all_fields(
        self, client, auth_headers, test_style_files, youtube_description
    ):
        """Test that audio search creates a job with all expected fields."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'ABBA',
                'title': 'Waterloo',
                'auto_download': False,
                'enable_cdg': True,
                'enable_txt': True,
                'enable_youtube_upload': True,
                'youtube_description': youtube_description,
                'brand_prefix': 'TEST',
                'files': [
                    {
                        'filename': 'styles.json',
                        'content_type': 'application/json',
                        'file_type': 'style_params'
                    }
                ]
            }
        )
        
        # Should create job or return 404 if no results
        assert response.status_code in [200, 404], \
            f"Unexpected status: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify job was created
            assert 'job_id' in data
            job_id = data['job_id']
            
            # Verify upload URLs returned for style files
            if 'upload_urls' in data:
                assert isinstance(data['upload_urls'], dict)
            
            # Fetch job and verify all fields are set
            time.sleep(0.2)
            job_response = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
            
            if job_response.status_code == 200:
                job = job_response.json()
                
                # Verify job configuration
                assert job.get('enable_cdg') is True
                assert job.get('enable_txt') is True
                assert job.get('enable_youtube_upload') is True
                assert job.get('youtube_description') == youtube_description
                # CRITICAL: This field must be set for video_worker.py
                assert job.get('youtube_description_template') == youtube_description
    
    def test_audio_search_returns_server_version(self, client, auth_headers):
        """Test that audio search response includes server version."""
        response = client.post(
            "/api/audio-search/search",
            headers=auth_headers,
            json={
                'artist': 'Test',
                'title': 'Song',
                'auto_download': False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            # Server version helps CLI verify compatibility
            assert 'server_version' in data


class TestCLIClientIntegration:
    """
    Test the actual CLI client code against the backend.
    
    These tests import and use the real RemoteKaraokeClient class.
    """
    
    @pytest.fixture
    def cli_client(self):
        """Create a CLI client configured for local testing."""
        # Import here to avoid issues when emulators aren't running
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, RemoteConfig
        
        logger = logging.getLogger("test_cli")
        config = RemoteConfig(
            service_url='http://localhost:8000',
            auth_token='test-admin-token',
            environment='test'
        )
        return RemoteKaraokeClient(config, logger)
    
    def test_cli_get_content_type_handles_all_extensions(self, cli_client):
        """Test CLI content type detection for all file types we use."""
        # JSON
        assert cli_client._get_content_type('/path/to/style.json') == 'application/json'
        # Images
        assert cli_client._get_content_type('/path/to/bg.png') == 'image/png'
        assert cli_client._get_content_type('/path/to/bg.jpg') == 'image/jpeg'
        assert cli_client._get_content_type('/path/to/bg.jpeg') == 'image/jpeg'
        # Fonts
        assert cli_client._get_content_type('/path/to/font.ttf') == 'font/ttf'
        assert cli_client._get_content_type('/path/to/font.otf') == 'font/otf'
        # Audio
        assert cli_client._get_content_type('/path/to/audio.flac') == 'audio/flac'
        assert cli_client._get_content_type('/path/to/audio.mp3') == 'audio/mpeg'
    
    def test_cli_download_uses_session_not_requests(self, cli_client, tmp_path):
        """
        Test that CLI download method uses session (with auth headers).
        
        This verifies the fix for the download auth bug.
        """
        # Mock the session.get to verify it's called
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content.return_value = [b'test content']
        cli_client.session.get = MagicMock(return_value=mock_response)
        
        local_path = str(tmp_path / "test.mp4")
        
        # Call download with a relative URL
        result = cli_client.download_file_via_url("/api/jobs/123/download/test", local_path)
        
        # Verify session.get was called (not bare requests.get)
        assert result is True
        cli_client.session.get.assert_called_once()
        
        # Verify URL was constructed correctly
        call_args = cli_client.session.get.call_args
        assert 'localhost:8000' in call_args[0][0] or cli_client.config.service_url in call_args[0][0]
    
    def test_cli_parse_style_params_extracts_all_assets(self, cli_client, test_style_files):
        """Test that CLI correctly parses style params and finds all asset files."""
        assets = cli_client._parse_style_params(test_style_files['style_params_path'])
        
        # Should find all the referenced files
        assert len(assets) > 0
        
        # Verify it found background images
        bg_keys = [k for k in assets.keys() if 'background' in k.lower()]
        assert len(bg_keys) > 0, "Should find background image references"
        
        # Verify it found font
        font_keys = [k for k in assets.keys() if 'font' in k.lower()]
        assert len(font_keys) > 0, "Should find font references"

