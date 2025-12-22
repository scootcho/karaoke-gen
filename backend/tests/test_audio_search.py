"""
Tests for audio search functionality (Batch 5).

Tests the audio search service, API routes, and job model fields.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from backend.models.job import Job, JobCreate, JobStatus, STATE_TRANSITIONS
from backend.services.audio_search_service import (
    AudioSearchService,
    AudioSearchResult,
    AudioDownloadResult,
    AudioSearchError,
    NoResultsError,
    DownloadError,
    get_audio_search_service,
)


class TestJobModelAudioSearchFields:
    """Test Job model has audio search fields."""
    
    def test_job_has_audio_search_fields(self):
        """Test Job model has audio search configuration fields."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            artist="ABBA",
            title="Waterloo",
            audio_search_artist="ABBA",
            audio_search_title="Waterloo",
            auto_download=True,
        )
        
        assert job.audio_search_artist == "ABBA"
        assert job.audio_search_title == "Waterloo"
        assert job.auto_download is True
    
    def test_job_audio_search_fields_default_values(self):
        """Test default values for audio search fields."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert job.audio_search_artist is None
        assert job.audio_search_title is None
        assert job.auto_download is False
    
    def test_job_create_has_audio_search_fields(self):
        """Test JobCreate model has audio search fields."""
        job_create = JobCreate(
            artist="ABBA",
            title="Waterloo",
            audio_search_artist="ABBA",
            audio_search_title="Waterloo",
            auto_download=True,
        )
        
        assert job_create.audio_search_artist == "ABBA"
        assert job_create.audio_search_title == "Waterloo"
        assert job_create.auto_download is True


class TestJobStatusAudioSearchStates:
    """Test Job status includes audio search states."""
    
    def test_audio_search_statuses_exist(self):
        """Test audio search status values exist."""
        assert hasattr(JobStatus, 'SEARCHING_AUDIO')
        assert hasattr(JobStatus, 'AWAITING_AUDIO_SELECTION')
        assert hasattr(JobStatus, 'DOWNLOADING_AUDIO')
        
        assert JobStatus.SEARCHING_AUDIO == "searching_audio"
        assert JobStatus.AWAITING_AUDIO_SELECTION == "awaiting_audio_selection"
        assert JobStatus.DOWNLOADING_AUDIO == "downloading_audio"
    
    def test_state_transitions_include_audio_search_flow(self):
        """Test state transitions include audio search flow."""
        # PENDING can go to SEARCHING_AUDIO
        assert JobStatus.SEARCHING_AUDIO in STATE_TRANSITIONS[JobStatus.PENDING]
        
        # SEARCHING_AUDIO can go to AWAITING_AUDIO_SELECTION or DOWNLOADING_AUDIO
        assert JobStatus.AWAITING_AUDIO_SELECTION in STATE_TRANSITIONS[JobStatus.SEARCHING_AUDIO]
        assert JobStatus.DOWNLOADING_AUDIO in STATE_TRANSITIONS[JobStatus.SEARCHING_AUDIO]
        
        # AWAITING_AUDIO_SELECTION can go to DOWNLOADING_AUDIO
        assert JobStatus.DOWNLOADING_AUDIO in STATE_TRANSITIONS[JobStatus.AWAITING_AUDIO_SELECTION]
        
        # DOWNLOADING_AUDIO can go to DOWNLOADING
        assert JobStatus.DOWNLOADING in STATE_TRANSITIONS[JobStatus.DOWNLOADING_AUDIO]


class TestAudioSearchResult:
    """Test AudioSearchResult dataclass.
    
    AudioSearchResult is now imported from karaoke_gen.audio_fetcher.
    These tests verify the backend can use it correctly.
    """
    
    def test_create_audio_search_result(self):
        """Test creating an AudioSearchResult."""
        result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="YouTube",
            url="https://youtube.com/watch?v=abc123",
            duration=180,
            quality="FLAC",
            source_id="abc123",
            index=0,
        )
        
        assert result.title == "Waterloo"
        assert result.artist == "ABBA"
        assert result.provider == "YouTube"
        assert result.url == "https://youtube.com/watch?v=abc123"
        assert result.duration == 180
        assert result.quality == "FLAC"
        assert result.source_id == "abc123"
        assert result.index == 0
    
    def test_to_dict(self):
        """Test converting to dict for serialization."""
        result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="YouTube",
            url="https://youtube.com/watch?v=abc123",
            index=0,
        )
        
        data = result.to_dict()
        
        assert data['title'] == "Waterloo"
        assert data['artist'] == "ABBA"
        assert data['provider'] == "YouTube"
        assert data['url'] == "https://youtube.com/watch?v=abc123"
        assert data['index'] == 0
        # raw_result should NOT be in serialized dict
        assert 'raw_result' not in data
    
    def test_from_dict(self):
        """Test creating from dict."""
        data = {
            'title': "Waterloo",
            'artist': "ABBA",
            'provider': "YouTube",
            'url': "https://youtube.com/watch?v=abc123",
            'duration': 180,
            'quality': "FLAC",
            'source_id': "abc123",
            'index': 0,
        }
        
        result = AudioSearchResult.from_dict(data)
        
        assert result.title == "Waterloo"
        assert result.artist == "ABBA"
        assert result.provider == "YouTube"
        assert result.index == 0
        assert result.raw_result is None  # Not set from dict


class TestAudioSearchServiceInit:
    """Test AudioSearchService initialization."""
    
    @patch.dict('os.environ', {'REDACTED_API_KEY': '', 'OPS_API_KEY': ''}, clear=False)
    def test_init_with_no_keys(self):
        """Test initialization without API keys."""
        # Pass explicit None to override environment
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        
        # Service should have a FlacFetcher internally
        assert service._fetcher is not None
        assert service._cached_results == []
    
    def test_init_with_keys(self):
        """Test initialization with API keys."""
        service = AudioSearchService(
            redacted_api_key="test_redacted_key",
            ops_api_key="test_ops_key",
        )
        
        # Keys are passed to FlacFetcher
        assert service._fetcher._redacted_api_key == "test_redacted_key"
        assert service._fetcher._ops_api_key == "test_ops_key"
    
    def test_init_reads_from_environment(self):
        """Test initialization reads keys from environment variables."""
        # Just test that the service can be initialized
        service = AudioSearchService()
        
        # The service should have a FlacFetcher
        assert service._fetcher is not None


class TestAudioSearchServiceSearch:
    """Test AudioSearchService.search() method."""
    
    def test_search_returns_results(self):
        """Test search returns AudioSearchResult list."""
        # Create mock result
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="YouTube",
            url="https://youtube.com/watch?v=abc123",
            duration=180,
            quality="FLAC",
            source_id="abc123",
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.search.return_value = [mock_result]
        
        results = service.search("ABBA", "Waterloo")
        
        assert len(results) == 1
        assert results[0].title == "Waterloo"
        assert results[0].artist == "ABBA"
        assert results[0].provider == "YouTube"
        assert results[0].index == 0
    
    def test_search_no_results_raises_error(self):
        """Test search raises NoResultsError when no results."""
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.search.side_effect = NoResultsError("No results found")
        
        with pytest.raises(NoResultsError) as exc_info:
            service.search("Unknown Artist", "Unknown Song")
        
        assert "No results found" in str(exc_info.value)
    
    def test_search_multiple_results(self):
        """Test search returns multiple results with correct indices."""
        mock_results = []
        for i in range(3):
            mock_results.append(AudioSearchResult(
                title=f"Song {i}",
                artist="Artist",
                provider=["YouTube", "Redacted", "OPS"][i],
                url=f"https://example.com/{i}",
                duration=180 + i * 10,
                quality=["320kbps", "FLAC", "FLAC"][i],
                source_id=str(i),
                index=i,
            ))
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.search.return_value = mock_results
        
        results = service.search("Artist", "Song")
        
        assert len(results) == 3
        assert results[0].index == 0
        assert results[1].index == 1
        assert results[2].index == 2


class TestAudioSearchServiceSelectBest:
    """Test AudioSearchService.select_best() method."""
    
    def test_select_best_delegates_to_fetcher(self):
        """Test select_best uses FlacFetcher's select_best."""
        mock_results = [
            AudioSearchResult(
                title="Waterloo",
                artist="ABBA",
                provider="YouTube",
                url="https://youtube.com/watch?v=abc123",
                index=0,
            ),
            AudioSearchResult(
                title="Waterloo",
                artist="ABBA",
                provider="Redacted",
                url="https://example.com/456",
                index=1,
            ),
        ]
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.select_best.return_value = 1
        
        best_index = service.select_best(mock_results)
        
        assert best_index == 1
        service._fetcher.select_best.assert_called_once_with(mock_results)
    
    def test_select_best_empty_list_returns_zero(self):
        """Test select_best returns 0 for empty list."""
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.select_best.return_value = 0
        
        best_index = service.select_best([])
        
        assert best_index == 0


