#!/bin/bash
# Debug a specific karaoke job
# Usage: ./scripts/debug-job.sh <job_id>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <job_id>"
    echo "Example: $0 e168cb20"
    exit 1
fi

JOB_ID="$1"
BACKEND_URL="${BACKEND_URL:-https://karaoke-backend-ipzqd2k4yq-uc.a.run.app}"
AUTH_TOKEN="${AUTH_TOKEN:-$(gcloud auth print-identity-token)}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "Debugging Job: $JOB_ID"
echo "========================================"
echo ""

# 1. Get job status
echo -e "${BLUE}1. Job Status:${NC}"
echo "---"
JOB_STATUS=$(curl -s -H "Authorization: Bearer $AUTH_TOKEN" "$BACKEND_URL/api/jobs/$JOB_ID")
echo "$JOB_STATUS" | jq '{status, progress, error_message, error_details, timeline: .timeline | length}'
echo ""

# 2. Get full timeline
echo -e "${BLUE}2. Timeline (last 10 events):${NC}"
echo "---"
echo "$JOB_STATUS" | jq -r '.timeline[-10:][] | "\(.timestamp) [\(.status)] \(.message)"'
echo ""

# 3. Check if files exist in GCS
echo -e "${BLUE}3. GCS Files:${NC}"
echo "---"
INPUT_PATH=$(echo "$JOB_STATUS" | jq -r '.input_media_gcs_path // empty')
if [ -n "$INPUT_PATH" ]; then
    echo "Input file: gs://karaoke-gen-storage-nomadkaraoke/$INPUT_PATH"
    if gsutil ls "gs://karaoke-gen-storage-nomadkaraoke/$INPUT_PATH" 2>/dev/null; then
        echo -e "${GREEN}✓ Input file exists${NC}"
        gsutil du -h "gs://karaoke-gen-storage-nomadkaraoke/$INPUT_PATH"
    else
        echo -e "${RED}✗ Input file NOT found${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No input_media_gcs_path in job${NC}"
fi
echo ""

# 4. Check Cloud Run logs
echo -e "${BLUE}4. Cloud Run Logs (last 20 relevant):${NC}"
echo "---"
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND textPayload=~\"$JOB_ID\"" \
    --limit=20 \
    --format="value(timestamp,severity,textPayload)" 2>/dev/null | \
    while IFS=$'\t' read -r timestamp severity message; do
        case "$severity" in
            ERROR)
                echo -e "${RED}[$timestamp] $severity: $message${NC}"
                ;;
            WARNING)
                echo -e "${YELLOW}[$timestamp] $severity: $message${NC}"
                ;;
            *)
                echo "[$timestamp] $severity: $message"
                ;;
        esac
    done
echo ""

# 5. Check Firestore document
echo -e "${BLUE}5. Firestore Document Fields:${NC}"
echo "---"
echo "$JOB_STATUS" | jq 'keys | sort'
echo ""

# 6. Summary
echo "========================================"
echo -e "${BLUE}Summary:${NC}"
STATUS=$(echo "$JOB_STATUS" | jq -r '.status')
ERROR=$(echo "$JOB_STATUS" | jq -r '.error_message // "None"')

case "$STATUS" in
    "completed")
        echo -e "${GREEN}✓ Job completed successfully${NC}"
        ;;
    "failed")
        echo -e "${RED}✗ Job failed: $ERROR${NC}"
        ;;
    "pending"|"processing"*)
        echo -e "${YELLOW}⏳ Job in progress: $STATUS${NC}"
        ;;
    *)
        echo -e "Status: $STATUS"
        ;;
esac
echo "========================================"

