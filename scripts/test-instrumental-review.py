#!/usr/bin/env python
"""
Test script for the Instrumental Review UI.

Usage:
    python scripts/test-instrumental-review.py <backing_vocals_path> <clean_instrumental_path> [with_backing_path]

Example:
    python scripts/test-instrumental-review.py \
        "/path/to/Artist - Song (Backing Vocals).flac" \
        "/path/to/Artist - Song (Instrumental).flac"

This will:
1. Analyze the backing vocals file
2. Generate a waveform visualization
3. Start a local web server
4. Open your browser to the review UI
"""

import argparse
import logging
import os
import sys
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from karaoke_gen.instrumental_review import (
    AudioAnalyzer,
    WaveformGenerator,
    InstrumentalReviewServer,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Test the Instrumental Review UI locally"
    )
    parser.add_argument(
        "backing_vocals",
        help="Path to backing vocals audio file (e.g., 'Artist - Song (Backing Vocals).flac')"
    )
    parser.add_argument(
        "clean_instrumental",
        help="Path to clean instrumental audio file (e.g., 'Artist - Song (Instrumental).flac')"
    )
    parser.add_argument(
        "with_backing",
        nargs="?",
        default=None,
        help="Optional: Path to instrumental with backing vocals file"
    )
    parser.add_argument(
        "--original",
        default=None,
        help="Optional: Path to original audio file (with vocals) for comparison"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run the server on (default: 8765)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=-40.0,
        help="Silence threshold in dB (default: -40.0)"
    )
    
    args = parser.parse_args()
    
    # Validate files exist
    if not os.path.exists(args.backing_vocals):
        logger.error(f"Backing vocals file not found: {args.backing_vocals}")
        sys.exit(1)
    if not os.path.exists(args.clean_instrumental):
        logger.error(f"Clean instrumental file not found: {args.clean_instrumental}")
        sys.exit(1)
    if args.with_backing and not os.path.exists(args.with_backing):
        logger.error(f"With backing file not found: {args.with_backing}")
        sys.exit(1)
    if args.original and not os.path.exists(args.original):
        logger.error(f"Original audio file not found: {args.original}")
        sys.exit(1)
    
    # Extract base name from backing vocals file
    base_name = os.path.basename(args.backing_vocals)
    # Remove common suffixes
    for suffix in [" (Backing Vocals)", "(Backing Vocals)", "_backing_vocals", "-backing"]:
        if suffix in base_name:
            base_name = base_name.replace(suffix, "")
            break
    # Remove extension
    base_name = os.path.splitext(base_name)[0]
    
    output_dir = os.path.dirname(args.backing_vocals) or "."
    
    logger.info("=" * 60)
    logger.info("INSTRUMENTAL REVIEW UI TEST")
    logger.info("=" * 60)
    logger.info(f"Backing vocals: {args.backing_vocals}")
    logger.info(f"Clean instrumental: {args.clean_instrumental}")
    if args.with_backing:
        logger.info(f"With backing: {args.with_backing}")
    if args.original:
        logger.info(f"Original audio: {args.original}")
    logger.info(f"Base name: {base_name}")
    logger.info(f"Output dir: {output_dir}")
    logger.info("")
    
    # Step 1: Analyze backing vocals
    logger.info("[1/3] Analyzing backing vocals...")
    analyzer = AudioAnalyzer(silence_threshold_db=args.threshold)
    analysis = analyzer.analyze(args.backing_vocals)
    
    logger.info(f"  Has audible content: {analysis.has_audible_content}")
    logger.info(f"  Total duration: {analysis.total_duration_seconds:.1f}s")
    logger.info(f"  Audible segments: {len(analysis.audible_segments)}")
    logger.info(f"  Audible duration: {analysis.total_audible_duration_seconds:.1f}s ({analysis.audible_percentage:.1f}%)")
    logger.info(f"  Recommendation: {analysis.recommended_selection.value}")
    
    if analysis.audible_segments:
        logger.info("  Segments:")
        for i, seg in enumerate(analysis.audible_segments[:5]):
            logger.info(
                f"    [{i+1}] {seg.start_seconds:.1f}s - {seg.end_seconds:.1f}s "
                f"({seg.duration_seconds:.1f}s, avg: {seg.avg_amplitude_db:.1f}dB)"
            )
        if len(analysis.audible_segments) > 5:
            logger.info(f"    ... and {len(analysis.audible_segments) - 5} more")
    logger.info("")
    
    # Step 2: Generate waveform
    logger.info("[2/3] Generating waveform visualization...")
    waveform_path = os.path.join(output_dir, f"{base_name}_waveform.png")
    generator = WaveformGenerator()
    generator.generate(
        audio_path=args.backing_vocals,
        output_path=waveform_path,
        segments=analysis.audible_segments,
    )
    logger.info(f"  Waveform saved to: {waveform_path}")
    logger.info("")
    
    # Step 3: Start review server
    logger.info("[3/3] Starting review server...")
    logger.info(f"  URL: http://localhost:{args.port}/")
    logger.info("")
    logger.info("=" * 60)
    logger.info("REVIEW UI READY")
    logger.info("=" * 60)
    logger.info("")
    logger.info("The review UI should open in your browser.")
    logger.info("Select your instrumental choice and click 'Submit'.")
    logger.info("Press Ctrl+C to stop the server.")
    logger.info("")
    
    server = InstrumentalReviewServer(
        output_dir=output_dir,
        base_name=base_name,
        analysis=analysis,
        waveform_path=waveform_path,
        backing_vocals_path=args.backing_vocals,
        clean_instrumental_path=args.clean_instrumental,
        with_backing_path=args.with_backing,
        original_audio_path=args.original,
    )
    
    try:
        selection = server.start_and_open_browser(port=args.port)
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"SELECTION: {selection}")
        logger.info("=" * 60)
        
        custom_path = server.get_custom_instrumental_path()
        if custom_path:
            logger.info(f"Custom instrumental created: {custom_path}")
        
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user.")
        server.stop()


if __name__ == "__main__":
    main()
