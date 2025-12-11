"""
Unit tests for backend workers.

These tests mock external dependencies and test worker logic in isolation.
This includes the functions that would have caught bugs like the
UnboundLocalError in upload_lyrics_results.
"""
import pytest
import os
import json
import tempfile
from datetime import datetime, UTC
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from pathlib import Path

from backend.models.job import Job, JobStatus


class TestAudioWorker:
    """Tests for audio_worker.py functions."""
    
    @pytest.fixture
    def mock_job(self):
        """Create a mock job for testing."""
        return Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song",
            input_media_gcs_path="uploads/test123/song.flac"
        )
    
    @pytest.fixture
    def mock_job_manager(self, mock_job):
        """Create a mock JobManager."""
        manager = MagicMock()
        manager.get_job.return_value = mock_job
        manager.update_job_status.return_value = None
        manager.update_file_url.return_value = None
        manager.update_state_data.return_value = None
        manager.mark_job_failed.return_value = None
        return manager
    
    @pytest.fixture
    def mock_storage(self):
        """Create a mock StorageService."""
        storage = MagicMock()
        storage.download_file.return_value = "/tmp/test/song.flac"
        storage.upload_file.return_value = "gs://bucket/path"
        return storage
    
    @pytest.mark.asyncio
    async def test_download_audio_from_gcs(self, mock_job_manager, mock_storage, mock_job):
        """Test downloading audio from GCS for uploaded files."""
        with patch('backend.workers.audio_worker.JobManager', return_value=mock_job_manager), \
             patch('backend.workers.audio_worker.StorageService', return_value=mock_storage):
            
            from backend.workers.audio_worker import download_audio
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = await download_audio("test123", temp_dir, mock_storage, mock_job)
                
                # Should have called download_file with the GCS path
                mock_storage.download_file.assert_called()
    
    @pytest.mark.asyncio
    async def test_upload_separation_results_handles_clean_stems(self, mock_job_manager, mock_storage):
        """Test that upload_separation_results handles clean stems correctly."""
        from backend.workers.audio_worker import upload_separation_results
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create actual test files
            inst_path = os.path.join(temp_dir, "instrumental.flac")
            vocals_path = os.path.join(temp_dir, "vocals.flac")
            with open(inst_path, 'wb') as f:
                f.write(b'fake audio data')
            with open(vocals_path, 'wb') as f:
                f.write(b'fake audio data')
            
            # Create mock separation result matching AudioProcessor output format
            separation_result = {
                "clean_instrumental": {
                    "instrumental": inst_path,
                    "vocals": vocals_path
                },
                "other_stems": {},
                "backing_vocals": {},
                "combined_instrumentals": {}
            }
            
            await upload_separation_results("test123", separation_result, mock_storage, mock_job_manager)
            
            # Should have uploaded files
            assert mock_storage.upload_file.called
    
    @pytest.mark.asyncio
    async def test_upload_separation_results_handles_other_stems_as_dict(self, mock_job_manager, mock_storage):
        """Test that upload_separation_results handles other_stems when values are dicts (bug fix)."""
        with patch('backend.workers.audio_worker.JobManager', return_value=mock_job_manager), \
             patch('backend.workers.audio_worker.StorageService', return_value=mock_storage):
            
            from backend.workers.audio_worker import upload_separation_results
            
            # This is the structure that caused the original bug - values are dicts, not strings
            separation_result = {
                "clean": {},
                "other_stems": {
                    "bass": {"path": "/tmp/test/bass.flac", "other_key": "value"},
                    "drums": "/tmp/test/drums.flac"  # String path
                },
                "backing_vocals": {},
                "combined_instrumentals": {}
            }
            
            # Mock os.path.exists
            with patch('os.path.exists', return_value=True):
                # This should NOT raise TypeError: stat: path should be string...
                await upload_separation_results("test123", separation_result, mock_storage, mock_job_manager)
    
    @pytest.mark.asyncio
    async def test_process_audio_separation_updates_status_on_failure(self, mock_job_manager, mock_storage):
        """Test that process_audio_separation marks job as failed on error."""
        mock_job_manager.get_job.return_value = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Test"
        )
        
        with patch('backend.workers.audio_worker.JobManager', return_value=mock_job_manager), \
             patch('backend.workers.audio_worker.StorageService', return_value=mock_storage), \
             patch('backend.workers.audio_worker.download_audio', side_effect=Exception("Download failed")):
            
            from backend.workers.audio_worker import process_audio_separation
            
            await process_audio_separation("test123")
            
            # Should have marked job as failed
            mock_job_manager.mark_job_failed.assert_called()


