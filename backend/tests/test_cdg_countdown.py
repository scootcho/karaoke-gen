"""
Tests for CDG countdown handling.

Tests cover:
- _remove_countdown_from_lyrics() helper method
- CDG generation with countdown-padded LRC files
- Timestamp adjustment for instrumental audio sync
"""

import pytest
from karaoke_gen.lyrics_transcriber.output.cdg import CDGGenerator


class TestCDGCountdownRemoval:
    """Test the _remove_countdown_from_lyrics helper method."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a CDGGenerator instance for testing."""
        return CDGGenerator(output_dir=str(tmp_path))

    def test_removes_countdown_segment(self, generator):
        """Test that countdown segment is removed from lyrics data."""
        # Simulated LRC data with countdown at 0.1s and first word at 3.6s
        lyrics_data = [
            {"timestamp": 10, "text": "3... 2... 1..."},  # 0.1s = 10 centiseconds
            {"timestamp": 360, "text": "IF"},  # 3.6s = 360 centiseconds
            {"timestamp": 380, "text": "YOU"},
            {"timestamp": 624, "text": "COULD"},
        ]

        # Remove 3 second countdown padding
        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.0)

        # Countdown segment should be removed (timestamp < 300cs)
        assert len(result) == 3
        assert result[0]["text"] == "IF"

        # Timestamps should be shifted back by 300cs (3 seconds)
        assert result[0]["timestamp"] == 60  # 360 - 300
        assert result[1]["timestamp"] == 80  # 380 - 300
        assert result[2]["timestamp"] == 324  # 624 - 300

    def test_handles_multiple_countdown_segments(self, generator):
        """Test with multiple early segments (e.g., multi-part countdown)."""
        lyrics_data = [
            {"timestamp": 10, "text": "3"},
            {"timestamp": 100, "text": "2"},
            {"timestamp": 200, "text": "1"},
            {"timestamp": 360, "text": "HELLO"},
            {"timestamp": 500, "text": "WORLD"},
        ]

        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.0)

        # All segments before 300cs should be removed
        assert len(result) == 2
        assert result[0]["text"] == "HELLO"
        assert result[0]["timestamp"] == 60  # 360 - 300
        assert result[1]["text"] == "WORLD"
        assert result[1]["timestamp"] == 200  # 500 - 300

    def test_handles_no_countdown_segment(self, generator):
        """Test when LRC has no countdown segment but flag is set."""
        # All timestamps are after the countdown duration
        lyrics_data = [
            {"timestamp": 400, "text": "FIRST"},
            {"timestamp": 500, "text": "SECOND"},
        ]

        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.0)

        # Should still shift timestamps back
        assert len(result) == 2
        assert result[0]["timestamp"] == 100  # 400 - 300
        assert result[1]["timestamp"] == 200  # 500 - 300

    def test_handles_different_padding_durations(self, generator):
        """Test with different countdown padding durations."""
        lyrics_data = [
            {"timestamp": 50, "text": "COUNTDOWN"},  # 0.5s
            {"timestamp": 560, "text": "WORD"},  # 5.6s
        ]

        # With 5s padding (500cs)
        result = generator._remove_countdown_from_lyrics(lyrics_data, 5.0)

        assert len(result) == 1
        assert result[0]["text"] == "WORD"
        assert result[0]["timestamp"] == 60  # 560 - 500

    def test_preserves_text_unchanged(self, generator):
        """Test that text content is preserved exactly."""
        lyrics_data = [
            {"timestamp": 10, "text": "3... 2... 1..."},
            {"timestamp": 360, "text": "HELLO, WORLD!"},
            {"timestamp": 500, "text": "IT'S ME"},
        ]

        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.0)

        assert result[0]["text"] == "HELLO, WORLD!"
        assert result[1]["text"] == "IT'S ME"

    def test_empty_lyrics_list(self, generator):
        """Test with empty lyrics list."""
        result = generator._remove_countdown_from_lyrics([], 3.0)
        assert result == []

    def test_all_segments_in_countdown_period(self, generator):
        """Test when all segments are within countdown period."""
        lyrics_data = [
            {"timestamp": 10, "text": "A"},
            {"timestamp": 100, "text": "B"},
            {"timestamp": 200, "text": "C"},
        ]

        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.0)

        # All segments removed - should return empty after shifting
        assert len(result) == 0

    def test_segment_exactly_at_boundary(self, generator):
        """Test with segment timestamp exactly at countdown boundary."""
        lyrics_data = [
            {"timestamp": 299, "text": "ALMOST"},  # Just before 3s
            {"timestamp": 300, "text": "EXACTLY"},  # Exactly at 3s
            {"timestamp": 301, "text": "AFTER"},  # Just after 3s
        ]

        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.0)

        # timestamp < countdown_cs means 299 is removed, 300 and 301 stay
        assert len(result) == 2
        assert result[0]["text"] == "EXACTLY"
        assert result[0]["timestamp"] == 0  # 300 - 300
        assert result[1]["text"] == "AFTER"
        assert result[1]["timestamp"] == 1  # 301 - 300

    def test_fractional_countdown_duration(self, generator):
        """Test with fractional countdown duration (e.g., 3.5 seconds)."""
        lyrics_data = [
            {"timestamp": 100, "text": "EARLY"},  # 1s
            {"timestamp": 340, "text": "MIDDLE"},  # 3.4s - still in countdown
            {"timestamp": 360, "text": "AFTER"},  # 3.6s - after 3.5s
        ]

        result = generator._remove_countdown_from_lyrics(lyrics_data, 3.5)

        # 350cs boundary
        assert len(result) == 1
        assert result[0]["text"] == "AFTER"
        assert result[0]["timestamp"] == 10  # 360 - 350


