"""
Unit tests for audio_fetcher module.

Tests cover the AudioFetcher abstraction layer and FlacFetchAudioFetcher implementation.
"""

import pytest
import os
import tempfile
import logging
from unittest.mock import MagicMock, patch, PropertyMock

from karaoke_gen.audio_fetcher import (
    AudioSearchResult,
    AudioFetchResult,
    AudioFetcher,
    AudioFetcherError,
    NoResultsError,
    DownloadError,
    UserCancelledError,
    FlacFetchAudioFetcher,
    create_audio_fetcher,
)
import karaoke_gen.audio_fetcher as audio_fetcher_module

# Import flacfetch models for creating test Release objects
from flacfetch.core.models import Release, Quality, AudioFormat, MediaSource


def create_test_release(
    title: str = "Test Song",
    artist: str = "Test Artist",
    source_name: str = "YouTube",
    duration_seconds: int = 180,
    seeders: int = None,
    is_lossless: bool = False,
) -> Release:
    """Create a real Release object for testing.
    
    This is needed because flacfetch's print_releases function does
    type comparisons that fail with MagicMock objects.
    """
    if is_lossless:
        quality = Quality(format=AudioFormat.FLAC, bit_depth=16, media=MediaSource.CD)
    else:
        quality = Quality(format=AudioFormat.MP3, bitrate=320, media=MediaSource.WEB)
    
    return Release(
        title=title,
        artist=artist,
        quality=quality,
        source_name=source_name,
        duration_seconds=duration_seconds,
        seeders=seeders,
    )


class TestAudioSearchResult:
    """Tests for AudioSearchResult dataclass."""

    def test_basic_creation(self):
        """Test creating an AudioSearchResult with required fields."""
        result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="YouTube",
        )
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.url == "https://example.com/song"
        assert result.provider == "YouTube"
        assert result.duration is None
        assert result.quality is None
        assert result.source_id is None
        assert result.index == 0  # Default index
        assert result.raw_result is None

    def test_full_creation(self):
        """Test creating an AudioSearchResult with all fields."""
        raw = {"some": "data"}
        result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="Redacted",
            duration=240,
            quality="FLAC",
            source_id="123456",
            index=5,
            raw_result=raw,
        )
        assert result.duration == 240
        assert result.quality == "FLAC"
        assert result.source_id == "123456"
        assert result.index == 5
        assert result.raw_result == raw

    def test_to_dict_basic(self):
        """Test to_dict with minimal fields."""
        result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="YouTube",
        )
        data = result.to_dict()
        
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"
        assert data["url"] == "https://example.com/song"
        assert data["provider"] == "YouTube"
        assert data["duration"] is None
        assert data["quality"] is None
        assert data["source_id"] is None
        assert data["index"] == 0
        # raw_result should NOT be in serialized dict
        assert "raw_result" not in data

    def test_to_dict_full(self):
        """Test to_dict with all fields populated."""
        raw = {"some": "data"}
        result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="Redacted",
            duration=240,
            quality="FLAC 24bit",
            source_id="abc123",
            index=3,
            raw_result=raw,
        )
        data = result.to_dict()
        
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"
        assert data["url"] == "https://example.com/song"
        assert data["provider"] == "Redacted"
        assert data["duration"] == 240
        assert data["quality"] == "FLAC 24bit"
        assert data["source_id"] == "abc123"
        assert data["index"] == 3
        # raw_result should NOT be in serialized dict
        assert "raw_result" not in data

    def test_to_dict_with_release_raw_result(self):
        """Test to_dict when raw_result has to_dict() that returns release fields."""
        # Create a mock raw_result that mimics flacfetch Release behavior
        class MockRelease:
            def to_dict(self):
                return {
                    'year': 2024,
                    'label': 'Test Records',
                    'edition_info': 'Remastered',
                    'release_type': 'Album',
                    'channel': 'TestChannel',
                    'view_count': 1000000,
                    'size_bytes': 52428800,
                    'target_file_size': 26214400,
                    'track_pattern': 'Test Song',
                    'match_score': 0.95,
                    'formatted_size': '50.0 MB',
                    'formatted_duration': '3:30',
                    'formatted_views': '1.0M',
                    'is_lossless': True,
                    'quality_str': 'FLAC 24bit WEB',
                    'quality': {'format': 'FLAC', 'bit_depth': 24, 'media': 'WEB'},
                }
        
        result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="Redacted",
            raw_result=MockRelease(),
        )
        data = result.to_dict()
        
        # Basic fields
        assert data["title"] == "Test Song"
        assert data["provider"] == "Redacted"
        
        # Release-specific fields should be included
        assert data["year"] == 2024
        assert data["label"] == "Test Records"
        assert data["edition_info"] == "Remastered"
        assert data["release_type"] == "Album"
        assert data["channel"] == "TestChannel"
        assert data["view_count"] == 1000000
        assert data["size_bytes"] == 52428800
        assert data["target_file_size"] == 26214400
        assert data["track_pattern"] == "Test Song"
        assert data["match_score"] == 0.95
        assert data["formatted_size"] == "50.0 MB"
        assert data["formatted_duration"] == "3:30"
        assert data["formatted_views"] == "1.0M"
        assert data["is_lossless"] == True
        assert data["quality_str"] == "FLAC 24bit WEB"
        # quality should be renamed to quality_data
        assert data["quality_data"] == {'format': 'FLAC', 'bit_depth': 24, 'media': 'WEB'}
        # raw_result should NOT be in serialized dict
        assert "raw_result" not in data

    def test_from_dict_basic(self):
        """Test from_dict with minimal fields."""
        data = {
            "title": "Test Song",
            "artist": "Test Artist",
            "url": "https://example.com/song",
            "provider": "YouTube",
        }
        result = AudioSearchResult.from_dict(data)
        
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.url == "https://example.com/song"
        assert result.provider == "YouTube"
        assert result.duration is None
        assert result.quality is None
        assert result.source_id is None
        assert result.index == 0  # Default
        assert result.raw_result is None  # Always None from dict

    def test_from_dict_full(self):
        """Test from_dict with all fields."""
        data = {
            "title": "Test Song",
            "artist": "Test Artist",
            "url": "https://example.com/song",
            "provider": "Redacted",
            "duration": 240,
            "quality": "FLAC 24bit",
            "source_id": "abc123",
            "index": 7,
            "seeders": 15,
            "target_file": "02. Test Song.flac",
        }
        result = AudioSearchResult.from_dict(data)
        
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.url == "https://example.com/song"
        assert result.provider == "Redacted"
        assert result.duration == 240
        assert result.quality == "FLAC 24bit"
        assert result.source_id == "abc123"
        assert result.index == 7
        assert result.seeders == 15
        assert result.target_file == "02. Test Song.flac"
        assert result.raw_result is None  # Never restored from dict

    def test_from_dict_with_defaults(self):
        """Test from_dict uses defaults for missing fields."""
        data = {}
        result = AudioSearchResult.from_dict(data)
        
        assert result.title == ""
        assert result.artist == ""
        assert result.url == ""
        assert result.provider == "Unknown"
        assert result.index == 0
        assert result.raw_result is None

    def test_roundtrip_serialization(self):
        """Test to_dict -> from_dict roundtrip preserves data."""
        original = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="Redacted",
            duration=240,
            quality="FLAC",
            source_id="abc123",
            index=2,
            raw_result={"will": "be lost"},
        )
        
        data = original.to_dict()
        restored = AudioSearchResult.from_dict(data)
        
        assert restored.title == original.title
        assert restored.artist == original.artist
        assert restored.url == original.url
        assert restored.provider == original.provider
        assert restored.duration == original.duration
        assert restored.quality == original.quality
        assert restored.source_id == original.source_id
        assert restored.index == original.index
        # raw_result is NOT preserved
        assert restored.raw_result is None


