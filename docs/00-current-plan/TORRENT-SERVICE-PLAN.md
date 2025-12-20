# Torrent Download Service Implementation Plan

**Created:** 2025-12-20  
**Status:** Draft  
**Priority:** Medium  
**Estimated Effort:** 2-3 days

## Problem Statement

BitTorrent downloads don't work reliably in Cloud Run due to:
- No inbound peer connections (NAT/firewall)
- Ephemeral containers with no stable IP
- DHT peer discovery blocked
- Container timeout limits (max 60 min)

This prevents downloading lossless audio from private trackers (Redacted, OPS) via the remote backend.

## Solution Overview

Deploy a dedicated lightweight VM running Transmission daemon that:
1. Receives download requests from Cloud Run backend
2. Downloads torrents with full peer connectivity
3. Uploads completed files to GCS
4. Cleans up after completion

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TORRENT SERVICE ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Cloud Run Backend                     Torrent VM (e2-micro)           │
│   ┌────────────────────┐                ┌────────────────────┐          │
│   │                    │                │                    │          │
│   │ Audio Search       │   1. Request   │  Transmission      │          │
│   │ Service            │ ─────────────▶ │  Daemon            │          │
│   │                    │   (torrent URL)│                    │          │
│   │                    │                │  • Full peer       │          │
│   │                    │   2. Status    │    connectivity    │          │
│   │                    │ ◀───────────── │  • DHT enabled     │          │
│   │                    │   (polling)    │  • Can seed        │          │
│   │                    │                │                    │          │
│   │                    │   3. Complete  │  FastAPI Service   │          │
│   │                    │ ◀───────────── │  • /download       │          │
│   │                    │   (GCS path)   │  • /status/{id}    │          │
│   │                    │                │  • /cancel/{id}    │          │
│   └────────────────────┘                └─────────┬──────────┘          │
│            │                                      │                      │
│            │                                      │ 4. Upload            │
│            │                                      │                      │
│            ▼                                      ▼                      │
│   ┌─────────────────────────────────────────────────────────────┐       │
│   │                    Google Cloud Storage                      │       │
│   │                                                              │       │
│   │   uploads/{job_id}/audio/{filename}.flac                    │       │
│   │                                                              │       │
│   └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Infrastructure Setup (Pulumi)

**Tasks:**
- [ ] Create Compute Engine VM resource in `infrastructure/__main__.py`
- [ ] Configure firewall rules for BitTorrent (port 51413 TCP/UDP)
- [ ] Set up service account with GCS write permissions
- [ ] Create startup script to install/configure Transmission
- [ ] Add VM IP to Secret Manager for backend access

**Pulumi Resources:**
```python
# infrastructure/__main__.py additions

# Torrent service VM
torrent_vm = gcp.compute.Instance(
    "torrent-service",
    machine_type="e2-micro",  # ~$5/month
    zone="us-central1-a",
    boot_disk=gcp.compute.InstanceBootDiskArgs(
        initialize_params=gcp.compute.InstanceBootDiskInitializeParamsArgs(
            image="debian-cloud/debian-12",
            size=20,  # GB - for temp torrent storage
        ),
    ),
    network_interfaces=[gcp.compute.InstanceNetworkInterfaceArgs(
        network="default",
        access_configs=[gcp.compute.InstanceNetworkInterfaceAccessConfigArgs()],  # Public IP
    )],
    service_account=gcp.compute.InstanceServiceAccountArgs(
        email=torrent_service_account.email,
        scopes=["cloud-platform"],
    ),
    metadata_startup_script=TORRENT_STARTUP_SCRIPT,
    tags=["torrent-service"],
)

# Firewall for BitTorrent
torrent_firewall = gcp.compute.Firewall(
    "torrent-firewall",
    network="default",
    allows=[
        gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["51413"]),
        gcp.compute.FirewallAllowArgs(protocol="udp", ports=["51413"]),
        gcp.compute.FirewallAllowArgs(protocol="tcp", ports=["8080"]),  # API
    ],
    source_ranges=["0.0.0.0/0"],
    target_tags=["torrent-service"],
)
```

**Estimated Cost:** ~$5-10/month

### Phase 2: Torrent Service Application

**Tasks:**
- [ ] Create `torrent-service/` directory with FastAPI application
- [ ] Implement `/download` endpoint (accepts torrent URL, returns job ID)
- [ ] Implement `/status/{id}` endpoint (returns progress, peers, speed)
- [ ] Implement `/cancel/{id}` endpoint
- [ ] Implement GCS upload on completion
- [ ] Add authentication (shared secret or service account)
- [ ] Create Dockerfile for the service
- [ ] Add systemd service file for auto-start

**API Design:**
```python
# POST /download
{
    "torrent_url": "https://redacted.sh/ajax.php?action=download&id=...",
    "target_file": "02. Song Name.flac",  # File to extract from torrent
    "gcs_destination": "uploads/job123/audio/",
    "callback_url": "https://api.nomadkaraoke.com/internal/torrent-complete"  # Optional
}

# Response
{
    "download_id": "abc123",
    "status": "queued"
}

# GET /status/{download_id}
{
    "download_id": "abc123",
    "status": "downloading",  # queued, downloading, uploading, complete, failed
    "progress": 45.2,
    "peers": 3,
    "download_speed": 1250.5,  # KB/s
    "eta_seconds": 120,
    "gcs_path": null  # Set when complete
}

# DELETE /cancel/{download_id}
{
    "status": "cancelled"
}
```

