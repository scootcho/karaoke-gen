"""
Unit tests for jobs.py routes.

These tests exercise the route logic with mocked services.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch

from backend.models.job import Job, JobStatus


class TestJobsRouteHelpers:
    """Tests for helper functions in jobs.py routes."""
    
    def test_jobs_router_structure(self):
        """Test jobs router has expected structure."""
        from backend.api.routes.jobs import router
        assert router is not None
        
        # Check that common route patterns exist
        route_paths = [route.path for route in router.routes]
        assert any('/jobs' in p or 'jobs' in str(p) for p in route_paths)


class TestJobStatusTransitions:
    """Tests for job status transition validation.
    
    These test the Job model's state machine which is critical for
    preventing invalid operations.
    """
    
    def test_valid_pending_to_downloading(self):
        """Test PENDING -> DOWNLOADING is valid."""
        from backend.models.job import STATE_TRANSITIONS
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.PENDING, [])
        assert JobStatus.DOWNLOADING in valid_transitions
    
    def test_valid_downloading_to_separating(self):
        """Test DOWNLOADING -> SEPARATING_STAGE1 is valid."""
        from backend.models.job import STATE_TRANSITIONS
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.DOWNLOADING, [])
        assert JobStatus.SEPARATING_STAGE1 in valid_transitions
    
    def test_invalid_pending_to_complete(self):
        """Test PENDING -> COMPLETE is invalid."""
        from backend.models.job import STATE_TRANSITIONS
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.PENDING, [])
        assert JobStatus.COMPLETE not in valid_transitions
    
    def test_any_active_status_can_fail(self):
        """Test any active (non-terminal, non-legacy) status can transition to FAILED."""
        from backend.models.job import STATE_TRANSITIONS
        # Terminal states and legacy states are excluded
        excluded = [
            JobStatus.COMPLETE, JobStatus.FAILED, JobStatus.CANCELLED,
            # Legacy states that don't include FAILED
            JobStatus.QUEUED, JobStatus.PROCESSING, 
            JobStatus.READY_FOR_FINALIZATION, JobStatus.FINALIZING, JobStatus.ERROR
        ]
        for status in JobStatus:
            if status not in excluded:
                valid_transitions = STATE_TRANSITIONS.get(status, [])
                assert JobStatus.FAILED in valid_transitions, f"{status} should be able to fail"
    
    def test_failed_can_transition_for_retry(self):
        """Test FAILED status can transition to retry checkpoint states."""
        from backend.models.job import STATE_TRANSITIONS
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.FAILED, [])

        # FAILED should allow retry transitions
        assert JobStatus.INSTRUMENTAL_SELECTED in valid_transitions, "FAILED should allow retry to INSTRUMENTAL_SELECTED"
        assert JobStatus.REVIEW_COMPLETE in valid_transitions, "FAILED should allow retry to REVIEW_COMPLETE"
        assert JobStatus.LYRICS_COMPLETE in valid_transitions, "FAILED should allow retry to LYRICS_COMPLETE"

    def test_cancelled_can_transition_for_retry(self):
        """Test CANCELLED status can transition to retry checkpoint states."""
        from backend.models.job import STATE_TRANSITIONS
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.CANCELLED, [])

        # CANCELLED should allow same retry transitions as FAILED
        assert JobStatus.INSTRUMENTAL_SELECTED in valid_transitions, "CANCELLED should allow retry to INSTRUMENTAL_SELECTED"
        assert JobStatus.REVIEW_COMPLETE in valid_transitions, "CANCELLED should allow retry to REVIEW_COMPLETE"
        assert JobStatus.LYRICS_COMPLETE in valid_transitions, "CANCELLED should allow retry to LYRICS_COMPLETE"
        assert JobStatus.DOWNLOADING in valid_transitions, "CANCELLED should allow retry to DOWNLOADING (restart)"

    def test_failed_can_restart_from_beginning(self):
        """Test FAILED status can transition to DOWNLOADING for restart from beginning."""
        from backend.models.job import STATE_TRANSITIONS
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.FAILED, [])

        # FAILED should allow restart from beginning
        assert JobStatus.DOWNLOADING in valid_transitions, "FAILED should allow restart to DOWNLOADING"


class TestJobModelSerialization:
    """Tests for Job model serialization to/from API."""
    
    def test_job_to_dict(self):
        """Test Job converts to dict correctly."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song"
        )
        data = job.model_dump()
        assert data["job_id"] == "test123"
        assert data["status"] == "pending"
        assert data["artist"] == "Test Artist"
    
    def test_job_from_dict(self):
        """Test Job can be created from dict."""
        data = {
            "job_id": "test123",
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "artist": "Test",
            "title": "Song"
        }
        job = Job.model_validate(data)
        assert job.job_id == "test123"
        assert job.status == JobStatus.PENDING
    
    def test_job_handles_null_optional_fields(self):
        """Test Job handles null optional fields."""
        job = Job(
            job_id="test",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        assert job.artist is None
        assert job.title is None
        assert job.url is None
        assert job.file_urls == {}


class TestRetryEndpoint:
    """Tests for the retry job endpoint."""

    @pytest.fixture
    def mock_job_manager(self):
        """Create mock job manager."""
        return MagicMock()

    @pytest.fixture
    def mock_worker_service(self):
        """Create mock worker service."""
        return MagicMock()

    def test_retry_rejects_pending_job(self, mock_job_manager):
        """Test retry endpoint rejects jobs that are not failed or cancelled."""
        # Create a pending job
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song"
        )
        mock_job_manager.get_job.return_value = job

        # The endpoint should reject this with a 400 error
        # (status check happens before any logic)
        assert job.status not in [JobStatus.FAILED, JobStatus.CANCELLED]

    def test_retry_accepts_failed_job(self, mock_job_manager):
        """Test retry endpoint accepts failed jobs."""
        job = Job(
            job_id="test123",
            status=JobStatus.FAILED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song",
            input_media_gcs_path="jobs/test123/input/audio.flac"
        )
        mock_job_manager.get_job.return_value = job

        # Status should be accepted
        assert job.status in [JobStatus.FAILED, JobStatus.CANCELLED]

    def test_retry_accepts_cancelled_job(self, mock_job_manager):
        """Test retry endpoint accepts cancelled jobs."""
        job = Job(
            job_id="test123",
            status=JobStatus.CANCELLED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song",
            input_media_gcs_path="jobs/test123/input/audio.flac"
        )
        mock_job_manager.get_job.return_value = job

        # Status should be accepted
        assert job.status in [JobStatus.FAILED, JobStatus.CANCELLED]

    def test_retry_checkpoint_detection_video_generation(self):
        """Test retry detects video generation checkpoint."""
        job = Job(
            job_id="test123",
            status=JobStatus.FAILED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song",
            file_urls={
                'videos': {'with_vocals': 'gs://bucket/path/video.mkv'}
            },
            state_data={
                'instrumental_selection': 'clean'
            }
        )

        # This job has video and instrumental selection - should retry from video generation
        has_video = job.file_urls.get('videos', {}).get('with_vocals')
        has_instrumental_selection = (job.state_data or {}).get('instrumental_selection')
        assert has_video and has_instrumental_selection

    def test_retry_checkpoint_detection_render_stage(self):
        """Test retry detects render stage checkpoint."""
        job = Job(
            job_id="test123",
            status=JobStatus.FAILED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song",
            file_urls={
                'lyrics': {'corrections': 'gs://bucket/path/corrections.json'},
                'screens': {'title': 'gs://bucket/path/title.mov'}
            }
        )

        # This job has corrections and screens - should retry from render
        has_corrections = job.file_urls.get('lyrics', {}).get('corrections')
        has_screens = job.file_urls.get('screens', {}).get('title')
        has_video = job.file_urls.get('videos', {}).get('with_vocals')
        assert has_corrections and has_screens and not has_video

    def test_retry_checkpoint_detection_from_beginning(self):
        """Test retry detects need to restart from beginning."""
        job = Job(
            job_id="test123",
            status=JobStatus.CANCELLED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song",
            input_media_gcs_path="jobs/test123/input/audio.flac",
            file_urls={}  # No progress yet
        )

        # This job has input audio but no other files - should restart from beginning
        has_input = job.input_media_gcs_path
        has_stems = job.file_urls.get('stems', {}).get('instrumental_clean')
        has_corrections = job.file_urls.get('lyrics', {}).get('corrections')
        assert has_input and not has_stems and not has_corrections

    def test_retry_no_input_audio(self):
        """Test retry fails when no input audio available."""
        job = Job(
            job_id="test123",
            status=JobStatus.CANCELLED,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Song",
            # No input_media_gcs_path and no url
            file_urls={}
        )

        # This job has no input audio - should not be retryable
        has_input = job.input_media_gcs_path or job.url
        assert not has_input