class TestLyricsWorker:
    """Tests for lyrics_worker.py functions."""
    
    @pytest.fixture
    def mock_job(self):
        """Create a mock job for testing."""
        return Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="ABBA",
            title="Waterloo",
            input_media_gcs_path="uploads/test123/song.flac"
        )
    
    @pytest.fixture
    def mock_job_manager(self, mock_job):
        """Create a mock JobManager."""
        manager = MagicMock()
        manager.get_job.return_value = mock_job
        manager.update_job_status.return_value = None
        manager.update_file_url.return_value = None
        manager.update_state_data.return_value = None
        manager.mark_job_failed.return_value = None
        return manager
    
    @pytest.fixture
    def mock_storage(self):
        """Create a mock StorageService."""
        storage = MagicMock()
        storage.download_file.return_value = "/tmp/test/song.flac"
        storage.upload_file.return_value = "gs://bucket/path"
        return storage
    
    @pytest.mark.asyncio
    async def test_upload_lyrics_results_requires_job(self, mock_job_manager, mock_storage, mock_job):
        """Test that upload_lyrics_results correctly fetches job for artist/title.
        
        This test would have caught the UnboundLocalError bug where job was used
        before being defined.
        """
        with patch('backend.workers.lyrics_worker.JobManager', return_value=mock_job_manager), \
             patch('backend.workers.lyrics_worker.StorageService', return_value=mock_storage):
            
            from backend.workers.lyrics_worker import upload_lyrics_results
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create mock lyrics directory and files
                lyrics_dir = os.path.join(temp_dir, "lyrics")
                os.makedirs(lyrics_dir)
                
                # Create test LRC file
                lrc_path = os.path.join(lyrics_dir, "ABBA - Waterloo (Karaoke).lrc")
                with open(lrc_path, 'w') as f:
                    f.write("[00:00.00]Test lyrics\n")
                
                # Create corrections JSON
                corrections_path = os.path.join(lyrics_dir, "ABBA - Waterloo (Lyrics Corrections).json")
                with open(corrections_path, 'w') as f:
                    json.dump({"lines": [], "corrections": []}, f)
                
                transcription_result = {
                    "lrc_filepath": lrc_path,
                    "corrections_filepath": corrections_path
                }
                
                # This should NOT raise UnboundLocalError
                await upload_lyrics_results(
                    "test123", 
                    temp_dir, 
                    transcription_result, 
                    mock_storage, 
                    mock_job_manager
                )
                
                # Verify job was fetched
                mock_job_manager.get_job.assert_called_with("test123")
    
    @pytest.mark.asyncio
    async def test_upload_lyrics_results_uploads_lrc_file(self, mock_job_manager, mock_storage, mock_job):
        """Test that LRC file is uploaded correctly."""
        from backend.workers.lyrics_worker import upload_lyrics_results
        import json
        
        with tempfile.TemporaryDirectory() as temp_dir:
            lyrics_dir = os.path.join(temp_dir, "lyrics")
            os.makedirs(lyrics_dir)
            
            lrc_path = os.path.join(lyrics_dir, "test.lrc")
            with open(lrc_path, 'w') as f:
                f.write("[00:00.00]Test\n")
            
            # Create required corrections.json file
            corrections_path = os.path.join(lyrics_dir, "corrections.json")
            with open(corrections_path, 'w') as f:
                json.dump({"corrected_segments": []}, f)
            
            transcription_result = {"lrc_filepath": lrc_path}
            
            await upload_lyrics_results(
                "test123", temp_dir, transcription_result, 
                mock_storage, mock_job_manager
            )
            
            # Should have uploaded the LRC file
            mock_storage.upload_file.assert_called()
            mock_job_manager.update_file_url.assert_called()
    
    @pytest.mark.asyncio
    async def test_upload_lyrics_results_handles_missing_files(self, mock_job_manager, mock_storage, mock_job):
        """Test graceful handling when optional files are missing."""
        from backend.workers.lyrics_worker import upload_lyrics_results
        import json
        
        with tempfile.TemporaryDirectory() as temp_dir:
            lyrics_dir = os.path.join(temp_dir, "lyrics")
            os.makedirs(lyrics_dir)
            
            # Only create LRC file and required corrections.json, no other files
            lrc_path = os.path.join(lyrics_dir, "test.lrc")
            with open(lrc_path, 'w') as f:
                f.write("[00:00.00]Test\n")
            
            # Create required corrections.json file
            corrections_path = os.path.join(lyrics_dir, "corrections.json")
            with open(corrections_path, 'w') as f:
                json.dump({"corrected_segments": []}, f)
            
            transcription_result = {"lrc_filepath": lrc_path}
            
            # Should not raise exception for missing optional files
            await upload_lyrics_results(
                "test123", temp_dir, transcription_result,
                mock_storage, mock_job_manager
            )
    
    @pytest.mark.asyncio
    async def test_upload_lyrics_results_uses_artist_title_from_job(self, mock_job_manager, mock_storage, mock_job):
        """Test that upload_lyrics_results correctly uses job.artist and job.title.
        
        This test specifically validates the bug fix where job was not defined
        when accessing job.artist and job.title for reference file lookups.
        """
        from backend.workers.lyrics_worker import upload_lyrics_results
        import json
        
        with tempfile.TemporaryDirectory() as temp_dir:
            lyrics_dir = os.path.join(temp_dir, "lyrics")
            os.makedirs(lyrics_dir)
            
            # Create LRC file
            lrc_path = os.path.join(lyrics_dir, "test.lrc")
            with open(lrc_path, 'w') as f:
                f.write("[00:00.00]Test\n")
            
            # Create required corrections.json file
            corrections_path = os.path.join(lyrics_dir, "corrections.json")
            with open(corrections_path, 'w') as f:
                json.dump({"corrected_segments": []}, f)
            
            # Create a reference lyrics file using the job's artist/title
            ref_path = os.path.join(lyrics_dir, f"{mock_job.artist} - {mock_job.title} (Lyrics Genius).txt")
            with open(ref_path, 'w') as f:
                f.write("Reference lyrics content\n")
            
            # Create uncorrected transcription file using job's artist/title
            uncorrected_path = os.path.join(lyrics_dir, f"{mock_job.artist} - {mock_job.title} (Lyrics Uncorrected).txt")
            with open(uncorrected_path, 'w') as f:
                f.write("Uncorrected transcription\n")
            
            transcription_result = {"lrc_filepath": lrc_path}
            
            # This should NOT raise UnboundLocalError for 'job'
            await upload_lyrics_results(
                "test123", temp_dir, transcription_result,
                mock_storage, mock_job_manager
            )
            
            # Verify job was fetched to get artist/title
            mock_job_manager.get_job.assert_called_with("test123")
            
            # Verify files were uploaded (the reference and uncorrected files exist)
            upload_calls = mock_storage.upload_file.call_args_list
            assert len(upload_calls) >= 2  # LRC + at least one reference or uncorrected
    
    @pytest.mark.asyncio
    async def test_process_lyrics_transcription_marks_failed_on_error(self, mock_job_manager, mock_storage):
        """Test that process_lyrics_transcription marks job as failed on error."""
        mock_job_manager.get_job.return_value = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Test",
            input_media_gcs_path="uploads/test123/song.flac"
        )
        
        with patch('backend.workers.lyrics_worker.JobManager', return_value=mock_job_manager), \
             patch('backend.workers.lyrics_worker.StorageService', return_value=mock_storage), \
             patch('backend.workers.lyrics_worker.download_audio', side_effect=Exception("Download failed")):
            
            from backend.workers.lyrics_worker import process_lyrics_transcription
            
            await process_lyrics_transcription("test123")
            
            mock_job_manager.mark_job_failed.assert_called()


