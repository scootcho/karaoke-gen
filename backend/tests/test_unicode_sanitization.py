"""
Comprehensive tests for Unicode and special character handling.

This test file verifies that artist/title with Unicode characters (curly quotes,
em dashes, non-ASCII characters) are properly sanitized throughout the codebase
to prevent:
1. HTTP header encoding failures (Content-Disposition, email subjects)
2. API query failures (Google Drive)
3. Filename encoding issues (Modal API, filesystem)

The root cause was job d49efab1 which had title "Mama Says (You Can't Back Down)"
with a curly apostrophe (U+2019) that caused the audio separation to fail because
the Modal API couldn't handle the non-latin-1 character in HTTP headers.
"""

import pytest
from karaoke_gen.utils import sanitize_filename, UNICODE_REPLACEMENTS


class TestSanitizeFilename:
    """Test the sanitize_filename function handles all edge cases."""

    def test_curly_single_quotes(self):
        """Test that curly single quotes are converted to straight quotes."""
        # The exact character that caused job d49efab1 to fail
        assert sanitize_filename("Can't") == "Can't"
        assert sanitize_filename("It's") == "It's"
        # Left single quote
        assert sanitize_filename("'Hello'") == "'Hello'"

    def test_curly_double_quotes(self):
        """Test that curly double quotes are converted to underscores.

        Note: Double quotes are filesystem-unsafe so they become underscores."""
        # Curly quotes first become straight, then straight quotes become underscore
        assert sanitize_filename("\u201cHello\u201d") == "_Hello_"

    def test_em_dash(self):
        """Test that em dashes are converted to regular hyphens."""
        assert sanitize_filename("Artist — Title") == "Artist - Title"
        assert sanitize_filename("Song—Name") == "Song-Name"

    def test_en_dash(self):
        """Test that en dashes are converted to regular hyphens."""
        assert sanitize_filename("1990–2000") == "1990-2000"

    def test_ellipsis(self):
        """Test that horizontal ellipsis is converted to three dots."""
        # Note: The ellipsis becomes "..." but trailing dots are stripped
        assert sanitize_filename("Wait\u2026") == "Wait"
        # But in the middle of a string they're preserved
        assert sanitize_filename("Wait\u2026Here") == "Wait...Here"

    def test_non_breaking_space(self):
        """Test that non-breaking spaces are converted to regular spaces."""
        # U+00A0 is non-breaking space
        assert sanitize_filename("Hello\u00A0World") == "Hello World"

    def test_filesystem_unsafe_characters(self):
        """Test that filesystem-unsafe characters are replaced."""
        assert sanitize_filename("file/name") == "file_name"
        assert sanitize_filename("file\\name") == "file_name"
        assert sanitize_filename("file:name") == "file_name"
        assert sanitize_filename("file*name") == "file_name"
        assert sanitize_filename("file?name") == "file_name"
        assert sanitize_filename('file"name') == "file_name"
        assert sanitize_filename("file<name") == "file_name"
        assert sanitize_filename("file>name") == "file_name"
        assert sanitize_filename("file|name") == "file_name"

    def test_trailing_periods_and_spaces(self):
        """Test that trailing periods and spaces are removed."""
        assert sanitize_filename("filename.") == "filename"
        assert sanitize_filename("filename...") == "filename"
        assert sanitize_filename("filename ") == "filename"
        assert sanitize_filename("filename . ") == "filename"

    def test_leading_periods_and_spaces(self):
        """Test that leading periods and spaces are removed."""
        assert sanitize_filename(".filename") == "filename"
        assert sanitize_filename("...filename") == "filename"
        assert sanitize_filename(" filename") == "filename"
        assert sanitize_filename(" . filename") == "filename"

    def test_multiple_underscores_collapsed(self):
        """Test that multiple consecutive underscores are collapsed to one."""
        assert sanitize_filename("file___name") == "file_name"
        # Multiple unsafe chars in a row
        assert sanitize_filename("file?*:name") == "file_name"

    def test_multiple_spaces_collapsed(self):
        """Test that multiple consecutive spaces are collapsed to one."""
        assert sanitize_filename("file   name") == "file name"

    def test_none_input(self):
        """Test that None input returns None."""
        assert sanitize_filename(None) is None

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert sanitize_filename("") == ""

    def test_real_world_examples(self):
        """Test real-world examples that have caused issues."""
        # The exact title from job d49efab1
        assert sanitize_filename("Mama Says (You Can't Back Down)") == "Mama Says (You Can't Back Down)"

        # Broadway cast with smart quotes
        assert sanitize_filename("Footloose (Broadway Cast) \u2014 \u201cFinal Song\u201d") == "Footloose (Broadway Cast) - _Final Song_"

        # Japanese artist with em dash
        assert sanitize_filename("宇多田ヒカル — First Love") == "宇多田ヒカル - First Love"

        # Korean title (should pass through unchanged)
        assert sanitize_filename("아이유 - 좋은 날") == "아이유 - 좋은 날"

        # Mixed content
        assert sanitize_filename("L'Arc～en～Ciel - Driver's High") == "L'Arc～en～Ciel - Driver's High"

    def test_combination_of_issues(self):
        """Test strings with multiple problematic characters."""
        result = sanitize_filename("It\u2019s \u201cMy\u201d Song \u2014 Volume\u20261")
        # Curly ' -> ', curly " -> _ (via filesystem check), em dash -> -, ellipsis -> ...
        assert result == "It's _My_ Song - Volume...1"

    def test_unicode_replacements_dict_complete(self):
        """Verify all expected Unicode characters are in the replacements dict."""
        # Curly quotes
        assert "\u2018" in UNICODE_REPLACEMENTS  # LEFT SINGLE QUOTATION MARK
        assert "\u2019" in UNICODE_REPLACEMENTS  # RIGHT SINGLE QUOTATION MARK
        assert "\u201A" in UNICODE_REPLACEMENTS  # SINGLE LOW-9 QUOTATION MARK
        assert "\u201B" in UNICODE_REPLACEMENTS  # SINGLE HIGH-REVERSED-9 QUOTATION MARK
        assert "\u201C" in UNICODE_REPLACEMENTS  # LEFT DOUBLE QUOTATION MARK
        assert "\u201D" in UNICODE_REPLACEMENTS  # RIGHT DOUBLE QUOTATION MARK
        assert "\u201E" in UNICODE_REPLACEMENTS  # DOUBLE LOW-9 QUOTATION MARK
        assert "\u201F" in UNICODE_REPLACEMENTS  # DOUBLE HIGH-REVERSED-9 QUOTATION MARK
        # Dashes
        assert "\u2013" in UNICODE_REPLACEMENTS  # EN DASH
        assert "\u2014" in UNICODE_REPLACEMENTS  # EM DASH
        # Other
        assert "\u2026" in UNICODE_REPLACEMENTS  # HORIZONTAL ELLIPSIS
        assert "\u00A0" in UNICODE_REPLACEMENTS  # NON-BREAKING SPACE


