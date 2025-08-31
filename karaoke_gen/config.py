import os
import sys
import json
import logging

# Default style parameters if no JSON file is provided or if it's invalid
DEFAULT_STYLE_PARAMS = {
    "intro": {
        "video_duration": 5,
        "existing_image": None,
        "background_color": "#000000",
        "background_image": None,
        "font": "Montserrat-Bold.ttf",
        "artist_color": "#ffdf6b",
        "artist_gradient": None,
        "title_color": "#ffffff",
        "title_gradient": None,
        "title_region": "370, 200, 3100, 480",
        "artist_region": "370, 700, 3100, 480",
        "extra_text": None,
        "extra_text_color": "#ffffff",
        "extra_text_gradient": None,
        "extra_text_region": "370, 1200, 3100, 480",
        "title_text_transform": None,  # none, uppercase, lowercase, propercase
        "artist_text_transform": None,  # none, uppercase, lowercase, propercase
    },
    "end": {
        "video_duration": 5,
        "existing_image": None,
        "background_color": "#000000",
        "background_image": None,
        "font": "Montserrat-Bold.ttf",
        "artist_color": "#ffdf6b",
        "artist_gradient": None,
        "title_color": "#ffffff",
        "title_gradient": None,
        "title_region": None,
        "artist_region": None,
        "extra_text": "THANK YOU FOR SINGING!",
        "extra_text_color": "#ff7acc",
        "extra_text_gradient": None,
        "extra_text_region": None,
        "title_text_transform": None,  # none, uppercase, lowercase, propercase
        "artist_text_transform": None,  # none, uppercase, lowercase, propercase
    },
}


def apply_style_overrides(style_params, overrides, logger):
    """Recursively applies overrides to the style parameters."""
    for key, value in overrides.items():
        keys = key.split('.')
        current_level = style_params
        for i, k in enumerate(keys):
            if i == len(keys) - 1:
                if k in current_level:
                    # Attempt to cast the value to the type of the existing value
                    try:
                        original_type = type(current_level[k])
                        if original_type == bool:
                            # Handle boolean conversion
                            value = value.lower() in ('true', '1', 't', 'y', 'yes')
                        else:
                            value = original_type(value)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not cast override value '{value}' for key '{key}' to original type. Using as string. Error: {e}")
                    current_level[k] = value
                    logger.info(f"Overrode style: {key} = {value}")
                else:
                    logger.warning(f"Override key '{key}' not found in style parameters.")
            elif k in current_level and isinstance(current_level[k], dict):
                current_level = current_level[k]
            else:
                logger.warning(f"Override key part '{k}' not found or not a dictionary for key '{key}'.")
                break


def load_style_params(style_params_json, style_overrides, logger):
    """Loads style parameters from a JSON file or uses defaults."""
    style_params = {}
    if style_params_json:
        try:
            with open(style_params_json, "r") as f:
                style_params = json.loads(f.read())
                logger.info(f"Loaded style parameters from {style_params_json}")
        except FileNotFoundError:
            logger.error(f"Style parameters configuration file not found: {style_params_json}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in style parameters configuration file: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading style parameters file {style_params_json}: {e}")
            sys.exit(1)
    else:
        logger.info("No style parameters JSON file provided. Using default styles.")
        style_params = DEFAULT_STYLE_PARAMS

    if style_overrides:
        apply_style_overrides(style_params, style_overrides, logger)

    return style_params

