# Current Project Status

**Last Updated:** 2025-12-08  
**Phase:** 1.3 - Workers & Human Review Integration (85% complete)

---

## 🎯 Overall Progress

```
Phase 1.1: Backend Foundation       ✅ 100% Complete
Phase 1.2: Async Job Processing     ✅ 100% Complete  
Phase 1.3: Workers Implementation   🔄  85% Complete (review architecture fix needed)
Phase 1.4: End-to-End Testing       🔄  50% Started (local emulator testing)
Phase 2.0: Frontend (React)         ⏳   0% Not started
```

---

## 🔑 Key Architectural Discovery

### LyricsTranscriber Review Process

During local testing, we discovered a critical architectural mismatch:

**The Problem:**
- The `LyricsTranscriber` library has a built-in `ReviewServer` (see `lyrics_transcriber/review/server.py`)
- This server is designed for **local CLI operation** - it **blocks** waiting for human review
- The server starts on port 8000, opens a browser, and waits for `/api/complete` to be called
- This blocking model is **incompatible** with our async Cloud Run architecture

**The Solution:**
- **Do NOT use** the `ReviewServer` class from LyricsTranscriber
- **DO use** the data structures: `CorrectionResult`, `CorrectionOperations`, `OutputGenerator`
- Build **separate backend API endpoints** for async review workflow
- Generate video **after** review using `OutputGenerator`

See `WHATS-NEXT.md` for the full architectural solution.

---

## ✅ What's Working

### Infrastructure
- ✅ Google Cloud Run deployment (Cloud)
- ✅ Local development with Firestore/GCS emulators
- ✅ Pulumi infrastructure as code
- ✅ Cloud Build automatic deployment
- ✅ Custom domain (api.nomadkaraoke.com)
- ✅ SSL certificate (Google-managed)
- ✅ Firestore database
- ✅ Cloud Storage buckets
- ✅ Secret Manager integration

### Backend API
- ✅ FastAPI application
- ✅ Health endpoint
- ✅ Job creation endpoint
- ✅ Job status endpoint
- ✅ File upload endpoint
- ✅ Internal worker trigger endpoints
- ✅ Instrumental selection endpoint
- ✅ Token-based authentication system

### Workers (Implemented but need review flow fix)
- ✅ Audio worker (stem separation via Modal API)
- ✅ Lyrics worker (transcription via AudioShake API)
- ✅ Screens worker (title/end screen generation)
- 🔄 Video worker (needs review flow integration)

### State Management
- ✅ 21-state job state machine
- ✅ Job timeline tracking
- ✅ Progress tracking via `state_data`
- ✅ Error handling with detailed messages

### Local Testing
- ✅ Firestore emulator integration
- ✅ GCS emulator integration
- ✅ `./scripts/run-backend-local.sh --with-emulators`
- ✅ Can upload files and trigger workers

---

## 🔄 Current Issue: Review Architecture

### What Needs to Change

```
CURRENT (BROKEN):                    TARGET (CORRECT):
─────────────────────                ─────────────────────
Lyrics Worker                        Lyrics Worker
├── Transcribe                       ├── Transcribe
├── Auto-correct                     ├── Auto-correct  
├── Generate video ❌                ├── Save corrections.json ✓
└── Upload                           └── → AWAITING_REVIEW
                                            │
                                     Human Review (React UI)
                                     ├── Load corrections
                                     ├── Edit/correct
                                     └── Save → REVIEW_COMPLETE
                                            │
                                     Render Video Worker (NEW)
                                     ├── Use OutputGenerator
                                     ├── Generate with_vocals.mkv
                                     └── → AWAITING_INSTRUMENTAL
                                            │
                                     Video Worker (Final)
                                     ├── Select instrumental
                                     ├── Remux + concatenate
                                     └── → COMPLETE
```

### Missing Pieces

1. **Review API Endpoints** - Need to add:
   - `GET /api/jobs/{job_id}/review` - Get correction data + audio URL
   - `POST /api/jobs/{job_id}/review` - Save updated corrections
   - `POST /api/jobs/{job_id}/complete-review` - Trigger video render

2. **Render Video Worker** - New worker that:
   - Downloads corrected lyrics from GCS
   - Uses `OutputGenerator` to create karaoke video
   - Uploads `with_vocals.mkv` to GCS
   - Transitions to `AWAITING_INSTRUMENTAL_SELECTION`

3. **State Machine Update** - Need transitions:
   - `AWAITING_REVIEW` → `REVIEW_COMPLETE` (after human submits)
   - `REVIEW_COMPLETE` → `RENDERING_VIDEO` (new state)
   - `RENDERING_VIDEO` → `AWAITING_INSTRUMENTAL_SELECTION`

---

## 📊 Test Results (Local Emulators)

### Latest Test Run

```
✅ File upload: Success
✅ Audio worker: Separates stems via Modal API
✅ Lyrics worker: Transcribes via AudioShake, saves corrections.json
✅ Screens worker: Generates title/end screens
❌ Video worker: Fails - "Missing lyrics video"
   └── Root cause: No video generated because review hasn't happened
```

### Understanding

The video worker expects a `with_vocals.mkv` file, but:
1. The lyrics worker doesn't generate video (correctly - review hasn't happened)
2. There's no worker to generate video AFTER review
3. We need to add the "Render Video Worker" to bridge this gap

---

## 🏗️ Architecture: Cloud vs LyricsTranscriber

