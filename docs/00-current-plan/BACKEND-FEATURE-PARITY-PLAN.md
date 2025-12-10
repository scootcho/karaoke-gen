# Backend Feature Parity Plan

**Last Updated:** 2024-12-10  
**Status:** ✅ Core Feature Parity Achieved (v0.71.0)

This document tracks the progress toward complete feature parity between the local `karaoke-gen` CLI and the cloud backend, enabling the `karaoke-gen-remote` CLI to have equivalent functionality.

---

## 🎉 Milestone: First Successful End-to-End Run

On December 10, 2024, we completed the first successful end-to-end karaoke track generation using `karaoke-gen-remote` with the cloud backend:

```bash
karaoke-gen-remote \
  --style_params_json="./karaoke-prep-styles-nomad.json" \
  --enable_cdg \
  --enable_txt \
  --brand_prefix=NOMAD \
  --enable_youtube_upload \
  --youtube_description_file="./youtube-video-description.txt" \
  ./waterloo1min.flac ABBA "Waterloo Test 3"
```

**Results:**
- ✅ Audio separation via Modal API
- ✅ Lyrics transcription via AudioShake
- ✅ Custom style assets uploaded and applied
- ✅ Lyrics review UI workflow
- ✅ Instrumental selection prompt
- ✅ Video rendering with corrected lyrics
- ✅ Final video encoding (4 formats)
- ✅ CDG/TXT package generation
- ✅ YouTube upload
- ✅ Dropbox upload with brand code (NOMAD-1163)
- ✅ Google Drive upload
- ✅ Discord notification
- ✅ All files downloaded locally

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
│   └─────────────────┘     │  • YouTube upload ✅         │   • Dropbox     │
│                           │  • Dropbox (native API) ✅   │   • Google Drive│
│                           │  • Google Drive (native) ✅  │   • Discord     │
│                           │  • Discord notification ✅   │                 │
│                           └──────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

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

### ✅ Distribution Features (Complete)

| Feature | Status | Notes |
|---------|--------|-------|
| YouTube upload | ✅ | Server-side OAuth credentials |
| Dropbox upload | ✅ | Native API (via refresh token) |
| Brand code calculation | ✅ | Sequential from existing folders |
| Google Drive upload | ✅ | Service account credentials |
| Discord notification | ✅ | Webhook URL from job or default |

### ⏳ Not Yet Implemented (Lower Priority)

| Feature | Priority | Notes |
|---------|----------|-------|
| Gmail draft creation | LOW | Nice-to-have, not blocking |
| YouTube URL input | LOW | Requires yt-dlp in container |
| Batch processing | LOW | Queue management needed |
| Existing instrumental support | LOW | For re-processing existing tracks |

---

## Required Secrets Configuration

### Secret Manager Secrets (All Configured)

| Secret Name | Status | Description |
|-------------|--------|-------------|
| `audioshake-api-key` | ✅ | AudioShake API key |
| `genius-api-key` | ✅ | Genius lyrics API |
| `audio-separator-api-url` | ✅ | Modal API URL |
| `spotify-cookie` | ✅ | Spotify lyrics access |
| `rapidapi-key` | ✅ | Musixmatch via RapidAPI |
| `youtube-oauth-credentials` | ✅ | YouTube upload OAuth tokens |
| `dropbox-oauth-credentials` | ✅ | Dropbox API OAuth tokens |
| `gdrive-service-account` | ✅ | Google Drive service account |
| `discord-webhook-url` | ✅ | Default Discord webhook |

### Default Distribution Settings

The backend supports default distribution settings via environment variables:

| Environment Variable | Description |
|---------------------|-------------|
| `DEFAULT_DROPBOX_PATH` | Default Dropbox folder path |
| `DEFAULT_GDRIVE_FOLDER_ID` | Default Google Drive folder ID |
| `DEFAULT_DISCORD_WEBHOOK_URL` | Default Discord webhook URL |

These can be overridden per-job via CLI arguments.

---

## Remote CLI Options

The `karaoke-gen-remote` CLI supports the following distribution options:

