"""
Tests for LocalEncodingService.

Tests cover:
- Service initialization
- Hardware acceleration detection
- FFmpeg command execution
- Individual encoding methods
- Full encoding pipeline
- Dry run mode
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch, call

from backend.services.local_encoding_service import (
    LocalEncodingService,
    EncodingConfig,
    EncodingResult,
    get_local_encoding_service,
)


class TestLocalEncodingServiceInit:
    """Test service initialization."""

    def test_init_default_values(self):
        """Test default initialization."""
        service = LocalEncodingService()
        assert service.dry_run is False
        assert "ffmpeg" in service._ffmpeg_base_command

    def test_init_with_dry_run(self):
        """Test initialization with dry run mode."""
        service = LocalEncodingService(dry_run=True)
        assert service.dry_run is True

    def test_init_with_debug_logging(self):
        """Test initialization with debug logging level."""
        import logging
        service = LocalEncodingService(log_level=logging.DEBUG)
        assert "-loglevel verbose" in service._ffmpeg_base_command

    def test_init_with_info_logging(self):
        """Test initialization with info logging level."""
        import logging
        service = LocalEncodingService(log_level=logging.INFO)
        assert "-loglevel fatal" in service._ffmpeg_base_command


class TestLocalEncodingServiceHWAccel:
    """Test hardware acceleration detection."""

    @patch("subprocess.run")
    def test_detect_nvenc_available(self, mock_run):
        """Test NVENC detection when available."""
        mock_run.return_value = MagicMock(returncode=0)

        service = LocalEncodingService()
        # Force detection
        service._detect_and_set_hwaccel()

        assert service._hwaccel_available is True
        assert service._video_encoder == "h264_nvenc"
        assert service._scale_filter == "scale_cuda"

    @patch("subprocess.run")
    def test_detect_no_hwaccel(self, mock_run):
        """Test fallback when no hardware acceleration available."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "test")

        service = LocalEncodingService()
        # Force detection
        service._detect_and_set_hwaccel()

        assert service._hwaccel_available is False
        assert service._video_encoder == "libx264"
        assert service._scale_filter == "scale"

    def test_nvenc_quality_settings(self):
        """Test NVENC quality settings for different presets."""
        service = LocalEncodingService()
        service._hwaccel_available = True

        lossless = service._get_nvenc_quality_settings("lossless")
        assert "cq 0" in lossless

        medium = service._get_nvenc_quality_settings("medium")
        assert "p4" in medium

    def test_nvenc_quality_settings_disabled(self):
        """Test NVENC quality settings when hwaccel is disabled."""
        service = LocalEncodingService()
        service._hwaccel_available = False

        settings = service._get_nvenc_quality_settings("lossless")
        assert settings == ""