class TestAudioSearchServiceDownload:
    """Test AudioSearchService.download() method."""
    
    def test_download_without_search_raises_error(self):
        """Test download without prior search raises error."""
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        
        with pytest.raises(DownloadError) as exc_info:
            service.download(0, "/tmp")
        
        assert "No cached result" in str(exc_info.value)
    
    def test_download_after_search(self):
        """Test download after search works."""
        import tempfile
        
        # Create a temp file to simulate downloaded file
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "test.flac")
        with open(temp_file, 'w') as f:
            f.write("test")
        
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="YouTube",
            url="https://youtube.com/watch?v=abc123",
            duration=180,
            quality="FLAC",
            source_id="abc123",
            index=0,
        )
        
        mock_fetch_result = AudioDownloadResult(
            filepath=temp_file,
            artist="ABBA",
            title="Waterloo",
            provider="YouTube",
            duration=180,
            quality="FLAC",
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.search.return_value = [mock_result]
        service._fetcher.download.return_value = mock_fetch_result
        
        service.search("ABBA", "Waterloo")
        result = service.download(0, temp_dir)
        
        assert result.filepath == temp_file
        assert result.artist == "ABBA"
        assert result.title == "Waterloo"
        assert result.provider == "YouTube"
        
        # Cleanup
        os.remove(temp_file)
        os.rmdir(temp_dir)
    
    def test_download_invalid_index_raises_error(self):
        """Test download with invalid index raises error."""
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="YouTube",
            url="https://youtube.com/watch?v=abc123",
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._fetcher.search.return_value = [mock_result]
        
        service.search("ABBA", "Waterloo")
        
        with pytest.raises(DownloadError) as exc_info:
            service.download(99, "/tmp")
        
        assert "No cached result for index 99" in str(exc_info.value)


class TestGetAudioSearchService:
    """Test get_audio_search_service singleton."""
    
    def test_get_audio_search_service_returns_instance(self):
        """Test get_audio_search_service returns an instance."""
        # Reset singleton
        import backend.services.audio_search_service as module
        module._audio_search_service = None
        
        service = get_audio_search_service()
        
        assert service is not None
        assert isinstance(service, AudioSearchService)
    
    def test_get_audio_search_service_singleton(self):
        """Test get_audio_search_service returns same instance."""
        service1 = get_audio_search_service()
        service2 = get_audio_search_service()
        
        assert service1 is service2


class TestRemoteDownloadPath:
    """Test remote download functionality when flacfetch service is configured.
    
    These tests verify the code path that uses the remote flacfetch service
    for torrent downloads (Redacted/OPS providers). This would have caught
    the 'extra_info' attribute error.
    
    The tests directly set up the service state without calling search() to avoid
    the complexity of mocking async remote search operations.
    """
    
    def test_download_uses_remote_for_redacted_provider(self):
        """Test download routes to remote service for Redacted provider.
        
        This test would have caught: 'AudioSearchResult' object has no attribute 'extra_info'
        """
        # Create a Redacted result (torrent source)
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="Redacted",  # Torrent provider - should use remote
            url="",  # No URL for torrent sources
            quality="FLAC 16bit CD",
            seeders=50,
            target_file="Waterloo.flac",
            index=0,
        )
        
        # Create service with mocked remote client
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        
        # Directly set cached results (simulating after search)
        service._cached_results = [mock_result]
        service._remote_search_id = "remote_search_123"  # Remote search was performed
        
        # Mock the remote client
        mock_remote_client = Mock()
        service._remote_client = mock_remote_client
        
        # Mock the remote download method
        mock_download_result = AudioDownloadResult(
            filepath="gs://bucket/uploads/job123/audio/Waterloo.flac",
            artist="ABBA",
            title="Waterloo",
            provider="Redacted",
            quality="FLAC 16bit CD",
        )
        service._download_remote = Mock(return_value=mock_download_result)
        
        # Call download - should route to remote
        result = service.download(0, "/tmp", gcs_path="uploads/job123/audio/")
        
        # Verify remote download was called
        service._download_remote.assert_called_once_with(0, "/tmp", None, "uploads/job123/audio/")
        assert result.filepath == "gs://bucket/uploads/job123/audio/Waterloo.flac"
    
    def test_download_uses_remote_for_ops_provider(self):
        """Test download routes to remote service for OPS provider."""
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="OPS",  # Torrent provider
            url="",
            quality="FLAC 16bit CD",
            seeders=30,
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        
        # Directly set cached results
        service._cached_results = [mock_result]
        service._remote_search_id = "remote_search_456"
        
        # Mock remote client
        mock_remote_client = Mock()
        service._remote_client = mock_remote_client
        
        # Mock remote download
        mock_download_result = AudioDownloadResult(
            filepath="gs://bucket/test.flac",
            artist="ABBA",
            title="Waterloo",
            provider="OPS",
            quality="FLAC",
        )
        service._download_remote = Mock(return_value=mock_download_result)
        
        # Call download
        result = service.download(0, "/tmp")
        
        # Should use remote for OPS
        service._download_remote.assert_called_once()
    
    def test_download_uses_local_for_youtube_even_with_remote_client(self):
        """Test YouTube downloads use local even when remote client is configured."""
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="YouTube",  # NOT a torrent provider
            url="https://youtube.com/watch?v=abc123",
            quality="Opus 128kbps",
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        
        # Directly set cached results
        service._cached_results = [mock_result]
        service._remote_search_id = "remote_search_789"  # Remote search was performed
        
        # Mock remote client (configured but shouldn't be used for YouTube)
        mock_remote_client = Mock()
        service._remote_client = mock_remote_client
        
        # Mock local download
        mock_fetch_result = AudioDownloadResult(
            filepath="/tmp/test.opus",
            artist="ABBA",
            title="Waterloo",
            provider="YouTube",
            quality="Opus 128kbps",
        )
        service._fetcher.download.return_value = mock_fetch_result
        
        # Mock _download_remote to ensure it's NOT called
        service._download_remote = Mock()
        
        # Call download
        result = service.download(0, "/tmp")
        
        # Should use local for YouTube
        service._download_remote.assert_not_called()
        service._fetcher.download.assert_called_once()
    
    def test_download_uses_local_when_no_remote_client(self):
        """Test download uses local when remote client is not configured."""
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="Redacted",  # Would normally use remote
            url="",
            quality="FLAC",
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        
        # Directly set cached results
        service._cached_results = [mock_result]
        
        # No remote client
        service._remote_client = None
        service._remote_search_id = None  # No remote search
        
        # Mock local download
        mock_fetch_result = AudioDownloadResult(
            filepath="/tmp/test.flac",
            artist="ABBA",
            title="Waterloo",
            provider="Redacted",
            quality="FLAC",
        )
        service._fetcher.download.return_value = mock_fetch_result
        
        # Call download
        result = service.download(0, "/tmp")
        
        # Should use local even though it's Redacted
        service._fetcher.download.assert_called_once()
    
    def test_download_uses_local_when_no_remote_search_id(self):
        """Test download uses local when search wasn't done remotely."""
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="Redacted",
            url="",
            quality="FLAC",
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        
        # Directly set cached results
        service._cached_results = [mock_result]
        
        # Remote client configured but search was local (fallback scenario)
        service._remote_client = Mock()
        service._remote_search_id = None  # Search was local, not remote
        
        # Mock local download
        mock_fetch_result = AudioDownloadResult(
            filepath="/tmp/test.flac",
            artist="ABBA",
            title="Waterloo",
            provider="Redacted",
            quality="FLAC",
        )
        service._fetcher.download.return_value = mock_fetch_result
        
        # Call download
        result = service.download(0, "/tmp")
        
        # Should use local since no remote search ID
        service._fetcher.download.assert_called_once()
    
    def test_torrent_provider_routing_checks_both_conditions(self):
        """Test that torrent provider routing requires BOTH remote_search_id AND remote_client.
        
        This test verifies the logical AND condition in the download routing.
        """
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="Redacted",
            url="",
            quality="FLAC",
            index=0,
        )
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._cached_results = [mock_result]
        
        # Test: remote_client set but no remote_search_id -> should use local
        service._remote_client = Mock()
        service._remote_search_id = None
        
        mock_fetch_result = AudioDownloadResult(
            filepath="/tmp/test.flac", artist="ABBA", title="Waterloo",
            provider="Redacted", quality="FLAC",
        )
        service._fetcher.download.return_value = mock_fetch_result
        service._download_remote = Mock()
        
        service.download(0, "/tmp")
        service._download_remote.assert_not_called()
        service._fetcher.download.assert_called_once()
        
        # Reset mocks
        service._fetcher.download.reset_mock()
        service._download_remote.reset_mock()
        
        # Test: remote_search_id set but no remote_client -> should use local
        service._remote_client = None
        service._remote_search_id = "search_123"
        
        service.download(0, "/tmp")
        service._download_remote.assert_not_called()
        service._fetcher.download.assert_called_once()
    
    def test_download_does_not_access_nonexistent_attributes(self):
        """Test that download() doesn't try to access nonexistent attributes.
        
        This test would have caught the 'extra_info' attribute error:
        AttributeError: 'AudioSearchResult' object has no attribute 'extra_info'
        
        AudioSearchResult only has: title, artist, url, provider, duration,
        quality, source_id, index, seeders, target_file, raw_result
        """
        mock_result = AudioSearchResult(
            title="Waterloo",
            artist="ABBA",
            provider="Redacted",
            url="",
            quality="FLAC 16bit CD",
            seeders=50,
            index=0,
        )
        
        # Verify AudioSearchResult doesn't have extra_info
        assert not hasattr(mock_result, 'extra_info')
        
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        service._fetcher = Mock()
        service._cached_results = [mock_result]
        service._remote_search_id = "search_123"
        service._remote_client = Mock()
        
        # Mock _download_remote to avoid actual network call
        mock_download_result = AudioDownloadResult(
            filepath="/tmp/test.flac",
            artist="ABBA",
            title="Waterloo", 
            provider="Redacted",
            quality="FLAC",
        )
        service._download_remote = Mock(return_value=mock_download_result)
        
        # This should NOT raise AttributeError: 'AudioSearchResult' object has no attribute 'extra_info'
        result = service.download(0, "/tmp")
        
        # Should succeed and use remote download for Redacted provider
        service._download_remote.assert_called_once()
        assert result.filepath == "/tmp/test.flac"


