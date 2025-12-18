#!/usr/bin/env python3
"""
Helper script to run the Instrumental Review UI from an existing karaoke job folder.

This allows iterating on the frontend without running a full karaoke generation.

Usage:
    python scripts/run_instrumental_review.py "path/to/Artist - Title"
    
    # Or with optional port:
    python scripts/run_instrumental_review.py "path/to/Artist - Title" --port 8888
"""

import argparse
import glob
import logging
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from karaoke_gen.instrumental_review import (
    AudioAnalyzer,
    InstrumentalReviewServer,
    WaveformGenerator,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def find_file(directory: str, patterns: list[str]) -> str | None:
    """Find a file matching any of the given patterns."""
    for pattern in patterns:
        matches = glob.glob(os.path.join(directory, pattern))
        if matches:
            return matches[0]
    return None


def find_audio_files(job_dir: str) -> dict:
    """
    Find the required audio files in a karaoke job directory.
    
    Returns dict with paths to:
    - backing_vocals: The backing vocals stem
    - clean_instrumental: The clean instrumental (no backing vocals)
    - with_backing: The instrumental with backing vocals (optional)
    """
    stems_dir = os.path.join(job_dir, "stems")
    
    if not os.path.exists(stems_dir):
        raise FileNotFoundError(f"stems/ directory not found in {job_dir}")
    
    # Find backing vocals - look for files with "Backing Vocals" in the name
    backing_vocals = find_file(stems_dir, [
        "*Backing Vocals*.flac",
        "*Backing Vocals*.mp3",
        "*Backing Vocals*.wav",
        "*backing_vocals*.flac",
        "*backing_vocals*.mp3",
    ])
    
    if not backing_vocals:
        raise FileNotFoundError(f"No backing vocals file found in {stems_dir}")
    
    # Find clean instrumental - look for "Instrumental" without "Backing"
    # Usually has model name like "(Instrumental mel_band_roformer...)"
    all_instrumentals = glob.glob(os.path.join(stems_dir, "*Instrumental*.flac"))
    all_instrumentals += glob.glob(os.path.join(stems_dir, "*Instrumental*.mp3"))
    
    # Filter out ones that have "Backing" in the name (those are combined)
    clean_instrumental = None
    with_backing = None
    
    for inst in all_instrumentals:
        basename = os.path.basename(inst)
        if "Backing" in basename or "backing" in basename:
            with_backing = inst
        else:
            clean_instrumental = inst
    
    if not clean_instrumental:
        raise FileNotFoundError(f"No clean instrumental file found in {stems_dir}")
    
    return {
        "backing_vocals": backing_vocals,
        "clean_instrumental": clean_instrumental,
        "with_backing": with_backing,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run the Instrumental Review UI from an existing karaoke job folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/run_instrumental_review.py "Sabrina Carpenter - Please, Please, Please"
    python scripts/run_instrumental_review.py "./output/Artist - Song" --port 9000
        """,
    )
    parser.add_argument(
        "job_dir",
        help="Path to the karaoke job directory (containing stems/ folder)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to run the server on (default: 8765)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't automatically open browser",
    )
    
    args = parser.parse_args()
    
    job_dir = os.path.abspath(args.job_dir)
    
    if not os.path.exists(job_dir):
        logger.error(f"Directory not found: {job_dir}")
        sys.exit(1)
    
    # Extract base name from directory name
    base_name = os.path.basename(job_dir)
    logger.info(f"Job directory: {job_dir}")
    logger.info(f"Base name: {base_name}")
    
    # Find audio files
    try:
        files = find_audio_files(job_dir)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    
    logger.info(f"Found backing vocals: {os.path.basename(files['backing_vocals'])}")
    logger.info(f"Found clean instrumental: {os.path.basename(files['clean_instrumental'])}")
    if files["with_backing"]:
        logger.info(f"Found with backing: {os.path.basename(files['with_backing'])}")
    else:
        logger.info("No combined instrumental found (optional)")
    
    # Analyze backing vocals
    logger.info("Analyzing backing vocals...")
    analyzer = AudioAnalyzer()
    analysis = analyzer.analyze(files["backing_vocals"])
    
    logger.info(f"  Has audible content: {analysis.has_audible_content}")
    logger.info(f"  Total duration: {analysis.total_duration_seconds:.1f}s")
    logger.info(f"  Audible segments: {len(analysis.audible_segments)}")
    logger.info(f"  Audible percentage: {analysis.audible_percentage:.1f}%")
    logger.info(f"  Recommendation: {analysis.recommended_selection.value}")
    
    # Generate or find waveform
    waveform_path = os.path.join(job_dir, f"{base_name} (Backing Vocals Waveform).png")
    
    if os.path.exists(waveform_path):
        logger.info(f"Using existing waveform: {os.path.basename(waveform_path)}")
    else:
        logger.info("Generating waveform visualization...")
        waveform_generator = WaveformGenerator()
        waveform_generator.generate(
            audio_path=files["backing_vocals"],
            output_path=waveform_path,
            segments=analysis.audible_segments,
        )
        logger.info(f"Generated waveform: {os.path.basename(waveform_path)}")
    
    # Create and start server
    logger.info(f"Starting instrumental review server on port {args.port}...")
    
    server = InstrumentalReviewServer(
        output_dir=job_dir,
        base_name=base_name,
        analysis=analysis,
        waveform_path=waveform_path,
        backing_vocals_path=files["backing_vocals"],
        clean_instrumental_path=files["clean_instrumental"],
        with_backing_path=files["with_backing"],
    )
    
    url = f"http://localhost:{args.port}/"
    logger.info(f"Server URL: {url}")
    
    if args.no_browser:
        logger.info("Browser auto-open disabled. Open the URL manually.")
        # Start server without opening browser
        import uvicorn
        app = server._create_app()
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    else:
        logger.info("Opening browser...")
        logger.info("Press Ctrl+C to stop the server")
        
        try:
            selection = server.start_and_open_browser(port=args.port)
            logger.info(f"Selection: {selection}")
            
            if selection == "custom":
                custom_path = server.get_custom_instrumental_path()
                if custom_path:
                    logger.info(f"Custom instrumental saved to: {custom_path}")
            
            if selection == "uploaded":
                uploaded_path = server.get_uploaded_instrumental_path()
                if uploaded_path:
                    logger.info(f"Uploaded instrumental saved to: {uploaded_path}")
                    
        except KeyboardInterrupt:
            logger.info("\nServer stopped")
            server.stop()


if __name__ == "__main__":
    main()