class TestCDGGenerateFromLRCWithCountdown:
    """Test generate_cdg_from_lrc with countdown parameters."""

    @pytest.fixture
    def generator(self, tmp_path):
        """Create a CDGGenerator instance for testing."""
        return CDGGenerator(output_dir=str(tmp_path))

    def test_passes_countdown_params_to_parse(self, generator, tmp_path, mocker):
        """Test that countdown params are used when processing LRC."""
        # Create a test LRC file with countdown
        lrc_file = tmp_path / "test.lrc"
        lrc_file.write_text("""[re:MidiCo]
[00:00.100]1:/3... 2... 1...
[00:03.600]1:/If
[00:03.800]1:you
""")

        audio_file = tmp_path / "test.flac"
        audio_file.write_text("fake audio")

        # Mock the methods that would actually generate the CDG
        mock_remove = mocker.patch.object(
            generator, "_remove_countdown_from_lyrics", wraps=generator._remove_countdown_from_lyrics
        )
        mocker.patch.object(generator, "_validate_and_setup_font")
        mocker.patch.object(generator, "_create_toml_file", return_value=str(tmp_path / "test.toml"))
        mocker.patch.object(generator, "_compose_cdg")
        mocker.patch.object(generator, "_find_cdg_zip", return_value=str(tmp_path / "test.zip"))
        mocker.patch.object(generator, "_extract_cdg_files")
        mocker.patch.object(generator, "_get_cdg_path", return_value=str(tmp_path / "test.cdg"))
        mocker.patch.object(generator, "_get_mp3_path", return_value=str(tmp_path / "test.mp3"))
        mocker.patch.object(generator, "_verify_output_files")

        # Create mock files
        (tmp_path / "test.toml").write_text("")
        (tmp_path / "test.zip").write_text("")
        (tmp_path / "test.cdg").write_text("")
        (tmp_path / "test.mp3").write_text("")

        # Call with countdown padding enabled
        generator.generate_cdg_from_lrc(
            lrc_file=str(lrc_file),
            audio_file=str(audio_file),
            title="Test",
            artist="Artist",
            cdg_styles={"font_path": None},  # Minimal styles to avoid validation
            lrc_has_countdown_padding=True,
            countdown_padding_seconds=3.0,
        )

        # Verify _remove_countdown_from_lyrics was called
        mock_remove.assert_called_once()
        # The method is called with (lyrics_data, countdown_padding_seconds)
        call_args = mock_remove.call_args
        # Check positional args - second arg should be countdown_padding_seconds
        assert call_args[0][1] == 3.0

    def test_skips_countdown_processing_when_disabled(self, generator, tmp_path, mocker):
        """Test that countdown processing is skipped when flag is False."""
        lrc_file = tmp_path / "test.lrc"
        lrc_file.write_text("[00:03.600]1:/Test\n")

        audio_file = tmp_path / "test.flac"
        audio_file.write_text("fake audio")

        mock_remove = mocker.patch.object(generator, "_remove_countdown_from_lyrics")
        mocker.patch.object(generator, "_validate_and_setup_font")
        mocker.patch.object(generator, "_create_toml_file", return_value=str(tmp_path / "test.toml"))
        mocker.patch.object(generator, "_compose_cdg")
        mocker.patch.object(generator, "_find_cdg_zip", return_value=str(tmp_path / "test.zip"))
        mocker.patch.object(generator, "_extract_cdg_files")
        mocker.patch.object(generator, "_get_cdg_path", return_value=str(tmp_path / "test.cdg"))
        mocker.patch.object(generator, "_get_mp3_path", return_value=str(tmp_path / "test.mp3"))
        mocker.patch.object(generator, "_verify_output_files")

        # Create mock files
        (tmp_path / "test.toml").write_text("")
        (tmp_path / "test.zip").write_text("")
        (tmp_path / "test.cdg").write_text("")
        (tmp_path / "test.mp3").write_text("")

        # Call with countdown padding DISABLED (default)
        generator.generate_cdg_from_lrc(
            lrc_file=str(lrc_file),
            audio_file=str(audio_file),
            title="Test",
            artist="Artist",
            cdg_styles={"font_path": None},
            lrc_has_countdown_padding=False,
        )

        # Verify _remove_countdown_from_lyrics was NOT called
        mock_remove.assert_not_called()
