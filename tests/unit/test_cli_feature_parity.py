"""
Tests verifying feature parity between local and remote CLIs.

These tests ensure that both local (karaoke-gen) and remote (karaoke-gen-remote)
CLIs use the same shared core module for instrumental review functionality.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestSharedCoreModuleAccess:
    """Verify both CLIs can access the shared core module."""
    
    def test_local_cli_can_import_analyzer(self):
        """Local CLI should be able to import AudioAnalyzer."""
        from karaoke_gen.instrumental_review import AudioAnalyzer
        assert AudioAnalyzer is not None
    
    def test_local_cli_can_import_editor(self):
        """Local CLI should be able to import AudioEditor."""
        from karaoke_gen.instrumental_review import AudioEditor
        assert AudioEditor is not None
    
    def test_local_cli_can_import_waveform_generator(self):
        """Local CLI should be able to import WaveformGenerator."""
        from karaoke_gen.instrumental_review import WaveformGenerator
        assert WaveformGenerator is not None
    
    def test_local_cli_can_import_review_server(self):
        """Local CLI should be able to import InstrumentalReviewServer."""
        from karaoke_gen.instrumental_review import InstrumentalReviewServer
        assert InstrumentalReviewServer is not None
    
    def test_backend_can_import_analyzer(self):
        """Backend should be able to import AudioAnalyzer."""
        from karaoke_gen.instrumental_review import AudioAnalyzer
        # Backend service wrapper imports from the same module
        from backend.services.audio_analysis_service import AudioAnalysisService
        
        # Verify they use the same analyzer class
        mock_storage = MagicMock()
        service = AudioAnalysisService(storage_service=mock_storage)
        assert service.analyzer.__class__.__name__ == "AudioAnalyzer"
    
    def test_backend_can_import_editor(self):
        """Backend should be able to import AudioEditor."""
        from karaoke_gen.instrumental_review import AudioEditor
        from backend.services.audio_editing_service import AudioEditingService
        
        mock_storage = MagicMock()
        service = AudioEditingService(storage_service=mock_storage)
        assert service.editor.__class__.__name__ == "AudioEditor"


class TestAnalyzerParity:
    """Verify that both CLIs get identical analysis results."""
    
    def test_analyzer_parameters_match(self):
        """Analyzer should have same default parameters for both CLIs."""
        from karaoke_gen.instrumental_review import AudioAnalyzer
        
        # Default analyzer for local CLI
        local_analyzer = AudioAnalyzer()
        
        # The backend service uses the same analyzer with defaults
        from backend.services.audio_analysis_service import AudioAnalysisService
        mock_storage = MagicMock()
        backend_service = AudioAnalysisService(storage_service=mock_storage)
        
        # Same default threshold
        assert local_analyzer.silence_threshold_db == backend_service.analyzer.silence_threshold_db
        assert local_analyzer.silence_threshold_db == -40.0
        
        # Same default min segment duration
        assert local_analyzer.min_segment_duration_ms == backend_service.analyzer.min_segment_duration_ms


class TestEditorParity:
    """Verify that both CLIs create identical custom instrumentals."""
    
    def test_editor_output_format_match(self):
        """Editor should produce same output format for both CLIs."""
        from karaoke_gen.instrumental_review import AudioEditor
        
        # Default editor for local CLI
        local_editor = AudioEditor()
        
        # Backend service uses same editor with same defaults
        from backend.services.audio_editing_service import AudioEditingService
        mock_storage = MagicMock()
        backend_service = AudioEditingService(storage_service=mock_storage)
        
        # Same default output format
        assert local_editor.output_format == backend_service.editor.output_format
        assert local_editor.output_format == "flac"


class TestModelConsistency:
    """Verify that models are consistent across CLIs."""
    
    def test_mute_region_model_shared(self):
        """MuteRegion model should be shared across CLIs."""
        from karaoke_gen.instrumental_review import MuteRegion
        from backend.models.requests import MuteRegionRequest
        
        # Both should validate start < end
        region = MuteRegion(start_seconds=10.0, end_seconds=20.0)
        request = MuteRegionRequest(start_seconds=10.0, end_seconds=20.0)
        
        assert region.start_seconds == request.start_seconds
        assert region.end_seconds == request.end_seconds
    
    def test_analysis_result_fields_match(self):
        """AnalysisResult should have fields expected by both CLIs."""
        from karaoke_gen.instrumental_review import AnalysisResult, RecommendedSelection
        
        # Create an analysis result
        result = AnalysisResult(
            has_audible_content=True,
            total_duration_seconds=180.0,
            audible_segments=[],
            recommended_selection=RecommendedSelection.REVIEW_NEEDED,
            silence_threshold_db=-40.0,
        )
        
        # Fields expected by the API response
        assert hasattr(result, 'has_audible_content')
        assert hasattr(result, 'total_duration_seconds')
        assert hasattr(result, 'audible_segments')
        assert hasattr(result, 'recommended_selection')
        assert hasattr(result, 'total_audible_duration_seconds')
        assert hasattr(result, 'audible_percentage')


class TestReviewServerParity:
    """Verify that local review server matches backend API."""
    
    def test_review_server_exists(self):
        """Local review server should exist."""
        from karaoke_gen.instrumental_review.server import InstrumentalReviewServer
        assert InstrumentalReviewServer is not None
    
    def test_review_server_can_be_instantiated(self):
        """Local review server should be instantiable with proper parameters."""
        from karaoke_gen.instrumental_review.server import InstrumentalReviewServer
        from karaoke_gen.instrumental_review import AnalysisResult, RecommendedSelection
        
        # Create mock analysis
        analysis = AnalysisResult(
            has_audible_content=False,
            total_duration_seconds=180.0,
            audible_segments=[],
            recommended_selection=RecommendedSelection.CLEAN,
            silence_threshold_db=-40.0,
        )
        
        # Should be able to create server instance
        server = InstrumentalReviewServer(
            output_dir="/tmp",
            base_name="Test - Song",
            analysis=analysis,
            waveform_path="/tmp/waveform.png",
            backing_vocals_path="/tmp/backing.flac",
            clean_instrumental_path="/tmp/clean.flac",
        )
        
        assert server is not None
        assert server.output_dir == "/tmp"
        assert server.base_name == "Test - Song"
    
    def test_review_server_api_endpoints_match_backend(self):
        """Review server should serve same API endpoints as backend."""
        from karaoke_gen.instrumental_review.server import InstrumentalReviewServer
        
        # The server should have methods to create app and register routes
        assert hasattr(InstrumentalReviewServer, '_create_app')
        assert hasattr(InstrumentalReviewServer, '_register_routes')
        assert hasattr(InstrumentalReviewServer, '_get_frontend_html')
        
        # Server should have the main interface methods
        assert hasattr(InstrumentalReviewServer, 'start_and_open_browser')
        assert hasattr(InstrumentalReviewServer, 'get_selection')
        assert hasattr(InstrumentalReviewServer, 'get_custom_instrumental_path')


class TestRemoteCLIAnalysisIntegration:
    """Verify remote CLI uses the analysis API."""
    
    def test_remote_cli_has_analysis_method(self):
        """Remote CLI client should have get_instrumental_analysis method."""
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient
        
        # The client should have the analysis method
        assert hasattr(RemoteKaraokeClient, 'get_instrumental_analysis')
    
    def test_remote_cli_has_browser_method(self):
        """Remote CLI should be able to open browser for review."""
        from karaoke_gen.utils.remote_cli import JobMonitor
        
        # The job monitor should have browser review method
        assert hasattr(JobMonitor, '_open_instrumental_review_and_wait')
    
    def test_remote_cli_handle_instrumental_selection_exists(self):
        """Remote CLI should have handle_instrumental_selection method."""
        from karaoke_gen.utils.remote_cli import JobMonitor
        
        assert hasattr(JobMonitor, 'handle_instrumental_selection')