class TestAudioFetchResult:
    """Tests for AudioFetchResult dataclass."""

    def test_basic_creation(self):
        """Test creating an AudioFetchResult with required fields."""
        result = AudioFetchResult(
            filepath="/path/to/song.flac",
            artist="Test Artist",
            title="Test Song",
            provider="YouTube",
        )
        assert result.filepath == "/path/to/song.flac"
        assert result.artist == "Test Artist"
        assert result.title == "Test Song"
        assert result.provider == "YouTube"
        assert result.duration is None
        assert result.quality is None

    def test_full_creation(self):
        """Test creating an AudioFetchResult with all fields."""
        result = AudioFetchResult(
            filepath="/path/to/song.flac",
            artist="Test Artist",
            title="Test Song",
            provider="Redacted",
            duration=180,
            quality="FLAC 24bit",
        )
        assert result.duration == 180
        assert result.quality == "FLAC 24bit"

    def test_to_dict_basic(self):
        """Test to_dict with minimal fields."""
        result = AudioFetchResult(
            filepath="/path/to/song.flac",
            artist="Test Artist",
            title="Test Song",
            provider="YouTube",
        )
        data = result.to_dict()
        
        assert data["filepath"] == "/path/to/song.flac"
        assert data["artist"] == "Test Artist"
        assert data["title"] == "Test Song"
        assert data["provider"] == "YouTube"
        assert data["duration"] is None
        assert data["quality"] is None

    def test_to_dict_full(self):
        """Test to_dict with all fields populated."""
        result = AudioFetchResult(
            filepath="/path/to/song.flac",
            artist="Test Artist",
            title="Test Song",
            provider="Redacted",
            duration=180,
            quality="FLAC 24bit",
        )
        data = result.to_dict()
        
        assert data["filepath"] == "/path/to/song.flac"
        assert data["artist"] == "Test Artist"
        assert data["title"] == "Test Song"
        assert data["provider"] == "Redacted"
        assert data["duration"] == 180
        assert data["quality"] == "FLAC 24bit"

    def test_from_dict_basic(self):
        """Test from_dict with minimal fields."""
        data = {
            "filepath": "/path/to/song.flac",
            "artist": "Test Artist",
            "title": "Test Song",
            "provider": "YouTube",
        }
        result = AudioFetchResult.from_dict(data)
        
        assert result.filepath == "/path/to/song.flac"
        assert result.artist == "Test Artist"
        assert result.title == "Test Song"
        assert result.provider == "YouTube"
        assert result.duration is None
        assert result.quality is None

    def test_from_dict_full(self):
        """Test from_dict with all fields."""
        data = {
            "filepath": "/path/to/song.flac",
            "artist": "Test Artist",
            "title": "Test Song",
            "provider": "Redacted",
            "duration": 180,
            "quality": "FLAC 24bit",
        }
        result = AudioFetchResult.from_dict(data)
        
        assert result.filepath == "/path/to/song.flac"
        assert result.artist == "Test Artist"
        assert result.title == "Test Song"
        assert result.provider == "Redacted"
        assert result.duration == 180
        assert result.quality == "FLAC 24bit"

    def test_from_dict_with_defaults(self):
        """Test from_dict uses defaults for missing fields."""
        data = {}
        result = AudioFetchResult.from_dict(data)
        
        assert result.filepath == ""
        assert result.artist == ""
        assert result.title == ""
        assert result.provider == "Unknown"
        assert result.duration is None
        assert result.quality is None

    def test_roundtrip_serialization(self):
        """Test to_dict -> from_dict roundtrip preserves data."""
        original = AudioFetchResult(
            filepath="/path/to/song.flac",
            artist="Test Artist",
            title="Test Song",
            provider="Redacted",
            duration=180,
            quality="FLAC 24bit",
        )
        
        data = original.to_dict()
        restored = AudioFetchResult.from_dict(data)
        
        assert restored.filepath == original.filepath
        assert restored.artist == original.artist
        assert restored.title == original.title
        assert restored.provider == original.provider
        assert restored.duration == original.duration
        assert restored.quality == original.quality


class TestExceptions:
    """Tests for custom exceptions."""

    def test_audio_fetcher_error(self):
        """Test AudioFetcherError can be raised and caught."""
        with pytest.raises(AudioFetcherError) as exc_info:
            raise AudioFetcherError("Test error")
        assert str(exc_info.value) == "Test error"

    def test_no_results_error(self):
        """Test NoResultsError inherits from AudioFetcherError."""
        with pytest.raises(AudioFetcherError):
            raise NoResultsError("No results found")
        
        with pytest.raises(NoResultsError) as exc_info:
            raise NoResultsError("No results found")
        assert str(exc_info.value) == "No results found"

    def test_download_error(self):
        """Test DownloadError inherits from AudioFetcherError."""
        with pytest.raises(AudioFetcherError):
            raise DownloadError("Download failed")
        
        with pytest.raises(DownloadError) as exc_info:
            raise DownloadError("Download failed")
        assert str(exc_info.value) == "Download failed"

    def test_user_cancelled_error(self):
        """Test UserCancelledError inherits from AudioFetcherError."""
        with pytest.raises(AudioFetcherError):
            raise UserCancelledError("User cancelled")
        
        with pytest.raises(UserCancelledError) as exc_info:
            raise UserCancelledError("User cancelled")
        assert str(exc_info.value) == "User cancelled"


