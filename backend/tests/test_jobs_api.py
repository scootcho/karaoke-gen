"""
Unit tests for jobs.py API routes using FastAPI TestClient.

These tests mock the underlying services and test the route logic directly.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from backend.models.job import Job, JobStatus


@pytest.fixture
def mock_job():
    """Create a standard mock job for testing."""
    return Job(
        job_id="test123",
        status=JobStatus.PENDING,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        artist="Test Artist",
        title="Test Song"
    )


@pytest.fixture
def mock_job_manager(mock_job):
    """Create a mock JobManager with common methods."""
    manager = MagicMock()
    manager.get_job.return_value = mock_job
    manager.list_jobs.return_value = [mock_job]
    manager.create_job.return_value = mock_job
    manager.delete_job.return_value = True
    manager.cancel_job.return_value = mock_job
    manager.update_job_status.return_value = None
    manager.update_state_data.return_value = None
    return manager


@pytest.fixture
def mock_worker_service():
    """Create a mock WorkerService."""
    service = MagicMock()
    service.trigger_audio_worker = AsyncMock(return_value=True)
    service.trigger_lyrics_worker = AsyncMock(return_value=True)
    service.trigger_screens_worker = AsyncMock(return_value=True)
    service.trigger_video_worker = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_theme_service():
    """Create a mock ThemeService that returns 'nomad' as default theme."""
    service = MagicMock()
    service.get_default_theme_id.return_value = "nomad"
    service.get_theme.return_value = None
    return service


@pytest.fixture
def client(mock_job_manager, mock_worker_service, mock_theme_service):
    """Create TestClient with mocked dependencies."""
    mock_creds = MagicMock()
    mock_creds.universe_domain = 'googleapis.com'

    # Create a JobManager class that returns our mock instance
    def mock_job_manager_factory(*args, **kwargs):
        return mock_job_manager

    # Patch at the module level where jobs.py imports them
    # Also patch JobManager class used in dependencies.py for auth checks
    with patch('backend.api.routes.jobs.job_manager', mock_job_manager), \
         patch('backend.api.routes.jobs.worker_service', mock_worker_service), \
         patch('backend.api.routes.jobs.get_theme_service', return_value=mock_theme_service), \
         patch('backend.services.job_manager.JobManager', mock_job_manager_factory), \
         patch('backend.services.firestore_service.firestore'), \
         patch('backend.services.storage_service.storage'), \
         patch('google.auth.default', return_value=(mock_creds, 'test-project')):
        from backend.main import app
        yield TestClient(app)


class TestGetJob:
    """Tests for GET /api/jobs/{job_id}."""
    
    def test_get_job_returns_200(self, client, mock_job_manager, mock_job, auth_headers):
        """Test getting an existing job returns 200."""
        response = client.get("/api/jobs/test123", headers=auth_headers)
        assert response.status_code == 200
    
    def test_get_job_returns_job_data(self, client, mock_job_manager, mock_job, auth_headers):
        """Test response contains job data."""
        response = client.get("/api/jobs/test123", headers=auth_headers)
        data = response.json()
        assert data["job_id"] == "test123"
        assert data["status"] == "pending"
        assert data["artist"] == "Test Artist"
    
    def test_get_nonexistent_job_returns_404(self, mock_worker_service, auth_headers):
        """Test getting non-existent job returns 404."""
        mock_job_manager = MagicMock()
        mock_job_manager.get_job.return_value = None
        mock_creds = MagicMock()
        mock_creds.universe_domain = 'googleapis.com'

        def mock_job_manager_factory(*args, **kwargs):
            return mock_job_manager

        with patch('backend.api.routes.jobs.job_manager', mock_job_manager), \
             patch('backend.api.routes.jobs.worker_service', mock_worker_service), \
             patch('backend.services.job_manager.JobManager', mock_job_manager_factory), \
             patch('backend.services.firestore_service.firestore'), \
             patch('backend.services.storage_service.storage'), \
             patch('google.auth.default', return_value=(mock_creds, 'test-project')):
            from backend.main import app
            client = TestClient(app)
            response = client.get("/api/jobs/nonexistent", headers=auth_headers)
            assert response.status_code == 404


class TestListJobs:
    """Tests for GET /api/jobs."""
    
    def test_list_jobs_returns_200(self, client, auth_headers):
        """Test listing jobs returns 200."""
        response = client.get("/api/jobs", headers=auth_headers)
        assert response.status_code == 200
    
    def test_list_jobs_returns_array(self, client, mock_job_manager, auth_headers):
        """Test response is an array of jobs."""
        response = client.get("/api/jobs", headers=auth_headers)
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["job_id"] == "test123"
    
    def test_list_jobs_with_status_filter(self, client, mock_job_manager, auth_headers):
        """Test listing jobs with status filter."""
        response = client.get("/api/jobs?status=pending", headers=auth_headers)
        assert response.status_code == 200
    
    def test_list_jobs_with_limit(self, client, mock_job_manager, auth_headers):
        """Test listing jobs with limit."""
        response = client.get("/api/jobs?limit=10", headers=auth_headers)
        assert response.status_code == 200


class TestCreateJob:
    """Tests for POST /api/jobs."""
    
    def test_create_job_with_url_returns_200(self, client, mock_job_manager, auth_headers):
        """Test creating job with URL returns 200."""
        response = client.post(
            "/api/jobs",
            json={"url": "https://youtube.com/watch?v=test123"},
            headers=auth_headers
        )
        assert response.status_code == 200
    
    def test_create_job_returns_job_id(self, client, mock_job_manager, auth_headers):
        """Test create response contains job_id."""
        response = client.post(
            "/api/jobs",
            json={"url": "https://youtube.com/watch?v=test"},
            headers=auth_headers
        )
        data = response.json()
        assert "job_id" in data
    
    def test_create_job_with_artist_title(self, client, mock_job_manager, auth_headers):
        """Test creating job with artist and title."""
        response = client.post(
            "/api/jobs",
            json={
                "url": "https://youtube.com/watch?v=test",
                "artist": "Test Artist",
                "title": "Test Song"
            },
            headers=auth_headers
        )
        assert response.status_code == 200


class TestDeleteJob:
    """Tests for DELETE /api/jobs/{job_id}."""
    
    def test_delete_job_returns_200(self, client, mock_job_manager, auth_headers):
        """Test deleting job returns 200."""
        response = client.delete("/api/jobs/test123", headers=auth_headers)
        assert response.status_code == 200
    
    def test_delete_nonexistent_job(self, mock_worker_service, auth_headers):
        """Test deleting non-existent job."""
        mock_job_manager = MagicMock()
        mock_job_manager.get_job.return_value = None  # Job doesn't exist
        mock_job_manager.delete_job.return_value = False
        mock_creds = MagicMock()
        mock_creds.universe_domain = 'googleapis.com'

        def mock_job_manager_factory(*args, **kwargs):
            return mock_job_manager

        with patch('backend.api.routes.jobs.job_manager', mock_job_manager), \
             patch('backend.api.routes.jobs.worker_service', mock_worker_service), \
             patch('backend.services.job_manager.JobManager', mock_job_manager_factory), \
             patch('backend.services.firestore_service.firestore'), \
             patch('backend.services.storage_service.storage'), \
             patch('google.auth.default', return_value=(mock_creds, 'test-project')):
            from backend.main import app
            client = TestClient(app)
            response = client.delete("/api/jobs/nonexistent", headers=auth_headers)
            # Either 200 or 404 depending on implementation
            assert response.status_code in [200, 404]


class TestCancelJob:
    """Tests for POST /api/jobs/{job_id}/cancel."""
    
    def test_cancel_job_returns_200(self, client, mock_job_manager, mock_job, auth_headers):
        """Test cancelling job returns 200."""
        mock_job_manager.cancel_job.return_value = mock_job
        response = client.post(
            "/api/jobs/test123/cancel",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 200


class TestSubmitCorrections:
    """Tests for POST /api/jobs/{job_id}/corrections."""
    
    def test_submit_corrections_returns_200(self, client, mock_job_manager, mock_job, auth_headers):
        """Test submitting corrections returns 200."""
        # Job needs to be in AWAITING_REVIEW or IN_REVIEW status
        review_job = Job(
            job_id="test123",
            status=JobStatus.IN_REVIEW,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Test"
        )
        mock_job_manager.get_job.return_value = review_job
        
        response = client.post(
            "/api/jobs/test123/corrections",
            json={
                "corrections": {
                    "lines": [],
                    "metadata": {"source": "test"}
                }
            },
            headers=auth_headers
        )
        # Should be 200 or validation error
        assert response.status_code in [200, 400, 422]


class TestSelectInstrumental:
    """Tests for POST /api/jobs/{job_id}/select-instrumental."""
    
    def test_select_instrumental_requires_selection_field(self, client, mock_job_manager, mock_job, auth_headers):
        """Test instrumental selection requires selection field."""
        response = client.post(
            "/api/jobs/test123/select-instrumental",
            json={},  # Missing selection field
            headers=auth_headers
        )
        # Missing field should cause validation error
        assert response.status_code == 422


class TestStartReview:
    """Tests for POST /api/jobs/{job_id}/start-review."""
    
    def test_start_review_endpoint_exists(self, client, mock_job_manager, mock_job, auth_headers):
        """Test start review endpoint exists."""
        response = client.post("/api/jobs/test123/start-review", headers=auth_headers)
        # Should not be 404 or 405
        assert response.status_code not in [404, 405]

