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
│                           │  • Dropbox (via rclone)      │   • Discord     │
│                           │  • Email draft               │   • Email       │
│                           │  • Discord notification      │                 │
│                           └──────────────────────────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Principle:** Regardless of which interface initiates a job, if given the same input with all variables/secrets etc. provided, the outputs should:
1. Be uploaded to the **same YouTube channel** (Nomad Karaoke)
2. Be organized in the **same Dropbox folder structure** (via rclone)
3. Generate the **same email draft** in the owner's Gmail
4. Send the **same Discord notification**

---

## Current State

### ✅ Fully Implemented

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
| Discord notifications | ✅ | KaraokeFinalise via video_worker |
| Brand code generation | ✅ | Server-side mode using rclone |
| Output file download | ✅ | `karaoke_gen/utils/remote_cli.py` |

### ⚠️ Partially Implemented

| Feature | Current State | Needed Work |
|---------|---------------|-------------|
| Dropbox upload | Has `organised_dir_rclone_root` param but not wired | Wire through from job model |
| Public share copy | Has server-side rclone support | Add to job model and API |

### ❌ Not Yet Implemented

| Feature | Priority | Notes |
|---------|----------|-------|
| **YouTube upload** | HIGH | Server-side OAuth required |
| **Email draft** | HIGH | Gmail API integration |
| **rclone sync** | MEDIUM | For public share distribution |
| YouTube URL input | LOW | Requires yt-dlp in container |
| Batch processing | LOW | Queue management needed |

---

## Implementation Plan

### Phase 1: Distribution Features (HIGH PRIORITY)

These features are essential for the business workflow - every karaoke video needs to end up on YouTube and Dropbox.

#### 1.1 YouTube Upload

**Goal:** Upload final videos to the Nomad Karaoke YouTube channel from the backend.

**Current Local CLI Flow:**
```python
# karaoke_gen/karaoke_finalise/karaoke_finalise.py
finalise = KaraokeFinalise(
    youtube_client_secrets_file="/path/to/client_secrets.json",
    youtube_description_file="/path/to/description.txt",
)
# Uses google-auth-oauthlib for OAuth flow
# Stores credentials in pickle file
```

**Backend Implementation Plan:**

1. **Store OAuth credentials in Secret Manager**
   - Upload refresh token to Google Secret Manager
   - Create helper to retrieve and refresh credentials
   - File: `backend/services/youtube_service.py` (new)

2. **Update Job model**
   ```python
   # backend/models/job.py
   youtube_upload_enabled: bool = False
   youtube_description: Optional[str] = None
   ```

3. **Update video_worker.py**
   ```python
   finalise = KaraokeFinalise(
       youtube_client_secrets_file=None,  # Not used
       user_youtube_credentials=credentials,  # Pre-loaded from Secret Manager
       youtube_description_file=youtube_desc_path,  # Downloaded from job
   )
   ```

4. **Update remote CLI and API**
   - Accept `--youtube_upload` flag
   - Accept `--youtube_description_file` parameter
   - Upload description file content to GCS with job

**Files to modify:**
- `backend/models/job.py` - Add youtube fields
- `backend/workers/video_worker.py` - Load credentials, pass to KaraokeFinalise
- `backend/services/youtube_service.py` - NEW: Credential management
- `backend/api/routes/file_upload.py` - Accept youtube params
- `karaoke_gen/utils/remote_cli.py` - Parse and upload youtube params

#### 1.2 Dropbox Upload (via rclone)

**Goal:** Upload all output files to organized Dropbox folder with brand code naming.

**Current Local CLI Flow:**
```python
finalise = KaraokeFinalise(
    brand_prefix="NOMAD",
    organised_dir="/local/path/to/dropbox/Karaoke",
    organised_dir_rclone_root="dropbox-nomad:Karaoke",  # For server-side
)
# In server_side_mode, uses rclone to:
# 1. List existing folders to get next brand code
# 2. Upload files to brand-coded folder
# 3. Generate sharing link
```

**Backend Implementation Plan:**

1. **Store rclone config in Secret Manager**
   - Upload rclone.conf to Secret Manager
   - Write to temp file when needed
   - File: `backend/services/rclone_service.py` (new)

