for context: @README.md  @docs/ARCHITECTURE.md @docs/MODAL-MIGRATION.md 

the modal web version of this is live on https://gen.nomadkaraoke.com/ , but it's not yet ready for use by customers.

there are several issues with this which need to be resolved, and I'm a bit overwhelmed by it all so would like your help breaking this down and figuring out a step by step plan to resolve the issues.

the way we architected and built the web version of this, currently deployed on modal, was flawed in several ways. 

1) all elements of the frontend and backend are served from Modal. while Modal is great for easily deploying and running stuff using GPUs, we should probably be serving the frontend from something better suited to static sites, e.g. cloudflare pages.

2) the backend code for everything running on modal was all lumped together in one huge (7000+ lines!) file "app.py" in the repo root: @app.py  
That's an absolute nightmare for maintainability, and I suspect there is a ton of redundant and duplicate code throughout all that too. I have no confidence that the code in there is well tested, high quality, or even makes sense, as it was never built in a modular, maintainable, SOLID way.

3) similarly, the frontend code for the entire web UI version of this was built in a very naive way with basic html/css/js with all of the logic inside a single huge (8000 lines!) javascript file frontend/app.js: @frontend/app.js  
This is awful for maintainability, and again I have no confidence any of it is actually sustainable, maintainable, and there are no tests.

4) the initial tenet of using Modal for this was that it was supposed to be well suited to running GPU workloads (as the audio separation part of the karaoke generation workflow runs much faster with GPU available). However, in practice I saw a bunch of issues when trying to actually use it, e.g. if I tried to run multiple karaoke generation jobs concurrently, inputs would somehow get mixed up and everything became slow and barely usable (e.g. the web interface no longer responded, since it was also served from modal). 

I think we should re-think the architecture so we're not using Modal for everything. We can probably still use it for the audio separation specifically (audio-separator is deployed on modal independently and separation jobs can be executed remotely using the client; details here: https://github.com/nomadkaraoke/python-audio-separator/blob/main/audio_separator/remote/README.md ), but I think we ought to recreate the frontend as a React app, deployed as a static site on Cloudflare pages.
I'd like the bulk of the backend processing (e.g. job processing, video rendering which needs CPU power but not GPU) should be hosted on google cloud, as I have a bunch of google cloud credits available.

I'd also really like to ensure we don't duplicate any code between the karaoke-gen CLI tool vs. this cloud-hosted, web based version. In the version which is currently deployed on Modal, I believe there's duplication of some of the functionality. Where possible, in this new version, I'd rather we rework karaoke-gen so it can be used as a CLI tool and as part of the web based system backend rather than duplicating any functionality.

Please investigate all of the existing code and help make a plan for the new approach to a web-based karaoke-gen.

---------------

# Web-Based Karaoke Generator Migration Plan

## Current State Analysis

**Critical Issues:**

- [`app.py`](app.py) (7000+ lines): Monolithic Modal application with all backend logic
- [`frontend/app.js`](frontend/app.js) (8000+ lines): Monolithic vanilla JS with all UI logic
- Everything served from Modal (frontend + backend + GPU tasks)
- Code duplication between CLI ([`karaoke_gen/`](karaoke_gen/)) and web version ([`core.py`](core.py))
- Performance issues with concurrent jobs on Modal

## Target Architecture

**Frontend:** React SPA on Cloudflare Pages

**Backend:** FastAPI on Google Cloud Run

**GPU Processing:** Audio Separator API (Modal or remote)

**Database:** Firestore for job state, user sessions

**Storage:** Google Cloud Storage for audio/video files

**Auth:** Token-based (keep existing system initially)

## Migration Strategy: MVP-First Approach

Focus on **basic karaoke generation** only. Defer: authentication, Stripe payments, YouTube upload, admin dashboard.

---

## Phase 1: Backend Refactoring (2-3 days)

### 1.1 Create Modular Backend Structure

**Goal:** Extract and organize backend code from [`app.py`](app.py) into maintainable modules.

**New structure:**