class TestCheckInterrupt:
    """Tests for the _check_interrupt function."""
    
    def test_check_interrupt_does_nothing_when_not_requested(self):
        """Test _check_interrupt passes when no interrupt requested."""
        # Ensure flag is False
        audio_fetcher_module._interrupt_requested = False
        # Should not raise
        audio_fetcher_module._check_interrupt()
    
    def test_check_interrupt_raises_when_requested(self):
        """Test _check_interrupt raises UserCancelledError when interrupt requested."""
        try:
            audio_fetcher_module._interrupt_requested = True
            with pytest.raises(UserCancelledError, match="cancelled by user"):
                audio_fetcher_module._check_interrupt()
        finally:
            # Reset the flag
            audio_fetcher_module._interrupt_requested = False


class TestFlacFetchAudioFetcher:
    """Tests for FlacFetchAudioFetcher implementation."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def fetcher(self, mock_logger):
        """Create a FlacFetchAudioFetcher instance with mocked dependencies."""
        return FlacFetchAudioFetcher(logger=mock_logger)

    @patch.dict(os.environ, {}, clear=True)
    def test_init_default(self):
        """Test default initialization without environment variables."""
        # Clear env vars to test default behavior
        with patch.dict(os.environ, {"REDACTED_API_KEY": "", "OPS_API_KEY": ""}, clear=False):
            fetcher = FlacFetchAudioFetcher()
            assert fetcher._manager is None

    def test_init_with_api_keys(self, mock_logger):
        """Test initialization with API keys."""
        fetcher = FlacFetchAudioFetcher(
            logger=mock_logger,
            redacted_api_key="red_key",
            ops_api_key="ops_key",
        )
        assert fetcher._redacted_api_key == "red_key"
        assert fetcher._ops_api_key == "ops_key"

    @patch.dict(os.environ, {"REDACTED_API_KEY": "env_red_key", "OPS_API_KEY": "env_ops_key"})
    def test_init_from_environment(self, mock_logger):
        """Test initialization reads API keys from environment."""
        fetcher = FlacFetchAudioFetcher(logger=mock_logger)
        assert fetcher._redacted_api_key == "env_red_key"
        assert fetcher._ops_api_key == "env_ops_key"

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_search_success(self, mock_get_manager, fetcher):
        """Test successful search returns results."""
        # Set up mock using correct flacfetch Release attribute names
        mock_manager = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Found Song"
        mock_result.artist = "Found Artist"
        mock_result.download_url = "https://example.com/song"
        mock_result.source_name = "YouTube"
        mock_result.duration_seconds = 200
        mock_result.quality = MagicMock(__str__=MagicMock(return_value="320kbps"))
        mock_result.info_hash = "abc123"
        mock_manager.search.return_value = [mock_result]
        mock_get_manager.return_value = mock_manager

        # Execute
        results = fetcher.search("Test Artist", "Test Song")

        # Verify
        assert len(results) == 1
        assert results[0].title == "Found Song"
        assert results[0].artist == "Found Artist"
        assert results[0].provider == "YouTube"
        assert results[0].raw_result == mock_result

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_search_no_results(self, mock_get_manager, fetcher):
        """Test search raises NoResultsError when no results found."""
        mock_manager = MagicMock()
        mock_manager.search.return_value = []
        mock_get_manager.return_value = mock_manager

        with pytest.raises(NoResultsError) as exc_info:
            fetcher.search("Unknown Artist", "Unknown Song")
        
        assert "No results found" in str(exc_info.value)

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_download_success(self, mock_get_manager, fetcher, tmp_path):
        """Test successful download returns AudioFetchResult."""
        # Set up mock
        mock_manager = MagicMock()
        downloaded_path = str(tmp_path / "song.flac")
        mock_manager.download.return_value = downloaded_path
        mock_get_manager.return_value = mock_manager

        # Create search result
        raw_result = MagicMock()
        search_result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="YouTube",
            duration=180,
            quality="FLAC",
            raw_result=raw_result,
        )

        # Execute
        result = fetcher.download(search_result, str(tmp_path))

        # Verify
        assert result.filepath == downloaded_path
        assert result.artist == "Test Artist"
        assert result.title == "Test Song"
        assert result.provider == "YouTube"
        mock_manager.download.assert_called_once()

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_download_failure(self, mock_get_manager, fetcher, tmp_path):
        """Test download raises DownloadError on failure."""
        mock_manager = MagicMock()
        mock_manager.download.return_value = None
        mock_get_manager.return_value = mock_manager

        raw_result = MagicMock()
        search_result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="YouTube",
            raw_result=raw_result,
        )

        with pytest.raises(DownloadError) as exc_info:
            fetcher.download(search_result, str(tmp_path))
        
        assert "Download returned no file path" in str(exc_info.value)

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_download_exception(self, mock_get_manager, fetcher, tmp_path):
        """Test download wraps exceptions in DownloadError."""
        mock_manager = MagicMock()
        mock_manager.download.side_effect = Exception("Network error")
        mock_get_manager.return_value = mock_manager

        raw_result = MagicMock()
        search_result = AudioSearchResult(
            title="Test Song",
            artist="Test Artist",
            url="https://example.com/song",
            provider="YouTube",
            raw_result=raw_result,
        )

        with pytest.raises(DownloadError) as exc_info:
            fetcher.download(search_result, str(tmp_path))
        
        assert "Failed to download" in str(exc_info.value)

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_search_and_download_auto_select(self, mock_get_manager, fetcher, tmp_path):
        """Test search_and_download with auto_select=True uses select_best."""
        # Set up mock using correct flacfetch Release attribute names
        mock_manager = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Test Song"
        mock_result.artist = "Test Artist"
        mock_result.source_name = "YouTube"
        mock_result.duration_seconds = 180
        mock_result.quality = MagicMock(__str__=MagicMock(return_value="FLAC 16bit CD"))
        mock_manager.search.return_value = [mock_result]
        mock_manager.select_best.return_value = mock_result
        downloaded_path = str(tmp_path / "song.flac")
        mock_manager.download.return_value = downloaded_path
        mock_get_manager.return_value = mock_manager

        # Execute
        result = fetcher.search_and_download(
            artist="Test Artist",
            title="Test Song",
            output_dir=str(tmp_path),
            auto_select=True,
        )

        # Verify
        mock_manager.select_best.assert_called_once()
        assert result.filepath == downloaded_path
        assert result.artist == "Test Artist"
        assert result.title == "Test Song"

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    @patch('builtins.input', return_value='1')
    def test_search_and_download_interactive_select(self, mock_input, mock_get_manager, fetcher, tmp_path, capsys):
        """Test search_and_download with interactive selection."""
        # Use real Release object to avoid MagicMock comparison issues in print_releases
        test_release = create_test_release(
            title="Test Song",
            artist="Test Artist",
            source_name="YouTube",
            duration_seconds=180,
        )
        
        mock_manager = MagicMock()
        mock_manager.search.return_value = [test_release]
        downloaded_path = str(tmp_path / "song.flac")
        mock_manager.download.return_value = downloaded_path
        mock_get_manager.return_value = mock_manager

        # Execute
        result = fetcher.search_and_download(
            artist="Test Artist",
            title="Test Song",
            output_dir=str(tmp_path),
            auto_select=False,
        )

        # Verify
        mock_manager.select_best.assert_not_called()
        assert result.filepath == downloaded_path
        
        # Check output shows options (flacfetch uses "Found X releases")
        captured = capsys.readouterr()
        assert "Found" in captured.out and "releases" in captured.out

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_search_and_download_no_results(self, mock_get_manager, fetcher, tmp_path):
        """Test search_and_download raises NoResultsError when no results."""
        mock_manager = MagicMock()
        mock_manager.search.return_value = []
        mock_get_manager.return_value = mock_manager

        with pytest.raises(NoResultsError):
            fetcher.search_and_download(
                artist="Unknown",
                title="Unknown",
                output_dir=str(tmp_path),
                auto_select=True,
            )

    @patch('builtins.input', return_value='0')
    def test_interactive_select_cancel(self, mock_input, fetcher):
        """Test interactive selection raises UserCancelledError when user cancels."""
        # Use real Release object to avoid MagicMock comparison issues
        test_release = create_test_release(title="Test", artist="Artist")

        with pytest.raises(UserCancelledError):
            fetcher._interactive_select([test_release], "Artist", "Test")

    @patch('builtins.input', side_effect=['invalid', '1'])
    def test_interactive_select_invalid_then_valid(self, mock_input, fetcher):
        """Test interactive selection handles invalid input gracefully."""
        # Use real Release object to avoid MagicMock comparison issues
        test_release = create_test_release(title="Test", artist="Artist")

        result = fetcher._interactive_select([test_release], "Artist", "Test")
        assert result == test_release

    @patch('builtins.input', side_effect=['5', '1'])
    def test_interactive_select_out_of_range_then_valid(self, mock_input, fetcher, capsys):
        """Test interactive selection handles out-of-range input."""
        # Use real Release object to avoid MagicMock comparison issues
        test_release = create_test_release(title="Test", artist="Artist")

        result = fetcher._interactive_select([test_release], "Artist", "Test")
        assert result == test_release
        
        captured = capsys.readouterr()
        # flacfetch's CLIHandler outputs "Invalid selection." for out-of-range
        assert "Invalid selection" in captured.out

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_interactive_select_keyboard_interrupt(self, mock_input, fetcher):
        """Test interactive selection raises UserCancelledError on keyboard interrupt."""
        # Use real Release object to avoid MagicMock comparison issues
        test_release = create_test_release(title="Test", artist="Artist")

        with pytest.raises(UserCancelledError):
            fetcher._interactive_select([test_release], "Artist", "Test")

    @patch('flacfetch.interface.cli.CLIHandler')
    @patch('builtins.input', return_value='1')
    def test_interactive_select_fallback_on_cli_handler_error(self, mock_input, mock_cli_handler, fetcher):
        """Test interactive selection falls back to basic when CLIHandler fails."""
        # Make CLIHandler raise AttributeError to trigger fallback
        mock_cli_handler.side_effect = AttributeError("CLIHandler error")
        
        # Use real Release object
        test_release = create_test_release(title="Test", artist="Artist")
        
        # Should fall back to _basic_interactive_select and succeed
        result = fetcher._interactive_select([test_release], "Artist", "Test")
        assert result == test_release

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_select_best_returns_index(self, mock_get_manager, fetcher):
        """Test select_best returns the index of the best result."""
        # Create mock raw results
        raw_result_1 = MagicMock()
        raw_result_2 = MagicMock()
        raw_result_3 = MagicMock()
        
        # Create AudioSearchResults with raw_result
        results = [
            AudioSearchResult(
                title="Song 1", artist="Artist", url="url1", provider="YouTube",
                index=0, raw_result=raw_result_1,
            ),
            AudioSearchResult(
                title="Song 2", artist="Artist", url="url2", provider="Redacted",
                index=1, raw_result=raw_result_2,
            ),
            AudioSearchResult(
                title="Song 3", artist="Artist", url="url3", provider="OPS",
                index=2, raw_result=raw_result_3,
            ),
        ]
        
        # Mock manager.select_best to return the second raw result (index 1)
        mock_manager = MagicMock()
        mock_manager.select_best.return_value = raw_result_2
        mock_get_manager.return_value = mock_manager
        
        # Execute
        best_index = fetcher.select_best(results)
        
        # Verify
        assert best_index == 1
        mock_manager.select_best.assert_called_once()

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_select_best_empty_list(self, mock_get_manager, fetcher):
        """Test select_best returns 0 for empty list."""
        best_index = fetcher.select_best([])
        assert best_index == 0

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_select_best_single_result(self, mock_get_manager, fetcher):
        """Test select_best returns 0 for single result."""
        raw_result = MagicMock()
        results = [
            AudioSearchResult(
                title="Song", artist="Artist", url="url", provider="YouTube",
                index=0, raw_result=raw_result,
            ),
        ]
        
        mock_manager = MagicMock()
        mock_manager.select_best.return_value = raw_result
        mock_get_manager.return_value = mock_manager
        
        best_index = fetcher.select_best(results)
        
        assert best_index == 0

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_select_best_without_raw_results(self, mock_get_manager, fetcher):
        """Test select_best returns 0 when results have no raw_result."""
        results = [
            AudioSearchResult(
                title="Song 1", artist="Artist", url="url1", provider="YouTube",
                index=0, raw_result=None,
            ),
            AudioSearchResult(
                title="Song 2", artist="Artist", url="url2", provider="Redacted",
                index=1, raw_result=None,
            ),
        ]
        
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        
        best_index = fetcher.select_best(results)
        
        # Should return 0 as fallback since no raw results
        assert best_index == 0

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_select_best_handles_exception(self, mock_get_manager, fetcher):
        """Test select_best returns 0 when manager.select_best raises exception."""
        raw_result = MagicMock()
        results = [
            AudioSearchResult(
                title="Song", artist="Artist", url="url", provider="YouTube",
                index=0, raw_result=raw_result,
            ),
        ]
        
        mock_manager = MagicMock()
        mock_manager.select_best.side_effect = Exception("Some error")
        mock_get_manager.return_value = mock_manager
        
        # Should not raise, should return 0 as fallback
        best_index = fetcher.select_best(results)
        
        assert best_index == 0

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_search_sets_index_on_results(self, mock_get_manager, fetcher):
        """Test search() sets the correct index on each result."""
        # Create multiple mock results
        mock_results = []
        for i in range(3):
            mock_result = MagicMock()
            mock_result.title = f"Song {i}"
            mock_result.artist = "Artist"
            mock_result.download_url = f"https://example.com/{i}"
            mock_result.source_name = "YouTube"
            mock_result.duration_seconds = 180
            mock_result.quality = None
            mock_result.info_hash = str(i)
            mock_results.append(mock_result)
        
        mock_manager = MagicMock()
        mock_manager.search.return_value = mock_results
        mock_get_manager.return_value = mock_manager
        
        results = fetcher.search("Artist", "Song")
        
        # Verify indices are set correctly
        assert len(results) == 3
        assert results[0].index == 0
        assert results[1].index == 1
        assert results[2].index == 2


class TestFlacFetcherAlias:
    """Tests for FlacFetcher alias."""
    
    def test_flacfetcher_alias_exists(self):
        """Test FlacFetcher alias is available."""
        from karaoke_gen.audio_fetcher import FlacFetcher
        assert FlacFetcher is not None

    def test_flacfetcher_is_flacfetchaudiofetcher(self):
        """Test FlacFetcher is the same as FlacFetchAudioFetcher."""
        from karaoke_gen.audio_fetcher import FlacFetcher
        assert FlacFetcher is FlacFetchAudioFetcher

    def test_flacfetcher_can_instantiate(self):
        """Test FlacFetcher alias can be used to create instances."""
        from karaoke_gen.audio_fetcher import FlacFetcher
        fetcher = FlacFetcher()
        assert isinstance(fetcher, FlacFetchAudioFetcher)

    def test_flacfetcher_with_parameters(self):
        """Test FlacFetcher alias passes parameters correctly."""
        from karaoke_gen.audio_fetcher import FlacFetcher
        fetcher = FlacFetcher(
            redacted_api_key="test_key",
            ops_api_key="ops_key",
        )
        assert fetcher._redacted_api_key == "test_key"
        assert fetcher._ops_api_key == "ops_key"


class TestCreateAudioFetcher:
    """Tests for create_audio_fetcher factory function."""

    def test_creates_flacfetch_fetcher(self):
        """Test factory creates FlacFetchAudioFetcher."""
        fetcher = create_audio_fetcher()
        assert isinstance(fetcher, FlacFetchAudioFetcher)

    def test_passes_parameters(self):
        """Test factory passes parameters to constructor."""
        logger = MagicMock()
        fetcher = create_audio_fetcher(
            logger=logger,
            redacted_api_key="red_key",
            ops_api_key="ops_key",
        )
        assert fetcher.logger == logger
        assert fetcher._redacted_api_key == "red_key"
        assert fetcher._ops_api_key == "ops_key"


class TestFlacFetchManagerInitialization:
    """Tests for lazy FetchManager initialization."""

    def test_manager_is_lazily_initialized(self):
        """Test FetchManager is lazily initialized (not created at init time)."""
        fetcher = FlacFetchAudioFetcher()
        # Manager should be None until first use
        assert fetcher._manager is None

    def test_api_keys_stored_at_init(self):
        """Test API keys are stored at init for later use."""
        fetcher = FlacFetchAudioFetcher(
            redacted_api_key="red_key",
            ops_api_key="ops_key",
        )
        assert fetcher._redacted_api_key == "red_key"
        assert fetcher._ops_api_key == "ops_key"


class TestGetManagerIntegration:
    """
    Integration tests for _get_manager that verify real flacfetch imports and registration.
    
    These tests catch issues like:
    - Import errors from renamed classes (e.g., YouTubeProvider vs YoutubeProvider)
    - Missing downloader registration
    - API changes in flacfetch
    """

    def test_get_manager_imports_work(self):
        """Test that _get_manager can import all required flacfetch modules.
        
        This test would have caught the YouTubeProvider -> YoutubeProvider rename.
        """
        fetcher = FlacFetchAudioFetcher()
        
        # Actually call _get_manager to verify imports work
        manager = fetcher._get_manager()
        
        # Verify manager was created
        assert manager is not None
        assert fetcher._manager is manager  # Should be cached
        
        # Verify calling again returns same instance (lazy init)
        manager2 = fetcher._get_manager()
        assert manager is manager2

    def test_get_manager_registers_youtube_provider_and_downloader(self):
        """Test that YouTube provider AND downloader are registered.
        
        This test would have caught the missing downloader registration.
        """
        fetcher = FlacFetchAudioFetcher()
        manager = fetcher._get_manager()
        
        # Verify YouTube provider is registered
        provider_names = [p.name for p in manager.providers]
        assert "YouTube" in provider_names
        
        # Verify YouTube downloader is registered
        assert "YouTube" in manager._downloader_map, \
            "YouTube downloader must be registered to download from YouTube"

    def test_get_manager_registers_redacted_with_api_key_and_transmission(self):
        """Test that Redacted provider is registered when API key AND Transmission are available."""
        fetcher = FlacFetchAudioFetcher(redacted_api_key="test_key")
        
        # Mock Transmission as available
        with patch.object(fetcher, '_check_transmission_available', return_value=True):
            manager = fetcher._get_manager()
        
        # Verify Redacted provider is registered
        provider_names = [p.name for p in manager.providers]
        assert "Redacted" in provider_names
        
        # Verify Redacted downloader is registered (if TorrentDownloader is available)
        try:
            from flacfetch.downloaders.torrent import TorrentDownloader
            assert "Redacted" in manager._downloader_map, \
                "Redacted downloader must be registered when TorrentDownloader is available"
        except ImportError:
            # TorrentDownloader not available, which is okay
            pass

    def test_get_manager_skips_redacted_without_transmission(self):
        """Test that Redacted provider is NOT registered when Transmission is unavailable."""
        fetcher = FlacFetchAudioFetcher(redacted_api_key="test_key")
        
        # Mock Transmission as unavailable (the default on Cloud Run)
        with patch.object(fetcher, '_check_transmission_available', return_value=False):
            manager = fetcher._get_manager()
        
        # Verify Redacted provider is NOT registered (can't download from it)
        provider_names = [p.name for p in manager.providers]
        assert "Redacted" not in provider_names, \
            "Redacted provider should NOT be registered when Transmission is unavailable"
        
        # YouTube should still be registered
        assert "YouTube" in provider_names

    def test_get_manager_registers_ops_with_api_key_and_transmission(self):
        """Test that OPS provider is registered when API key AND Transmission are available."""
        fetcher = FlacFetchAudioFetcher(ops_api_key="test_key")
        
        # Mock Transmission as available
        with patch.object(fetcher, '_check_transmission_available', return_value=True):
            manager = fetcher._get_manager()
        
        # Verify OPS provider is registered
        provider_names = [p.name for p in manager.providers]
        assert "OPS" in provider_names
        
        # Verify OPS downloader is registered (if TorrentDownloader is available)
        try:
            from flacfetch.downloaders.torrent import TorrentDownloader
            assert "OPS" in manager._downloader_map, \
                "OPS downloader must be registered when TorrentDownloader is available"
        except ImportError:
            pass

    def test_get_manager_skips_ops_without_transmission(self):
        """Test that OPS provider is NOT registered when Transmission is unavailable."""
        fetcher = FlacFetchAudioFetcher(ops_api_key="test_key")
        
        # Mock Transmission as unavailable
        with patch.object(fetcher, '_check_transmission_available', return_value=False):
            manager = fetcher._get_manager()
        
        # Verify OPS provider is NOT registered
        provider_names = [p.name for p in manager.providers]
        assert "OPS" not in provider_names, \
            "OPS provider should NOT be registered when Transmission is unavailable"
        
        # YouTube should still be registered
        assert "YouTube" in provider_names

    def test_get_manager_with_all_providers_and_transmission(self):
        """Test manager setup with all providers configured when Transmission is available."""
        fetcher = FlacFetchAudioFetcher(
            redacted_api_key="red_key",
            ops_api_key="ops_key",
        )
        
        # Mock Transmission as available
        with patch.object(fetcher, '_check_transmission_available', return_value=True):
            manager = fetcher._get_manager()
        
        provider_names = [p.name for p in manager.providers]
        
        # All three providers should be registered when Transmission is available
        assert "Redacted" in provider_names
        assert "OPS" in provider_names
        assert "YouTube" in provider_names
        
        # YouTube downloader should always be registered
        assert "YouTube" in manager._downloader_map

    def test_get_manager_only_youtube_without_transmission(self):
        """Test that only YouTube is registered when Transmission is unavailable."""
        fetcher = FlacFetchAudioFetcher(
            redacted_api_key="red_key",
            ops_api_key="ops_key",
        )
        
        # Mock Transmission as unavailable (simulates Cloud Run environment)
        with patch.object(fetcher, '_check_transmission_available', return_value=False):
            manager = fetcher._get_manager()
        
        provider_names = [p.name for p in manager.providers]
        
        # Only YouTube should be registered
        assert "Redacted" not in provider_names
        assert "OPS" not in provider_names
        assert "YouTube" in provider_names
        
        # YouTube downloader should always be registered
        assert "YouTube" in manager._downloader_map


class TestTransmissionAvailabilityCheck:
    """Tests for the Transmission daemon availability check."""

    def test_check_transmission_available_returns_true_when_connected(self):
        """Test that check returns True when Transmission is responsive."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_client = MagicMock()
        mock_client.session_stats.return_value = {}  # Successful response
        
        with patch('transmission_rpc.Client', return_value=mock_client):
            result = fetcher._check_transmission_available()
        
        assert result is True
        # Result should be cached
        assert fetcher._transmission_available is True

    def test_check_transmission_available_returns_false_on_connection_error(self):
        """Test that check returns False when Transmission connection fails."""
        fetcher = FlacFetchAudioFetcher()
        
        with patch('transmission_rpc.Client', side_effect=Exception("Cannot connect")):
            result = fetcher._check_transmission_available()
        
        assert result is False
        # Result should be cached
        assert fetcher._transmission_available is False

    def test_check_transmission_available_caches_result(self):
        """Test that Transmission availability is only checked once."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_client = MagicMock()
        
        with patch('transmission_rpc.Client', return_value=mock_client) as mock_constructor:
            # First call - should connect
            result1 = fetcher._check_transmission_available()
            # Second call - should use cache
            result2 = fetcher._check_transmission_available()
        
        # Should only create client once (cached after first call)
        assert mock_constructor.call_count == 1
        assert result1 == result2

    def test_check_transmission_uses_environment_variables(self):
        """Test that Transmission host/port can be configured via env vars."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_client = MagicMock()
        
        with patch.dict(os.environ, {'TRANSMISSION_HOST': 'custom-host', 'TRANSMISSION_PORT': '9999'}):
            with patch('transmission_rpc.Client', return_value=mock_client) as mock_constructor:
                fetcher._check_transmission_available()
        
        # Verify custom host/port were used
        mock_constructor.assert_called_once_with(host='custom-host', port=9999, timeout=5)


