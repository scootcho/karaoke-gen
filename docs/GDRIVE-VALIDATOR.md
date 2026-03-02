# Google Drive Validator

Automated validation of the Nomad Karaoke public Google Drive share folder. Detects duplicate brand codes, invalid filenames, and sequence gaps.

## Overview

The public share folder (`1laRKAyxo0v817SstfM5XkpbWiNKNAMSX`) contains all published karaoke tracks organized into subfolders:

```
Public Share/
  CDG/         # .zip files (MP3 + CDG for KJ players)
  MP4/         # .mp4 files (4K lossless)
  MP4-720p/    # .mp4 files (720p lossy)
```

Each file follows the naming convention: `NOMAD-XXXX - Artist - Title.(mp4|zip)`

The validator checks:
- **Duplicate sequence numbers** - e.g., two files both named `NOMAD-1271`
- **Invalid filenames** - files that don't match the expected pattern
- **Sequence gaps** - missing numbers in the NOMAD-XXXX sequence (with known exclusions)

## Architecture

```
                              ┌────────────────────────┐
                              │  Cloud Scheduler       │
                              │  (9 PM ET daily)       │
                              └──────────┬─────────────┘
                                         │ OIDC auth
                                         ▼
┌──────────────────┐          ┌────────────────────────┐          ┌──────────────┐
│ Backend (post-   │  OIDC    │  gdrive-validator      │  API     │ Google Drive │
│ job completion)  │─────────→│  Cloud Function (Gen2) │─────────→│ API v3       │
└──────────────────┘          └──────────┬─────────────┘          └──────────────┘
                                         │
┌──────────────────┐              ┌──────┴──────┐
│ gcloud functions │              │             │
│ call (manual)    │─────────→    ▼             ▼
└──────────────────┘       ┌───────────┐ ┌────────────┐
                           │ SendGrid  │ │ Pushbullet │
                           │ (primary) │ │ (fallback) │
                           └───────────┘ └────────────┘
```

### Trigger Points

| Trigger | When | How |
|---------|------|-----|
| **Daily schedule** | 9:00 PM ET every day | Cloud Scheduler → HTTP POST with OIDC token |
| **Post-job** | 5 minutes after each job uploads to public share | Backend orchestrator → Cloud Tasks (5 min delay) → internal endpoint → Cloud Function |
| **Manual** | On demand | `python scripts/check_public_share.py` via gcloud CLI |

### Notifications

Notifications are sent via **both** channels (belt + suspenders):

1. **SendGrid email** (primary) - Sent to `gen@nomadkaraoke.com`. Provides a persistent, searchable record.
2. **Pushbullet** (fallback) - Push notification for immediate visibility.

Notifications are sent when:
- Issues are found (always)
- No issues found and `NOTIFY_ON_SUCCESS=true` (daily summary)
- Errors occur during validation

## Files

| File | Purpose |
|------|---------|
| `infrastructure/functions/gdrive_validator/main.py` | Cloud Function source code |
| `infrastructure/functions/gdrive_validator/requirements.txt` | Python dependencies |
| `infrastructure/functions/gdrive_validator/deploy.sh` | Manual deployment script |
| `infrastructure/__main__.py` | Pulumi config (env vars, secrets, IAM) |
| `infrastructure/modules/iam/worker_sas.py` | Service account definition |
| `backend/services/gdrive_validator_client.py` | Backend HTTP client (OIDC auth) |
| `backend/services/worker_service.py` | Cloud Tasks scheduling (5 min delay) |
| `backend/api/routes/internal.py` | `/internal/trigger-gdrive-validation` endpoint |
| `backend/workers/video_worker_orchestrator.py` | Post-job trigger integration |
| `infrastructure/modules/cloud_tasks.py` | Pulumi config for `gdrive-validation-queue` |
| `infrastructure/functions/gdrive_validator/test_main.py` | Unit tests for Cloud Function |
| `scripts/check_public_share.py` | Local CLI for manual checks |

## Configuration

### Environment Variables (Cloud Function)

| Variable | Value | Description |
|----------|-------|-------------|
| `GDRIVE_FOLDER_ID` | `1laRKAyxo0v817SstfM5XkpbWiNKNAMSX` | Root folder of public share |
| `NOTIFY_ON_SUCCESS` | `true` | Send daily "all clear" summary |
| `EMAIL_TO` | `gen@nomadkaraoke.com` | Email recipient |
| `EMAIL_FROM` | `gen@nomadkaraoke.com` | Email sender |

### Secrets (Cloud Function)

| Secret | Source | Description |
|--------|--------|-------------|
| `SENDGRID_API_KEY` | `sendgrid-api-key:latest` | SendGrid API key for email |
| `PUSHBULLET_API_KEY` | `pushbullet-api-key:latest` | Pushbullet API key for push notifications |

### Secrets (Backend / Cloud Run)

| Secret | Source | Description |
|--------|--------|-------------|
| `GDRIVE_VALIDATOR_URL` | `gdrive-validator-url:latest` | Cloud Function URL for post-job trigger |

### IAM

