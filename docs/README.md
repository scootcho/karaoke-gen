# Karaoke-Gen Documentation

This directory contains all documentation for the karaoke-gen project, organized by purpose.

## 📋 Current Status (Updated: 2025-12-08)

**Project:** Cloud-hosted karaoke generation with async human review  
**Backend:** 🔄 Phase 1.3 (85%) - Implementing review architecture  
**Frontend:** ⏸️ Not started (waiting for backend review flow)  
**Deployment:** ✅ Cloud Run with custom domain (api.nomadkaraoke.com)  
**Testing:** 🔄 Local emulator testing in progress

### Key Discovery

We identified that the `LyricsTranscriber` library's `ReviewServer` **blocks** waiting for human input, which doesn't work in our async cloud architecture. The solution is to:

1. Use LyricsTranscriber for transcription + auto-correction
2. Save corrections to GCS for async human review
3. Use `OutputGenerator` to render video **after** review completes

See `00-current-plan/CURRENT-STATUS.md` for full details.

---

## 📂 Documentation Structure

### `00-current-plan/` - **START HERE**
Active migration plan and current status.

| File | Purpose |
|------|---------|
| **`CURRENT-STATUS.md`** | Where we are now, what's working, what's next |
| **`WHATS-NEXT.md`** | Detailed plan for review architecture implementation |
| **`WORKER-IMPLEMENTATION-PLAN.md`** | Worker responsibilities and implementation details |
| `MASTER-PLAN.md` | Overall migration strategy |
| `CLOUD-MIGRATION-REQUIREMENTS.md` | Architectural analysis from CLI workflow |

### `01-reference/` - Reference Documentation
Core system documentation.

| File | Purpose |
|------|---------|
| **`ARCHITECTURE.md`** | Cloud + CLI architecture with diagrams |
| `KARAOKE-GEN-CLI-WORKFLOW.md` | CLI workflow breakdown (8 stages) |
| `API-MANUAL-TESTING.md` | How to test backend API with curl |
| `AUTHENTICATION.md` | Token-based auth system |
| `CLOUD-RUN-ARCHITECTURE.md` | Cloud Run concepts |

### `02-implementation-history/` - Session Logs
Historical implementation records.

### `03-deployment/` - Deployment Guides
How to deploy and operate the system.

| File | Purpose |
|------|---------|
| **`EMULATOR-TESTING.md`** | Local testing with Firestore/GCS emulators |
| **`SETUP-VENV.md`** | Python venv setup |
| **`LOCAL-VALIDATION.md`** | Validate before deploying |
| **`OBSERVABILITY-GUIDE.md`** | Debug production issues |

### `04-testing/` - Testing Guides

| File | Purpose |
|------|---------|
| **`TESTING-GUIDE.md`** | Complete testing guide |

---

## 🚀 Quick Start

### I want to understand the current state:
1. Read `00-current-plan/CURRENT-STATUS.md` - where we are now
2. Read `00-current-plan/WHATS-NEXT.md` - what needs to be done
3. Read `01-reference/ARCHITECTURE.md` - system architecture

### I want to work on the backend:
1. Read `03-deployment/EMULATOR-TESTING.md` - local testing setup
2. Read `00-current-plan/WORKER-IMPLEMENTATION-PLAN.md` - worker details
3. Run `./scripts/run-backend-local.sh --with-emulators`

### I want to test:
```bash
# Start backend with emulators
./scripts/run-backend-local.sh --with-emulators

# Upload test file
curl -X POST http://localhost:8000/api/jobs/upload \
  -F "file=@tests/data/waterloo10sec.flac" \
  -F "artist=ABBA" \
  -F "title=Waterloo"

# Check status
curl http://localhost:8000/api/jobs/{job_id}
```

---

## 🎯 Current Phase: Review Architecture

**Goal:** Implement async human review workflow

**What Works:**
- ✅ File upload → GCS
- ✅ Audio separation via Modal API
- ✅ Lyrics transcription via AudioShake
- ✅ Auto-correction via LyricsTranscriber
- ✅ Title/end screen generation
- ✅ Instrumental selection endpoint

**What's Being Implemented:**
- 🔄 Review API endpoints (`GET/POST /api/jobs/{id}/review`)
- 🔄 Render Video Worker (uses `OutputGenerator` after review)
- 🔄 Updated state machine with `RENDERING_VIDEO` state

**The Key Insight:**
```
WRONG: Lyrics Worker → Generate Video → Review → ???
RIGHT: Lyrics Worker → Save JSON → Human Review → Render Video → Final Assembly
```

Video generation happens AFTER human review, not during the lyrics worker.

---

## 📝 Key Technical Decisions

### Why Not Use LyricsTranscriber's ReviewServer?

The `ReviewServer` class (in `lyrics_transcriber/review/server.py`):
- Starts a local web server on port 8000
- Opens a browser window
- **BLOCKS** the thread until human submits corrections
- Designed for local CLI operation

This doesn't work in Cloud Run where:
- We can't open browsers
- Workers must be non-blocking
- Human review happens asynchronously via React frontend

**Solution:** Use the data structures and `OutputGenerator` directly, skip the server.

### Why Separate Video Rendering?

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Lyrics Worker  │ ──▶ │ Human Reviews   │ ──▶ │ Render Worker   │
│                 │     │ (React UI)      │     │                 │
│ • Transcribe    │     │ • Corrects      │     │ • OutputGenerator│
│ • Auto-correct  │     │ • Saves JSON    │     │ • with_vocals.mkv│
│ • Save JSON     │     │                 │     │                 │
│ • NO VIDEO      │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

The video must include the human-corrected lyrics, so it can only be generated AFTER review.

---

## 🔄 Job State Flow

```
PENDING → DOWNLOADING → [parallel audio+lyrics] → GENERATING_SCREENS
    ↓
AWAITING_REVIEW → IN_REVIEW → REVIEW_COMPLETE
    ↓
RENDERING_VIDEO (NEW)
    ↓
AWAITING_INSTRUMENTAL_SELECTION → INSTRUMENTAL_SELECTED
    ↓
GENERATING_VIDEO → COMPLETE
```

Two human interaction points:
1. **AWAITING_REVIEW** - User corrects lyrics
2. **AWAITING_INSTRUMENTAL_SELECTION** - User chooses audio track

---

## 📞 Getting Help

1. Check `00-current-plan/CURRENT-STATUS.md` first
2. Look for specific guides in `03-deployment/`
3. Review session history in `02-implementation-history/`

### Common Issues

| Issue | Solution |
|-------|----------|
| Emulator not starting | Check ports 8080, 4443 are free |
| "Missing lyrics video" | Review hasn't happened yet - expected behavior |
| Workers not progressing | Check `state_data` in Firestore |
| FFmpeg errors | Ensure FFmpeg is in PATH |
