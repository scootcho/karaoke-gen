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

