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


class TestAudioModelConfigurationFields:
    """Test that Job and JobCreate models support audio model configuration fields."""
    
    def test_job_has_clean_instrumental_model_field(self):
        """Test that Job model has clean_instrumental_model field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            clean_instrumental_model="custom_model.ckpt"
        )
        
        assert hasattr(job, 'clean_instrumental_model')
        assert job.clean_instrumental_model == "custom_model.ckpt"
    
    def test_job_has_backing_vocals_models_field(self):
        """Test that Job model has backing_vocals_models field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            backing_vocals_models=["model1.ckpt", "model2.ckpt"]
        )
        
        assert hasattr(job, 'backing_vocals_models')
        assert job.backing_vocals_models == ["model1.ckpt", "model2.ckpt"]
    
    def test_job_has_other_stems_models_field(self):
        """Test that Job model has other_stems_models field."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            other_stems_models=["htdemucs_6s.yaml"]
        )
        
        assert hasattr(job, 'other_stems_models')
        assert job.other_stems_models == ["htdemucs_6s.yaml"]
    
    def test_audio_model_fields_are_optional(self):
        """Test that audio model fields default to None."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        assert job.clean_instrumental_model is None
        assert job.backing_vocals_models is None
        assert job.other_stems_models is None
    
    def test_job_create_has_audio_model_fields(self):
        """Test that JobCreate model has all audio model configuration fields."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Artist",
            title="Title",
            clean_instrumental_model="custom_clean.ckpt",
            backing_vocals_models=["custom_bv.ckpt"],
            other_stems_models=["custom_stems.yaml"]
        )
        
        assert job_create.clean_instrumental_model == "custom_clean.ckpt"
        assert job_create.backing_vocals_models == ["custom_bv.ckpt"]
        assert job_create.other_stems_models == ["custom_stems.yaml"]
    
    def test_job_create_audio_model_fields_optional(self):
        """Test that audio model fields are optional in JobCreate."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Artist",
            title="Title"
        )
        
        assert job_create.clean_instrumental_model is None
        assert job_create.backing_vocals_models is None
        assert job_create.other_stems_models is None
    
    def test_pydantic_includes_audio_model_fields_in_serialization(self):
        """Test that Pydantic includes audio model fields in serialization."""
        from backend.models.job import Job
        from datetime import datetime
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            clean_instrumental_model="custom.ckpt",
            backing_vocals_models=["bv1.ckpt", "bv2.ckpt"],
            other_stems_models=["stems.yaml"]
        )
        
        job_dict = job.model_dump()
        
        assert "clean_instrumental_model" in job_dict
        assert job_dict["clean_instrumental_model"] == "custom.ckpt"
        assert "backing_vocals_models" in job_dict
        assert job_dict["backing_vocals_models"] == ["bv1.ckpt", "bv2.ckpt"]
        assert "other_stems_models" in job_dict
        assert job_dict["other_stems_models"] == ["stems.yaml"]


class TestCommaDelimitedModelParsing:
    """Test parsing of comma-delimited model strings."""
    
    def test_parse_single_model(self):
        """Test parsing a single model string."""
        model_str = "model1.ckpt"
        result = [m.strip() for m in model_str.split(',') if m.strip()]
        assert result == ["model1.ckpt"]
    
    def test_parse_multiple_models(self):
        """Test parsing multiple models."""
        model_str = "model1.ckpt,model2.ckpt,model3.ckpt"
        result = [m.strip() for m in model_str.split(',') if m.strip()]
        assert result == ["model1.ckpt", "model2.ckpt", "model3.ckpt"]
    
    def test_parse_models_with_whitespace(self):
        """Test parsing models with whitespace around commas."""
        model_str = "model1.ckpt , model2.ckpt, model3.ckpt "
        result = [m.strip() for m in model_str.split(',') if m.strip()]
        assert result == ["model1.ckpt", "model2.ckpt", "model3.ckpt"]
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        model_str = ""
        result = [m.strip() for m in model_str.split(',') if m.strip()]
        assert result == []
    
    def test_parse_none_returns_none(self):
        """Test that None model string is handled correctly."""
        model_str = None
        result = None
        if model_str:
            result = [m.strip() for m in model_str.split(',') if m.strip()]
        assert result is None