class TestFlacfetchIntegration:
    """
    Integration tests that verify flacfetch imports work correctly.
    
    These tests ensure the backend code is compatible with the installed
    flacfetch version and would catch issues like renamed classes.
    
    Note: Some tests are marked with pytest.importorskip for flacfetch
    since it may not be installed in all test environments (e.g., CI).
    """
    
    def test_flacfetch_imports_work(self):
        """Test that all flacfetch imports in audio_search_service work.
        
        This test would have caught the YouTubeProvider -> YoutubeProvider rename.
        """
        flacfetch = pytest.importorskip("flacfetch")
        
        # These imports match what karaoke_gen.audio_fetcher does
        from flacfetch.core.manager import FetchManager
        from flacfetch.providers.youtube import YoutubeProvider
        from flacfetch.core.models import TrackQuery
        
        # Verify the classes exist and are callable
        assert FetchManager is not None
        assert YoutubeProvider is not None
        assert TrackQuery is not None
    
    def test_karaoke_gen_audio_fetcher_imports_work(self):
        """Test that karaoke_gen.audio_fetcher imports work.
        
        Since backend now imports from karaoke_gen, this is the critical test.
        This should work even without flacfetch installed (lazy import).
        """
        from karaoke_gen.audio_fetcher import (
            FlacFetcher,
            AudioSearchResult,
            AudioFetchResult,
            AudioFetcherError,
            NoResultsError,
            DownloadError,
        )
        
        assert FlacFetcher is not None
        assert AudioSearchResult is not None
        assert AudioFetchResult is not None
        assert AudioFetcherError is not None
        assert NoResultsError is not None
        assert DownloadError is not None
    
    def test_audio_search_service_can_initialize_fetcher(self):
        """Test AudioSearchService can initialize its FlacFetcher.
        
        This verifies the actual initialization code path works.
        """
        pytest.importorskip("flacfetch")
        
        service = AudioSearchService(
            redacted_api_key=None,
            ops_api_key=None,
        )
        
        # Verify FlacFetcher was initialized
        assert service._fetcher is not None
        
        # FlacFetcher can initialize its manager (tests actual flacfetch)
        manager = service._fetcher._get_manager()
        assert manager is not None
    
    def test_shared_classes_are_same_as_karaoke_gen(self):
        """Verify backend uses the same classes as karaoke_gen."""
        from karaoke_gen.audio_fetcher import (
            AudioSearchResult as KGAudioSearchResult,
            AudioFetchResult as KGAudioFetchResult,
            NoResultsError as KGNoResultsError,
            DownloadError as KGDownloadError,
        )
        
        # These should be the exact same classes, not copies
        assert AudioSearchResult is KGAudioSearchResult
        assert AudioDownloadResult is KGAudioFetchResult
        assert NoResultsError is KGNoResultsError
        assert DownloadError is KGDownloadError


