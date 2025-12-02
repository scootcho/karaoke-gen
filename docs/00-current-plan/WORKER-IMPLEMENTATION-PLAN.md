# Worker Implementation Plan - Making the Backend Actually Work

**Date**: December 2, 2025  
**Status**: Planning phase  
**Goal**: Implement actual karaoke generation functionality in Cloud Run backend

---

## Problem Statement

The current workers are stubbed out because they were trying to use `karaoke_gen` library classes (`AudioProcessor`, `LyricsProcessor`) which are **CLI-oriented** with incompatible signatures designed for local disk operations and synchronous workflows.

However, the **actual processing logic** in `karaoke_gen` calls **remote APIs** that we can use directly from Cloud Run:
- ✅ **Audio separation**: Already calls Modal API remotely
- ✅ **Lyrics transcription**: Already calls AudioShake API remotely
- ✅ **Lyrics correction**: Uses `lyrics_transcriber` library (which we have in `lyrics_transcriber_local/`)

**We don't need to refactor `karaoke_gen` - we need to call the same APIs it calls, adapted for our async Cloud Run workflow.**

---

## Architecture Overview

### Current CLI Flow (Synchronous)
```
CLI → AudioProcessor (local disk) → Modal API → Download stems → Local processing
CLI → LyricsProcessor (local disk) → AudioShake API → Review server (port 8000) → WAIT FOR HUMAN
```

### Target Cloud Flow (Asynchronous)
```
API → Audio Worker → Modal API → Upload to GCS → Update Firestore
API → Lyrics Worker → AudioShake API → Upload to GCS → Transition to AWAITING_REVIEW
User → Review UI (React) → Submit corrections → API → Video Worker
```

---

## Phase 1: Audio Worker (Real Implementation)

### What It Actually Needs to Do

Based on `karaoke_gen/audio_processor.py`, the audio separation:
1. **Calls Modal API** for stem separation (already implemented in `karaoke_gen`)
2. **Downloads stems** from Modal's response
3. **Normalizes audio** levels
4. **Generates combined instrumentals** (clean + with backing vocals)

### Implementation Strategy

**Option A: Use `karaoke_gen.audio_processor.AudioProcessor` Properly**

Looking at the actual code, `AudioProcessor` **does work with remote APIs** - we just need to provide the right parameters:

```python
# From karaoke_gen/audio_processor.py __init__
def __init__(
    self,
    logger,
    log_level,
    log_formatter,
    model_file_dir,  # Can be None for remote API
    lossless_output_format,
    clean_instrumental_model,
    backing_vocals_models,
    other_stems_models,
    # ... more params
):
```

**Key insight**: We need to provide ALL the parameters from the CLI's config, but we can use:
- `model_file_dir=None` (not needed for remote API)
- Set `AUDIO_SEPARATOR_API_URL` environment variable
- Provide all the model names from config

**Option B: Call Modal API Directly**

Extract the Modal API calling logic from `AudioProcessor` and call it directly:

```python
from audio_separator.remote import AudioSeparatorAPIClient

async def separate_audio_via_modal(audio_path: str, models: list):
    client = AudioSeparatorAPIClient(
        api_url=os.environ["AUDIO_SEPARATOR_API_URL"]
    )
    
    # Stage 1: Clean instrumental
    job_id = await client.separate(
        audio_file=audio_path,
        model_name="model_bs_roformer_ep_317_sdr_12.9755.ckpt"
    )
    
    # Poll for completion
    while True:
        status = await client.get_status(job_id)
        if status["state"] == "complete":
            break
        await asyncio.sleep(15)
    
    # Download stems
    stems = await client.download_stems(job_id)
    return stems
```

### Recommended Approach: **Option B (Direct Modal API)**

**Why:**
- ✅ Full control over async flow
- ✅ No dependency on CLI-specific config
- ✅ Can adapt to Cloud Run environment
- ✅ Cleaner error handling
- ✅ Can store progress in Firestore

**Implementation Steps:**

