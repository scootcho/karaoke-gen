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
