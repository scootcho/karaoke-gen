# What's Next: Testing Phase 1.3

**Current Status:** Phase 1.3 video generation worker is implemented but **untested**.

**Your Next Actions:** You have 2 options depending on what you want to do.

---

## Option A: Deploy & Test End-to-End (Recommended)

This will test the entire workflow with real audio processing.

### Step 1: Deploy Updated Backend to Cloud Run

The backend code is ready, but needs to be deployed:

```bash
# From project root
cd /Users/andrew/Projects/karaoke-gen

# Build and push new Docker image (with video worker)
gcloud builds submit --config cloudbuild.yaml

# This will:
# 1. Build new Docker image with video worker
# 2. Push to Artifact Registry
# 3. Cloud Run will automatically deploy latest image
```

**Time:** ~5-10 minutes

### Step 2: Test with Real Audio File

Use the backend API to submit a test job:

```bash
# Set your Cloud Run URL
BACKEND_URL="https://karaoke-backend-<hash>-uc.a.run.app"

# Submit a job with a short song (use waterloo30sec.flac for quick test)
curl -X POST "$BACKEND_URL/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=Sj_9CiNkkn4",
    "artist": "ABBA",
    "title": "Waterloo"
  }'

# Note the job_id from response
JOB_ID="<job_id_from_response>"

# Monitor progress (run this multiple times or use watch)
curl "$BACKEND_URL/api/jobs/$JOB_ID" | jq '{status, progress, message}'

# Or use watch to monitor continuously
watch -n 5 "curl -s $BACKEND_URL/api/jobs/$JOB_ID | jq '{status, progress, message}'"
```

**Expected Timeline:**
- Download: 1-2 min
- Audio separation: 5-8 min (2 stages)
- Lyrics transcription: 2-3 min (parallel with audio)
- Screens generation: 30 sec
- **AWAITING_REVIEW** ⚠️ (you need to review lyrics)
- **AWAITING_INSTRUMENTAL_SELECTION** ⚠️ (you need to select)
- Video encoding: 15-20 min
- **COMPLETE** ✅

**Total:** ~30-45 minutes (including your interaction time)

### Step 3: Interact at Human Checkpoints

#### A. Review Lyrics (when status = AWAITING_REVIEW)

```bash
# Get review data
curl "$BACKEND_URL/api/jobs/$JOB_ID/review-data" | jq .

# Start review
curl -X POST "$BACKEND_URL/api/jobs/$JOB_ID/start-review"

# Submit corrections (or just accept as-is)
curl -X POST "$BACKEND_URL/api/jobs/$JOB_ID/corrections" \
  -H "Content-Type: application/json" \
  -d '{
    "corrected_lyrics_json": {}
  }'
```

#### B. Select Instrumental (when status = AWAITING_INSTRUMENTAL_SELECTION)

```bash
# Get instrumental options
curl "$BACKEND_URL/api/jobs/$JOB_ID/instrumental-options" | jq .

# Select instrumental (clean or with_backing)
curl -X POST "$BACKEND_URL/api/jobs/$JOB_ID/select-instrumental" \
  -H "Content-Type: application/json" \
  -d '{"selection": "clean"}'
```

### Step 4: Download Final Videos (when status = COMPLETE)

```bash
# Get all download URLs
curl "$BACKEND_URL/api/jobs/$JOB_ID" | jq '.file_urls.finals'

# Download a format (URLs are signed, valid for 2 hours)
curl -o lossless_4k.mp4 "<signed_url_from_above>"
```

**Expected Output:**
- 4 video files (lossless 4K MP4/MKV, lossy 4K, 720p)
- Optional: CDG and TXT packages if enabled

---

## Option B: Local Development Testing (If You Want to Debug First)

If you want to test locally before deploying:

### Step 1: Set Up Local Environment

