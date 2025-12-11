# Scalable Architecture Plan

**Last Updated:** 2025-12-11

This document outlines the plan for evolving karaoke-gen's cloud backend to support **100+ concurrent jobs** with no performance degradation, while also achieving a clean, maintainable codebase with proper separation of concerns.

---

## Goals

### Infrastructure Goals
1. **Horizontal scalability** - Each job gets dedicated resources (no resource contention)
2. **Maximum processing speed** - Same speed for 1 job or 100 concurrent jobs
3. **Reliability** - Automatic retries, no lost jobs from container restarts
4. **Cost efficiency** - Scale to zero when idle, pay only for active processing

### Software Architecture Goals
1. **SOLID principles** - Single responsibility, clean interfaces
2. **DRY** - Share code between local CLI and remote backend
3. **Testability** - Each component independently testable
4. **Maintainability** - Bug fixes apply everywhere, easy to add features

---

## Current Architecture

### What Works Well

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CURRENT ARCHITECTURE (v0.71.x)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ✅ Heavy work already offloaded to external services:                     │
│                                                                             │
│   Audio Separation  ──────────────────▶  Modal API (GPU, ~5-8 min)         │
│   Lyrics Transcription  ──────────────▶  AudioShake API (~2-3 min)         │
│                                                                             │
│   ✅ State persistence in Firestore (survives restarts)                     │
│   ✅ Files in GCS (no local storage dependencies)                           │
│   ✅ Internal HTTP endpoints exist for worker triggers                      │
│   ✅ Workers are self-contained (only need job_id)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Current Limitations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CURRENT FLOW (PROBLEMATIC)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   POST /api/jobs/upload                                                     │
│      │                                                                      │
│      ├──▶ Save job to Firestore  ✅                                         │
│      │                                                                      │
│      └──▶ BackgroundTasks.add_task(trigger_workers)                        │
│               │                                                             │
│               └──▶ HTTP POST /api/internal/workers/audio                   │
│                        │                                                    │
│                        └──▶ BackgroundTasks.add_task(process_audio)  ⚠️    │
│                                   │                                         │
│                                   └── Runs IN THE SAME CONTAINER            │
│                                       as the API request handler            │
│                                                                             │
│   PROBLEMS:                                                                 │
│   ⚠️  Container may be killed before background tasks complete              │
│   ⚠️  No guaranteed delivery - if container crashes, job is lost            │
│   ⚠️  Multiple concurrent jobs share CPU/memory (resource contention)       │
│   ⚠️  Long-running video encoding (15-20 min) vulnerable to timeouts        │
│   ⚠️  FFmpeg renders compete for resources when jobs run in parallel        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Target Architecture: Horizontally Scalable Infrastructure