```bash
karaoke-gen-remote \
  --style_params_json="/path/to/styles.json" \
  --enable_cdg \
  --enable_txt \
  --brand_prefix=NOMAD \
  --enable_youtube_upload \
  --youtube_description_file="/path/to/description.txt" \
  ./audio.flac "Artist" "Title"
```

**Notes:**
- `--style_params_json`: All referenced images/fonts are auto-uploaded
- Distribution uses server-side credentials (no local secrets needed)
- `--dropbox_path` and `--gdrive_folder_id` can override defaults

---

## Future Architecture: Shared Pipeline

Once feature parity is achieved, the codebase should be refactored toward a **shared pipeline architecture** where both local and remote execution use the same abstractions.

### Current State (Divergent Paths)

```
LOCAL CLI                               CLOUD BACKEND
─────────                               ─────────────
KaraokeGen.process()                    API Routes
    │                                       │
    ├─► AudioProcessor                      ├─► audio_worker.py
    │   └── Modal API or local              │   └── Modal API
    │                                       │
    ├─► LyricsProcessor                     ├─► lyrics_worker.py
    │   └── Orchestrates everything         │   └── Transcription only
    │       including video generation      │
    │                                       ├─► screens_worker.py
    │                                       │
    │                                       ├─► render_video_worker.py
    │                                       │   └── OutputGenerator directly
    │                                       │
    └─► KaraokeFinalise                     └─► video_worker.py
        └── Encoding, distribution              └── KaraokeFinalise
```

**Problems:**
- Video generation called differently (via LyricsProcessor vs OutputGenerator directly)
- LyricsProcessor does too many things (fetching, transcription, video, file management)
- Testing requires mocking different things for local vs remote
- Bug fixes may need to be applied in multiple places

### Target State (Shared Pipeline)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SHARED PIPELINE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   AudioInput → Separation → Transcription → Review → Render → Finalize     │
│       │            │             │            │         │          │        │
│       ▼            ▼             ▼            ▼         ▼          ▼        │
│   ┌────────┐  ┌────────┐   ┌────────┐   ┌────────┐ ┌────────┐ ┌────────┐  │
│   │ Stage  │  │ Stage  │   │ Stage  │   │ Stage  │ │ Stage  │ │ Stage  │  │
│   │  API   │  │  API   │   │  API   │   │  API   │ │  API   │ │  API   │  │
│   └────┬───┘  └────┬───┘   └────┬───┘   └────┬───┘ └────┬───┘ └────┬───┘  │
│        │           │            │            │          │          │       │
│   ┌────┴───────────┴────────────┴────────────┴──────────┴──────────┴────┐  │
│   │                         EXECUTION LAYER                              │  │
│   │                                                                      │  │
│   │   Local Mode:        │    Remote Mode:                              │  │
│   │   - Direct calls     │    - HTTP to backend                         │  │
│   │   - Local GPU/CPU    │    - Workers + Modal                         │  │
│   │   - Blocking         │    - Async + polling                         │  │
│   └──────────────────────┴───────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- Single source of truth for each pipeline stage
- Each stage independently testable
- Same business logic regardless of execution mode
- Easier to add new stages or modify existing ones
- DRY - fix bugs once, works everywhere

### Implementation Plan for Shared Pipeline

This refactor should be done in a separate branch after the v0.71.0 release:

1. **Extract stage interfaces**
   ```python
   class PipelineStage(Protocol):
       async def execute(self, context: PipelineContext) -> StageResult:
           ...
   ```

2. **Create execution adapters**
   ```python
   class LocalExecutor:
       """Runs stages directly in-process"""
       
   class RemoteExecutor:
       """Runs stages via backend API/workers"""
   ```

3. **Refactor incrementally**
   - Start with one stage (e.g., Separation)
   - Prove the pattern works
   - Migrate other stages

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ backend/tests/ -v

# Backend tests only
pytest backend/tests/ -v

