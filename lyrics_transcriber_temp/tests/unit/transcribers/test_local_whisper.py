"""Tests for LocalWhisperTranscriber."""

import pytest
import logging
import os
import shutil
import tempfile
from unittest.mock import Mock, patch, MagicMock
from lyrics_transcriber.types import TranscriptionData
from lyrics_transcriber.transcribers.local_whisper import (
    LocalWhisperTranscriber,
    LocalWhisperConfig,
)
from lyrics_transcriber.transcribers.base_transcriber import TranscriptionError
from tests.test_helpers import create_test_word, create_test_segment


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def test_cache_dir():
    """Create and cleanup a test cache directory."""
    cache_dir = tempfile.mkdtemp(prefix="test_local_whisper_cache_")
    yield cache_dir
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)


@pytest.fixture
def default_config():
    """Create a default LocalWhisperConfig for testing."""
    return LocalWhisperConfig(
        model_size="medium",
        device="cpu",
        cache_dir=None,
        language=None,
    )


@pytest.fixture
def mock_whisper_output():
    """Sample output from whisper-timestamped."""
    return {
        "text": "Hello world, this is a test.",
        "segments": [
            {
                "id": 0,
                "text": "Hello world,",
                "start": 0.0,
                "end": 1.5,
                "words": [
                    {"text": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.95},
                    {"text": "world,", "start": 0.6, "end": 1.5, "confidence": 0.92},
                ],
            },
            {
                "id": 1,
                "text": "this is a test.",
                "start": 1.6,
                "end": 3.0,
                "words": [
                    {"text": "this", "start": 1.6, "end": 1.8, "confidence": 0.98},
                    {"text": "is", "start": 1.9, "end": 2.0, "confidence": 0.97},
                    {"text": "a", "start": 2.1, "end": 2.2, "confidence": 0.99},
                    {"text": "test.", "start": 2.3, "end": 3.0, "confidence": 0.96},
                ],
            },
        ],
        "language": "en",
    }


