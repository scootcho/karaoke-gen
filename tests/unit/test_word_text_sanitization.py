"""Tests for Word text sanitization — ensures embedded newlines never reach ASS output."""

import pytest
from karaoke_gen.lyrics_transcriber.types import Word, LyricsSegment


class TestWordTextSanitization:
    """Word.__post_init__ must strip whitespace/newlines from text."""

    def test_trailing_newline_stripped(self):
        word = Word(id="w1", text="spell\n", start_time=1.0, end_time=2.0)
        assert word.text == "spell"

    def test_trailing_double_newline_stripped(self):
        word = Word(id="w1", text="end\n\n", start_time=1.0, end_time=2.0)
        assert word.text == "end"

    def test_leading_whitespace_stripped(self):
        word = Word(id="w1", text=" hello", start_time=1.0, end_time=2.0)
        assert word.text == "hello"

    def test_mixed_whitespace_stripped(self):
        word = Word(id="w1", text="\n spell \n", start_time=1.0, end_time=2.0)
        assert word.text == "spell"

    def test_clean_text_unchanged(self):
        word = Word(id="w1", text="hello", start_time=1.0, end_time=2.0)
        assert word.text == "hello"

    def test_from_dict_strips_text(self):
        """from_dict must also strip — this was the original bug."""
        word = Word.from_dict({
            "id": "w1",
            "text": "spell\n",
            "start_time": 1.0,
            "end_time": 2.0,
        })
        assert word.text == "spell"

    def test_from_dict_with_double_newline(self):
        word = Word.from_dict({
            "id": "w1",
            "text": "broken\n\n",
            "start_time": 1.0,
            "end_time": 2.0,
        })
        assert word.text == "broken"
