"""
Integration tests using local GCP emulators.

These tests use real Firestore and GCS emulators running locally,
providing true integration testing without cloud resources or costs.

Run with: ./scripts/run-emulator-tests.sh

NOTE: These tests mock background workers to avoid race conditions.
The fixtures are defined in conftest.py in this directory.
"""
import pytest
import time

# Fixtures are loaded from conftest.py in this directory


class TestEmulatorBasics:
    """Basic emulator connectivity tests."""
    
    def test_health_endpoint(self, client):
        """Test health endpoint works."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test root endpoint works."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "karaoke-gen-backend"


class TestJobCreation:
    """Test job creation with Firestore emulator."""
    
    def test_create_job_simple(self, client, auth_headers):
        """Test creating a simple job."""
        response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "job_id" in data
        
    def test_create_job_with_metadata(self, client, auth_headers):
        """Test creating a job with artist/title."""
        response = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "url": "https://youtube.com/watch?v=test",
                "artist": "Test Artist",
                "title": "Test Song"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data


class TestJobRetrieval:
    """Test job retrieval from Firestore emulator."""
    
    def test_create_and_get_job(self, client, auth_headers):
        """Test creating and then retrieving a job."""
        # Create
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "url": "https://youtube.com/watch?v=abc123",
                "artist": "Test Artist",
                "title": "Test Song"
            }
        )
        assert create_resp.status_code == 200
        job_id = create_resp.json()["job_id"]
        
        # Small delay for emulator consistency
        time.sleep(0.2)
        
        # Retrieve
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        
        if get_resp.status_code != 200:
            print(f"GET failed: {get_resp.status_code} - {get_resp.text}")
        
        assert get_resp.status_code == 200
        
        job = get_resp.json()
        assert job["job_id"] == job_id
        assert job["status"] == "pending"
        assert job["artist"] == "Test Artist"
        assert job["title"] == "Test Song"
        
    def test_get_nonexistent_job(self, client, auth_headers):
        """Test fetching a job that doesn't exist."""
        response = client.get("/api/jobs/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404


class TestJobList:
    """Test listing jobs from Firestore."""
    
    def test_list_jobs(self, client, auth_headers):
        """Test listing jobs."""
        # Create a few jobs
        for i in range(3):
            client.post(
                "/api/jobs",
                headers=auth_headers,
                json={"url": f"https://youtube.com/watch?v=list{i}"}
            )
        
        time.sleep(0.2)
        
        # List
        response = client.get("/api/jobs", headers=auth_headers)
        assert response.status_code == 200
        
        jobs = response.json()
        assert isinstance(jobs, list)
        # We should have at least the 3 we just created
        assert len(jobs) >= 3


class TestJobDeletion:
    """Test job deletion."""
    
    def test_delete_job(self, client, auth_headers):
        """Test deleting a job."""
        # Create
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=delete-me"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Delete
        del_resp = client.delete(f"/api/jobs/{job_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        
        # Verify deleted
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 404


class TestJobUpdates:
    """Test job status updates."""
    
    def test_cancel_job(self, client, auth_headers):
        """Test cancelling a job."""
        # Create
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=cancel-me"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Cancel
        cancel_resp = client.post(
            f"/api/jobs/{job_id}/cancel",
            headers=auth_headers,
            json={"reason": "test cancellation"}
        )
        assert cancel_resp.status_code == 200
        
        # Verify cancelled
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        job = get_resp.json()
        assert job["status"] == "cancelled"


class TestFileUpload:
    """Test file upload with GCS emulator."""
    
    def test_upload_file(self, client, auth_headers):
        """Test uploading a file."""
        test_file_content = b"fake audio data for testing"
        
        response = client.post(
            "/api/jobs/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            files={"file": ("test.flac", test_file_content, "audio/flac")},
            data={"artist": "Upload Artist", "title": "Upload Song"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "job_id" in data
        
        job_id = data["job_id"]
        
        time.sleep(0.2)
        
        # Verify job created with upload data
        get_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        job = get_resp.json()
        assert job["artist"] == "Upload Artist"
        assert job["title"] == "Upload Song"
        assert "input_media_gcs_path" in job


class TestInternalEndpoints:
    """Test internal worker endpoints."""
    
    def test_internal_workers_exist(self, client, auth_headers):
        """Test that internal worker endpoints exist and respond."""
        # Create a job first
        create_resp = client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=worker-test"}
        )
        job_id = create_resp.json()["job_id"]
        
        time.sleep(0.2)
        
        # Test audio worker endpoint exists
        response = client.post(
            "/api/internal/workers/audio",
            headers=auth_headers,
            json={"job_id": job_id}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "started"


print("✅ Emulator integration tests ready to run")