def setup_title_format(style_params):
    """Sets up the title format dictionary from style parameters."""
    intro_params = style_params.get("intro", DEFAULT_STYLE_PARAMS["intro"])
    return {
        "background_color": intro_params.get("background_color", DEFAULT_STYLE_PARAMS["intro"]["background_color"]),
        "background_image": intro_params.get("background_image"),
        "font": intro_params.get("font", DEFAULT_STYLE_PARAMS["intro"]["font"]),
        "artist_color": intro_params.get("artist_color", DEFAULT_STYLE_PARAMS["intro"]["artist_color"]),
        "artist_gradient": intro_params.get("artist_gradient"),
        "title_color": intro_params.get("title_color", DEFAULT_STYLE_PARAMS["intro"]["title_color"]),
        "title_gradient": intro_params.get("title_gradient"),
        "extra_text": intro_params.get("extra_text"),
        "extra_text_color": intro_params.get("extra_text_color", DEFAULT_STYLE_PARAMS["intro"]["extra_text_color"]),
        "extra_text_gradient": intro_params.get("extra_text_gradient"),
        "extra_text_region": intro_params.get("extra_text_region", DEFAULT_STYLE_PARAMS["intro"]["extra_text_region"]),
        "title_region": intro_params.get("title_region", DEFAULT_STYLE_PARAMS["intro"]["title_region"]),
        "artist_region": intro_params.get("artist_region", DEFAULT_STYLE_PARAMS["intro"]["artist_region"]),
        "title_text_transform": intro_params.get("title_text_transform"),
        "artist_text_transform": intro_params.get("artist_text_transform"),
    }

def setup_end_format(style_params):
    """Sets up the end format dictionary from style parameters."""
    end_params = style_params.get("end", DEFAULT_STYLE_PARAMS["end"])
    return {
        "background_color": end_params.get("background_color", DEFAULT_STYLE_PARAMS["end"]["background_color"]),
        "background_image": end_params.get("background_image"),
        "font": end_params.get("font", DEFAULT_STYLE_PARAMS["end"]["font"]),
        "artist_color": end_params.get("artist_color", DEFAULT_STYLE_PARAMS["end"]["artist_color"]),
        "artist_gradient": end_params.get("artist_gradient"),
        "title_color": end_params.get("title_color", DEFAULT_STYLE_PARAMS["end"]["title_color"]),
        "title_gradient": end_params.get("title_gradient"),
        "extra_text": end_params.get("extra_text", DEFAULT_STYLE_PARAMS["end"]["extra_text"]),
        "extra_text_color": end_params.get("extra_text_color", DEFAULT_STYLE_PARAMS["end"]["extra_text_color"]),
        "extra_text_gradient": end_params.get("extra_text_gradient"),
        "extra_text_region": end_params.get("extra_text_region"),
        "title_region": end_params.get("title_region"),
        "artist_region": end_params.get("artist_region"),
        "title_text_transform": end_params.get("title_text_transform"),
        "artist_text_transform": end_params.get("artist_text_transform"),
    }

def get_video_durations(style_params):
    """Gets intro and end video durations from style parameters."""
    intro_duration = style_params.get("intro", {}).get("video_duration", DEFAULT_STYLE_PARAMS["intro"]["video_duration"])
    end_duration = style_params.get("end", {}).get("video_duration", DEFAULT_STYLE_PARAMS["end"]["video_duration"])
    return intro_duration, end_duration

def get_existing_images(style_params):
    """Gets existing title and end images from style parameters."""
    existing_title_image = style_params.get("intro", {}).get("existing_image")
    existing_end_image = style_params.get("end", {}).get("existing_image")
    return existing_title_image, existing_end_image

def setup_ffmpeg_command(log_level):
    """Sets up the base ffmpeg command string based on log level."""
    # Path to the Windows PyInstaller frozen bundled ffmpeg.exe, or the system-installed FFmpeg binary on Mac/Linux
    ffmpeg_path = os.path.join(sys._MEIPASS, "ffmpeg.exe") if getattr(sys, "frozen", False) else "ffmpeg"
    ffmpeg_base_command = f"{ffmpeg_path} -hide_banner -nostats"
    if log_level == logging.DEBUG:
        ffmpeg_base_command += " -loglevel verbose"
    else:
        ffmpeg_base_command += " -loglevel fatal"
    return ffmpeg_base_command