1. **Install/import audio-separator library** with remote support
2. **Extract Modal API client code** from `karaoke_gen/audio_processor.py`
3. **Implement separation with GCS integration:**
   ```python
   async def process_audio_separation(job_id: str):
       # Download audio from GCS
       audio_path = await download_from_gcs(job.input_media_gcs_path)
       
       # Separate via Modal (Stage 1: Clean instrumental)
       stems_stage1 = await separate_via_modal(
           audio_path=audio_path,
           models=["model_bs_roformer_ep_317_sdr_12.9755.ckpt", "htdemucs_6s.yaml"]
       )
       
       # Upload stems to GCS
       await upload_stems_to_gcs(job_id, stems_stage1)
       
       # Separate via Modal (Stage 2: Backing vocals)
       vocals_path = stems_stage1["vocals"]
       stems_stage2 = await separate_via_modal(
           audio_path=vocals_path,
           models=["mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"]
       )
       
       # Upload stage 2 stems
       await upload_stems_to_gcs(job_id, stems_stage2)
       
       # Generate combined instrumentals (instrumental + backing vocals)
       instrumental_with_bv = await combine_stems(
           instrumental=stems_stage1["instrumental"],
           backing_vocals=stems_stage2["backing_vocals"]
       )
       
       # Upload final instrumentals
       await upload_instrumental_to_gcs(job_id, {
           "clean": stems_stage1["instrumental"],
           "with_backing": instrumental_with_bv
       })
       
       # Mark complete
       job_manager.mark_audio_complete(job_id)
   ```

4. **Handle progress updates:**
   ```python
   # Update Firestore during processing
   job_manager.transition_to_state(
       job_id=job_id,
       new_status=JobStatus.SEPARATING_STAGE1,
       progress=25,
       message="Separating audio (Stage 1/2)"
   )
   ```

---

## Phase 2: Lyrics Worker (Real Implementation)

### What It Actually Needs to Do

Based on `karaoke_gen/lyrics_processor.py`:

1. **Fetch reference lyrics** from Genius/Spotify/Musixmatch
2. **Transcribe audio** via AudioShake API
3. **Run automatic correction** using `lyrics_transcriber` library
4. **Generate corrections JSON** for human review
5. **Upload for review** → Transition to `AWAITING_REVIEW`

### Implementation Strategy

**The lyrics_transcriber library is already available** in `lyrics_transcriber_local/` submodule!

```python
from lyrics_transcriber.transcriber import LyricsTranscriber

async def process_lyrics_transcription(job_id: str):
    # 1. Download audio from GCS
    audio_path = await download_from_gcs(job.input_media_gcs_path)
    
    # 2. Fetch reference lyrics
    reference_lyrics = await fetch_lyrics_from_apis(
        artist=job.artist,
        title=job.title
    )
    
    # 3. Transcribe via AudioShake
    transcription = await transcribe_via_audioshake(audio_path)
    
    # 4. Run automatic correction
    transcriber = LyricsTranscriber()
    correction_result = await transcriber.correct_lyrics(
        transcription=transcription,
        reference_lyrics=reference_lyrics
    )
    
    # 5. Generate preview video (for review UI)
    preview_video = await generate_preview_video(
        audio_path=audio_path,
        corrections=correction_result
    )
    
    # 6. Upload corrections and preview to GCS
    corrections_url = await upload_to_gcs(
        f"jobs/{job_id}/corrections.json",
        correction_result.to_json()
    )
    preview_url = await upload_to_gcs(
        f"jobs/{job_id}/preview.mp4",
        preview_video
    )
    
    # 7. Transition to AWAITING_REVIEW
    job_manager.transition_to_state(
        job_id=job_id,
        new_status=JobStatus.AWAITING_REVIEW,
        progress=50,
        message="Ready for lyrics review"
    )
    
    # 8. TODO: Send email notification with review URL
    # await send_email_notification(job)
```

### Key Dependencies

1. **AudioShake API client** - Extract from `karaoke_gen` or implement directly
2. **Lyrics APIs** - Genius, Spotify (via RapidAPI), Musixmatch
3. **lyrics_transcriber library** - Already in submodule
4. **FFmpeg** - For preview video generation

---

## Phase 3: Human Interaction - Lyrics Review

### Current State
- ❌ No review UI deployed
- ❌ No corrections submission endpoint

### What Needs to Happen

1. **React Review UI** (separate frontend):
   ```
   Frontend repo: TBD
   URL: https://gen.nomadkaraoke.com/review/{job_id}
   ```

2. **API Endpoint for Corrections Submission**:
   ```python
   @app.post("/api/jobs/{job_id}/corrections")
   async def submit_corrections(
       job_id: str,
       corrections: CorrectionResult
   ):
       # Validate corrections
       # Update job in Firestore
       # Trigger screens worker
       return {"status": "accepted"}
   ```

3. **Email Notification** when review is ready:
   ```python
   await send_email(
       to=job.user_email,
       subject=f"Review ready: {job.artist} - {job.title}",
       body=f"Review at: https://gen.nomadkaraoke.com/review/{job_id}"
   )
   ```

---

## Phase 4: Screens Worker

### What It Does

Generate title and end screens using the style parameters from the job.

Based on `karaoke_gen/video_generator.py`:

