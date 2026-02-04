"""
Integration tests for admin job reset using REAL job fixture from production.

This test validates that:
1. update_job() returns None, not a boolean (the root cause of PR #371 bug)
2. The admin reset endpoint returns 200 when update_job returns None

Uses actual data from production job 984da08b which needed admin reset.

Run with: scripts/run-emulator-tests.sh
"""
import pytest
from datetime import datetime, UTC
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.tests.emulator.conftest import emulators_running

pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

if emulators_running():
    from backend.models.job import Job, JobStatus
    from backend.services.job_manager import JobManager
    from backend.services.firestore_service import FirestoreService
    from backend.api.routes.admin import router
    from backend.api.dependencies import require_admin


# Real state_data from production job 984da08b
REAL_JOB_STATE_DATA = {
    "backing_vocals_analysis": {"has_audible_content": True},
    "video_progress": {"stage": "running"},  # Stale progress
    "lyrics_complete": True,
    "audio_complete": True
}


class TestAdminResetBugFix:
    """
    Tests that prove the PR #371 bug fix works.

    The bug: admin reset endpoint returned 500 because:
        success = job_manager.update_job(job_id, updates)
        if not success:  # BUG: update_job returns None, not True!
            raise HTTPException(500)
    """

    def test_update_job_returns_none_not_boolean(self):
        """
        Prove that update_job() returns None, not a boolean.

        This is the root cause of the bug. Any code that does
        'if not update_job(...)' will always be True.
        """
        jm = JobManager()
        job_id = f"test-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.COMPLETE,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Mark Mallman",
            title="Minneapolis",
        )

        try:
            jm.firestore.create_job(job)

            # THE KEY TEST: update_job returns None
            result = jm.update_job(job_id, {"status": "pending"})

            assert result is None, (
                "update_job() must return None. "
                "Code checking 'if not success:' would always fail!"
            )
        finally:
            try:
                jm.firestore.delete_job(job_id)
            except Exception:
                pass

    def test_reset_endpoint_returns_200_with_none_return_value(self):
        """
        Test that reset endpoint returns 200 (not 500) when update_job
        returns None, matching the real API behavior.

        Before fix: endpoint checked 'if not success:' which was always True
        After fix: endpoint doesn't check return value
        """
        from backend.api.dependencies import AuthResult, UserType

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[require_admin] = lambda: AuthResult(
            is_valid=True,
            user_type=UserType.ADMIN,
            remaining_uses=999,
            message="OK",
            user_email="admin@test.com",
            is_admin=True,
        )
        client = TestClient(app)

        # Mock job with real production data
        mock_job = Mock(spec=Job)
        mock_job.job_id = "984da08b"
        mock_job.status = JobStatus.COMPLETE
        mock_job.artist = "Mark Mallman"
        mock_job.title = "Minneapolis"
        mock_job.theme_id = "nomad"
        mock_job.user_email = "madeforyou@nomadkaraoke.com"
        mock_job.file_urls = {"stems": {}, "lyrics": {}}
        mock_job.state_data = REAL_JOB_STATE_DATA.copy()
        mock_job.timeline = []

        with patch('backend.api.routes.admin.JobManager') as mock_jm:
            mock_jm.return_value.get_job.return_value = mock_job
            # KEY: return None (matching real API)
            mock_jm.return_value.update_job.return_value = None

            response = client.post(
                "/api/admin/jobs/984da08b/reset",
                json={"target_state": "pending"},
            )

            # This is the bug fix - before it was 500, now 200
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            assert response.json()["new_status"] == "pending"
