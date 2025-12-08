"""
Style configuration helper for workers.

Downloads and processes style assets from GCS, making them available
for screen generation, video rendering, and CDG generation.
"""
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from backend.services.storage_service import StorageService


logger = logging.getLogger(__name__)


# Default style configuration (used when no custom style is provided)
DEFAULT_INTRO_FORMAT = {
    "video_duration": 5,
    "existing_image": None,
    "background_color": "#000000",
    "background_image": None,
    "font": None,
    "artist_color": "#CCCCCC",
    "artist_text_transform": "none",
    "title_color": "#FFFFFF",
    "title_gradient": None,
    "title_text_transform": "none",
    "title_region": "200,700,3440,400",
    "artist_region": "200,1100,3440,300",
    "artist_gradient": None,
    "extra_text": None,
    "extra_text_color": "#FFFFFF",
    "extra_text_gradient": None,
    "extra_text_region": None,
    "extra_text_text_transform": "none",
}

DEFAULT_END_FORMAT = {
    "video_duration": 5,
    "existing_image": None,
    "background_color": "#000000",
    "background_image": None,
    "font": None,
    "artist_color": "#CCCCCC",
    "artist_text_transform": "none",
    "title_color": "#FFFFFF",
    "title_gradient": None,
    "title_text_transform": "none",
    "title_region": "200,900,3440,400",
    "artist_region": None,
    "artist_gradient": None,
    "extra_text": "Thank you for singing!",
    "extra_text_color": "#AAAAAA",
    "extra_text_region": "200,1300,3440,200",
    "extra_text_text_transform": "none",
    "extra_text_gradient": None,
}

DEFAULT_KARAOKE_FORMAT = {
    "background_image": None,
    "background_color": "#000000",
    "font_path": None,
    "font": None,
    "ass_name": "Default",
    "primary_color": "255, 255, 255, 255",
    "secondary_color": "255, 255, 0, 255",
    "outline_color": "0, 0, 0, 255",
    "back_color": "0, 0, 0, 128",
    "bold": False,
    "italic": False,
    "underline": False,
    "strike_out": False,
    "scale_x": 100,
    "scale_y": 100,
    "spacing": 0,
    "angle": 0.0,
    "border_style": 1,
    "outline": 2,
    "shadow": 1,
    "margin_l": 0,
    "margin_r": 0,
    "margin_v": 50,
    "encoding": 0,
}


class StyleConfig:
    """
    Manages style configuration for a job.
    
    Downloads style assets from GCS and provides processed style parameters
    with local file paths for use by video generators.
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
        self._loaded = False
    
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
        
        # Download style assets
        style_assets = getattr(self.job, 'style_assets', {}) or {}
        
        logger.info(f"Job has {len(style_assets)} style assets defined")
        for key, path in style_assets.items():
            logger.info(f"  Style asset '{key}': {path}")
        
        for asset_key, gcs_path in style_assets.items():
            if gcs_path:
                try:
                    local_path = await self._download_asset(asset_key, gcs_path)
                    if local_path:
                        self._local_assets[asset_key] = local_path
                        logger.info(f"Downloaded style asset '{asset_key}' to {local_path}")
                    else:
                        logger.warning(f"Failed to download style asset '{asset_key}' - got None")
                except Exception as e:
                    logger.warning(f"Failed to download style asset '{asset_key}': {e}")
        
        logger.info(f"Successfully downloaded {len(self._local_assets)} style assets")
        
        # Load and parse style_params.json
        if 'style_params' in self._local_assets:
            try:
                with open(self._local_assets['style_params'], 'r') as f:
                    self._style_params = json.load(f)
                logger.info(f"Loaded style params from {self._local_assets['style_params']}")
                logger.info(f"Style params sections: {list(self._style_params.keys()) if self._style_params else 'None'}")
                
                # Update file paths in style params to use local downloaded files
                self._update_style_paths()
            except Exception as e:
                logger.warning(f"Failed to parse style_params.json: {e}")
                self._style_params = None
        else:
            logger.warning("No style_params asset found in downloaded assets")
        
        self._loaded = True
    
    async def _download_asset(self, asset_key: str, gcs_path: str) -> Optional[str]:
        """Download a single asset from GCS."""
        try:
            # Determine local filename
            ext = Path(gcs_path).suffix
            local_path = os.path.join(self.style_dir, f"{asset_key}{ext}")
            
            # Download from GCS
            self.storage.download_file(gcs_path, local_path)
            
            if os.path.exists(local_path):
                return local_path
            return None
        except Exception as e:
            logger.error(f"Error downloading asset {asset_key}: {e}")
            return None
    
    def _update_style_paths(self) -> None:
        """
        Update file paths in style params to use downloaded local files.
        
        The uploaded style_params.json may have paths like "/tmp/font.ttf"
        which don't exist on the Cloud Run instance. We need to replace
        these with the actual downloaded file paths.
        """
        if not self._style_params:
            return
        
        # Map of style param keys to asset keys
        path_mappings = {
            ('intro', 'background_image'): 'intro_background',
            ('intro', 'font'): 'font',
            ('karaoke', 'background_image'): 'karaoke_background',
            ('karaoke', 'font_path'): 'font',
            ('end', 'background_image'): 'end_background',
            ('end', 'font'): 'font',
            ('cdg', 'font_path'): 'font',
            ('cdg', 'instrumental_background'): 'cdg_instrumental_background',
            ('cdg', 'title_screen_background'): 'cdg_title_background',
            ('cdg', 'outro_background'): 'cdg_outro_background',
        }
        
        for (section, key), asset_key in path_mappings.items():
            if section in self._style_params and key in self._style_params[section]:
                if asset_key in self._local_assets:
                    old_path = self._style_params[section][key]
                    self._style_params[section][key] = self._local_assets[asset_key]
                    logger.debug(f"Updated {section}.{key}: {old_path} -> {self._local_assets[asset_key]}")
    
    def get_intro_format(self) -> Dict[str, Any]:
        """Get title/intro screen format, with custom styles if available."""
        if self._style_params and 'intro' in self._style_params:
            # Merge custom params with defaults
            format_dict = DEFAULT_INTRO_FORMAT.copy()
            format_dict.update(self._style_params['intro'])
            return format_dict
        return DEFAULT_INTRO_FORMAT.copy()
    
    def get_end_format(self) -> Dict[str, Any]:
        """Get end screen format, with custom styles if available."""
        if self._style_params and 'end' in self._style_params:
            format_dict = DEFAULT_END_FORMAT.copy()
            format_dict.update(self._style_params['end'])
            return format_dict
        return DEFAULT_END_FORMAT.copy()
    
    def get_karaoke_format(self) -> Dict[str, Any]:
        """Get karaoke video format, with custom styles if available."""
        if self._style_params and 'karaoke' in self._style_params:
            format_dict = DEFAULT_KARAOKE_FORMAT.copy()
            format_dict.update(self._style_params['karaoke'])
            return format_dict
        return DEFAULT_KARAOKE_FORMAT.copy()
    
    def get_cdg_styles(self) -> Optional[Dict[str, Any]]:
        """Get CDG generation styles if available."""
        if self._style_params and 'cdg' in self._style_params:
            return self._style_params['cdg']
        return None
    
    def get_style_params_path(self) -> Optional[str]:
        """Get local path to style_params.json if available."""
        return self._local_assets.get('style_params')
    
    def get_local_asset_path(self, asset_key: str) -> Optional[str]:
        """Get local path for a specific asset."""
        return self._local_assets.get(asset_key)
    
    def has_custom_styles(self) -> bool:
        """Check if custom styles were provided."""
        return self._style_params is not None
    
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
