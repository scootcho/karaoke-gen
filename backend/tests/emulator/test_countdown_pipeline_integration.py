"""
Integration tests for countdown padding across the full worker pipeline.

These tests use Firestore emulator to verify real state updates flow correctly
between workers. They mock only external services (Modal, AudioShake, etc.)
but use real Firestore for state persistence.

Run with: scripts/run-emulator-tests.sh
"""

import pytest
import os
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch
import tempfile

# Import base fixtures from conftest
from backend.tests.emulator.conftest import emulators_running

# Skip all tests if emulators aren't running
pytestmark = pytest.mark.skipif(
    not emulators_running(),
    reason="GCP emulators not running. Start with: scripts/start-emulators.sh"
)

# Only import if emulators are running
if emulators_running():
    from backend.models.job import Job, JobStatus
    from backend.services.job_manager import JobManager
    from backend.services.storage_service import StorageService
    from backend.services.firestore_service import FirestoreService


class TestCountdownStateFlowThroughPipeline:
    """
    Integration tests verifying countdown state flows correctly through
    the full worker pipeline: lyrics -> render_video -> video.
    """

    @pytest.fixture
    def job_manager(self):
        """Create a real JobManager using emulator."""
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        """Create a real FirestoreService using emulator for direct job operations."""
        return FirestoreService()

    @pytest.fixture
    def storage_service(self):
        """Create a real StorageService using emulator."""
        return StorageService()

    @pytest.fixture
    def job_with_early_start_song(self, job_manager, firestore_service):
        """
        Create a job where lyrics start within 3 seconds (needs countdown).

        This simulates a song where the first word appears at 0.5 seconds,
        which triggers countdown processing.
        """
        job_id = f"countdown-test-early-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Early Start Song",
            state_data={
                'lyrics_metadata': {
                    'has_countdown_padding': False,
                    'countdown_padding_seconds': 0.0,
                    'first_word_start_time': 0.5,  # Within 3s threshold
                }
            }
        )

        # Create job in Firestore directly
        firestore_service.create_job(job)

        yield job

        # Cleanup
        try:
            firestore_service.delete_job(job_id)
        except Exception:
            pass

    @pytest.fixture
    def job_with_late_start_song(self, job_manager, firestore_service):
        """
        Create a job where lyrics start after 3 seconds (no countdown needed).

        This simulates a song where the first word appears at 5.0 seconds,
        which does NOT trigger countdown processing.
        """
        job_id = f"countdown-test-late-{datetime.now(UTC).timestamp()}"

        job = Job(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Late Start Song",
            state_data={
                'lyrics_metadata': {
                    'has_countdown_padding': False,
                    'countdown_padding_seconds': 0.0,
                    'first_word_start_time': 5.0,  # After 3s threshold
                }
            }
        )

        firestore_service.create_job(job)

        yield job

        try:
            firestore_service.delete_job(job_id)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_state_update_persists_to_firestore(self, job_with_early_start_song, job_manager):
        """
        Verify that state updates via update_state_data() persist to Firestore.

        This is the foundation of the countdown state flow - if updates don't
        persist, video_worker can't read the countdown state.
        """
        job = job_with_early_start_song

        # Simulate render_video_worker updating countdown state
        new_lyrics_metadata = {
            'has_countdown_padding': True,
            'countdown_padding_seconds': 3.0,
            'first_word_start_time': 0.5,
        }

        job_manager.update_state_data(job.job_id, 'lyrics_metadata', new_lyrics_metadata)

        # Read job back from Firestore
        refreshed_job = job_manager.get_job(job.job_id)

        assert refreshed_job is not None
        lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})
        assert lyrics_metadata.get('has_countdown_padding') is True
        assert lyrics_metadata.get('countdown_padding_seconds') == 3.0

    @pytest.mark.asyncio
    async def test_video_worker_reads_updated_state(self, job_with_early_start_song, job_manager):
        """
        Verify that video_worker can read countdown state after render_video_worker sets it.

        This simulates the full flow:
        1. render_video_worker sets has_countdown_padding=True
        2. video_worker reads the state and extracts countdown_padding_seconds
        """
        job = job_with_early_start_song

        # Step 1: render_video_worker updates state
        new_lyrics_metadata = {
            'has_countdown_padding': True,
            'countdown_padding_seconds': 3.0,
        }
        job_manager.update_state_data(job.job_id, 'lyrics_metadata', new_lyrics_metadata)

        # Step 2: video_worker reads state (simulated)
        refreshed_job = job_manager.get_job(job.job_id)

        # video_worker extraction logic
        lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})
        countdown_padding_seconds = None
        if lyrics_metadata.get('has_countdown_padding'):
            countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

        assert countdown_padding_seconds == 3.0

    @pytest.mark.asyncio
    async def test_no_countdown_state_when_not_needed(self, job_with_late_start_song, job_manager):
        """
        Verify that when song doesn't need countdown, state remains False.
        """
        job = job_with_late_start_song

        # Read initial state
        current_job = job_manager.get_job(job.job_id)
        lyrics_metadata = current_job.state_data.get('lyrics_metadata', {})

        assert lyrics_metadata.get('has_countdown_padding') is False
        assert lyrics_metadata.get('countdown_padding_seconds') == 0.0

        # video_worker extraction logic
        countdown_padding_seconds = None
        if lyrics_metadata.get('has_countdown_padding'):
            countdown_padding_seconds = lyrics_metadata.get('countdown_padding_seconds', 3.0)

        assert countdown_padding_seconds is None


