"""
Unit tests for run_instrumental_review function.

These tests verify that run_instrumental_review correctly integrates:
- AudioAnalyzer
- WaveformGenerator  
- InstrumentalReviewServer

Importantly, these tests verify that the correct parameter names are used
when calling the underlying components, which caught the 'audible_segments'
vs 'segments' parameter name bug.
"""

import pytest
import os
import logging
from unittest.mock import MagicMock, patch, PropertyMock

from karaoke_gen.instrumental_review import (
    AnalysisResult,
    RecommendedSelection,
    AudibleSegment,
)


class TestRunInstrumentalReviewIntegration:
    """Tests for run_instrumental_review that verify component integration."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        logger = MagicMock(spec=logging.Logger)
        return logger
    
    @pytest.fixture
    def sample_analysis(self):
        """Create a sample AnalysisResult."""
        return AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=180.0,
            audible_segments=[
                AudibleSegment(
                    start_seconds=10.0,
                    end_seconds=20.0,
                    duration_seconds=10.0,
                    avg_amplitude_db=-25.0,
                ),
                AudibleSegment(
                    start_seconds=60.0,
                    end_seconds=75.0,
                    duration_seconds=15.0,
                    avg_amplitude_db=-22.0,
                ),
            ],
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
            silence_threshold_db=-40.0,
        )
    
    @pytest.fixture
    def sample_track(self, tmp_path):
        """Create a sample track dictionary with test files."""
        # Create fake files
        stems_dir = tmp_path / "stems"
        stems_dir.mkdir()
        
        backing_vocals = stems_dir / "Test - Song (Backing Vocals model.ckpt).flac"
        backing_vocals.touch()
        
        clean_instrumental = tmp_path / "Test - Song (Instrumental model.ckpt).flac"
        clean_instrumental.touch()
        
        combined_instrumental = tmp_path / "Test - Song (Instrumental +BV model.ckpt).flac"
        combined_instrumental.touch()
        
        return {
            "artist": "Test",
            "title": "Song",
            "track_output_dir": str(tmp_path),
            "separated_audio": {
                "backing_vocals": {
                    "model.ckpt": {
                        "backing_vocals": str(backing_vocals),
                    }
                },
                "clean_instrumental": {
                    "instrumental": str(clean_instrumental),
                },
                "combined_instrumentals": {
                    "model.ckpt": str(combined_instrumental),
                },
            },
        }
    
    def test_waveform_generator_called_with_correct_param_names(
        self, sample_track, sample_analysis, mock_logger, tmp_path
    ):
        """
        CRITICAL TEST: Verify WaveformGenerator.generate() is called with 
        'segments' parameter, NOT 'audible_segments'.
        
        This test would have caught the bug where 'audible_segments' was
        incorrectly used instead of 'segments'.
        """
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        # Change to the track directory (simulating gen_cli behavior)
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer, \
                 patch('karaoke_gen.utils.gen_cli.WaveformGenerator') as MockWaveformGen, \
                 patch('karaoke_gen.utils.gen_cli.InstrumentalReviewServer') as MockServer:
                
                # Setup analyzer mock
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.return_value = sample_analysis
                
                # Setup waveform generator mock
                mock_waveform_instance = MockWaveformGen.return_value
                mock_waveform_instance.generate.return_value = "waveform.png"
                
                # Setup server mock - simulate user selecting "clean"
                mock_server_instance = MockServer.return_value
                mock_server_instance._selection_event = MagicMock()
                mock_server_instance._selection_event.wait.return_value = None
                mock_server_instance.get_selection.return_value = "clean"
                
                # Call the function
                result = run_instrumental_review(
                    track=sample_track,
                    logger=mock_logger,
                )
                
                # CRITICAL ASSERTION: Verify correct parameter name
                # The method should be called with 'segments=', not 'audible_segments='
                mock_waveform_instance.generate.assert_called_once()
                call_kwargs = mock_waveform_instance.generate.call_args.kwargs
                
                # This is the key check that would have caught the bug
                assert 'segments' in call_kwargs, \
                    "WaveformGenerator.generate() should be called with 'segments' parameter"
                assert 'audible_segments' not in call_kwargs, \
                    "WaveformGenerator.generate() should NOT use 'audible_segments' (wrong param name)"
                
                # Verify the segments value is the analysis segments
                assert call_kwargs['segments'] == sample_analysis.audible_segments
        finally:
            os.chdir(original_dir)
    
    def test_waveform_generator_receives_analysis_segments(
        self, sample_track, sample_analysis, mock_logger, tmp_path
    ):
        """Verify the analysis audible_segments are passed to waveform generator."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer, \
                 patch('karaoke_gen.utils.gen_cli.WaveformGenerator') as MockWaveformGen, \
                 patch('karaoke_gen.utils.gen_cli.InstrumentalReviewServer') as MockServer:
                
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.return_value = sample_analysis
                
                mock_waveform_instance = MockWaveformGen.return_value
                mock_waveform_instance.generate.return_value = "waveform.png"
                
                mock_server_instance = MockServer.return_value
                mock_server_instance._selection_event = MagicMock()
                mock_server_instance._selection_event.wait.return_value = None
                mock_server_instance.get_selection.return_value = "clean"
                
                run_instrumental_review(track=sample_track, logger=mock_logger)
                
                # Verify the correct segments were passed
                call_kwargs = mock_waveform_instance.generate.call_args.kwargs
                passed_segments = call_kwargs['segments']
                
                assert len(passed_segments) == 2
                assert passed_segments[0].start_seconds == 10.0
                assert passed_segments[1].start_seconds == 60.0
        finally:
            os.chdir(original_dir)
    
    def test_analyzer_called_with_backing_vocals_path(
        self, sample_track, sample_analysis, mock_logger, tmp_path
    ):
        """Verify AudioAnalyzer.analyze() is called with backing vocals path."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer, \
                 patch('karaoke_gen.utils.gen_cli.WaveformGenerator') as MockWaveformGen, \
                 patch('karaoke_gen.utils.gen_cli.InstrumentalReviewServer') as MockServer:
                
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.return_value = sample_analysis
                
                mock_waveform_instance = MockWaveformGen.return_value
                mock_waveform_instance.generate.return_value = "waveform.png"
                
                mock_server_instance = MockServer.return_value
                mock_server_instance._selection_event = MagicMock()
                mock_server_instance._selection_event.wait.return_value = None
                mock_server_instance.get_selection.return_value = "clean"
                
                run_instrumental_review(track=sample_track, logger=mock_logger)
                
                # Verify analyzer was called with a backing vocals path
                mock_analyzer_instance.analyze.assert_called_once()
                analyzed_path = mock_analyzer_instance.analyze.call_args[0][0]
                assert "Backing Vocals" in analyzed_path or os.path.exists(analyzed_path)
        finally:
            os.chdir(original_dir)
    
    def test_server_started_with_correct_parameters(
        self, sample_track, sample_analysis, mock_logger, tmp_path
    ):
        """Verify InstrumentalReviewServer is created with correct parameters."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer, \
                 patch('karaoke_gen.utils.gen_cli.WaveformGenerator') as MockWaveformGen, \
                 patch('karaoke_gen.utils.gen_cli.InstrumentalReviewServer') as MockServer:
                
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.return_value = sample_analysis
                
                mock_waveform_instance = MockWaveformGen.return_value
                mock_waveform_instance.generate.return_value = "waveform.png"
                
                mock_server_instance = MockServer.return_value
                mock_server_instance._selection_event = MagicMock()
                mock_server_instance._selection_event.wait.return_value = None
                mock_server_instance.get_selection.return_value = "clean"
                
                run_instrumental_review(track=sample_track, logger=mock_logger)
                
                # Verify server was created with expected parameters
                MockServer.assert_called_once()
                server_kwargs = MockServer.call_args.kwargs
                
                assert server_kwargs['base_name'] == "Test - Song"
                assert server_kwargs['analysis'] == sample_analysis
                assert 'waveform_path' in server_kwargs
                assert 'backing_vocals_path' in server_kwargs
                assert 'clean_instrumental_path' in server_kwargs
        finally:
            os.chdir(original_dir)
    
    def test_returns_clean_instrumental_when_clean_selected(
        self, sample_track, sample_analysis, mock_logger, tmp_path
    ):
        """Verify correct path returned when user selects 'clean'."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer, \
                 patch('karaoke_gen.utils.gen_cli.WaveformGenerator') as MockWaveformGen, \
                 patch('karaoke_gen.utils.gen_cli.InstrumentalReviewServer') as MockServer:
                
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.return_value = sample_analysis
                
                mock_waveform_instance = MockWaveformGen.return_value
                mock_waveform_instance.generate.return_value = "waveform.png"
                
                mock_server_instance = MockServer.return_value
                mock_server_instance._selection_event = MagicMock()
                mock_server_instance._selection_event.wait.return_value = None
                mock_server_instance.get_selection.return_value = "clean"
                
                result = run_instrumental_review(track=sample_track, logger=mock_logger)
                
                # Should return the clean instrumental path
                assert result is not None
                assert "Instrumental" in result
                assert "+BV" not in result
        finally:
            os.chdir(original_dir)
    
    def test_returns_with_backing_when_selected(
        self, sample_track, sample_analysis, mock_logger, tmp_path
    ):
        """Verify correct path returned when user selects 'with_backing'."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer, \
                 patch('karaoke_gen.utils.gen_cli.WaveformGenerator') as MockWaveformGen, \
                 patch('karaoke_gen.utils.gen_cli.InstrumentalReviewServer') as MockServer:
                
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.return_value = sample_analysis
                
                mock_waveform_instance = MockWaveformGen.return_value
                mock_waveform_instance.generate.return_value = "waveform.png"
                
                mock_server_instance = MockServer.return_value
                mock_server_instance._selection_event = MagicMock()
                mock_server_instance._selection_event.wait.return_value = None
                mock_server_instance.get_selection.return_value = "with_backing"
                
                result = run_instrumental_review(track=sample_track, logger=mock_logger)
                
                # Should return the combined instrumental path (with backing vocals)
                assert result is not None
                assert "+BV" in result
        finally:
            os.chdir(original_dir)
    
    def test_returns_none_when_no_backing_vocals(
        self, mock_logger, tmp_path
    ):
        """Verify None returned when no backing vocals file exists."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        track = {
            "artist": "Test",
            "title": "Song",
            "track_output_dir": str(tmp_path),
            "separated_audio": {
                "backing_vocals": {},  # No backing vocals
                "clean_instrumental": {},
                "combined_instrumentals": {},
            },
        }
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            result = run_instrumental_review(track=track, logger=mock_logger)
            assert result is None
        finally:
            os.chdir(original_dir)
    
    def test_returns_none_when_no_separated_audio(
        self, mock_logger, tmp_path
    ):
        """Verify None returned when no separated_audio in track."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        track = {
            "artist": "Test",
            "title": "Song",
            "track_output_dir": str(tmp_path),
            "separated_audio": {},
        }
        
        result = run_instrumental_review(track=track, logger=mock_logger)
        assert result is None
    
    def test_handles_exception_gracefully(
        self, sample_track, mock_logger, tmp_path
    ):
        """Verify exceptions are caught and None is returned."""
        from karaoke_gen.utils.gen_cli import run_instrumental_review
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            with patch('karaoke_gen.utils.gen_cli.AudioAnalyzer') as MockAnalyzer:
                # Make analyzer raise an exception
                mock_analyzer_instance = MockAnalyzer.return_value
                mock_analyzer_instance.analyze.side_effect = Exception("Test error")
                
                result = run_instrumental_review(track=sample_track, logger=mock_logger)
                
                # Should return None on error
                assert result is None
                
                # Should log the error
                mock_logger.error.assert_called()
        finally:
            os.chdir(original_dir)


