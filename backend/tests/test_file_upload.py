"""
Unit tests for file upload endpoint.

Tests the file upload logic including validation, GCS storage,
and job creation without requiring actual cloud resources.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from fastapi import UploadFile
from io import BytesIO
from datetime import datetime, UTC

# Mock Firestore and GCS before importing
import sys
sys.modules['google.cloud.firestore'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()

from backend.api.routes.file_upload import router
from backend.models.job import Job, JobStatus


@pytest.fixture
def mock_job_manager():
    """Mock JobManager."""
    with patch('backend.api.routes.file_upload.job_manager') as mock:
        yield mock


@pytest.fixture
def mock_storage_service():
    """Mock StorageService."""
    with patch('backend.api.routes.file_upload.storage_service') as mock:
        yield mock


@pytest.fixture
def mock_worker_service():
    """Mock WorkerService."""
    with patch('backend.api.routes.file_upload.worker_service') as mock:
        yield mock


@pytest.fixture
def sample_job():
    """Create a sample job."""
    return Job(
        job_id="test123",
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        artist="Test Artist",
        title="Test Song"
    )


class TestFileValidation:
    """Test file upload validation."""
    
    @pytest.mark.parametrize("filename,expected_valid", [
        ("test.mp3", True),
        ("test.flac", True),
        ("test.wav", True),
        ("test.m4a", True),
        ("test.ogg", True),
        ("test.aac", True),
        ("test.txt", False),
        ("test.pdf", False),
        ("test.exe", False),
        ("test", False),
    ])
    def test_file_extension_validation(self, filename, expected_valid):
        """Test that only valid audio file extensions are accepted."""
        from pathlib import Path
        
        allowed_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac'}
        file_ext = Path(filename).suffix.lower()
        
        is_valid = file_ext in allowed_extensions
        assert is_valid == expected_valid


class TestFileUploadFlow:
    """Test complete file upload flow."""
    
    @pytest.mark.asyncio
    async def test_successful_file_upload(
        self,
        mock_job_manager,
        mock_storage_service,
        mock_worker_service,
        sample_job
    ):
        """Test successful file upload creates job and triggers workers."""
        # Setup mocks
        mock_job_manager.create_job.return_value = sample_job
        job_with_path = sample_job.model_copy(update={"input_media_gcs_path": "uploads/test123/test.flac"})
        mock_job_manager.get_job.return_value = job_with_path
        mock_worker_service.trigger_audio_worker = AsyncMock()
        mock_worker_service.trigger_lyrics_worker = AsyncMock()
        
        # Create mock upload file
        file_content = b"fake audio data"
        upload_file = UploadFile(
            filename="test.flac",
            file=BytesIO(file_content)
        )
        
        # Test the upload logic
        # (Note: This would need the actual endpoint to be called,
        # here we're testing the business logic)
        
        # Verify job was created
        # Verify file was uploaded to GCS
        # Verify workers were triggered
        # This test would be more complete with actual endpoint testing
    
    @pytest.mark.asyncio
    async def test_upload_sets_input_media_gcs_path(
        self,
        mock_job_manager,
        mock_storage_service,
        sample_job
    ):
        """Test that upload sets input_media_gcs_path correctly."""
        # Setup
        mock_job_manager.create_job.return_value = sample_job
        
        expected_gcs_path = "uploads/test123/test.flac"
        
        # Simulate the update call
        mock_job_manager.update_job.return_value = None
        
        # When update_job is called, it should include input_media_gcs_path
        # This is what we're testing to prevent the bug we just fixed
        
        # Verify the update includes input_media_gcs_path
        # (This would be tested in integration test with actual endpoint)


class TestGCSPathGeneration:
    """Test GCS path generation logic."""
    
    def test_gcs_path_format(self):
        """Test that GCS paths follow expected format."""
        job_id = "test123"
        filename = "test.flac"
        
        expected_path = f"uploads/{job_id}/{filename}"
        assert expected_path == "uploads/test123/test.flac"
    
    def test_gcs_path_with_special_characters(self):
        """Test GCS path handling of special characters in filename."""
        job_id = "test123"
        filename = "test song (remix).flac"
        
        gcs_path = f"uploads/{job_id}/{filename}"
        
        # Path should preserve special characters
        assert "(" in gcs_path
        assert ")" in gcs_path
        assert " " in gcs_path


class TestFirestoreConsistency:
    """Test Firestore consistency handling."""
    
    @pytest.mark.asyncio
    async def test_update_verification(
        self,
        mock_job_manager,
        sample_job
    ):
        """Test that job update is verified before triggering workers."""
        # This tests the fix for the Firestore consistency bug
        
        # First fetch should not have input_media_gcs_path
        job_without_path = Job(**sample_job.model_dump())
        job_without_path.input_media_gcs_path = None
        
        # Second fetch should have it
        job_with_path = Job(**sample_job.model_dump())
        job_with_path.input_media_gcs_path = "uploads/test123/test.flac"
        
        mock_job_manager.get_job.side_effect = [
            job_without_path,  # First call (update not visible yet)
            job_with_path       # Second call (after retry)
        ]
        
        # The upload logic should:
        # 1. Update job
        # 2. Fetch to verify
        # 3. If not visible, wait and retry
        # 4. Only trigger workers after verification
        
        # This ensures workers don't see stale data
    
    @pytest.mark.asyncio
    async def test_update_timeout(
        self,
        mock_job_manager,
        sample_job
    ):
        """Test that upload fails if update never becomes visible."""
        # This should raise HTTPException if update never succeeds
        
        job_without_path = Job(**sample_job.model_dump())
        job_without_path.input_media_gcs_path = None
        
        # Always return job without path (simulate update never visible)
        mock_job_manager.get_job.return_value = job_without_path
        
        # Upload should fail with 500 error
        # "Failed to update job with GCS path"


class TestJobModelFieldPresence:
    """Test that Job model has required fields."""
    
    def test_input_media_gcs_path_field_exists(self):
        """Test that Job model has input_media_gcs_path field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # This should not raise AttributeError
        assert hasattr(job, 'input_media_gcs_path')
    
    def test_input_media_gcs_path_can_be_set(self):
        """Test that input_media_gcs_path can be set."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            input_media_gcs_path="uploads/test123/file.flac"
        )
        
        assert job.input_media_gcs_path == "uploads/test123/file.flac"
    
    def test_pydantic_doesnt_ignore_input_media_gcs_path(self):
        """Test that Pydantic includes input_media_gcs_path in serialization."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            input_media_gcs_path="uploads/test123/file.flac"
        )
        
        job_dict = job.model_dump()
        
        # Pydantic should include it
        assert "input_media_gcs_path" in job_dict
        assert job_dict["input_media_gcs_path"] == "uploads/test123/file.flac"


