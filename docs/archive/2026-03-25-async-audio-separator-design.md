# Async Audio Separator Architecture

**Date:** 2026-03-25
**Status:** Design approved, pending implementation
**Repos:** python-audio-separator (primary), karaoke-gen (dependency bump)

## Problem

The Cloud Run GPU audio separator service (`/separate` endpoint in `deploy_cloudrun.py`) processes requests **synchronously** — it `await`s `run_in_executor()` and blocks the HTTP response until separation completes. The client (`AudioSeparatorAPIClient.separate_audio()`) has a hardcoded `timeout=300` (5 minutes) on the POST request.

Ensemble presets on large WAV files take >5 minutes, so the client times out before the server finishes. This was observed on job `45f9bbc0` after the 413 fix (GCS URI passthrough) was shipped.

Additionally, there is no GPU concurrency protection — multiple concurrent requests could OOM the L4's 24GB VRAM, and the in-memory job status store prevents multi-instance scaling.

## Context

The server already has `/status/{task_id}` and `/download/{task_id}/{file_hash}` endpoints, and the client already has polling logic in `separate_audio_and_wait()`. These were designed for async operation but are never exercised because the POST blocks until completion.

**Current flow (broken for long jobs):**
1. karaoke-gen audio worker calls `audio_processor._process_audio_separation_remote()`
2. `AudioSeparatorAPIClient.separate_audio_and_wait()` calls `separate_audio()` which POSTs to `/separate`
3. Cloud Run `/separate` blocks (awaits executor) until separation finishes
4. POST response contains completed result — client never enters polling loop
5. If separation takes >300s, client POST times out

**Key files:**
- `python-audio-separator/audio_separator/remote/deploy_cloudrun.py` — server endpoint (line 367-518)
- `python-audio-separator/audio_separator/remote/api_client.py` — client (line 30-168 POST, line 172-399 polling)
- `karaoke-gen/karaoke_gen/audio_processor.py` — orchestration (line 310-477)
- `karaoke-gen/backend/workers/audio_worker.py` — worker (line 259-504)

## Design

### 1. Server-side async separation

**Change in `deploy_cloudrun.py`**: Replace `await loop.run_in_executor(...)` with fire-and-forget. Return immediately with the "submitted" status.

Before:
```python
await loop.run_in_executor(None, lambda: separate_audio_sync(...))
return job_status_store.get(task_id, ...)  # blocks until done, returns completed result
```

After:
```python
loop.run_in_executor(None, lambda: separate_audio_sync(...))
# Return immediately — client will poll /status/{task_id}
return {"task_id": task_id, "status": "submitted", ...}
```

The `job_status_store` is already set to `"submitted"` before the executor call (line 456), so the immediate response is correct. The background thread updates status as processing progresses.

### 2. Job status in Firestore

Replace the in-memory `job_status_store` dict with Firestore to support multi-instance scaling.

**Collection:** `audio_separation_jobs` (in the existing `nomadkaraoke` Firestore instance)

**Document schema** (keyed by `task_id`):
```
{
  "task_id": str,
  "status": str,          # submitted | queued | processing | completed | error
  "progress": int,        # 0-100
  "original_filename": str,
  "models_used": list[str],
  "total_models": int,
  "current_model_index": int,
  "files": dict,          # hash -> filename mapping
  "error": str | null,
  "created_at": timestamp,
  "updated_at": timestamp,
  "instance_id": str      # for debugging which instance processed the job
}
```

**Status transitions:**
- `submitted` — POST accepted, returned to client immediately
- `queued` — waiting for GPU semaphore (another job is using the GPU on this instance)
- `processing` — actively running on GPU
- `completed` — separation done, output files uploaded to GCS
- `error` — separation failed

The client polling loop already treats anything that isn't "completed" or "error" as "keep polling", so the new intermediate statuses are transparent to the client.

**Dependencies:** `google-cloud-firestore` and `google-cloud-storage` are already in the Docker image.

### 3. Output files on GCS

