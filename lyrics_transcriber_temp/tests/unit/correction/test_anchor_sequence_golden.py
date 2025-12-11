"""
Golden tests for AnchorSequenceFinder using real song data fixtures.

These tests verify that the AnchorSequenceFinder produces equivalent results
to the baseline fixtures generated from real cache data. They serve as
regression tests to ensure algorithm changes don't break correctness.

Usage:
    pytest tests/unit/correction/test_anchor_sequence_golden.py -v
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any, Tuple

from lyrics_transcriber.types import (
    LyricsData,
    LyricsSegment,
    LyricsMetadata,
    TranscriptionData,
    TranscriptionResult,
    Word,
    ScoredAnchor,
)
from lyrics_transcriber.correction.anchor_sequence import AnchorSequenceFinder


# Path to golden test fixtures
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "anchor_golden"


def load_fixture(fixture_path: Path) -> Dict[str, Any]:
    """Load a fixture JSON file."""
    with open(fixture_path) as f:
        return json.load(f)


def fixture_to_transcription_result(fixture: Dict[str, Any]) -> TranscriptionResult:
    """Convert fixture data to TranscriptionResult."""
    segments = []
    all_words = []
    
    for seg_data in fixture["transcription"]["segments"]:
        words = []
        for w_data in seg_data["words"]:
            word = Word(
                id=w_data["id"],
                text=w_data["text"],
                start_time=w_data.get("start_time") or 0.0,
                end_time=w_data.get("end_time") or 0.0,
                confidence=w_data.get("confidence"),
                created_during_correction=w_data.get("created_during_correction", False),
            )
            words.append(word)
            all_words.append(word)
        
        segment = LyricsSegment(
            id=seg_data["id"],
            text=seg_data["text"],
            words=words,
            start_time=seg_data.get("start_time") or 0.0,
            end_time=seg_data.get("end_time") or 0.0,
        )
        segments.append(segment)
    
    transcription_data = TranscriptionData(
        segments=segments,
        words=all_words,
        text=fixture["transcription"]["text"],
        source="audioshake",
    )
    
    return TranscriptionResult(
        name="audioshake",
        priority=1,
        result=transcription_data,
    )


def fixture_to_references(fixture: Dict[str, Any]) -> Dict[str, LyricsData]:
    """Convert fixture data to references dict."""
    references = {}
    
    for source, ref_data in fixture["references"].items():
        segments = []
        for seg_data in ref_data["segments"]:
            words = []
            for w_data in seg_data["words"]:
                word = Word(
                    id=w_data["id"],
                    text=w_data["text"],
                    start_time=w_data.get("start_time") or 0.0,
                    end_time=w_data.get("end_time") or 0.0,
                    confidence=w_data.get("confidence"),
                    created_during_correction=w_data.get("created_during_correction", False),
                )
                words.append(word)
            
            segment = LyricsSegment(
                id=seg_data["id"],
                text=seg_data["text"],
                words=words,
                start_time=seg_data.get("start_time") or 0.0,
                end_time=seg_data.get("end_time") or 0.0,
            )
            segments.append(segment)
        
        metadata = LyricsMetadata(
            source=source,
            track_name="Unknown",
            artist_names="Unknown",
            is_synced=True,
        )
        
        references[source] = LyricsData(
            segments=segments,
            metadata=metadata,
            source=source,
        )
    
    return references


def get_transcribed_words(transcription_result: TranscriptionResult) -> List[str]:
    """Extract word texts from transcription result."""
    words = []
    for segment in transcription_result.result.segments:
        for word in segment.words:
            words.append(word.text)
    return words


def calculate_coverage(anchors: List[ScoredAnchor], word_count: int) -> float:
    """Calculate the percentage of words covered by anchors."""
    if word_count == 0:
        return 0.0
    
    covered_positions = set()
    for anchor in anchors:
        pos = anchor.anchor.transcription_position
        length = anchor.anchor.length
        for i in range(pos, pos + length):
            covered_positions.add(i)
    
    return len(covered_positions) / word_count * 100


# Collect all fixture files
FIXTURE_FILES = list(FIXTURES_DIR.glob("*.json")) if FIXTURES_DIR.exists() else []


# Cache for computed anchor results - avoid running expensive algorithm multiple times
_anchor_cache: Dict[str, Tuple[Dict[str, Any], List[ScoredAnchor]]] = {}


def get_anchors_for_fixture(fixture_path: Path, tmp_path: Path) -> Tuple[Dict[str, Any], List[ScoredAnchor]]:
    """
    Get anchors for a fixture, using cache to avoid re-running expensive algorithm.
    Returns (fixture_data, anchors).
    """
    cache_key = str(fixture_path)
    
    if cache_key in _anchor_cache:
        return _anchor_cache[cache_key]
    
    fixture = load_fixture(fixture_path)
    transcription_result = fixture_to_transcription_result(fixture)
    references = fixture_to_references(fixture)
    transcribed = get_transcribed_words(transcription_result)
    
    # Use tmp_path to avoid using cached results from user's actual cache
    finder = AnchorSequenceFinder(
        cache_dir=str(tmp_path),
        timeout_seconds=120,  # 2 minute timeout per fixture
    )
    
    anchors = finder.find_anchors(
        transcribed=transcribed,
        references=references,
        transcription_result=transcription_result,
    )
    
    _anchor_cache[cache_key] = (fixture, anchors)
    return fixture, anchors


class TestAnchorSequenceGolden:
    """
    Golden tests to verify AnchorSequenceFinder produces expected results.
    
    These tests use the EXPECTED values from fixtures (not re-running the algorithm)
    to verify fixture validity. The algorithm correctness tests are separate.
    """
    
    @pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda f: f.stem)
    def test_fixture_has_reasonable_coverage(self, fixture_path):
        """Fixture should have reasonable coverage (at least 30%)."""
        fixture = load_fixture(fixture_path)
        expected_coverage = fixture["expected_coverage_percent"]
        
        # All fixtures should have at least some coverage
        assert expected_coverage >= 30.0, (
            f"Fixture {fixture_path.name} has low coverage: {expected_coverage:.1f}%"
        )
    
    @pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda f: f.stem)
    def test_expected_anchors_are_valid(self, fixture_path):
        """Expected anchors in fixture should have valid positions."""
        fixture = load_fixture(fixture_path)
        word_count = fixture["transcription"]["word_count"]
        expected_anchors = fixture["expected_anchors"]
        
        for i, anchor_data in enumerate(expected_anchors):
            # Handle both nested and flat anchor structures
            if "anchor" in anchor_data:
                pos = anchor_data["anchor"]["transcription_position"]
                length = anchor_data["anchor"].get("length", len(anchor_data["anchor"].get("transcribed_word_ids", [])))
            else:
                pos = anchor_data["transcription_position"]
                length = anchor_data.get("length", len(anchor_data.get("transcribed_word_ids", [])))
            
            end_pos = pos + length
            
            assert pos >= 0, f"Anchor {i} has negative position: {pos}"
            assert end_pos <= word_count, (
                f"Anchor {i} end position {end_pos} exceeds word count {word_count}"
            )
    
    @pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda f: f.stem)
    def test_expected_anchors_dont_overlap(self, fixture_path):
        """Expected anchors in fixture should not overlap."""
        fixture = load_fixture(fixture_path)
        expected_anchors = fixture["expected_anchors"]
        
        covered_positions = set()
        for i, anchor_data in enumerate(expected_anchors):
            # Handle both nested and flat anchor structures
            if "anchor" in anchor_data:
                pos = anchor_data["anchor"]["transcription_position"]
                length = anchor_data["anchor"].get("length", len(anchor_data["anchor"].get("transcribed_word_ids", [])))
            else:
                pos = anchor_data["transcription_position"]
                length = anchor_data.get("length", len(anchor_data.get("transcribed_word_ids", [])))
            
            for j in range(pos, pos + length):
                assert j not in covered_positions, (
                    f"Position {j} is covered by multiple anchors"
                )
                covered_positions.add(j)


class TestGoldenFixturesExist:
    """Verify that golden fixtures exist and are valid."""
    
    def test_fixtures_directory_exists(self):
        """The fixtures directory should exist."""
        assert FIXTURES_DIR.exists(), f"Fixtures directory not found: {FIXTURES_DIR}"
    
    def test_at_least_10_fixtures(self):
        """There should be at least 10 fixture files."""
        fixture_count = len(FIXTURE_FILES)
        assert fixture_count >= 10, f"Expected at least 10 fixtures, found {fixture_count}"
    
    @pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda f: f.stem)
    def test_fixture_has_required_fields(self, fixture_path):
        """Each fixture should have all required fields."""
        required_fields = [
            "name",
            "description",
            "transcription",
            "references",
            "expected_anchors",
            "expected_anchor_count",
            "expected_coverage_percent",
        ]
        
        fixture = load_fixture(fixture_path)
        for field in required_fields:
            assert field in fixture, (
                f"Fixture {fixture_path.name} missing required field: {field}"
            )


# Skip running the expensive algorithm tests by default - run with --run-slow
@pytest.mark.slow
class TestAnchorSequenceAlgorithm:
    """
    Tests that actually run the AnchorSequenceFinder algorithm.
    These are slow and should only be run when verifying algorithm changes.
    
    Run with: pytest -v -m slow --run-slow
    """
    
    @pytest.mark.parametrize("fixture_path", FIXTURE_FILES[:3], ids=lambda f: f.stem)  # Only first 3 for speed
    def test_algorithm_produces_similar_count(self, fixture_path, tmp_path):
        """Re-running algorithm should produce similar anchor count."""
        fixture, anchors = get_anchors_for_fixture(fixture_path, tmp_path)
        
        expected_count = fixture["expected_anchor_count"]
        actual_count = len(anchors)
        
        # Allow 30% tolerance for anchor count (algorithm may vary slightly)
        tolerance = max(expected_count * 0.3, 3)
        assert abs(actual_count - expected_count) <= tolerance, (
            f"Anchor count {actual_count} differs from expected {expected_count} "
            f"by more than {tolerance:.0f} (30% tolerance)"
        )
    
    @pytest.mark.parametrize("fixture_path", FIXTURE_FILES[:3], ids=lambda f: f.stem)
    def test_algorithm_produces_similar_coverage(self, fixture_path, tmp_path):
        """Re-running algorithm should produce similar coverage."""
        fixture, anchors = get_anchors_for_fixture(fixture_path, tmp_path)
        
        word_count = fixture["transcription"]["word_count"]
        expected_coverage = fixture["expected_coverage_percent"]
        actual_coverage = calculate_coverage(anchors, word_count)
        
        # Allow 15% tolerance for coverage
        tolerance = 15.0
        assert abs(actual_coverage - expected_coverage) <= tolerance, (
            f"Coverage {actual_coverage:.1f}% differs from expected {expected_coverage:.1f}% "
            f"by more than {tolerance:.1f}%"
        )


def pytest_configure(config):
    """Register the 'slow' marker."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (run with --run-slow)"
    )


def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --run-slow is specified."""
    if config.getoption("--run-slow", default=False):
        return
    
    skip_slow = pytest.mark.skip(reason="need --run-slow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Add --run-slow option to pytest."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests that execute the anchor finding algorithm"
    )
