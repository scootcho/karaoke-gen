"""
Tests for native distribution services (Dropbox and Google Drive).

These tests verify the service interfaces without requiring actual
cloud credentials, using mocks to simulate API responses.
"""
import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open


class TestDropboxService:
    """Tests for the DropboxService class."""

    def test_module_imports(self):
        """Test that the module imports correctly."""
        from backend.services.dropbox_service import DropboxService, get_dropbox_service
        assert DropboxService is not None
        assert get_dropbox_service is not None

    def test_init_creates_instance(self):
        """Test that we can create a DropboxService instance."""
        from backend.services.dropbox_service import DropboxService
        service = DropboxService()
        assert service is not None
        assert service._client is None  # Client not initialized until first use
        assert service._is_configured is False

    def test_is_configured_returns_false_without_credentials(self):
        """Test that is_configured returns False when credentials are missing."""
        from backend.services.dropbox_service import DropboxService
        
        with patch.object(DropboxService, '_load_credentials', return_value=None):
            service = DropboxService()
            assert service.is_configured is False

    def test_is_configured_returns_true_with_credentials(self):
        """Test that is_configured returns True when credentials are present."""
        from backend.services.dropbox_service import DropboxService
        
        mock_creds = {"access_token": "test_token"}
        with patch.object(DropboxService, '_load_credentials', return_value=mock_creds):
            service = DropboxService()
            assert service.is_configured is True

    def test_get_next_brand_code_first_track(self):
        """Test brand code calculation when no existing tracks."""
        from backend.services.dropbox_service import DropboxService
        
        service = DropboxService()
        with patch.object(service, 'list_folders', return_value=[]):
            brand_code = service.get_next_brand_code("/test/path", "NOMAD")
            assert brand_code == "NOMAD-0001"

    def test_get_next_brand_code_sequential(self):
        """Test brand code calculation with existing tracks."""
        from backend.services.dropbox_service import DropboxService
        
        service = DropboxService()
        existing_folders = [
            "NOMAD-0001 - Artist1 - Song1",
            "NOMAD-0002 - Artist2 - Song2",
            "NOMAD-0005 - Artist3 - Song3",  # Gap in sequence
            "OTHER-0001 - Different Brand",  # Different brand
        ]
        with patch.object(service, 'list_folders', return_value=existing_folders):
            brand_code = service.get_next_brand_code("/test/path", "NOMAD")
            assert brand_code == "NOMAD-0006"

    def test_get_next_brand_code_different_prefix(self):
        """Test brand code calculation with different brand prefix."""
        from backend.services.dropbox_service import DropboxService
        
        service = DropboxService()
        existing_folders = [
            "NOMAD-0001 - Artist1 - Song1",
            "TEST-0010 - Artist2 - Song2",
        ]
        with patch.object(service, 'list_folders', return_value=existing_folders):
            brand_code = service.get_next_brand_code("/test/path", "TEST")
            assert brand_code == "TEST-0011"

    def test_factory_function_returns_instance(self):
        """Test that get_dropbox_service returns a service instance."""
        from backend.services.dropbox_service import get_dropbox_service
        
        service = get_dropbox_service()
        assert service is not None


class TestGoogleDriveService:
    """Tests for the GoogleDriveService class."""

    def test_module_imports(self):
        """Test that the module imports correctly."""
        from backend.services.gdrive_service import GoogleDriveService, get_gdrive_service
        assert GoogleDriveService is not None
        assert get_gdrive_service is not None

    def test_init_creates_instance(self):
        """Test that we can create a GoogleDriveService instance."""
        from backend.services.gdrive_service import GoogleDriveService
        service = GoogleDriveService()
        assert service is not None
        assert service._service is None  # Service not initialized until first use
        assert service._loaded is False

    def test_is_configured_returns_false_without_credentials(self):
        """Test that is_configured returns False when credentials are missing."""
        from backend.services.gdrive_service import GoogleDriveService
        
        with patch.object(GoogleDriveService, '_load_credentials', return_value=None):
            service = GoogleDriveService()
            assert service.is_configured is False

    def test_is_configured_returns_true_with_credentials(self):
        """Test that is_configured returns True when credentials are present."""
        from backend.services.gdrive_service import GoogleDriveService
        
        mock_creds = {
            "token": "test_token",
            "refresh_token": "test_refresh",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        }
        with patch.object(GoogleDriveService, '_load_credentials', return_value=mock_creds):
            service = GoogleDriveService()
            assert service.is_configured is True

    def test_factory_function_returns_singleton(self):
        """Test that get_gdrive_service returns a singleton."""
        from backend.services.gdrive_service import get_gdrive_service, _gdrive_service
        
        # Reset singleton
        import backend.services.gdrive_service as gdrive_module
        gdrive_module._gdrive_service = None
        
        service1 = get_gdrive_service()
        service2 = get_gdrive_service()
        assert service1 is service2


