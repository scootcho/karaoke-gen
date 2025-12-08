#!/usr/bin/env python
# Suppress SyntaxWarnings from third-party dependencies (pydub, syrics)
# that have invalid escape sequences in regex patterns (not yet fixed for Python 3.12+)
import warnings
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
warnings.filterwarnings("ignore", category=SyntaxWarning, module="syrics")

import argparse
import logging
from importlib import metadata
import tempfile
import os
import sys
import json
import asyncio
import time
import pyperclip
from karaoke_gen import KaraokePrep
from karaoke_gen.karaoke_finalise import KaraokeFinalise
from .cli_args import create_parser, process_style_overrides, is_url, is_file


async def async_main():
    logger = logging.getLogger(__name__)
    log_handler = logging.StreamHandler()
    log_formatter = logging.Formatter(fmt="%(asctime)s.%(msecs)03d - %(levelname)s - %(module)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)

    # Use shared CLI parser
    parser = create_parser(prog="karaoke-gen")
    args = parser.parse_args()

    # Process style overrides
    try:
        style_overrides = process_style_overrides(args.style_override, logger)
    except ValueError:
        sys.exit(1)

    # Handle test email template case first
    if args.test_email_template:
        log_level = getattr(logging, args.log_level.upper())
        logger.setLevel(log_level)
        logger.info("Testing email template functionality...")
        kfinalise = KaraokeFinalise(
            log_formatter=log_formatter,
            log_level=log_level,
            email_template_file=args.email_template_file,
        )
        kfinalise.test_email_template()
        return

    # Handle edit-lyrics mode
    if args.edit_lyrics:
        log_level = getattr(logging, args.log_level.upper())
        logger.setLevel(log_level)
        logger.info("Running in edit-lyrics mode...")
        
        # Get the current directory name to extract artist and title
        current_dir = os.path.basename(os.getcwd())
        logger.info(f"Current directory: {current_dir}")
        
        # Extract artist and title from directory name
        # Format could be either "Artist - Title" or "BRAND-XXXX - Artist - Title"
        if " - " not in current_dir:
            logger.error("Current directory name does not contain ' - ' separator. Cannot extract artist and title.")
            sys.exit(1)
            return  # Explicit return for testing
            
        parts = current_dir.split(" - ")
        if len(parts) == 2:
            artist, title = parts
        elif len(parts) >= 3:
            # Handle brand code format: "BRAND-XXXX - Artist - Title"
            artist = parts[1]
            title = " - ".join(parts[2:])
        else:
            logger.error(f"Could not parse artist and title from directory name: {current_dir}")
            sys.exit(1)
            return  # Explicit return for testing
            
        logger.info(f"Extracted artist: {artist}, title: {title}")
        
        # Initialize KaraokePrep
        kprep_coroutine = KaraokePrep(
            artist=artist,
            title=title,
            input_media=None,  # Will be set by backup_existing_outputs
            dry_run=args.dry_run,
            log_formatter=log_formatter,
            log_level=log_level,
            render_bounding_boxes=args.render_bounding_boxes,
            output_dir=".",  # We're already in the track directory
            create_track_subfolders=False,  # Don't create subfolders, we're already in one
            lossless_output_format=args.lossless_output_format,
            output_png=args.output_png,
            output_jpg=args.output_jpg,
            clean_instrumental_model=args.clean_instrumental_model,
            backing_vocals_models=args.backing_vocals_models,
            other_stems_models=args.other_stems_models,
            model_file_dir=args.model_file_dir,
            skip_separation=True,  # Skip separation as we already have the audio files
            lyrics_artist=args.lyrics_artist or artist,
            lyrics_title=args.lyrics_title or title,
            lyrics_file=args.lyrics_file,
            skip_lyrics=False,  # We want to process lyrics
            skip_transcription=False,  # We want to transcribe
            skip_transcription_review=args.skip_transcription_review,
            subtitle_offset_ms=args.subtitle_offset_ms,
            style_params_json=args.style_params_json,
            style_overrides=style_overrides,
            background_video=args.background_video,
            background_video_darkness=args.background_video_darkness,
            auto_download=getattr(args, 'auto_download', False),
        )
        # No await needed for constructor
        kprep = kprep_coroutine
        
        # Backup existing outputs and get the input audio file
        track_output_dir = os.getcwd()
        input_audio_wav = kprep.file_handler.backup_existing_outputs(track_output_dir, artist, title)
        kprep.input_media = input_audio_wav
        
        # Run KaraokePrep
        tracks = await kprep.process()
        
        # Load CDG styles if CDG generation is enabled
        cdg_styles = None
        if args.enable_cdg:
            if not args.style_params_json:
                logger.error("CDG styles JSON file path (--style_params_json) is required when --enable_cdg is used")
                sys.exit(1)
                return  # Explicit return for testing
            try:
                with open(args.style_params_json, "r") as f:
                    style_params = json.loads(f.read())
                    cdg_styles = style_params["cdg"]
            except FileNotFoundError:
                logger.error(f"CDG styles configuration file not found: {args.style_params_json}")
                sys.exit(1)
                return  # Explicit return for testing
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in CDG styles configuration file: {e}")
                sys.exit(1)
                return  # Explicit return for testing
            except KeyError:
                logger.error(f"'cdg' key not found in style parameters file: {args.style_params_json}")
                sys.exit(1)
                return # Explicit return for testing
        
        # Run KaraokeFinalise with keep_brand_code=True and replace_existing=True
        kfinalise = KaraokeFinalise(
            log_formatter=log_formatter,
            log_level=log_level,
            dry_run=args.dry_run,
            instrumental_format=args.instrumental_format,
            enable_cdg=args.enable_cdg,
            enable_txt=args.enable_txt,
            brand_prefix=args.brand_prefix,
            organised_dir=args.organised_dir,
            organised_dir_rclone_root=args.organised_dir_rclone_root,
            public_share_dir=args.public_share_dir,
            youtube_client_secrets_file=args.youtube_client_secrets_file,
            youtube_description_file=args.youtube_description_file,
            rclone_destination=args.rclone_destination,
            discord_webhook_url=args.discord_webhook_url,
            email_template_file=args.email_template_file,
            cdg_styles=cdg_styles,
            keep_brand_code=True,  # Always keep brand code in edit mode
            non_interactive=args.yes,
        )
        
        try:
            final_track = kfinalise.process(replace_existing=True)  # Replace existing YouTube video
            logger.info(f"Successfully completed editing lyrics for: {artist} - {title}")
            
            # Display summary of outputs
            logger.info(f"Karaoke lyrics edit complete! Output files:")
            logger.info(f"")
            logger.info(f"Track: {final_track['artist']} - {final_track['title']}")
            logger.info(f"")
            logger.info(f"Working Files:")
            logger.info(f" Video With Vocals: {final_track['video_with_vocals']}")
            logger.info(f" Video With Instrumental: {final_track['video_with_instrumental']}")
            logger.info(f"")
            logger.info(f"Final Videos:")
            logger.info(f" Lossless 4K MP4 (PCM): {final_track['final_video']}")
            logger.info(f" Lossless 4K MKV (FLAC): {final_track['final_video_mkv']}")
            logger.info(f" Lossy 4K MP4 (AAC): {final_track['final_video_lossy']}")
            logger.info(f" Lossy 720p MP4 (AAC): {final_track['final_video_720p']}")

            if "final_karaoke_cdg_zip" in final_track or "final_karaoke_txt_zip" in final_track:
                logger.info(f"")
                logger.info(f"Karaoke Files:")

            if "final_karaoke_cdg_zip" in final_track:
                logger.info(f" CDG+MP3 ZIP: {final_track['final_karaoke_cdg_zip']}")

            if "final_karaoke_txt_zip" in final_track:
                logger.info(f" TXT+MP3 ZIP: {final_track['final_karaoke_txt_zip']}")

            if final_track["brand_code"]:
                logger.info(f"")
                logger.info(f"Organization:")
                logger.info(f" Brand Code: {final_track['brand_code']}")
                logger.info(f" Directory: {final_track['new_brand_code_dir_path']}")

            if final_track["youtube_url"] or final_track["brand_code_dir_sharing_link"]:
                logger.info(f"")
                logger.info(f"Sharing:")

            if final_track["brand_code_dir_sharing_link"]:
                logger.info(f" Folder Link: {final_track['brand_code_dir_sharing_link']}")
                try:
                    time.sleep(1)  # Brief pause between clipboard operations
                    pyperclip.copy(final_track["brand_code_dir_sharing_link"])
                    logger.info(f" (Folder link copied to clipboard)")
                except Exception as e:
                    logger.warning(f" Failed to copy folder link to clipboard: {str(e)}")

            if final_track["youtube_url"]:
                logger.info(f" YouTube URL: {final_track['youtube_url']}")
                try:
                    pyperclip.copy(final_track["youtube_url"])
                    logger.info(f" (YouTube URL copied to clipboard)")
                except Exception as e:
                    logger.warning(f" Failed to copy YouTube URL to clipboard: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error during finalisation: {str(e)}")
            raise e
            
        return

    # Handle finalise-only mode
    if args.finalise_only:
        log_level = getattr(logging, args.log_level.upper())
        logger.setLevel(log_level)
        logger.info("Running in finalise-only mode...")
        
        # Load CDG styles if CDG generation is enabled
        cdg_styles = None
        if args.enable_cdg:
            if not args.style_params_json:
                logger.error("CDG styles JSON file path (--style_params_json) is required when --enable_cdg is used")
                sys.exit(1)
                return  # Explicit return for testing
            try:
                with open(args.style_params_json, "r") as f:
                    style_params = json.loads(f.read())
                    cdg_styles = style_params["cdg"]
            except FileNotFoundError:
                logger.error(f"CDG styles configuration file not found: {args.style_params_json}")
                sys.exit(1)
                return  # Explicit return for testing
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in CDG styles configuration file: {e}")
                sys.exit(1)
                return  # Explicit return for testing
            except KeyError:
                logger.error(f"'cdg' key not found in style parameters file: {args.style_params_json}")
                sys.exit(1)
                return # Explicit return for testing
        
        kfinalise = KaraokeFinalise(
            log_formatter=log_formatter,
            log_level=log_level,
            dry_run=args.dry_run,
            instrumental_format=args.instrumental_format,
            enable_cdg=args.enable_cdg,
            enable_txt=args.enable_txt,
            brand_prefix=args.brand_prefix,
            organised_dir=args.organised_dir,
            organised_dir_rclone_root=args.organised_dir_rclone_root,
            public_share_dir=args.public_share_dir,
            youtube_client_secrets_file=args.youtube_client_secrets_file,
            youtube_description_file=args.youtube_description_file,
            rclone_destination=args.rclone_destination,
            discord_webhook_url=args.discord_webhook_url,
            email_template_file=args.email_template_file,
            cdg_styles=cdg_styles,
            keep_brand_code=getattr(args, 'keep_brand_code', False),
            non_interactive=args.yes,
        )
        
        try:
            track = kfinalise.process()
            logger.info(f"Successfully completed finalisation for: {track['artist']} - {track['title']}")
            
            # Display summary of outputs
            logger.info(f"Karaoke finalisation complete! Output files:")
            logger.info(f"")
            logger.info(f"Track: {track['artist']} - {track['title']}")
            logger.info(f"")
            logger.info(f"Working Files:")
            logger.info(f" Video With Vocals: {track['video_with_vocals']}")
            logger.info(f" Video With Instrumental: {track['video_with_instrumental']}")
            logger.info(f"")
            logger.info(f"Final Videos:")
            logger.info(f" Lossless 4K MP4 (PCM): {track['final_video']}")
            logger.info(f" Lossless 4K MKV (FLAC): {track['final_video_mkv']}")
            logger.info(f" Lossy 4K MP4 (AAC): {track['final_video_lossy']}")
            logger.info(f" Lossy 720p MP4 (AAC): {track['final_video_720p']}")

            if "final_karaoke_cdg_zip" in track or "final_karaoke_txt_zip" in track:
                logger.info(f"")
                logger.info(f"Karaoke Files:")

            if "final_karaoke_cdg_zip" in track:
                logger.info(f" CDG+MP3 ZIP: {track['final_karaoke_cdg_zip']}")

            if "final_karaoke_txt_zip" in track:
                logger.info(f" TXT+MP3 ZIP: {track['final_karaoke_txt_zip']}")

            if track["brand_code"]:
                logger.info(f"")
                logger.info(f"Organization:")
                logger.info(f" Brand Code: {track['brand_code']}")
                logger.info(f" Directory: {track['new_brand_code_dir_path']}")

            if track["youtube_url"] or track["brand_code_dir_sharing_link"]:
                logger.info(f"")
                logger.info(f"Sharing:")

            if track["brand_code_dir_sharing_link"]:
                logger.info(f" Folder Link: {track['brand_code_dir_sharing_link']}")
                try:
                    time.sleep(1)  # Brief pause between clipboard operations
                    pyperclip.copy(track["brand_code_dir_sharing_link"])
                    logger.info(f" (Folder link copied to clipboard)")
                except Exception as e:
                    logger.warning(f" Failed to copy folder link to clipboard: {str(e)}")

            if track["youtube_url"]:
                logger.info(f" YouTube URL: {track['youtube_url']}")
                try:
                    pyperclip.copy(track["youtube_url"])
                    logger.info(f" (YouTube URL copied to clipboard)")
                except Exception as e:
                    logger.warning(f" Failed to copy YouTube URL to clipboard: {str(e)}")
        except Exception as e:
            logger.error(f"An error occurred during finalisation, see stack trace below: {str(e)}")
            raise e
        
        return

    # For prep or full workflow, parse input arguments
    input_media, artist, title, filename_pattern = None, None, None, None

    if not args.args:
        parser.print_help()
        sys.exit(1)
        return  # Explicit return for testing

    # Allow 3 forms of positional arguments:
    # 1. URL or Media File only (may be single track URL, playlist URL, or local file)
    # 2. Artist and Title only
    # 3. URL, Artist, and Title
    if args.args and (is_url(args.args[0]) or is_file(args.args[0])):
        input_media = args.args[0]
        if len(args.args) > 2:
            artist = args.args[1]
            title = args.args[2]
        elif len(args.args) > 1:
            artist = args.args[1]
        else:
            logger.warning("Input media provided without Artist and Title, both will be guessed from title")

    elif os.path.isdir(args.args[0]):
        if not args.filename_pattern:
            logger.error("Filename pattern is required when processing a folder.")
            sys.exit(1)
            return  # Explicit return for testing
        if len(args.args) <= 1:
            logger.error("Second parameter provided must be Artist name; Artist is required when processing a folder.")
            sys.exit(1)
            return  # Explicit return for testing

        input_media = args.args[0]
        artist = args.args[1]
        filename_pattern = args.filename_pattern

    elif len(args.args) > 1:
        artist = args.args[0]
        title = args.args[1]
        if getattr(args, 'auto_download', False):
            logger.info(f"No input media provided, flacfetch will automatically search and download: {artist} - {title}")
        else:
            logger.info(f"No input media provided, flacfetch will search for: {artist} - {title} (interactive selection)")

    else:
        parser.print_help()
        sys.exit(1)
        return  # Explicit return for testing

    log_level = getattr(logging, args.log_level.upper())
    logger.setLevel(log_level)

    # Set up environment variables for lyrics-only mode
    if args.lyrics_only:
        args.skip_separation = True
        os.environ["KARAOKE_GEN_SKIP_AUDIO_SEPARATION"] = "1"
        os.environ["KARAOKE_GEN_SKIP_TITLE_END_SCREENS"] = "1"
        logger.info("Lyrics-only mode enabled: skipping audio separation and title/end screen generation")

    # Step 1: Run KaraokePrep
    kprep_coroutine = KaraokePrep(
        input_media=input_media,
        artist=artist,
        title=title,
        filename_pattern=filename_pattern,
        dry_run=args.dry_run,
        log_formatter=log_formatter,
        log_level=log_level,
        render_bounding_boxes=args.render_bounding_boxes,
        output_dir=args.output_dir,
        create_track_subfolders=args.no_track_subfolders,
        lossless_output_format=args.lossless_output_format,
        output_png=args.output_png,
        output_jpg=args.output_jpg,
        clean_instrumental_model=args.clean_instrumental_model,
        backing_vocals_models=args.backing_vocals_models,
        other_stems_models=args.other_stems_models,
        model_file_dir=args.model_file_dir,
        existing_instrumental=args.existing_instrumental,
        skip_separation=args.skip_separation,
        lyrics_artist=args.lyrics_artist,
        lyrics_title=args.lyrics_title,
        lyrics_file=args.lyrics_file,
        skip_lyrics=args.skip_lyrics,
        skip_transcription=args.skip_transcription,
        skip_transcription_review=args.skip_transcription_review,
        subtitle_offset_ms=args.subtitle_offset_ms,
        style_params_json=args.style_params_json,
        style_overrides=style_overrides,
        background_video=args.background_video,
        background_video_darkness=args.background_video_darkness,
        auto_download=getattr(args, 'auto_download', False),
    )
    # No await needed for constructor
    kprep = kprep_coroutine

    # Create final tracks data structure
    tracks = await kprep.process()

    # If prep-only mode, we're done
    if args.prep_only:
        logger.info("Prep-only mode: skipping finalisation phase")
        return

    # Step 2: For each track, run KaraokeFinalise
    for track in tracks:
        logger.info(f"Starting finalisation phase for {track['artist']} - {track['title']}...")

        # Use the track directory that was actually created by KaraokePrep
        track_dir = track["track_output_dir"]
        if not os.path.exists(track_dir):
            logger.error(f"Track directory not found: {track_dir}")
            continue

        logger.info(f"Changing to directory: {track_dir}")
        os.chdir(track_dir)

        # Load CDG styles if CDG generation is enabled
        cdg_styles = None
        if args.enable_cdg:
            if not args.style_params_json:
                logger.error("CDG styles JSON file path (--style_params_json) is required when --enable_cdg is used")
                sys.exit(1)
                return  # Explicit return for testing
            try:
                with open(args.style_params_json, "r") as f:
                    style_params = json.loads(f.read())
                    cdg_styles = style_params["cdg"]
            except FileNotFoundError:
                logger.error(f"CDG styles configuration file not found: {args.style_params_json}")
                sys.exit(1)
                return  # Explicit return for testing
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in CDG styles configuration file: {e}")
                sys.exit(1)
                return  # Explicit return for testing
            except KeyError:
                logger.error(f"'cdg' key not found in style parameters file: {args.style_params_json}")
                sys.exit(1)
                return # Explicit return for testing

        kfinalise = KaraokeFinalise(
            log_formatter=log_formatter,
            log_level=log_level,
            dry_run=args.dry_run,
            instrumental_format=args.instrumental_format,
            enable_cdg=args.enable_cdg,
            enable_txt=args.enable_txt,
            brand_prefix=args.brand_prefix,
            organised_dir=args.organised_dir,
            organised_dir_rclone_root=args.organised_dir_rclone_root,
            public_share_dir=args.public_share_dir,
            youtube_client_secrets_file=args.youtube_client_secrets_file,
            youtube_description_file=args.youtube_description_file,
            rclone_destination=args.rclone_destination,
            discord_webhook_url=args.discord_webhook_url,
            email_template_file=args.email_template_file,
            cdg_styles=cdg_styles,
            keep_brand_code=getattr(args, 'keep_brand_code', False),
            non_interactive=args.yes,
        )

        try:
            final_track = kfinalise.process()
            logger.info(f"Successfully completed processing: {final_track['artist']} - {final_track['title']}")
            
            # Display summary of outputs
            logger.info(f"Karaoke generation complete! Output files:")
            logger.info(f"")
            logger.info(f"Track: {final_track['artist']} - {final_track['title']}")
            logger.info(f"")
            logger.info(f"Working Files:")
            logger.info(f" Video With Vocals: {final_track['video_with_vocals']}")
            logger.info(f" Video With Instrumental: {final_track['video_with_instrumental']}")
            logger.info(f"")
            logger.info(f"Final Videos:")
            logger.info(f" Lossless 4K MP4 (PCM): {final_track['final_video']}")
            logger.info(f" Lossless 4K MKV (FLAC): {final_track['final_video_mkv']}")
            logger.info(f" Lossy 4K MP4 (AAC): {final_track['final_video_lossy']}")
            logger.info(f" Lossy 720p MP4 (AAC): {final_track['final_video_720p']}")

            if "final_karaoke_cdg_zip" in final_track or "final_karaoke_txt_zip" in final_track:
                logger.info(f"")
                logger.info(f"Karaoke Files:")

            if "final_karaoke_cdg_zip" in final_track:
                logger.info(f" CDG+MP3 ZIP: {final_track['final_karaoke_cdg_zip']}")

            if "final_karaoke_txt_zip" in final_track:
                logger.info(f" TXT+MP3 ZIP: {final_track['final_karaoke_txt_zip']}")

            if final_track["brand_code"]:
                logger.info(f"")
                logger.info(f"Organization:")
                logger.info(f" Brand Code: {final_track['brand_code']}")
                logger.info(f" Directory: {final_track['new_brand_code_dir_path']}")

            if final_track["youtube_url"] or final_track["brand_code_dir_sharing_link"]:
                logger.info(f"")
                logger.info(f"Sharing:")

            if final_track["brand_code_dir_sharing_link"]:
                logger.info(f" Folder Link: {final_track['brand_code_dir_sharing_link']}")
                try:
                    time.sleep(1)  # Brief pause between clipboard operations
                    pyperclip.copy(final_track["brand_code_dir_sharing_link"])
                    logger.info(f" (Folder link copied to clipboard)")
                except Exception as e:
                    logger.warning(f" Failed to copy folder link to clipboard: {str(e)}")

            if final_track["youtube_url"]:
                logger.info(f" YouTube URL: {final_track['youtube_url']}")
                try:
                    pyperclip.copy(final_track["youtube_url"])
                    logger.info(f" (YouTube URL copied to clipboard)")
                except Exception as e:
                    logger.warning(f" Failed to copy YouTube URL to clipboard: {str(e)}")
        except Exception as e:
            logger.error(f"An error occurred during finalisation, see stack trace below: {str(e)}")
            raise e
        
        return


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
