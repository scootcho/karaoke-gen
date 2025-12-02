# Karaoke-Gen Documentation

This directory contains all documentation for the karaoke-gen project, organized by purpose.

## 📋 Current Status (Updated: 2025-12-01)

**Project:** Migrating from Modal-based monolithic web app to scalable cloud architecture  
**Backend:** ✅ Phase 1.3 Complete (Workers + Video Generation)  
**Frontend:** ⏸️ Not started (waiting for backend stability)  
**Deployment:** ✅ Cloud Run with custom domain (api.nomadkaraoke.com)  
**Testing:** ✅ Complete (62 unit tests + 11 emulator integration tests, all passing)

---

## 📂 Documentation Structure

### `00-current-plan/` - **START HERE**
The active migration plan and requirements. Read these first.

| File | Purpose |
|------|---------|
| **`MASTER-PLAN.md`** | **Main migration plan** - phases, architecture, timeline |
| `CLOUD-MIGRATION-REQUIREMENTS.md` | Architectural implications from CLI workflow analysis |

### `01-reference/` - Reference Documentation
Core system documentation that doesn't change often.

| File | Purpose |
|------|---------|
| `KARAOKE-GEN-CLI-WORKFLOW.md` | Complete technical breakdown of CLI workflow (8 stages) |
| `ARCHITECTURE.md` | Original CLI architecture documentation |
| `API-MANUAL-TESTING.md` | How to manually test backend API with curl |
| `AUTHENTICATION.md` | Token-based authentication system (implemented) |
| `CLOUD-RUN-ARCHITECTURE.md` | How Cloud Run works, containers, scaling, concurrency |

### `02-implementation-history/` - Session Logs
Historical records of implementation sessions. Useful for understanding decisions made.

| File | Date | Purpose |
|------|------|---------|
| `PHASE-1-2-PROGRESS.md` | 2025-12-01 | Async job processing, workers, state machine |
| `PHASE-1-3-PROGRESS.md` | 2025-12-01 | Video generation worker implementation |
| `AUTHENTICATION-IMPLEMENTATION.md` | 2025-12-01 | Token-based auth system implementation |
| `FIRST-TEST-FIXES.md` | 2025-12-01 | Environment variables & race condition fixes |
| `FILE-UPLOAD-IMPLEMENTATION.md` | 2025-12-01 | File upload endpoint implementation |
| `DOCKER-BUILD-OPTIMIZATION.md` | 2025-12-01 | Build caching improvements (20min → 2min) |

### `03-deployment/` - Deployment Guides
How to deploy and operate the system.

| File | Purpose |
|------|---------|
| **`EMULATOR-TESTING.md`** | **Local integration testing** with Firestore/GCS emulators |
| **`SETUP-VENV.md`** | **Quick venv setup** (Python 3.12, dependencies) |
| **`LOCAL-VALIDATION.md`** | **Validate before deploying** (catches import errors) |
| **`OBSERVABILITY-GUIDE.md`** | **Debug production issues** (logs, metrics, debug script) |
| `CUSTOM-DOMAIN-SETUP.md` | Setting up api.nomadkaraoke.com |
| `WHY-BUILD-DIDNT-DEPLOY.md` | Cloud Build deployment troubleshooting |
| `VENV-SETUP-COMPLETE.md` | Complete venv setup walkthrough |
| `OBSERVABILITY-IMPROVEMENTS.md` | Observability improvements made |

### `archived/` - Old/Deprecated Files
Historical documents no longer relevant to current architecture.

<details>
<summary>Click to see archived files</summary>

- `MODAL-MIGRATION.md` - Original Modal-based architecture (deprecated)
- `NEW-ARCHITECTURE.md` - Early architecture draft (superseded by MASTER-PLAN)
- `MIGRATION-CUTOVER.md` - Old cutover plan (no longer relevant)
- `MIGRATION-SUMMARY.md` - Old migration summary
- `PERFORMANCE-OPTIMIZATION.md` - Old optimization guide
- `TESTING-GUIDE.md` - Old testing guide (superseded by TESTING-BACKEND)
- `AUTHENTICATION_SETUP.md` - Old auth setup (deferred to later phase)
- `FINALIZATION-SETUP.md` - Old finalization docs
- `stripe-wip.md` - Stripe integration WIP (deferred to later phase)
- `COUNTDOWN_PADDING_*.md` - Implementation details (now in karaoke-gen package)

