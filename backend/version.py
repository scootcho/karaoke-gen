"""
Version module for karaoke-gen backend.

Separated to avoid circular imports.
"""
import os


def get_version() -> str:
    """Get package version from environment variable, installed package, or fallback."""
    # First check environment variable (set during deployment)
    env_version = os.environ.get("KARAOKE_GEN_VERSION")
    if env_version:
        return env_version
    
    # Try to get from installed package metadata
    try:
        from importlib.metadata import version
        return version("karaoke-gen")
    except Exception:
        pass
    
    # Fallback if package not installed (e.g., during development)
    return "dev"


VERSION = get_version()