class TestLyricsWorkerConfiguration:
    """Tests for lyrics worker configuration parameters."""
    
    def test_create_lyrics_processor_with_defaults(self):
        """Test creating LyricsProcessor with default parameters."""
        with patch('backend.workers.lyrics_worker.LyricsProcessor') as mock_processor:
            from backend.workers.lyrics_worker import create_lyrics_processor
            
            result = create_lyrics_processor()
            
            mock_processor.assert_called_once()
            call_kwargs = mock_processor.call_args[1]
            assert call_kwargs['lyrics_file'] is None
            assert call_kwargs['subtitle_offset_ms'] == 0
    
    def test_create_lyrics_processor_with_lyrics_file(self):
        """Test creating LyricsProcessor with custom lyrics file."""
        with patch('backend.workers.lyrics_worker.LyricsProcessor') as mock_processor:
            from backend.workers.lyrics_worker import create_lyrics_processor
            
            result = create_lyrics_processor(
                lyrics_file="/path/to/lyrics.txt",
                subtitle_offset_ms=0
            )
            
            mock_processor.assert_called_once()
            call_kwargs = mock_processor.call_args[1]
            assert call_kwargs['lyrics_file'] == "/path/to/lyrics.txt"
    
    def test_create_lyrics_processor_with_subtitle_offset(self):
        """Test creating LyricsProcessor with subtitle offset."""
        with patch('backend.workers.lyrics_worker.LyricsProcessor') as mock_processor:
            from backend.workers.lyrics_worker import create_lyrics_processor
            
            result = create_lyrics_processor(
                subtitle_offset_ms=500
            )
            
            mock_processor.assert_called_once()
            call_kwargs = mock_processor.call_args[1]
            assert call_kwargs['subtitle_offset_ms'] == 500