```python
from karaoke_gen.video_generator import VideoGenerator

async def generate_screens(job_id: str):
    job = job_manager.get_job(job_id)
    
    # Initialize video generator
    video_gen = VideoGenerator(
        style_params=job.style_params,  # From job metadata
        output_dir=temp_dir
    )
    
    # Generate title screen
    title_video = await video_gen.create_title_video(
        artist=job.artist,
        title=job.title
    )
    
    # Generate end screen
    end_video = await video_gen.create_end_video()
    
    # Upload to GCS
    await upload_to_gcs(f"jobs/{job_id}/title.mov", title_video)
    await upload_to_gcs(f"jobs/{job_id}/end.mov", end_video)
    
    # Mark complete, trigger video worker
    job_manager.mark_screens_complete(job_id)
    await trigger_video_worker(job_id)
```

---

## Phase 5: Video Worker (Finalization)

### What It Does

This is the most complex worker - it:
1. Generates the main karaoke video with scrolling lyrics
2. Presents instrumental selection to user
3. Combines everything into final videos
4. Exports multiple formats

### Challenge: Long-Running Task

Video encoding takes 15-20 minutes, which is:
- ✅ Within Cloud Run timeout (60 min max)
- ❌ Too long for synchronous request
- ✅ Perfect for background task

### Implementation Approach

**Step 1: Generate Main Karaoke Video**
```python
from lyrics_transcriber.video.generator import generate_karaoke_video

async def generate_main_video(job_id: str):
    # Get corrected lyrics
    corrections = await download_from_gcs(f"jobs/{job_id}/corrections.json")
    
    # Get audio with vocals
    audio_path = await download_from_gcs(job.input_media_gcs_path)
    
    # Generate 4K karaoke video
    video_path = await generate_karaoke_video(
        audio_path=audio_path,
        corrections=corrections,
        style_params=job.style_params,
        resolution="4k"
    )
    
    # Upload
    await upload_to_gcs(f"jobs/{job_id}/with_vocals.mkv", video_path)
```

**Step 2: Transition to Instrumental Selection**
```python
# Provide both instrumental options
job_manager.transition_to_state(
    job_id=job_id,
    new_status=JobStatus.AWAITING_INSTRUMENTAL_SELECTION,
    message="Choose your instrumental"
)

# User sees UI with audio preview players
# User selects "clean" or "with_backing"
# Frontend calls: POST /api/jobs/{job_id}/select-instrumental
```

**Step 3: Final Video Assembly**
```python
async def finalize_video(job_id: str):
    # Get selected instrumental
    instrumental_path = job.state_data.get("selected_instrumental")
    
    # Download components
    title_video = await download_from_gcs(f"jobs/{job_id}/title.mov")
    main_video = await download_from_gcs(f"jobs/{job_id}/with_vocals.mkv")
    end_video = await download_from_gcs(f"jobs/{job_id}/end.mov")
    instrumental_audio = await download_from_gcs(instrumental_path)
    
    # Remux main video with instrumental audio
    karaoke_video = await remux_audio(main_video, instrumental_audio)
    
    # Concatenate: title + karaoke + end
    combined = await concat_videos([title_video, karaoke_video, end_video])
    
    # Encode to multiple formats
    outputs = await encode_formats(combined, {
        "lossless_4k_mp4": {"video": "h264", "audio": "pcm"},
        "lossless_4k_mkv": {"video": "h264", "audio": "flac"},
        "lossy_4k_mp4": {"video": "h264", "audio": "aac"},
        "lossy_720p_mp4": {"video": "h264", "audio": "aac", "scale": "1280:720"}
    })
    
    # Upload all formats
    for format_name, file_path in outputs.items():
        await upload_to_gcs(f"jobs/{job_id}/final/{format_name}.mp4", file_path)
    
    # Mark job complete
    job_manager.mark_job_complete(job_id)
```

---

## Phase 6: Optional - CDG/TXT Generation

Generate CDG and TXT formats for compatibility with physical karaoke systems.

