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
    """Test AudioSearchResult dataclass."""
    
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


class TestAudioSearchServiceInit:
    """Test AudioSearchService initialization."""
    
    @patch.dict('os.environ', {'REDACTED_API_KEY': '', 'OPS_API_KEY': ''}, clear=False)
    def test_init_with_no_keys(self):
        """Test initialization without API keys."""
        # Pass explicit None to override environment
        service = AudioSearchService(redacted_api_key=None, ops_api_key=None)
        
        # When explicitly passed None, it should be None (not from env)
        assert service._redacted_api_key is None
        assert service._ops_api_key is None
        assert service._manager is None
    
    def test_init_with_keys(self):
        """Test initialization with API keys."""
        service = AudioSearchService(
            redacted_api_key="test_redacted_key",
            ops_api_key="test_ops_key",
        )
        
        assert service._redacted_api_key == "test_redacted_key"
        assert service._ops_api_key == "test_ops_key"
    
    def test_init_reads_from_environment(self):
        """Test initialization reads keys from environment variables."""
        import os
        
        # Just test that the service can be initialized
        service = AudioSearchService()
        
        # The service should have API keys from env or None
        assert service._manager is None  # Not yet initialized


class TestAudioSearchServiceSearch:
    """Test AudioSearchService.search() method."""
    
    @patch('backend.services.audio_search_service.AudioSearchService._get_manager')
    def test_search_returns_results(self, mock_get_manager):
        """Test search returns AudioSearchResult list."""
        # Mock the flacfetch result
        mock_result = Mock()
        mock_result.title = "Waterloo"
        mock_result.artist = "ABBA"
        mock_result.provider = "YouTube"
        mock_result.url = "https://youtube.com/watch?v=abc123"
        mock_result.duration = 180
        mock_result.quality = "FLAC"
        mock_result.id = "abc123"
        
        mock_manager = Mock()
        mock_manager.search.return_value = [mock_result]
        mock_get_manager.return_value = mock_manager
        
        service = AudioSearchService()
        results = service.search("ABBA", "Waterloo")
        
        assert len(results) == 1
        assert results[0].title == "Waterloo"
        assert results[0].artist == "ABBA"
        assert results[0].provider == "YouTube"
        assert results[0].index == 0
    
    @patch('backend.services.audio_search_service.AudioSearchService._get_manager')
    def test_search_no_results_raises_error(self, mock_get_manager):
        """Test search raises NoResultsError when no results."""
        mock_manager = Mock()
        mock_manager.search.return_value = []
        mock_get_manager.return_value = mock_manager
        
        service = AudioSearchService()
        
        with pytest.raises(NoResultsError) as exc_info:
            service.search("Unknown Artist", "Unknown Song")
        
        assert "No results found" in str(exc_info.value)
    
    @patch('backend.services.audio_search_service.AudioSearchService._get_manager')
    def test_search_multiple_results(self, mock_get_manager):
        """Test search returns multiple results with correct indices."""
        mock_results = []
        for i in range(3):
            mock_result = Mock()
            mock_result.title = f"Song {i}"
            mock_result.artist = "Artist"
            mock_result.provider = ["YouTube", "Redacted", "OPS"][i]
            mock_result.url = f"https://example.com/{i}"
            mock_result.duration = 180 + i * 10
            mock_result.quality = ["320kbps", "FLAC", "FLAC"][i]
            mock_result.id = str(i)
            mock_results.append(mock_result)
        
        mock_manager = Mock()
        mock_manager.search.return_value = mock_results
        mock_get_manager.return_value = mock_manager
        
        service = AudioSearchService()
        results = service.search("Artist", "Song")
        
        assert len(results) == 3
        assert results[0].index == 0
        assert results[1].index == 1
        assert results[2].index == 2


class TestAudioSearchServiceSelectBest:
    """Test AudioSearchService.select_best() method."""
    
    @patch('backend.services.audio_search_service.AudioSearchService._get_manager')
    def test_select_best_uses_manager(self, mock_get_manager):
        """Test select_best uses flacfetch's select_best."""
        # First need to do a search to populate cache
        mock_result = Mock()
        mock_result.title = "Waterloo"
        mock_result.artist = "ABBA"
        mock_result.provider = "YouTube"
        mock_result.url = "https://youtube.com/watch?v=abc123"
        mock_result.duration = 180
        mock_result.quality = "FLAC"
        mock_result.id = "abc123"
        
        mock_manager = Mock()
        mock_manager.search.return_value = [mock_result]
        mock_manager.select_best.return_value = mock_result
        mock_get_manager.return_value = mock_manager
        
        service = AudioSearchService()
        results = service.search("ABBA", "Waterloo")
        
        best_index = service.select_best(results)
        
        assert best_index == 0
    
    def test_select_best_empty_list_returns_zero(self):
        """Test select_best returns 0 for empty list."""
        service = AudioSearchService()
        
        best_index = service.select_best([])
        
        assert best_index == 0


class TestAudioSearchServiceDownload:
    """Test AudioSearchService.download() method."""
    
    @patch('backend.services.audio_search_service.AudioSearchService._get_manager')
    def test_download_without_search_raises_error(self, mock_get_manager):
        """Test download without prior search raises error."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        service = AudioSearchService()
        
        with pytest.raises(DownloadError) as exc_info:
            service.download(0, "/tmp")
        
        assert "No cached result" in str(exc_info.value)
    
    @patch('backend.services.audio_search_service.AudioSearchService._get_manager')
    def test_download_after_search(self, mock_get_manager):
        """Test download after search works."""
        import tempfile
        import os
        
        # Create a temp file to simulate downloaded file
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "test.flac")
        with open(temp_file, 'w') as f:
            f.write("test")
        
        mock_result = Mock()
        mock_result.title = "Waterloo"
        mock_result.artist = "ABBA"
        mock_result.provider = "YouTube"
        mock_result.url = "https://youtube.com/watch?v=abc123"
        mock_result.duration = 180
        mock_result.quality = "FLAC"
        mock_result.id = "abc123"
        
        mock_manager = Mock()
        mock_manager.search.return_value = [mock_result]
        mock_manager.download.return_value = temp_file
        mock_get_manager.return_value = mock_manager
        
        service = AudioSearchService()
        service.search("ABBA", "Waterloo")
        
        result = service.download(0, temp_dir)
        
        assert result.filepath == temp_file
        assert result.artist == "ABBA"
        assert result.title == "Waterloo"
        assert result.provider == "YouTube"
        
        # Cleanup
        os.remove(temp_file)
        os.rmdir(temp_dir)


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
    """
    
    def test_flacfetch_imports_work(self):
        """Test that all flacfetch imports in audio_search_service work.
        
        This test would have caught the YouTubeProvider -> YoutubeProvider rename.
        """
        # These imports match what audio_search_service.py does
        from flacfetch.core.manager import FetchManager
        from flacfetch.providers.youtube import YoutubeProvider
        from flacfetch.core.models import TrackQuery
        
        # Verify the classes exist and are callable
        assert FetchManager is not None
        assert YoutubeProvider is not None
        assert TrackQuery is not None
    
    def test_audio_search_service_can_initialize_manager(self):
        """Test AudioSearchService can initialize its FetchManager.
        
        This verifies the actual initialization code path works.
        """
        service = AudioSearchService(
            redacted_api_key=None,
            ops_api_key=None,
        )
        
        # This calls _get_manager() which does the actual imports
        manager = service._get_manager()
        
        assert manager is not None