class TestLyricsOverrideParameters:
    """Tests for lyrics artist/title override functionality."""
    
    @pytest.fixture
    def mock_job_with_overrides(self):
        """Create a mock job with lyrics override fields."""
        return Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Beatles, The",
            title="Hey Jude - 2009 Remaster",
            lyrics_artist="The Beatles",
            lyrics_title="Hey Jude",
            subtitle_offset_ms=250,
            input_media_gcs_path="uploads/test123/song.flac"
        )
    
    def test_job_uses_lyrics_artist_override(self, mock_job_with_overrides):
        """Test that job uses lyrics_artist when searching for lyrics."""
        job = mock_job_with_overrides
        
        # Use override if present, else fall back to main artist
        lyrics_search_artist = job.lyrics_artist or job.artist
        
        assert lyrics_search_artist == "The Beatles"
        assert lyrics_search_artist != job.artist  # Override is different
    
    def test_job_uses_lyrics_title_override(self, mock_job_with_overrides):
        """Test that job uses lyrics_title when searching for lyrics."""
        job = mock_job_with_overrides
        
        # Use override if present, else fall back to main title
        lyrics_search_title = job.lyrics_title or job.title
        
        assert lyrics_search_title == "Hey Jude"
        assert lyrics_search_title != job.title  # Override is different
    
    def test_job_falls_back_when_no_override(self):
        """Test that job falls back to main artist/title when no override."""
        job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song",
            input_media_gcs_path="uploads/test123/song.flac"
        )
        
        # When override is None, use main values
        lyrics_search_artist = job.lyrics_artist or job.artist
        lyrics_search_title = job.lyrics_title or job.title
        
        assert lyrics_search_artist == "Test Artist"
        assert lyrics_search_title == "Test Song"


