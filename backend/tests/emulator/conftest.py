"""
Fixtures for emulator integration tests.

These tests use REAL Firestore and GCS emulators, so we DON'T mock google.cloud modules.
"""
import pytest
import os
import requests
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# Set emulator environment variables (use 127.0.0.1 to force IPv4)
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"
os.environ["STORAGE_EMULATOR_HOST"] = "http://127.0.0.1:4443"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["GCS_BUCKET_NAME"] = "test-bucket"
os.environ["FIRESTORE_COLLECTION"] = "test-jobs"
os.environ["ENVIRONMENT"] = "test"
os.environ["ADMIN_TOKENS"] = "test-admin-token"

# Import app AFTER setting env vars
from backend.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_gcs_bucket():
    """Create GCS bucket in emulator before all tests."""
    try:
        response = requests.post(
            "http://127.0.0.1:4443/storage/v1/b",
            json={"name": "test-bucket"},
            params={"project": "test-project"}
        )
        if response.status_code in [200, 409]:
            print(f"✅ GCS bucket 'test-bucket' ready in emulator")
    except Exception as e:
        print(f"⚠️  GCS bucket setup failed: {e}")
    yield


@pytest.fixture(scope="session")
def mock_worker_service():
    """Mock worker service to prevent background tasks."""
    with patch("backend.api.routes.jobs.worker_service") as mock:
        mock.trigger_audio_worker = AsyncMock(return_value=True)
        mock.trigger_lyrics_worker = AsyncMock(return_value=True)
        mock.trigger_screens_worker = AsyncMock(return_value=True)
        mock.trigger_video_worker = AsyncMock(return_value=True)
        yield mock


@pytest.fixture(scope="session")
def client(mock_worker_service):
    """Create FastAPI test client with mocked workers."""
    with patch("backend.api.routes.file_upload.worker_service", mock_worker_service):
        return TestClient(app)


@pytest.fixture
def auth_headers():
    """Auth headers for testing."""
    return {"Authorization": "Bearer test-admin-token"}

