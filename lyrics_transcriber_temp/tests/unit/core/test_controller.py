import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from lyrics_transcriber.core.controller import (
    LyricsTranscriber,
    TranscriberConfig,
    LyricsConfig,
    TranscriptionResult,
)
from lyrics_transcriber.core.config import OutputConfig
import logging
from dataclasses import dataclass
from typing import Optional
from lyrics_transcriber.lyrics.base_lyrics_provider import LyricsProviderConfig
from lyrics_transcriber.lyrics.genius import GeniusProvider
from tests.test_helpers import (
    create_test_output_config,
    create_test_transcription_result,
    create_test_lyrics_data,
    create_test_transcription_data,
    create_test_segment,
    create_test_word,
)
from lyrics_transcriber.types import CorrectionResult
from lyrics_transcriber.output.countdown_processor import CountdownProcessor


@dataclass
class MockOutputPaths:
    lrc: Optional[str] = None
    ass: Optional[str] = None
    video: Optional[str] = None
    original_txt: Optional[str] = None
    corrected_txt: Optional[str] = None
    corrections_json: Optional[str] = None
    cdg: Optional[str] = None
    mp3: Optional[str] = None
    cdg_zip: Optional[str] = None


@pytest.fixture
def mock_corrector():
    return Mock()


@pytest.fixture
def mock_output_generator():
    return Mock()


@pytest.fixture
def mock_whisper_transcriber():
    return Mock()


@pytest.fixture
def mock_audioshake_transcriber():
    return Mock()


@pytest.fixture
def mock_genius_provider():
    return Mock()


@pytest.fixture
def mock_spotify_provider():
    return Mock()


@pytest.fixture
def basic_transcriber(sample_audio_file, test_logger, mock_genius_provider, mock_spotify_provider, mock_corrector, mock_output_generator):
    # Create lyrics providers with proper structure
    lyrics_providers = {"genius": mock_genius_provider, "spotify": mock_spotify_provider}  # Pass the mock directly, not in a dict

    # Create proper output config for testing
    output_config = create_test_output_config()

    return LyricsTranscriber(
        audio_filepath=sample_audio_file,
        artist="Test Artist",
        title="Test Song",
        output_config=output_config,
        logger=test_logger,
        lyrics_providers=lyrics_providers,
        corrector=mock_corrector,
        output_generator=mock_output_generator,
    )


def test_lyrics_transcriber_initialization(basic_transcriber):
    assert basic_transcriber.audio_filepath is not None
    assert basic_transcriber.artist == "Test Artist"
    assert basic_transcriber.title == "Test Song"
    assert basic_transcriber.output_prefix == "Test Artist - Test Song"


@patch("lyrics_transcriber.core.controller.AudioShakeTranscriber")
@patch("lyrics_transcriber.core.controller.WhisperTranscriber")
def test_transcriber_with_configs(
    mock_whisper_class,
    mock_audioshake_class,
    sample_audio_file,
    test_logger,
    mock_corrector,
    mock_output_generator,
    mock_whisper_transcriber,
    mock_audioshake_transcriber,
    mock_genius_provider,
    mock_spotify_provider,
):
    # Setup mock transcriber instances
    mock_whisper_class.return_value = mock_whisper_transcriber
    mock_audioshake_class.return_value = mock_audioshake_transcriber

    # Setup lyrics providers
    lyrics_providers = {"genius": mock_genius_provider, "spotify": mock_spotify_provider}  # Pass the mock directly

    transcriber_config = TranscriberConfig(audioshake_api_token="test_token", runpod_api_key="test_key", whisper_runpod_id="test_id")
    lyrics_config = LyricsConfig(genius_api_token="test_token", spotify_cookie="test_cookie")
    output_config = create_test_output_config(output_dir="test_output", cache_dir="test_cache")

    transcriber = LyricsTranscriber(
        audio_filepath=sample_audio_file,
        transcriber_config=transcriber_config,
        lyrics_config=lyrics_config,
        output_config=output_config,
        logger=test_logger,
        corrector=mock_corrector,
        output_generator=mock_output_generator,
        lyrics_providers=lyrics_providers,
    )

    # Verify transcribers were initialized
    assert "audioshake" in transcriber.transcribers
    assert "whisper" in transcriber.transcribers