class TestScreensWorker:
    """Tests for screens_worker.py functions.
    
    Note: The main process function is tested indirectly via integration tests.
    These unit tests focus on helper functions and module structure.
    """
    
    def test_screens_worker_module_imports(self):
        """Test screens worker module can be imported."""
        from backend.workers import screens_worker
        assert hasattr(screens_worker, 'logger')


class TestVideoWorker:
    """Tests for video_worker.py functions.
    
    Note: The main process function is tested indirectly via integration tests.
    These unit tests focus on helper functions and module structure.
    """
    
    def test_video_worker_module_imports(self):
        """Test video worker module can be imported."""
        from backend.workers import video_worker
        assert hasattr(video_worker, 'logger')


class TestRenderVideoWorkerConfiguration:
    """Tests for render_video_worker subtitle_offset_ms support."""
    
    @pytest.fixture
    def mock_job_with_offset(self):
        """Create a mock job with subtitle offset."""
        return Job(
            job_id="test123",
            status=JobStatus.RENDERING_VIDEO,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song",
            subtitle_offset_ms=500,
            input_media_gcs_path="uploads/test123/song.flac"
        )
    
    def test_job_has_subtitle_offset_ms(self, mock_job_with_offset):
        """Test that job has subtitle_offset_ms field."""
        assert mock_job_with_offset.subtitle_offset_ms == 500
    
    def test_subtitle_offset_from_job(self, mock_job_with_offset):
        """Test extracting subtitle offset from job with getattr."""
        job = mock_job_with_offset
        
        # This mirrors the logic in render_video_worker.py
        subtitle_offset = getattr(job, 'subtitle_offset_ms', 0) or 0
        
        assert subtitle_offset == 500
    
    def test_subtitle_offset_default_zero(self):
        """Test that subtitle offset defaults to 0 when not set."""
        job = Job(
            job_id="test123",
            status=JobStatus.RENDERING_VIDEO,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song",
            input_media_gcs_path="uploads/test123/song.flac"
        )
        
        subtitle_offset = getattr(job, 'subtitle_offset_ms', 0) or 0
        
        assert subtitle_offset == 0
    
    def test_subtitle_offset_negative_value(self):
        """Test that subtitle offset can be negative (advance subtitles)."""
        job = Job(
            job_id="test123",
            status=JobStatus.RENDERING_VIDEO,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test Artist",
            title="Test Song",
            subtitle_offset_ms=-250,  # Negative = advance subtitles
            input_media_gcs_path="uploads/test123/song.flac"
        )
        
        subtitle_offset = getattr(job, 'subtitle_offset_ms', 0) or 0
        
        # Negative values should be preserved (not converted to 0)
        assert subtitle_offset == -250


class TestDownloadHelpers:
    """Tests for download helper functions in workers."""
    
    @pytest.mark.asyncio
    async def test_download_audio_handles_uploaded_file(self):
        """Test download_audio handles jobs with uploaded file."""
        mock_storage = MagicMock()
        mock_storage.download_file.return_value = "/tmp/downloaded.flac"
        
        mock_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Test",
            input_media_gcs_path="uploads/test123/song.flac"  # Uploaded file
        )
        
        from backend.workers.audio_worker import download_audio
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await download_audio("test123", temp_dir, mock_storage, mock_job)
            
            # Should have downloaded from GCS
            mock_storage.download_file.assert_called()