</details>

### `NEXT-STEPS.md` - Current TODO
What to do next after current phase completes. Gets updated frequently.

---

## 🚀 Quick Start

### I want to understand the project:
1. Read `00-current-plan/MASTER-PLAN.md` - overall strategy
2. Read `00-current-plan/CLOUD-MIGRATION-REQUIREMENTS.md` - why it's complex
3. Read `01-reference/KARAOKE-GEN-CLI-WORKFLOW.md` - how the CLI works

### I want to work on the backend:
1. Read `03-deployment/EMULATOR-TESTING.md` - run local integration tests
2. Read `01-reference/API-MANUAL-TESTING.md` - test the API manually
3. Read `03-deployment/LOCAL-VALIDATION.md` - validate before deploying
4. Read `03-deployment/INFRASTRUCTURE-AS-CODE.md` - manage infrastructure

### I want to deploy:
1. Read `03-deployment/INFRASTRUCTURE-AS-CODE.md` - provision infrastructure
2. Read `03-deployment/CLOUD-RUN-DEPLOYMENT.md` - deploy backend
3. Read `03-deployment/CLOUDFLARE-PAGES-DEPLOYMENT.md` - deploy frontend (future)

### I want to see what was done previously:
- Check `02-implementation-history/` for session summaries

---

## 🎯 Current Phase: Backend Workers & Testing

**Goal:** Complete async job processing and fix production issues

**Status:** ✅ Phase 1.3 Nearly Complete
- ✅ Backend API deployed to Cloud Run
- ✅ All infrastructure in Pulumi  
- ✅ Custom domain with SSL (api.nomadkaraoke.com)
- ✅ 4 workers implemented (audio, lyrics, screens, video)
- ✅ 21-state job state machine
- ✅ Human-in-the-loop API endpoints
- ✅ Local validation & debug tooling
- ✅ Token-based authentication system
- 🔄 **Current:** Fixing Firestore consistency issues

**What Works:**
- Health endpoint
- Job creation
- File uploads to GCS
- Firestore job storage
- Environment variables
- Cloud Build deployment

**What's Being Fixed:**
- Firestore eventual consistency causing race condition
- Workers seeing stale job data

**Next:** Phase 1.4 - End-to-end testing with real job processing

See `NEXT-STEPS.md` for detailed next actions.

---

## 📝 Key Insights

### Why This Is Complex

The karaoke-gen CLI is **not a simple batch job**. It's a multi-stage process with:
- **2 human interaction points** (lyrics review, instrumental selection)
- **30-45 minute total processing time**
- **Multiple external APIs** (Modal, AudioShake, Genius, YouTube)
- **~2GB working files** per song
- **Parallel processing** (audio + lyrics simultaneously)

**The cloud version must support async processing with human-in-the-loop.**

See `00-current-plan/CLOUD-MIGRATION-REQUIREMENTS.md` for full analysis.

### Critical Design Decisions

1. **Why not simplify the workflow?**  
   → Human review is essential for quality. Cannot be automated without sacrificing output quality.

2. **Why so many output formats?**  
   → Different use cases: archival (lossless), streaming (lossy 4K), mobile (720p), karaoke machines (CDG).

3. **Why async job queue?**  
   → Processing takes 30-45 min with gaps for human decisions. Cannot block HTTP requests.

4. **Why Firestore + GCS?**  
   → Need state persistence (Firestore) and large file storage (GCS). Cloud Run is stateless.

---

## 🔄 How This Repo Is Updated

- **Active development docs** stay in `00-current-plan/`
- **Completed session summaries** go to `02-implementation-history/`
- **Reference docs** stay stable in `01-reference/`
- **Deployment guides** get updated as infrastructure changes
- **Superseded docs** move to `archived/`

---

## 🆘 Getting Help

If you're confused:
1. Start with `00-current-plan/MASTER-PLAN.md`
2. Check if there's a recent session summary in `02-implementation-history/`
3. Look for specific deployment guides in `03-deployment/`

If something seems outdated, it might be in `archived/` - check there before assuming it's lost.