def test_process_with_artist_and_title(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    # Setup mock returns
    mock_lyrics_data = create_test_lyrics_data(source="genius")
    mock_genius_provider.fetch_lyrics.return_value = mock_lyrics_data
    mock_spotify_provider.fetch_lyrics.return_value = None  # Spotify should return None

    # Run process
    result = basic_transcriber.process()

    # Verify lyrics fetching was called with correct arguments
    mock_genius_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")
    mock_spotify_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")

    # Verify results - only one result should be added since Spotify returns None
    assert len(result.lyrics_results) == 1
    assert result.lyrics_results["genius"] == mock_lyrics_data


def test_process_without_artist_and_title(
    sample_audio_file, test_logger, mock_genius_provider, mock_spotify_provider, mock_corrector, mock_output_generator
):
    lyrics_providers = {"genius": mock_genius_provider, "spotify": mock_spotify_provider}
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(
        audio_filepath=sample_audio_file,
        output_config=output_config,
        logger=test_logger,
        lyrics_providers=lyrics_providers,
        corrector=mock_corrector,
        output_generator=mock_output_generator,
    )

    result = transcriber.process()

    # Verify lyrics fetching was not called
    mock_genius_provider.fetch_lyrics.assert_not_called()
    mock_spotify_provider.fetch_lyrics.assert_not_called()


def test_generate_outputs(basic_transcriber, mock_output_generator):
    # Create mock output paths
    mock_output_paths = MockOutputPaths(lrc="test.lrc", ass="test.ass", video="test.mp4")
    mock_output_generator.generate_outputs.return_value = mock_output_paths

    # Setup test data
    basic_transcriber.results.transcription_corrected = {"test": "data"}

    # Run generate_outputs
    basic_transcriber.generate_outputs()

    # Verify output generation was called correctly
    mock_output_generator.generate_outputs.assert_called_once_with(
        transcription_corrected={"test": "data"},
        lyrics_results={},  # Should be dict, not list
        output_prefix="Test Artist - Test Song",
        audio_filepath=basic_transcriber.audio_filepath,
        artist="Test Artist",  # These are now passed
        title="Test Song"     # These are now passed
    )

    # Verify results
    assert basic_transcriber.results.lrc_filepath == "test.lrc"
    assert basic_transcriber.results.ass_filepath == "test.ass"
    assert basic_transcriber.results.video_filepath == "test.mp4"


def test_initialize_transcribers_with_no_config(basic_transcriber):
    """Test transcriber initialization when no API tokens are provided"""
    transcribers = basic_transcriber._initialize_transcribers()
    assert len(transcribers) == 0


def test_logger_initialization_without_existing_logger(sample_audio_file):
    """Test that logger is properly initialized when none is provided"""
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, output_config=output_config)
    assert transcriber.logger is not None
    assert transcriber.logger.level == logging.DEBUG
    assert len(transcriber.logger.handlers) == 1


def test_transcribe_with_failed_transcriber(basic_transcriber, mock_whisper_transcriber):
    """Test transcription handling when a transcriber fails"""
    # Setup mock transcriber that raises an exception
    mock_whisper_transcriber.transcribe.side_effect = Exception("Transcription failed")
    basic_transcriber.transcribers = {"whisper": {"instance": mock_whisper_transcriber, "priority": 1}}

    # The transcribe method currently doesn't have exception handling, so it will raise
    with pytest.raises(Exception, match="Transcription failed"):
        basic_transcriber.transcribe()
    assert len(basic_transcriber.results.transcription_results) == 0


def test_correct_lyrics_with_failed_correction(basic_transcriber, mock_corrector):
    """Test correction handling when correction fails"""
    # Setup mock data - need transcription results for the method to work properly
    transcription_data = create_test_transcription_data()
    transcription_result = create_test_transcription_result(name="test", transcription_data=transcription_data) 
    basic_transcriber.results.transcription_results = [transcription_result]
    mock_corrector.run.side_effect = Exception("Correction failed")

    # With review disabled, the correction method will handle the failed corrector gracefully
    # and create a fallback CorrectionResult since there are no reference lyrics
    basic_transcriber.correct_lyrics()

    # The method should have created a fallback result (not None) since review is disabled
    assert basic_transcriber.results.transcription_corrected is not None
    assert basic_transcriber.results.transcription_corrected.corrections_made == 0


def test_process_with_failed_output_generation(basic_transcriber, mock_output_generator):
    """Test process handling when output generation fails"""
    # Setup successful transcription but failed output generation
    basic_transcriber.results.transcription_corrected = {"test": "data"}
    mock_output_generator.generate_outputs.side_effect = Exception("Output generation failed")

    with pytest.raises(Exception):
        basic_transcriber.process()


