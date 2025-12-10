"""
Tests for remote_cli.py - the cloud-hosted karaoke generation CLI.

These tests mock network calls and subprocess calls to test the CLI logic
without requiring actual network or GCP connectivity.
"""
import argparse
import json
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from karaoke_gen.utils import remote_cli
from karaoke_gen.utils.remote_cli import (
    Config,
    JobStatus,
    RemoteKaraokeClient,
    JobMonitor,
    check_prerequisites,
    get_auth_token,
    main,
)


# Sample style params JSON for testing
SAMPLE_STYLE_PARAMS = {
    "intro": {
        "background_image": "/path/to/intro_bg.png",
        "font": "/path/to/font.ttf"
    },
    "karaoke": {
        "background_image": "/path/to/karaoke_bg.jpg",
        "font_path": "/path/to/font.ttf"
    },
    "end": {
        "background_image": "/path/to/end_bg.png",
        "font": "/path/to/font.ttf"
    },
    "cdg": {
        "font_path": "/path/to/font.ttf",
        "title_screen_background": "/path/to/cdg_title.png"
    }
}


class TestJobStatus:
    """Tests for the JobStatus enum."""
    
    def test_job_status_values(self):
        """Test that all expected status values exist."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.DOWNLOADING == "downloading"
        assert JobStatus.SEPARATING_STAGE1 == "separating_stage1"
        assert JobStatus.SEPARATING_STAGE2 == "separating_stage2"
        assert JobStatus.AUDIO_COMPLETE == "audio_complete"
        assert JobStatus.TRANSCRIBING == "transcribing"
        assert JobStatus.CORRECTING == "correcting"
        assert JobStatus.LYRICS_COMPLETE == "lyrics_complete"
        assert JobStatus.GENERATING_SCREENS == "generating_screens"
        assert JobStatus.APPLYING_PADDING == "applying_padding"
        assert JobStatus.AWAITING_REVIEW == "awaiting_review"
        assert JobStatus.IN_REVIEW == "in_review"
        assert JobStatus.REVIEW_COMPLETE == "review_complete"
        assert JobStatus.RENDERING_VIDEO == "rendering_video"
        assert JobStatus.AWAITING_INSTRUMENTAL_SELECTION == "awaiting_instrumental_selection"
        assert JobStatus.INSTRUMENTAL_SELECTED == "instrumental_selected"
        assert JobStatus.GENERATING_VIDEO == "generating_video"
        assert JobStatus.ENCODING == "encoding"
        assert JobStatus.PACKAGING == "packaging"
        assert JobStatus.UPLOADING == "uploading"
        assert JobStatus.NOTIFYING == "notifying"
        assert JobStatus.COMPLETE == "complete"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"
        assert JobStatus.ERROR == "error"
    
    def test_job_status_is_string(self):
        """Test that JobStatus values are strings."""
        assert isinstance(JobStatus.PENDING.value, str)
        assert JobStatus.PENDING == "pending"


class TestConfig:
    """Tests for the Config dataclass."""
    
    def test_config_creation(self):
        """Test creating a Config instance."""
        config = Config(
            service_url="https://example.com",
            review_ui_url="https://review.example.com",
            poll_interval=10,
            output_dir="/tmp/output",
            auth_token="test-token"
        )
        assert config.service_url == "https://example.com"
        assert config.review_ui_url == "https://review.example.com"
        assert config.poll_interval == 10
        assert config.output_dir == "/tmp/output"
        assert config.auth_token == "test-token"
    
    def test_config_optional_auth_token(self):
        """Test that auth_token is optional."""
        config = Config(
            service_url="https://example.com",
            review_ui_url="https://review.example.com",
            poll_interval=5,
            output_dir="/tmp"
        )
        assert config.auth_token is None


class TestRemoteKaraokeClient:
    """Tests for the RemoteKaraokeClient class."""
    
    @pytest.fixture
    def config(self):
        """Create a test config."""
        return Config(
            service_url="https://api.example.com",
            review_ui_url="https://review.example.com",
            poll_interval=5,
            output_dir="/tmp/output",
            auth_token="test-token"
        )
    
    @pytest.fixture
    def logger(self):
        """Create a test logger."""
        return logging.getLogger("test")
    
    @pytest.fixture
    def client(self, config, logger):
        """Create a test client."""
        return RemoteKaraokeClient(config, logger)
    
    def test_client_creation(self, config, logger):
        """Test creating a client."""
        client = RemoteKaraokeClient(config, logger)
        assert client.config == config
        assert client.logger == logger
    
    def test_setup_auth_with_token(self, config, logger):
        """Test that auth header is set when token is provided."""
        client = RemoteKaraokeClient(config, logger)
        assert 'Authorization' in client.session.headers
        assert client.session.headers['Authorization'] == 'Bearer test-token'
    
    def test_setup_auth_without_token(self, logger):
        """Test that no auth header is set when no token is provided."""
        config = Config(
            service_url="https://api.example.com",
            review_ui_url="https://review.example.com",
            poll_interval=5,
            output_dir="/tmp"
        )
        client = RemoteKaraokeClient(config, logger)
        assert 'Authorization' not in client.session.headers
    
    def test_allowed_extensions(self, client):
        """Test that allowed extensions are defined."""
        assert '.mp3' in client.ALLOWED_AUDIO_EXTENSIONS
        assert '.wav' in client.ALLOWED_AUDIO_EXTENSIONS
        assert '.flac' in client.ALLOWED_AUDIO_EXTENSIONS
        assert '.png' in client.ALLOWED_IMAGE_EXTENSIONS
        assert '.jpg' in client.ALLOWED_IMAGE_EXTENSIONS
        assert '.ttf' in client.ALLOWED_FONT_EXTENSIONS
        assert '.otf' in client.ALLOWED_FONT_EXTENSIONS
    
    @patch('subprocess.run')
    def test_get_auth_token_from_gcloud_success(self, mock_run, client):
        """Test getting auth token from gcloud."""
        mock_run.return_value = MagicMock(
            stdout="test-identity-token\n",
            returncode=0
        )
        token = client._get_auth_token_from_gcloud()
        assert token == "test-identity-token"
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_get_auth_token_from_gcloud_failure(self, mock_run, client):
        """Test handling gcloud auth failure."""
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, 'gcloud')
        token = client._get_auth_token_from_gcloud()
        assert token is None
    
    @patch('subprocess.run')
    def test_get_auth_token_gcloud_not_found(self, mock_run, client):
        """Test handling missing gcloud CLI."""
        mock_run.side_effect = FileNotFoundError()
        token = client._get_auth_token_from_gcloud()
        assert token is None
    
    @patch('subprocess.run')
    def test_refresh_auth_success(self, mock_run, client):
        """Test refreshing auth token."""
        mock_run.return_value = MagicMock(
            stdout="new-token\n",
            returncode=0
        )
        result = client.refresh_auth()
        assert result is True
        assert client.config.auth_token == "new-token"
        assert client.session.headers['Authorization'] == 'Bearer new-token'
    
    @patch('subprocess.run')
    def test_refresh_auth_failure(self, mock_run, client):
        """Test handling auth refresh failure."""
        mock_run.side_effect = FileNotFoundError()
        result = client.refresh_auth()
        assert result is False
    
    def test_parse_style_params_with_files(self, client, tmp_path):
        """Test parsing style params JSON with file references."""
        # Create temp files
        font_file = tmp_path / "font.ttf"
        font_file.write_bytes(b"font data")
        bg_file = tmp_path / "bg.png"
        bg_file.write_bytes(b"image data")
        
        style_params = {
            "intro": {
                "background_image": str(bg_file),
                "font": str(font_file)
            }
        }
        
        style_file = tmp_path / "style_params.json"
        style_file.write_text(json.dumps(style_params))
        
        assets = client._parse_style_params(str(style_file))
        
        assert "style_intro_background" in assets
        assert "style_font" in assets
        assert assets["style_intro_background"] == str(bg_file)
        assert assets["style_font"] == str(font_file)
    
    def test_parse_style_params_nonexistent_file(self, client, tmp_path):
        """Test parsing style params with nonexistent referenced files."""
        style_params = {
            "intro": {
                "background_image": "/nonexistent/file.png"
            }
        }
        
        style_file = tmp_path / "style_params.json"
        style_file.write_text(json.dumps(style_params))
        
        assets = client._parse_style_params(str(style_file))
        
        # Should not include nonexistent files
        assert "style_intro_background" not in assets
    
    def test_parse_style_params_invalid_json(self, client, tmp_path):
        """Test handling invalid JSON in style params."""
        style_file = tmp_path / "style_params.json"
        style_file.write_text("not valid json")
        
        assets = client._parse_style_params(str(style_file))
        assert assets == {}
    
    def test_parse_style_params_file_not_found(self, client):
        """Test handling nonexistent style params file."""
        assets = client._parse_style_params("/nonexistent/style.json")
        assert assets == {}
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_get_job_success(self, mock_request, client):
        """Test getting job status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "job-123",
            "status": "complete",
            "artist": "Test Artist",
            "title": "Test Title"
        }
        mock_request.return_value = mock_response
        
        result = client.get_job("job-123")
        
        assert result["id"] == "job-123"
        assert result["status"] == "complete"
        mock_request.assert_called_once_with('GET', '/api/jobs/job-123')
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_get_job_not_found(self, mock_request, client):
        """Test handling job not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response
        
        with pytest.raises(ValueError, match="Job not found"):
            client.get_job("nonexistent-job")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_get_job_error(self, mock_request, client):
        """Test handling job API error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Error getting job"):
            client.get_job("job-123")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_list_jobs_success(self, mock_request, client):
        """Test listing jobs successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"job_id": "job-1", "status": "complete", "artist": "Artist 1", "title": "Title 1"},
            {"job_id": "job-2", "status": "processing", "artist": "Artist 2", "title": "Title 2"},
        ]
        mock_request.return_value = mock_response
        
        result = client.list_jobs()
        
        assert len(result) == 2
        assert result[0]["job_id"] == "job-1"
        mock_request.assert_called_once_with('GET', '/api/jobs', params={'limit': 100})
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_list_jobs_with_status_filter(self, mock_request, client):
        """Test listing jobs with status filter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response
        
        client.list_jobs(status="complete", limit=50)
        
        mock_request.assert_called_once_with('GET', '/api/jobs', params={'limit': 50, 'status': 'complete'})
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_list_jobs_error(self, mock_request, client):
        """Test handling list jobs error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Error listing jobs"):
            client.list_jobs()
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_cancel_job_success(self, mock_request, client):
        """Test cancelling a job successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "cancelled"}
        mock_request.return_value = mock_response
        
        result = client.cancel_job("job-123")
        
        assert result["status"] == "cancelled"
        mock_request.assert_called_once_with(
            'POST',
            '/api/jobs/job-123/cancel',
            json={'reason': 'User requested'}
        )
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_cancel_job_not_found(self, mock_request, client):
        """Test cancelling non-existent job."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response
        
        with pytest.raises(ValueError, match="Job not found"):
            client.cancel_job("nonexistent-job")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_cancel_job_invalid_state(self, mock_request, client):
        """Test cancelling job in invalid state."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Job already complete"}
        mock_request.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Cannot cancel job"):
            client.cancel_job("job-123")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_delete_job_success(self, mock_request, client):
        """Test deleting a job successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "deleted"}
        mock_request.return_value = mock_response
        
        result = client.delete_job("job-123")
        
        assert result["status"] == "deleted"
        mock_request.assert_called_once_with(
            'DELETE',
            '/api/jobs/job-123',
            params={'delete_files': 'true'}
        )
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_delete_job_keep_files(self, mock_request, client):
        """Test deleting a job but keeping files."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "deleted"}
        mock_request.return_value = mock_response
        
        client.delete_job("job-123", delete_files=False)
        
        mock_request.assert_called_once_with(
            'DELETE',
            '/api/jobs/job-123',
            params={'delete_files': 'false'}
        )
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_delete_job_not_found(self, mock_request, client):
        """Test deleting non-existent job."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response
        
        with pytest.raises(ValueError, match="Job not found"):
            client.delete_job("nonexistent-job")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_get_instrumental_options(self, mock_request, client):
        """Test getting instrumental options."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "clean": {"url": "https://example.com/clean.mp3"},
            "with_backing": {"url": "https://example.com/backing.mp3"}
        }
        mock_request.return_value = mock_response
        
        result = client.get_instrumental_options("job-123")
        
        assert "clean" in result
        assert "with_backing" in result
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_select_instrumental(self, mock_request, client):
        """Test selecting instrumental."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response
        
        result = client.select_instrumental("job-123", "clean")
        
        assert result["status"] == "success"
        mock_request.assert_called_once_with(
            'POST',
            '/api/jobs/job-123/select-instrumental',
            json={'selection': 'clean'}
        )
    
    @patch('subprocess.run')
    def test_download_file_via_gsutil_success(self, mock_run, client):
        """Test successful file download."""
        mock_run.return_value = MagicMock(returncode=0)
        
        result = client.download_file_via_gsutil("path/to/file.mp4", "/local/file.mp4")
        
        assert result is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_download_file_via_gsutil_failure(self, mock_run, client):
        """Test failed file download."""
        mock_run.return_value = MagicMock(returncode=1)
        
        result = client.download_file_via_gsutil("path/to/file.mp4", "/local/file.mp4")
        
        assert result is False
    
    @patch('subprocess.run')
    def test_download_file_gsutil_not_found(self, mock_run, client):
        """Test handling missing gsutil."""
        mock_run.side_effect = FileNotFoundError()
        
        result = client.download_file_via_gsutil("path/to/file.mp4", "/local/file.mp4")
        
        assert result is False
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_submit_job_file_not_found(self, mock_request, client):
        """Test submitting job with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            client.submit_job("/nonexistent/file.mp3", "Artist", "Title")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_submit_job_unsupported_format(self, mock_request, client, tmp_path):
        """Test submitting job with unsupported file format."""
        # Create a file with unsupported extension
        test_file = tmp_path / "test.exe"
        test_file.write_bytes(b"test")
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            client.submit_job(str(test_file), "Artist", "Title")
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_submit_job_success(self, mock_request, client, tmp_path):
        """Test successful job submission."""
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"audio data")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "job_id": "new-job-123"
        }
        mock_request.return_value = mock_response
        
        result = client.submit_job(str(audio_file), "Test Artist", "Test Title")
        
        assert result["status"] == "success"
        assert result["job_id"] == "new-job-123"
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_submit_job_with_style_params(self, mock_request, client, tmp_path):
        """Test job submission with style params."""
        # Create test files
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"audio data")
        
        style_file = tmp_path / "style_params.json"
        style_file.write_text(json.dumps({"intro": {}}))
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "job_id": "new-job-456",
            "style_assets_uploaded": []
        }
        mock_request.return_value = mock_response
        
        result = client.submit_job(
            str(audio_file),
            "Test Artist",
            "Test Title",
            style_params_path=str(style_file),
            enable_cdg=True,
            enable_txt=True,
            brand_prefix="TEST",
            discord_webhook_url="https://discord.webhook/url"
        )
        
        assert result["status"] == "success"
    
    @patch.object(RemoteKaraokeClient, '_request')
    def test_submit_job_api_error(self, mock_request, client, tmp_path):
        """Test handling API error during job submission."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"audio data")
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Server error"}
        mock_request.return_value = mock_response
        
        with pytest.raises(RuntimeError, match="Error submitting job"):
            client.submit_job(str(audio_file), "Artist", "Title")


class TestJobMonitor:
    """Tests for the JobMonitor class."""
    
    @pytest.fixture
    def config(self):
        return Config(
            service_url="https://api.example.com",
            review_ui_url="https://review.example.com",
            poll_interval=1,
            output_dir="/tmp/output"
        )
    
    @pytest.fixture
    def logger(self):
        return logging.getLogger("test")
    
    @pytest.fixture
    def client(self, config, logger):
        return RemoteKaraokeClient(config, logger)
    
    @pytest.fixture
    def monitor(self, client, config, logger):
        return JobMonitor(client, config, logger)
    
    def test_monitor_creation(self, client, config, logger):
        """Test creating a JobMonitor."""
        monitor = JobMonitor(client, config, logger)
        assert monitor.client == client
        assert monitor.config == config
        assert monitor._review_opened is False
        assert monitor._instrumental_prompted is False
        assert monitor._last_timeline_index == 0
    
    @patch('subprocess.run')
    def test_open_browser_darwin(self, mock_run, monitor):
        """Test opening browser on macOS."""
        with patch('platform.system', return_value='Darwin'):
            monitor.open_browser("https://example.com")
            mock_run.assert_called_with(['open', 'https://example.com'], check=True)
    
    @patch('subprocess.run')
    def test_open_browser_linux(self, mock_run, monitor):
        """Test opening browser on Linux."""
        with patch('platform.system', return_value='Linux'):
            monitor.open_browser("https://example.com")
            mock_run.assert_called()
    
    @patch('webbrowser.open')
    def test_open_browser_windows(self, mock_webbrowser, monitor):
        """Test opening browser on Windows."""
        with patch('platform.system', return_value='Windows'):
            monitor.open_browser("https://example.com")
            mock_webbrowser.assert_called_with("https://example.com")
    
    @patch('subprocess.run')
    def test_open_browser_failure(self, mock_run, monitor):
        """Test handling browser open failure."""
        mock_run.side_effect = Exception("Failed")
        # Should not raise, just log
        with patch('platform.system', return_value='Darwin'):
            monitor.open_browser("https://example.com")
    
    @patch.object(JobMonitor, 'open_browser')
    @patch.object(RemoteKaraokeClient, 'get_job')
    def test_open_review_ui(self, mock_get_job, mock_open_browser, monitor):
        """Test opening review UI."""
        mock_get_job.return_value = {"audio_hash": "abc123"}
        
        monitor.open_review_ui("job-123")
        
        mock_open_browser.assert_called_once()
        call_url = mock_open_browser.call_args[0][0]
        assert "review.example.com" in call_url
        assert "job-123" in call_url
        assert "audioHash=abc123" in call_url
    
    def test_log_timeline_updates(self, monitor):
        """Test logging timeline events."""
        job_data = {
            "timeline": [
                {"timestamp": "2024-01-01T10:00:00Z", "status": "pending", "message": "Job created"},
                {"timestamp": "2024-01-01T10:01:00Z", "status": "processing", "message": "Processing", "progress": "50"}
            ]
        }
        
        monitor.log_timeline_updates(job_data)
        
        assert monitor._last_timeline_index == 2
        
        # Calling again with same data should not log again
        monitor.log_timeline_updates(job_data)
        assert monitor._last_timeline_index == 2
    
    def test_log_timeline_updates_new_events(self, monitor):
        """Test that only new events are logged."""
        monitor._last_timeline_index = 1
        
        job_data = {
            "timeline": [
                {"timestamp": "2024-01-01T10:00:00Z", "status": "pending", "message": "Old event"},
                {"timestamp": "2024-01-01T10:01:00Z", "status": "processing", "message": "New event"}
            ]
        }
        
        monitor.log_timeline_updates(job_data)
        
        assert monitor._last_timeline_index == 2


class TestHelperFunctions:
    """Tests for module-level helper functions."""
    
    @patch('subprocess.run')
    def test_check_prerequisites_all_available(self, mock_run):
        """Test checking prerequisites when all tools are available."""
        mock_run.return_value = MagicMock(returncode=0)
        logger = logging.getLogger("test")
        
        result = check_prerequisites(logger)
        
        assert result is True
        assert mock_run.call_count == 2  # gcloud and gsutil
    
    @patch('subprocess.run')
    def test_check_prerequisites_gcloud_missing(self, mock_run):
        """Test handling missing gcloud."""
        mock_run.side_effect = FileNotFoundError()
        logger = logging.getLogger("test")
        
        result = check_prerequisites(logger)
        
        # Should still return True but with warnings
        assert result is True
    
    @patch('subprocess.run')
    def test_get_auth_token_from_env(self, mock_run):
        """Test getting auth token from environment variable."""
        logger = logging.getLogger("test")
        
        with patch.dict(os.environ, {'KARAOKE_GEN_AUTH_TOKEN': 'env-token'}):
            token = get_auth_token(logger)
            assert token == 'env-token'
    
    @patch('subprocess.run')
    def test_get_auth_token_from_gcloud(self, mock_run):
        """Test getting auth token from gcloud."""
        mock_run.return_value = MagicMock(
            stdout="gcloud-token\n",
            returncode=0
        )
        logger = logging.getLogger("test")
        
        # Make sure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            # Clear the env var if it exists
            os.environ.pop('KARAOKE_GEN_AUTH_TOKEN', None)
            token = get_auth_token(logger)
            assert token == "gcloud-token"
    
    @patch('subprocess.run')
    def test_get_auth_token_not_available(self, mock_run):
        """Test when no auth token is available."""
        mock_run.side_effect = FileNotFoundError()
        logger = logging.getLogger("test")
        
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop('KARAOKE_GEN_AUTH_TOKEN', None)
            token = get_auth_token(logger)
            assert token is None


class TestMain:
    """Tests for the main() function."""
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    def test_main_no_service_url(self, mock_create_parser):
        """Test main exits when no service URL is provided."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = None
        mock_args.log_level = "info"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        result = main()
        
        assert result == 1
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    def test_main_finalise_only_not_supported(
        self, mock_check, mock_auth, mock_create_parser
    ):
        """Test main rejects --finalise-only in remote mode."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.log_level = "info"
        mock_args.finalise_only = True
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        result = main()
        
        assert result == 1
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    def test_main_edit_lyrics_not_supported(
        self, mock_check, mock_auth, mock_create_parser
    ):
        """Test main rejects --edit-lyrics in remote mode."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = True
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        result = main()
        
        assert result == 1
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    def test_main_test_email_not_supported(
        self, mock_check, mock_auth, mock_create_parser
    ):
        """Test main rejects --test_email_template in remote mode."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = True
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        result = main()
        
        assert result == 1
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    def test_main_no_args_shows_help(
        self, mock_check, mock_auth, mock_create_parser
    ):
        """Test main shows help when no positional args provided."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_args.args = []  # No positional args
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        result = main()
        
        assert result == 1
        mock_parser.print_help.assert_called_once()
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.JobMonitor')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_resume_mode(
        self, mock_client_class, mock_monitor_class, mock_check, mock_auth, mock_create_parser
    ):
        """Test main in resume mode."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = "job-123"
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        mock_client = MagicMock()
        mock_client.get_job.return_value = {
            "artist": "Artist",
            "title": "Title",
            "status": "processing"
        }
        mock_client_class.return_value = mock_client
        
        mock_monitor = MagicMock()
        mock_monitor.monitor.return_value = 0
        mock_monitor_class.return_value = mock_monitor
        
        result = main()
        
        assert result == 0
        mock_monitor.monitor.assert_called_once_with("job-123")
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_list_jobs_mode(
        self, mock_client_class, mock_check, mock_create_parser
    ):
        """Test main in list jobs mode."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = True
        mock_args.cancel = None
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.list_jobs.return_value = [
            {"job_id": "job-1", "status": "complete", "artist": "Artist 1", "title": "Title 1"},
            {"job_id": "job-2", "status": "processing", "artist": "Artist 2", "title": "Title 2"},
        ]
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 0
        mock_client.list_jobs.assert_called_once_with(limit=100)
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_list_jobs_empty(
        self, mock_client_class, mock_check, mock_create_parser
    ):
        """Test main in list jobs mode with no jobs."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = True
        mock_args.cancel = None
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.list_jobs.return_value = []
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 0
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_cancel_job_mode(
        self, mock_client_class, mock_check, mock_create_parser
    ):
        """Test main in cancel job mode."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = "job-123"
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.get_job.return_value = {
            "artist": "Artist",
            "title": "Title",
            "status": "processing"
        }
        mock_client.cancel_job.return_value = {"status": "cancelled"}
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 0
        mock_client.cancel_job.assert_called_once_with("job-123")
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_cancel_job_not_found(
        self, mock_client_class, mock_check, mock_create_parser
    ):
        """Test main cancel job when job not found."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = "nonexistent"
        mock_args.delete = None
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.get_job.side_effect = ValueError("Job not found: nonexistent")
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 1
    
    @patch('builtins.input', return_value='y')
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_delete_job_mode(
        self, mock_client_class, mock_check, mock_create_parser, mock_input
    ):
        """Test main in delete job mode with confirmation."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = "job-123"
        mock_args.yes = False  # Interactive mode
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.get_job.return_value = {
            "artist": "Artist",
            "title": "Title",
            "status": "complete"
        }
        mock_client.delete_job.return_value = {"status": "deleted"}
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 0
        mock_client.delete_job.assert_called_once_with("job-123", delete_files=True)
    
    @patch('builtins.input', return_value='n')
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_delete_job_cancelled(
        self, mock_client_class, mock_check, mock_create_parser, mock_input
    ):
        """Test main delete job when user cancels."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = "job-123"
        mock_args.yes = False  # Interactive mode
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.get_job.return_value = {
            "artist": "Artist",
            "title": "Title",
            "status": "complete"
        }
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 0
        mock_client.delete_job.assert_not_called()
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.RemoteKaraokeClient')
    def test_main_delete_job_non_interactive(
        self, mock_client_class, mock_check, mock_create_parser
    ):
        """Test main delete job in non-interactive mode (with -y flag)."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = "job-123"
        mock_args.yes = True  # Non-interactive mode
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        
        mock_client = MagicMock()
        mock_client.get_job.return_value = {
            "artist": "Artist",
            "title": "Title",
            "status": "complete"
        }
        mock_client.delete_job.return_value = {"status": "deleted"}
        mock_client_class.return_value = mock_client
        
        result = main()
        
        assert result == 0
        mock_client.delete_job.assert_called_once_with("job-123", delete_files=True)
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_main_directory_input_not_supported(
        self, mock_isdir, mock_isfile, mock_check, mock_auth, mock_create_parser
    ):
        """Test main rejects directory input."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_args.args = ["/path/to/folder"]
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        
        result = main()
        
        assert result == 1
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.is_url')
    @patch('karaoke_gen.utils.remote_cli.is_file')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    def test_main_audio_search_not_supported(
        self, mock_isdir, mock_isfile, mock_is_file, mock_is_url, 
        mock_check, mock_auth, mock_create_parser
    ):
        """Test main rejects audio search (artist+title without file)."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_args.args = ["Artist", "Title"]  # Audio search format (not yet supported in remote)
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        mock_is_url.return_value = False
        mock_is_file.return_value = False
        mock_isfile.return_value = False
        mock_isdir.return_value = False
        
        result = main()
        
        assert result == 1
    
    @patch('karaoke_gen.utils.remote_cli.create_parser')
    @patch('karaoke_gen.utils.remote_cli.get_auth_token')
    @patch('karaoke_gen.utils.remote_cli.check_prerequisites')
    @patch('karaoke_gen.utils.remote_cli.is_url')
    @patch('karaoke_gen.utils.remote_cli.is_file')
    @patch('os.path.isfile')
    def test_main_missing_artist_title(
        self, mock_isfile, mock_is_file, mock_is_url, 
        mock_check, mock_auth, mock_create_parser
    ):
        """Test main rejects file without artist/title."""
        mock_parser = MagicMock()
        mock_args = MagicMock()
        mock_args.service_url = "https://api.example.com"
        mock_args.review_ui_url = "https://review.example.com"
        mock_args.poll_interval = 5
        mock_args.output_dir = "/tmp"
        mock_args.log_level = "info"
        mock_args.finalise_only = False
        mock_args.edit_lyrics = False
        mock_args.test_email_template = False
        mock_args.resume = None
        mock_args.list_jobs = False
        mock_args.cancel = None
        mock_args.delete = None
        mock_args.args = ["/path/to/file.mp3"]  # File only, no artist/title
        mock_parser.parse_args.return_value = mock_args
        mock_create_parser.return_value = mock_parser
        mock_auth.return_value = "token"
        
        mock_is_url.return_value = False
        mock_is_file.return_value = True
        mock_isfile.return_value = True
        
        result = main()
        
        assert result == 1


