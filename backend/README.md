# Karaoke Generation Backend

## Overview

This is the backend service for the web-based karaoke generation system. It provides a REST API for job submission, status tracking, and result download.

## Architecture

- **FastAPI**: Modern Python web framework
- **Google Cloud Run**: Serverless container platform
- **Firestore**: NoSQL database for job state
- **Cloud Storage**: File storage for uploads and outputs
- **karaoke_gen**: Shared CLI modules for processing

## Local Development

### Prerequisites

- Python 3.11+
- Google Cloud SDK (for local testing with GCP services)
- FFmpeg and audio processing libraries

### Setup

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export GCS_BUCKET_NAME=karaoke-gen-storage
export AUDIO_SEPARATOR_API_URL=https://your-audio-separator-api
export AUDIOSHAKE_API_KEY=your-key
export GENIUS_API_KEY=your-key
```

3. Run locally:
```bash
uvicorn backend.main:app --reload --port 8080
```

4. Access API docs at: http://localhost:8080/docs

## API Endpoints

### Health Check
- `GET /api/health` - Health check
- `GET /api/readiness` - Readiness check for Cloud Run

### Jobs
- `POST /api/jobs` - Create job from URL
- `GET /api/jobs/{job_id}` - Get job status
- `GET /api/jobs` - List all jobs
- `DELETE /api/jobs/{job_id}` - Delete job

### Upload
- `POST /api/upload` - Upload audio file and create job

## Deployment to Cloud Run

### Build and deploy:

```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/karaoke-backend

# Deploy to Cloud Run
gcloud run deploy karaoke-backend \
  --image gcr.io/PROJECT_ID/karaoke-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=PROJECT_ID,GCS_BUCKET_NAME=karaoke-gen-storage
```

## Configuration

All configuration is managed through environment variables. See `config.py` for available options.

## Integration with karaoke_gen CLI

This backend reuses the existing `karaoke_gen` package for all processing logic. There is no code duplication - the same modules used by the CLI are used by the web backend.

Key integration points:
- `backend/services/processing_service.py` uses `KaraokePrep` from `karaoke_gen`
- Audio separation automatically uses remote API when `AUDIO_SEPARATOR_API_URL` is set
- All processing logic is identical to the CLI version