**Directory Structure:**
```
torrent-service/
├── Dockerfile
├── requirements.txt
├── main.py              # FastAPI app
├── transmission.py      # Transmission RPC wrapper
├── gcs_uploader.py      # GCS upload logic
├── config.py            # Settings
└── systemd/
    └── torrent-service.service
```

### Phase 3: Backend Integration

**Tasks:**
- [ ] Add `TorrentServiceClient` class in `backend/services/`
- [ ] Modify `audio_search.py` to use torrent service for Redacted/OPS downloads
- [ ] Add timeout handling (fall back to YouTube if service unavailable)
- [ ] Update health endpoint to include torrent service status
- [ ] Add environment variable for torrent service URL

**Integration Code:**
```python
# backend/services/torrent_service.py

class TorrentServiceClient:
    def __init__(self, service_url: str, api_key: str):
        self.service_url = service_url
        self.api_key = api_key
    
    async def download(
        self,
        torrent_url: str,
        target_file: str,
        gcs_destination: str,
        timeout: int = 600,  # 10 min default
    ) -> str:
        """
        Start download and wait for completion.
        
        Returns GCS path on success.
        Raises TorrentDownloadError on failure.
        """
        # 1. POST /download
        # 2. Poll /status until complete or timeout
        # 3. Return GCS path
        pass
    
    async def get_status(self, download_id: str) -> dict:
        """Get current download status."""
        pass
    
    async def cancel(self, download_id: str) -> None:
        """Cancel a download."""
        pass
```

**Modified Download Flow:**
```python
# backend/api/routes/audio_search.py

async def _download_and_start_processing(...):
    selected = results[selection_index]
    
    if selected['provider'] in ['Redacted', 'OPS']:
        # Use torrent service
        try:
            gcs_path = await torrent_client.download(
                torrent_url=selected['url'],
                target_file=selected['target_file'],
                gcs_destination=f"uploads/{job_id}/audio/",
                timeout=600,
            )
            # Continue with processing...
        except TorrentServiceError as e:
            # Fall back to YouTube or fail
            logger.warning(f"Torrent download failed: {e}")
            raise DownloadError(f"Torrent download failed: {e}")
    else:
        # YouTube - use existing flacfetch download
        ...
```

### Phase 4: Monitoring & Reliability

**Tasks:**
- [ ] Add Cloud Monitoring alerts for VM health
- [ ] Implement auto-restart on failure (watchdog)
- [ ] Add logging to Cloud Logging
- [ ] Implement disk space management (auto-cleanup)
- [ ] Add metrics endpoint for Prometheus/Grafana (optional)

**Health Checks:**
- Transmission daemon running
- Disk space > 5GB free
- API responsive
- GCS credentials valid

### Phase 5: Documentation Updates

**Tasks:**
- [ ] Update `docs/01-reference/ARCHITECTURE.md` with torrent service diagram
- [ ] Add deployment instructions to README or new doc
- [ ] Document environment variables
- [ ] Add troubleshooting guide
- [ ] Update API documentation

## Environment Variables

### Torrent Service VM
```bash
# Transmission config
TRANSMISSION_RPC_PORT=9091
TRANSMISSION_PEER_PORT=51413
TRANSMISSION_DOWNLOAD_DIR=/var/lib/transmission/downloads

# GCS
GOOGLE_CLOUD_PROJECT=nomadkaraoke
GCS_BUCKET=karaoke-uploads

# API
API_PORT=8080
API_KEY=<shared-secret>
```

### Cloud Run Backend
```bash
# New variables
TORRENT_SERVICE_URL=http://<vm-ip>:8080
TORRENT_SERVICE_API_KEY=<shared-secret>
TORRENT_DOWNLOAD_TIMEOUT=600
```

## Security Considerations

1. **API Authentication**: Use shared secret or Google IAM
2. **Firewall**: Only allow Cloud Run egress IPs to API port
3. **GCS**: Service account with minimal permissions (write to specific prefix)
4. **Transmission**: Disable web UI, RPC only on localhost

## Rollback Plan

If torrent service fails:
1. Set `TORRENT_SERVICE_ENABLED=false` in Cloud Run
2. Backend falls back to YouTube-only downloads
3. Users see warning that lossless downloads unavailable

## Testing Plan

1. **Unit Tests**: Mock torrent service client
2. **Integration Tests**: Test against local Docker Transmission
3. **E2E Tests**: Full flow with real torrent (test tracker)

## Success Criteria

- [ ] Torrent downloads complete successfully for Redacted/OPS sources
- [ ] Downloads complete within 10 minutes for typical album tracks
- [ ] Service recovers automatically from failures
- [ ] Fallback to YouTube works when service unavailable
- [ ] Remote CLI shows download progress from torrent service

## Open Questions

1. Should we maintain seeding ratio? (May require persistent storage)
2. Should we support multiple concurrent downloads?
3. Do we need a queue system for high load?
4. Should we cache downloaded files for repeat requests?

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: Infrastructure | 0.5 day | None |
| Phase 2: Torrent Service | 1 day | Phase 1 |
| Phase 3: Backend Integration | 0.5 day | Phase 2 |
| Phase 4: Monitoring | 0.5 day | Phase 3 |
| Phase 5: Documentation | 0.5 day | Phase 3 |
| **Total** | **3 days** | |

## References

- [Transmission RPC Spec](https://github.com/transmission/transmission/blob/main/docs/rpc-spec.md)
- [transmission-rpc Python library](https://github.com/Trim21/transmission-rpc)
- [Cloud Run networking limitations](https://cloud.google.com/run/docs/container-contract#network)