```python
from lyrics_transcriber.output.cdg import CDGGenerator

async def generate_cdg_txt(job_id: str):
    # Get LRC file
    lrc_path = await download_from_gcs(f"jobs/{job_id}/karaoke.lrc")
    
    # Convert to CDG
    cdg_gen = CDGGenerator()
    cdg_file = await cdg_gen.generate(lrc_path)
    
    # Convert to TXT
    txt_file = await convert_lrc_to_txt(lrc_path)
    
    # Get instrumental MP3 (convert from FLAC)
    instrumental_flac = await download_from_gcs(job.instrumentals["clean"])
    instrumental_mp3 = await convert_to_mp3(instrumental_flac)
    
    # Create ZIPs
    cdg_zip = await create_zip({
        f"{job.artist} - {job.title} (Karaoke).cdg": cdg_file,
        f"{job.artist} - {job.title} (Karaoke).mp3": instrumental_mp3
    })
    
    txt_zip = await create_zip({
        f"{job.artist} - {job.title} (Karaoke).txt": txt_file,
        f"{job.artist} - {job.title} (Karaoke).mp3": instrumental_mp3
    })
    
    # Upload
    await upload_to_gcs(f"jobs/{job_id}/final/cdg.zip", cdg_zip)
    await upload_to_gcs(f"jobs/{job_id}/final/txt.zip", txt_zip)
```

---

## Implementation Priority

### Sprint 1: Core Audio/Lyrics Processing (Week 1)
1. ✅ Audio worker - Modal API integration
2. ✅ Lyrics worker - AudioShake + lyrics_transcriber
3. ✅ GCS file operations
4. ✅ Job state transitions

### Sprint 2: Human Interaction (Week 2)
1. ✅ Corrections submission endpoint
2. ✅ Instrumental selection endpoint
3. ✅ React review UI (separate repo/Cloudflare Pages)
4. ✅ Email notifications (SendGrid)

### Sprint 3: Video Generation (Week 3)
1. ✅ Screens worker
2. ✅ Main karaoke video generation
3. ✅ Video finalization worker
4. ✅ Multiple format encoding

### Sprint 4: Polish & Optional Features (Week 4)
1. ✅ CDG/TXT generation
2. ✅ YouTube upload (optional)
3. ✅ Better error handling
4. ✅ Retry logic
5. ✅ Cost tracking

---

## Key Technical Decisions

### 1. Where to Run Video Encoding?

**Option A: Cloud Run Background Task**
- ✅ Simple (same codebase)
- ✅ Within timeout limits (60 min)
- ❌ Competes with API requests for resources

**Option B: Cloud Build Job**
- ✅ Dedicated compute
- ✅ Higher resource limits
- ❌ More complex orchestration

**Recommendation**: Start with **Option A** (Cloud Run background task), migrate to Option B if needed.

### 2. How to Handle FFmpeg?

**Option A: Include in Docker image**
- ✅ Simple
- ✅ Consistent version
- ❌ Larger image size

**Option B: Cloud Build with FFmpeg pre-installed**
- ✅ Optimized for video work
- ❌ More complex

**Recommendation**: **Option A** - Include FFmpeg in our Docker image.

### 3. How to Access lyrics_transcriber?

The `lyrics_transcriber_local/` submodule is already available!

```python
# Add to Python path in workers
import sys
sys.path.insert(0, "/app/lyrics_transcriber_local")

from lyrics_transcriber.transcriber import LyricsTranscriber
```

---

## Environment Variables Needed

Add to Cloud Run service:

```bash
# Audio separation
AUDIO_SEPARATOR_API_URL=https://your-modal-endpoint.modal.run

# Lyrics APIs
AUDIOSHAKE_API_TOKEN=your-audioshake-token
GENIUS_API_TOKEN=your-genius-token
RAPIDAPI_KEY=your-rapidapi-key
SPOTIFY_COOKIE_SP_DC=your-spotify-cookie

# Notifications (optional)
SENDGRID_API_KEY=your-sendgrid-key
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# YouTube (optional, later)
YOUTUBE_CLIENT_SECRETS={"installed":{"client_id":"...","...}}
```

---

## Success Criteria

### Phase 1 Complete When:
- ✅ Can upload audio file
- ✅ Audio worker separates stems via Modal
- ✅ Lyrics worker transcribes via AudioShake
- ✅ All stems/lyrics uploaded to GCS
- ✅ Job transitions to `AWAITING_REVIEW`

### Phase 2 Complete When:
- ✅ Review UI loads corrections
- ✅ User can submit corrections
- ✅ Job transitions to video generation

### Phase 3 Complete When:
- ✅ Full video pipeline works
- ✅ User can select instrumental
- ✅ Final videos generated in all formats
- ✅ Job marked `COMPLETE`

### MVP Complete When:
- ✅ End-to-end workflow works
- ✅ User can download all final files
- ✅ Quality matches CLI output

---

## Next Steps

1. **Revert stub workers** to start fresh
2. **Implement audio worker** with actual Modal API calls
3. **Implement lyrics worker** with AudioShake + lyrics_transcriber
4. **Test with real audio file** end-to-end
5. **Build corrections submission endpoint**
6. **Start React review UI** (separate task/repo)

---

**This is a REAL implementation plan, not stubs!** 🚀

