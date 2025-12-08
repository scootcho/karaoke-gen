"""
FastAPI application entry point for karaoke generation backend.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes import health, jobs, internal, file_upload, review


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


# Package version
VERSION = get_version()


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("Starting karaoke generation backend")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"GCS Bucket: {settings.gcs_bucket_name}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down karaoke generation backend")


# Create FastAPI app
app = FastAPI(
    title="Karaoke Generator API",
    description="Backend API for web-based karaoke video generation",
    version=VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(file_upload.router, prefix="/api")  # File upload endpoint
app.include_router(internal.router, prefix="/api")  # Internal worker endpoints
app.include_router(review.router, prefix="/api")  # Review UI compatibility endpoints


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "karaoke-gen-backend",
        "version": VERSION,
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

