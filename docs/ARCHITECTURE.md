# Architecture

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (Cloudflare Pages)                                    │
│  Next.js + TypeScript                                           │
│  https://gen.nomadkaraoke.com                                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend API (Cloud Run)                                        │
│  FastAPI + Python 3.12                                          │
│  https://api.nomadkaraoke.com                                   │
│                                                                 │
│  Workers:                                                       │
│  • Audio Worker    - Stem separation via Modal API              │
│  • Lyrics Worker   - Transcription via AudioShake               │
│  • Screens Worker  - Title/end screen generation                │
│  • Render Worker   - Karaoke video with lyrics                  │
│  • Video Worker    - Final assembly and encoding                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┬───────────────┐
              ▼             ▼             ▼               ▼
        ┌──────────┐  ┌──────────┐  ┌──────────────┐ ┌──────────────┐
        │ Firestore│  │   GCS    │  │Secret Manager│ │GCE Encoding  │
        │ (jobs)   │  │ (files)  │  │  (API keys)  │ │  Worker (*)  │
        └──────────┘  └──────────┘  └──────────────┘ └──────────────┘

(*) GCE Encoding Worker: C4-standard-8 VM with Intel Granite Rapids for
    high-performance FFmpeg encoding. Optional - falls back to Cloud Run.
```

## Processing Pipeline

```text
1. UPLOAD
   POST /api/jobs/upload
   • Save audio to GCS
   • Create job in Firestore
   • Trigger parallel workers

2. PARALLEL PROCESSING
   ┌─────────────────┐    ┌─────────────────┐
   │  Audio Worker   │    │  Lyrics Worker  │
   │  Modal API      │    │  AudioShake     │
   │  2-stage sep    │    │  Auto-correct   │
   └────────┬────────┘    └────────┬────────┘
            └──────────┬───────────┘
                       ▼
3. SCREENS GENERATION
   • Title screen (5s video)
   • End screen (5s video)
                       ▼
4. HUMAN REVIEW (AWAITING_REVIEW)
   • React UI for lyrics correction
   • Preview video generation
   • Submit corrections
                       ▼
5. VIDEO RENDERING
   • Merge corrections with original data
   • Generate karaoke video with lyrics
                       ▼
6. INSTRUMENTAL SELECTION
   • User chooses: clean or with_backing
                       ▼
7. FINAL VIDEO
   • Remux with selected instrumental
   • Concatenate: title + karaoke + end
   • Encode to 4 formats
                       ▼
8. COMPLETE
   • User downloads via signed URLs
```

## Job States

| State | Description | Human Action |
|-------|-------------|--------------|
| `pending` | Job created | - |
| `downloading` | Processing audio | - |
| `separating_stage1` | Audio separation stage 1 | - |
| `separating_stage2` | Audio separation stage 2 | - |
| `transcribing` | Lyrics transcription | - |
| `generating_screens` | Creating title/end screens | - |
| `awaiting_review` | **Waiting for human** | Review lyrics |
| `in_review` | Human actively reviewing | Edit lyrics |
| `review_complete` | Review submitted | - |
| `rendering_video` | Generating karaoke video | - |
| `awaiting_instrumental_selection` | **Waiting for human** | Choose audio |
| `instrumental_selected` | Selection made | - |
| `generating_video` | Final encoding | - |
| `complete` | All done | Download files |
| `failed` | Error occurred | - |

## GCS File Structure

```text
jobs/{job_id}/
├── input/
│   └── original.flac              # Uploaded audio
├── stems/
│   ├── vocals.flac
│   ├── instrumental_clean.flac
│   ├── instrumental_with_backing.flac
│   └── ...
├── lyrics/
│   ├── corrections.json           # Auto-corrected
│   ├── corrections_updated.json   # After human review
│   └── karaoke.ass
├── screens/
│   ├── title.mov
│   └── end.mov
├── videos/
│   └── with_vocals.mkv            # Karaoke video
└── finals/
    ├── lossless_4k.mp4
    ├── lossless_4k.mkv
    ├── lossy_4k.mp4
    └── lossy_720p.mp4
