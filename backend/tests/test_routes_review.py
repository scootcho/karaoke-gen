"""
Unit tests for review.py routes and related components.

These tests verify the review-related state transitions and data structures.
Tests that require full backend imports are in the emulator integration tests.
"""
import pytest
import json


class TestJobStatusTransitionsForReview:
    """Tests for review-related state transitions.
    
    These tests verify the Job model's state machine handles review flow correctly.
    """
    
    def test_awaiting_review_can_transition_to_in_review(self):
        """Test AWAITING_REVIEW -> IN_REVIEW is valid."""
        from backend.models.job import STATE_TRANSITIONS, JobStatus
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.AWAITING_REVIEW, [])
        assert JobStatus.IN_REVIEW in valid_transitions
    
    def test_awaiting_review_can_transition_to_review_complete(self):
        """Test AWAITING_REVIEW -> REVIEW_COMPLETE is valid (skip in_review)."""
        from backend.models.job import STATE_TRANSITIONS, JobStatus
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.AWAITING_REVIEW, [])
        assert JobStatus.REVIEW_COMPLETE in valid_transitions
    
    def test_in_review_can_transition_to_review_complete(self):
        """Test IN_REVIEW -> REVIEW_COMPLETE is valid."""
        from backend.models.job import STATE_TRANSITIONS, JobStatus
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.IN_REVIEW, [])
        assert JobStatus.REVIEW_COMPLETE in valid_transitions
    
    def test_review_complete_transitions_to_rendering_video(self):
        """Test REVIEW_COMPLETE -> RENDERING_VIDEO is valid."""
        from backend.models.job import STATE_TRANSITIONS, JobStatus
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.REVIEW_COMPLETE, [])
        assert JobStatus.RENDERING_VIDEO in valid_transitions
    
    def test_rendering_video_status_exists(self):
        """Test RENDERING_VIDEO status exists in JobStatus enum."""
        from backend.models.job import JobStatus
        assert hasattr(JobStatus, 'RENDERING_VIDEO')
        assert JobStatus.RENDERING_VIDEO.value == "rendering_video"
    
    def test_rendering_video_transitions_to_instrumental(self):
        """Test RENDERING_VIDEO -> AWAITING_INSTRUMENTAL_SELECTION is valid."""
        from backend.models.job import STATE_TRANSITIONS, JobStatus
        valid_transitions = STATE_TRANSITIONS.get(JobStatus.RENDERING_VIDEO, [])
        assert JobStatus.AWAITING_INSTRUMENTAL_SELECTION in valid_transitions


class TestStylesConfigRequirements:
    """Tests documenting the required fields for ASS subtitle generation.
    
    These tests verify that the styles config format is documented correctly.
    The actual styles creation is tested in integration tests.
    """
    
    def test_required_karaoke_fields_documented(self):
        """Document required karaoke style fields for ASS generation."""
        # These fields are required by the ASS subtitle generator
        # Missing any of them will cause video generation to fail
        required_fields = [
            "font",        # Font name for ASS
            "font_path",   # Path to font file (can be empty string, NOT None)
            "ass_name",    # Style name in ASS file
            "primary_color",    # Format: "R, G, B, A"
            "secondary_color",  # Format: "R, G, B, A"
            "outline_color",    # Format: "R, G, B, A"
            "back_color",       # Format: "R, G, B, A"
            "bold",        # Boolean
            "italic",      # Boolean
            "underline",   # Boolean
            "strike_out",  # Boolean
            "scale_x",     # Integer
            "scale_y",     # Integer
            "spacing",     # Integer
            "angle",       # Float
            "border_style", # Integer
            "outline",     # Integer
            "shadow",      # Integer
            "margin_l",    # Integer
            "margin_r",    # Integer
            "margin_v",    # Integer
            "encoding",    # Integer
        ]
        
        # This test documents the required fields
        # Actual validation happens in integration tests
        assert len(required_fields) == 22
        assert "ass_name" in required_fields  # This was missing initially
        assert "font_path" in required_fields  # Must be string, not None
    
    def test_minimal_styles_structure(self):
        """Document the minimal styles JSON structure."""
        minimal_styles = {
            "karaoke": {
                "background_color": "#000000",
                "font_path": "",  # MUST be string, NOT None
                "font": "Arial",
                "ass_name": "Default",  # REQUIRED
                "primary_color": "112, 112, 247, 255",
                "secondary_color": "255, 255, 255, 255",
                "outline_color": "26, 58, 235, 255",
                "back_color": "0, 0, 0, 0",
                "bold": False,
                "italic": False,
                "underline": False,
                "strike_out": False,
                "scale_x": 100,
                "scale_y": 100,
                "spacing": 0,
                "angle": 0.0,
                "border_style": 1,
                "outline": 1,
                "shadow": 0,
                "margin_l": 0,
                "margin_r": 0,
                "margin_v": 0,
                "encoding": 0
            }
        }
        
        # Verify structure is valid JSON
        json_str = json.dumps(minimal_styles)
        parsed = json.loads(json_str)
        
        assert "karaoke" in parsed
        assert parsed["karaoke"]["font_path"] == ""  # Not None
        assert parsed["karaoke"]["ass_name"] == "Default"


