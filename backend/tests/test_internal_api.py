"""
Unit tests for internal.py API routes using FastAPI TestClient.

Internal routes are used for worker communication within Cloud Run.
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from backend.models.job import Job, JobStatus


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


class TestAudioWorkerEndpoint:
    """Tests for POST /api/internal/workers/audio."""
    
    def test_audio_worker_returns_200(self, client):
        """Test audio worker endpoint returns 200."""
        response = client.post(
            "/api/internal/workers/audio",
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_audio_worker_accepts_job_id(self, client):
        """Test audio worker accepts job_id in body."""
        response = client.post(
            "/api/internal/workers/audio",
            json={"job_id": "any-job-id"}
        )
        assert response.status_code == 200
    
    def test_audio_worker_requires_job_id(self, client):
        """Test audio worker requires job_id."""
        response = client.post(
            "/api/internal/workers/audio",
            json={}
        )
        assert response.status_code == 422


class TestLyricsWorkerEndpoint:
    """Tests for POST /api/internal/workers/lyrics."""
    
    def test_lyrics_worker_returns_200(self, client):
        """Test lyrics worker endpoint returns 200."""
        response = client.post(
            "/api/internal/workers/lyrics",
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_lyrics_worker_requires_job_id(self, client):
        """Test lyrics worker requires job_id."""
        response = client.post(
            "/api/internal/workers/lyrics",
            json={}
        )
        assert response.status_code == 422


class TestScreensWorkerEndpoint:
    """Tests for POST /api/internal/workers/screens."""
    
    def test_screens_worker_returns_200(self, client):
        """Test screens worker endpoint returns 200."""
        response = client.post(
            "/api/internal/workers/screens",
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_screens_worker_requires_job_id(self, client):
        """Test screens worker requires job_id."""
        response = client.post(
            "/api/internal/workers/screens",
            json={}
        )
        assert response.status_code == 422


class TestVideoWorkerEndpoint:
    """Tests for POST /api/internal/workers/video."""
    
    def test_video_worker_returns_200(self, client):
        """Test video worker endpoint returns 200."""
        response = client.post(
            "/api/internal/workers/video",
            json={"job_id": "test123"}
        )
        assert response.status_code == 200
    
    def test_video_worker_requires_job_id(self, client):
        """Test video worker requires job_id."""
        response = client.post(
            "/api/internal/workers/video",
            json={}
        )
        assert response.status_code == 422


class TestWorkerResponseFormat:
    """Tests for worker response format."""
    
    def test_audio_worker_response_contains_status(self, client):
        """Test audio worker response contains status."""
        response = client.post(
            "/api/internal/workers/audio",
            json={"job_id": "test123"}
        )
        data = response.json()
        assert "status" in data or "message" in data
    
    def test_lyrics_worker_response_contains_status(self, client):
        """Test lyrics worker response contains status."""
        response = client.post(
            "/api/internal/workers/lyrics",
            json={"job_id": "test123"}
        )
        data = response.json()
        assert "status" in data or "message" in data