```

## LyricsTranscriber Integration

**Key Design Decision**: We use LyricsTranscriber as a **library**, not a server.

```text
CLI Mode (Original):              Cloud Mode (Our Approach):
────────────────────              ──────────────────────────
LyricsTranscriber                 LyricsTranscriber
├── transcribe()                  ├── transcribe()    ✅
├── correct()                     ├── correct()       ✅
├── ReviewServer.start()          │
│   └── BLOCKS (waits)            │  (Skip server, save JSON)
│                                 │  ... ASYNC GAP ...
│                                 │  (Human reviews via React)
└── OutputGenerator               │
                                  └── OutputGenerator  ✅
                                      (called after review)
```

**Use**: `LyricsTranscriber`, `CorrectionResult`, `OutputGenerator`, `OutputConfig`
**Don't use**: `ReviewServer`, blocking waits

## External Services

| Service | Purpose | Required |
|---------|---------|----------|
| Modal | GPU audio separation | Yes |
| AudioShake | Lyrics transcription | Yes |
| Vertex AI | Agentic AI correction (Gemini 3 Flash) | Default on |
| Genius | Reference lyrics | Yes |
| YouTube API | Video upload | Optional |

## Firestore Collections

karaoke-gen shares a GCP project (`nomadkaraoke`) with karaoke-decide, but uses separate Firestore collections:

| Collection | Purpose | Key Fields |
|------------|---------|------------|
| `gen_users` | karaoke-gen user accounts | email, credits, role, is_active |
| `jobs` | Karaoke generation jobs | job_id, user_email, status, state_data |
| `sessions` | Magic link auth sessions | user_email, token, expires_at |
| `magic_links` | Passwordless auth tokens | email, token, expires_at, used |
| `beta_feedback` | Beta program feedback | user_email, ratings, comments |

**Note**: The `users` collection in the same Firestore instance belongs to karaoke-decide (different schema: user_id, is_guest, quiz_* fields). Don't use it for karaoke-gen.

## Video Worker Orchestrator

The Video Worker uses an orchestrator pattern to ensure all features work regardless of encoding backend (local Cloud Run or GCE VM).

```text
┌─────────────────────────────────────────────────────────────┐
│                 VideoWorkerOrchestrator                      │
│                                                             │
│  Stage 1: PACKAGING        Stage 2: ENCODING                │
│  ├─ CDG file generation    ├─ Local (FFmpeg)               │
│  └─ TXT lyrics export      └─ GCE (remote VM)              │
│                                                             │
│  Stage 3: ORGANIZATION     Stage 4: DISTRIBUTION           │
│  ├─ Final path setup       ├─ Dropbox upload               │
│  └─ File organization      ├─ Google Drive upload          │
│                            └─ YouTube upload               │
│                                                             │
│  Stage 5: NOTIFICATIONS                                     │
│  └─ Discord webhooks                                        │
└─────────────────────────────────────────────────────────────┘
```

**Key Design Decision**: The orchestrator coordinates stages rather than embedding logic in monolithic functions. This:
- Ensures all features work with both local and GCE encoding
- Makes each stage independently testable (139 new tests)
- Allows feature flag rollback via `USE_NEW_ORCHESTRATOR` env var

**Service Modules**:
| Module | Purpose |
|--------|---------|
| `youtube_upload_service.py` | YouTube OAuth flow and upload |
| `discord_service.py` | Discord webhook notifications |
| `packaging_service.py` | CDG/TXT package generation |
| `local_encoding_service.py` | FFmpeg encoding (Cloud Run) |
| `encoding_interface.py` | Abstract interface + GCE backend |
| `video_worker_orchestrator.py` | Stage coordination |

## Tech Stack

- **Backend**: FastAPI, Python 3.12, Cloud Run
- **Frontend**: Next.js, TypeScript, Cloudflare Pages
- **Database**: Firestore
- **Storage**: Google Cloud Storage
- **Secrets**: Google Secret Manager
- **IaC**: Pulumi
- **CI/CD**: GitHub Actions
