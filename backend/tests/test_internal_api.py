"""
Unit tests for internal.py API routes using FastAPI TestClient.

Internal routes are used for worker communication within Cloud Run.
These endpoints require admin authentication.
"""
import os
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from backend.models.job import Job, JobStatus


# Set test admin token for auth
os.environ.setdefault('ADMIN_TOKENS', 'test-admin-token')


@pytest.fixture
def client():
    """Create TestClient with mocked workers."""
    mock_creds = MagicMock()
    mock_creds.universe_domain = 'googleapis.com'
    
    # Mock the worker functions at the internal routes module level
    mock_audio = AsyncMock()
    mock_lyrics = AsyncMock()
    mock_screens = AsyncMock()
    mock_video = AsyncMock()
    
    with patch('backend.api.routes.internal.process_audio_separation', mock_audio), \
         patch('backend.api.routes.internal.process_lyrics_transcription', mock_lyrics), \
         patch('backend.api.routes.internal.generate_screens', mock_screens), \
         patch('backend.api.routes.internal.generate_video', mock_video), \
         patch('backend.services.firestore_service.firestore'), \
         patch('backend.services.storage_service.storage'), \
         patch('google.auth.default', return_value=(mock_creds, 'test-project')):
        from backend.main import app
        yield TestClient(app)


@pytest.fixture
def auth_headers():
    """Auth headers for internal API testing."""
    return {"Authorization": "Bearer test-admin-token"}


class TestAudioWorkerEndpoint:
    """Tests for POST /api/internal/workers/audio."""
    
    def test_audio_worker_returns_200(self, client, auth_headers):
        """Test audio worker endpoint returns 200 with auth."""
        response = client.post(
            "/api/internal/workers/audio",
            headers=auth_headers,
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_audio_worker_accepts_job_id(self, client, auth_headers):
        """Test audio worker accepts job_id in body."""
        response = client.post(
            "/api/internal/workers/audio",
            headers=auth_headers,
            json={"job_id": "any-job-id"}
        )
        assert response.status_code == 200
    
    def test_audio_worker_requires_job_id(self, client, auth_headers):
        """Test audio worker requires job_id."""
        response = client.post(
            "/api/internal/workers/audio",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 422
    
    def test_audio_worker_requires_auth(self, client):
        """Test audio worker requires authentication."""
        response = client.post(
            "/api/internal/workers/audio",
            json={"job_id": "test123"}
        )
        assert response.status_code == 401


class TestLyricsWorkerEndpoint:
    """Tests for POST /api/internal/workers/lyrics."""
    
    def test_lyrics_worker_returns_200(self, client, auth_headers):
        """Test lyrics worker endpoint returns 200 with auth."""
        response = client.post(
            "/api/internal/workers/lyrics",
            headers=auth_headers,
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_lyrics_worker_requires_job_id(self, client, auth_headers):
        """Test lyrics worker requires job_id."""
        response = client.post(
            "/api/internal/workers/lyrics",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 422
    
    def test_lyrics_worker_requires_auth(self, client):
        """Test lyrics worker requires authentication."""
        response = client.post(
            "/api/internal/workers/lyrics",
            json={"job_id": "test123"}
        )
        assert response.status_code == 401


class TestScreensWorkerEndpoint:
    """Tests for POST /api/internal/workers/screens."""
    
    def test_screens_worker_returns_200(self, client, auth_headers):
        """Test screens worker endpoint returns 200 with auth."""
        response = client.post(
            "/api/internal/workers/screens",
            headers=auth_headers,
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_screens_worker_requires_job_id(self, client, auth_headers):
        """Test screens worker requires job_id."""
        response = client.post(
            "/api/internal/workers/screens",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 422
    
    def test_screens_worker_requires_auth(self, client):
        """Test screens worker requires authentication."""
        response = client.post(
            "/api/internal/workers/screens",
            json={"job_id": "test123"}
        )
        assert response.status_code == 401


class TestVideoWorkerEndpoint:
    """Tests for POST /api/internal/workers/video."""
    
    def test_video_worker_returns_200(self, client, auth_headers):
        """Test video worker endpoint returns 200 with auth."""
        response = client.post(
            "/api/internal/workers/video",
            headers=auth_headers,
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_video_worker_requires_job_id(self, client, auth_headers):
        """Test video worker requires job_id."""
        response = client.post(
            "/api/internal/workers/video",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 422
    
    def test_video_worker_requires_auth(self, client):
        """Test video worker requires authentication."""
        response = client.post(
            "/api/internal/workers/video",
            json={"job_id": "test123"}
        )
        assert response.status_code == 401


class TestWorkerResponseFormat:
    """Tests for worker response format."""
    
    def test_audio_worker_response_contains_status(self, client, auth_headers):
        """Test audio worker response contains status."""
        response = client.post(
            "/api/internal/workers/audio",
            headers=auth_headers,
            json={"job_id": "test123"}
        )
        data = response.json()
        assert "status" in data or "message" in data
    
    def test_lyrics_worker_response_contains_status(self, client, auth_headers):
        """Test lyrics worker response contains status."""
        response = client.post(
            "/api/internal/workers/lyrics",
            headers=auth_headers,
            json={"job_id": "test123"}
        )
        data = response.json()
        assert "status" in data or "message" in data