# With coverage
pytest tests/unit/ -v --cov=karaoke_gen --cov-report=term-missing
```

### Test Coverage Requirements

- Minimum 70% coverage enforced in CI
- All new features must have tests
- Integration tests for critical paths

---

## Deployment

### Environment Variables (Cloud Run)

```
GOOGLE_CLOUD_PROJECT=karaoke-gen
GCS_BUCKET_NAME=karaoke-gen-storage
MODAL_API_URL=https://modal-api-url
AUDIOSHAKE_API_TOKEN=xxx
GENIUS_API_TOKEN=xxx
DEFAULT_DROPBOX_PATH=/path/to/dropbox/folder
DEFAULT_GDRIVE_FOLDER_ID=folder-id
DEFAULT_DISCORD_WEBHOOK_URL=https://discord.com/...
```

### CI/CD Pipeline

- **Test Workflow**: Runs on all PRs
- **Build Workflow**: Builds Docker image on push to main
- **Deploy**: Manual trigger to Cloud Run

---

## Files Reference

### Core Backend Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app entry point |
| `backend/config.py` | Environment configuration |
| `backend/models/job.py` | Job data model (Firestore) |
| `backend/services/job_manager.py` | Job state management |
| `backend/services/storage_service.py` | GCS operations |
| `backend/services/credential_manager.py` | OAuth credential management |
| `backend/services/dropbox_service.py` | Native Dropbox API |
| `backend/services/gdrive_service.py` | Native Google Drive API |
| `backend/services/youtube_service.py` | YouTube upload service |

### Worker Files

| File | Purpose |
|------|---------|
| `backend/workers/audio_worker.py` | Modal API audio separation |
| `backend/workers/lyrics_worker.py` | AudioShake transcription |
| `backend/workers/screens_worker.py` | Title/end screen generation |
| `backend/workers/render_video_worker.py` | Post-review video with lyrics |
| `backend/workers/video_worker.py` | Final encoding via KaraokeFinalise |
| `backend/workers/style_helper.py` | Style config loading from GCS |

### API Routes

| File | Purpose |
|------|---------|
| `backend/api/routes/file_upload.py` | Job submission with file upload |
| `backend/api/routes/jobs.py` | Job status/management |
| `backend/api/routes/review.py` | Lyrics review endpoints |
| `backend/api/routes/internal.py` | Worker callback endpoints |
| `backend/api/routes/auth.py` | OAuth flow for distribution services |

### Remote CLI

| File | Purpose |
|------|---------|
| `karaoke_gen/utils/remote_cli.py` | Remote CLI implementation |
| `karaoke_gen/utils/cli_args.py` | Shared CLI argument definitions |

---

## Recent Changes Log

### 2024-12-10: v0.71.0 - Core Feature Parity Complete

**First successful end-to-end remote run!**

- All core processing working (audio, lyrics, screens, video)
- All distribution features working (YouTube, Dropbox, Google Drive, Discord)
- Native API integration for Dropbox and Google Drive (no rclone dependency)
- Comprehensive documentation updates
- Ready for merge to main

### 2024-12-09: Distribution Services Integration

- Added native Dropbox API service with OAuth refresh
- Added native Google Drive API with service account
- Added YouTube upload with OAuth credentials
- Added credential validation on job submission
- Added default distribution settings from environment

### 2024-12-09: Download Fix

- Added streaming download endpoint `/api/jobs/{job_id}/download/{category}/{file_key}`
- Removed dependency on signed URLs (simpler, works without special IAM permissions)
- CLI downloads via HTTP through backend

### 2024-12-09: Non-Interactive Mode

- Added `-y` flag for automated testing
- Auto-completes lyrics review
- Auto-selects clean instrumental

### 2024-12-08: Style Loader Consolidation

- Created `karaoke_gen/style_loader.py` as single source of truth
- Updated all workers to use unified style loading
- Style assets properly uploaded and applied

---

## Next Steps

### Immediate (Post-Merge)
1. ✅ Merge `replace-modal-with-google-cloud` branch to main
2. ✅ Tag v0.71.0 release
3. Update PyPI package

### Short-Term
1. Monitor production usage
2. Address any edge cases found
3. Improve error messages and logging

### Long-Term (Shared Pipeline Refactor)
1. Create new branch for shared pipeline architecture
2. Extract stage interfaces
3. Implement execution adapters
4. Migrate stages incrementally
5. Achieve true code sharing between local and remote
