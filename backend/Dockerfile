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

# ============================================
# OPTIMIZATION: Install dependencies BEFORE copying code
# This allows Docker to cache the dependency layer
# ============================================

# Copy ONLY dependency files first
COPY pyproject.toml /app/
COPY README.md /app/
COPY LICENSE /app/
COPY backend/requirements.txt /app/backend/requirements.txt

# Install Python dependencies (this layer will be cached unless requirements change)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Now copy the karaoke_gen package and install it
# This includes karaoke_gen dependencies
COPY karaoke_gen /app/karaoke_gen
RUN pip install --no-cache-dir -e .

# ============================================
# Copy application code LAST (changes frequently)
# ============================================

# Copy backend code (this invalidates cache only for code changes)
COPY backend /app/backend

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