class TestCorrectionDataMerging:
    """Tests documenting correction data merging requirements.
    
    The LyricsTranscriber React UI sends only partial correction data:
    - corrections
    - corrected_segments
    
    The backend must merge this with the original corrections.json to
    reconstruct a full CorrectionResult.
    """
    
    def test_frontend_sends_partial_data(self):
        """Document what the frontend sends."""
        # The frontend sends only these fields
        frontend_payload = {
            "corrections": [],  # List of corrections made
            "corrected_segments": []  # Updated segment data
        }
        
        # This is NOT a full CorrectionResult
        assert "original_segments" not in frontend_payload
        assert "metadata" not in frontend_payload
    
    def test_merging_strategy(self):
        """Document the merging strategy for corrections."""
        # Original data has full structure
        original_data = {
            "original_segments": [{"id": 1, "text": "test"}],
            "corrected_segments": [{"id": 1, "text": "test"}],
            "corrections": [],
            "metadata": {"artist": "Test"}
        }
        
        # Frontend sends partial update
        frontend_update = {
            "corrections": [{"id": 1, "type": "edit"}],
            "corrected_segments": [{"id": 1, "text": "updated"}]
        }
        
        # Merging strategy: update only the fields sent by frontend
        if 'corrections' in frontend_update:
            original_data['corrections'] = frontend_update['corrections']
        if 'corrected_segments' in frontend_update:
            original_data['corrected_segments'] = frontend_update['corrected_segments']
        
        # Result preserves original_segments and metadata
        assert original_data['original_segments'] == [{"id": 1, "text": "test"}]
        assert original_data['metadata'] == {"artist": "Test"}
        # But has updated corrections and corrected_segments
        assert original_data['corrections'] == [{"id": 1, "type": "edit"}]
        assert original_data['corrected_segments'] == [{"id": 1, "text": "updated"}]


