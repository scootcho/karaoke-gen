"""
Tests for pipeline stages.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestSeparationStage:
    """Tests for SeparationStage."""

    def test_stage_imports(self):
        """Test that the stage can be imported."""
        from karaoke_gen.pipeline.stages.separation import SeparationStage
        assert SeparationStage is not None

    def test_stage_name(self):
        """Test the stage name."""
        from karaoke_gen.pipeline.stages.separation import SeparationStage
        
        stage = SeparationStage()
        assert stage.name == "separation"

    def test_stage_required_inputs(self):
        """Test that separation has no required inputs."""
        from karaoke_gen.pipeline.stages.separation import SeparationStage
        
        stage = SeparationStage()
        assert stage.required_inputs == []

    def test_stage_output_keys(self):
        """Test the declared output keys."""
        from karaoke_gen.pipeline.stages.separation import SeparationStage
        
        stage = SeparationStage()
        assert "clean_instrumental" in stage.output_keys
        assert "other_stems" in stage.output_keys
        assert "backing_vocals" in stage.output_keys
        assert "combined_instrumentals" in stage.output_keys

    def test_stage_init_with_custom_params(self):
        """Test initializing with custom parameters."""
        from karaoke_gen.pipeline.stages.separation import SeparationStage
        
        stage = SeparationStage(
            model_file_dir="/custom/models",
            lossless_output_format="wav",
            skip_separation=True,
        )
        
        assert stage.model_file_dir == "/custom/models"
        assert stage.lossless_output_format == "wav"
        assert stage.skip_separation is True


class TestTranscriptionStage:
    """Tests for TranscriptionStage."""

    def test_stage_imports(self):
        """Test that the stage can be imported."""
        from karaoke_gen.pipeline.stages.transcription import TranscriptionStage
        assert TranscriptionStage is not None

    def test_stage_name(self):
        """Test the stage name."""
        from karaoke_gen.pipeline.stages.transcription import TranscriptionStage
        
        stage = TranscriptionStage()
        assert stage.name == "transcription"

    def test_stage_required_inputs(self):
        """Test that transcription has no required inputs from other stages."""
        from karaoke_gen.pipeline.stages.transcription import TranscriptionStage
        
        stage = TranscriptionStage()
        assert stage.required_inputs == []

    def test_stage_optional_inputs(self):
        """Test optional inputs."""
        from karaoke_gen.pipeline.stages.transcription import TranscriptionStage
        
        stage = TranscriptionStage()
        assert "separation" in stage.optional_inputs

    def test_stage_output_keys(self):
        """Test the declared output keys."""
        from karaoke_gen.pipeline.stages.transcription import TranscriptionStage
        
        stage = TranscriptionStage()
        assert "lrc_filepath" in stage.output_keys
        assert "ass_filepath" in stage.output_keys


class TestScreensStage:
    """Tests for ScreensStage."""

    def test_stage_imports(self):
        """Test that the stage can be imported."""
        from karaoke_gen.pipeline.stages.screens import ScreensStage
        assert ScreensStage is not None

    def test_stage_name(self):
        """Test the stage name."""
        from karaoke_gen.pipeline.stages.screens import ScreensStage
        
        stage = ScreensStage()
        assert stage.name == "screens"

    def test_stage_output_keys(self):
        """Test the declared output keys."""
        from karaoke_gen.pipeline.stages.screens import ScreensStage
        
        stage = ScreensStage()
        assert "title_video_path" in stage.output_keys
        assert "end_video_path" in stage.output_keys

    def test_stage_init_options(self):
        """Test initialization options."""
        from karaoke_gen.pipeline.stages.screens import ScreensStage
        
        stage = ScreensStage(output_png=False, output_jpg=False)
        
        assert stage.output_png is False
        assert stage.output_jpg is False


class TestRenderStage:
    """Tests for RenderStage."""

    def test_stage_imports(self):
        """Test that the stage can be imported."""
        from karaoke_gen.pipeline.stages.render import RenderStage
        assert RenderStage is not None

    def test_stage_name(self):
        """Test the stage name."""
        from karaoke_gen.pipeline.stages.render import RenderStage
        
        stage = RenderStage()
        assert stage.name == "render"

    def test_stage_required_inputs(self):
        """Test that render requires transcription."""
        from karaoke_gen.pipeline.stages.render import RenderStage
        
        stage = RenderStage()
        assert "transcription" in stage.required_inputs

    def test_stage_output_keys(self):
        """Test the declared output keys."""
        from karaoke_gen.pipeline.stages.render import RenderStage
        
        stage = RenderStage()
        assert "with_vocals_video_path" in stage.output_keys


class TestFinalizeStage:
    """Tests for FinalizeStage."""

    def test_stage_imports(self):
        """Test that the stage can be imported."""
        from karaoke_gen.pipeline.stages.finalize import FinalizeStage
        assert FinalizeStage is not None

    def test_stage_name(self):
        """Test the stage name."""
        from karaoke_gen.pipeline.stages.finalize import FinalizeStage
        
        stage = FinalizeStage()
        assert stage.name == "finalize"

    def test_stage_required_inputs(self):
        """Test required inputs."""
        from karaoke_gen.pipeline.stages.finalize import FinalizeStage
        
        stage = FinalizeStage()
        assert "render" in stage.required_inputs
        assert "screens" in stage.required_inputs

    def test_stage_output_keys(self):
        """Test the declared output keys."""
        from karaoke_gen.pipeline.stages.finalize import FinalizeStage
        
        stage = FinalizeStage()
        assert "brand_code" in stage.output_keys
        assert "youtube_url" in stage.output_keys
        assert "cdg_zip_path" in stage.output_keys

    def test_stage_init_options(self):
        """Test initialization options."""
        from karaoke_gen.pipeline.stages.finalize import FinalizeStage
        
        stage = FinalizeStage(
            enable_cdg=False,
            enable_txt=False,
            non_interactive=True,
            server_side_mode=True,
        )
        
        assert stage.enable_cdg is False
        assert stage.enable_txt is False
        assert stage.non_interactive is True
        assert stage.server_side_mode is True


class TestStageModuleExports:
    """Tests for module exports."""

    def test_stages_init_exports(self):
        """Test that stages __init__ exports all stages."""
        from karaoke_gen.pipeline.stages import (
            SeparationStage,
            TranscriptionStage,
            ScreensStage,
            RenderStage,
            FinalizeStage,
        )
        
        assert SeparationStage is not None
        assert TranscriptionStage is not None
        assert ScreensStage is not None
        assert RenderStage is not None
        assert FinalizeStage is not None
