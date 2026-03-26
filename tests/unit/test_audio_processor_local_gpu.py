from backend.workers.audio_worker import create_audio_processor


class TestCreateAudioProcessorLocalGPU:
    """Tests for create_audio_processor with local GPU (model_file_dir set)."""

    def test_model_file_dir_passed_through(self):
        """When model_file_dir is provided, AudioProcessor gets it for local separation."""
        processor = create_audio_processor(
            temp_dir="/tmp/test",
            model_file_dir="/models",
        )
        assert processor.model_file_dir == "/models"

    def test_model_file_dir_none_by_default(self):
        """When model_file_dir is not provided, AudioProcessor gets None (remote mode)."""
        processor = create_audio_processor(
            temp_dir="/tmp/test",
        )
        assert processor.model_file_dir is None

    def test_presets_set_by_default(self):
        """Ensemble presets are always set on the processor."""
        processor = create_audio_processor(
            temp_dir="/tmp/test",
            model_file_dir="/models",
        )
        assert processor.instrumental_preset == "instrumental_clean"
        assert processor.karaoke_preset == "karaoke"

    def test_custom_presets_override_defaults(self):
        """Custom presets override the defaults."""
        processor = create_audio_processor(
            temp_dir="/tmp/test",
            model_file_dir="/models",
            instrumental_preset="instrumental_full",
            karaoke_preset="vocal_clean",
        )
        assert processor.instrumental_preset == "instrumental_full"
        assert processor.karaoke_preset == "vocal_clean"