class TestAudioWorkerModelConfiguration:
    """Tests for audio worker model configuration parameters."""
    
    def test_create_audio_processor_with_defaults(self):
        """Test creating AudioProcessor with default models."""
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = create_audio_processor(temp_dir)
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # Should use default models
                assert call_kwargs['clean_instrumental_model'] == "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
                assert call_kwargs['backing_vocals_models'] == ["mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"]
                assert call_kwargs['other_stems_models'] == ["htdemucs_6s.yaml"]
    
    def test_create_audio_processor_with_custom_clean_model(self):
        """Test creating AudioProcessor with custom clean instrumental model."""
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = create_audio_processor(
                    temp_dir,
                    clean_instrumental_model="custom_clean_model.ckpt"
                )
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # Should use custom clean model
                assert call_kwargs['clean_instrumental_model'] == "custom_clean_model.ckpt"
                # Other models should still be defaults
                assert call_kwargs['backing_vocals_models'] == ["mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"]
    
    def test_create_audio_processor_with_custom_backing_models(self):
        """Test creating AudioProcessor with custom backing vocals models."""
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = create_audio_processor(
                    temp_dir,
                    backing_vocals_models=["custom_bv1.ckpt", "custom_bv2.ckpt"]
                )
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # Should use custom backing vocals models
                assert call_kwargs['backing_vocals_models'] == ["custom_bv1.ckpt", "custom_bv2.ckpt"]
    
    def test_create_audio_processor_with_custom_other_stems_models(self):
        """Test creating AudioProcessor with custom other stems models."""
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = create_audio_processor(
                    temp_dir,
                    other_stems_models=["custom_demucs.yaml"]
                )
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # Should use custom other stems models
                assert call_kwargs['other_stems_models'] == ["custom_demucs.yaml"]
    
    def test_create_audio_processor_with_all_custom_models(self):
        """Test creating AudioProcessor with all custom models."""
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = create_audio_processor(
                    temp_dir,
                    clean_instrumental_model="custom_clean.ckpt",
                    backing_vocals_models=["custom_bv.ckpt"],
                    other_stems_models=["custom_stems.yaml"]
                )
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # All models should be custom
                assert call_kwargs['clean_instrumental_model'] == "custom_clean.ckpt"
                assert call_kwargs['backing_vocals_models'] == ["custom_bv.ckpt"]
                assert call_kwargs['other_stems_models'] == ["custom_stems.yaml"]
    
    def test_job_model_fields_are_passed_to_processor(self):
        """Test that job model fields can be passed to create_audio_processor."""
        mock_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Test",
            clean_instrumental_model="job_clean.ckpt",
            backing_vocals_models=["job_bv.ckpt"],
            other_stems_models=["job_stems.yaml"]
        )
        
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Simulate passing job model fields to create_audio_processor
                result = create_audio_processor(
                    temp_dir,
                    clean_instrumental_model=mock_job.clean_instrumental_model,
                    backing_vocals_models=mock_job.backing_vocals_models,
                    other_stems_models=mock_job.other_stems_models
                )
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # Models from job should be used
                assert call_kwargs['clean_instrumental_model'] == "job_clean.ckpt"
                assert call_kwargs['backing_vocals_models'] == ["job_bv.ckpt"]
                assert call_kwargs['other_stems_models'] == ["job_stems.yaml"]
    
    def test_none_model_values_use_defaults(self):
        """Test that None model values fall back to defaults."""
        mock_job = Job(
            job_id="test123",
            status=JobStatus.PENDING,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            artist="Test",
            title="Test",
            clean_instrumental_model=None,  # Not specified
            backing_vocals_models=None,     # Not specified
            other_stems_models=None         # Not specified
        )
        
        with patch('backend.workers.audio_worker.AudioProcessor') as mock_processor:
            from backend.workers.audio_worker import create_audio_processor
            
            with tempfile.TemporaryDirectory() as temp_dir:
                result = create_audio_processor(
                    temp_dir,
                    clean_instrumental_model=mock_job.clean_instrumental_model,
                    backing_vocals_models=mock_job.backing_vocals_models,
                    other_stems_models=mock_job.other_stems_models
                )
                
                mock_processor.assert_called_once()
                call_kwargs = mock_processor.call_args[1]
                
                # Should fall back to defaults
                assert call_kwargs['clean_instrumental_model'] == "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
                assert call_kwargs['backing_vocals_models'] == ["mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"]
                assert call_kwargs['other_stems_models'] == ["htdemucs_6s.yaml"]

