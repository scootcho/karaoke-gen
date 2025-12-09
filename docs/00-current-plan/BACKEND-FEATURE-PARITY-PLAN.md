# Backend Feature Parity Plan

**Last Updated:** 2024-12-09

This document outlines the plan to achieve complete feature parity between the local `karaoke-gen` CLI and the cloud backend, enabling both the `karaoke-gen-remote` CLI and future web UI to have identical functionality.

---

## Vision

The karaoke-gen system supports multiple interfaces to the same core functionality:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KARAOKE-GEN ECOSYSTEM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INTERFACES                          BACKEND                               │
│   ──────────                          ───────                               │
│                                                                             │
│   ┌─────────────────┐                                                       │
│   │ karaoke-gen CLI │ ──── Local Processing (CPU/GPU) ────────┐            │
│   │ (local mode)    │                                          │            │
│   └─────────────────┘                                          │            │
│                                                                │            │
│   ┌─────────────────┐     ┌──────────────────────────────┐    │            │
│   │ karaoke-gen-    │     │  Cloud Backend (Cloud Run)   │    │            │
│   │ remote CLI      │ ──► │  • FastAPI                   │    ▼            │
│   └─────────────────┘     │  • Modal GPU for separation  │                 │
│                           │  • AudioShake for lyrics     │   OUTPUTS       │
│   ┌─────────────────┐     │  • KaraokeFinalise for video │   ───────       │
│   │ Web UI          │ ──► │                              │                 │
│   │ (future)        │     │  DISTRIBUTION:               │   • YouTube     │
│   └─────────────────┘     │  • YouTube upload            │   • Dropbox     │
│                           │  • Dropbox (via API/rclone)  │   • Google Drive│
│                           │  • Google Drive (public)     │   • Gmail Draft │
│                           │  • Gmail draft               │   • Discord     │
│                           │  • Discord notification      │                 │
│                           └──────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Principle:** Regardless of which interface initiates a job, if given the same input with all variables/secrets etc. provided, the outputs should:
1. Be uploaded to the **same YouTube channel** (Nomad Karaoke)
2. Be organized in the **same Dropbox folder** with brand-coded naming (e.g., NOMAD-1163)
3. Have final files copied to the **same Google Drive public share folders**
4. Generate the **same email draft** in the owner's Gmail
5. Send the **same Discord notification**

---

## Distribution Features - Full Specification

This section provides a detailed specification of how the distribution features work locally and how they must work in remote/cloud mode to achieve full feature parity.

### Feature 1: YouTube Upload

**Purpose:** Upload the final karaoke video to a YouTube channel.

**Local CLI Parameters:**
- `--enable_youtube_upload` - Enable the feature
- `--youtube_client_secrets_file` - Path to OAuth client secrets JSON
- `--youtube_description_file` - Path to description template file

**How It Works Locally:**
1. User provides OAuth client secrets file (from Google Cloud Console)
2. First run triggers browser OAuth flow, stores credentials in pickle file
3. Subsequent runs reuse stored credentials (refreshing if needed)
4. Final video uploaded with title from track metadata
5. Description populated from template file

**Remote/Cloud Implementation:**
- Store OAuth tokens in Secret Manager (`youtube-oauth-credentials`)
- Store client secrets in Secret Manager
- Description file content uploaded with job (or stored in Secret Manager as default)
- Backend uses stored credentials directly (no browser OAuth flow needed)

**CLI Mapping:**
| Local CLI | Remote CLI | Notes |
|-----------|------------|-------|
| `--enable_youtube_upload` | `--enable_youtube_upload` | Same flag |
| `--youtube_client_secrets_file` | N/A | Uses server-side credentials |
| `--youtube_description_file` | `--youtube_description_file` | Uploaded with job |

---

### Feature 2: Organized Directory (Dropbox) with Brand Code

**Purpose:** Rename the output folder with a sequential brand code and move to Dropbox, then get a sharing link.

**Local CLI Parameters:**
- `--brand_prefix` - Brand identifier (e.g., "NOMAD")
- `--organised_dir` - Local filesystem path to organized folder (Dropbox-synced)
- `--organised_dir_rclone_root` - rclone path mapping for the same folder

**How It Works Locally:**
1. Scan `organised_dir` for existing folders matching `{brand_prefix}-NNNN - *`
2. Calculate next sequence number (e.g., NOMAD-1163)
3. Rename output folder to `{brand_prefix}-{seq} - {Artist} - {Title}`
4. Move folder to `organised_dir`
5. Use rclone with `organised_dir_rclone_root` to get Dropbox sharing link

**Example existing structure:**
```
/Users/andrew/AB Dropbox/.../Tracks-Organized/
├── NOMAD-1162 - Arcy Drive - Roll My Stone/
├── NOMAD-1161 - Iggy Pop - Five Foot One/
├── NOMAD-1160 - Doug Stone - I'd Be Better Off (In a Pine Box)/
└── ...
```