class TestLocalWhisperConfig:
    """Tests for LocalWhisperConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = LocalWhisperConfig()
        assert config.model_size == "medium"
        assert config.device is None
        assert config.cache_dir is None
        assert config.language is None

    def test_custom_values(self):
        """Test that custom values can be set."""
        config = LocalWhisperConfig(
            model_size="large",
            device="cuda",
            cache_dir="/custom/cache",
            language="en",
        )
        assert config.model_size == "large"
        assert config.device == "cuda"
        assert config.cache_dir == "/custom/cache"
        assert config.language == "en"


class TestLocalWhisperTranscriber:
    """Tests for LocalWhisperTranscriber class."""

    def test_init_with_config(self, mock_logger, test_cache_dir, default_config):
        """Test initialization with explicit config."""
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=default_config,
            logger=mock_logger,
        )
        assert transcriber.config == default_config
        assert transcriber.logger == mock_logger
        assert str(transcriber.cache_dir) == test_cache_dir

    def test_init_without_config(self, mock_logger, test_cache_dir):
        """Test initialization without config uses environment variables."""
        with patch.dict(
            os.environ,
            {
                "WHISPER_MODEL_SIZE": "small",
                "WHISPER_DEVICE": "cpu",
            },
            clear=False,
        ):
            transcriber = LocalWhisperTranscriber(
                cache_dir=test_cache_dir,
                logger=mock_logger,
            )
            assert transcriber.config.model_size == "small"
            assert transcriber.config.device == "cpu"

    def test_get_name(self, mock_logger, test_cache_dir, default_config):
        """Test that get_name returns correct name."""
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=default_config,
            logger=mock_logger,
        )
        assert transcriber.get_name() == "LocalWhisper"

    def test_check_dependencies_not_installed(self, mock_logger, test_cache_dir, default_config):
        """Test that missing dependencies raise TranscriptionError."""
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=default_config,
            logger=mock_logger,
        )

        # Mock import to fail
        with patch.dict("sys.modules", {"whisper_timestamped": None}):
            with pytest.raises(TranscriptionError, match="whisper-timestamped is not installed"):
                transcriber._check_dependencies()

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._check_dependencies")
    def test_get_device_explicit(self, mock_check, mock_logger, test_cache_dir):
        """Test device selection when explicitly set."""
        config = LocalWhisperConfig(device="cuda")
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=config,
            logger=mock_logger,
        )
        assert transcriber._get_device() == "cuda"

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._check_dependencies")
    def test_get_device_auto_detect_cpu(self, mock_check, mock_logger, test_cache_dir, default_config):
        """Test auto-detection falls back to CPU."""
        # Mock torch to simulate no GPU available
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            config = LocalWhisperConfig(device=None)  # Auto-detect
            transcriber = LocalWhisperTranscriber(
                cache_dir=test_cache_dir,
                config=config,
                logger=mock_logger,
            )
            device = transcriber._get_device()
            assert device == "cpu"


class TestLocalWhisperTranscriberConversion:
    """Tests for result format conversion."""

    @pytest.fixture
    def transcriber(self, mock_logger, test_cache_dir, default_config):
        """Create transcriber instance for conversion tests."""
        return LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=default_config,
            logger=mock_logger,
        )

    def test_convert_result_format_basic(self, transcriber, mock_whisper_output):
        """Test basic conversion of whisper output."""
        result = transcriber._convert_result_format(mock_whisper_output)

        assert isinstance(result, TranscriptionData)
        assert result.text == "Hello world, this is a test."
        assert result.source == "LocalWhisper"
        assert len(result.segments) == 2
        assert len(result.words) == 6  # 2 + 4 words

    def test_convert_result_format_segments(self, transcriber, mock_whisper_output):
        """Test that segments are correctly converted."""
        result = transcriber._convert_result_format(mock_whisper_output)

        # Check first segment
        seg1 = result.segments[0]
        assert seg1.text == "Hello world,"
        assert seg1.start_time == 0.0
        assert seg1.end_time == 1.5
        assert len(seg1.words) == 2

        # Check second segment
        seg2 = result.segments[1]
        assert seg2.text == "this is a test."
        assert seg2.start_time == 1.6
        assert seg2.end_time == 3.0
        assert len(seg2.words) == 4

    def test_convert_result_format_words(self, transcriber, mock_whisper_output):
        """Test that words are correctly converted with IDs."""
        result = transcriber._convert_result_format(mock_whisper_output)

        # Check first word
        word1 = result.words[0]
        assert word1.text == "Hello"
        assert word1.start_time == 0.0
        assert word1.end_time == 0.5
        assert word1.confidence == 0.95
        assert word1.id is not None  # Should have generated ID

        # Check that all words have unique IDs
        word_ids = [w.id for w in result.words]
        assert len(word_ids) == len(set(word_ids))  # All unique

    def test_convert_result_format_metadata(self, transcriber, mock_whisper_output):
        """Test that metadata is correctly set."""
        result = transcriber._convert_result_format(mock_whisper_output)

        assert result.metadata["model_size"] == "medium"
        assert result.metadata["detected_language"] == "en"
        assert result.metadata["device"] == "cpu"

    def test_convert_result_format_empty_segments(self, transcriber):
        """Test conversion with empty segments."""
        empty_output = {
            "text": "",
            "segments": [],
            "language": "en",
        }
        result = transcriber._convert_result_format(empty_output)

        assert result.text == ""
        assert len(result.segments) == 0
        assert len(result.words) == 0

    def test_convert_result_format_missing_confidence(self, transcriber):
        """Test conversion when words are missing confidence scores."""
        output_no_confidence = {
            "text": "Hello world",
            "segments": [
                {
                    "id": 0,
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 1.0,
                    "words": [
                        {"text": "Hello", "start": 0.0, "end": 0.4},
                        {"text": "world", "start": 0.5, "end": 1.0},
                    ],
                }
            ],
            "language": "en",
        }
        result = transcriber._convert_result_format(output_no_confidence)

        # Words should have None confidence
        assert result.words[0].confidence is None
        assert result.words[1].confidence is None

    def test_convert_result_format_special_characters(self, transcriber):
        """Test conversion with special characters in lyrics."""
        output_special = {
            "text": "Don't stop believin'!",
            "segments": [
                {
                    "id": 0,
                    "text": "Don't stop believin'!",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {"text": "Don't", "start": 0.0, "end": 0.5, "confidence": 0.9},
                        {"text": "stop", "start": 0.6, "end": 1.0, "confidence": 0.95},
                        {"text": "believin'!", "start": 1.1, "end": 2.0, "confidence": 0.88},
                    ],
                }
            ],
            "language": "en",
        }
        result = transcriber._convert_result_format(output_special)

        assert result.text == "Don't stop believin'!"
        assert result.words[0].text == "Don't"
        assert result.words[2].text == "believin'!"


class TestLocalWhisperTranscriberTranscription:
    """Tests for actual transcription functionality."""

    @pytest.fixture
    def transcriber(self, mock_logger, test_cache_dir, default_config):
        """Create transcriber instance."""
        return LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=default_config,
            logger=mock_logger,
        )

    @pytest.fixture
    def test_audio_file(self, test_cache_dir):
        """Create a dummy audio file for testing."""
        audio_path = os.path.join(test_cache_dir, "test_audio.wav")
        with open(audio_path, "wb") as f:
            f.write(b"dummy audio content")
        return audio_path

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._load_model")
    def test_perform_transcription_calls_model(
        self, mock_load_model, transcriber, test_audio_file, mock_whisper_output
    ):
        """Test that _perform_transcription calls the model correctly."""
        # Setup mock
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model

        mock_whisper = MagicMock()
        mock_whisper.transcribe_timestamped.return_value = mock_whisper_output
        transcriber._whisper_module = mock_whisper

        # Call transcription
        result = transcriber._perform_transcription(test_audio_file)

        # Verify model was loaded and transcription was called
        mock_load_model.assert_called_once()
        mock_whisper.transcribe_timestamped.assert_called_once()

        # Verify the audio file path was passed
        call_args = mock_whisper.transcribe_timestamped.call_args
        assert call_args[0][1] == test_audio_file

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._load_model")
    def test_perform_transcription_with_language(
        self, mock_load_model, mock_logger, test_cache_dir, test_audio_file, mock_whisper_output
    ):
        """Test transcription with specified language."""
        config = LocalWhisperConfig(language="en")
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=config,
            logger=mock_logger,
        )

        mock_model = MagicMock()
        mock_load_model.return_value = mock_model

        mock_whisper = MagicMock()
        mock_whisper.transcribe_timestamped.return_value = mock_whisper_output
        transcriber._whisper_module = mock_whisper

        transcriber._perform_transcription(test_audio_file)

        # Verify language was passed
        call_kwargs = mock_whisper.transcribe_timestamped.call_args[1]
        assert call_kwargs["language"] == "en"

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._load_model")
    def test_perform_transcription_oom_error(
        self, mock_load_model, transcriber, test_audio_file
    ):
        """Test that OOM errors are handled gracefully."""
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model

        mock_whisper = MagicMock()
        mock_whisper.transcribe_timestamped.side_effect = RuntimeError("CUDA out of memory")
        transcriber._whisper_module = mock_whisper

        with pytest.raises(TranscriptionError, match="out of memory"):
            transcriber._perform_transcription(test_audio_file)


class TestLocalWhisperTranscriberModelLoading:
    """Tests for model loading functionality."""

    @pytest.fixture
    def transcriber(self, mock_logger, test_cache_dir, default_config):
        """Create transcriber instance."""
        return LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=default_config,
            logger=mock_logger,
        )

    def test_lazy_model_loading(self, transcriber):
        """Test that model is not loaded until first use."""
        assert transcriber._model is None
        assert transcriber._whisper_module is None

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._check_dependencies")
    def test_model_caching(self, mock_check, transcriber):
        """Test that model is cached after first load."""
        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model

        with patch.dict("sys.modules", {"whisper_timestamped": mock_whisper}):
            # First load
            model1 = transcriber._load_model()
            # Second load should return cached model
            model2 = transcriber._load_model()

            assert model1 is model2
            # load_model should only be called once
            mock_whisper.load_model.assert_called_once()

    @patch("lyrics_transcriber.transcribers.local_whisper.LocalWhisperTranscriber._check_dependencies")
    def test_load_model_with_custom_cache_dir(self, mock_check, mock_logger, test_cache_dir):
        """Test model loading with custom cache directory."""
        custom_cache = "/custom/whisper/cache"
        config = LocalWhisperConfig(cache_dir=custom_cache)
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=config,
            logger=mock_logger,
        )

        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model

        with patch.dict("sys.modules", {"whisper_timestamped": mock_whisper}):
            transcriber._load_model()

            # Verify custom cache dir was passed
            call_kwargs = mock_whisper.load_model.call_args[1]
            assert call_kwargs["download_root"] == custom_cache


class TestLocalWhisperTranscriberIntegration:
    """Integration tests for full transcription flow."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Clean up test environment."""
        test_cache_dir = tempfile.mkdtemp(prefix="test_local_whisper_integration_")
        os.environ["LYRICS_TRANSCRIBER_CACHE_DIR"] = test_cache_dir
        yield test_cache_dir
        if os.path.exists(test_cache_dir):
            shutil.rmtree(test_cache_dir)
        if "LYRICS_TRANSCRIBER_CACHE_DIR" in os.environ:
            del os.environ["LYRICS_TRANSCRIBER_CACHE_DIR"]

    def test_full_transcription_flow(self, setup_teardown, mock_logger, mock_whisper_output):
        """Test complete transcription flow from audio to TranscriptionData."""
        test_cache_dir = setup_teardown

        # Create test audio file
        audio_path = os.path.join(test_cache_dir, "test.wav")
        with open(audio_path, "wb") as f:
            f.write(b"dummy audio content for testing")

        config = LocalWhisperConfig(model_size="tiny", device="cpu")
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=config,
            logger=mock_logger,
        )

        # Mock the model and transcription
        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model
        mock_whisper.transcribe_timestamped.return_value = mock_whisper_output

        with patch.dict("sys.modules", {"whisper_timestamped": mock_whisper}):
            # Bypass dependency check
            with patch.object(transcriber, "_check_dependencies"):
                result = transcriber.transcribe(audio_path)

        # Verify result
        assert isinstance(result, TranscriptionData)
        assert result.source == "LocalWhisper"
        assert len(result.segments) == 2
        assert len(result.words) == 6

        # Verify caching
        file_hash = transcriber._get_file_hash(audio_path)
        raw_cache_path = transcriber._get_cache_path(file_hash, "raw")
        converted_cache_path = transcriber._get_cache_path(file_hash, "converted")
        assert os.path.exists(raw_cache_path)
        assert os.path.exists(converted_cache_path)

    def test_transcription_uses_cache(self, setup_teardown, mock_logger, mock_whisper_output):
        """Test that subsequent transcriptions use cache."""
        test_cache_dir = setup_teardown

        audio_path = os.path.join(test_cache_dir, "test.wav")
        with open(audio_path, "wb") as f:
            f.write(b"dummy audio content for testing")

        config = LocalWhisperConfig(model_size="tiny", device="cpu")
        transcriber = LocalWhisperTranscriber(
            cache_dir=test_cache_dir,
            config=config,
            logger=mock_logger,
        )

        mock_whisper = MagicMock()
        mock_model = MagicMock()
        mock_whisper.load_model.return_value = mock_model
        mock_whisper.transcribe_timestamped.return_value = mock_whisper_output

        with patch.dict("sys.modules", {"whisper_timestamped": mock_whisper}):
            with patch.object(transcriber, "_check_dependencies"):
                # First transcription
                result1 = transcriber.transcribe(audio_path)

                # Second transcription should use cache
                result2 = transcriber.transcribe(audio_path)

        # Both results should match
        assert result1.text == result2.text
        assert len(result1.segments) == len(result2.segments)

        # transcribe_timestamped should only be called once
        mock_whisper.transcribe_timestamped.assert_called_once()