### Option A: Google Cloud Tasks (Recommended for Workers)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLOUD TASKS ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   POST /api/jobs/upload                                                     │
│      │                                                                      │
│      ├──▶ Save job to Firestore                                            │
│      │                                                                      │
│      └──▶ Enqueue Cloud Tasks:                                             │
│              │                                                              │
│              ├──▶ audio-worker-queue ──────────────────────────────┐       │
│              │    {job_id, target: /internal/workers/audio}        │       │
│              │                                                      │       │
│              └──▶ lyrics-worker-queue ─────────────────────────────┤       │
│                   {job_id, target: /internal/workers/lyrics}       │       │
│                                                                    ▼       │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                     Cloud Tasks Queue                               │   │
│   │                                                                     │   │
│   │  • Guaranteed delivery (retries on failure)                        │   │
│   │  • Rate limiting / concurrency control                             │   │
│   │  • Task deduplication                                              │   │
│   │  • Configurable timeouts (up to 30 min per task)                   │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │           Cloud Run (Auto-Scaled Worker Instances)                  │   │
│   │                                                                     │   │
│   │   Instance 1        Instance 2        Instance 3        ...        │   │
│   │   ┌──────────┐      ┌──────────┐      ┌──────────┐                 │   │
│   │   │  Job A   │      │  Job B   │      │  Job C   │                 │   │
│   │   │  Audio   │      │  Audio   │      │  Lyrics  │                 │   │
│   │   └──────────┘      └──────────┘      └──────────┘                 │   │
│   │                                                                     │   │
│   │   Each task gets a DEDICATED container instance                    │   │
│   │   • Full CPU/memory for that task alone                            │   │
│   │   • No resource contention with other jobs                         │   │
│   │   • Container lifecycle tied to task completion                    │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ Each job gets dedicated resources (no contention)
- ✅ Automatic retries on failure
- ✅ Queue-based backpressure (won't overwhelm external APIs)
- ✅ Container lifecycle matches task lifecycle
- ✅ Cloud Run auto-scales based on queue depth
- ✅ Scales to 1000s of concurrent jobs

**Migration Effort:** LOW - Internal HTTP endpoints already exist

### Option B: Cloud Run Jobs (For Long-Running Tasks)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLOUD RUN JOBS ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   For tasks that exceed 30-minute Cloud Tasks timeout (video encoding):    │
│                                                                             │
│   POST /api/jobs/{id}/select-instrumental                                  │
│      │                                                                      │
│      └──▶ Start Cloud Run Job execution:                                   │
│              │                                                              │
│              └──▶ gcloud run jobs execute video-worker-job \               │
│                      --args job_id=$JOB_ID                                 │
│                                                                             │
│   ┌────────────────────────────────────────────────────────────────────┐   │
│   │                    Cloud Run Job Execution                          │   │
│   │                                                                     │   │
│   │   • Container runs until completion (up to 24 hours)               │   │
│   │   • Clean separation from API service                              │   │
│   │   • Can request higher CPU/memory than service                     │   │
│   │   • Ideal for video encoding (15-20 min)                           │   │
│   │   • Progress written to Firestore for CLI monitoring               │   │
│   └────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Use Cases:**
- Video rendering (15-20 min of FFmpeg encoding)
- Final video generation with multiple output formats
- Any task that might exceed 30 minutes

### Option C: Pub/Sub + Cloud Run (Event-Driven)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PUB/SUB EVENT-DRIVEN ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Job State Changes ──────────▶ Pub/Sub Topics                             │
│                                      │                                      │
│   job.created ───────────────────────┼──▶ audio-worker subscription        │
│                                      │    └──▶ /internal/workers/audio     │
│                                      │                                      │
│   job.created ───────────────────────┼──▶ lyrics-worker subscription       │
│                                      │    └──▶ /internal/workers/lyrics    │
│                                      │                                      │
│   audio.complete + lyrics.complete ──┼──▶ screens-worker subscription      │
│                                      │    └──▶ /internal/workers/screens   │
│                                      │                                      │
│   review.complete ───────────────────┼──▶ render-worker subscription       │
│                                      │    └──▶ /internal/workers/render    │
│                                      │                                      │
│   instrumental.selected ─────────────┼──▶ video-worker subscription        │
│                                           └──▶ /internal/workers/video     │
│                                                                             │
│   Benefits:                                                                 │
│   • True decoupling (workers don't know about each other)                  │
│   • Dead-letter queues for failed messages                                 │
│   • Can add new worker types without changing existing code                │
│   • Natural fit for event-sourced architecture                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Recommended Hybrid Approach

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RECOMMENDED: HYBRID ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Cloud Tasks (fast workers < 30 min):                                     │
│   ├── audio-worker-queue     (5-8 min via Modal API)                       │
│   ├── lyrics-worker-queue    (2-3 min via AudioShake)                      │
│   ├── screens-worker-queue   (30 sec FFmpeg)                               │
│   └── render-worker-queue    (10-15 min LyricsTranscriber)                 │
│                                                                             │
│   Cloud Run Jobs (long workers > 30 min):                                  │
│   └── video-encoding-job     (15-20 min FFmpeg multi-format encoding)      │
│                                                                             │
│   Both use the SAME internal HTTP endpoints - minimal code changes!        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Target Architecture: Shared Pipeline (Software)

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
│   │   - Local GPU/CPU    │    - Cloud Tasks queue                       │  │
│   │   - Blocking         │    - Async + polling                         │  │
│   └──────────────────────┴───────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stage Interface Design

```python
# karaoke_gen/pipeline/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

@dataclass
class PipelineContext:
    """Shared context passed between pipeline stages."""
    job_id: str
    artist: str
    title: str
    temp_dir: str
    style_config: dict
    # ... other shared state

@dataclass  
class StageResult:
    """Result from a pipeline stage."""
    success: bool
    outputs: dict  # Stage-specific outputs
    error: Optional[str] = None

class PipelineStage(Protocol):
    """Interface for all pipeline stages."""
    
    @property
    def name(self) -> str:
        """Stage identifier."""
        ...
    
    async def execute(self, context: PipelineContext) -> StageResult:
        """Execute the stage."""
        ...
    
    async def validate_inputs(self, context: PipelineContext) -> bool:
        """Verify required inputs exist."""
        ...
```

### Execution Adapters

```python
# karaoke_gen/pipeline/executors/local.py

class LocalExecutor:
    """Runs stages directly in-process (for CLI)."""
    
    async def run_stage(self, stage: PipelineStage, context: PipelineContext) -> StageResult:
        # Validate inputs
        if not await stage.validate_inputs(context):
            return StageResult(success=False, outputs={}, error="Missing inputs")
        
        # Run directly
        return await stage.execute(context)

# karaoke_gen/pipeline/executors/remote.py

class RemoteExecutor:
    """Runs stages via backend API/Cloud Tasks (for remote CLI)."""
    
    async def run_stage(self, stage: PipelineStage, context: PipelineContext) -> StageResult:
        # Enqueue to Cloud Tasks
        task = cloud_tasks_client.create_task(
            queue=f"{stage.name}-worker-queue",
            http_request={
                "url": f"{self.backend_url}/api/internal/workers/{stage.name}",
                "body": json.dumps({"job_id": context.job_id}),
            }
        )
        
        # Poll for completion
        while True:
            status = await self.get_job_status(context.job_id)
            if status.stage_complete(stage.name):
                return StageResult(success=True, outputs=status.stage_outputs)
            await asyncio.sleep(5)
```

---

## Combined Architecture Vision

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE TARGET ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      PIPELINE STAGES (SHARED)                        │  │
│   │                                                                      │  │
│   │   SeparationStage  TranscriptionStage  RenderStage  FinalizeStage   │  │
│   │        │                  │                │              │         │  │
│   │   Single source of truth for business logic                         │  │
│   │   Used by both local CLI and cloud workers                          │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│                          ┌───────────┴───────────┐                         │
│                          │                       │                         │
│   ┌──────────────────────▼───────┐   ┌──────────▼──────────────────────┐  │
│   │      LOCAL EXECUTOR          │   │      REMOTE EXECUTOR            │  │
│   │                              │   │                                  │  │
│   │   karaoke-gen CLI            │   │   karaoke-gen-remote CLI        │  │
│   │   • Direct stage calls       │   │   • HTTP to backend             │  │
│   │   • Local GPU/CPU            │   │   • Progress polling            │  │
│   │   • Blocking execution       │   │                                  │  │
│   │   • Browser review UI        │   │                                  │  │
│   └──────────────────────────────┘   └──────────┬──────────────────────┘  │
│                                                  │                         │
│                                                  ▼                         │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    CLOUD INFRASTRUCTURE                              │  │
│   │                                                                      │  │
│   │   Cloud Run Service (API)                                           │  │
│   │   ├── Job submission, status, review endpoints                      │  │
│   │   └── Enqueues tasks to Cloud Tasks                                 │  │
│   │                                                                      │  │
│   │   Cloud Tasks Queues (Guaranteed Delivery)                          │  │
│   │   ├── audio-worker-queue     ──▶  Cloud Run (auto-scaled)          │  │
│   │   ├── lyrics-worker-queue    ──▶  Cloud Run (auto-scaled)          │  │
│   │   ├── screens-worker-queue   ──▶  Cloud Run (auto-scaled)          │  │
│   │   └── render-worker-queue    ──▶  Cloud Run (auto-scaled)          │  │
│   │                                                                      │  │
│   │   Cloud Run Jobs (Long-Running)                                     │  │
│   │   └── video-encoding-job     ──▶  Dedicated high-CPU instance      │  │
│   │                                                                      │  │
│   │   Each task gets DEDICATED RESOURCES:                               │  │
│   │   • 2-4 vCPU, 4-8GB RAM per task                                   │  │
│   │   • No contention with other jobs                                   │  │
│   │   • Same speed whether 1 job or 100 jobs                           │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   External Services (Unchanged):                                           │
│   ├── Modal API (GPU audio separation)                                    │
│   ├── AudioShake API (transcription)                                      │
│   ├── Firestore (job state)                                               │
│   └── GCS (file storage)                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Infrastructure Scaling (Priority: HIGH)

**Goal:** Enable 100+ concurrent jobs with no performance degradation

**Changes:**

1. **Add Cloud Tasks infrastructure (Pulumi)**
   ```python
   # infrastructure/__main__.py
   
   # Create Cloud Tasks queues
   audio_queue = gcp.cloudtasks.Queue("audio-worker-queue",
       location=region,
       rate_limits={
           "max_dispatches_per_second": 10,  # Rate limit to protect Modal API
           "max_concurrent_dispatches": 50,   # Max parallel workers
       },
       retry_config={
           "max_attempts": 3,
           "min_backoff": "10s",
           "max_backoff": "300s",
       }
   )
   # Similar for lyrics, screens, render queues
   ```

2. **Update WorkerService to use Cloud Tasks**
   ```python
   # backend/services/worker_service.py
   
   async def trigger_worker(self, worker_type: str, job_id: str) -> bool:
       if self.use_cloud_tasks:
           # Production: enqueue to Cloud Tasks
           return await self._enqueue_cloud_task(worker_type, job_id)
       else:
           # Development: direct HTTP call (existing behavior)
           return await self._trigger_http(worker_type, job_id)
   ```

3. **Add Cloud Run Job for video encoding**
   ```yaml
   # cloudbuild-video-job.yaml
   - name: gcr.io/cloud-builders/gcloud
     args:
       - run
       - jobs
       - create
       - video-encoding-job
       - --image=${_IMAGE}
       - --cpu=4
       - --memory=8Gi
       - --max-retries=2
       - --task-timeout=3600  # 1 hour max
   ```

4. **Update internal endpoints for Cloud Tasks**
   - Add request validation for Cloud Tasks headers
   - Extend timeout handling for long-running tasks
   - Add idempotency for safe retries

**Estimated Effort:** 2-3 days
**Risk:** Low (existing endpoints work unchanged)

### Phase 2: Shared Pipeline Architecture (Priority: MEDIUM)

**Goal:** Single source of truth for business logic, DRY codebase

**Changes:**

1. **Extract stage interfaces**
   ```
   karaoke_gen/pipeline/
   ├── __init__.py
   ├── base.py              # PipelineStage, PipelineContext, StageResult
   ├── context.py           # Context management
   ├── stages/
   │   ├── __init__.py
   │   ├── separation.py    # Audio separation stage
   │   ├── transcription.py # Lyrics transcription stage
   │   ├── screens.py       # Title/end screen generation
   │   ├── render.py        # Video rendering with lyrics
   │   └── finalize.py      # Final encoding and distribution
   └── executors/
       ├── __init__.py
       ├── local.py         # Direct execution for CLI
       └── remote.py        # Cloud Tasks execution for remote CLI
   ```

2. **Migrate stages incrementally**
   - Start with SeparationStage (simplest, well-isolated)
   - Prove pattern works with both executors
   - Migrate remaining stages one at a time
   - Keep old code paths working during migration

3. **Update CLIs to use pipeline**
   ```python
   # karaoke_gen/utils/gen_cli.py (local)
   executor = LocalExecutor()
   pipeline = Pipeline([
       SeparationStage(),
       TranscriptionStage(),
       ReviewStage(),
       RenderStage(),
       FinalizeStage(),
   ])
   await pipeline.run(executor, context)
   
   # karaoke_gen/utils/remote_cli.py (remote)
   executor = RemoteExecutor(backend_url)
   # Same pipeline, different executor
   await pipeline.run(executor, context)
   ```

**Estimated Effort:** 1-2 weeks
**Risk:** Medium (requires careful refactoring)

### Phase 3: Advanced Features (Priority: LOW)

1. **Event-driven architecture with Pub/Sub** (optional)
2. **Workflow orchestration with Cloud Workflows** (optional)
3. **Cost optimization with preemptible VMs** (for video encoding)
4. **Multi-region deployment** for lower latency

---

## Migration Strategy

### Zero-Downtime Migration

```
Week 1: Deploy Cloud Tasks infrastructure (no code changes)
        └── Queues exist but aren't used yet

Week 2: Add feature flag for Cloud Tasks
        └── ENABLE_CLOUD_TASKS=false (default)
        └── Test with flag enabled in staging

Week 3: Enable Cloud Tasks in production
        └── ENABLE_CLOUD_TASKS=true
        └── Monitor for issues

Week 4: Remove old BackgroundTasks code paths
        └── Clean up feature flag
        └── Update documentation
```

### Rollback Plan

If issues occur after enabling Cloud Tasks:
1. Set `ENABLE_CLOUD_TASKS=false`
2. Redeploy (takes ~2 minutes)
3. New jobs use BackgroundTasks (old behavior)
4. In-flight Cloud Tasks jobs continue to completion

---

## Resource Configuration

### Cloud Tasks Queues

| Queue | Max Concurrent | Rate Limit | Timeout | Retries |
|-------|---------------|------------|---------|---------|
| audio-worker | 50 | 10/sec | 15 min | 3 |
| lyrics-worker | 50 | 10/sec | 10 min | 3 |
| screens-worker | 100 | 50/sec | 2 min | 3 |
| render-worker | 20 | 5/sec | 30 min | 2 |

### Cloud Run Worker Instances

| Worker | CPU | Memory | Timeout | Notes |
|--------|-----|--------|---------|-------|
| audio | 2 | 2Gi | 15 min | Mostly I/O (Modal API) |
| lyrics | 2 | 2Gi | 10 min | Mostly I/O (AudioShake) |
| screens | 2 | 2Gi | 2 min | FFmpeg (quick) |
| render | 4 | 4Gi | 30 min | LyricsTranscriber + FFmpeg |
| video-job | 4 | 8Gi | 60 min | Heavy FFmpeg encoding |

### Cost Estimate (100 concurrent jobs)

```
Cloud Tasks:    ~$0.40/million tasks    ≈ $0.01/day
Cloud Run:      ~$0.00002/vCPU-sec      ≈ $5-10/day (100 jobs)
Cloud Run Jobs: ~$0.00002/vCPU-sec      ≈ $2-5/day (100 jobs)
Modal (GPU):    ~$2.50/hour             ≈ $20-40/day (100 jobs)
AudioShake:     Usage-based             ≈ $10-20/day (100 jobs)

Total: ~$40-80/day for 100 concurrent jobs
```

---

## Success Criteria

### Infrastructure
- [ ] 100 concurrent jobs complete without failures
- [ ] Processing time per job unchanged (same as 1 job)
- [ ] No resource contention (CPU/memory per job consistent)
- [ ] Automatic retry on transient failures
- [ ] Zero lost jobs from container restarts

### Software Architecture
- [ ] Single stage implementation used by both CLIs
- [ ] Bug fixes apply to both local and remote execution
- [ ] Each stage independently testable
- [ ] Clear interfaces between stages
- [ ] 80%+ code coverage on pipeline module

---

## Related Documents

- [ARCHITECTURE.md](../01-reference/ARCHITECTURE.md) - Current system architecture
- [BACKEND-FEATURE-PARITY-PLAN.md](./BACKEND-FEATURE-PARITY-PLAN.md) - Feature parity roadmap
- [WORKER-IMPLEMENTATION-PLAN.md](./WORKER-IMPLEMENTATION-PLAN.md) - Worker details

---

## Changelog

### 2025-12-11: Initial Plan
- Documented current architecture limitations
- Proposed Cloud Tasks + Cloud Run Jobs hybrid
- Outlined shared pipeline architecture
- Created implementation roadmap