class TestSanitizationInContext:
    """Test that sanitization is applied correctly in various contexts.

    These tests verify that the fixes we applied work in the actual
    code paths that use artist/title data.
    """

    def test_artist_title_format_for_audio_separation(self):
        """Verify artist-title formatting is sanitized for Modal API."""
        # Simulate what audio_worker.py does
        artist = "Footloose (Broadway Cast)"
        title = "Mama Says (You Can\u2019t Back Down)"  # Curly apostrophe U+2019

        safe_artist = sanitize_filename(artist) if artist else "Unknown"
        safe_title = sanitize_filename(title) if title else "Unknown"
        artist_title = f"{safe_artist} - {safe_title}"

        # The curly apostrophe should be converted to straight
        assert "'" in artist_title  # Straight apostrophe
        assert "\u2019" not in artist_title  # No curly apostrophe (U+2019)

    def test_email_subject_safe_for_latin1(self):
        """Verify email subjects can be encoded to latin-1 after sanitization."""
        artist = "Café del Mar"  # Has accented e
        title = "It\u2019s a \u201cBeautiful\u201d Day \u2014 Remix"

        safe_artist = sanitize_filename(artist) if artist else None
        safe_title = sanitize_filename(title) if title else None
        subject = f"{safe_artist} - {safe_title}"

        # Accented characters should pass through (they're valid latin-1)
        assert "é" in subject
        # But curly quotes and em dash should be converted
        assert "'" in subject  # Straight apostrophe
        assert "-" in subject  # Regular hyphen
        # No curly apostrophe (U+2019)
        assert "\u2019" not in subject

    def test_content_disposition_safe(self):
        """Verify filenames are safe for HTTP Content-Disposition headers."""
        artist = "Artist\u2019s \u201cName\u201d"
        title = "Song\u2014Title"

        safe_artist = sanitize_filename(artist) if artist else None
        safe_title = sanitize_filename(title) if title else None
        filename = f"{safe_artist} - {safe_title} (Final Karaoke).mp4"

        # Should be able to encode to latin-1 for HTTP headers
        try:
            filename.encode('latin-1')
            can_encode = True
        except UnicodeEncodeError:
            can_encode = False

        # Standard ASCII chars and latin-1 safe accented chars should work
        # Note: The test above with 'é' passes latin-1; smart quotes do not
        assert can_encode

    def test_google_drive_query_safe(self):
        """Verify filenames don't break Google Drive API queries."""
        base_name = "Artist\u2019s \u201cSong\u201d"

        safe_base_name = sanitize_filename(base_name) if base_name else base_name
        filename = f"NOMAD-1234 - {safe_base_name}.mp4"

        # Google Drive queries use single quotes - our sanitized string
        # should have straight single quotes, not curly
        # The query escaping handles straight quotes: '
        escaped = filename.replace("'", "\\'")
        query = f"name='{escaped}'"

        # Should be a valid query string (no curly quotes to break syntax)
        assert "\u2019" not in query  # No curly single quote (U+2019)
        assert "\u2018" not in query  # No curly single quote (U+2018)

    def test_dropbox_path_safe(self):
        """Verify Dropbox paths don't have problematic characters."""
        artist = "Don\u2019t Stop"
        title = "Believin\u2019"

        safe_artist = sanitize_filename(artist) if artist else "Unknown"
        safe_title = sanitize_filename(title) if title else "Unknown"
        folder_name = f"NOMAD-1234 - {safe_artist} - {safe_title}"
        remote_path = f"/Karaoke/{folder_name}"

        # Path should not have curly quotes (U+2018 and U+2019)
        assert "\u2018" not in remote_path
        assert "\u2019" not in remote_path
        # But should have the converted straight apostrophe
        assert "'" in remote_path


