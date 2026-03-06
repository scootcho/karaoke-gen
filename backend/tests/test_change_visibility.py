"""
Tests for the visibility change service.

Tests validation logic and the two visibility change flows:
- Public -> Private (fast redistribution)
- Private -> Public (full re-processing)
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace

from backend.services.visibility_change_service import VisibilityChangeService


def _make_job(
    job_id="test-123",
    status="complete",
    is_private=False,
    tenant_id="",
    user_email="user@example.com",
    state_data=None,
):
    """Create a mock job object for testing."""
    return SimpleNamespace(
        job_id=job_id,
        status=status,
        is_private=is_private,
        tenant_id=tenant_id,
        user_email=user_email,
        state_data=state_data or {},
        artist="Test Artist",
        title="Test Song",
        outputs_deleted_at=None,
        dropbox_path="/Tracks-Organized",
        file_urls={"finals": {"lossy_4k_mp4": "gs://test/4k.mp4"}},
    )


class TestValidation:
    """Test validation logic for visibility changes."""

    def setup_method(self):
        self.service = VisibilityChangeService(job_manager=MagicMock())

    def test_validates_job_exists(self):
        error = self.service.validate_change(None, "user@example.com", False, "private")
        assert error == "Job not found"

    def test_validates_complete_status(self):
        job = _make_job(status="generating_video")
        error = self.service.validate_change(job, "user@example.com", False, "private")
        assert "completed jobs" in error

    def test_validates_not_tenant_job(self):
        job = _make_job(tenant_id="vocalstar")
        error = self.service.validate_change(job, "user@example.com", False, "private")
        assert "tenant" in error

    def test_validates_different_visibility(self):
        job = _make_job(is_private=True)
        error = self.service.validate_change(job, "user@example.com", False, "private")
        assert "already private" in error

    def test_validates_same_visibility_public(self):
        job = _make_job(is_private=False)
        error = self.service.validate_change(job, "user@example.com", False, "public")
        assert "already public" in error

    def test_validates_ownership(self):
        job = _make_job(user_email="owner@example.com")
        error = self.service.validate_change(job, "other@example.com", False, "private")
        assert "your own jobs" in error

    def test_admin_can_change_any_job(self):
        job = _make_job(user_email="owner@example.com")
        error = self.service.validate_change(job, "admin@example.com", True, "private")
        assert error is None

    def test_owner_can_change_own_job(self):
        job = _make_job(user_email="user@example.com")
        error = self.service.validate_change(job, "user@example.com", False, "private")
        assert error is None

    def test_validates_no_concurrent_change(self):
        job = _make_job(state_data={"visibility_change_in_progress": True})
        error = self.service.validate_change(job, "user@example.com", False, "private")
        assert "already in progress" in error

    def test_valid_public_to_private(self):
        job = _make_job(is_private=False)
        error = self.service.validate_change(job, "user@example.com", False, "private")
        assert error is None

    def test_valid_private_to_public(self):
        job = _make_job(is_private=True)
        error = self.service.validate_change(job, "user@example.com", False, "public")
        assert error is None


class TestChangeToPrivate:
    """Test public -> private visibility change."""

    @pytest.mark.asyncio
    async def test_calls_redistribute(self):
        mock_job_manager = MagicMock()
        mock_job_ref = MagicMock()
        mock_job_manager.firestore.db.collection.return_value.document.return_value = mock_job_ref

        service = VisibilityChangeService(job_manager=mock_job_manager)
        job = _make_job(is_private=False, state_data={
            "youtube_url": "https://youtube.com/watch?v=abc",
            "brand_code": "NOMAD-0001",
            "dropbox_link": "https://dropbox.com/test",
        })

        with patch("backend.services.visibility_change_service.VisibilityChangeService._delete_distributed_outputs", new_callable=AsyncMock) as mock_delete, \
             patch("backend.workers.video_worker.redistribute_video", new_callable=AsyncMock, return_value=True) as mock_redist:

            result = await service.change_to_private("test-123", job, "user@example.com")

            assert result["status"] == "success"
            assert result["reprocessing_required"] is False
            mock_delete.assert_called_once_with("test-123", job, keep_gcs_finals=True)
            mock_redist.assert_called_once_with("test-123")

    @pytest.mark.asyncio
    async def test_sets_is_private_true(self):
        mock_job_manager = MagicMock()
        mock_job_ref = MagicMock()
        mock_job_manager.firestore.db.collection.return_value.document.return_value = mock_job_ref

        service = VisibilityChangeService(job_manager=mock_job_manager)
        job = _make_job(is_private=False, state_data={})

        with patch("backend.services.visibility_change_service.VisibilityChangeService._delete_distributed_outputs", new_callable=AsyncMock), \
             patch("backend.workers.video_worker.redistribute_video", new_callable=AsyncMock, return_value=True):

            await service.change_to_private("test-123", job, "user@example.com")

            # Check that is_private was set to True in one of the update calls
            update_calls = mock_job_ref.update.call_args_list
            found_private_update = any(
                call.args[0].get("is_private") is True
                for call in update_calls
            )
            assert found_private_update


class TestChangeToPublic:
    """Test private -> public visibility change."""

    @pytest.mark.asyncio
    async def test_triggers_screens_worker(self):
        mock_job_manager = MagicMock()
        mock_job_ref = MagicMock()
        mock_job_manager.firestore.db.collection.return_value.document.return_value = mock_job_ref

        service = VisibilityChangeService(job_manager=mock_job_manager)
        job = _make_job(is_private=True, state_data={
            "brand_code": "NOMADNP-0001",
            "dropbox_link": "https://dropbox.com/test",
        })

        with patch("backend.services.visibility_change_service.VisibilityChangeService._delete_distributed_outputs", new_callable=AsyncMock), \
             patch("backend.services.visibility_change_service.StorageService") as mock_storage_cls, \
             patch("backend.services.worker_service.get_worker_service") as mock_worker_svc:

            mock_storage = MagicMock()
            mock_storage_cls.return_value = mock_storage
            mock_worker = MagicMock()
            mock_worker.trigger_screens_worker = AsyncMock(return_value=True)
            mock_worker_svc.return_value = mock_worker

            result = await service.change_to_public("test-123", job, "user@example.com")

            assert result["status"] == "processing"
            assert result["reprocessing_required"] is True
            mock_worker.trigger_screens_worker.assert_called_once_with("test-123")

    @pytest.mark.asyncio
    async def test_resets_styles_to_nomad_theme(self):
        mock_job_manager = MagicMock()
        mock_job_ref = MagicMock()
        mock_job_manager.firestore.db.collection.return_value.document.return_value = mock_job_ref

        service = VisibilityChangeService(job_manager=mock_job_manager)
        job = _make_job(is_private=True, state_data={})

        with patch("backend.services.visibility_change_service.VisibilityChangeService._delete_distributed_outputs", new_callable=AsyncMock), \
             patch("backend.services.visibility_change_service.StorageService") as mock_storage_cls, \
             patch("backend.services.worker_service.get_worker_service") as mock_worker_svc:

            mock_storage_cls.return_value = MagicMock()
            mock_worker = MagicMock()
            mock_worker.trigger_screens_worker = AsyncMock(return_value=True)
            mock_worker_svc.return_value = mock_worker

            await service.change_to_public("test-123", job, "user@example.com")

            # Verify the update payload resets styles
            update_calls = mock_job_ref.update.call_args_list
            # Find the main update call (the one with theme_id)
            style_update = None
            for call in update_calls:
                payload = call.args[0]
                if "theme_id" in payload:
                    style_update = payload
                    break

            assert style_update is not None
            assert style_update["theme_id"] == "nomad"
            assert style_update["color_overrides"] == {}
            assert style_update["style_assets"] == {}
            assert style_update["is_private"] is False
            assert style_update["status"] == "lyrics_complete"

    @pytest.mark.asyncio
    async def test_rollback_on_worker_failure(self):
        mock_job_manager = MagicMock()
        mock_job_ref = MagicMock()
        mock_job_manager.firestore.db.collection.return_value.document.return_value = mock_job_ref

        service = VisibilityChangeService(job_manager=mock_job_manager)
        job = _make_job(is_private=True, state_data={})

        with patch("backend.services.visibility_change_service.VisibilityChangeService._delete_distributed_outputs", new_callable=AsyncMock), \
             patch("backend.services.visibility_change_service.StorageService") as mock_storage_cls, \
             patch("backend.services.worker_service.get_worker_service") as mock_worker_svc:

            mock_storage_cls.return_value = MagicMock()
            mock_worker = MagicMock()
            mock_worker.trigger_screens_worker = AsyncMock(return_value=False)
            mock_worker_svc.return_value = mock_worker

            with pytest.raises(RuntimeError, match="Failed to trigger screens worker"):
                await service.change_to_public("test-123", job, "user@example.com")

            # Verify rollback was attempted
            rollback_call = mock_job_ref.update.call_args_list[-1]
            payload = rollback_call.args[0]
            assert payload["status"] == "complete"
            assert payload["is_private"] is True


class TestStateTransitions:
    """Test that the COMPLETE -> LYRICS_COMPLETE state transition is valid."""

    def test_complete_allows_lyrics_complete_transition(self):
        from backend.models.job import STATE_TRANSITIONS, JobStatus
        allowed = STATE_TRANSITIONS[JobStatus.COMPLETE]
        assert JobStatus.LYRICS_COMPLETE in allowed
