"""
Unit tests for theme validation functionality.

Tests validate_theme_completeness() and warning behavior in getter functions.
"""
import logging
import pytest
from karaoke_gen.style_loader import (
    DEFAULT_INTRO_STYLE,
    DEFAULT_END_STYLE,
    DEFAULT_KARAOKE_STYLE,
    DEFAULT_CDG_STYLE,
    validate_theme_completeness,
    get_intro_format,
    get_end_format,
    get_karaoke_format,
    get_cdg_format,
)


class TestValidateThemeCompleteness:
    """Test validate_theme_completeness function."""

    def test_complete_theme(self, caplog):
        """Test that a complete theme passes validation."""
        complete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(complete_theme)

        assert is_complete is True
        assert missing == []

    def test_missing_section(self, caplog):
        """Test that missing sections are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            # Missing karaoke and cdg sections
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert "Missing section: karaoke" in missing
        assert "Missing section: cdg" in missing

    def test_missing_intro_fields(self, caplog):
        """Test that missing intro fields are detected."""
        incomplete_theme = {
            "intro": {
                "video_duration": 5,
                "background_color": "#000000",
                # Missing other required fields
            },
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("intro." in m for m in missing)
        # Check a few specific missing fields
        assert "intro.font" in missing
        assert "intro.artist_color" in missing
        assert "intro.title_color" in missing

    def test_missing_end_fields(self, caplog):
        """Test that missing end fields are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": {
                "video_duration": 5,
                # Missing other required fields
            },
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("end." in m for m in missing)
        assert "end.font" in missing
        assert "end.background_color" in missing

    def test_missing_karaoke_fields(self, caplog):
        """Test that missing karaoke fields are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": {
                "background_color": "#000000",
                "font": "Noto Sans",
                # Missing other required fields
            },
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("karaoke." in m for m in missing)
        assert "karaoke.primary_color" in missing
        assert "karaoke.font_size" in missing

    def test_missing_cdg_fields(self, caplog):
        """Test that missing cdg fields are detected."""
        incomplete_theme = {
            "intro": DEFAULT_INTRO_STYLE.copy(),
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": {
                # Missing all fields
            },
        }

        is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert any("cdg." in m for m in missing)

    def test_logs_warning_on_incomplete(self, caplog):
        """Test that validation logs a warning for incomplete themes."""
        incomplete_theme = {
            "intro": {"video_duration": 5},
            "end": DEFAULT_END_STYLE.copy(),
            "karaoke": DEFAULT_KARAOKE_STYLE.copy(),
            "cdg": DEFAULT_CDG_STYLE.copy(),
        }

        with caplog.at_level(logging.WARNING):
            is_complete, missing = validate_theme_completeness(incomplete_theme)

        assert is_complete is False
        assert "Theme validation failed" in caplog.text
        assert "Missing:" in caplog.text


class TestGetterFunctionWarnings:
    """Test that getter functions warn about incomplete themes."""

    def test_get_intro_format_complete(self, caplog):
        """Test get_intro_format with complete intro section."""
        style_params = {"intro": DEFAULT_INTRO_STYLE.copy()}

        with caplog.at_level(logging.WARNING):
            result = get_intro_format(style_params)

        # Should not warn for complete theme
        assert "Incomplete intro theme" not in caplog.text
        assert result == DEFAULT_INTRO_STYLE

    def test_get_intro_format_incomplete_warns(self, caplog):
        """Test get_intro_format warns about incomplete intro section."""
        style_params = {
            "intro": {
                "video_duration": 5,
                "background_color": "#000000",
                # Missing other fields
            }
        }

        with caplog.at_level(logging.WARNING):
            result = get_intro_format(style_params)

        # Should warn about missing fields
        assert "Incomplete intro theme" in caplog.text
        assert "Missing fields:" in caplog.text
        assert "In future versions, incomplete themes will be rejected" in caplog.text

        # Should still return merged result with defaults (Phase 1 behavior)
        assert result["video_duration"] == 5
        assert result["background_color"] == "#000000"
        assert result["font"] == DEFAULT_INTRO_STYLE["font"]  # From defaults

    def test_get_end_format_incomplete_warns(self, caplog):
        """Test get_end_format warns about incomplete end section."""
        style_params = {"end": {"video_duration": 3}}

        with caplog.at_level(logging.WARNING):
            result = get_end_format(style_params)

        assert "Incomplete end theme" in caplog.text
        assert result["video_duration"] == 3  # Custom value
        assert result["font"] == DEFAULT_END_STYLE["font"]  # From defaults

    def test_get_karaoke_format_incomplete_warns(self, caplog):
        """Test get_karaoke_format warns about incomplete karaoke section."""
        style_params = {"karaoke": {"background_color": "#FF0000"}}

        with caplog.at_level(logging.WARNING):
            result = get_karaoke_format(style_params)

        assert "Incomplete karaoke theme" in caplog.text
        assert result["background_color"] == "#FF0000"  # Custom value
        assert result["font"] == DEFAULT_KARAOKE_STYLE["font"]  # From defaults

    def test_get_cdg_format_incomplete_warns(self, caplog):
        """Test get_cdg_format warns about incomplete cdg section."""
        style_params = {"cdg": {"font_path": "/custom/font.ttf"}}

        with caplog.at_level(logging.WARNING):
            result = get_cdg_format(style_params)

        assert "Incomplete cdg theme" in caplog.text
        assert result["font_path"] == "/custom/font.ttf"  # Custom value
        assert result["instrumental_background"] == DEFAULT_CDG_STYLE["instrumental_background"]  # From defaults

    def test_get_cdg_format_missing_section_returns_none(self):
        """Test get_cdg_format returns None when cdg section is missing."""
        style_params = {"intro": DEFAULT_INTRO_STYLE.copy()}

        result = get_cdg_format(style_params)

        assert result is None

    def test_empty_theme_sections_warn(self, caplog):
        """Test that empty theme sections (empty dicts) trigger warnings."""
        style_params = {
            "intro": {},
            "end": {},
            "karaoke": {},
            "cdg": {},
        }

        with caplog.at_level(logging.WARNING):
            intro = get_intro_format(style_params)
            end = get_end_format(style_params)
            karaoke = get_karaoke_format(style_params)
            cdg = get_cdg_format(style_params)

        # All should warn
        assert caplog.text.count("Incomplete") == 4

        # All should return defaults
        assert intro == DEFAULT_INTRO_STYLE
        assert end == DEFAULT_END_STYLE
        assert karaoke == DEFAULT_KARAOKE_STYLE
        assert cdg == DEFAULT_CDG_STYLE


class TestPartialThemes:
    """Test behavior with partially complete themes."""

    def test_partial_intro_merges_correctly(self):
        """Test that partial themes merge correctly with defaults."""
        style_params = {
            "intro": {
                "video_duration": 10,
                "background_color": "#FF0000",
                "artist_color": "#00FF00",
                # Missing remaining 12 fields
            }
        }

        result = get_intro_format(style_params)

        # Custom values should be present
        assert result["video_duration"] == 10
        assert result["background_color"] == "#FF0000"
        assert result["artist_color"] == "#00FF00"

        # Default values should fill in missing fields
        assert result["font"] == DEFAULT_INTRO_STYLE["font"]
        assert result["title_color"] == DEFAULT_INTRO_STYLE["title_color"]
        assert result["title_region"] == DEFAULT_INTRO_STYLE["title_region"]

    def test_missing_optional_fields_handled(self):
        """Test that None/null fields are preserved."""
        style_params = {
            "intro": DEFAULT_INTRO_STYLE.copy()
        }
        # Explicitly set some optional fields to None
        style_params["intro"]["background_image"] = None
        style_params["intro"]["artist_gradient"] = None

        result = get_intro_format(style_params)

        assert result["background_image"] is None
        assert result["artist_gradient"] is None