Separation output files are written to local disk during processing (required by the separator library), then uploaded to GCS on completion.

- **Bucket:** `gs://nomadkaraoke-audio-separator-outputs/{task_id}/`
- **`/download/{task_id}/{file_hash}`** serves from GCS instead of local disk — any instance can serve downloads
- **Cleanup:** GCS lifecycle policy deletes files after 1 hour
- **Startup cleanup:** Wipe local `STORAGE_DIR/outputs/` on server start (any in-flight jobs from a previous instance are lost)

### 4. GPU concurrency protection

A `threading.Semaphore(1)` serializes GPU access per instance. Acquired at the start of `separate_audio_sync()`, released when done.

Jobs that arrive while the GPU is busy queue in the thread pool. Their Firestore status shows `"queued"` until the semaphore is acquired, then transitions to `"processing"`.

### 5. Scaling model

- **Per instance:** `Semaphore(1)` — one GPU job at a time per L4
- **Cloud Run concurrency:** ~50 per instance (polling/download requests flow while GPU is busy)
- **`max_instances`:** 10 (expandable as demand grows — supports 10 concurrent separations)
- **`min_instances`:** 0 (scale to zero when idle — GPU instances are ~$1/hr)
- **No session affinity needed** — Firestore + GCS means any instance can handle any request

Cloud Run auto-scales based on request load. With concurrency=50, a single instance can handle 1 GPU job + many polling/download requests. When a second separation request arrives and the first instance's GPU is busy, Cloud Run scales to a second instance.

### 6. Client-side POST timeout

Reduce POST timeout from 300s to 60s in `api_client.py`. The POST now only needs to upload a file or send a GCS URI and get back a task_id. For GCS URI (the common path), this completes in seconds.

No other client changes needed — `separate_audio_and_wait()` polling already handles async responses correctly.

### 7. Job cleanup

- **GCS lifecycle policy:** Delete output files after 1 hour
- **Firestore TTL:** Mark completed/errored jobs for deletion after 1 hour via `updated_at` field
- **Startup cleanup:** Wipe local `STORAGE_DIR/outputs/` on container start
- **Lazy sweep:** Before starting a new job, delete any local temp files from previous jobs on this instance

## Cross-repo changes

### python-audio-separator (primary)

| File | Change |
|------|--------|
| `audio_separator/remote/deploy_cloudrun.py` | Async endpoint, Firestore job store, GCS output upload, GPU semaphore, job cleanup |
| `audio_separator/remote/api_client.py` | Reduce POST timeout from 300s to 60s |
| Tests | New tests for async behavior, Firestore store, GCS upload |

### karaoke-gen (dependency bump only)

| File | Change |
|------|--------|
| `pyproject.toml` | Bump audio-separator version |
| No code changes | Existing polling logic already handles async flow |

### Infrastructure (karaoke-gen Pulumi)

| File | Change |
|------|--------|
| `infrastructure/modules/audio_separator_service.py` | Set concurrency=50, configure max_instances |
| GCS | Create `nomadkaraoke-audio-separator-outputs` bucket with 1-hour lifecycle policy |

## Deployment order

1. Ship python-audio-separator changes, build and deploy Cloud Run GPU service
2. Create GCS bucket and lifecycle policy
3. Bump dependency in karaoke-gen, deploy

**Backward compatibility:** The changes are backward-compatible in both directions:
- Old sync server + new client: POST blocks, returns completed, client skips polling (works)
- New async server + old client: POST returns fast, old client's 300s timeout is fine, polling kicks in (works)
- New async server + new client: POST returns fast with 60s timeout, polling kicks in (optimal)

No deployment race condition.

## Not in scope

- **Stage 1/Stage 2 parallelism:** Stage 2 depends on Stage 1's mixed vocals output. Cannot parallelize within a single job.
- **Env var consolidation:** Tracked separately in `docs/task-consolidate-env-var-config.md`
- **Model caching/singleton:** Each separation creates fresh Separator instances. Optimization for later if needed.
