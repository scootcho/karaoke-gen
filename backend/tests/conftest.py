"""
Shared pytest fixtures for backend tests.

Provides common mocks and test utilities across all test modules.
"""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime, UTC
from fastapi.testclient import TestClient

# Mock Google Cloud modules before any imports
import sys
sys.modules['google.cloud.firestore'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()

from backend.models.job import Job, JobStatus, JobCreate


@pytest.fixture
def mock_firestore():
    """Mock Firestore client."""
    with patch('backend.services.firestore_service.firestore') as mock:
        client = MagicMock()
        mock.Client.return_value = client
        yield client


@pytest.fixture
def mock_storage_client():
    """Mock GCS Storage client."""
    with patch('backend.services.storage_service.storage') as mock:
        client = MagicMock()
        mock.Client.return_value = client
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