2. **Update Job model**
   ```python
   # backend/models/job.py
   organised_dir_rclone_root: Optional[str] = None
   ```

3. **Update video_worker.py** (already has the param, just wire it)
   ```python
   finalise = KaraokeFinalise(
       organised_dir_rclone_root=job.organised_dir_rclone_root,
       server_side_mode=True,
   )
   ```

4. **Update remote CLI and API**
   - Accept `--organised_dir_rclone_root` parameter
   - Store in job data

**Files to modify:**
- `backend/models/job.py` - Add rclone root field
- `backend/workers/video_worker.py` - Pass through rclone root (partial - already has it)
- `backend/services/rclone_service.py` - NEW: Config management
- `backend/api/routes/file_upload.py` - Accept rclone params
- `karaoke_gen/utils/remote_cli.py` - Parse rclone params

#### 1.3 Email Draft Creation

**Goal:** Create draft email in owner's Gmail with YouTube URL and Dropbox link.

**Current Local CLI Flow:**
```python
finalise = KaraokeFinalise(
    email_template_file="/path/to/template.txt",
)
# Uses Gmail API to create draft
# Template has placeholders: {youtube_url}, {dropbox_link}, {artist}, {title}
```

**Backend Implementation Plan:**

1. **Store Gmail OAuth credentials in Secret Manager**
   - Similar to YouTube credentials
   - File: `backend/services/gmail_service.py` (new)

2. **Update Job model**
   ```python
   # backend/models/job.py
   email_template: Optional[str] = None  # Template content
   ```

3. **Update video_worker.py**
   - After KaraokeFinalise.process(), call email draft creation
   - Use results from process() for YouTube URL and Dropbox link

4. **Update remote CLI and API**
   - Accept `--email_template_file` parameter
   - Upload template content with job

**Files to modify:**
- `backend/models/job.py` - Add email template field
- `backend/workers/video_worker.py` - Create email draft after processing
- `backend/services/gmail_service.py` - NEW: Gmail API integration
- `backend/api/routes/file_upload.py` - Accept email template
- `karaoke_gen/utils/remote_cli.py` - Parse email params

### Phase 2: Input Source Features (MEDIUM PRIORITY)

#### 2.1 YouTube URL Input

**Goal:** Accept YouTube URLs as input source (same as local CLI).

**Implementation:**
1. Add yt-dlp to backend Docker image
2. Create `backend/workers/download_worker.py`
3. Update job submission to accept URL instead of file

**Files to create/modify:**
- `backend/Dockerfile` - Add yt-dlp
- `backend/workers/download_worker.py` - NEW
- `backend/api/routes/file_upload.py` - Accept URL param
- `backend/models/job.py` - Add input_url field

### Phase 3: Advanced Features (LOW PRIORITY)

#### 3.1 Batch Processing
- Bulk job submission endpoint
- Queue management
- Progress tracking for multiple jobs

#### 3.2 Existing Instrumental Support
- Accept pre-separated instrumental file
- Skip audio separation worker

#### 3.3 Lyrics File Support
- Accept pre-existing lyrics file
- Skip transcription, go straight to review

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

### Implementation Approach