**Remote/Cloud Implementation:**

The backend cannot rely on local filesystem paths. Instead, it must:

1. **Query Dropbox directly** to list existing folders and calculate sequence number
   - Use Dropbox API or rclone to list `organised_dir_rclone_root`
   - Parse folder names to find highest existing sequence number
   
2. **Upload folder contents directly to Dropbox** with the brand-coded name
   - Upload via Dropbox API or rclone
   - Create folder: `{organised_dir_rclone_root}/{brand_prefix}-{seq} - {Artist} - {Title}/`
   
3. **Get sharing link** for the uploaded folder
   - Use Dropbox API or rclone `link` command

**CLI Mapping:**
| Local CLI | Remote CLI | Notes |
|-----------|------------|-------|
| `--brand_prefix` | `--brand_prefix` | Same |
| `--organised_dir` | N/A | Not needed - uploads directly via API |
| `--organised_dir_rclone_root` | `--organised_dir_rclone_root` | Required for remote |

**Required Secrets:**
- `rclone-config` - Contains Dropbox config section (e.g., `[andrewdropboxfull]`)

---

### Feature 3: Public Share Directory (Google Drive)

**Purpose:** Copy final output files (MP4, MP4-720p, CDG) to a publicly shared Google Drive folder.

**Local CLI Parameters:**
- `--public_share_dir` - Local filesystem path to public share folder
- `--rclone_destination` - rclone destination for syncing to Google Drive

**How It Works Locally:**
1. Copy final files to subdirectories:
   - `{public_share_dir}/MP4/{brand_code} - {Artist} - {Title}.mp4` (4K)
   - `{public_share_dir}/MP4-720p/{brand_code} - {Artist} - {Title}.mp4`
   - `{public_share_dir}/CDG/{brand_code} - {Artist} - {Title}.zip`
2. Sync to Google Drive using rclone

**Example existing structure:**
```
/Users/andrew/.../Tracks-PublicShare/
├── CDG/
│   ├── NOMAD-1162 - Arcy Drive - Roll My Stone.zip
│   └── ...
├── MP4/
│   ├── NOMAD-1162 - Arcy Drive - Roll My Stone.mp4
│   └── ...
└── MP4-720p/
    ├── NOMAD-1162 - Arcy Drive - Roll My Stone.mp4
    └── ...
```

**Remote/Cloud Implementation:**

The backend must upload directly to Google Drive:

1. **Upload files directly to Google Drive** via API or rclone
   - `{rclone_destination}/MP4/{filename}.mp4`
   - `{rclone_destination}/MP4-720p/{filename}.mp4`
   - `{rclone_destination}/CDG/{filename}.zip`

**CLI Mapping:**
| Local CLI | Remote CLI | Notes |
|-----------|------------|-------|
| `--public_share_dir` | N/A | Not needed - uploads directly via API |
| `--rclone_destination` | `--rclone_destination` | Required for remote (or `--public_share_rclone_root`) |

**Required Secrets:**
- `rclone-config` - Contains Google Drive config section (e.g., `[googledrive]`)

---

### Feature 4: Email Draft (Gmail)

**Purpose:** Create a draft email in Gmail with the YouTube URL and Dropbox sharing link.

**Local CLI Parameters:**
- `--email_template_file` - Path to email template with placeholders

**Template Placeholders:**
- `{youtube_url}` - URL of uploaded YouTube video
- `{dropbox_link}` - Sharing link for Dropbox folder
- `{artist}` - Artist name
- `{title}` - Track title
- `{brand_code}` - Full brand code (e.g., NOMAD-1163)

**How It Works Locally:**
1. Read email template file
2. Replace placeholders with actual values
3. Create draft in Gmail via API (uses same OAuth credentials as YouTube)

**Remote/Cloud Implementation:**
1. Store Gmail OAuth credentials in Secret Manager
2. Upload template file content with job (or use default template from config)
3. After processing, create draft with populated template

**CLI Mapping:**
| Local CLI | Remote CLI | Notes |
|-----------|------------|-------|
| `--email_template_file` | `--email_template_file` | Uploaded with job |

**Required Secrets:**
- `gmail-oauth-credentials` - OAuth tokens for Gmail API

---

### Feature 5: Discord Notification

**Purpose:** Send a notification to Discord with track details.

**Local CLI Parameters:**
- `--discord_webhook_url` - Discord webhook URL

**Remote/Cloud Implementation:**
- Same as local - webhook URL passed through to backend
- KaraokeFinalise handles the notification