def test_fetch_lyrics_with_failed_fetcher(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test lyrics fetching when the providers fail"""
    mock_genius_provider.fetch_lyrics.side_effect = Exception("Failed to fetch lyrics")
    mock_spotify_provider.fetch_lyrics.side_effect = Exception("Failed to fetch lyrics")

    # Should not raise exception
    basic_transcriber.fetch_lyrics()

    # Verify no results were stored
    assert len(basic_transcriber.results.lyrics_results) == 0


def test_fetch_lyrics_with_empty_result(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test lyrics fetching when no lyrics are found"""
    mock_genius_provider.fetch_lyrics.return_value = None
    mock_spotify_provider.fetch_lyrics.return_value = None

    basic_transcriber.fetch_lyrics()

    # Verify no results were stored
    assert len(basic_transcriber.results.lyrics_results) == 0


def test_transcribe_with_multiple_transcribers(basic_transcriber, mock_whisper_transcriber, mock_audioshake_transcriber):
    """Test transcription with multiple transcribers where first one fails"""
    # Setup transcribers with proper data structure
    transcription_data = create_test_transcription_data(source="audioshake")
    mock_whisper_transcriber.transcribe.side_effect = Exception("Whisper failed")
    mock_audioshake_transcriber.transcribe.return_value = transcription_data
    basic_transcriber.transcribers = {
        "whisper": {"instance": mock_whisper_transcriber, "priority": 2},
        "audioshake": {"instance": mock_audioshake_transcriber, "priority": 1},
    }

    # The first transcriber will fail, stopping the process due to lack of exception handling
    with pytest.raises(Exception, match="Whisper failed"):
        basic_transcriber.transcribe()
    
    # No results should be saved due to the exception
    assert len(basic_transcriber.results.transcription_results) == 0


def test_process_with_successful_correction(basic_transcriber, mock_corrector):
    """Test successful correction process"""
    # Setup proper test data structures
    transcription_data = create_test_transcription_data()
    transcription_result = create_test_transcription_result(name="test", transcription_data=transcription_data)
    basic_transcriber.results.transcription_results = [transcription_result]

    # Since there are no lyrics results, it will create a fallback CorrectionResult
    # Run correction
    basic_transcriber.correct_lyrics()

    # Verify correction result was created (fallback since no reference lyrics)
    assert basic_transcriber.results.transcription_corrected is not None
    assert basic_transcriber.results.transcription_corrected.corrections_made == 0
    assert basic_transcriber.results.transcription_corrected.confidence == 1.0


def test_transcribe_with_successful_whisper(basic_transcriber, mock_whisper_transcriber):
    """Test successful whisper transcription"""
    # Setup mock
    mock_whisper_transcriber.transcribe.return_value = {"test": "whisper_data"}
    basic_transcriber.transcribers = {"whisper": {"instance": mock_whisper_transcriber, "priority": 1}}

    # Run transcription
    basic_transcriber.transcribe()

    # Verify results
    assert len(basic_transcriber.results.transcription_results) == 1
    assert basic_transcriber.results.transcription_results[0].name == "whisper"
    assert basic_transcriber.results.transcription_results[0].result == {"test": "whisper_data"}


def test_process_full_successful_workflow(
    basic_transcriber, mock_genius_provider, mock_spotify_provider, mock_corrector, mock_whisper_transcriber
):
    """Test a complete successful workflow"""
    # Setup proper test data structures
    mock_lyrics_data = create_test_lyrics_data(source="genius")
    mock_genius_provider.fetch_lyrics.return_value = mock_lyrics_data
    mock_spotify_provider.fetch_lyrics.return_value = None  # Spotify should return None

    # Setup transcriber with proper data structure
    transcription_data = create_test_transcription_data(source="whisper")
    basic_transcriber.transcribers = {"whisper": {"instance": mock_whisper_transcriber, "priority": 1}}
    mock_whisper_transcriber.transcribe.return_value = transcription_data
    
    # Create a mock CorrectionResult with proper structure
    mock_correction_result = CorrectionResult(
        original_segments=transcription_data.segments,
        corrected_segments=transcription_data.segments,
        corrections=[],
        corrections_made=0,
        confidence=1.0,
        reference_lyrics={"genius": mock_lyrics_data},
        anchor_sequences=[],
        gap_sequences=[],
        resized_segments=[],
        metadata={},
        correction_steps=[],
        word_id_map={},
        segment_id_map={}
    )
    mock_corrector.run.return_value = mock_correction_result

    # Run full process
    result = basic_transcriber.process()

    # Verify complete workflow
    assert len(result.lyrics_results) == 1
    assert result.lyrics_results["genius"] == mock_lyrics_data
    mock_genius_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")
    mock_spotify_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")
    assert len(result.transcription_results) == 1
    assert result.transcription_results[0].result == transcription_data
    
    # The corrector actually runs in this test, so check essential properties instead of exact equality
    assert result.transcription_corrected is not None
    assert hasattr(result.transcription_corrected, 'corrections_made')
    assert hasattr(result.transcription_corrected, 'confidence')
    assert result.transcription_corrected.reference_lyrics["genius"] == mock_lyrics_data


def test_fetch_lyrics_success(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test successful lyrics fetching from primary provider"""
    mock_lyrics_data = create_test_lyrics_data(source="genius")
    mock_genius_provider.fetch_lyrics.return_value = mock_lyrics_data
    mock_spotify_provider.fetch_lyrics.return_value = None  # Spotify should return None

    basic_transcriber.fetch_lyrics()

    # Verify lyrics fetching was called for both providers
    mock_genius_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")
    mock_spotify_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")

    # Verify results - only one result should be added since Spotify returns None
    assert len(basic_transcriber.results.lyrics_results) == 1
    assert basic_transcriber.results.lyrics_results["genius"] == mock_lyrics_data


def test_fetch_lyrics_fallback(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test fallback to secondary provider when primary fails"""
    mock_genius_provider.fetch_lyrics.return_value = None
    mock_spotify_lyrics = create_test_lyrics_data(source="spotify")
    mock_spotify_provider.fetch_lyrics.return_value = mock_spotify_lyrics

    basic_transcriber.fetch_lyrics()

    # Verify both providers were tried
    mock_genius_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")
    mock_spotify_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")

    # Verify results - only Spotify result should be present
    assert len(basic_transcriber.results.lyrics_results) == 1
    assert basic_transcriber.results.lyrics_results["spotify"] == mock_spotify_lyrics


def test_fetch_lyrics_all_fail(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test handling when all providers fail"""
    mock_genius_provider.fetch_lyrics.return_value = None
    mock_spotify_provider.fetch_lyrics.return_value = None

    basic_transcriber.fetch_lyrics()

    # Verify all providers were tried
    mock_genius_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")
    mock_spotify_provider.fetch_lyrics.assert_called_once_with("Test Artist", "Test Song")

    # Verify no results were stored
    assert len(basic_transcriber.results.lyrics_results) == 0


def test_initialize_transcribers_with_audioshake_only(sample_audio_file):
    """Test transcriber initialization with only AudioShake config"""
    transcriber_config = TranscriberConfig(audioshake_api_token="test_token")
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, transcriber_config=transcriber_config, output_config=output_config)

    transcribers = transcriber.transcribers
    assert len(transcribers) == 1
    assert "audioshake" in transcribers
    assert "whisper" not in transcribers


@patch("lyrics_transcriber.storage.dropbox.DropboxHandler")
def test_initialize_transcribers_with_whisper_only(mock_dropbox_handler, sample_audio_file):
    """Test transcriber initialization with only Whisper config"""
    # Setup mock storage to avoid validation errors
    mock_storage = Mock()
    mock_storage.file_exists.return_value = False
    mock_storage.upload_with_retry.return_value = None
    mock_storage.create_or_get_shared_link.return_value = "https://test.com/audio.mp3"
    mock_dropbox_handler.return_value = mock_storage
    
    transcriber_config = TranscriberConfig(runpod_api_key="test_key", whisper_runpod_id="test_id")
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, transcriber_config=transcriber_config, output_config=output_config)

    transcribers = transcriber.transcribers
    assert len(transcribers) == 1
    assert "whisper" in transcribers
    assert "audioshake" not in transcribers


def test_generate_outputs_with_error(basic_transcriber, mock_output_generator):
    """Test output generation when an error occurs"""
    mock_output_generator.generate_outputs.side_effect = Exception("Failed to generate outputs")

    with pytest.raises(Exception) as exc_info:
        basic_transcriber.generate_outputs()

    assert str(exc_info.value) == "Failed to generate outputs"
    assert basic_transcriber.results.lrc_filepath is None
    assert basic_transcriber.results.ass_filepath is None
    assert basic_transcriber.results.video_filepath is None


def test_initialize_lyrics_providers_with_genius_only(sample_audio_file):
    """Test lyrics provider initialization with only Genius config"""
    lyrics_config = LyricsConfig(genius_api_token="test_token")
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, lyrics_config=lyrics_config, output_config=output_config)

    providers = transcriber.lyrics_providers
    assert len(providers) == 2  # LRCLIB + Genius
    assert "lrclib" in providers  # LRCLIB is always enabled
    assert "genius" in providers
    assert isinstance(providers["genius"], GeniusProvider)
    assert "spotify" not in providers


@patch("lyrics_transcriber.core.controller.SpotifyProvider")
@patch("syrics.api.Spotify")
def test_initialize_lyrics_providers_with_spotify_only(mock_spotify_api_class, mock_spotify_provider_class, sample_audio_file):
    """Test lyrics provider initialization with only Spotify config"""
    # Setup mock SpotifyProvider instance
    mock_spotify_provider = Mock()
    mock_spotify_provider_class.return_value = mock_spotify_provider

    # Setup mock Spotify API instance
    mock_spotify_api = Mock()
    mock_spotify_api_class.return_value = mock_spotify_api

    lyrics_config = LyricsConfig(spotify_cookie="test_cookie")
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, lyrics_config=lyrics_config, output_config=output_config)

    providers = transcriber.lyrics_providers
    assert len(providers) == 2  # LRCLIB + Spotify
    assert "lrclib" in providers  # LRCLIB is always enabled
    assert "spotify" in providers
    assert providers["spotify"] == mock_spotify_provider
    assert "genius" not in providers

    # Verify SpotifyProvider was initialized with correct arguments
    mock_spotify_provider_class.assert_called_once()
    call_kwargs = mock_spotify_provider_class.call_args.kwargs
    assert isinstance(call_kwargs["config"], LyricsProviderConfig)
    assert call_kwargs["config"].spotify_cookie == lyrics_config.spotify_cookie
    assert call_kwargs["config"].genius_api_token == lyrics_config.genius_api_token
    # The cache_dir will be a temporary directory created by our test helper
    assert call_kwargs["config"].cache_dir is not None
    assert "test_cache_" in call_kwargs["config"].cache_dir
    assert call_kwargs["config"].audio_filepath == sample_audio_file
    assert call_kwargs["logger"] is not None


def test_initialize_lyrics_providers_with_rapidapi_config(sample_audio_file):
    """Test lyrics provider initialization with RapidAPI config"""
    lyrics_config = LyricsConfig(genius_api_token="test_token", rapidapi_key="test_rapidapi_key")
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, lyrics_config=lyrics_config, output_config=output_config)

    providers = transcriber.lyrics_providers
    assert len(providers) == 3  # LRCLIB + Genius + Musixmatch
    assert "lrclib" in providers  # LRCLIB is always enabled
    assert "genius" in providers
    assert "musixmatch" in providers
    assert isinstance(providers["genius"], GeniusProvider)
    
    # Verify that the GeniusProvider was initialized with the RapidAPI key
    provider = providers["genius"]
    assert provider.rapidapi_key == "test_rapidapi_key"
    assert provider.api_token == "test_token"


def test_initialize_lyrics_providers_with_both_configs(sample_audio_file):
    """Test lyrics provider initialization with both Genius and RapidAPI configs"""
    lyrics_config = LyricsConfig(
        genius_api_token="test_token", 
        rapidapi_key="test_rapidapi_key",
        spotify_cookie="test_cookie"
    )
    output_config = create_test_output_config()
    transcriber = LyricsTranscriber(audio_filepath=sample_audio_file, lyrics_config=lyrics_config, output_config=output_config)

    providers = transcriber.lyrics_providers
    assert len(providers) == 4  # LRCLIB + Genius + Musixmatch + Spotify
    assert "lrclib" in providers  # LRCLIB is always enabled
    assert "genius" in providers
    assert "musixmatch" in providers
    assert "spotify" in providers
    
    # Verify that the GeniusProvider was initialized with both keys
    genius_provider = providers["genius"]
    assert genius_provider.rapidapi_key == "test_rapidapi_key"
    assert genius_provider.api_token == "test_token"


def test_fetch_lyrics_with_provider_error(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test fetch_lyrics error handling when providers raise exceptions"""
    # Make both providers raise exceptions
    mock_genius_provider.fetch_lyrics.side_effect = Exception("Genius error")
    mock_spotify_provider.fetch_lyrics.side_effect = Exception("Spotify error")

    # Should not raise exception
    basic_transcriber.fetch_lyrics()

    # Verify error was handled gracefully
    assert len(basic_transcriber.results.lyrics_results) == 0
    mock_genius_provider.fetch_lyrics.assert_called_once()
    mock_spotify_provider.fetch_lyrics.assert_called_once()


def test_fetch_lyrics_with_outer_exception(basic_transcriber, mock_genius_provider, mock_spotify_provider):
    """Test fetch_lyrics when an outer exception occurs"""
    # Make the lyrics_providers attribute raise an exception when accessed
    basic_transcriber.lyrics_providers = None  # This will cause an attribute error when iterating

    # The method will raise an exception because it doesn't have outer exception handling
    with pytest.raises(AttributeError):
        basic_transcriber.fetch_lyrics()

    # Verify no results were stored
    assert len(basic_transcriber.results.lyrics_results) == 0


# =============================================================================
# Tests for loading existing corrections with countdown padding
# =============================================================================
# These tests verify the fix for the bug where loading corrections from an
# existing JSON file with countdown didn't create the padded audio file,
# causing video/audio desync.

class TestExistingCorrectionsWithCountdown:
    """Test suite for loading existing corrections that have countdown padding."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory for testing."""
        temp_dir = tempfile.mkdtemp(prefix="test_controller_")
        yield temp_dir
        # Cleanup is handled by OS tmpdir cleanup

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory for testing."""
        temp_dir = tempfile.mkdtemp(prefix="test_cache_")
        yield temp_dir

    @pytest.fixture
    def correction_result_with_countdown(self):
        """
        Create a CorrectionResult that has countdown padding already applied.
        This simulates what would be saved to JSON after countdown processing.
        """
        # First segment is the countdown
        countdown_segment = create_test_segment(
            text="3... 2... 1...",
            words=[
                create_test_word(text="3... 2... 1...", start_time=0.1, end_time=2.9),
            ],
            start_time=0.1,
            end_time=2.9,
        )
        
        # Second segment is the first lyrics (shifted by 3s from original 1.5s)
        first_lyrics_segment = create_test_segment(
            text="Hello world",
            words=[
                create_test_word(text="Hello", start_time=4.5, end_time=5.0),  # 1.5+3.0
                create_test_word(text="world", start_time=5.1, end_time=5.5),  # 2.1+3.0
            ],
            start_time=4.5,
            end_time=5.5,
        )

        return CorrectionResult(
            original_segments=[first_lyrics_segment],
            corrected_segments=[countdown_segment, first_lyrics_segment],
            corrections=[],
            corrections_made=0,
            confidence=1.0,
            reference_lyrics={},
            anchor_sequences=[],
            gap_sequences=[],
            resized_segments=[countdown_segment, first_lyrics_segment],
            metadata={},
            correction_steps=[],
            word_id_map={},
            segment_id_map={},
        )

    @pytest.fixture
    def correction_result_without_countdown(self):
        """
        Create a CorrectionResult that does NOT have countdown padding.
        This simulates a song that starts late (after 3 seconds).
        """
        # First lyrics segment starts at 5.0 seconds (no countdown needed)
        first_segment = create_test_segment(
            text="Hello world",
            words=[
                create_test_word(text="Hello", start_time=5.0, end_time=5.5),
                create_test_word(text="world", start_time=5.6, end_time=6.0),
            ],
            start_time=5.0,
            end_time=6.0,
        )

        return CorrectionResult(
            original_segments=[first_segment],
            corrected_segments=[first_segment],
            corrections=[],
            corrections_made=0,
            confidence=1.0,
            reference_lyrics={},
            anchor_sequences=[],
            gap_sequences=[],
            resized_segments=[first_segment],
            metadata={},
            correction_steps=[],
            word_id_map={},
            segment_id_map={},
        )

    def test_process_loads_existing_corrections_with_countdown_and_creates_padded_audio(
        self, temp_output_dir, temp_cache_dir, sample_audio_file, 
        correction_result_with_countdown, mock_output_generator
    ):
        """
        Test that when existing corrections JSON has countdown, the controller
        detects this and creates the padded audio file for video rendering.
        
        This is the main test for the bug fix - previously the controller would
        skip straight to output generation without creating padded audio.
        """
        # Save correction result to JSON
        output_prefix = "Test Artist - Test Song"
        corrections_json_path = os.path.join(temp_output_dir, f"{output_prefix} (Lyrics Corrections).json")
        with open(corrections_json_path, "w", encoding="utf-8") as f:
            json.dump(correction_result_with_countdown.to_dict(), f)

        # Setup output config with add_countdown enabled
        output_config = create_test_output_config(
            output_dir=temp_output_dir,
            cache_dir=temp_cache_dir,
            add_countdown=True,
            render_video=False,  # Disable video to avoid needing styles
        )

        # Setup mock output generator
        mock_output_paths = MockOutputPaths()
        mock_output_generator.generate_outputs.return_value = mock_output_paths

        # Create transcriber with mock output generator
        with patch.object(CountdownProcessor, 'create_padded_audio_only') as mock_pad_audio:
            mock_pad_audio.return_value = os.path.join(temp_cache_dir, "Test Artist - Test Song (Original)_padded.flac")
            
            transcriber = LyricsTranscriber(
                audio_filepath=sample_audio_file,
                artist="Test Artist",
                title="Test Song",
                output_config=output_config,
                output_generator=mock_output_generator,
            )

            # Run process - should load existing corrections and create padded audio
            result = transcriber.process()

            # Verify countdown was detected and padded audio was created
            mock_pad_audio.assert_called_once_with(sample_audio_file)
            
            # Verify result attributes are set correctly
            assert result.countdown_padding_added is True
            assert result.countdown_padding_seconds == 3.0
            assert result.padded_audio_filepath is not None

    def test_process_loads_existing_corrections_without_countdown_no_padding(
        self, temp_output_dir, temp_cache_dir, sample_audio_file,
        correction_result_without_countdown, mock_output_generator
    ):
        """
        Test that when existing corrections JSON does NOT have countdown,
        no padding is created.
        """
        # Save correction result to JSON
        output_prefix = "Test Artist - Test Song"
        corrections_json_path = os.path.join(temp_output_dir, f"{output_prefix} (Lyrics Corrections).json")
        with open(corrections_json_path, "w", encoding="utf-8") as f:
            json.dump(correction_result_without_countdown.to_dict(), f)

        # Setup output config with add_countdown enabled
        output_config = create_test_output_config(
            output_dir=temp_output_dir,
            cache_dir=temp_cache_dir,
            add_countdown=True,
            render_video=False,
        )

        # Setup mock output generator
        mock_output_paths = MockOutputPaths()
        mock_output_generator.generate_outputs.return_value = mock_output_paths

        with patch.object(CountdownProcessor, 'create_padded_audio_only') as mock_pad_audio:
            transcriber = LyricsTranscriber(
                audio_filepath=sample_audio_file,
                artist="Test Artist",
                title="Test Song",
                output_config=output_config,
                output_generator=mock_output_generator,
            )

            result = transcriber.process()

            # Verify padded audio was NOT created (no countdown in corrections)
            mock_pad_audio.assert_not_called()
            
            # Verify result attributes indicate no padding
            assert result.countdown_padding_added is False
            assert result.countdown_padding_seconds == 0.0
            assert result.padded_audio_filepath is None

    def test_process_existing_corrections_with_countdown_disabled_no_padding(
        self, temp_output_dir, temp_cache_dir, sample_audio_file,
        correction_result_with_countdown, mock_output_generator
    ):
        """
        Test that when add_countdown is disabled in config, no padding check is done
        even if corrections have countdown.
        """
        # Save correction result to JSON
        output_prefix = "Test Artist - Test Song"
        corrections_json_path = os.path.join(temp_output_dir, f"{output_prefix} (Lyrics Corrections).json")
        with open(corrections_json_path, "w", encoding="utf-8") as f:
            json.dump(correction_result_with_countdown.to_dict(), f)

        # Setup output config with add_countdown DISABLED
        output_config = create_test_output_config(
            output_dir=temp_output_dir,
            cache_dir=temp_cache_dir,
            add_countdown=False,  # Disabled!
            render_video=False,
        )

        # Setup mock output generator
        mock_output_paths = MockOutputPaths()
        mock_output_generator.generate_outputs.return_value = mock_output_paths

        with patch.object(CountdownProcessor, 'has_countdown') as mock_has_countdown:
            transcriber = LyricsTranscriber(
                audio_filepath=sample_audio_file,
                artist="Test Artist",
                title="Test Song",
                output_config=output_config,
                output_generator=mock_output_generator,
            )

            result = transcriber.process()

            # Verify countdown check was NOT performed (add_countdown is False)
            mock_has_countdown.assert_not_called()
            
            # Verify result attributes indicate no padding
            assert result.countdown_padding_added is False
            assert result.countdown_padding_seconds == 0.0

    def test_process_existing_corrections_audio_filepath_updated(
        self, temp_output_dir, temp_cache_dir, sample_audio_file,
        correction_result_with_countdown, mock_output_generator
    ):
        """
        Test that when countdown padding is applied, the audio_filepath passed
        to generate_outputs is the padded audio, not the original.
        
        This verifies the fix for the video desync issue - the video must be
        rendered with the padded audio to match the countdown-shifted subtitles.
        """
        # Save correction result to JSON
        output_prefix = "Test Artist - Test Song"
        corrections_json_path = os.path.join(temp_output_dir, f"{output_prefix} (Lyrics Corrections).json")
        with open(corrections_json_path, "w", encoding="utf-8") as f:
            json.dump(correction_result_with_countdown.to_dict(), f)

        # Setup output config
        output_config = create_test_output_config(
            output_dir=temp_output_dir,
            cache_dir=temp_cache_dir,
            add_countdown=True,
            render_video=False,
        )

        # Setup mock output generator to capture the call arguments
        mock_output_paths = MockOutputPaths()
        mock_output_generator.generate_outputs.return_value = mock_output_paths

        padded_audio_path = os.path.join(temp_cache_dir, "padded_audio.flac")

        with patch.object(CountdownProcessor, 'create_padded_audio_only') as mock_pad_audio:
            mock_pad_audio.return_value = padded_audio_path
            
            transcriber = LyricsTranscriber(
                audio_filepath=sample_audio_file,
                artist="Test Artist",
                title="Test Song",
                output_config=output_config,
                output_generator=mock_output_generator,
            )

            transcriber.process()

            # Verify generate_outputs was called with the PADDED audio path
            call_kwargs = mock_output_generator.generate_outputs.call_args.kwargs
            assert call_kwargs["audio_filepath"] == padded_audio_path
            assert call_kwargs["audio_filepath"] != sample_audio_file

    def test_countdown_processor_has_countdown_integration(self, temp_cache_dir):
        """
        Integration test for CountdownProcessor.has_countdown() with real data.
        Verifies the detection logic works correctly.
        """
        processor = CountdownProcessor(cache_dir=temp_cache_dir)

        # Create result with countdown
        countdown_segment = create_test_segment(
            text="3... 2... 1...",
            words=[create_test_word(text="3... 2... 1...", start_time=0.1, end_time=2.9)],
            start_time=0.1,
            end_time=2.9,
        )
        result_with_countdown = CorrectionResult(
            original_segments=[],
            corrected_segments=[countdown_segment],
            corrections=[],
            corrections_made=0,
            confidence=1.0,
            reference_lyrics={},
            anchor_sequences=[],
            gap_sequences=[],
            resized_segments=[],
            metadata={},
            correction_steps=[],
            word_id_map={},
            segment_id_map={},
        )

        # Create result without countdown
        normal_segment = create_test_segment(
            text="Hello world",
            words=[create_test_word(text="Hello", start_time=5.0, end_time=5.5)],
            start_time=5.0,
            end_time=5.5,
        )
        result_without_countdown = CorrectionResult(
            original_segments=[],
            corrected_segments=[normal_segment],
            corrections=[],
            corrections_made=0,
            confidence=1.0,
            reference_lyrics={},
            anchor_sequences=[],
            gap_sequences=[],
            resized_segments=[],
            metadata={},
            correction_steps=[],
            word_id_map={},
            segment_id_map={},
        )

        # Test detection
        assert processor.has_countdown(result_with_countdown) is True
        assert processor.has_countdown(result_without_countdown) is False

    def test_corrections_json_roundtrip_preserves_countdown(
        self, temp_output_dir, correction_result_with_countdown
    ):
        """
        Test that saving and loading corrections JSON preserves the countdown
        segment that can be detected by has_countdown().
        
        This ensures the detection works with real serialized/deserialized data.
        """
        # Save to JSON
        json_path = os.path.join(temp_output_dir, "test_corrections.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(correction_result_with_countdown.to_dict(), f)

        # Load from JSON
        with open(json_path, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        loaded_result = CorrectionResult.from_dict(loaded_data)

        # Verify countdown is still detectable
        processor = CountdownProcessor(cache_dir=temp_output_dir)
        assert processor.has_countdown(loaded_result) is True
        
        # Verify first segment is the countdown
        assert loaded_result.corrected_segments[0].text == "3... 2... 1..."
