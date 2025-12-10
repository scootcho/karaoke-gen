"""
Style configuration helper for workers.

Downloads and processes style assets from GCS, making them available
for screen generation, video rendering, and CDG generation.

This module uses the unified style_loader from karaoke_gen for
consistent style handling across local CLI and cloud backend.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from backend.services.storage_service import StorageService

# Import from the unified style loader module
from karaoke_gen.style_loader import (
    # Defaults
    DEFAULT_INTRO_STYLE,
    DEFAULT_END_STYLE,
    DEFAULT_KARAOKE_STYLE,
    DEFAULT_CDG_STYLE,
    # Functions
    load_styles_from_gcs,
    update_asset_paths,
    save_style_params,
    get_intro_format,
    get_end_format,
    get_karaoke_format,
    get_cdg_format,
)


logger = logging.getLogger(__name__)


# Re-export defaults for backwards compatibility with existing code
DEFAULT_INTRO_FORMAT = DEFAULT_INTRO_STYLE
DEFAULT_END_FORMAT = DEFAULT_END_STYLE
DEFAULT_KARAOKE_FORMAT = DEFAULT_KARAOKE_STYLE


class StyleConfig:
    """
    Manages style configuration for a job.
    
    Downloads style assets from GCS and provides processed style parameters
    with local file paths for use by video generators.
    
    This class wraps the unified style_loader module to provide an
    object-oriented interface for backend workers.
    """
    
    def __init__(self, job, storage: StorageService, temp_dir: str):
        """
        Initialize style configuration.
        
        Args:
            job: Job object with style_assets and style_params_gcs_path
            storage: Storage service for downloading files
            temp_dir: Temporary directory for downloaded assets
        """
        self.job = job
        self.storage = storage
        self.temp_dir = temp_dir
        self.style_dir = os.path.join(temp_dir, "style")
        os.makedirs(self.style_dir, exist_ok=True)
        
        self._style_params: Optional[Dict[str, Any]] = None
        self._local_assets: Dict[str, str] = {}
        self._styles_path: Optional[str] = None
        self._loaded = False
        self._has_custom_styles = False  # Track if custom styles were loaded
    
    async def load(self) -> None:
        """
        Download and parse style configuration from GCS.
        
        Downloads:
        - style_params.json (if exists)
        - All style assets (backgrounds, fonts)
        
        After loading, style params will have local file paths.
        """
        if self._loaded:
            return
        
        logger.info(f"Loading style configuration for job {self.job.job_id}")
        
        # Get style assets from job
        style_assets = getattr(self.job, 'style_assets', {}) or {}
        style_params_gcs_path = getattr(self.job, 'style_params_gcs_path', None)
        
        logger.info(f"Job has {len(style_assets)} style assets defined")
        for key, path in style_assets.items():
            logger.info(f"  Style asset '{key}': {path}")
        
        # Check if we have custom styles before loading
        self._has_custom_styles = bool(style_params_gcs_path)
        
        # Use the unified style loader
        self._styles_path, self._style_params = load_styles_from_gcs(
            style_params_gcs_path=style_params_gcs_path,
            style_assets=style_assets,
            temp_dir=self.temp_dir,
            download_func=self.storage.download_file,
            logger=logger,
        )
        
        # Track local assets for get_local_asset_path()
        if style_assets:
            for asset_key in style_assets.keys():
                if asset_key == 'style_params':
                    self._local_assets['style_params'] = self._styles_path
                else:
                    ext = os.path.splitext(style_assets[asset_key])[1] or '.png'
                    local_path = os.path.join(self.style_dir, f"{asset_key}{ext}")
                    if os.path.exists(local_path):
                        self._local_assets[asset_key] = local_path
        
        self._loaded = True
        logger.info(f"Successfully loaded style configuration")
    
    def get_intro_format(self) -> Dict[str, Any]:
        """Get title/intro screen format, with custom styles if available."""
        if self._style_params:
            return get_intro_format(self._style_params)
        return DEFAULT_INTRO_STYLE.copy()
    
    def get_end_format(self) -> Dict[str, Any]:
        """Get end screen format, with custom styles if available."""
        if self._style_params:
            return get_end_format(self._style_params)
        return DEFAULT_END_STYLE.copy()
    
    def get_karaoke_format(self) -> Dict[str, Any]:
        """Get karaoke video format, with custom styles if available."""
        if self._style_params:
            return get_karaoke_format(self._style_params)
        return DEFAULT_KARAOKE_STYLE.copy()
    
    def get_cdg_styles(self) -> Optional[Dict[str, Any]]:
        """Get CDG generation styles if available, falling back to defaults."""
        if self._style_params:
            cdg_styles = get_cdg_format(self._style_params)
            if cdg_styles:
                return cdg_styles
        # Return default CDG styles if no custom styles
        return DEFAULT_CDG_STYLE.copy()
    
    def get_style_params_path(self) -> Optional[str]:
        """
        Get local path to style_params.json with updated asset paths.
        
        Returns the styles JSON file path, or None if not loaded.
        """
        return self._styles_path
    
    def get_local_asset_path(self, asset_key: str) -> Optional[str]:
        """Get local path for a specific asset."""
        return self._local_assets.get(asset_key)
    
    def has_custom_styles(self) -> bool:
        """Check if custom styles were provided (not using defaults)."""
        return self._has_custom_styles
    
    @property
    def intro_video_duration(self) -> int:
        """Get intro video duration in seconds."""
        if self._style_params and 'intro' in self._style_params:
            return self._style_params['intro'].get('video_duration', 5)
        return 5
    
    @property
    def end_video_duration(self) -> int:
        """Get end video duration in seconds."""
        if self._style_params and 'end' in self._style_params:
            return self._style_params['end'].get('video_duration', 5)
        return 5


async def load_style_config(job, storage: StorageService, temp_dir: str) -> StyleConfig:
    """
    Helper function to load style configuration for a job.
    
    Args:
        job: Job object
        storage: Storage service
        temp_dir: Temporary directory
        
    Returns:
        Loaded StyleConfig instance
    """
    config = StyleConfig(job, storage, temp_dir)
    await config.load()
    return config
