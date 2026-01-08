"""
Unit tests for Job Manager service.

Tests the job lifecycle management without requiring actual Firestore connection.
Uses mocking to isolate the business logic.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, UTC

# Mock Firestore before importing JobManager
import sys
sys.modules['google.cloud.firestore'] = MagicMock()

from backend.services.job_manager import JobManager
from backend.models.job import Job, JobCreate, JobStatus


@pytest.fixture
def mock_firestore_service():
    """Mock FirestoreService."""
    with patch('backend.services.job_manager.FirestoreService') as mock:
        service = Mock()
        mock.return_value = service
        yield service


@pytest.fixture
def job_manager(mock_firestore_service):
    """Create JobManager with mocked dependencies."""
    return JobManager()


class TestJobCreation:
    """Test job creation logic."""

    def test_create_job_requires_theme_id(self, job_manager, mock_firestore_service):
        """Test that jobs without theme_id are rejected."""
        job_create = JobCreate(
            artist="Test Artist",
            title="Test Song"
            # No theme_id - should fail
        )

        with pytest.raises(ValueError, match="theme_id is required"):
            job_manager.create_job(job_create)

        # Verify Firestore was NOT called
        mock_firestore_service.create_job.assert_not_called()

    def test_create_job_with_url(self, job_manager, mock_firestore_service):
        """Test creating a job with YouTube URL."""
        job_create = JobCreate(
            url="https://youtube.com/watch?v=test",
            artist="Test Artist",
            title="Test Song",
            theme_id="nomad"  # Required for all jobs
        )
        
        # The actual create_job method creates the job and returns it
        job = job_manager.create_job(job_create)
        
        assert job.job_id is not None
        assert job.status == JobStatus.PENDING
        assert job.url == "https://youtube.com/watch?v=test"
        assert job.artist == "Test Artist"
        assert job.title == "Test Song"
        assert job.progress == 0
        
        # Verify Firestore was called
        mock_firestore_service.create_job.assert_called_once()
    
    def test_create_job_without_url(self, job_manager, mock_firestore_service):
        """Test creating a job without URL (for file upload)."""
        job_create = JobCreate(
            artist="Test Artist",
            title="Test Song",
            theme_id="nomad"  # Required for all jobs
        )
        
        job = job_manager.create_job(job_create)
        
        assert job.artist == "Test Artist"
        assert job.title == "Test Song"
        assert job.url is None
    
    def test_create_job_generates_unique_id(self, job_manager, mock_firestore_service):
        """Test that each job gets a unique ID."""
        job_create = JobCreate(theme_id="nomad")  # Required for all jobs

        # Create multiple jobs
        ids = []
        for i in range(5):
            mock_firestore_service.create_job.return_value = Job(
                job_id=f"test{i}",
                status=JobStatus.PENDING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            job = job_manager.create_job(job_create)
            ids.append(job.job_id)
        
        # All IDs should be unique
        assert len(ids) == len(set(ids))
    
    def test_create_job_sets_initial_status(self, job_manager, mock_firestore_service):
        """Test that new jobs start with PENDING status."""
        job_create = JobCreate(theme_id="nomad")  # Required for all jobs

        mock_firestore_service.create_job.return_value = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        job = job_manager.create_job(job_create)
        
        assert job.status == JobStatus.PENDING
        assert job.progress == 0
    
    def test_create_job_with_distribution_settings(self, job_manager, mock_firestore_service):
        """Test that distribution settings are passed from JobCreate to Job.

        This was a bug where brand_prefix, dropbox_path, gdrive_folder_id, and
        discord_webhook_url were NOT being passed to the Job constructor.
        """
        job_create = JobCreate(
            artist="Test Artist",
            title="Test Song",
            theme_id="nomad",  # Required for all jobs
            brand_prefix="NOMAD",
            discord_webhook_url="https://discord.com/webhook/test",
            dropbox_path="/Karaoke/Tracks-Organized",
            gdrive_folder_id="1abc123xyz",
            enable_youtube_upload=True,
        )
        
        job = job_manager.create_job(job_create)
        
        # Verify distribution settings are passed through
        assert job.brand_prefix == "NOMAD"
        assert job.discord_webhook_url == "https://discord.com/webhook/test"
        assert job.dropbox_path == "/Karaoke/Tracks-Organized"
        assert job.gdrive_folder_id == "1abc123xyz"
        assert job.enable_youtube_upload is True
        
        # Verify Firestore was called with job containing these fields
        mock_firestore_service.create_job.assert_called_once()
        created_job = mock_firestore_service.create_job.call_args[0][0]
        assert created_job.brand_prefix == "NOMAD"
        assert created_job.dropbox_path == "/Karaoke/Tracks-Organized"


class TestJobRetrieval:
    """Test job retrieval logic."""
    
    def test_get_existing_job(self, job_manager, mock_firestore_service):
        """Test retrieving an existing job."""
        expected_job = Job(
            job_id="test123",
            status=JobStatus.SEPARATING_STAGE1,
            progress=25,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        mock_firestore_service.get_job.return_value = expected_job
        
        job = job_manager.get_job("test123")
        
        assert job.job_id == "test123"
        assert job.status == JobStatus.SEPARATING_STAGE1
        assert job.progress == 25
        
        mock_firestore_service.get_job.assert_called_once_with("test123")
    
    def test_get_nonexistent_job(self, job_manager, mock_firestore_service):
        """Test retrieving a nonexistent job returns None."""
        mock_firestore_service.get_job.return_value = None
        
        job = job_manager.get_job("nonexistent")
        
        assert job is None


class TestJobUpdate:
    """Test job update logic."""
    
    def test_update_job_status(self, job_manager, mock_firestore_service):
        """Test updating job status."""
        # Setup: job exists
        existing_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            progress=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        # Update status
        updates = {"status": JobStatus.SEPARATING_STAGE1, "progress": 25}
        job_manager.update_job("test123", updates)
        
        # Verify update was called
        mock_firestore_service.update_job.assert_called_once()
        call_args = mock_firestore_service.update_job.call_args
        assert call_args[0][0] == "test123"  # job_id
        assert "status" in call_args[0][1]  # updates dict
    
    def test_update_job_multiple_fields(self, job_manager, mock_firestore_service):
        """Test updating multiple fields at once."""
        existing_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            progress=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            timeline=[]
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        updates = {"status": JobStatus.SEPARATING_STAGE1, "progress": 25}
        job_manager.update_job("test123", updates)
        
        # Verify update was called
        call_args = mock_firestore_service.update_job.call_args
        updates_dict = call_args[0][1]
        assert "status" in updates_dict
        assert "progress" in updates_dict
    
    def test_update_input_media_gcs_path(self, job_manager, mock_firestore_service):
        """Test updating input_media_gcs_path field."""
        existing_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            progress=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        updates = {"input_media_gcs_path": "uploads/test123/file.flac"}
        job_manager.update_job("test123", updates)
        
        # Verify update was called with input_media_gcs_path
        call_args = mock_firestore_service.update_job.call_args
        updates_dict = call_args[0][1]
        assert "input_media_gcs_path" in updates_dict
        assert updates_dict["input_media_gcs_path"] == "uploads/test123/file.flac"


class TestJobStatusTransitions:
    """Test valid job status transitions."""
    
    def test_pending_to_downloading(self, job_manager, mock_firestore_service):
        """Test transition from PENDING to DOWNLOADING."""
        existing_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            progress=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        job_manager.update_job("test123", {"status": JobStatus.DOWNLOADING})
        
        # Should succeed (valid transition)
        mock_firestore_service.update_job.assert_called_once()
    
    def test_downloading_to_separating(self, job_manager, mock_firestore_service):
        """Test transition from DOWNLOADING to SEPARATING_STAGE1."""
        existing_job = Job(
            job_id="test123",
            status=JobStatus.DOWNLOADING,
            progress=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        job_manager.update_job("test123", {"status": JobStatus.SEPARATING_STAGE1})
        
        mock_firestore_service.update_job.assert_called_once()


class TestJobFailure:
    """Test job failure handling."""
    
    def test_mark_job_as_failed(self, job_manager, mock_firestore_service):
        """Test marking a job as failed."""
        error_message = "Audio separation failed"
        job_manager.mark_job_failed("test123", error_message)
        
        # mark_job_failed calls firestore.update_job_status
        mock_firestore_service.update_job_status.assert_called_once()
        call_args = mock_firestore_service.update_job_status.call_args
        assert call_args[1]['job_id'] == "test123"
        assert call_args[1]['status'] == JobStatus.FAILED
        assert 'error_message' in call_args[1]
    
    def test_mark_job_error(self, job_manager, mock_firestore_service):
        """Test marking a job with an error."""
        error_message = "Test error"
        job_manager.mark_job_error("test123", error_message)
        
        # mark_job_error calls firestore.update_job_status
        mock_firestore_service.update_job_status.assert_called_once()
        call_args = mock_firestore_service.update_job_status.call_args
        assert call_args[1]['job_id'] == "test123"
        assert call_args[1]['error_message'] == error_message


class TestJobDeletion:
    """Test job deletion logic."""
    
    def test_delete_job(self, job_manager, mock_firestore_service):
        """Test deleting a job."""
        existing_job = Job(
            job_id="test123",
            status=JobStatus.COMPLETE,
            progress=100,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            output_files={}  # Empty dict so iteration works
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        job_manager.delete_job("test123")
        
        # Verify delete was called
        mock_firestore_service.delete_job.assert_called_once_with("test123")
    
    def test_delete_job_with_files(self, job_manager, mock_firestore_service):
        """Test deleting a job and its files."""
        existing_job = Job(
            job_id="test123",
            status=JobStatus.COMPLETE,
            progress=100,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            output_files={}  # Empty dict so iteration works
        )
        mock_firestore_service.get_job.return_value = existing_job
        
        job_manager.delete_job("test123", delete_files=True)
        
        # Verify delete was called
        mock_firestore_service.delete_job.assert_called_once_with("test123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