**CLI Mapping:**
| Local CLI | Remote CLI | Notes |
|-----------|------------|-------|
| `--discord_webhook_url` | `--discord_webhook_url` | Same |

---

## Implementation Status

### ✅ Core Processing (Complete)

| Feature | Status | Implementation |
|---------|--------|----------------|
| File upload | ✅ | `backend/api/routes/file_upload.py` |
| Audio separation | ✅ | `backend/workers/audio_worker.py` (Modal API) |
| Lyrics transcription | ✅ | `backend/workers/lyrics_worker.py` (AudioShake) |
| Human lyrics review | ✅ | `backend/api/routes/review.py` + hosted UI |
| Custom styles (video) | ✅ | `karaoke_gen/style_loader.py` unified module |
| Custom styles (CDG) | ✅ | Passed through to KaraokeFinalise |
| Title/End screens | ✅ | `backend/workers/screens_worker.py` |
| Video rendering | ✅ | `backend/workers/render_video_worker.py` |
| Instrumental selection | ✅ | API endpoint + CLI prompt |
| Video encoding (4 formats) | ✅ | `backend/workers/video_worker.py` |
| CDG/TXT packages | ✅ | KaraokeFinalise via video_worker |
| Non-interactive mode | ✅ | `-y` flag for automated testing |
| Output file download | ✅ | Streaming download endpoint |

### ⚠️ Distribution Features (Partial)

| Feature | Status | What Works | What's Needed |
|---------|--------|------------|---------------|
| YouTube upload | ⚠️ Partial | Server-side OAuth credentials loaded | Test with real credentials |
| Dropbox upload | ⚠️ Partial | rclone config loaded from Secret Manager | Test, verify sequence calculation works |
| Brand code calculation | ⚠️ Partial | Works via rclone ls | Test with real Dropbox |
| Public share (Google Drive) | ❌ Not done | - | Add rclone_destination param, implement upload |
| Gmail draft | ❌ Not done | - | Add gmail-oauth-credentials, implement |
| Discord notification | ⚠️ Untested | Webhook URL accepted | Test with real webhook |
| YouTube description file | ⚠️ Partial | Param exists | Upload file content with job |

### ❌ Not Yet Implemented

| Feature | Priority | Notes |
|---------|----------|-------|
| Public share upload to Google Drive | HIGH | Need `--rclone_destination` support |
| Gmail draft creation | HIGH | Need Gmail OAuth in Secret Manager |
| YouTube URL input | LOW | Requires yt-dlp in container |
| Batch processing | LOW | Queue management needed |

---

## Required Secrets Configuration

### Secret Manager Secrets

| Secret Name | Status | Contents | Description |
|-------------|--------|----------|-------------|
| `youtube-oauth-credentials` | ⚠️ Needs setup | JSON | OAuth tokens for YouTube upload |
| `rclone-config` | ⚠️ Needs setup | INI | rclone.conf with Dropbox + Google Drive configs |
| `gmail-oauth-credentials` | ❌ Not created | JSON | OAuth tokens for Gmail API |

### YouTube Credentials Format
```json
{
  "token": "ya29...",
  "refresh_token": "1//...",
  "token_uri": "https://oauth2.googleapis.com/token",
  "client_id": "xxx.apps.googleusercontent.com",
  "client_secret": "xxx",
  "scopes": ["https://www.googleapis.com/auth/youtube.upload"]
}
```

### rclone Config Format
```ini
[andrewdropboxfull]
type = dropbox
client_id = xxx
client_secret = xxx
token = {"access_token":"...","refresh_token":"..."}

[googledrive]
type = drive
client_id = xxx
client_secret = xxx
token = {"access_token":"...","refresh_token":"..."}
```

---

## Target Remote CLI Alias

Once fully implemented, the remote equivalent of `nomadauto` would be:

```bash
nomadauto_remote() {
    karaoke-gen-remote \
        --style_params_json="/path/to/karaoke-prep-styles-nomad.json" \
        --enable_cdg \
        --enable_txt \
        --brand_prefix=NOMAD \
        --organised_dir_rclone_root='andrewdropboxfull:MediaUnsynced/Karaoke/Tracks-Organized' \
        --rclone_destination='googledrive:Nomad Karaoke' \
        --enable_youtube_upload \
        --youtube_description_file='/path/to/youtube-video-description.txt' \
        --discord_webhook_url='https://discord.com/api/webhooks/...' \
        --email_template_file='/path/to/email-template.txt' \
        "$@"
}
```

**Key Differences from Local:**
- No `--organised_dir` (uploads directly via API, not local filesystem)
- No `--public_share_dir` (uploads directly via API, not local filesystem)
- No `--youtube_client_secrets_file` (uses server-side credentials)
- Files like youtube description and email template are uploaded with the job

---

## Architecture Considerations

### API vs rclone for Cloud Storage