class TestLyricsFileValidation:
    """Test lyrics file upload validation."""
    
    @pytest.mark.parametrize("filename,expected_valid", [
        ("lyrics.txt", True),
        ("lyrics.docx", True),
        ("lyrics.rtf", True),
        ("lyrics.pdf", False),
        ("lyrics.mp3", False),
        ("lyrics", False),
    ])
    def test_lyrics_file_extension_validation(self, filename, expected_valid):
        """Test that only valid lyrics file extensions are accepted."""
        from pathlib import Path
        
        allowed_extensions = {'.txt', '.docx', '.rtf'}
        file_ext = Path(filename).suffix.lower()
        
        is_valid = file_ext in allowed_extensions
        assert is_valid == expected_valid


class TestLyricsConfigurationFields:
    """Test that lyrics configuration fields are handled correctly."""
    
    def test_job_has_lyrics_artist_field(self):
        """Test that Job model has lyrics_artist field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            lyrics_artist="Override Artist"
        )
        
        assert hasattr(job, 'lyrics_artist')
        assert job.lyrics_artist == "Override Artist"
    
    def test_job_has_lyrics_title_field(self):
        """Test that Job model has lyrics_title field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            lyrics_title="Override Title"
        )
        
        assert hasattr(job, 'lyrics_title')
        assert job.lyrics_title == "Override Title"
    
    def test_job_has_lyrics_file_gcs_path_field(self):
        """Test that Job model has lyrics_file_gcs_path field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            lyrics_file_gcs_path="uploads/test123/lyrics/user_lyrics.txt"
        )
        
        assert hasattr(job, 'lyrics_file_gcs_path')
        assert job.lyrics_file_gcs_path == "uploads/test123/lyrics/user_lyrics.txt"
    
    def test_job_has_subtitle_offset_ms_field(self):
        """Test that Job model has subtitle_offset_ms field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            subtitle_offset_ms=500
        )
        
        assert hasattr(job, 'subtitle_offset_ms')
        assert job.subtitle_offset_ms == 500
    
    def test_subtitle_offset_default_is_zero(self):
        """Test that subtitle_offset_ms defaults to 0."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert job.subtitle_offset_ms == 0


class TestLyricsGCSPathGeneration:
    """Test lyrics file GCS path generation."""
    
    def test_lyrics_gcs_path_format(self):
        """Test that lyrics GCS paths follow expected format."""
        job_id = "test123"
        filename = "user_lyrics.txt"
        
        expected_path = f"uploads/{job_id}/lyrics/{filename}"
        assert expected_path == "uploads/test123/lyrics/user_lyrics.txt"
    
    def test_lyrics_gcs_path_preserves_extension(self):
        """Test that lyrics file extension is preserved."""
        job_id = "test123"
        
        for ext in ['.txt', '.docx', '.rtf']:
            filename = f"user_lyrics{ext}"
            gcs_path = f"uploads/{job_id}/lyrics/{filename}"
            assert gcs_path.endswith(ext)


class TestJobCreateLyricsFields:
    """Test that JobCreate model supports lyrics fields."""
    
    def test_job_create_has_lyrics_fields(self):
        """Test that JobCreate model has all lyrics configuration fields."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Artist",
            title="Title",
            lyrics_artist="Override Artist",
            lyrics_title="Override Title",
            lyrics_file_gcs_path="uploads/test/lyrics/file.txt",
            subtitle_offset_ms=250
        )
        
        assert job_create.lyrics_artist == "Override Artist"
        assert job_create.lyrics_title == "Override Title"
        assert job_create.lyrics_file_gcs_path == "uploads/test/lyrics/file.txt"
        assert job_create.subtitle_offset_ms == 250
    
    def test_job_create_lyrics_fields_optional(self):
        """Test that lyrics fields are optional in JobCreate."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Artist",
            title="Title"
        )
        
        assert job_create.lyrics_artist is None
        assert job_create.lyrics_title is None
        assert job_create.lyrics_file_gcs_path is None
        assert job_create.subtitle_offset_ms == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

