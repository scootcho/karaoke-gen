#!/bin/bash
# Run the backend locally for manual testing
# Usage: ./scripts/run-backend-local.sh [--with-emulators]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting local backend server..."

# Set environment variables for local development
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-nomadkaraoke}"
export GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-karaoke-gen-storage-nomadkaraoke}"
export FIRESTORE_COLLECTION="${FIRESTORE_COLLECTION:-jobs-dev}"
export ENVIRONMENT="development"
export ADMIN_TOKENS="${ADMIN_TOKENS:-local-dev-token}"
export PORT="${PORT:-8000}"

# If --with-emulators flag, start emulators first
if [[ "$1" == "--with-emulators" ]]; then
    echo "📦 Starting GCP emulators..."
    "$SCRIPT_DIR/start-emulators.sh"
    
    export FIRESTORE_EMULATOR_HOST="127.0.0.1:8080"
    export STORAGE_EMULATOR_HOST="http://127.0.0.1:4443"
    export GCS_BUCKET_NAME="test-bucket"
    export FIRESTORE_COLLECTION="test-jobs"
    
    # Create test bucket
    curl -s -X POST "http://127.0.0.1:4443/storage/v1/b" \
        -H "Content-Type: application/json" \
        -d '{"name":"test-bucket"}' \
        --data-urlencode "project=test-project" || true
    
    echo "✅ Emulators running"
fi

# Change to project root
cd "$PROJECT_ROOT"

# Run the backend with uvicorn
echo ""
echo "🌐 Backend starting at http://localhost:$PORT"
echo "📋 API docs at http://localhost:$PORT/docs"
echo ""
echo "Test endpoints:"
echo "  curl http://localhost:$PORT/api/health"
echo "  curl -X POST http://localhost:$PORT/api/jobs -H 'Content-Type: application/json' -d '{\"url\": \"https://youtube.com/watch?v=...\"}'"
echo ""
echo "Press Ctrl+C to stop"
echo ""

poetry run uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --reload

