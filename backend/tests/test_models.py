"""
Unit tests for Pydantic models - simplified version that matches actual models.

Tests validate that our data models work correctly.
"""
import pytest
from datetime import datetime, UTC
from pydantic import ValidationError

from backend.models.job import (
    Job, JobCreate, JobStatus, TimelineEvent
)


class TestJobModel:
    """Test Job Pydantic model - the bug we just fixed!"""
    
    def test_input_media_gcs_path_field_exists(self):
        """
        Test that Job model has input_media_gcs_path field.
        
        This test would have caught the bug where we tried to use
        job.input_media_gcs_path but it wasn't defined in the model!
        """
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            input_media_gcs_path="uploads/test123/file.flac"
        )
        
        # This should NOT raise AttributeError
        assert hasattr(job, 'input_media_gcs_path')
        assert job.input_media_gcs_path == "uploads/test123/file.flac"
    
    def test_input_media_gcs_path_optional(self):
        """Test that input_media_gcs_path is optional."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        assert job.input_media_gcs_path is None
    
    def test_pydantic_includes_input_media_gcs_path_in_dict(self):
        """
        Test that Pydantic includes input_media_gcs_path in serialization.
        
        This ensures Pydantic doesn't silently ignore the field.
        """
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            input_media_gcs_path="uploads/test123/file.flac"
        )
        
        job_dict = job.model_dump()
        
        # Pydantic should include it
        assert "input_media_gcs_path" in job_dict
        assert job_dict["input_media_gcs_path"] == "uploads/test123/file.flac"
    
    def test_create_minimal_job(self):
        """Test creating a job with minimal required fields."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        assert job.job_id == "test123"
        assert job.status == JobStatus.PENDING
        assert job.progress == 0
        assert job.url is None
        assert job.input_media_gcs_path is None
    
    def test_create_job_with_url(self):
        """Test creating a job with YouTube URL."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            url="https://youtube.com/watch?v=test",
            artist="Test Artist",
            title="Test Song"
        )
        
        assert job.url == "https://youtube.com/watch?v=test"
        assert job.artist == "Test Artist"
        assert job.title == "Test Song"
    
    def test_create_job_with_uploaded_file(self):
        """Test creating a job with uploaded file."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            input_media_gcs_path="uploads/test123/file.flac",
            artist="Test Artist",
            title="Test Song"
        )
        
        assert job.input_media_gcs_path == "uploads/test123/file.flac"
        assert job.url is None


class TestJobCreate:
    """Test JobCreate validation model."""
    
    def test_create_with_url(self):
        """Test creating job with YouTube URL."""
        job_create = JobCreate(
            url="https://youtube.com/watch?v=test",
            artist="Test Artist",
            title="Test Song"
        )
        
        assert job_create.url == "https://youtube.com/watch?v=test"
        assert job_create.artist == "Test Artist"
        assert job_create.title == "Test Song"
    
    def test_create_minimal(self):
        """Test creating job with minimal fields."""
        job_create = JobCreate()
        
        assert job_create.url is None
        assert job_create.artist is None
        assert job_create.title is None


class TestJobStatus:
    """Test JobStatus enum."""
    
    def test_critical_statuses_defined(self):
        """Test that critical statuses exist."""
        critical_statuses = [
            "pending", "downloading",
            "separating_stage1", "separating_stage2", "audio_complete",
            "transcribing", "correcting", "lyrics_complete",
            "generating_screens", "applying_padding",
            "awaiting_review", "in_review", "review_complete",
            "awaiting_instrumental_selection", "instrumental_selected",
            "generating_video", "encoding", "packaging",
            "complete", "failed"
        ]
        
        actual_statuses = [status.value for status in JobStatus]
        
        for status in critical_statuses:
            assert status in actual_statuses, f"Missing critical status: {status}"


class TestTimelineEvent:
    """Test TimelineEvent model."""
    
    def test_create_timeline_event(self):
        """Test creating a timeline event."""
        event = TimelineEvent(
            status="pending",
            timestamp="2025-12-01T08:00:00Z",
            progress=0,
            message="Job created"
        )
        
        assert event.status == "pending"
        assert event.timestamp == "2025-12-01T08:00:00Z"
        assert event.progress == 0
        assert event.message == "Job created"
    
    def test_timeline_event_optional_fields(self):
        """Test that progress and message are optional."""
        event = TimelineEvent(
            status="pending",
            timestamp="2025-12-01T08:00:00Z"
        )
        
        assert event.progress is None
        assert event.message is None


class TestModelValidation:
    """Test model validation rules."""
    
    def test_invalid_job_status(self):
        """Test that invalid status is rejected."""
        with pytest.raises((ValidationError, ValueError)):
            Job(
                job_id="test123",
                status="invalid_status",  # Not a valid JobStatus
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
    
    def test_missing_required_fields(self):
        """Test that missing required fields are rejected."""
        with pytest.raises(ValidationError):
            Job(
                job_id="test123"
                # Missing required fields: status, created_at, updated_at
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