```bash
cd /Users/andrew/Projects/karaoke-gen/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e ..  # Install karaoke_gen package

# Set environment variables
export GOOGLE_CLOUD_PROJECT="nomadkaraoke"
export GCS_UPLOAD_BUCKET="karaoke-uploads"
export ENVIRONMENT="development"

# Add API keys (these should be in Secret Manager already)
export AUDIOSHAKE_API_TOKEN="<your-token>"
export GENIUS_API_TOKEN="<your-token>"
export AUDIO_SEPARATOR_API_URL="https://nomadkaraoke--audio-separator-api.modal.run"
```

### Step 2: Run Backend Locally

```bash
# From backend directory
uvicorn backend.main:app --reload --port 8080
```

### Step 3: Test with Local Requests

Use the same curl commands from Option A, but with:
```bash
BACKEND_URL="http://localhost:8080"
```

**Note:** This requires:
- Google Cloud credentials configured locally
- Access to Firestore and GCS
- API keys for external services

---

## What Will Happen During Testing?

### Success Indicators ✅

1. **Job Creation:** Status transitions to `DOWNLOADING`
2. **Parallel Processing:** Both audio and lyrics workers start
3. **Audio Complete:** Status reaches `AUDIO_COMPLETE` with all stems in GCS
4. **Lyrics Complete:** Status reaches `LYRICS_COMPLETE` with corrections JSON
5. **Screens Generated:** Title and end screens created
6. **Human Checkpoints Work:** You can review/correct lyrics and select instrumental
7. **Video Generation:** All 4 formats encode successfully
8. **Completion:** Status = `COMPLETE` with all files downloadable

### Potential Issues 🐛

**If something fails, check:**

1. **Worker Logs:**
   ```bash
   # Cloud Run logs
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend" --limit 50 --format json
   ```

2. **Firestore Job State:**
   - Check job document in Firestore console
   - Look at `status`, `error_message`, `error_details`

3. **GCS Files:**
   - Check if files are being uploaded
   - Verify file permissions

**Common Issues:**
- **Secret Manager:** API keys not configured → Set secrets in GCP console
- **Permissions:** Service account lacks roles → Check IAM
- **Audio Separator:** Modal API down → Check Modal status
- **FFmpeg:** Not found → Already in Docker, should work
- **Memory:** Out of memory → Increase Cloud Run memory

---

## My Recommendation

**Do Option A (Deploy & Test End-to-End)** because:

1. ✅ **Realistic environment** - Tests actual production setup
2. ✅ **GPU access** - Modal API for audio separation
3. ✅ **GCS storage** - Real cloud storage
4. ✅ **Firestore** - Real database
5. ✅ **Easier debugging** - Cloud Run logs are comprehensive

**Time Investment:** ~1 hour total
- 5 min: Deploy
- 5 min: Submit job and set up monitoring
- 30-45 min: Wait and interact at checkpoints
- 10 min: Verify outputs

---

## What I'll Do

I can help with:

1. **Monitoring:** I can parse logs if issues occur
2. **Debugging:** If something fails, I'll investigate
3. **Bug Fixes:** If issues found, I'll fix them immediately
4. **Documentation:** Update docs based on testing results

---

## After Testing

Once testing succeeds, we'll:

1. ✅ Mark Phase 1.3 as 100% complete
2. 📝 Document any issues found and fixed
3. 🎯 **Decision Point:** Do we continue to Phase 2 (React Frontend) or add optional features first?

Optional features to consider:
- Cloud Build for faster encoding (20 min → 5-10 min)
- Countdown padding application
- Distribution worker (YouTube upload, notifications)

But honestly, **React Frontend (Phase 2)** is probably more valuable at this point since the backend is nearly feature-complete!

---

## Ready to Proceed?

**Just tell me:**
- "Deploy and test" → I'll guide you through deployment commands
- "Test locally first" → I'll help set up local environment
- "Wait, I have questions" → Ask away!

**My Recommendation:** Deploy and test end-to-end. It's the fastest path to validation! 🚀