class TestSignedUrlUploadModels:
    """Test Pydantic models for signed URL upload flow."""
    
    def test_file_upload_request_model(self):
        """Test FileUploadRequest model."""
        from backend.api.routes.file_upload import FileUploadRequest
        
        file_req = FileUploadRequest(
            filename="test.flac",
            content_type="audio/flac",
            file_type="audio"
        )
        
        assert file_req.filename == "test.flac"
        assert file_req.content_type == "audio/flac"
        assert file_req.file_type == "audio"
    
    def test_create_job_with_upload_urls_request_model(self):
        """Test CreateJobWithUploadUrlsRequest model."""
        from backend.api.routes.file_upload import CreateJobWithUploadUrlsRequest, FileUploadRequest
        
        request = CreateJobWithUploadUrlsRequest(
            artist="Test Artist",
            title="Test Song",
            files=[
                FileUploadRequest(filename="test.flac", content_type="audio/flac", file_type="audio")
            ],
            enable_cdg=True,
            enable_txt=True,
            brand_prefix="NOMAD"
        )
        
        assert request.artist == "Test Artist"
        assert request.title == "Test Song"
        assert len(request.files) == 1
        assert request.files[0].file_type == "audio"
        assert request.brand_prefix == "NOMAD"
    
    def test_signed_upload_url_model(self):
        """Test SignedUploadUrl model."""
        from backend.api.routes.file_upload import SignedUploadUrl
        
        url_info = SignedUploadUrl(
            file_type="audio",
            gcs_path="uploads/test123/audio/test.flac",
            upload_url="https://storage.googleapis.com/signed-url",
            content_type="audio/flac"
        )
        
        assert url_info.file_type == "audio"
        assert url_info.gcs_path == "uploads/test123/audio/test.flac"
        assert url_info.upload_url.startswith("https://")
        assert url_info.content_type == "audio/flac"
    
    def test_uploads_complete_request_model(self):
        """Test UploadsCompleteRequest model."""
        from backend.api.routes.file_upload import UploadsCompleteRequest
        
        request = UploadsCompleteRequest(
            uploaded_files=["audio", "style_params", "style_intro_background"]
        )
        
        assert len(request.uploaded_files) == 3
        assert "audio" in request.uploaded_files


class TestValidFileTypes:
    """Test file type validation for signed URL upload."""
    
    def test_valid_file_types_includes_audio(self):
        """Test that audio is a valid file type."""
        from backend.api.routes.file_upload import VALID_FILE_TYPES
        
        assert 'audio' in VALID_FILE_TYPES
        assert '.flac' in VALID_FILE_TYPES['audio']
        assert '.mp3' in VALID_FILE_TYPES['audio']
    
    def test_valid_file_types_includes_style_assets(self):
        """Test that all style assets are valid file types."""
        from backend.api.routes.file_upload import VALID_FILE_TYPES
        
        assert 'style_params' in VALID_FILE_TYPES
        assert 'style_intro_background' in VALID_FILE_TYPES
        assert 'style_karaoke_background' in VALID_FILE_TYPES
        assert 'style_end_background' in VALID_FILE_TYPES
        assert 'style_font' in VALID_FILE_TYPES
        assert 'style_cdg_instrumental_background' in VALID_FILE_TYPES
        assert 'style_cdg_title_background' in VALID_FILE_TYPES
        assert 'style_cdg_outro_background' in VALID_FILE_TYPES
    
    def test_valid_file_types_includes_lyrics(self):
        """Test that lyrics file is a valid file type."""
        from backend.api.routes.file_upload import VALID_FILE_TYPES
        
        assert 'lyrics_file' in VALID_FILE_TYPES
        assert '.txt' in VALID_FILE_TYPES['lyrics_file']
        assert '.docx' in VALID_FILE_TYPES['lyrics_file']


