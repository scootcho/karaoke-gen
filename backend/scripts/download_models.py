#!/usr/bin/env python3
"""
Download ensemble preset models at Docker build time.

Bakes models into the image so they're available immediately at runtime,
avoiding cold-start model download latency in Cloud Run Jobs.

Usage: python backend/scripts/download_models.py /models
"""
import sys
import logging
from audio_separator.separator import Separator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Presets to bake into the GPU image
PRESETS_TO_DOWNLOAD = ["instrumental_clean", "karaoke"]


def download_preset_models(model_dir: str) -> None:
    """Download all models for the configured presets."""
    for preset in PRESETS_TO_DOWNLOAD:
        logger.info(f"Downloading models for preset: {preset}")
        sep = Separator(
            model_file_dir=model_dir,
            output_format="FLAC",
            ensemble_preset=preset,
        )
        # load_model triggers the download for each model in the preset
        sep.load_model()
        logger.info(f"Preset '{preset}' models downloaded to {model_dir}")


if __name__ == "__main__":
    model_dir = sys.argv[1] if len(sys.argv) > 1 else "/models"
    download_preset_models(model_dir)
    logger.info(f"All preset models downloaded to {model_dir}")