class TestJobMonitorDownloads:
    """Tests for JobMonitor file download functionality."""
    
    @pytest.fixture
    def config(self):
        return Config(
            service_url="https://api.example.com",
            review_ui_url="https://review.example.com",
            poll_interval=1,
            output_dir="/tmp/output"
        )
    
    @pytest.fixture
    def logger(self):
        return logging.getLogger("test")
    
    @pytest.fixture
    def client(self, config, logger):
        return RemoteKaraokeClient(config, logger)
    
    @pytest.fixture
    def monitor(self, client, config, logger):
        return JobMonitor(client, config, logger)
    
    @patch.object(RemoteKaraokeClient, 'download_file_via_gsutil')
    @patch('pathlib.Path.mkdir')
    def test_download_outputs_with_brand_code(self, mock_mkdir, mock_download, monitor, tmp_path):
        """Test downloading outputs with brand code in folder name."""
        monitor.config.output_dir = str(tmp_path)
        mock_download.return_value = True
        
        job_data = {
            "artist": "Test Artist",
            "title": "Test Title",
            "state_data": {"brand_code": "TEST-0001"},
            "file_urls": {
                "finals": {
                    "lossless_4k_mp4": "jobs/123/final.mp4"
                }
            }
        }
        
        monitor.download_outputs("job-123", job_data)
        
        mock_download.assert_called()
    
    @patch.object(RemoteKaraokeClient, 'download_file_via_gsutil')
    @patch('pathlib.Path.mkdir')
    def test_download_outputs_without_brand_code(self, mock_mkdir, mock_download, monitor, tmp_path):
        """Test downloading outputs without brand code."""
        monitor.config.output_dir = str(tmp_path)
        mock_download.return_value = True
        
        job_data = {
            "artist": "Test Artist",
            "title": "Test Title",
            "state_data": {},
            "file_urls": {
                "finals": {
                    "lossy_720p": "jobs/123/final_720p.mp4"
                }
            }
        }
        
        monitor.download_outputs("job-123", job_data)
        
        mock_download.assert_called()
    
    @patch.object(RemoteKaraokeClient, 'download_file_via_gsutil')
    @patch('pathlib.Path.mkdir')
    def test_download_outputs_packages(self, mock_mkdir, mock_download, monitor, tmp_path):
        """Test downloading CDG/TXT packages."""
        monitor.config.output_dir = str(tmp_path)
        mock_download.return_value = True
        
        job_data = {
            "artist": "Test Artist",
            "title": "Test Title",
            "state_data": {},
            "file_urls": {
                "packages": {
                    "cdg_zip": "jobs/123/cdg.zip",
                    "txt_zip": "jobs/123/txt.zip"
                }
            }
        }
        
        monitor.download_outputs("job-123", job_data)
        
        # Should be called twice for the two packages
        assert mock_download.call_count >= 2


class TestJobMonitorHandleReview:
    """Tests for JobMonitor review handling."""
    
    @pytest.fixture
    def config(self):
        return Config(
            service_url="https://api.example.com",
            review_ui_url="https://review.example.com",
            poll_interval=0.1,  # Short for testing
            output_dir="/tmp/output"
        )
    
    @pytest.fixture
    def logger(self):
        return logging.getLogger("test")
    
    @pytest.fixture
    def client(self, config, logger):
        return RemoteKaraokeClient(config, logger)
    
    @pytest.fixture
    def monitor(self, client, config, logger):
        return JobMonitor(client, config, logger)
    
    @patch.object(JobMonitor, 'open_review_ui')
    @patch.object(RemoteKaraokeClient, 'get_job')
    def test_handle_review_waits_for_completion(self, mock_get_job, mock_open_ui, monitor):
        """Test handle_review waits until review is complete."""
        # First call returns in_review, second returns review_complete
        mock_get_job.side_effect = [
            {"status": "in_review"},
            {"status": "review_complete"}
        ]
        
        monitor.handle_review("job-123")
        
        mock_open_ui.assert_called_once_with("job-123")
        assert mock_get_job.call_count == 2