```
backend/
├── main.py                      # FastAPI app entry point
├── api/
│   ├── routes/
│   │   ├── jobs.py             # Job submission, status
│   │   ├── uploads.py          # File upload handling
│   │   └── health.py           # Health checks
│   └── dependencies.py         # Shared dependencies
├── services/
│   ├── job_manager.py          # Job queue & state management
│   ├── storage_service.py      # GCS file operations
│   ├── firestore_service.py    # Database operations
│   └── processing_service.py   # Core karaoke processing
├── models/
│   ├── job.py                  # Job data models
│   └── requests.py             # API request models
├── config.py                   # Configuration management
├── requirements.txt
└── Dockerfile                  # For Cloud Run deployment
```

**Key changes:**

- Move job submission logic from [`app.py:3294-3334`](app.py) into `api/routes/jobs.py`
- Extract `update_job_status_with_timeline` (app.py:6055) into `services/job_manager.py`
- Reuse existing [`karaoke_gen/`](karaoke_gen/) modules directly (no duplication!)

### 1.2 Integrate karaoke_gen CLI Modules

**Critical:** Use [`karaoke_gen/karaoke_gen.py:KaraokePrep`](karaoke_gen/karaoke_gen.py) directly instead of [`core.py:ServerlessKaraokeProcessor`](core.py).

**Changes needed:**

1. Import `KaraokePrep` from `karaoke_gen` in `services/processing_service.py`
2. Configure `AUDIO_SEPARATOR_API_URL` environment variable to use remote GPU separation
3. Remove [`core.py`](core.py) wrapper (eliminates duplication)
4. Pass custom logger to `KaraokePrep` for job-specific logging

**Key insight:** Audio separation already supports remote API via environment variable ([`karaoke_gen/audio_processor.py:168-374`](karaoke_gen/audio_processor.py)), so GPU tasks automatically offload to audio-separator API!

### 1.3 Setup Google Cloud Infrastructure

**Services to configure:**

1. **Firestore:** Collections for `jobs`, `sessions`
2. **Cloud Storage:** Buckets for `uploads/`, `outputs/`, `temp/`
3. **Cloud Run:** Service for backend API
4. **Secret Manager:** API keys (AudioShake, Genius, etc.)

**Environment variables:**

```bash
AUDIO_SEPARATOR_API_URL=https://your-modal-url/api
GOOGLE_CLOUD_PROJECT=your-project-id
GCS_BUCKET_NAME=karaoke-gen-storage
FIRESTORE_COLLECTION=jobs
AUDIOSHAKE_API_KEY=...
GENIUS_API_KEY=...
```

---

## Phase 2: Frontend Rebuild (3-4 days)

### 2.1 Create React Application

**Tech stack:**

- React 18 with TypeScript
- Vite for build tooling
- TanStack Query for API state management
- Tailwind CSS for styling
- Zustand for client state

**New structure:**

```
frontend-react/
├── src/
│   ├── components/
│   │   ├── JobSubmission.tsx    # Upload/URL input
│   │   ├── JobStatus.tsx        # Progress display
│   │   ├── DownloadResults.tsx  # Download links
│   │   └── ErrorDisplay.tsx     # Error handling
│   ├── hooks/
│   │   ├── useJobSubmit.ts      # Job submission logic
│   │   ├── useJobStatus.ts      # Polling for status
│   │   └── useFileUpload.ts     # File upload handling
│   ├── services/
│   │   └── api.ts               # Backend API client
│   ├── types/
│   │   └── job.ts               # TypeScript types
│   ├── App.tsx
│   └── main.tsx
├── public/
├── package.json
└── vite.config.ts
```

### 2.2 Extract Core UI Logic

**From [`frontend/app.js`](frontend/app.js) extract:**

1. Job submission flow (lines ~3500-3700)
2. Status polling mechanism (lines ~200-400)
3. File upload handling
4. Progress display logic

**Convert to React components:**

- Replace global state with Zustand stores
- Replace DOM manipulation with React state
- Replace fetch calls with TanStack Query
- Add TypeScript types for safety

### 2.3 Deploy to Cloudflare Pages

**Setup:**

1. Connect GitHub repo to Cloudflare Pages
2. Configure build: `npm run build` (Vite output to `dist/`)
3. Set custom domain: `gen.nomadkaraoke.com`
4. Add environment variable: `VITE_API_URL=https://your-cloud-run-url`

