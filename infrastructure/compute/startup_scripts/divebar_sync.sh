#!/bin/bash
# Divebar File Sync VM startup script
#
# Downloads karaoke files from Google Drive to GCS using the BigQuery index.
# Auto-shuts down after sync completes. Designed to be started daily by
# Cloud Scheduler or manually for initial bulk sync.
#
# Logs: journalctl -u divebar-sync -f
#       OR: /var/log/divebar-sync.log

set -euo pipefail

LOG_FILE="/var/log/divebar-sync.log"
REPO_DIR="/opt/nomad/divebar-sync"
SCRIPT="infrastructure/scripts/divebar_file_sync.py"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"
}

log "=== Divebar file sync starting ==="

# Install dependencies (idempotent)
if ! command -v pip3 &>/dev/null; then
    log "Installing Python3 and pip..."
    apt-get update -qq && apt-get install -y -qq python3-pip python3-venv git
fi

# Clone or update the repo
if [ -d "$REPO_DIR" ]; then
    log "Updating repo..."
    cd "$REPO_DIR" && git pull origin main --quiet
else
    log "Cloning repo..."
    git clone --depth 1 https://github.com/nomadkaraoke/karaoke-gen.git "$REPO_DIR"
fi

cd "$REPO_DIR"

# Set up venv (idempotent)
if [ ! -d "venv" ]; then
    log "Creating venv..."
    python3 -m venv venv
fi

source venv/bin/activate

log "Installing Python dependencies..."
pip install -q google-api-python-client google-cloud-storage google-cloud-bigquery google-auth

# Run the sync
log "Starting file sync (workers=4)..."
python3 "$SCRIPT" --workers 4 2>&1 | tee -a "$LOG_FILE"

# The script handles shutdown itself after completion
log "=== Divebar file sync script exited ==="