class TestPreviewStyleLoading:
    """Tests for custom style loading in preview video generation.
    
    When a job has custom styles (uploaded via --style_params_json), these
    must be loaded and applied to preview videos, not just the final render.
    
    This was a bug: preview videos were using minimal styles (black background)
    even when the job had custom backgrounds and fonts configured.
    """
    
    def test_get_or_create_styles_with_custom_styles(self, tmp_path):
        """Test that custom styles are downloaded and applied for preview."""
        import os
        from unittest.mock import Mock, MagicMock
        from backend.api.routes.review import _get_or_create_styles
        
        # Create mock job with custom styles
        mock_job = Mock()
        mock_job.job_id = "test123"
        mock_job.style_params_gcs_path = "uploads/test123/style/style_params.json"
        mock_job.style_assets = {
            "style_params": "uploads/test123/style/style_params.json",
            "karaoke_background": "uploads/test123/style/karaoke_background.png",
            "font": "uploads/test123/style/font.ttf",
        }
        
        # Create source style params file
        source_style_params = tmp_path / "source_styles.json"
        style_data = {
            "karaoke": {
                "background_image": "/original/path/background.png",
                "font_path": "/original/path/font.ttf",
                "background_color": "#000000",
                "font": "Arial",
                "ass_name": "Default",
            }
        }
        source_style_params.write_text(json.dumps(style_data))
        
        # Create source asset files
        source_background = tmp_path / "background.png"
        source_background.write_bytes(b"PNG image data")
        source_font = tmp_path / "font.ttf"
        source_font.write_bytes(b"TTF font data")
        
        # Create mock storage that "downloads" files by copying from source
        mock_storage = Mock()
        def mock_download(gcs_path, local_path):
            if "style_params.json" in gcs_path:
                with open(local_path, 'w') as f:
                    f.write(source_style_params.read_text())
            elif "karaoke_background" in gcs_path:
                with open(local_path, 'wb') as f:
                    f.write(source_background.read_bytes())
            elif "font.ttf" in gcs_path:
                with open(local_path, 'wb') as f:
                    f.write(source_font.read_bytes())
        mock_storage.download_file = mock_download
        
        # Call the function
        styles_path = _get_or_create_styles(mock_job, str(tmp_path / "workdir"), mock_storage)
        
        # Verify styles file was created
        assert os.path.exists(styles_path)
        
        # Load and verify the styles have updated paths
        with open(styles_path, 'r') as f:
            result_styles = json.load(f)
        
        # The paths should now point to the local downloaded files, not the original paths
        assert "karaoke" in result_styles
        assert result_styles["karaoke"]["background_image"] != "/original/path/background.png"
        assert "karaoke_background.png" in result_styles["karaoke"]["background_image"]
        assert result_styles["karaoke"]["font_path"] != "/original/path/font.ttf"
        assert "font.ttf" in result_styles["karaoke"]["font_path"]
    
    def test_get_or_create_styles_falls_back_to_minimal(self, tmp_path):
        """Test that minimal styles are used when job has no custom styles."""
        import os
        from unittest.mock import Mock
        from backend.api.routes.review import _get_or_create_styles
        
        # Create mock job WITHOUT custom styles
        mock_job = Mock()
        mock_job.job_id = "test456"
        mock_job.style_params_gcs_path = None  # No custom styles
        mock_job.style_assets = {}
        
        mock_storage = Mock()
        
        # Call the function
        styles_path = _get_or_create_styles(mock_job, str(tmp_path), mock_storage)
        
        # Verify styles file was created
        assert os.path.exists(styles_path)
        
        # Load and verify minimal styles
        with open(styles_path, 'r') as f:
            result_styles = json.load(f)
        
        # Should have karaoke section with minimal/default values
        assert "karaoke" in result_styles
        assert result_styles["karaoke"]["background_color"] == "#000000"
        assert result_styles["karaoke"]["font"] == "Arial"
        # Should NOT have background_image (minimal styles don't include it)
        assert "background_image" not in result_styles["karaoke"] or result_styles["karaoke"].get("background_image") is None
    
    def test_asset_mapping_is_complete(self):
        """Verify all required asset mappings are defined for preview styles."""
        from backend.api.routes.review import _get_or_create_styles
        import inspect
        
        # Get the source code of the function to check the asset_mapping
        source = inspect.getsource(_get_or_create_styles)
        
        # These mappings must be present for styles to work correctly
        required_mappings = [
            "'karaoke_background'",
            "'intro_background'",
            "'end_background'",
            "'font'",
            "('karaoke', 'background_image')",
            "('karaoke', 'font_path')",
        ]
        
        for mapping in required_mappings:
            assert mapping in source, f"Asset mapping {mapping} not found in _get_or_create_styles"
