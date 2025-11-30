# Use Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies required by karaoke-gen
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    libsox-dev \
    sox \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy karaoke_gen package first (from parent directory)
COPY karaoke_gen /app/karaoke_gen
COPY pyproject.toml /app/
COPY README.md /app/
COPY LICENSE /app/

# Copy backend code
COPY backend /app/backend

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}