**Current approach:** Use rclone with config from Secret Manager

**Pros:**
- Consistent with local CLI
- Supports many cloud providers
- rclone handles OAuth token refresh

**Cons:**
- Extra dependency
- Need to manage rclone config as secret

**Alternative:** Use native APIs (Dropbox SDK, Google Drive API)

**Pros:**
- Cleaner, no external dependencies
- More control over error handling

**Cons:**
- Need separate implementations for each provider
- More code to maintain

**Recommendation:** Continue with rclone approach for now, as it's already working locally and provides flexibility. Could migrate to native APIs later if needed.

### Secrets Management

**Current:** Individual secrets in Secret Manager

**Future consideration:** Could consolidate into a single "distribution-config" secret with all OAuth tokens and settings, making it easier to manage.

---

## Implementation Plan

### Phase 1: Complete Distribution Features (HIGH PRIORITY)

1. **YouTube Upload**
   - [x] Server-side OAuth credential loading
   - [ ] Test with real credentials
   - [ ] Upload youtube_description_file content with job

2. **Dropbox Organized Folder**
   - [x] rclone config loading from Secret Manager
   - [ ] Test sequence calculation via rclone ls
   - [ ] Test folder upload and sharing link

3. **Google Drive Public Share**
   - [ ] Add `--rclone_destination` to remote CLI
   - [ ] Add to Job model
   - [ ] Implement upload in video_worker

4. **Gmail Draft**
   - [ ] Create gmail_service.py
   - [ ] Add gmail-oauth-credentials to Secret Manager
   - [ ] Add `--email_template_file` upload support
   - [ ] Implement draft creation in video_worker

5. **Discord Notification**
   - [x] Webhook URL passed through
   - [ ] Test with real webhook

### Phase 2: Testing & Validation

1. **Set up all Secret Manager secrets**
2. **Run end-to-end test with all features enabled**
3. **Verify:**
   - Video uploaded to correct YouTube channel
   - Folder created in correct Dropbox location with correct brand code
   - Files uploaded to correct Google Drive folders
   - Email draft created with correct content
   - Discord notification sent

### Phase 3: Future Features (LOW PRIORITY)

- YouTube URL input (requires yt-dlp)
- Batch processing
- Existing instrumental support

---

## Files Reference

### Core Backend Files

| File | Purpose |
|------|---------|
| `backend/models/job.py` | Job data model - add new distribution fields |
| `backend/workers/video_worker.py` | Final processing - distribution happens here |
| `backend/services/rclone_service.py` | rclone config from Secret Manager |
| `backend/services/youtube_service.py` | YouTube OAuth from Secret Manager |
| `backend/services/gmail_service.py` | Gmail OAuth (to be created) |

### Shared Code

| File | Purpose |
|------|---------|
| `karaoke_gen/karaoke_finalise/karaoke_finalise.py` | All distribution logic |
| `karaoke_gen/utils/cli_args.py` | Shared CLI argument definitions |
| `karaoke_gen/utils/remote_cli.py` | Remote CLI implementation |

---

## Testing Checklist

Before declaring feature parity complete:

- [ ] Run `karaoke-gen` locally with all distribution features → verify outputs
- [ ] Run `karaoke-gen-remote` with same inputs → verify SAME outputs appear in SAME locations
- [ ] Specifically verify:
  - [ ] Same YouTube channel, same video title/description
  - [ ] Same Dropbox folder, correct sequence number
  - [ ] Same Google Drive folders (CDG/, MP4/, MP4-720p/)
  - [ ] Same email draft content
  - [ ] Same Discord notification

---

## Recent Changes Log

### 2024-12-09: Download Fix
- Added streaming download endpoint `/api/jobs/{job_id}/download/{category}/{file_key}`
- Removed dependency on signed URLs (simpler, works without special IAM permissions)
- CLI downloads via HTTP through backend

### 2024-12-09: Non-Interactive Mode
- Added `-y` flag for automated testing
- Auto-completes lyrics review
- Auto-selects clean instrumental

### 2024-12-09: Distribution Features (Partial)
- Added rclone config loading from Secret Manager
- Added YouTube OAuth credential loading from Secret Manager
- Wired `organised_dir_rclone_root` through API and CLI
- Added `enable_youtube_upload` flag

### 2024-12-09: Style Loader Consolidation
- Created `karaoke_gen/style_loader.py` as single source of truth
- Updated all workers to use unified style loading

---

## Next Steps for New Agent

1. **Read this document thoroughly** - understand the distribution features
2. **Set up Secret Manager secrets** for testing
3. **Complete the remaining distribution features:**
   - Google Drive public share upload
   - Gmail draft creation
4. **Test end-to-end** with real credentials
5. **Bump version in pyproject.toml** on each commit
