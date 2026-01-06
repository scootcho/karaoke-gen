#!/bin/bash
set -e

# Log to a file for debugging
exec > >(tee /var/log/flacfetch-startup.log) 2>&1
echo "Starting flacfetch setup at $(date)"

# Install dependencies
apt-get update
apt-get install -y python3-pip python3-venv transmission-daemon ffmpeg git curl

# Configure Transmission
echo "Configuring Transmission daemon..."
systemctl stop transmission-daemon || true

# Create transmission directories
mkdir -p /var/lib/transmission-daemon/downloads
mkdir -p /var/lib/transmission-daemon/.config/transmission-daemon
chown -R debian-transmission:debian-transmission /var/lib/transmission-daemon

# Configure transmission settings
cat > /var/lib/transmission-daemon/.config/transmission-daemon/settings.json << 'SETTINGS'
{
    "download-dir": "/var/lib/transmission-daemon/downloads",
    "incomplete-dir": "/var/lib/transmission-daemon/.incomplete",
    "incomplete-dir-enabled": true,
    "rpc-authentication-required": false,
    "rpc-bind-address": "127.0.0.1",
    "rpc-enabled": true,
    "rpc-port": 9091,
    "rpc-whitelist-enabled": false,
    "peer-port": 51413,
    "port-forwarding-enabled": false,
    "speed-limit-down": 0,
    "speed-limit-down-enabled": false,
    "speed-limit-up": 0,
    "speed-limit-up-enabled": false,
    "ratio-limit-enabled": false,
    "umask": 2,
    "encryption": 1
}
SETTINGS

chown debian-transmission:debian-transmission /var/lib/transmission-daemon/.config/transmission-daemon/settings.json
systemctl start transmission-daemon
echo "Transmission daemon started"

# Install flacfetch
echo "Installing flacfetch..."
cd /opt

# Clone flacfetch (we'll use the repo from GitHub)
if [ ! -d "flacfetch" ]; then
    git clone https://github.com/nomadkaraoke/flacfetch.git
fi
cd flacfetch

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install flacfetch with API dependencies
pip install -e ".[api]"

# Get secrets from Secret Manager
echo "Fetching secrets from Secret Manager..."
FLACFETCH_API_KEY=$(gcloud secrets versions access latest --secret=flacfetch-api-key 2>/dev/null || echo "")
RED_API_KEY=$(gcloud secrets versions access latest --secret=red-api-key 2>/dev/null || echo "")
RED_API_URL=$(gcloud secrets versions access latest --secret=red-api-url 2>/dev/null || echo "")
OPS_API_KEY=$(gcloud secrets versions access latest --secret=ops-api-key 2>/dev/null || echo "")
OPS_API_URL=$(gcloud secrets versions access latest --secret=ops-api-url 2>/dev/null || echo "")

# Get bucket name from project metadata
GCS_BUCKET=$(gcloud compute project-info describe --format='value(commonInstanceMetadata.items.gcs-bucket)' 2>/dev/null || echo "")
if [ -z "$GCS_BUCKET" ]; then
    # Fallback: construct from project ID
    PROJECT_ID=$(curl -s "http://metadata.google.internal/computeMetadata/v1/project/project-id" -H "Metadata-Flavor: Google")
    GCS_BUCKET="karaoke-gen-storage-${PROJECT_ID}"
fi

echo "Using GCS bucket: $GCS_BUCKET"

# Create systemd service for flacfetch
echo "Creating systemd service..."
cat > /etc/systemd/system/flacfetch.service << SYSTEMD
[Unit]
Description=Flacfetch HTTP API Service
After=network.target transmission-daemon.service
Requires=transmission-daemon.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/flacfetch
Environment="FLACFETCH_API_KEY=${FLACFETCH_API_KEY}"
Environment="RED_API_KEY=${RED_API_KEY}"
Environment="RED_API_URL=${RED_API_URL}"
Environment="OPS_API_KEY=${OPS_API_KEY}"
Environment="OPS_API_URL=${OPS_API_URL}"
Environment="GCS_BUCKET=${GCS_BUCKET}"
Environment="FLACFETCH_KEEP_SEEDING=true"
Environment="FLACFETCH_MIN_FREE_GB=5"
Environment="FLACFETCH_DOWNLOAD_DIR=/var/lib/transmission-daemon/downloads"
Environment="TRANSMISSION_HOST=localhost"
Environment="TRANSMISSION_PORT=9091"
ExecStart=/opt/flacfetch/venv/bin/flacfetch serve --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable flacfetch
systemctl start flacfetch

echo "Flacfetch service started at $(date)"
echo "Setup complete!"
