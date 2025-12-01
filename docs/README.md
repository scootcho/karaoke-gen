# Karaoke-Gen Documentation

This directory contains all documentation for the karaoke-gen project, organized by purpose.

## 📋 Current Status

**Project:** Migrating from Modal-based monolithic web app to scalable cloud architecture  
**Backend:** ✅ Phase 1.1 Complete (FastAPI on Google Cloud Run)  
**Frontend:** ⏸️ Not started (waiting for backend stability)  
**Testing:** ✅ Complete (17/17 tests passing)

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

### `02-implementation-history/` - Session Logs
Historical records of implementation sessions. Useful for understanding decisions made.

| File | Date | Purpose |
|------|------|---------|
| `SESSION-SUMMARY-2025-12-01.md` | 2025-12-01 | Backend Phase 1.1 completion summary |
| `BUG-FIXES-2025-12-01.md` | 2025-12-01 | Backend bugs fixed during testing |
| `TEST-RESULTS-2025-12-01.md` | 2025-12-01 | Backend integration test results |
| `CLEANUP-COMPLETE.md` | 2025-12-01 | Deprecated file cleanup summary |
| `IMPLEMENTATION-COMPLETE.md` | 2025-12-01 | Phase 1.1 implementation details |

### `03-deployment/` - Deployment Guides
How to deploy and operate the system.

| File | Purpose |
|------|---------|
| `INFRASTRUCTURE-AS-CODE.md` | Pulumi IaC setup and usage |
| `CLOUD-RUN-DEPLOYMENT.md` | Deploying backend to Cloud Run |
| `CLOUDBUILD-PERMISSIONS-FIX.md` | Cloud Build permission troubleshooting |
| `CLOUDFLARE-PAGES-DEPLOYMENT.md` | Frontend deployment (future) |
| `TESTING-BACKEND.md` | Running backend tests |

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
1. Read `01-reference/API-MANUAL-TESTING.md` - test the API
2. Read `03-deployment/TESTING-BACKEND.md` - run automated tests
3. Read `03-deployment/INFRASTRUCTURE-AS-CODE.md` - manage infrastructure

### I want to deploy:
1. Read `03-deployment/INFRASTRUCTURE-AS-CODE.md` - provision infrastructure
2. Read `03-deployment/CLOUD-RUN-DEPLOYMENT.md` - deploy backend
3. Read `03-deployment/CLOUDFLARE-PAGES-DEPLOYMENT.md` - deploy frontend (future)

### I want to see what was done previously:
- Check `02-implementation-history/` for session summaries

---

## 🎯 Current Phase: Backend Stability

**Goal:** Ensure backend works perfectly before touching frontend

**Status:** ✅ Phase 1.1 Complete
- Backend API deployed to Cloud Run
- All infrastructure in Pulumi
- 17/17 integration tests passing
- Manual API testing documented

**Next:** Phase 1.2 - Async job processing (audio separation, lyrics transcription)

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

