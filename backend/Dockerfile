# Fast application image - uses pre-built base with all dependencies
#
# The base image (karaoke-backend-base) contains:
# - Python 3.11, ffmpeg, sox, system deps
# - All pip dependencies from requirements.txt
# - The karaoke_gen package
#
# This Dockerfile only copies the backend code, making builds very fast (~30s).
# 
# If the base image doesn't exist yet, build it first:
#   gcloud builds submit --config=cloudbuild-base.yaml --project=nomadkaraoke

# Use pre-built base image with all dependencies
FROM us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend-base:latest

# Set working directory (should already exist from base)
WORKDIR /app

# Copy backend code (this is the only thing that changes frequently)
COPY backend /app/backend

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