class TestJobModelDistributionFields:
    """Tests for distribution fields in Job model."""

    def test_job_model_has_dropbox_path_field(self):
        """Test that Job model has dropbox_path field."""
        from backend.models.job import Job, JobStatus
        from datetime import datetime
        
        job = Job(
            job_id="test-123",
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            dropbox_path="/Karaoke/Tracks-Organized",
        )
        assert job.dropbox_path == "/Karaoke/Tracks-Organized"

    def test_job_model_has_gdrive_folder_id_field(self):
        """Test that Job model has gdrive_folder_id field."""
        from backend.models.job import Job, JobStatus
        from datetime import datetime
        
        job = Job(
            job_id="test-123",
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            gdrive_folder_id="1abc123xyz",
        )
        assert job.gdrive_folder_id == "1abc123xyz"

    def test_job_model_distribution_fields_optional(self):
        """Test that distribution fields are optional."""
        from backend.models.job import Job, JobStatus
        from datetime import datetime
        
        job = Job(
            job_id="test-123",
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert job.dropbox_path is None
        assert job.gdrive_folder_id is None


class TestJobCreateDistributionFields:
    """Tests for distribution fields in JobCreate model."""

    def test_job_create_has_dropbox_path_field(self):
        """Test that JobCreate model has dropbox_path field."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Test Artist",
            title="Test Title",
            dropbox_path="/Karaoke/Tracks-Organized",
        )
        assert job_create.dropbox_path == "/Karaoke/Tracks-Organized"

    def test_job_create_has_gdrive_folder_id_field(self):
        """Test that JobCreate model has gdrive_folder_id field."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Test Artist",
            title="Test Title",
            gdrive_folder_id="1abc123xyz",
        )
        assert job_create.gdrive_folder_id == "1abc123xyz"

    def test_job_create_distribution_fields_optional(self):
        """Test that distribution fields are optional in JobCreate."""
        from backend.models.job import JobCreate
        
        job_create = JobCreate(
            artist="Test Artist",
            title="Test Title",
        )
        assert job_create.dropbox_path is None
        assert job_create.gdrive_folder_id is None


class TestFileUploadDistributionParams:
    """Tests for distribution parameters in file upload endpoint."""

    def test_endpoint_has_dropbox_path_parameter(self):
        """Test that upload endpoint signature includes dropbox_path parameter."""
        import inspect
        from backend.api.routes.file_upload import upload_and_create_job
        
        sig = inspect.signature(upload_and_create_job)
        param_names = list(sig.parameters.keys())
        
        assert "dropbox_path" in param_names

    def test_endpoint_has_gdrive_folder_id_parameter(self):
        """Test that upload endpoint signature includes gdrive_folder_id parameter."""
        import inspect
        from backend.api.routes.file_upload import upload_and_create_job
        
        sig = inspect.signature(upload_and_create_job)
        param_names = list(sig.parameters.keys())
        
        assert "gdrive_folder_id" in param_names

    def test_endpoint_dropbox_path_is_optional(self):
        """Test that dropbox_path parameter has a default value (Form(None))."""
        import inspect
        from backend.api.routes.file_upload import upload_and_create_job
        
        sig = inspect.signature(upload_and_create_job)
        param = sig.parameters.get("dropbox_path")
        
        assert param is not None
        # Default is Form(None), so check that it's not required
        assert param.default is not inspect.Parameter.empty

    def test_endpoint_gdrive_folder_id_is_optional(self):
        """Test that gdrive_folder_id parameter has a default value (Form(None))."""
        import inspect
        from backend.api.routes.file_upload import upload_and_create_job
        
        sig = inspect.signature(upload_and_create_job)
        param = sig.parameters.get("gdrive_folder_id")
        
        assert param is not None
        # Default is Form(None), so check that it's not required
        assert param.default is not inspect.Parameter.empty


class TestVideoWorkerDistribution:
    """Tests for distribution handling in video worker."""

    def test_handle_native_distribution_function_exists(self):
        """Test that _handle_native_distribution function exists."""
        from backend.workers import video_worker
        assert hasattr(video_worker, '_handle_native_distribution')

    def test_video_worker_imports_distribution_services(self):
        """Test that video worker can import distribution services."""
        # The services should be importable (even if credentials aren't available)
        try:
            from backend.services.dropbox_service import DropboxService
            from backend.services.gdrive_service import GoogleDriveService
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import distribution services: {e}")