---

## Phase 3: Integration & Testing (2-3 days)

### 3.1 End-to-End Workflow Testing

**Test scenarios:**

1. Upload audio file → Process → Download result
2. Submit YouTube URL → Process → Download result
3. Concurrent job processing (multiple users)
4. Error handling (invalid files, API failures)
5. Large file handling (5+ minute songs)

### 3.2 Performance Optimization

**Backend:**

- Configure Cloud Run: min 0, max 10 instances
- Set timeout: 600 seconds for long jobs
- Enable Cloud Run CPU throttling
- Add Cloud Storage signed URLs for downloads

**Frontend:**

- Code splitting for faster initial load
- Asset optimization (images, fonts)
- Service worker for offline status viewing
- Progressive loading for large lists

### 3.3 Monitoring & Logging

**Setup:**

- Cloud Run logging to Cloud Logging
- Firestore metrics dashboard
- Error tracking (Sentry or Cloud Error Reporting)
- Job completion rate tracking

---

## Phase 4: Migration & Cleanup (1-2 days)

### 4.1 Cutover Process

1. Deploy new backend to Cloud Run
2. Deploy new frontend to Cloudflare Pages
3. Update DNS/routing for `gen.nomadkaraoke.com`
4. Monitor for 24 hours with both systems running
5. Shut down Modal deployment

### 4.2 Code Cleanup

**Remove:**

- [`app.py`](app.py) (replaced by modular backend)
- [`core.py`](core.py) (duplication eliminated)
- [`frontend/app.js`](frontend/app.js) (replaced by React)
- Modal-specific configuration

**Keep:**

- [`karaoke_gen/`](karaoke_gen/) (shared with CLI)
- [`docs/`](docs/) (update architecture docs)
- [`tests/`](tests/) (update for new architecture)

### 4.3 Documentation Updates

Update these files:

- [`README.md`](README.md): Add web app usage
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): New architecture diagram
- Create `docs/DEPLOYMENT.md`: Cloud Run + Cloudflare setup
- Create `docs/API.md`: Backend API reference

---

## Key Technical Decisions

### Why Cloud Run?

- Auto-scaling (0 to N instances)
- Pay-per-use (fits usage patterns)
- Container-based (easy deployment)
- Built-in load balancing
- 600s timeout (sufficient for video rendering)

### Why Reuse karaoke_gen Modules?

- **Zero duplication:** One codebase for CLI + web
- **Battle-tested:** CLI code is proven and tested
- **Maintainability:** Fix bugs once, benefits both
- **Audio separation:** Already supports remote API mode

### Why Firestore?

- Native GCP integration
- Flexible schema (job data varies)
- Real-time updates (for status polling)
- Auto-scaling built-in
- No server management

### Critical Path: Audio Separation

The [`karaoke_gen/audio_processor.py`](karaoke_gen/audio_processor.py) already supports remote audio separation:

- Checks `AUDIO_SEPARATOR_API_URL` environment variable
- If set, uses remote API (GPU on Modal)
- If not set, falls back to local processing

**Therefore:** Set `AUDIO_SEPARATOR_API_URL` in Cloud Run, and GPU tasks automatically offload to audio-separator API!

---

## Estimated Timeline

**Total: 8-12 days for MVP**

- Phase 1 (Backend): 2-3 days
- Phase 2 (Frontend): 3-4 days  
- Phase 3 (Integration): 2-3 days
- Phase 4 (Migration): 1-2 days

## Future Enhancements (Post-MVP)

These features exist in current Modal version but are deferred:

- Authentication system (token management)
- Stripe payment integration  
- YouTube upload functionality
- Admin dashboard & monitoring
- Lyrics review interface
- Job queue prioritization

---

## Risk Mitigation

**Concurrency Issues:** Use Firestore transactions for job state updates

**Long Processing:** Cloud Run 600s timeout should suffice; add timeout handling

**Large Files:** Use GCS signed URLs for direct upload/download

**Cost Control:** Set Cloud Run max instances, implement usage quotas

**Rollback Plan:** Keep Modal deployment running during migration period