| Principal | Role | Resource | Purpose |
|-----------|------|----------|---------|
| `gdrive-validator@` SA | `roles/cloudfunctions.invoker` | gdrive-validator function | Self-invoke (Cloud Scheduler) |
| Cloud Scheduler agent | `roles/cloudfunctions.invoker` | gdrive-validator function | Daily trigger |
| `karaoke-backend@` SA | `roles/cloudfunctions.invoker` | gdrive-validator function | Post-job trigger |
| `karaoke-backend@` SA | `roles/run.invoker` | gdrive-validator Cloud Run service | Gen2 function HTTP access |

### Known Gaps

The validator knows about expected sequence gaps (historical missing numbers). These are configured identically in both:
- `infrastructure/functions/gdrive_validator/main.py` (Cloud Function)
- `scripts/validate_and_sync.py` (local script)

When a new gap is discovered intentionally (e.g., a track was removed), update the `KNOWN_GAPS` dict in **both** files.

## Usage

### Manual Check

```bash
# Formatted output
python scripts/check_public_share.py

# Raw JSON
python scripts/check_public_share.py --json
```

Exit codes: `0` = all clear, `1` = issues found, `2` = error.

### Checking Cloud Function Logs

```bash
gcloud functions logs read gdrive-validator --region=us-central1 --project=nomadkaraoke --limit=50
```

### Redeploying the Cloud Function

The Cloud Function source is not deployed via CI — it's deployed either:
1. **Via Pulumi** (infrastructure changes like env vars, secrets, IAM)
2. **Via `deploy.sh`** (code changes to `main.py`)

```bash
cd infrastructure/functions/gdrive_validator
./deploy.sh
```

Note: `deploy.sh` deploys the source code. Pulumi manages the infrastructure (env vars, secrets, IAM, scheduler). After running `deploy.sh`, the Pulumi-managed config is overwritten by the gcloud deploy — run `pulumi up` afterward if you need to restore Pulumi-managed settings.

## Troubleshooting

### Email Not Received

1. Check Cloud Function logs for SendGrid errors:
   ```bash
   gcloud functions logs read gdrive-validator --region=us-central1 --limit=20
   ```
2. Verify the SendGrid API key is set:
   ```bash
   gcloud secrets versions access latest --secret=sendgrid-api-key --project=nomadkaraoke | head -c 10
   ```
3. Check SendGrid dashboard for delivery status
4. Pushbullet should still work as fallback

### Post-Job Trigger Not Firing

The post-job trigger uses a 5-minute Cloud Tasks delay (via `gdrive-validation-queue`) to allow E2E test cleanup to finish before validation runs.

1. Check that `GDRIVE_VALIDATOR_URL` secret is set:
   ```bash
   gcloud secrets versions access latest --secret=gdrive-validator-url --project=nomadkaraoke
   ```
2. Check backend logs for "Scheduled delayed GDrive validation" or "GDrive validation trigger failed"
3. Check Cloud Tasks queue for pending tasks:
   ```bash
   gcloud tasks list --queue=gdrive-validation-queue --location=us-central1 --project=nomadkaraoke
   ```
4. Verify the backend SA has invoker permissions:
   ```bash
   gcloud functions get-iam-policy gdrive-validator --region=us-central1 --project=nomadkaraoke
   ```
5. The trigger only fires for non-private jobs (jobs with `gdrive_folder_id` set)
6. If Cloud Tasks scheduling fails, the orchestrator falls back to immediate validation

### False Positive Gaps

If the validator reports gaps that are intentional:
1. Add the gap number(s) to `KNOWN_GAPS` in both `main.py` and `scripts/validate_and_sync.py`
2. Redeploy the cloud function with `./deploy.sh`

### Duplicate Brand Code Detected

This is the most critical alert. Steps:
1. Check which files have the duplicate: the notification lists them
2. Determine which is correct (check Firestore job records)
3. Remove or rename the incorrect file in Google Drive
4. Re-trigger validation to confirm the fix

## Cloud Function vs Local Script

| Check | Cloud Function | Local Script (`validate_and_sync.py`) |
|-------|---------------|--------------------------------------|
| Duplicate sequence numbers | Yes | Yes |
| Invalid filenames | Yes | Yes |
| Sequence gaps | Yes | Yes |
| ZIP contents (MP3+CDG) | No (expensive) | Yes |
| Video resolution | No (expensive) | Yes |
| Render quality | No (expensive) | Yes |
| Bidirectional sync | No (read-only) | Yes (rclone) |

The cloud function does metadata-only checks via the GDrive API (fast, cheap, can run frequently). The local script does deep content validation that requires downloading files (slow, run manually).

## History

- **2025-12-24**: Initial cloud function deployed with Pushbullet notifications and daily Cloud Scheduler trigger
- **2026-02-28**: Added SendGrid email (primary), kept Pushbullet (fallback). Added post-job trigger from backend. Added `scripts/check_public_share.py` for manual invocation. Motivated by NOMAD-1271 duplicate brand code incident where daily-only checks left a duplicate undetected for ~24 hours.
- **2026-03-02**: NOMAD-1276 incident fix. Post-job trigger now uses 5-minute Cloud Tasks delay instead of immediate invocation, preventing false "all clear" when E2E test files are still in GDrive during cleanup. Also fixed cross-folder gap detection (uses global max across all folders) and added 28 unit tests for the Cloud Function.
