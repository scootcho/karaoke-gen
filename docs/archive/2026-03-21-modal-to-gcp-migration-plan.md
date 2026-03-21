# Modal to GCP Audio Separation Migration Plan

**Date:** 2026-03-21
**Status:** Planning seed (not yet started)
**Priority:** Medium - reduces external dependency risk and cost

## Why Migrate

1. **Reliability** - Modal API intermittently fails to return stem files ("no files were downloaded" errors), causing job failures that require manual retries.
2. **Latency** - Round-trip to Modal (upload audio, wait for GPU separation, download stems) adds network overhead. Local GCP processing eliminates cross-provider data transfer.
3. **Cost** - Modal charges for GPU compute on their platform. GCP GPU VMs or spot instances may be cheaper, especially with sustained use discounts.
4. **Dependency reduction** - Modal is the only third-party compute dependency. Removing it means the entire pipeline runs within GCP.

## Current State

### How Modal Is Used

The audio worker (`backend/workers/audio_worker.py`) runs on Cloud Run and calls Modal via the `audio-separator[remote]` Python package:

1. Cloud Run audio worker downloads the source audio from GCS
2. `AudioProcessor.process_audio_separation()` checks `AUDIO_SEPARATOR_API_URL` env var
3. Calls `AudioSeparatorAPIClient.separate_audio()` which POSTs the audio file to Modal's HTTP API
4. Modal runs GPU separation and returns stem files
5. Worker downloads stems, post-processes, and uploads to GCS

**API endpoint:** `https://nomadkaraoke--audio-separator-api.modal.run`
**Configured in:** `infrastructure/modules/cloud_run.py` (env var on Cloud Run service)

### Models Used

- **Stage 1 (Clean instrumental):** `model_bs_roformer_ep_317_sdr_12.9755.ckpt` (BS-Roformer)
- **Stage 1 (Other stems):** `htdemucs_6s.yaml` (Demucs 6-stem)
- **Stage 2 (Backing vocals):** `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` (Mel-Band Roformer)

### Processing Time

- Stage 1: ~3-5 minutes
- Stage 2: ~2-3 minutes
- Total audio worker timeout: 30 minutes (includes download/upload overhead)

### Existing GCP Infrastructure

- **Encoding worker VM** (`c4d-highcpu-32`, `us-central1-c`) - CPU-only, handles video encoding
- Packer-based image build, GCS-based deployment (wheel + startup.sh)
- Pulumi IaC in `infrastructure/`
- The `audio-separator` package already supports local processing (just needs GPU + models)

## Target State

Run audio separation on a GCP GPU VM instead of Modal. The `audio-separator` package already supports both local and remote modes - we just need to point it at our own GPU endpoint (or run locally on the GPU VM).

## Options

### Option A: Dedicated GCE GPU VM (Recommended)

Similar pattern to the encoding worker. A persistent VM with GPU that runs the audio-separator API.

- **Pros:** Simple, mirrors existing encoding worker pattern, models stay loaded in memory, fast cold start after first load
- **Cons:** Pays for GPU even when idle, need to handle scaling
- **GPU:** NVIDIA T4 (~$0.35/hr) or L4 (~$0.70/hr) sufficient for these models
- **Cost estimate:** T4 spot instance ~$100-150/month if running 24/7 (vs Modal pay-per-use)

### Option B: GCE Spot GPU VM (Start/Stop)

Same as A but stop the VM when not processing, start on demand.

- **Pros:** Only pay when processing, cheapest option
- **Cons:** Cold start (VM boot + model loading ~2-5 min), spot can be preempted, more complex orchestration
- **Best if:** Job volume is low/bursty

### Option C: Cloud Run Jobs with GPU

Cloud Run now supports GPU (L4) for jobs.

- **Pros:** Serverless, auto-scaling, no idle cost, Cloud Run already used for other workers
- **Cons:** GPU availability can be limited, cold start on each job, 1-hour max timeout, model download on each cold start unless cached
- **Cost estimate:** Pay only for job duration, but model loading adds per-job overhead

### Option D: Run Locally on Audio Worker (Cloud Run)

Run separation directly in the Cloud Run audio worker with a GPU.

- **Pros:** Simplest code change (just remove AUDIO_SEPARATOR_API_URL, models load locally)
- **Cons:** Cloud Run GPU instances are expensive if kept warm, model loading on cold start

## Recommendation

**Option A (dedicated GCE GPU VM)** for initial migration, with a path to Option B if cost is a concern.

Rationale:
- Mirrors the proven encoding worker pattern (Packer image, GCS deploy, Pulumi)
- Models stay loaded = fast separation with no cold start penalty
- Simplest to implement and debug
- Can add start/stop automation later (Option B) if idle cost is too high

## Key Considerations

- **Model storage:** ~2-3 GB total for the three models. Bake into Packer image or download on first start to a persistent disk.
- **GPU memory:** These models fit comfortably in a T4 (16 GB VRAM). L4 (24 GB) provides headroom.
- **API compatibility:** Can reuse the existing `AudioSeparatorAPIClient` by running the audio-separator API server on the GCE VM and updating `AUDIO_SEPARATOR_API_URL` to point to it.
- **Fallback:** Keep Modal config as a fallback during migration. The `AUDIO_SEPARATOR_API_URL` env var swap makes this easy.
- **Networking:** VM needs to accept requests from Cloud Run audio worker. Use internal networking or IAP + auth token (same pattern as encoding worker).

## Migration Steps (High Level)

1. **Spike:** Run audio-separator API server locally with GPU, verify it produces identical output to Modal
2. **Infrastructure:** Create Pulumi resources for GPU VM (instance, disk, firewall, service account) - copy encoding worker pattern
3. **Packer image:** Build image with CUDA, Python, audio-separator, pre-downloaded models
4. **Deploy & test:** Stand up VM, point a test job at it, compare output quality and timing
5. **Cutover:** Update `AUDIO_SEPARATOR_API_URL` in Cloud Run config to point to GCE VM
6. **Monitor:** Watch for errors/quality issues for a week
7. **Decommission:** Remove Modal deployment, remove `audio-separator-api-url` secret, clean up Modal account

## Files to Modify (When Implementing)

- `infrastructure/compute/` - New GPU VM module (similar to `encoding_worker_vm.py`)
- `infrastructure/packer/` - New Packer template for GPU image
- `infrastructure/modules/cloud_run.py` - Update `AUDIO_SEPARATOR_API_URL` value
- `infrastructure/__main__.py` - Wire up new resources
- `infrastructure/config.py` - Add GPU VM machine type/zone constants
- No backend code changes needed if we keep the HTTP API interface