class TestInternationalCharacters:
    """Test that international/non-ASCII characters are handled properly.

    The goal is NOT to strip all non-ASCII, but to convert problematic
    Unicode to safe equivalents while preserving legitimate international text.
    """

    def test_japanese_preserved(self):
        """Japanese characters should pass through unchanged."""
        assert sanitize_filename("宇多田ヒカル") == "宇多田ヒカル"
        assert sanitize_filename("君が代") == "君が代"

    def test_korean_preserved(self):
        """Korean characters should pass through unchanged."""
        assert sanitize_filename("방탄소년단") == "방탄소년단"
        assert sanitize_filename("좋은 날") == "좋은 날"

    def test_chinese_preserved(self):
        """Chinese characters should pass through unchanged."""
        assert sanitize_filename("周杰倫") == "周杰倫"
        assert sanitize_filename("青花瓷") == "青花瓷"

    def test_cyrillic_preserved(self):
        """Cyrillic characters should pass through unchanged."""
        assert sanitize_filename("Тату") == "Тату"
        assert sanitize_filename("Не верь, не бойся") == "Не верь, не бойся"

    def test_arabic_preserved(self):
        """Arabic characters should pass through unchanged."""
        assert sanitize_filename("فيروز") == "فيروز"

    def test_accented_latin_preserved(self):
        """Accented Latin characters should pass through unchanged."""
        assert sanitize_filename("Café") == "Café"
        assert sanitize_filename("Señorita") == "Señorita"
        assert sanitize_filename("Naïve") == "Naïve"
        assert sanitize_filename("Björk") == "Björk"

    def test_mixed_script_preserved(self):
        """Mixed script text should work correctly."""
        # Japanese artist, English title
        assert sanitize_filename("宇多田ヒカル - First Love") == "宇多田ヒカル - First Love"
        # K-pop with English
        assert sanitize_filename("BTS 방탄소년단 - Dynamite") == "BTS 방탄소년단 - Dynamite"


class TestEdgeCasesAndRegression:
    """Edge cases and regression tests for specific bugs."""

    def test_job_d49efab1_exact_title(self):
        """Exact reproduction of job d49efab1 failure case.

        The job had:
        - artist: "Footloose (Broadway Cast)" (from display_artist override)
        - title: "Mama Says (You Can't Back Down)" (with curly apostrophe U+2019)

        This caused Stage 2 audio separation to fail because the filename
        with the curly apostrophe couldn't be encoded in HTTP headers.
        """
        artist = "Footloose (Broadway Cast)"
        title = "Mama Says (You Can\u2019t Back Down)"  # Explicit U+2019

        safe_artist = sanitize_filename(artist)
        safe_title = sanitize_filename(title)
        artist_title = f"{safe_artist} - {safe_title}"

        # The result should use straight apostrophe
        assert "Can't" in artist_title
        assert "\u2019" not in artist_title  # No curly apostrophe

        # Should be HTTP-header safe
        try:
            artist_title.encode('latin-1')
            header_safe = True
        except UnicodeEncodeError:
            header_safe = False
        assert header_safe

    def test_double_sanitization_idempotent(self):
        """Sanitizing twice should give the same result as once."""
        original = "It\u2019s \u201cMy\u201d Song \u2014 Test\u2026"
        once = sanitize_filename(original)
        twice = sanitize_filename(once)
        assert once == twice

    def test_only_problematic_chars_string(self):
        """Test string made entirely of problematic characters."""
        result = sanitize_filename("\u2018\u2019\u201c\u201d\u2014\u2026")
        # Should become: ''""--...  then quotes -> underscores, collapses
        # Actually: ' ' " " - ... -> underscores for filesystem chars
        assert result  # Should not be empty

    def test_very_long_filename(self):
        """Test that very long filenames are handled."""
        long_name = "A" * 1000
        result = sanitize_filename(long_name)
        assert result == long_name  # No truncation in sanitize_filename itself

    def test_special_musical_characters(self):
        """Test musical symbols and special characters."""
        # These should pass through as they're not in our replacement list
        assert "♪" in sanitize_filename("♪ Intro ♪")
        assert "♫" in sanitize_filename("♫ Music ♫")
        assert "♯" in sanitize_filename("C♯ Minor")
        assert "♭" in sanitize_filename("B♭ Major")