class TestWaveformGeneratorParameterContract:
    """
    Contract tests to verify WaveformGenerator.generate() parameter signature.
    
    These tests ensure the interface is stable and document expected parameters.
    """
    
    def test_generate_accepts_segments_parameter(self):
        """Verify generate() method accepts 'segments' as a keyword argument."""
        from karaoke_gen.instrumental_review import WaveformGenerator
        import inspect
        
        sig = inspect.signature(WaveformGenerator.generate)
        params = sig.parameters
        
        assert 'segments' in params, \
            "WaveformGenerator.generate() must have a 'segments' parameter"
    
    def test_generate_does_not_have_audible_segments_parameter(self):
        """
        Verify generate() does NOT have 'audible_segments' parameter.
        
        This documents that the correct parameter name is 'segments',
        not 'audible_segments' (which matches the model field name).
        """
        from karaoke_gen.instrumental_review import WaveformGenerator
        import inspect
        
        sig = inspect.signature(WaveformGenerator.generate)
        params = sig.parameters
        
        assert 'audible_segments' not in params, \
            "WaveformGenerator.generate() should use 'segments', not 'audible_segments'"
    
    def test_generate_parameter_types_documented(self):
        """Verify generate() method has proper type annotations."""
        from karaoke_gen.instrumental_review import WaveformGenerator
        import inspect
        
        sig = inspect.signature(WaveformGenerator.generate)
        params = sig.parameters
        
        # Key parameters should have annotations
        assert params['audio_path'].annotation == str
        assert params['output_path'].annotation == str

