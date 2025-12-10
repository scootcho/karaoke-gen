#!/bin/bash
# Quick deploy script with validation
set -e

echo "================================"
echo "Backend Deployment Script"
echo "================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/.."

echo ""
echo "Step 1: Validating backend code..."
echo "-----------------------------------"

# Check if venv is available and activated
if [ -d "backend/venv" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}💡 Virtual environment exists but not activated.${NC}"
    echo "   Activate it for full validation: source backend/venv/bin/activate"
    echo "   Falling back to quick check..."
    echo ""
fi

# If venv is activated, use full validation (catches import errors!)
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Running full validation (venv activated)..."
    if ! python3 backend/validate.py; then
        echo ""
        echo -e "${RED}❌ Validation failed! Fix errors before deploying.${NC}"
        exit 1
    fi
else
    # Otherwise use quick check
    echo "Running quick validation (activate venv for full validation)..."
    if ! ./backend/quick-check.sh; then
        echo ""
        echo -e "${RED}❌ Validation failed! Fix errors before deploying.${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✅ Validation passed!${NC}"
echo ""

# Ask for confirmation
read -p "Deploy to Cloud Run? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "Step 2: Building and deploying..."
echo "-----------------------------------"

# Submit build
gcloud builds submit --config=cloudbuild.yaml --timeout=20m

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo "Check status:"
echo "  gcloud run services describe karaoke-backend --region us-central1"
echo ""
echo "View logs:"
echo "  gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend\" --limit=50"
echo ""
echo "Test endpoint:"
echo "  export BACKEND_URL=\"https://karaoke-backend-ipzqd2k4yq-uc.a.run.app\""
echo "  export AUTH_TOKEN=\$(gcloud auth print-identity-token)"
echo "  curl -H \"Authorization: Bearer \$AUTH_TOKEN\" \$BACKEND_URL/api/health"

