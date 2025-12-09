"""
Tests for PipelineContext.
"""
import pytest
from pathlib import Path


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_create_minimal_context(self):
        """Test creating a context with minimal required fields."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test-123",
            artist="Test Artist",
            title="Test Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/path/to/output",
        )
        
        assert context.job_id == "test-123"
        assert context.artist == "Test Artist"
        assert context.title == "Test Title"
        assert context.input_audio_path == "/path/to/audio.flac"
        assert context.output_dir == "/path/to/output"

    def test_base_name_property(self):
        """Test the base_name property."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="The Beatles",
            title="Hey Jude",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        assert context.base_name == "The Beatles - Hey Jude"

    def test_output_path_property(self):
        """Test the output_path property returns Path object."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/path/to/output",
        )
        
        assert isinstance(context.output_path, Path)
        assert str(context.output_path) == "/path/to/output"

    def test_input_path_property(self):
        """Test the input_path property returns Path object."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/path/to/audio.flac",
            output_dir="/output",
        )
        
        assert isinstance(context.input_path, Path)
        assert str(context.input_path) == "/path/to/audio.flac"

    def test_default_values(self):
        """Test default values for optional fields."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        assert context.style_params == {}
        assert context.enable_cdg is True
        assert context.enable_txt is True
        assert context.brand_prefix is None
        assert context.enable_youtube_upload is False
        assert context.discord_webhook_url is None
        assert context.dropbox_path is None
        assert context.gdrive_folder_id is None
        assert context.stage_outputs == {}
        assert context.current_stage is None
        assert context.progress_percent == 0
        assert context.temp_paths == []

    def test_get_stage_output(self):
        """Test getting stage output."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            stage_outputs={
                "separation": {
                    "instrumental": "/path/to/instrumental.flac",
                    "vocals": "/path/to/vocals.flac",
                },
            },
        )
        
        # Existing key
        assert context.get_stage_output("separation", "instrumental") == "/path/to/instrumental.flac"
        
        # Missing key with default
        assert context.get_stage_output("separation", "missing", "default") == "default"
        
        # Missing stage
        assert context.get_stage_output("missing_stage", "key") is None

    def test_set_stage_output(self):
        """Test setting stage output."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        context.set_stage_output("separation", {"instrumental": "/path.flac"})
        
        assert context.stage_outputs["separation"]["instrumental"] == "/path.flac"
        
        # Update existing stage output
        context.set_stage_output("separation", {"vocals": "/vocals.flac"})
        
        assert context.stage_outputs["separation"]["instrumental"] == "/path.flac"
        assert context.stage_outputs["separation"]["vocals"] == "/vocals.flac"

    def test_update_progress(self):
        """Test progress update."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        context.update_progress("separation", 50, "Processing...")
        
        assert context.current_stage == "separation"
        assert context.progress_percent == 50

    def test_update_progress_calls_callback(self):
        """Test that update_progress calls the callback if set."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        callback_calls = []
        
        def mock_callback(stage, percent, message):
            callback_calls.append((stage, percent, message))
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            on_progress=mock_callback,
        )
        
        context.update_progress("separation", 50, "Processing...")
        
        assert len(callback_calls) == 1
        assert callback_calls[0] == ("separation", 50, "Processing...")

    def test_add_temp_path(self):
        """Test adding temporary paths."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
        )
        
        context.add_temp_path("/tmp/file1.txt")
        context.add_temp_path("/tmp/file2.txt")
        
        assert len(context.temp_paths) == 2
        assert "/tmp/file1.txt" in context.temp_paths
        assert "/tmp/file2.txt" in context.temp_paths

    def test_to_dict(self):
        """Test serialization to dictionary."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        context = PipelineContext(
            job_id="test-123",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            brand_prefix="NOMAD",
            dropbox_path="/Karaoke",
        )
        
        data = context.to_dict()
        
        assert data["job_id"] == "test-123"
        assert data["artist"] == "Artist"
        assert data["title"] == "Title"
        assert data["brand_prefix"] == "NOMAD"
        assert data["dropbox_path"] == "/Karaoke"
        # Non-serializable fields should not be included
        assert "on_progress" not in data
        assert "logger" not in data

    def test_from_dict(self):
        """Test deserialization from dictionary."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        data = {
            "job_id": "test-123",
            "artist": "Artist",
            "title": "Title",
            "input_audio_path": "/audio.flac",
            "output_dir": "/output",
            "brand_prefix": "NOMAD",
            "dropbox_path": "/Karaoke",
            "stage_outputs": {"separation": {"done": True}},
        }
        
        context = PipelineContext.from_dict(data)
        
        assert context.job_id == "test-123"
        assert context.artist == "Artist"
        assert context.brand_prefix == "NOMAD"
        assert context.dropbox_path == "/Karaoke"
        assert context.stage_outputs == {"separation": {"done": True}}

    def test_roundtrip_serialization(self):
        """Test that serialization and deserialization roundtrip works."""
        from karaoke_gen.pipeline.context import PipelineContext
        
        original = PipelineContext(
            job_id="test-123",
            artist="Artist",
            title="Title",
            input_audio_path="/audio.flac",
            output_dir="/output",
            brand_prefix="NOMAD",
            enable_cdg=False,
            stage_outputs={"test": {"key": "value"}},
        )
        
        data = original.to_dict()
        restored = PipelineContext.from_dict(data)
        
        assert restored.job_id == original.job_id
        assert restored.artist == original.artist
        assert restored.brand_prefix == original.brand_prefix
        assert restored.enable_cdg == original.enable_cdg
        assert restored.stage_outputs == original.stage_outputs
