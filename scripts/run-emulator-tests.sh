#!/bin/bash
# Run integration tests with GCP emulators
# This script starts emulators, runs tests, and stops emulators

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🧪 Running integration tests with GCP emulators"
echo "=============================================="
echo ""

# Start emulators
echo "Step 1/3: Starting emulators..."
"$SCRIPT_DIR/start-emulators.sh"
echo ""

# Ensure we stop emulators on exit
trap "$SCRIPT_DIR/stop-emulators.sh" EXIT

# Set environment variables for tests
export FIRESTORE_EMULATOR_HOST="localhost:8080"
export STORAGE_EMULATOR_HOST="http://localhost:4443"
export GOOGLE_CLOUD_PROJECT="test-project"
export GCS_BUCKET_NAME="test-bucket"
export FIRESTORE_COLLECTION="jobs"
export ENVIRONMENT="test"
export ADMIN_TOKENS="test-admin-token"

# Activate venv if available
if [ -d "$PROJECT_ROOT/backend/venv" ]; then
    echo "Step 2/3: Activating Python virtual environment..."
    source "$PROJECT_ROOT/backend/venv/bin/activate"
else
    echo "⚠️  Warning: backend/venv not found. Using system Python."
fi

echo ""
echo "Step 3/3: Running emulator integration tests..."
echo ""

cd "$PROJECT_ROOT"

# Run the emulator integration tests
if pytest backend/tests/emulator/ -v --tb=short --color=yes; then
    echo ""
    echo "✅ All emulator integration tests passed!"
    echo ""
    exit 0
else
    echo ""
    echo "❌ Some emulator integration tests failed"
    echo ""
    exit 1
fi