1. **Complete feature parity first** (this plan's focus)
   - Get all features working in remote mode
   - Identify all the places where logic is duplicated

2. **Extract stage interfaces**
   ```python
   class PipelineStage(Protocol):
       async def execute(self, context: PipelineContext) -> StageResult:
           ...
   ```

3. **Create execution adapters**
   ```python
   class LocalExecutor:
       """Runs stages directly in-process"""
       
   class RemoteExecutor:
       """Runs stages via backend API/workers"""
   ```

4. **Refactor incrementally**
   - Start with one stage (e.g., Separation)
   - Prove the pattern works
   - Migrate other stages

### Reference

See [STYLE-LOADER-REFACTOR.md](./STYLE-LOADER-REFACTOR.md) for details on the style loader consolidation, which was the first step toward this unified architecture.

---

## Important Files Reference

### Core Backend Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI app entry point |
| `backend/config.py` | Environment configuration |
| `backend/models/job.py` | Job data model (Firestore) |
| `backend/models/requests.py` | API request schemas |
| `backend/services/job_manager.py` | Job state management |
| `backend/services/storage_service.py` | GCS operations |
| `backend/services/worker_service.py` | Worker triggering |

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
| `backend/api/routes/file_upload.py` | Job submission endpoint |
| `backend/api/routes/jobs.py` | Job status/management |
| `backend/api/routes/review.py` | Lyrics review endpoints |
| `backend/api/routes/internal.py` | Worker callback endpoints |

### Shared Code (Used by Both Local and Backend)

| File | Purpose |
|------|---------|
| `karaoke_gen/style_loader.py` | **Unified style loading** - single source of truth |
| `karaoke_gen/karaoke_finalise/karaoke_finalise.py` | Video encoding, CDG, YouTube, Discord, email |
| `karaoke_gen/video_generator.py` | Title/end screen generation |
| `karaoke_gen/utils/cli_args.py` | Shared CLI argument definitions |

### Remote CLI

| File | Purpose |
|------|---------|
| `karaoke_gen/utils/remote_cli.py` | Remote CLI implementation |

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ backend/tests/ -v

# Backend tests only
pytest backend/tests/ -v

# Specific test files
pytest backend/tests/test_workers.py -v
pytest backend/tests/test_style_upload.py -v
```

### Key Test Files

| File | Tests |
|------|-------|
| `backend/tests/test_workers.py` | Worker functionality |
| `backend/tests/test_style_upload.py` | Style parsing and loading |
| `backend/tests/test_routes_review.py` | Review API and preview styles |
| `backend/tests/test_upload_api.py` | File upload validation |
| `tests/unit/test_karaoke_finalise/` | KaraokeFinalise tests |

---

## Deployment

### Environment Variables (Cloud Run)

```
GOOGLE_CLOUD_PROJECT=karaoke-gen
GCS_BUCKET_NAME=karaoke-gen-uploads
MODAL_API_URL=https://modal-api-url
AUDIOSHAKE_API_TOKEN=xxx
GENIUS_API_TOKEN=xxx
ADMIN_TOKEN=xxx
```

### Secret Manager Secrets (To Add)

```
youtube-oauth-credentials   # For YouTube upload
gmail-oauth-credentials     # For email draft
rclone-config              # For Dropbox sync
```

---

## Architecture Documents

- [ARCHITECTURE.md](../01-reference/ARCHITECTURE.md) - System architecture overview
- [STYLE-LOADER-REFACTOR.md](./STYLE-LOADER-REFACTOR.md) - Style loading consolidation

---

## Recent Changes Log

### 2024-12-09: Output File Parity
- Enhanced `remote_cli.py` download to match local CLI output structure
- Added screen image uploads (.jpg, .png) to screens_worker
- Added descriptive stem naming with model names
- Added CDG extraction to root directory

### 2024-12-09: Style Loader Consolidation
- Created `karaoke_gen/style_loader.py` as single source of truth
- Updated all workers to use unified style loading
- Fixed preview video custom styles bug

---

## Next Steps for New Agent

1. **Read these files first:**
   - This document (BACKEND-FEATURE-PARITY-PLAN.md)
   - `backend/workers/video_worker.py` - Main integration point
   - `karaoke_gen/karaoke_finalise/karaoke_finalise.py` - Has all distribution features
   - `backend/models/job.py` - Job data model

2. **Start with Phase 1.2 (Dropbox upload)** - Simplest to implement:
   - The `organised_dir_rclone_root` parameter already exists in KaraokeFinalise
   - The video_worker already has the parameter wired (just getting None)
   - Just need to add field to job model and pass through from API

3. **Then Phase 1.1 (YouTube upload):**
   - More complex due to OAuth credential management
   - KaraokeFinalise already supports `user_youtube_credentials` param
   - Need Secret Manager integration for credential storage

4. **Run tests before committing:**
   ```bash
   pytest tests/ backend/tests/ -v
   ```

5. **Bump version in pyproject.toml** on each commit (workspace rule)