class TestCountdownStateTransitions:
    """Tests for state transitions during countdown processing."""

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_state_transitions_preserve_countdown_info(self, job_manager, firestore_service):
        """
        Countdown state should survive job state transitions.

        When job moves from RENDERING_VIDEO to ENCODING,
        the lyrics_metadata should remain intact.
        """
        job_id = f"transition-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job in RENDERING_VIDEO state
            job = Job(
                job_id=job_id,
                status=JobStatus.RENDERING_VIDEO,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': True,
                        'countdown_padding_seconds': 3.0,
                    }
                }
            )
            firestore_service.create_job(job)

            # Transition to ENCODING
            job_manager.transition_to_state(
                job_id=job_id,
                new_status=JobStatus.ENCODING,
                progress=75,
                message="Starting encoding"
            )

            # Read job and verify countdown state preserved
            refreshed_job = job_manager.get_job(job_id)
            lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})

            assert lyrics_metadata.get('has_countdown_padding') is True
            assert lyrics_metadata.get('countdown_padding_seconds') == 3.0

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass


class TestWorkerStateDataIsolation:
    """Tests that different workers don't overwrite each other's state data."""

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.mark.asyncio
    async def test_lyrics_metadata_not_overwritten_by_other_updates(self, job_manager, firestore_service):
        """
        Updating video_worker state should NOT overwrite lyrics_metadata.

        Each worker stores its state in separate keys within state_data.
        """
        job_id = f"isolation-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job with countdown state
            job = Job(
                job_id=job_id,
                status=JobStatus.ENCODING,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': True,
                        'countdown_padding_seconds': 3.0,
                    }
                }
            )
            firestore_service.create_job(job)

            # Update video_worker state (different key)
            job_manager.update_state_data(job_id, 'video_worker', {
                'instrumental_source': 'clean',
                'encoding_started': True,
            })

            # Verify lyrics_metadata preserved
            refreshed_job = job_manager.get_job(job_id)
            lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})

            assert lyrics_metadata.get('has_countdown_padding') is True
            assert lyrics_metadata.get('countdown_padding_seconds') == 3.0

            # Verify video_worker state also present
            video_worker_state = refreshed_job.state_data.get('video_worker', {})
            assert video_worker_state.get('instrumental_source') == 'clean'

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass


class TestCountdownEndToEndWithMockedWorkers:
    """
    End-to-end tests that run actual worker code with mocked external services.

    These tests verify the countdown state flows through actual worker code,
    not just simulated state updates.
    """

    @pytest.fixture
    def job_manager(self):
        return JobManager()

    @pytest.fixture
    def firestore_service(self):
        return FirestoreService()

    @pytest.fixture
    def storage_service(self):
        return StorageService()

    @pytest.mark.asyncio
    async def test_render_video_worker_updates_countdown_state(self, job_manager, firestore_service, storage_service):
        """
        Run render_video_worker code and verify countdown state is updated.

        This test will FAIL until render_video_worker is fixed to call
        update_state_data() when CountdownProcessor adds padding.
        """
        job_id = f"render-worker-test-{datetime.now(UTC).timestamp()}"

        try:
            # Create job
            job = Job(
                job_id=job_id,
                status=JobStatus.RENDERING_VIDEO,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                artist="Test",
                title="Test",
                file_urls={
                    'vocals': 'gs://test-bucket/vocals.flac',
                },
                state_data={
                    'lyrics_metadata': {
                        'has_countdown_padding': False,
                        'countdown_padding_seconds': 0.0,
                    }
                }
            )
            firestore_service.create_job(job)

            # Mock CountdownProcessor to return padding_added=True
            mock_correction_result = MagicMock()
            mock_correction_result.corrected_segments = []

            with patch('backend.workers.render_video_worker.CountdownProcessor') as MockCountdown, \
                 patch('backend.workers.render_video_worker.load_styles_from_gcs') as mock_styles, \
                 patch('backend.workers.render_video_worker.OutputGenerator') as MockOutput:

                mock_processor = MagicMock()
                mock_processor.process.return_value = (
                    mock_correction_result,
                    "/tmp/padded.flac",
                    True,  # padding_added
                    3.0,   # padding_seconds
                )
                MockCountdown.return_value = mock_processor

                mock_styles.return_value = ("/tmp/styles.json", {})
                MockOutput.return_value.generate_outputs.return_value = {}

                from backend.workers.render_video_worker import process_render_video

                # Run worker (will fail on external calls, but should update state)
                try:
                    await process_render_video(job_id)
                except Exception:
                    pass  # Expected to fail on some mocked calls

                # Check if countdown state was updated
                refreshed_job = job_manager.get_job(job_id)
                lyrics_metadata = refreshed_job.state_data.get('lyrics_metadata', {})

                # The fix ensures has_countdown_padding is set when countdown is added
                assert lyrics_metadata.get('has_countdown_padding') is True, (
                    "render_video_worker must set has_countdown_padding=True when countdown added"
                )

        finally:
            try:
                firestore_service.delete_job(job_id)
            except Exception:
                pass
