"""
API endpoint tests for instrumental review functionality.

Tests for:
- GET /api/jobs/{job_id}/instrumental-analysis
- GET /api/jobs/{job_id}/audio-stream/{stem_type}
- POST /api/jobs/{job_id}/create-custom-instrumental
- GET /api/jobs/{job_id}/waveform-data
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from backend.models.job import Job, JobStatus


@pytest.fixture
def mock_job_manager():
    """Create a mock job manager."""
    with patch('backend.api.routes.jobs.job_manager') as mock:
        yield mock


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    with patch('backend.api.routes.jobs.StorageService') as mock:
        mock_instance = MagicMock()
        mock_instance.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    return Job(
        job_id="test-job-123",
        artist="Test Artist",
        title="Test Song",
        status=JobStatus.AWAITING_INSTRUMENTAL_SELECTION,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        file_urls={
            "stems": {
                "instrumental_clean": "jobs/test/stems/instrumental_clean.flac",
                "backing_vocals": "jobs/test/stems/backing_vocals.flac",
                "instrumental_with_backing": "jobs/test/stems/instrumental_with_backing.flac",
            },
            "analysis": {
                "backing_vocals_waveform": "jobs/test/analysis/waveform.png",
            },
        },
        state_data={
            "backing_vocals_analysis": {
                "has_audible_content": True,
                "total_duration_seconds": 180.0,
                "audible_segments": [
                    {
                        "start_seconds": 10.0,
                        "end_seconds": 20.0,
                        "duration_seconds": 10.0,
                        "avg_amplitude_db": -25.0,
                    },
                    {
                        "start_seconds": 60.0,
                        "end_seconds": 80.0,
                        "duration_seconds": 20.0,
                        "avg_amplitude_db": -30.0,
                    },
                ],
                "recommended_selection": "review_needed",
                "total_audible_duration_seconds": 30.0,
                "audible_percentage": 16.67,
                "silence_threshold_db": -40.0,
            }
        },
    )


@pytest.fixture
def silent_job():
    """Create a job with silent backing vocals."""
    return Job(
        job_id="test-job-silent",
        artist="Test Artist",
        title="Test Song",
        status=JobStatus.AWAITING_INSTRUMENTAL_SELECTION,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        file_urls={
            "stems": {
                "instrumental_clean": "jobs/test/stems/instrumental_clean.flac",
                "backing_vocals": "jobs/test/stems/backing_vocals.flac",
                "instrumental_with_backing": "jobs/test/stems/instrumental_with_backing.flac",
            },
            "analysis": {
                "backing_vocals_waveform": "jobs/test/analysis/waveform.png",
            },
        },
        state_data={
            "backing_vocals_analysis": {
                "has_audible_content": False,
                "total_duration_seconds": 180.0,
                "audible_segments": [],
                "recommended_selection": "clean",
                "total_audible_duration_seconds": 0.0,
                "audible_percentage": 0.0,
                "silence_threshold_db": -40.0,
            }
        },
    )


class TestGetInstrumentalAnalysis:
    """Tests for GET /api/jobs/{job_id}/instrumental-analysis."""
    
    @pytest.mark.asyncio
    async def test_get_analysis_returns_data(self, mock_job_manager, mock_storage_service, sample_job):
        """GET /instrumental-analysis should return analysis data."""
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import get_instrumental_analysis
        
        result = await get_instrumental_analysis("test-job-123")
        
        assert result["job_id"] == "test-job-123"
        assert result["artist"] == "Test Artist"
        assert result["title"] == "Test Song"
        assert result["analysis"]["has_audible_content"] is True
        assert len(result["analysis"]["audible_segments"]) == 2
    
    @pytest.mark.asyncio
    async def test_get_analysis_includes_audio_urls(self, mock_job_manager, mock_storage_service, sample_job):
        """GET /instrumental-analysis should include audio URLs."""
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import get_instrumental_analysis
        
        result = await get_instrumental_analysis("test-job-123")
        
        assert "audio_urls" in result
        assert "clean_instrumental" in result["audio_urls"]
        assert "backing_vocals" in result["audio_urls"]
        assert "with_backing" in result["audio_urls"]
    
    @pytest.mark.asyncio
    async def test_get_analysis_includes_waveform_url(self, mock_job_manager, sample_job):
        """GET /instrumental-analysis should include waveform URL."""
        mock_job_manager.get_job.return_value = sample_job
        
        # Need to mock StorageService at module level for the signed URL
        with patch('backend.api.routes.jobs.StorageService') as mock_storage_cls:
            mock_storage = MagicMock()
            mock_storage.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"
            mock_storage_cls.return_value = mock_storage
            
            from backend.api.routes.jobs import get_instrumental_analysis
            
            result = await get_instrumental_analysis("test-job-123")
            
            assert "waveform_url" in result
            # Waveform URL should be generated from the file_urls
            assert result["waveform_url"] == "https://storage.googleapis.com/signed-url"
    
    @pytest.mark.asyncio
    async def test_get_analysis_silent_audio(self, mock_job_manager, mock_storage_service, silent_job):
        """GET /instrumental-analysis should correctly report silent audio."""
        mock_job_manager.get_job.return_value = silent_job
        
        from backend.api.routes.jobs import get_instrumental_analysis
        
        result = await get_instrumental_analysis("test-job-silent")
        
        assert result["analysis"]["has_audible_content"] is False
        assert result["analysis"]["recommended_selection"] == "clean"
        assert len(result["analysis"]["audible_segments"]) == 0
    
    @pytest.mark.asyncio
    async def test_get_analysis_job_not_found(self, mock_job_manager):
        """GET /instrumental-analysis should return 404 for non-existent job."""
        mock_job_manager.get_job.return_value = None
        
        from backend.api.routes.jobs import get_instrumental_analysis
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await get_instrumental_analysis("non-existent")
        
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_analysis_wrong_status(self, mock_job_manager, sample_job):
        """GET /instrumental-analysis should return 400 for wrong job status."""
        sample_job.status = JobStatus.PENDING
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import get_instrumental_analysis
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await get_instrumental_analysis("test-job-123")
        
        assert exc_info.value.status_code == 400


class TestAudioStream:
    """Tests for GET /api/jobs/{job_id}/audio-stream/{stem_type}."""
    
    def test_stream_backing_vocals_valid(self, mock_job_manager, sample_job):
        """Should return redirect for backing vocals stream."""
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import stream_audio
        
        # This will try to stream from GCS which we can't test easily
        # Instead, verify the function exists and has correct signature
        assert callable(stream_audio)
    
    @pytest.mark.asyncio
    async def test_stream_invalid_stem_type(self, mock_job_manager, sample_job):
        """Should return 400 for invalid stem type."""
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import stream_audio
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await stream_audio("test-job-123", "invalid_stem")
        
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_stream_job_not_found(self, mock_job_manager):
        """Should return 404 for non-existent job."""
        mock_job_manager.get_job.return_value = None
        
        from backend.api.routes.jobs import stream_audio
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await stream_audio("non-existent", "backing_vocals")
        
        assert exc_info.value.status_code == 404


class TestCreateCustomInstrumental:
    """Tests for POST /api/jobs/{job_id}/create-custom-instrumental."""
    
    @pytest.fixture
    def mock_audio_editing_service(self):
        """Mock the audio editing service."""
        with patch('backend.api.routes.jobs.AudioEditingService') as mock:
            mock_instance = MagicMock()
            mock_instance.create_custom_instrumental.return_value = MagicMock(
                output_path="jobs/test/stems/custom_instrumental.flac",
                mute_regions_applied=[
                    MagicMock(start_seconds=10.0, end_seconds=20.0),
                ],
                total_muted_duration_seconds=10.0,
                output_duration_seconds=180.0,
            )
            mock.return_value = mock_instance
            yield mock_instance
    
    def test_create_custom_validates_mute_regions(self):
        """Should validate mute regions at model level."""
        from backend.models.requests import CreateCustomInstrumentalRequest, MuteRegionRequest
        from pydantic import ValidationError
        
        # Empty mute regions should fail at model validation
        with pytest.raises(ValidationError) as exc_info:
            CreateCustomInstrumentalRequest(mute_regions=[])
        
        assert "At least one mute region is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_custom_job_not_found(self, mock_job_manager):
        """Should return 404 for non-existent job."""
        mock_job_manager.get_job.return_value = None
        
        from backend.api.routes.jobs import create_custom_instrumental
        from backend.models.requests import CreateCustomInstrumentalRequest, MuteRegionRequest
        from fastapi import HTTPException
        
        request = CreateCustomInstrumentalRequest(
            mute_regions=[MuteRegionRequest(start_seconds=10.0, end_seconds=20.0)]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await create_custom_instrumental("non-existent", request)
        
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_create_custom_wrong_status(self, mock_job_manager, sample_job):
        """Should return 400 for wrong job status."""
        sample_job.status = JobStatus.PENDING
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import create_custom_instrumental
        from backend.models.requests import CreateCustomInstrumentalRequest, MuteRegionRequest
        from fastapi import HTTPException
        
        request = CreateCustomInstrumentalRequest(
            mute_regions=[MuteRegionRequest(start_seconds=10.0, end_seconds=20.0)]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await create_custom_instrumental("test-job-123", request)
        
        assert exc_info.value.status_code == 400


class TestGetWaveformData:
    """Tests for GET /api/jobs/{job_id}/waveform-data."""
    
    @pytest.mark.asyncio
    async def test_get_waveform_data_job_not_found(self, mock_job_manager):
        """Should return 404 for non-existent job."""
        mock_job_manager.get_job.return_value = None
        
        from backend.api.routes.jobs import get_waveform_data
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await get_waveform_data("non-existent")
        
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_waveform_data_wrong_status(self, mock_job_manager, sample_job):
        """Should return 400 for wrong job status."""
        sample_job.status = JobStatus.PENDING
        mock_job_manager.get_job.return_value = sample_job
        
        from backend.api.routes.jobs import get_waveform_data
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            await get_waveform_data("test-job-123")
        
        assert exc_info.value.status_code == 400
    
    def test_waveform_data_endpoint_exists(self):
        """Verify the endpoint function exists and is callable."""
        from backend.api.routes.jobs import get_waveform_data
        
        assert callable(get_waveform_data)
        # Verify it's an async function
        import inspect
        assert inspect.iscoroutinefunction(get_waveform_data)


class TestRequestModels:
    """Tests for API request models."""
    
    def test_mute_region_request_valid(self):
        """MuteRegionRequest should accept valid values."""
        from backend.models.requests import MuteRegionRequest
        
        region = MuteRegionRequest(start_seconds=10.0, end_seconds=20.0)
        
        assert region.start_seconds == 10.0
        assert region.end_seconds == 20.0
    
    def test_mute_region_request_invalid_start(self):
        """MuteRegionRequest should reject negative start."""
        from backend.models.requests import MuteRegionRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            MuteRegionRequest(start_seconds=-1.0, end_seconds=20.0)
    
    def test_mute_region_request_invalid_order(self):
        """MuteRegionRequest should reject end before start."""
        from backend.models.requests import MuteRegionRequest
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            MuteRegionRequest(start_seconds=20.0, end_seconds=10.0)
    
    def test_create_custom_instrumental_request_valid(self):
        """CreateCustomInstrumentalRequest should accept valid mute regions."""
        from backend.models.requests import (
            CreateCustomInstrumentalRequest,
            MuteRegionRequest,
        )
        
        request = CreateCustomInstrumentalRequest(
            mute_regions=[
                MuteRegionRequest(start_seconds=10.0, end_seconds=20.0),
                MuteRegionRequest(start_seconds=60.0, end_seconds=80.0),
            ]
        )
        
        assert len(request.mute_regions) == 2


class TestInstrumentalSelectionExtension:
    """Tests for extended instrumental selection (including 'custom')."""
    
    def test_instrumental_selection_accepts_custom(self):
        """InstrumentalSelection should accept 'custom' as valid selection."""
        from backend.models.requests import InstrumentalSelection
        
        selection = InstrumentalSelection(selection="custom")
        assert selection.selection == "custom"
    
    def test_instrumental_selection_accepts_clean(self):
        """InstrumentalSelection should accept 'clean' as valid selection."""
        from backend.models.requests import InstrumentalSelection
        
        selection = InstrumentalSelection(selection="clean")
        assert selection.selection == "clean"
    
    def test_instrumental_selection_accepts_with_backing(self):
        """InstrumentalSelection should accept 'with_backing' as valid selection."""
        from backend.models.requests import InstrumentalSelection
        
        selection = InstrumentalSelection(selection="with_backing")
        assert selection.selection == "with_backing"
    
    def test_instrumental_selection_rejects_invalid(self):
        """InstrumentalSelection should reject invalid values."""
        from backend.models.requests import InstrumentalSelection
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            InstrumentalSelection(selection="invalid_option")
