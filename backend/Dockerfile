# Fast application image - uses pre-built base with all dependencies
#
# The base image (karaoke-backend-base) contains:
# - Python 3.11, ffmpeg, sox, system deps
# - All pip dependencies from requirements-frozen.txt (NO code)
#
# This Dockerfile adds the actual application code on top.
# Build time: ~1-2 minutes (deps already cached in base)
# 
# If the base image doesn't exist yet, build it first:
#   gcloud builds submit --config=cloudbuild-base.yaml --project=nomadkaraoke

# Use pre-built base image with all dependencies
FROM us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend-base:latest

# Set working directory (should already exist from base)
WORKDIR /app

# Copy backend code (this is the only thing that changes frequently)
COPY backend /app/backend

# Copy and reinstall karaoke_gen from local source
# This ensures new modules (like style_loader.py) are included without rebuilding base image
# Note: lyrics_transcriber is vendored in lyrics_transcriber_temp/ and bundled via pyproject.toml
COPY karaoke_gen /app/karaoke_gen
COPY lyrics_transcriber_temp /app/lyrics_transcriber_temp
COPY pyproject.toml README.md LICENSE /app/
RUN pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Create startup script that launches Transmission daemon before the main app
# Transmission is needed for flacfetch to download from music trackers (Redacted, OPS)
RUN echo '#!/bin/bash\n\
# Start Transmission daemon in background\n\
echo "Starting Transmission daemon..."\n\
transmission-daemon --foreground --config-dir /var/lib/transmission-daemon/.config/transmission-daemon &\n\
TRANSMISSION_PID=$!\n\
\n\
# Wait for Transmission to be ready (up to 10 seconds)\n\
for i in {1..20}; do\n\
    if curl -s http://127.0.0.1:9091/transmission/rpc > /dev/null 2>&1; then\n\
        echo "Transmission daemon ready"\n\
        break\n\
    fi\n\
    sleep 0.5\n\
done\n\
\n\
# Start the main application\n\
exec uvicorn backend.main:app --host 0.0.0.0 --port 8080\n\
' > /app/start.sh && chmod +x /app/start.sh

# Run the startup script
CMD ["/bin/bash", "/app/start.sh"]