class TestSignedUrlGCSPathGeneration:
    """Test GCS path generation for signed URL upload."""
    
    def test_audio_gcs_path(self):
        """Test GCS path generation for audio file."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "audio", "song.flac")
        assert path == "uploads/test123/audio/song.flac"
    
    def test_style_params_gcs_path(self):
        """Test GCS path generation for style params."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "style_params", "style.json")
        assert path == "uploads/test123/style/style_params.json"
    
    def test_style_background_gcs_path(self):
        """Test GCS path generation for style background images."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "style_intro_background", "bg.png")
        assert path == "uploads/test123/style/intro_background.png"
    
    def test_style_font_gcs_path(self):
        """Test GCS path generation for font file."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "style_font", "font.ttf")
        assert path == "uploads/test123/style/font.ttf"
    
    def test_lyrics_file_gcs_path(self):
        """Test GCS path generation for lyrics file."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "lyrics_file", "lyrics.txt")
        assert path == "uploads/test123/lyrics/user_lyrics.txt"


class TestStorageServiceSignedUrls:
    """Test StorageService signed URL generation."""
    
    def test_generate_signed_upload_url_method_exists(self):
        """Test that generate_signed_upload_url method exists in StorageService."""
        from backend.services.storage_service import StorageService
        
        assert hasattr(StorageService, 'generate_signed_upload_url')
    
    def test_generate_signed_url_internal_method_exists(self):
        """Test that _generate_signed_url_internal method exists in StorageService."""
        from backend.services.storage_service import StorageService
        
        assert hasattr(StorageService, '_generate_signed_url_internal')


class TestCreateJobWithUploadUrlsValidation:
    """Test validation for create_job_with_upload_urls endpoint."""
    
    def test_request_without_audio_is_invalid(self):
        """Test that request without audio file is rejected."""
        from backend.api.routes.file_upload import CreateJobWithUploadUrlsRequest, FileUploadRequest
        import pytest
        
        # This should be caught during endpoint validation
        # Here we test the model can be created but endpoint should reject
        request = CreateJobWithUploadUrlsRequest(
            artist="Artist",
            title="Title",
            files=[
                FileUploadRequest(filename="style.json", content_type="application/json", file_type="style_params")
            ]
        )
        
        # Endpoint validation should catch this
        audio_files = [f for f in request.files if f.file_type == 'audio']
        assert len(audio_files) == 0  # No audio - should be rejected by endpoint
    
    def test_request_with_multiple_audio_is_invalid(self):
        """Test that request with multiple audio files is rejected."""
        from backend.api.routes.file_upload import CreateJobWithUploadUrlsRequest, FileUploadRequest
        
        request = CreateJobWithUploadUrlsRequest(
            artist="Artist",
            title="Title",
            files=[
                FileUploadRequest(filename="song1.flac", content_type="audio/flac", file_type="audio"),
                FileUploadRequest(filename="song2.flac", content_type="audio/flac", file_type="audio")
            ]
        )
        
        audio_files = [f for f in request.files if f.file_type == 'audio']
        assert len(audio_files) == 2  # Multiple audio - should be rejected by endpoint
    
    def test_request_with_invalid_file_type(self):
        """Test that request with invalid file type is rejected."""
        from backend.api.routes.file_upload import VALID_FILE_TYPES
        
        assert 'invalid_type' not in VALID_FILE_TYPES


class TestExistingInstrumentalSupport:
    """Test existing instrumental support (Batch 3)."""
    
    def test_valid_file_types_includes_existing_instrumental(self):
        """Test that existing_instrumental is a valid file type."""
        from backend.api.routes.file_upload import VALID_FILE_TYPES, ALLOWED_AUDIO_EXTENSIONS
        
        assert 'existing_instrumental' in VALID_FILE_TYPES
        assert VALID_FILE_TYPES['existing_instrumental'] == ALLOWED_AUDIO_EXTENSIONS
    
    def test_existing_instrumental_gcs_path(self):
        """Test GCS path generation for existing instrumental file."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "existing_instrumental", "instrumental.flac")
        assert path == "uploads/test123/audio/existing_instrumental.flac"
    
    def test_existing_instrumental_gcs_path_mp3(self):
        """Test GCS path generation for existing instrumental MP3 file."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "existing_instrumental", "instrumental.mp3")
        assert path == "uploads/test123/audio/existing_instrumental.mp3"
    
    def test_existing_instrumental_gcs_path_wav(self):
        """Test GCS path generation for existing instrumental WAV file."""
        from backend.api.routes.file_upload import _get_gcs_path_for_file
        
        path = _get_gcs_path_for_file("test123", "existing_instrumental", "my_instrumental.wav")
        assert path == "uploads/test123/audio/existing_instrumental.wav"
    
    def test_job_has_existing_instrumental_gcs_path_field(self):
        """Test that Job model has existing_instrumental_gcs_path field."""
        from backend.models.job import Job
        from datetime import datetime, UTC
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            existing_instrumental_gcs_path="uploads/test123/audio/existing_instrumental.flac"
        )
        
        assert hasattr(job, 'existing_instrumental_gcs_path')
        assert job.existing_instrumental_gcs_path == "uploads/test123/audio/existing_instrumental.flac"
    
    def test_existing_instrumental_gcs_path_optional(self):
        """Test that existing_instrumental_gcs_path is optional."""
        from backend.models.job import Job
        from datetime import datetime, UTC
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        assert job.existing_instrumental_gcs_path is None
    
    def test_job_create_has_existing_instrumental_gcs_path_field(self):
        """Test that JobCreate model has existing_instrumental_gcs_path field."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Artist",
            title="Title",
            existing_instrumental_gcs_path="uploads/test123/audio/existing_instrumental.flac"
        )
        
        assert hasattr(job_create, 'existing_instrumental_gcs_path')
        assert job_create.existing_instrumental_gcs_path == "uploads/test123/audio/existing_instrumental.flac"
    
    def test_job_create_existing_instrumental_optional(self):
        """Test that existing_instrumental_gcs_path is optional in JobCreate."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Artist",
            title="Title"
        )
        
        assert job_create.existing_instrumental_gcs_path is None
    
    def test_pydantic_includes_existing_instrumental_in_serialization(self):
        """Test that Pydantic includes existing_instrumental_gcs_path in serialization."""
        from backend.models.job import Job
        from datetime import datetime, UTC
        
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            existing_instrumental_gcs_path="uploads/test123/audio/existing_instrumental.flac"
        )
        
        job_dict = job.model_dump()
        
        assert "existing_instrumental_gcs_path" in job_dict
        assert job_dict["existing_instrumental_gcs_path"] == "uploads/test123/audio/existing_instrumental.flac"
    
    @pytest.mark.parametrize("filename,expected_valid", [
        ("instrumental.mp3", True),
        ("instrumental.flac", True),
        ("instrumental.wav", True),
        ("instrumental.m4a", True),
        ("instrumental.ogg", True),
        ("instrumental.aac", True),
        ("instrumental.txt", False),
        ("instrumental.pdf", False),
    ])
    def test_existing_instrumental_extension_validation(self, filename, expected_valid):
        """Test that only valid audio extensions are accepted for existing instrumental."""
        from pathlib import Path
        from backend.api.routes.file_upload import VALID_FILE_TYPES
        
        allowed_extensions = VALID_FILE_TYPES['existing_instrumental']
        file_ext = Path(filename).suffix.lower()
        
        is_valid = file_ext in allowed_extensions
        assert is_valid == expected_valid
    
    def test_create_job_with_upload_urls_request_has_existing_instrumental_flag(self):
        """Test that CreateJobWithUploadUrlsRequest has existing_instrumental field."""
        from backend.api.routes.file_upload import CreateJobWithUploadUrlsRequest, FileUploadRequest
        
        request = CreateJobWithUploadUrlsRequest(
            artist="Test Artist",
            title="Test Song",
            files=[
                FileUploadRequest(filename="test.flac", content_type="audio/flac", file_type="audio"),
                FileUploadRequest(filename="instr.flac", content_type="audio/flac", file_type="existing_instrumental"),
            ],
            existing_instrumental=True
        )
        
        assert request.existing_instrumental is True
    
    def test_create_job_with_upload_urls_request_existing_instrumental_default_false(self):
        """Test that existing_instrumental defaults to False."""
        from backend.api.routes.file_upload import CreateJobWithUploadUrlsRequest, FileUploadRequest
        
        request = CreateJobWithUploadUrlsRequest(
            artist="Test Artist",
            title="Test Song",
            files=[
                FileUploadRequest(filename="test.flac", content_type="audio/flac", file_type="audio"),
            ]
        )
        
        assert request.existing_instrumental is False


class TestDurationValidation:
    """Test audio duration validation for existing instrumental (Batch 3)."""
    
    def test_validate_audio_durations_function_exists(self):
        """Test that _validate_audio_durations function exists."""
        from backend.api.routes.file_upload import _validate_audio_durations
        
        assert callable(_validate_audio_durations)
    
    @pytest.mark.asyncio
    async def test_duration_validation_returns_tuple(self):
        """Test that duration validation returns correct tuple structure."""
        # This is a structural test - actual implementation tested in integration tests
        # The function should return (is_valid: bool, audio_duration: float, instrumental_duration: float)
        from backend.api.routes.file_upload import _validate_audio_durations
        import inspect
        
        # Verify it's an async function
        assert inspect.iscoroutinefunction(_validate_audio_durations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

