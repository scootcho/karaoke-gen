"""
Shared pytest fixtures for backend tests.

Provides common mocks and test utilities across all test modules.

NOTE: Module-level mocks are NOT applied here to allow emulator tests to work.
Individual tests must mock dependencies as needed.
"""
import os
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime, UTC
from fastapi.testclient import TestClient

# Mock google.auth.default for unit tests if not using emulator
# This prevents DefaultCredentialsError during imports
if 'FIRESTORE_EMULATOR_HOST' not in os.environ:
    from unittest.mock import MagicMock
    
    # Only mock the default() function, not the entire module
    # This allows other google.auth imports to work normally
    try:
        import google.auth
        mock_credentials = MagicMock()
        mock_credentials.token = 'fake-token'
        mock_credentials.valid = True
        mock_credentials.universe_domain = 'googleapis.com'  # Required by google-cloud-storage
        mock_credentials.project_id = 'test-project'
        google.auth.default = MagicMock(return_value=(mock_credentials, 'test-project'))
    except ImportError:
        # If google.auth not installed, that's ok for some tests
        pass

from backend.models.job import Job, JobStatus, JobCreate


@pytest.fixture
def mock_auth_service():
    """Mock AuthService to accept test tokens."""
    with patch('backend.api.dependencies.get_auth_service') as mock_get_service:
        mock_service = MagicMock()
        # Accept "test-admin-token" as valid admin token
        mock_service.validate_token.return_value = (True, 'admin', 999, 'Valid token')
        mock_get_service.return_value = mock_service
        yield mock_service


@pytest.fixture
def auth_headers():
    """Get authentication headers for test requests."""
    return {
        "Authorization": "Bearer test-admin-token",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_firestore():
    """Mock Firestore client for unit tests."""
    # Mock at module level for unit tests
    with patch('google.cloud.firestore.Client') as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.fixture
def mock_storage_client():
    """Mock GCS Storage client for unit tests."""
    # Mock at module level for unit tests  
    with patch('google.cloud.storage.Client') as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        yield client


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient for worker service."""
    with patch('backend.services.worker_service.httpx.AsyncClient') as mock:
        client = AsyncMock()
        mock.return_value.__aenter__.return_value = client
        yield client


@pytest.fixture
def sample_job():
    """Create a sample Job instance for testing."""
    return Job(
        job_id="test123",
        status=JobStatus.PENDING,
        progress=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        artist="Test Artist",
        title="Test Song",
        url="https://youtube.com/watch?v=test"
    )


@pytest.fixture
def sample_job_create():
    """Create a sample JobCreate instance for testing."""
    return JobCreate(
        url="https://youtube.com/watch?v=test",
        artist="Test Artist",
        title="Test Song"
    )


@pytest.fixture
def test_client():
    """Create a FastAPI TestClient."""
    # Import here to avoid circular dependency
    from backend.main import app
    return TestClient(app)


def create_mock_job(**kwargs):
    """
    Factory function to create mock Job instances with custom fields.
    
    Args:
        **kwargs: Job fields to override defaults
        
    Returns:
        Job instance with specified fields
    """
    defaults = {
        "job_id": "test123",
        "status": JobStatus.PENDING,
        "progress": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC)
    }
    defaults.update(kwargs)
    return Job(**defaults)

