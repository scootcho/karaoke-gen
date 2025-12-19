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
            raw_result=raw,
        )
        assert result.duration == 240
        assert result.quality == "FLAC"
        assert result.source_id == "123456"
        assert result.raw_result == raw


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
        # Set up mock using correct flacfetch Release attribute names
        mock_manager = MagicMock()
        mock_result = MagicMock()
        mock_result.title = "Test Song"
        mock_result.artist = "Test Artist"
        mock_result.source_name = "YouTube"
        mock_result.duration_seconds = 180
        mock_result.quality = MagicMock(__str__=MagicMock(return_value="320kbps"))
        mock_result.seeders = None
        mock_result.target_file = None
        mock_manager.search.return_value = [mock_result]
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
        
        # Check output shows options
        captured = capsys.readouterr()
        assert "Search Results" in captured.out

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
        # Use correct flacfetch Release attribute names for fallback display
        mock_result = MagicMock()
        mock_result.source_name = "YouTube"
        mock_result.title = "Test"
        mock_result.artist = "Artist"
        mock_result.quality = MagicMock(__str__=MagicMock(return_value="FLAC 16bit CD"))
        mock_result.duration_seconds = 180
        mock_result.seeders = None
        mock_result.target_file = None

        with pytest.raises(UserCancelledError):
            fetcher._interactive_select([mock_result], "Artist", "Test")

    @patch('builtins.input', side_effect=['invalid', '1'])
    def test_interactive_select_invalid_then_valid(self, mock_input, fetcher):
        """Test interactive selection handles invalid input gracefully."""
        mock_result = MagicMock()
        mock_result.source_name = "YouTube"
        mock_result.title = "Test"
        mock_result.artist = "Artist"
        mock_result.quality = MagicMock(__str__=MagicMock(return_value="FLAC 16bit CD"))
        mock_result.duration_seconds = 180
        mock_result.seeders = None
        mock_result.target_file = None

        result = fetcher._interactive_select([mock_result], "Artist", "Test")
        assert result == mock_result

    @patch('builtins.input', side_effect=['5', '1'])
    def test_interactive_select_out_of_range_then_valid(self, mock_input, fetcher, capsys):
        """Test interactive selection handles out-of-range input."""
        mock_result = MagicMock()
        mock_result.source_name = "YouTube"
        mock_result.title = "Test"
        mock_result.artist = "Artist"
        mock_result.quality = MagicMock(__str__=MagicMock(return_value="FLAC 16bit CD"))
        mock_result.duration_seconds = 180
        mock_result.seeders = None
        mock_result.target_file = None

        result = fetcher._interactive_select([mock_result], "Artist", "Test")
        assert result == mock_result
        
        captured = capsys.readouterr()
        assert "Please enter a number between" in captured.out

    @patch('builtins.input', side_effect=KeyboardInterrupt)
    def test_interactive_select_keyboard_interrupt(self, mock_input, fetcher, capsys):
        """Test interactive selection raises UserCancelledError on keyboard interrupt."""
        mock_result = MagicMock()
        mock_result.source_name = "YouTube"
        mock_result.title = "Test"
        mock_result.artist = "Artist"
        mock_result.quality = None
        mock_result.duration_seconds = None
        mock_result.seeders = None
        mock_result.target_file = None

        with pytest.raises(UserCancelledError):
            fetcher._interactive_select([mock_result], "Artist", "Test")
        
        captured = capsys.readouterr()
        assert "Cancelled" in captured.out


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

    def test_get_manager_registers_redacted_with_api_key(self):
        """Test that Redacted provider and downloader are registered when API key is provided."""
        fetcher = FlacFetchAudioFetcher(redacted_api_key="test_key")
        manager = fetcher._get_manager()
        
        # Verify Redacted provider is registered
        provider_names = [p.name for p in manager.providers]
        assert "Redacted" in provider_names
        
        # Verify Redacted downloader is registered (if TorrentDownloader is available)
        # Note: TorrentDownloader may not be available in all environments
        try:
            from flacfetch.downloaders.torrent import TorrentDownloader
            assert "Redacted" in manager._downloader_map, \
                "Redacted downloader must be registered when TorrentDownloader is available"
        except ImportError:
            # TorrentDownloader not available, which is okay
            pass

    def test_get_manager_registers_ops_with_api_key(self):
        """Test that OPS provider and downloader are registered when API key is provided."""
        fetcher = FlacFetchAudioFetcher(ops_api_key="test_key")
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

    def test_get_manager_with_all_providers(self):
        """Test manager setup with all providers configured."""
        fetcher = FlacFetchAudioFetcher(
            redacted_api_key="red_key",
            ops_api_key="ops_key",
        )
        manager = fetcher._get_manager()
        
        provider_names = [p.name for p in manager.providers]
        
        # All three providers should be registered
        assert "Redacted" in provider_names
        assert "OPS" in provider_names
        assert "YouTube" in provider_names
        
        # YouTube downloader should always be registered
        assert "YouTube" in manager._downloader_map


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
        from flacfetch.interface.cli import CLIHandler
        
        quality = Quality(format=AudioFormat.FLAC, bit_depth=16, media=MediaSource.CD)
        release = Release(
            title="Test Song",
            artist="Test Artist", 
            quality=quality,
            source_name="Redacted",
            seeders=25,
        )
        
        handler = CLIHandler(target_artist="Test Artist")
        
        # This should not raise any AttributeError
        # (Previously would fail if quality.is_lossless() didn't exist)
        try:
            # We can't easily test the full select_release without mocking input,
            # but we can at least verify _print_release works
            import io
            import sys
            
            # Capture stdout
            captured = io.StringIO()
            sys.stdout = captured
            try:
                handler._print_release(1, release)
            finally:
                sys.stdout = sys.__stdout__
            
            output = captured.getvalue()
            assert "Test Artist" in output or "Test Song" in output
        except AttributeError as e:
            pytest.fail(f"CLIHandler failed with AttributeError: {e}")


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
