#!/usr/bin/env python3
"""
Generate golden test fixtures for AnchorSequenceFinder using real cache data.

This script loads real transcription and reference data from the local cache,
runs the current AnchorSequenceFinder implementation, and saves the results
as fixtures for regression testing.

Usage:
    python scripts/generate_anchor_fixtures.py
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

# Add the parent directory to the path so we can import lyrics_transcriber
sys.path.insert(0, str(Path(__file__).parent.parent))

from lyrics_transcriber.types import (
    LyricsData, 
    LyricsSegment, 
    LyricsMetadata,
    TranscriptionData,
    TranscriptionResult,
    Word,
)
from lyrics_transcriber.correction.anchor_sequence import AnchorSequenceFinder


@dataclass
class SongMapping:
    """Maps an audioshake transcription to its reference lyrics."""
    name: str
    description: str
    audioshake_hash: str
    reference_hash: str


# 10 diverse songs with varying lengths and characteristics
SONG_MAPPINGS = [
    SongMapping(
        name="waterloo_abba",
        description="ABBA - Waterloo, short song snippet (30 words)",
        audioshake_hash="1654b7c0755fad7f23bc888308f274de",
        reference_hash="3365f6a1e42388d84bcbfc0ac6f8aa6c",
    ),
    SongMapping(
        name="let_your_hair_down",
        description="Let Your Hair Down, short song (86 words)",
        audioshake_hash="b19b4fca60015bbec16e4e0d68c2e777",
        reference_hash="a2e1d435193bf261db0246b535a87de9",
    ),
    SongMapping(
        name="daddy_fell_into_sun",
        description="Daddy Fell Into The Sun, short (97 words)",
        audioshake_hash="2f7e53617228901f67c2256e5648fbd6",
        reference_hash="b1aac2e85a3800fddae4a77c74b37280",
    ),
    SongMapping(
        name="pull_the_curtain",
        description="Pull the Curtain, medium-short (140 words)",
        audioshake_hash="87a40e919d0ba2066fa22c2b74cacc19",
        reference_hash="3448335d15fc3b842eef858e59681300",
    ),
    SongMapping(
        name="bright_eyes",
        description="Bright Eyes, medium (164 words)",
        audioshake_hash="6cfe3e59cb5c0a10d935396ff8b96752",
        reference_hash="748e5a24b339ab66e8bbb55e42e67770",
    ),
    SongMapping(
        name="texas_sun",
        description="Texas Sun, medium (183 words)",
        audioshake_hash="d0f851c8b3e7d56784c185f02416485b",
        reference_hash="2f0173340cb1169caf003cbfe535315b",
    ),
    SongMapping(
        name="shut_up_and_let_me_go",
        description="Ting Tings - Shut Up and Let Me Go, medium-long (231 words)",
        audioshake_hash="489c65695fca5bbe9cd11325af8e34ca",
        reference_hash="e96729ca29274f64ddc9ad461058949d",
    ),
    SongMapping(
        name="for_your_pleasure",
        description="For Your Pleasure, medium-long (251 words)",
        audioshake_hash="89fec5f0c8520e98bbeb17fe349e3182",
        reference_hash="7b2afa24bfb3f9611b45fb70698a8263",
    ),
    SongMapping(
        name="mayday_situation",
        description="Mayday Situation Overload, long (292 words)",
        audioshake_hash="0655f3ddeac47008cee8f484f4a1ed55",
        reference_hash="35d368e93554c99d18d666eafe37f16c",
    ),
    SongMapping(
        name="devil_went_down_to_georgia",
        description="The Devil Went Down to Georgia, long (391 words)",
        audioshake_hash="6f76f504e6a3c6dff7ee99191973579a",
        reference_hash="a98b3484d65c132218575f9cc118994d",
    ),
]


def get_cache_dir() -> Path:
    """Get the lyrics transcriber cache directory."""
    return Path(os.path.expanduser("~/lyrics-transcriber-cache"))


def load_audioshake_as_transcription(cache_dir: Path, audioshake_hash: str) -> Optional[TranscriptionResult]:
    """Load an audioshake converted file and convert it to TranscriptionResult."""
    file_path = cache_dir / f"audioshake_{audioshake_hash}_converted.json"
    if not file_path.exists():
        print(f"  WARNING: Audioshake file not found: {file_path}")
        return None
    
    with open(file_path) as f:
        data = json.load(f)
    
    # Convert the raw cache format to LyricsSegment objects
    segments = []
    all_words = []
    
    for seg_data in data.get("segments", []):
        words = []
        for w_data in seg_data.get("words", []):
            word = Word(
                id=w_data.get("id", f"w_{len(all_words)}"),
                text=w_data.get("text", ""),
                start_time=w_data.get("start_time") or 0.0,
                end_time=w_data.get("end_time") or 0.0,
                confidence=w_data.get("confidence"),
                created_during_correction=w_data.get("created_during_correction", False),
            )
            words.append(word)
            all_words.append(word)
        
        segment = LyricsSegment(
            id=seg_data.get("id", f"s_{len(segments)}"),
            text=seg_data.get("text", ""),
            words=words,
            start_time=seg_data.get("start_time") or 0.0,
            end_time=seg_data.get("end_time") or 0.0,
        )
        segments.append(segment)
    
    # Create TranscriptionData
    full_text = " ".join(seg.text for seg in segments)
    transcription_data = TranscriptionData(
        segments=segments,
        words=all_words,
        text=full_text,
        source="audioshake",
    )
    
    return TranscriptionResult(
        name="audioshake",
        priority=1,
        result=transcription_data,
    )


def load_reference_lyrics(cache_dir: Path, reference_hash: str) -> Dict[str, LyricsData]:
    """Load all available reference lyrics for a given hash."""
    references = {}
    providers = ["spotify", "genius", "lrclib", "musixmatch"]
    
    for provider in providers:
        file_path = cache_dir / f"{provider}_{reference_hash}_converted.json"
        if not file_path.exists():
            continue
        
        with open(file_path) as f:
            data = json.load(f)
        
        # Convert to LyricsSegment objects
        segments = []
        for seg_data in data.get("segments", []):
            words = []
            for w_data in seg_data.get("words", []):
                word = Word(
                    id=w_data.get("id", f"w_{len(words)}"),
                    text=w_data.get("text", ""),
                    start_time=w_data.get("start_time") or 0.0,
                    end_time=w_data.get("end_time") or 0.0,
                    confidence=w_data.get("confidence"),
                    created_during_correction=w_data.get("created_during_correction", False),
                )
                words.append(word)
            
            segment = LyricsSegment(
                id=seg_data.get("id", f"s_{len(segments)}"),
                text=seg_data.get("text", ""),
                words=words,
                start_time=seg_data.get("start_time") or 0.0,
                end_time=seg_data.get("end_time") or 0.0,
            )
            segments.append(segment)
        
        # Try to get metadata from raw file
        raw_path = cache_dir / f"{provider}_{reference_hash}_raw.json"
        track_name = "Unknown"
        artist_names = "Unknown"
        if raw_path.exists():
            try:
                with open(raw_path) as f:
                    raw_data = json.load(f)
                track_name = raw_data.get("trackName") or raw_data.get("name") or raw_data.get("track_data", {}).get("name", "Unknown")
                artist_names = raw_data.get("artistName") or raw_data.get("track_data", {}).get("artists", [{}])[0].get("name", "Unknown")
            except:
                pass
        
        metadata = LyricsMetadata(
            source=provider,
            track_name=track_name,
            artist_names=artist_names,
            is_synced=True,
        )
        
        lyrics_data = LyricsData(
            segments=segments,
            metadata=metadata,
            source=provider,
        )
        references[provider] = lyrics_data
    
    return references


def extract_words_from_segments(segments: List[LyricsSegment]) -> List[str]:
    """Extract all word texts from segments."""
    words = []
    for seg in segments:
        for word in seg.words:
            words.append(word.text)
    return words


def generate_fixture(mapping: SongMapping, cache_dir: Path, output_dir: Path) -> bool:
    """Generate a fixture for a single song mapping."""
    print(f"Generating fixture for: {mapping.name}")
    print(f"  Description: {mapping.description}")
    
    # Load transcription
    transcription_result = load_audioshake_as_transcription(cache_dir, mapping.audioshake_hash)
    if transcription_result is None:
        print(f"  SKIPPED: Could not load transcription")
        return False
    
    # Load references
    references = load_reference_lyrics(cache_dir, mapping.reference_hash)
    if not references:
        print(f"  SKIPPED: No reference lyrics found")
        return False
    
    print(f"  Loaded {len(references)} reference sources: {list(references.keys())}")
    
    # Get transcribed words and text
    transcribed_words = extract_words_from_segments(transcription_result.result.segments)
    transcribed_text = " ".join(transcribed_words)
    print(f"  Transcription word count: {len(transcribed_words)}")
    
    # Run AnchorSequenceFinder
    print(f"  Running AnchorSequenceFinder...")
    try:
        finder = AnchorSequenceFinder(
            cache_dir=str(cache_dir),
            timeout_seconds=300,  # 5 minute timeout for fixture generation
        )
        
        anchors = finder.find_anchors(
            transcribed=transcribed_text,
            references=references,
            transcription_result=transcription_result,
        )
        
        print(f"  Found {len(anchors)} anchors")
    except Exception as e:
        print(f"  ERROR running AnchorSequenceFinder: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Calculate coverage
    covered_positions = set()
    for anchor in anchors:
        pos = anchor.anchor.transcription_position
        length = anchor.anchor.length
        for i in range(pos, pos + length):
            covered_positions.add(i)
    
    coverage_percent = (len(covered_positions) / len(transcribed_words) * 100) if transcribed_words else 0
    
    # Build fixture
    fixture = {
        "name": mapping.name,
        "description": mapping.description,
        "source_hashes": {
            "audioshake": mapping.audioshake_hash,
            "references": mapping.reference_hash,
        },
        "transcription": {
            "segments": [seg.to_dict() for seg in transcription_result.result.segments],
            "word_count": len(transcribed_words),
            "text": transcription_result.result.text,
        },
        "references": {
            source: {
                "segments": [seg.to_dict() for seg in lyrics.segments],
                "word_count": sum(len(seg.words) for seg in lyrics.segments),
            }
            for source, lyrics in references.items()
        },
        "expected_anchors": [anchor.to_dict() for anchor in anchors],
        "expected_anchor_count": len(anchors),
        "expected_word_coverage": len(covered_positions),
        "expected_coverage_percent": round(coverage_percent, 2),
    }
    
    # Save fixture
    output_path = output_dir / f"{mapping.name}.json"
    with open(output_path, 'w') as f:
        json.dump(fixture, f, indent=2)
    
    print(f"  Saved fixture to: {output_path}")
    print(f"  Coverage: {coverage_percent:.1f}% ({len(covered_positions)}/{len(transcribed_words)} words)")
    
    return True


def main():
    """Generate all fixtures."""
    cache_dir = get_cache_dir()
    output_dir = Path(__file__).parent.parent / "tests" / "fixtures" / "anchor_golden"
    
    print(f"Cache directory: {cache_dir}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate fixtures
    success_count = 0
    for mapping in SONG_MAPPINGS:
        if generate_fixture(mapping, cache_dir, output_dir):
            success_count += 1
        print()
    
    print(f"Generated {success_count}/{len(SONG_MAPPINGS)} fixtures successfully")
    
    if success_count < len(SONG_MAPPINGS):
        print("\nWARNING: Some fixtures could not be generated. Check the errors above.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
