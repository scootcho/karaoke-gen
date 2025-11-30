"""
Configuration management for the karaoke generation backend.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Google Cloud
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    gcs_bucket_name: str = os.getenv("GCS_BUCKET_NAME", "karaoke-gen-storage")
    firestore_collection: str = os.getenv("FIRESTORE_COLLECTION", "jobs")
    
    # Audio Separator API (for GPU processing)
    audio_separator_api_url: Optional[str] = os.getenv("AUDIO_SEPARATOR_API_URL")
    
    # External APIs
    audioshake_api_key: Optional[str] = os.getenv("AUDIOSHAKE_API_KEY")
    genius_api_key: Optional[str] = os.getenv("GENIUS_API_KEY")
    
    # Application
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Processing
    max_concurrent_jobs: int = int(os.getenv("MAX_CONCURRENT_JOBS", "5"))
    job_timeout_seconds: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "600"))
    
    # Storage paths
    temp_dir: str = os.getenv("TEMP_DIR", "/tmp/karaoke-gen")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