class TestLocalEncodingServiceExecuteCommand:
    """Test command execution."""

    @patch("subprocess.run")
    def test_execute_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = MagicMock(returncode=0)

        service = LocalEncodingService()
        result = service._execute_command("echo test", "Test command")

        assert result is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_execute_command_failure(self, mock_run):
        """Test command execution failure."""
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "test", stderr="Error message"
        )

        service = LocalEncodingService()
        result = service._execute_command("echo test", "Test command")

        assert result is False

    @patch("subprocess.run")
    def test_execute_command_timeout(self, mock_run):
        """Test command execution timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("test", 30)

        service = LocalEncodingService()
        result = service._execute_command("echo test", "Test command", timeout=30)

        assert result is False

    def test_execute_command_dry_run(self):
        """Test command execution in dry run mode."""
        service = LocalEncodingService(dry_run=True)
        result = service._execute_command("echo test", "Test command")

        assert result is True
        # No actual subprocess should be called in dry run mode


class TestLocalEncodingServiceEncodingMethods:
    """Test individual encoding methods."""

    @patch.object(LocalEncodingService, "_execute_command")
    def test_remux_with_instrumental(self, mock_execute):
        """Test remuxing with instrumental audio."""
        mock_execute.return_value = True

        service = LocalEncodingService()
        result = service.remux_with_instrumental(
            "/input/video.mov",
            "/input/audio.flac",
            "/output/video.mp4"
        )

        assert result is True
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0][0]
        assert "/input/video.mov" in call_args
        assert "/input/audio.flac" in call_args
        assert "-map 0:v -map 1:a" in call_args

    @patch.object(LocalEncodingService, "_execute_command_with_fallback")
    def test_convert_mov_to_mp4(self, mock_execute):
        """Test MOV to MP4 conversion."""
        mock_execute.return_value = True

        service = LocalEncodingService()
        result = service.convert_mov_to_mp4(
            "/input/video.mov",
            "/output/video.mp4"
        )

        assert result is True
        mock_execute.assert_called_once()

    @patch.object(LocalEncodingService, "_execute_command_with_fallback")
    def test_encode_lossless_mp4_without_end(self, mock_execute):
        """Test lossless 4K MP4 encoding without end credits."""
        mock_execute.return_value = True

        service = LocalEncodingService()
        result = service.encode_lossless_mp4(
            "/input/title.mov",
            "/input/karaoke.mp4",
            "/output/lossless.mp4"
        )

        assert result is True
        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "concat=n=2" in call_args[0][0]  # GPU command

    @patch.object(LocalEncodingService, "_execute_command_with_fallback")
    def test_encode_lossless_mp4_with_end(self, mock_execute):
        """Test lossless 4K MP4 encoding with end credits."""
        mock_execute.return_value = True

        with tempfile.TemporaryDirectory() as tmpdir:
            end_file = os.path.join(tmpdir, "end.mov")
            with open(end_file, "w") as f:
                f.write("fake video")

            service = LocalEncodingService()
            result = service.encode_lossless_mp4(
                "/input/title.mov",
                "/input/karaoke.mp4",
                "/output/lossless.mp4",
                end_video=end_file
            )

            assert result is True
            call_args = mock_execute.call_args
            assert "concat=n=3" in call_args[0][0]  # 3 videos

    @patch.object(LocalEncodingService, "_execute_command")
    def test_encode_lossy_mp4(self, mock_execute):
        """Test lossy 4K MP4 encoding."""
        mock_execute.return_value = True

        service = LocalEncodingService()
        result = service.encode_lossy_mp4(
            "/input/lossless.mp4",
            "/output/lossy.mp4"
        )

        assert result is True
        call_args = mock_execute.call_args[0][0]
        assert "-c:v copy" in call_args
        assert "aac" in call_args.lower()

    @patch.object(LocalEncodingService, "_execute_command")
    def test_encode_lossless_mkv(self, mock_execute):
        """Test MKV encoding with FLAC audio."""
        mock_execute.return_value = True

        service = LocalEncodingService()
        result = service.encode_lossless_mkv(
            "/input/lossless.mp4",
            "/output/video.mkv"
        )

        assert result is True
        call_args = mock_execute.call_args[0][0]
        assert "-c:v copy" in call_args
        assert "-c:a flac" in call_args

    @patch.object(LocalEncodingService, "_execute_command_with_fallback")
    def test_encode_720p(self, mock_execute):
        """Test 720p encoding."""
        mock_execute.return_value = True

        service = LocalEncodingService()
        result = service.encode_720p(
            "/input/lossless.mp4",
            "/output/720p.mp4"
        )

        assert result is True
        call_args = mock_execute.call_args
        # Should contain scale filter
        assert "1280:720" in call_args[0][0] or "1280:720" in call_args[0][1]


class TestLocalEncodingServiceFullPipeline:
    """Test full encoding pipeline."""

    @patch.object(LocalEncodingService, "remux_with_instrumental")
    @patch.object(LocalEncodingService, "convert_mov_to_mp4")
    @patch.object(LocalEncodingService, "encode_lossless_mp4")
    @patch.object(LocalEncodingService, "encode_lossy_mp4")
    @patch.object(LocalEncodingService, "encode_lossless_mkv")
    @patch.object(LocalEncodingService, "encode_720p")
    def test_encode_all_formats_success(
        self, mock_720p, mock_mkv, mock_lossy, mock_lossless, mock_convert, mock_remux
    ):
        """Test successful full encoding pipeline."""
        mock_remux.return_value = True
        mock_convert.return_value = True
        mock_lossless.return_value = True
        mock_lossy.return_value = True
        mock_mkv.return_value = True
        mock_720p.return_value = True

        service = LocalEncodingService()
        config = EncodingConfig(
            title_video="/input/title.mov",
            karaoke_video="/input/karaoke.mov",
            instrumental_audio="/input/instrumental.flac",
            output_karaoke_mp4="/output/karaoke.mp4",
            output_with_vocals_mp4="/output/with_vocals.mp4",
            output_lossless_4k_mp4="/output/lossless_4k.mp4",
            output_lossy_4k_mp4="/output/lossy_4k.mp4",
            output_lossless_mkv="/output/lossless.mkv",
            output_720p_mp4="/output/720p.mp4",
        )

        result = service.encode_all_formats(config)

        assert result.success is True
        assert "karaoke_mp4" in result.output_files
        assert "lossless_4k_mp4" in result.output_files
        assert "720p_mp4" in result.output_files

    @patch.object(LocalEncodingService, "remux_with_instrumental")
    def test_encode_all_formats_failure_early(self, mock_remux):
        """Test encoding pipeline failure at early step."""
        mock_remux.return_value = False

        service = LocalEncodingService()
        config = EncodingConfig(
            title_video="/input/title.mov",
            karaoke_video="/input/karaoke.mov",
            instrumental_audio="/input/instrumental.flac",
            output_karaoke_mp4="/output/karaoke.mp4",
            output_lossless_4k_mp4="/output/lossless_4k.mp4",
        )

        result = service.encode_all_formats(config)

        assert result.success is False
        assert "Failed to remux" in result.error

    def test_encode_all_formats_dry_run(self):
        """Test encoding pipeline in dry run mode."""
        service = LocalEncodingService(dry_run=True)
        config = EncodingConfig(
            title_video="/input/title.mov",
            karaoke_video="/input/karaoke.mp4",  # Already MP4
            instrumental_audio="/input/instrumental.flac",
            output_karaoke_mp4="/output/karaoke.mp4",
            output_lossless_4k_mp4="/output/lossless_4k.mp4",
            output_lossy_4k_mp4="/output/lossy_4k.mp4",
            output_lossless_mkv="/output/lossless.mkv",
            output_720p_mp4="/output/720p.mp4",
        )

        result = service.encode_all_formats(config)

        # In dry run mode, all operations should "succeed"
        assert result.success is True


class TestEncodingConfig:
    """Test EncodingConfig dataclass."""

    def test_config_required_fields(self):
        """Test that required fields must be provided."""
        config = EncodingConfig(
            title_video="/path/title.mov",
            karaoke_video="/path/karaoke.mov",
            instrumental_audio="/path/audio.flac",
        )
        assert config.title_video == "/path/title.mov"
        assert config.end_video is None  # Optional field

    def test_config_all_fields(self):
        """Test config with all fields."""
        config = EncodingConfig(
            title_video="/path/title.mov",
            karaoke_video="/path/karaoke.mov",
            instrumental_audio="/path/audio.flac",
            end_video="/path/end.mov",
            output_karaoke_mp4="/output/karaoke.mp4",
            output_720p_mp4="/output/720p.mp4",
        )
        assert config.end_video == "/path/end.mov"
        assert config.output_karaoke_mp4 == "/output/karaoke.mp4"


class TestEncodingResult:
    """Test EncodingResult dataclass."""

    def test_result_success(self):
        """Test successful result."""
        result = EncodingResult(
            success=True,
            output_files={"key": "/path/file.mp4"}
        )
        assert result.success is True
        assert result.error is None

    def test_result_failure(self):
        """Test failure result."""
        result = EncodingResult(
            success=False,
            output_files={},
            error="Something went wrong"
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestGetLocalEncodingService:
    """Test factory function."""

    def test_get_service_creates_instance(self):
        """Test that factory function creates a new instance."""
        import backend.services.local_encoding_service as module
        module._local_encoding_service = None

        service = get_local_encoding_service()

        assert service is not None
        assert isinstance(service, LocalEncodingService)

    def test_get_service_with_dry_run(self):
        """Test factory function with dry run option."""
        import backend.services.local_encoding_service as module
        module._local_encoding_service = None

        service = get_local_encoding_service(dry_run=True)

        assert service.dry_run is True
