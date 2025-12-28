"""Tests for core configuration classes."""

import os
import pytest
from unittest.mock import patch
from lyrics_transcriber.core.config import TranscriberConfig


class TestTranscriberConfig:
    """Tests for TranscriberConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly when no env vars are present."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove any existing WHISPER_* env vars
            for key in list(os.environ.keys()):
                if key.startswith("WHISPER_"):
                    del os.environ[key]

            config = TranscriberConfig()
            assert config.enable_local_whisper is True
            assert config.local_whisper_model_size == "medium"
            assert config.local_whisper_device is None
            assert config.local_whisper_cache_dir is None
            assert config.local_whisper_language is None

    def test_reads_whisper_model_size_from_env(self):
        """Test that WHISPER_MODEL_SIZE env var is respected."""
        with patch.dict(os.environ, {"WHISPER_MODEL_SIZE": "large"}, clear=False):
            config = TranscriberConfig()
            assert config.local_whisper_model_size == "large"

    def test_reads_whisper_device_from_env(self):
        """Test that WHISPER_DEVICE env var is respected."""
        with patch.dict(os.environ, {"WHISPER_DEVICE": "mps"}, clear=False):
            config = TranscriberConfig()
            assert config.local_whisper_device == "mps"

    def test_reads_whisper_cache_dir_from_env(self):
        """Test that WHISPER_CACHE_DIR env var is respected."""
        with patch.dict(os.environ, {"WHISPER_CACHE_DIR": "/custom/cache"}, clear=False):
            config = TranscriberConfig()
            assert config.local_whisper_cache_dir == "/custom/cache"

    def test_reads_whisper_language_from_env(self):
        """Test that WHISPER_LANGUAGE env var is respected."""
        with patch.dict(os.environ, {"WHISPER_LANGUAGE": "en"}, clear=False):
            config = TranscriberConfig()
            assert config.local_whisper_language == "en"

    def test_reads_all_whisper_env_vars(self):
        """Test that all WHISPER_* env vars are respected together."""
        env_vars = {
            "WHISPER_MODEL_SIZE": "large-v3",
            "WHISPER_DEVICE": "cuda",
            "WHISPER_CACHE_DIR": "/models/whisper",
            "WHISPER_LANGUAGE": "es",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = TranscriberConfig()
            assert config.local_whisper_model_size == "large-v3"
            assert config.local_whisper_device == "cuda"
            assert config.local_whisper_cache_dir == "/models/whisper"
            assert config.local_whisper_language == "es"

    def test_explicit_values_override_env_vars(self):
        """Test that explicitly passed values override env vars."""
        with patch.dict(os.environ, {"WHISPER_MODEL_SIZE": "large"}, clear=False):
            config = TranscriberConfig(local_whisper_model_size="small")
            assert config.local_whisper_model_size == "small"

    def test_cloud_provider_config(self):
        """Test that cloud provider config fields work correctly."""
        config = TranscriberConfig(
            audioshake_api_token="test_token",
            runpod_api_key="test_key",
            whisper_runpod_id="test_id",
        )
        assert config.audioshake_api_token == "test_token"
        assert config.runpod_api_key == "test_key"
        assert config.whisper_runpod_id == "test_id"
