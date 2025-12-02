#!/bin/bash
# Start GCP emulators for local testing
# This script starts Firestore and GCS emulators in the background

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
EMULATOR_LOG_DIR="$PROJECT_ROOT/.emulator-logs"

# Create log directory
mkdir -p "$EMULATOR_LOG_DIR"

echo "🚀 Starting GCP emulators for local testing..."
echo ""

# Check if emulators are already running
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Firestore emulator already running on port 8080"
else
    echo "📦 Starting Firestore emulator on port 8080..."
    gcloud beta emulators firestore start \
        --host-port=localhost:8080 \
        > "$EMULATOR_LOG_DIR/firestore.log" 2>&1 &
    
    FIRESTORE_PID=$!
    echo $FIRESTORE_PID > "$EMULATOR_LOG_DIR/firestore.pid"
    echo "   ✅ Firestore emulator started (PID: $FIRESTORE_PID)"
fi

if lsof -Pi :4443 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  GCS emulator already running on port 4443"
else
    echo "📦 Starting GCS emulator (fake-gcs-server) on port 4443..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Stop any existing container
    docker rm -f test-gcs-emulator >/dev/null 2>&1 || true
    
    # Start fake-gcs-server
    docker run -d \
        --name test-gcs-emulator \
        -p 4443:4443 \
        fsouza/fake-gcs-server:latest \
        -scheme http \
        -port 4443 \
        -external-url http://localhost:4443 \
        > "$EMULATOR_LOG_DIR/gcs.log" 2>&1
    
    GCS_CONTAINER=$(docker ps -q -f name=test-gcs-emulator)
    echo "   ✅ GCS emulator started (Container: $GCS_CONTAINER)"
fi

echo ""
echo "⏳ Waiting for emulators to be ready..."
sleep 5

# Test if emulators are responding
echo ""
if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "✅ Firestore emulator is ready"
else
    echo "⚠️  Firestore emulator may not be ready yet"
fi

if curl -s http://localhost:4443/storage/v1/b > /dev/null 2>&1; then
    echo "✅ GCS emulator is ready"
else
    echo "⚠️  GCS emulator may not be ready yet"
fi

echo ""
echo "🎉 Emulators started successfully!"
echo ""
echo "Environment variables to use:"
echo "  export FIRESTORE_EMULATOR_HOST=localhost:8080"
echo "  export STORAGE_EMULATOR_HOST=http://localhost:4443"
echo "  export GOOGLE_CLOUD_PROJECT=test-project"
echo ""
echo "To stop emulators, run: ./scripts/stop-emulators.sh"