class TestAudioSearchApiRouteDownload:
    """
    Tests for _download_and_start_processing function in audio_search routes.
    
    This tests the API layer's handling of the download flow, including:
    - Correct routing between local and remote downloads
    - GCS path handling for remote downloads
    - Error handling
    """
    
    @pytest.fixture
    def mock_job_manager(self):
        """Mock the job manager singleton."""
        with patch('backend.api.routes.audio_search.job_manager') as mock:
            yield mock
    
    @pytest.fixture
    def mock_storage_service(self):
        """Mock the storage service singleton."""
        with patch('backend.api.routes.audio_search.storage_service') as mock:
            yield mock
    
    def test_remote_download_passes_gcs_path(self, mock_job_manager, mock_storage_service):
        """
        Test that remote torrent downloads include GCS path for direct upload.
        
        This was the bug: we were calling download() without gcs_path for
        torrent sources, causing flacfetch VM to return a local path that
        Cloud Run couldn't access.
        """
        from backend.api.routes.audio_search import _download_and_start_processing
        import asyncio
        
        # Setup mock job with Redacted search result
        mock_job = Mock()
        mock_job.state_data = {
            'audio_search_results': [{
                'title': 'Unwanted',
                'artist': 'Avril Lavigne',
                'provider': 'Redacted',  # Torrent source
                'quality': 'FLAC 16bit CD',
            }]
        }
        mock_job.audio_search_artist = 'Avril Lavigne'
        mock_job.audio_search_title = 'Unwanted'
        mock_job_manager.get_job.return_value = mock_job
        
        # Create mock audio search service with remote client
        mock_audio_service = Mock()
        mock_audio_service.is_remote_enabled.return_value = True
        
        # Mock download to return GCS path
        mock_download_result = Mock()
        mock_download_result.filepath = "gs://bucket/uploads/job123/audio/Avril Lavigne - Unwanted.flac"
        mock_audio_service.download.return_value = mock_download_result
        
        # Create mock background tasks
        mock_bg_tasks = Mock()
        
        # Run the async function
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                _download_and_start_processing(
                    job_id="job123",
                    selection_index=0,
                    audio_search_service=mock_audio_service,
                    background_tasks=mock_bg_tasks,
                )
            )
        finally:
            loop.close()
        
        # CRITICAL: Verify download was called with gcs_path for remote torrent source
        mock_audio_service.download.assert_called_once()
        call_kwargs = mock_audio_service.download.call_args.kwargs
        
        # The gcs_path should be set for remote torrent downloads
        assert 'gcs_path' in call_kwargs
        assert call_kwargs['gcs_path'] == "uploads/job123/audio/"
    
    def test_local_youtube_download_does_not_pass_gcs_path(self, mock_job_manager, mock_storage_service):
        """Test that YouTube downloads don't use gcs_path (download locally, upload manually)."""
        from backend.api.routes.audio_search import _download_and_start_processing
        import asyncio
        import tempfile
        
        # Setup mock job with YouTube search result
        mock_job = Mock()
        mock_job.state_data = {
            'audio_search_results': [{
                'title': 'Unwanted',
                'artist': 'Avril Lavigne',
                'provider': 'YouTube',  # NOT a torrent source
                'quality': 'Opus 128kbps',
            }]
        }
        mock_job.audio_search_artist = 'Avril Lavigne'
        mock_job.audio_search_title = 'Unwanted'
        mock_job_manager.get_job.return_value = mock_job
        
        # Create mock audio search service with remote client (but YouTube doesn't use it)
        mock_audio_service = Mock()
        mock_audio_service.is_remote_enabled.return_value = True
        
        # Create a temp file to simulate downloaded file
        temp_file = tempfile.NamedTemporaryFile(suffix='.opus', delete=False)
        temp_file.write(b'fake audio data')
        temp_file.close()
        
        try:
            # Mock download to return local path
            mock_download_result = Mock()
            mock_download_result.filepath = temp_file.name
            mock_audio_service.download.return_value = mock_download_result
            
            # Create mock background tasks
            mock_bg_tasks = Mock()
            
            # Run the async function
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    _download_and_start_processing(
                        job_id="job456",
                        selection_index=0,
                        audio_search_service=mock_audio_service,
                        background_tasks=mock_bg_tasks,
                    )
                )
            finally:
                loop.close()
            
            # YouTube should NOT have gcs_path in kwargs
            mock_audio_service.download.assert_called_once()
            call_kwargs = mock_audio_service.download.call_args.kwargs
            
            # For YouTube, gcs_path should NOT be set (or should be None)
            assert call_kwargs.get('gcs_path') is None
            
            # Instead, storage service should be called to upload
            mock_storage_service.upload_fileobj.assert_called_once()
        finally:
            import os
            try:
                os.unlink(temp_file.name)
            except:
                pass
    
    def test_handles_gcs_path_response_correctly(self, mock_job_manager, mock_storage_service):
        """Test that GCS path responses are parsed correctly."""
        from backend.api.routes.audio_search import _download_and_start_processing
        import asyncio
        
        # Setup mock job with Redacted search result
        mock_job = Mock()
        mock_job.state_data = {
            'audio_search_results': [{
                'title': 'Test',
                'artist': 'Test Artist',
                'provider': 'Redacted',
                'quality': 'FLAC',
            }]
        }
        mock_job_manager.get_job.return_value = mock_job
        
        # Create mock audio search service
        mock_audio_service = Mock()
        mock_audio_service.is_remote_enabled.return_value = True
        
        # Mock download to return full GCS path
        mock_download_result = Mock()
        mock_download_result.filepath = "gs://karaoke-gen-bucket/uploads/job789/audio/test.flac"
        mock_audio_service.download.return_value = mock_download_result
        
        # Run the async function
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                _download_and_start_processing(
                    job_id="job789",
                    selection_index=0,
                    audio_search_service=mock_audio_service,
                    background_tasks=Mock(),
                )
            )
        finally:
            loop.close()
        
        # Verify job was updated with correct GCS path (without gs://bucket/ prefix)
        update_calls = mock_job_manager.update_job.call_args_list
        
        # Find the call that sets input_media_gcs_path
        gcs_path_set = False
        for call in update_calls:
            if 'input_media_gcs_path' in call.args[1]:
                gcs_path = call.args[1]['input_media_gcs_path']
                # The path stored should be the relative path, not the full gs:// URL
                assert gcs_path == "uploads/job789/audio/test.flac"
                gcs_path_set = True
                break
        
        assert gcs_path_set, "input_media_gcs_path was not set in job update"
    
    def test_remote_disabled_always_uses_local(self, mock_job_manager, mock_storage_service):
        """Test that when remote is disabled, even torrent sources use local download."""
        from backend.api.routes.audio_search import _download_and_start_processing
        import asyncio
        import tempfile
        
        # Setup mock job with Redacted search result
        mock_job = Mock()
        mock_job.state_data = {
            'audio_search_results': [{
                'title': 'Test',
                'artist': 'Test',
                'provider': 'Redacted',  # Torrent source, but remote is disabled
                'quality': 'FLAC',
            }]
        }
        mock_job_manager.get_job.return_value = mock_job
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(suffix='.flac', delete=False)
        temp_file.write(b'fake')
        temp_file.close()
        
        try:
            # Create mock audio search service WITHOUT remote client
            mock_audio_service = Mock()
            mock_audio_service.is_remote_enabled.return_value = False  # REMOTE DISABLED
            
            mock_download_result = Mock()
            mock_download_result.filepath = temp_file.name
            mock_audio_service.download.return_value = mock_download_result
            
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    _download_and_start_processing(
                        job_id="job_no_remote",
                        selection_index=0,
                        audio_search_service=mock_audio_service,
                        background_tasks=Mock(),
                    )
                )
            finally:
                loop.close()
            
            # When remote is disabled, gcs_path should NOT be passed
            mock_audio_service.download.assert_called_once()
            call_kwargs = mock_audio_service.download.call_args.kwargs
            assert call_kwargs.get('gcs_path') is None
            
            # And storage should upload manually
            mock_storage_service.upload_fileobj.assert_called_once()
        finally:
            import os
            try:
                os.unlink(temp_file.name)
            except:
                pass