class TestFlacFetchReleaseModelCompatibility:
    """
    Tests to verify our code is compatible with flacfetch's Release model.
    
    These tests use real flacfetch models to catch attribute name mismatches.
    """

    def test_release_model_has_expected_attributes(self):
        """Verify flacfetch Release model has the attributes we expect.
        
        This serves as a canary test - if flacfetch changes attribute names,
        this test will fail immediately.
        """
        from flacfetch.core.models import Release, Quality, AudioFormat, MediaSource
        
        # Create a real Release object
        quality = Quality(format=AudioFormat.FLAC, bit_depth=16, media=MediaSource.CD)
        release = Release(
            title="Test Song",
            artist="Test Artist",
            quality=quality,
            source_name="Redacted",
        )
        
        # Verify the attributes we use in audio_fetcher.py exist
        assert hasattr(release, 'title')
        assert hasattr(release, 'artist')
        assert hasattr(release, 'source_name')  # NOT 'provider'
        assert hasattr(release, 'quality')
        assert hasattr(release, 'download_url')
        assert hasattr(release, 'duration_seconds')  # NOT 'duration'
        assert hasattr(release, 'info_hash')  # NOT 'id'
        assert hasattr(release, 'seeders')
        assert hasattr(release, 'target_file')
        
        # Verify quality can be converted to string
        quality_str = str(quality)
        assert isinstance(quality_str, str)
        assert "FLAC" in quality_str

    def test_search_converts_release_attributes_correctly(self):
        """Test that search() correctly maps Release attributes to AudioSearchResult."""
        from flacfetch.core.models import Release, Quality, AudioFormat, MediaSource
        
        fetcher = FlacFetchAudioFetcher()
        
        # Create a real Release object with all fields populated
        quality = Quality(format=AudioFormat.FLAC, bit_depth=24, media=MediaSource.WEB)
        real_release = Release(
            title="Real Song",
            artist="Real Artist",
            quality=quality,
            source_name="Redacted",
            download_url="https://example.com/download",
            duration_seconds=240,
            info_hash="abc123hash",
            seeders=50,
            target_file="01 - Real Song.flac",
        )
        
        # Mock the manager to return our real release
        with patch.object(fetcher, '_get_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.search.return_value = [real_release]
            mock_get_manager.return_value = mock_manager
            
            results = fetcher.search("Real Artist", "Real Song")
        
        # Verify correct attribute mapping
        assert len(results) == 1
        result = results[0]
        
        assert result.title == "Real Song"
        assert result.artist == "Real Artist"
        assert result.provider == "Redacted"  # source_name -> provider
        assert result.duration == 240  # duration_seconds -> duration
        assert result.url == "https://example.com/download"  # download_url -> url
        assert result.source_id == "abc123hash"  # info_hash -> source_id
        assert "FLAC" in result.quality  # quality converted to string
        assert result.raw_result is real_release


class TestFlacFetchCLIHandlerCompatibility:
    """Tests to verify compatibility with flacfetch's CLIHandler for rich output."""

    def test_cli_handler_import_works(self):
        """Verify we can import CLIHandler from flacfetch."""
        from flacfetch.interface.cli import CLIHandler
        
        handler = CLIHandler(target_artist="Test Artist")
        assert handler is not None

    def test_cli_handler_works_with_real_releases(self):
        """Test that CLIHandler can display real Release objects.
        
        This ensures we're passing proper Release objects, not mocks with wrong attributes.
        """
        from flacfetch.core.models import Release, Quality, AudioFormat, MediaSource
        from flacfetch import print_releases, format_release_line
        
        quality = Quality(format=AudioFormat.FLAC, bit_depth=16, media=MediaSource.CD)
        release = Release(
            title="Test Song",
            artist="Test Artist", 
            quality=quality,
            source_name="Redacted",
            seeders=25,
        )
        
        # Test format_release_line works with a real Release
        try:
            import io
            import sys
            
            # Capture stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                # Test single line formatting
                line = format_release_line(1, release, target_artist="Test Artist")
                print(line)
            finally:
                sys.stdout = sys.__stdout__
            
            output = captured.getvalue()
            assert "Test Artist" in output or "Test Song" in output
        except AttributeError as e:
            pytest.fail(f"format_release_line failed with AttributeError: {e}")


class TestDownloadWithCustomFilename:
    """Tests for download with custom filename."""

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_download_uses_custom_filename(self, mock_get_manager, tmp_path):
        """Test download uses provided custom filename."""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        downloaded_path = str(tmp_path / "custom_name.flac")
        mock_manager.download.return_value = downloaded_path

        fetcher = FlacFetchAudioFetcher()
        raw_result = MagicMock()
        search_result = AudioSearchResult(
            title="Original Title",
            artist="Original Artist",
            url="https://example.com/song",
            provider="YouTube",
            raw_result=raw_result,
        )

        result = fetcher.download(
            search_result,
            str(tmp_path),
            output_filename="custom_name",
        )

        # Verify custom filename was passed
        mock_manager.download.assert_called_once_with(
            raw_result,
            output_path=str(tmp_path),
            output_filename="custom_name",
        )

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_download_generates_filename_from_metadata(self, mock_get_manager, tmp_path):
        """Test download generates filename from artist/title if not provided."""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        downloaded_path = str(tmp_path / "Artist - Title.flac")
        mock_manager.download.return_value = downloaded_path

        fetcher = FlacFetchAudioFetcher()
        raw_result = MagicMock()
        search_result = AudioSearchResult(
            title="Title",
            artist="Artist",
            url="https://example.com/song",
            provider="YouTube",
            raw_result=raw_result,
        )

        result = fetcher.download(search_result, str(tmp_path))

        # Verify filename was generated from metadata
        mock_manager.download.assert_called_once_with(
            raw_result,
            output_path=str(tmp_path),
            output_filename="Artist - Title",
        )


class TestOutputDirectoryCreation:
    """Tests for output directory handling."""

    @patch('karaoke_gen.audio_fetcher.FlacFetchAudioFetcher._get_manager')
    def test_download_creates_output_directory(self, mock_get_manager, tmp_path):
        """Test download creates output directory if it doesn't exist."""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        
        new_dir = tmp_path / "new_directory"
        downloaded_path = str(new_dir / "song.flac")
        mock_manager.download.return_value = downloaded_path

        fetcher = FlacFetchAudioFetcher()
        raw_result = MagicMock()
        search_result = AudioSearchResult(
            title="Test",
            artist="Artist",
            url="https://example.com/song",
            provider="YouTube",
            raw_result=raw_result,
        )

        # Directory should be created
        assert not new_dir.exists()
        result = fetcher.download(search_result, str(new_dir))
        assert new_dir.exists()


class TestInterruptibleDownload:
    """Tests for the interruptible download functionality."""

    def test_interruptible_download_returns_filepath_on_success(self):
        """Test that _interruptible_download returns filepath when download succeeds."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_manager = MagicMock()
        mock_manager.download.return_value = "/path/to/downloaded.flac"
        mock_selected = MagicMock()
        
        result = fetcher._interruptible_download(
            mock_manager, mock_selected, "/output", "filename"
        )
        
        assert result == "/path/to/downloaded.flac"
        mock_manager.download.assert_called_once_with(
            mock_selected,
            output_path="/output",
            output_filename="filename",
        )

    def test_interruptible_download_propagates_errors(self):
        """Test that _interruptible_download raises DownloadError on failure."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_manager = MagicMock()
        mock_manager.download.side_effect = Exception("Download failed")
        mock_selected = MagicMock()
        
        with pytest.raises(Exception, match="Download failed"):
            fetcher._interruptible_download(
                mock_manager, mock_selected, "/output", "filename"
            )

    def test_interruptible_download_handles_interrupt(self):
        """Test that _interruptible_download handles Ctrl+C gracefully."""
        import signal
        import threading
        import time
        
        fetcher = FlacFetchAudioFetcher()
        
        # Create a mock download that takes a long time
        def slow_download(*args, **kwargs):
            time.sleep(10)  # Simulate slow download
            return "/path/to/file.flac"
        
        mock_manager = MagicMock()
        mock_manager.download.side_effect = slow_download
        mock_selected = MagicMock()
        mock_selected.name = "Test Release"
        
        # Mock the cleanup to avoid needing real transmission
        with patch.object(fetcher, '_cleanup_transmission_torrents'):
            # Start download in a thread and send interrupt
            def send_interrupt():
                time.sleep(0.3)  # Wait for download to start
                # Simulate Ctrl+C by setting the global flag
                import karaoke_gen.audio_fetcher as af
                af._interrupt_requested = True
            
            interrupt_thread = threading.Thread(target=send_interrupt, daemon=True)
            interrupt_thread.start()
            
            with pytest.raises(UserCancelledError, match="cancelled by user"):
                fetcher._interruptible_download(
                    mock_manager, mock_selected, "/output", "filename"
                )

    def test_interruptible_download_calls_cleanup_on_cancel(self):
        """Test that cleanup is called when download is cancelled."""
        import threading
        import time
        
        fetcher = FlacFetchAudioFetcher()
        
        def slow_download(*args, **kwargs):
            time.sleep(10)
            return "/path/to/file.flac"
        
        mock_manager = MagicMock()
        mock_manager.download.side_effect = slow_download
        mock_selected = MagicMock()
        mock_selected.name = "Test Release"
        
        with patch.object(fetcher, '_cleanup_transmission_torrents') as mock_cleanup:
            def send_interrupt():
                time.sleep(0.3)
                import karaoke_gen.audio_fetcher as af
                af._interrupt_requested = True
            
            interrupt_thread = threading.Thread(target=send_interrupt, daemon=True)
            interrupt_thread.start()
            
            with pytest.raises(UserCancelledError):
                fetcher._interruptible_download(
                    mock_manager, mock_selected, "/output", "filename"
                )
            
            # Verify cleanup was called with the selected release
            mock_cleanup.assert_called_once_with(mock_selected)


class TestTransmissionCleanup:
    """Tests for Transmission torrent cleanup functionality."""

    def test_cleanup_removes_matching_incomplete_torrent(self):
        """Test that cleanup removes incomplete torrents matching the release name."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_selected = MagicMock()
        mock_selected.name = "Test Artist - Test Song"
        
        # Create mock torrents
        incomplete_torrent = MagicMock()
        incomplete_torrent.id = 1
        incomplete_torrent.name = "Test Artist - Test Song [FLAC]"
        incomplete_torrent.progress = 50.0
        
        complete_torrent = MagicMock()
        complete_torrent.id = 2
        complete_torrent.name = "Other Album"
        complete_torrent.progress = 100.0
        
        mock_client = MagicMock()
        mock_client.get_torrents.return_value = [incomplete_torrent, complete_torrent]
        
        with patch('transmission_rpc.Client', return_value=mock_client):
            fetcher._cleanup_transmission_torrents(mock_selected)
        
        # Should only remove the matching incomplete torrent
        mock_client.remove_torrent.assert_called_once_with(1, delete_data=True)

    def test_cleanup_does_not_remove_complete_torrents(self):
        """Test that cleanup only removes incomplete torrents."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_selected = MagicMock()
        mock_selected.name = "Test Artist - Test Song"
        
        complete_torrent = MagicMock()
        complete_torrent.id = 1
        complete_torrent.name = "Test Artist - Test Song [FLAC]"
        complete_torrent.progress = 100.0  # Complete
        
        mock_client = MagicMock()
        mock_client.get_torrents.return_value = [complete_torrent]
        
        with patch('transmission_rpc.Client', return_value=mock_client):
            fetcher._cleanup_transmission_torrents(mock_selected)
        
        # Should not remove complete torrents
        mock_client.remove_torrent.assert_not_called()

    def test_cleanup_handles_connection_errors_gracefully(self):
        """Test that cleanup doesn't raise if Transmission connection fails."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_selected = MagicMock()
        mock_selected.name = "Test Song"
        
        with patch('transmission_rpc.Client', side_effect=Exception("Connection refused")):
            # Should not raise - cleanup failures are non-fatal
            fetcher._cleanup_transmission_torrents(mock_selected)

    def test_cleanup_handles_missing_release_name(self):
        """Test that cleanup handles releases without a name attribute."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_selected = MagicMock(spec=[])  # No attributes
        
        mock_client = MagicMock()
        
        with patch('transmission_rpc.Client', return_value=mock_client):
            # Should not raise - just return early
            fetcher._cleanup_transmission_torrents(mock_selected)
        
        # Should not even try to get torrents if no name
        mock_client.get_torrents.assert_not_called()

    def test_cleanup_uses_title_as_fallback_for_name(self):
        """Test that cleanup falls back to 'title' if 'name' not present."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_selected = MagicMock()
        del mock_selected.name  # Remove name attribute
        mock_selected.title = "Test Title"
        
        incomplete_torrent = MagicMock()
        incomplete_torrent.id = 1
        incomplete_torrent.name = "Test Title [FLAC]"
        incomplete_torrent.progress = 25.0
        
        mock_client = MagicMock()
        mock_client.get_torrents.return_value = [incomplete_torrent]
        
        with patch('transmission_rpc.Client', return_value=mock_client):
            fetcher._cleanup_transmission_torrents(mock_selected)
        
        # Should match on title and remove
        mock_client.remove_torrent.assert_called_once_with(1, delete_data=True)

    def test_cleanup_uses_environment_variables(self):
        """Test that cleanup uses TRANSMISSION_HOST/PORT env vars."""
        fetcher = FlacFetchAudioFetcher()
        
        mock_selected = MagicMock()
        mock_selected.name = "Test"
        
        mock_client = MagicMock()
        mock_client.get_torrents.return_value = []
        
        with patch.dict(os.environ, {'TRANSMISSION_HOST': 'remote-host', 'TRANSMISSION_PORT': '9999'}):
            with patch('transmission_rpc.Client', return_value=mock_client) as mock_constructor:
                fetcher._cleanup_transmission_torrents(mock_selected)
        
        mock_constructor.assert_called_once_with(host='remote-host', port=9999, timeout=5)
