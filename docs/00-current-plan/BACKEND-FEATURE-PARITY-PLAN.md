# Backend Feature Parity Plan

**Last Updated:** 2024-12-10  
**Status:** ✅ Core Feature Parity Achieved (v0.71.0)

This document tracks the progress toward complete feature parity between the local `karaoke-gen` CLI and the cloud backend, enabling the `karaoke-gen-remote` CLI to have equivalent functionality.

### Quick Parity Summary

| Category | Supported | Total | Parity |
|----------|-----------|-------|--------|
| Core Processing | 12 | 12 | **100%** |
| Distribution | 5 | 5 | **100%** |
| Lyrics Configuration | 1 | 5 | **20%** |
| Style Configuration | 1 | 4 | **25%** |
| Workflow Control | 0 | 7 | **0%** |
| Audio Processing | 0 | 6 | **0%** |
| Input Modes | 1 | 4 | **25%** |

**Overall:** Core workflow complete, but many optional parameters not yet supported. See [CLI Parameter Parity Analysis](#-cli-parameter-parity-analysis) for details.

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

## 📊 CLI Parameter Parity Analysis

This section provides a comprehensive comparison of all CLI parameters between `karaoke-gen` (local) and `karaoke-gen-remote`.

**Legend:**
- ✅ Fully supported
- ⚠️ Partially supported (limited functionality)
- ❌ Not supported (ignored or errors)
- 🔹 Remote-only (not applicable to local CLI)
- N/A Not applicable to this mode

### Positional Arguments

| Parameter | Local | Remote | Notes |
|-----------|-------|--------|-------|
| `<file>` | ✅ | ✅ | Local file path |
| `<url>` (YouTube) | ✅ | ❌ | YouTube URL input not yet supported |
| `<artist> <title>` (search) | ✅ | ❌ | Audio search via flacfetch not yet supported |
| Folder input | ✅ | ❌ | Batch folder processing not yet supported |

### Workflow Control

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--prep-only` | ✅ | ❌ | LOW | Ignored - remote always runs full pipeline |
| `--finalise-only` | ✅ | ❌ | LOW | Errors - not applicable to remote |
| `--skip-transcription` | ✅ | ❌ | MEDIUM | Ignored - could be useful for re-processing |
| `--skip-separation` | ✅ | ❌ | MEDIUM | Ignored - could be useful for re-processing |
| `--skip-lyrics` | ✅ | ❌ | LOW | Ignored |
| `--lyrics-only` | ✅ | ❌ | LOW | Ignored |
| `--edit-lyrics` | ✅ | ❌ | MEDIUM | Errors - useful for fixing existing tracks |
| `--resume` | N/A | 🔹 | - | Resume monitoring existing job |
| `--cancel` | N/A | 🔹 | - | Cancel running job |
| `--retry` | N/A | 🔹 | - | Retry failed job |
| `--delete` | N/A | 🔹 | - | Delete job and files |
| `--list` | N/A | 🔹 | - | List all jobs |

### Logging & Debugging

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--log_level` | ✅ | ✅ | - | Fully supported |
| `--dry_run` | ✅ | ❌ | LOW | Ignored |
| `--render_bounding_boxes` | ✅ | ❌ | LOW | Ignored - debugging only |

### Input/Output Configuration

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--filename_pattern` | ✅ | N/A | - | Only for folder processing |
| `--output_dir` | ✅ | ✅ | - | Download location for remote |
| `--no_track_subfolders` | ✅ | ❌ | LOW | Ignored - remote always creates subfolders |
| `--lossless_output_format` | ✅ | ❌ | LOW | Ignored - backend uses FLAC |
| `--output_png` | ✅ | ❌ | LOW | Ignored - backend outputs both |
| `--output_jpg` | ✅ | ❌ | LOW | Ignored - backend outputs both |

### Audio Fetching Configuration

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--auto-download` | ✅ | ❌ | LOW | Warned - audio search not yet supported |

### Audio Processing Configuration

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--clean_instrumental_model` | ✅ | ❌ | LOW | Ignored - backend uses fixed models |
| `--backing_vocals_models` | ✅ | ❌ | LOW | Ignored - backend uses fixed models |
| `--other_stems_models` | ✅ | ❌ | LOW | Ignored - backend uses fixed models |
| `--model_file_dir` | ✅ | N/A | - | Not applicable - backend has own models |
| `--existing_instrumental` | ✅ | ❌ | MEDIUM | Warned - useful for re-processing |
| `--instrumental_format` | ✅ | ❌ | LOW | Ignored - backend uses FLAC |

### Lyrics Configuration

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--lyrics_artist` | ✅ | ❌ | **HIGH** | Not sent to backend - **NEEDED** |
| `--lyrics_title` | ✅ | ❌ | **HIGH** | Not sent to backend - **NEEDED** |
| `--lyrics_file` | ✅ | ❌ | **HIGH** | Not sent to backend - **NEEDED** |
| `--subtitle_offset_ms` | ✅ | ❌ | MEDIUM | Not sent to backend |
| `--skip_transcription_review` | ✅ | ⚠️ | LOW | Use `-y` flag for non-interactive mode |

### Style Configuration

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--style_params_json` | ✅ | ✅ | - | Fully supported with asset uploads |
| `--style_override` | ✅ | ❌ | MEDIUM | Not sent to backend |
| `--background_video` | ✅ | ❌ | MEDIUM | Warned - would need video upload support |
| `--background_video_darkness` | ✅ | ❌ | LOW | Depends on --background_video |

### Finalisation Configuration

| Parameter | Local | Remote | Priority | Notes |
|-----------|-------|--------|----------|-------|
| `--enable_cdg` | ✅ | ✅ | - | Fully supported |
| `--enable_txt` | ✅ | ✅ | - | Fully supported |
| `--brand_prefix` | ✅ | ✅ | - | Fully supported |
| `--organised_dir` | ✅ | N/A | - | Local-only (local filesystem) |
| `--organised_dir_rclone_root` | ✅ | ✅ | - | Legacy rclone support |
| `--public_share_dir` | ✅ | N/A | - | Local-only (local filesystem) |
| `--enable_youtube_upload` | ✅ | ✅ | - | Fully supported (server-side credentials) |
| `--youtube_client_secrets_file` | ✅ | N/A | - | Server uses stored credentials |
| `--youtube_description_file` | ✅ | ✅ | - | Fully supported |
| `--rclone_destination` | ✅ | N/A | - | Local-only (use `--gdrive_folder_id`) |
| `--dropbox_path` | N/A | 🔹 | - | Remote-only (native API) |
| `--gdrive_folder_id` | N/A | 🔹 | - | Remote-only (native API) |
| `--discord_webhook_url` | ✅ | ✅ | - | Fully supported |
| `--email_template_file` | ✅ | ❌ | LOW | Warned - not implemented |
| `--keep-brand-code` | ✅ | ❌ | LOW | Not sent to backend |
| `-y` / `--yes` | ✅ | ✅ | - | Non-interactive mode |
| `--test_email_template` | ✅ | N/A | - | Local testing only |

### Remote CLI Specific Options

| Parameter | Local | Remote | Notes |
|-----------|-------|--------|-------|
| `--service-url` | N/A | 🔹 | Backend service URL |
| `--review-ui-url` | N/A | 🔹 | Lyrics review UI URL |
| `--poll-interval` | N/A | 🔹 | Status polling interval |
| `--environment` | N/A | 🔹 | Job tagging for filtering |
| `--client-id` | N/A | 🔹 | Job tagging for filtering |
| `--filter-environment` | N/A | 🔹 | Filter jobs in --list |
| `--filter-client-id` | N/A | 🔹 | Filter jobs in --list |
| `--bulk-delete` | N/A | 🔹 | Bulk delete matching jobs |

---

## 🎯 High Priority Parity Gaps

These parameters are commonly used and should be prioritized for remote CLI support:

### 1. Lyrics Override Parameters (HIGH)

**Parameters:** `--lyrics_artist`, `--lyrics_title`, `--lyrics_file`

**Use Case:** Override lyrics search or provide custom lyrics file when:
- Song has a different name in lyrics databases
- Artist name differs (feat. artists, etc.)
- User has manually corrected lyrics file

**Implementation Required:**
1. Remote CLI: Add to `submit_job()` method
2. Remote CLI: Upload lyrics file if provided
3. Backend: Add Form parameters to upload endpoint
4. Backend: Pass to lyrics worker

### 2. Subtitle Offset (MEDIUM)

**Parameter:** `--subtitle_offset_ms`

**Use Case:** Adjust timing when audio has intro padding or sync issues.

**Implementation Required:**
1. Remote CLI: Send to backend
2. Backend: Store in job and pass to render worker

### 3. Style Override (MEDIUM)

**Parameter:** `--style_override`

**Use Case:** Quick style tweaks without modifying JSON file.

**Implementation Required:**
1. Remote CLI: Send overrides to backend
2. Backend: Merge with style_params before processing

### 4. Existing Instrumental (MEDIUM)

**Parameter:** `--existing_instrumental`

**Use Case:** Re-process a track with better instrumental, skip separation.

**Implementation Required:**
1. Remote CLI: Upload instrumental file
2. Backend: Skip audio worker, use provided file

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

### ⏳ Not Yet Implemented

| Feature | Priority | Notes |
|---------|----------|-------|
| **Lyrics override params** | **HIGH** | `--lyrics_artist`, `--lyrics_title`, `--lyrics_file` |
| Subtitle offset | MEDIUM | `--subtitle_offset_ms` for timing adjustments |
| Style override | MEDIUM | `--style_override` for quick tweaks |
| Existing instrumental | MEDIUM | `--existing_instrumental` for re-processing |
| Skip separation/transcription | MEDIUM | Workflow control for re-processing |
| Edit lyrics mode | MEDIUM | `--edit-lyrics` for fixing existing tracks |
| Background video | MEDIUM | `--background_video` requires video upload |
| YouTube URL input | LOW | Requires yt-dlp in container |
| Audio search (flacfetch) | LOW | Artist+title search, auto-download |
| Batch folder processing | LOW | Process multiple files at once |
| Gmail draft creation | LOW | Nice-to-have, not blocking |

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

### Short-Term: Feature Parity (Priority Order)

1. **Lyrics Override Parameters** (HIGH)
   - Add `--lyrics_artist`, `--lyrics_title`, `--lyrics_file` support
   - Files: `remote_cli.py`, `file_upload.py`, `lyrics_worker.py`
   - Enables: Using correct lyrics for covers, remixes, alternate titles

2. **Subtitle Offset** (MEDIUM)
   - Add `--subtitle_offset_ms` support
   - Files: `remote_cli.py`, `file_upload.py`, `render_video_worker.py`
   - Enables: Timing adjustments for sync issues

3. **Style Override** (MEDIUM)
   - Add `--style_override` support
   - Files: `remote_cli.py`, `file_upload.py`, `style_helper.py`
   - Enables: Quick style tweaks without editing JSON

4. **Existing Instrumental** (MEDIUM)
   - Add `--existing_instrumental` upload support
   - Files: `remote_cli.py`, `file_upload.py`, `audio_worker.py`
   - Enables: Re-processing with better instrumentals

### Medium-Term: Workflow Features

1. **Skip Separation/Transcription flags**
   - Enable re-processing workflows
   
2. **Edit Lyrics Mode**
   - Allow fixing lyrics on completed jobs

3. **Background Video Support**
   - Upload and use video backgrounds

### Long-Term (Shared Pipeline Refactor)
1. Create new branch for shared pipeline architecture
2. Extract stage interfaces
3. Implement execution adapters
4. Migrate stages incrementally
5. Achieve true code sharing between local and remote