### LyricsTranscriber (CLI Mode)

```python
# This BLOCKS waiting for human input
from lyrics_transcriber.review.server import ReviewServer

server = ReviewServer(correction_result, config, audio_path, logger)
corrected_result = server.start()  # ❌ BLOCKS HERE until browser submits
# Then continues to video generation
```

### Cloud Backend (Async Mode)

```python
# Our approach - NO BLOCKING
async def lyrics_worker(job_id):
    # 1. Transcribe
    result = transcriber.transcribe(audio_path)
    
    # 2. Auto-correct
    corrections = corrector.correct(result)
    
    # 3. Save for human review (NO VIDEO YET)
    upload_to_gcs(f"jobs/{job_id}/corrections.json", corrections.to_dict())
    upload_to_gcs(f"jobs/{job_id}/audio.flac", audio_path)
    
    # 4. Transition and STOP
    job_manager.transition_to_state(job_id, JobStatus.AWAITING_REVIEW)
    # Worker exits - human will review via React UI

async def render_video_worker(job_id):  # NEW - called after review
    # 1. Download corrected data
    corrections = download_from_gcs(f"jobs/{job_id}/corrections_updated.json")
    correction_result = CorrectionResult.from_dict(corrections)
    
    # 2. Use OutputGenerator to render video
    output_generator = OutputGenerator(config, logger)
    outputs = output_generator.generate_outputs(
        transcription_corrected=correction_result,
        lyrics_results={},
        output_prefix=f"{artist} - {title}",
        audio_filepath=audio_path
    )
    
    # 3. Upload and continue
    upload_to_gcs(f"jobs/{job_id}/videos/with_vocals.mkv", outputs.video)
    job_manager.transition_to_state(job_id, JobStatus.AWAITING_INSTRUMENTAL_SELECTION)
```

---

## 📈 Performance Metrics

### Build Times
- **Before optimization:** 15-20 minutes
- **After Docker caching:** 2-3 minutes

### API Response Times
- **Health endpoint:** <50ms
- **Job creation:** <200ms
- **Job status:** <100ms
- **File upload:** ~300ms + file size

### Processing Times (Expected)
- **Audio separation:** 5-8 minutes (Modal API)
- **Lyrics transcription:** 2-3 minutes (AudioShake API)
- **Screens generation:** 30 seconds
- **Human review:** 5-15 minutes (user-dependent)
- **Video rendering:** 10-15 minutes
- **Final encoding:** 5-10 minutes
- **Total:** 30-50 minutes (including human interaction)

---

## 🚀 Next Steps

### Immediate (Current Session)
1. ✅ Document the review architecture issue
2. ⏭️ Add review API endpoints
3. ⏭️ Create render video worker
4. ⏭️ Update state machine
5. ⏭️ Test end-to-end with local emulators

### Short Term (Next Session)
1. ⏳ Test full workflow with real song
2. ⏳ Build React review UI (can use LyricsTranscriber components)
3. ⏳ Deploy to Cloud Run for production test

### Medium Term (Next Week)
1. ⏳ React frontend for full workflow
2. ⏳ Email notifications for review ready
3. ⏳ Error recovery and retry logic

---

## 📝 Key Documentation Files

| File | Purpose |
|------|---------|
| `WHATS-NEXT.md` | Detailed plan for review architecture fix |
| `WORKER-IMPLEMENTATION-PLAN.md` | Updated worker responsibilities |
| `ARCHITECTURE.md` | Cloud architecture with review flow |
| `../04-testing/TESTING-GUIDE.md` | Local testing with emulators |

---

## 🔗 Quick Reference

### Run Local Tests
```bash
# Start backend with emulators
./scripts/run-backend-local.sh --with-emulators

# Upload test file
curl -X POST http://localhost:8000/api/jobs/upload \
  -F "file=@tests/data/waterloo10sec.flac" \
  -F "artist=ABBA" \
  -F "title=Waterloo"

# Check job status
curl http://localhost:8000/api/jobs/{job_id}

# Select instrumental (when AWAITING_INSTRUMENTAL_SELECTION)
curl -X POST http://localhost:8000/api/jobs/{job_id}/select-instrumental \
  -H "Content-Type: application/json" \
  -d '{"selection": "clean"}'
```

### Key Endpoints
- `GET /api/health` - Health check
- `POST /api/jobs/upload` - Upload file and create job
- `GET /api/jobs/{job_id}` - Get job status
- `GET /api/jobs/{job_id}/review` - Get review data (TODO)
- `POST /api/jobs/{job_id}/review` - Submit corrections (TODO)
- `POST /api/jobs/{job_id}/complete-review` - Finish review (TODO)
- `POST /api/jobs/{job_id}/select-instrumental` - Choose instrumental

---

## Summary

**We discovered a key architectural issue:** The LyricsTranscriber library's review server blocks waiting for human input, which doesn't work in our async cloud architecture.

**The fix:** Separate video generation into a post-review step:
1. Lyrics worker → transcribe + auto-correct → save corrections → AWAITING_REVIEW
2. Human reviews via React UI → submits corrections → REVIEW_COMPLETE
3. **New** render video worker → generates with_vocals.mkv → AWAITING_INSTRUMENTAL
4. Human selects instrumental → INSTRUMENTAL_SELECTED
5. Video worker → final assembly → COMPLETE

This is a clean separation that uses LyricsTranscriber as a library without its blocking review server.
