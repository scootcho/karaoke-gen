# Performance Investigation: Lyrics Processing Bottlenecks

**Date**: 2026-01-08
**Job Analyzed**: 36c21ece (ABBA - Waterloo)
**Goal**: Reduce total karaoke generation time from ~30 minutes to ~10 minutes

## Executive Summary

Analysis of job 36c21ece revealed that the **lyrics transcription stage alone took 16 minutes 28 seconds** - over half the target total time. The job hadn't even reached human review yet.

Key bottlenecks identified:
1. **Langfuse callback initialization**: 201 seconds (3.3 minutes)
2. **SyllablesMatchHandler initialized twice**: 158 seconds combined
3. **Model initialization timeouts**: 300+ seconds wasted on failed parallel inits
4. **Sequential anchor search**: 38 seconds (could be parallelized)

**Estimated savings from fixes: 11+ minutes** from quick wins alone.

## Detailed Timeline Analysis

### Job 36c21ece Timeline (ABBA - Waterloo)

| Phase | Start | End | Duration | Notes |
|-------|-------|-----|----------|-------|
| Job created | 07:44:28 | - | - | |
| Workers started | 07:44:41 | - | +13s | Audio + Lyrics parallel |
| Audio separation (Modal) | 07:45:10 | 07:46:22 | **72s** | Good! |
| Stems download | 07:46:22 | 07:47:09 | 47s | 8 files |
| Stage 2 separation | 07:47:10 | 07:47:33 | 23s | |
| **Audio worker done** | - | 07:47:36 | **2m 55s total** | Good! |
| AudioShake upload+transcribe | 07:47:23 | 07:48:41 | **78s** | Waiting for API |
| SyllablesMatchHandler init #1 | 07:46:37 | - | **106s** | During OutputGenerator |
| Correction started | 07:48:42 | - | - | |
| SyllablesMatchHandler init #2 | 07:48:42 | 07:49:34 | **52s** | Second init! |
| Anchor search | 07:49:34 | 07:50:12 | **38s** | N-gram processing |
| AgenticCorrector creation | 07:50:27 | - | - | |
| Langfuse init | 07:50:27 | 07:53:48 | **201s** | 3.3 MINUTES! |
| AgenticCorrector ready | - | 07:53:57 | - | |
| Gap processing started | 07:53:58 | - | 5 parallel workers |
| Model init attempts | 07:54:05 | 07:59:14 | **~5 min** | Multiple timeouts! |
| Agentic timeout reached | - | 07:59:14 | - | 0/8 gaps corrected |
| **Lyrics worker done** | - | 08:01:09 | **16m 28s** | VERY SLOW |

### Key Observations

The audio worker completed in **2 minutes 55 seconds** - this is acceptable.

The lyrics worker took **16 minutes 28 seconds** - this is the primary bottleneck.

## Bottleneck Deep Dive

### 1. Langfuse Callback Initialization (201 seconds)

**Evidence from logs:**
```
07:50:27 [lyrics] 🤖 Creating single AgenticCorrector with model: vertexai/gemini-3-flash-preview
07:53:48 [lyrics] 🤖 Langfuse callback handler initialized for vertexai/gemini-3-flash-preview
```

**Root cause**: The `CallbackHandler()` constructor in `langfuse.langchain` makes blocking network calls to `us.cloud.langfuse.com` during initialization. In Cloud Run, network latency to external services during cold starts can be significant.

**Location**: `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/providers/model_factory.py:113`

```python
def _initialize_langfuse(self, model_spec: str) -> None:
    # This is slow on Cloud Run!
    self._langfuse_handler = CallbackHandler()
```

**Fix**: Preload Langfuse handler at container startup in FastAPI lifespan handler.

### 2. SyllablesMatchHandler Initialized Twice (158 seconds)

**Evidence from logs:**
```
07:46:37 [lyrics] Initialized SyllablesMatchHandler in 106.31s (preloaded)
07:49:34 [lyrics] Initialized SyllablesMatchHandler in 51.68s (preloaded)
```

**Root cause**: Two issues:
1. `SyllablesMatchHandler` is instantiated in multiple places (OutputGenerator and Corrector)
2. Each initialization calls `cmudict.dict()` which downloads NLTK data (~30MB) since Cloud Run's filesystem is ephemeral

**Location**: `lyrics_transcriber_temp/lyrics_transcriber/correction/handlers/syllables_match.py:75-86`

```python
def _init_nltk_resources(self):
    try:
        self.cmudict = cmudict.dict()  # Downloads if not present!
    except LookupError:
        nltk.download("cmudict")
        self.cmudict = cmudict.dict()
```

**Fix**:
1. Preload NLTK cmudict at container startup
2. Create singleton pattern for SyllablesMatchHandler

### 3. Model Initialization Timeouts (300+ seconds wasted)

**Evidence from logs:**
```
07:53:58 [lyrics] 🤖 Processing 8 gaps in parallel (max_workers=5)
07:53:59 [lyrics] 🤖 Classifying gap gap_1 (8 chars)
07:54:00 [lyrics] 🤖 Classifying gap gap_2 (23 chars)
07:54:00 [lyrics] 🤖 Classifying gap gap_3 (124 chars)
07:54:01 [lyrics] 🤖 Classifying gap gap_4 (8 chars)
07:54:02 [lyrics] 🤖 Classifying gap gap_5 (23 chars)
07:54:05 [lyrics] 🤖 Initializing model vertexai/gemini-3-flash-preview with 30.0s timeout...
...
07:59:10 [lyrics] 🤖 Classification returned error for gap gap_3: {'error': 'initialization_timeout'...
07:59:14 [lyrics] ⏰ AGENTIC TIMEOUT: Deadline exceeded after processing 0/8 gaps
```

**Root cause**: Despite having a lock in `LangChainBridge._model_init_lock`, 5 parallel threads are all attempting to initialize the model. The issue is that each `classify_gap()` call in the parallel ThreadPoolExecutor creates a NEW `LangChainBridge` instance (via the provider), so each has its own lock.

The fix from PR #232 added locking to prevent multiple threads from initializing the same LangChainBridge instance, but if multiple LangChainBridge instances are created, each will still initialize its own model.

**Location**:
- `lyrics_transcriber_temp/lyrics_transcriber/correction/agentic/providers/langchain_bridge.py:150-167`
- The issue is how `AgenticCorrector` and its provider are used in parallel

**Fix**: Ensure a single `LangChainBridge` instance is shared across all gap processing threads, not just thread-safe within one instance.

### 4. Sequential Anchor Search (38 seconds)

**Evidence from logs:**
```
07:49:42 [lyrics] 🔍 ANCHOR SEARCH: Starting sequential n-gram processing (189 lengths)
07:50:09 [lyrics] 🔍 ANCHOR SEARCH: ✅ Found 277 candidate anchors in 35.5s
```

**Root cause**: N-gram matching is done sequentially across 189 different n-gram lengths. This is CPU-bound work that could be parallelized.

**Location**: `lyrics_transcriber_temp/lyrics_transcriber/correction/anchor_sequence.py` (exact location TBD)

**Fix**: Use ThreadPoolExecutor or multiprocessing to parallelize n-gram length processing.

### 5. AudioShake API Wait (78 seconds)

**Evidence from logs:**
```
07:47:23 [lyrics] Uploading /tmp/karaoke_lyrics_36c21ece_xt55p3q_/ABBA - Waterloo... to AudioShake
07:48:41 [lyrics] All targets completed successfully
```

**Root cause**: External API - we're waiting for AudioShake to process the audio.

**Fix**: Not easily fixable. Could consider:
- Running Whisper locally on GPU as alternative
- More aggressive caching of results

## Why Cloud is 3x Slower Than Local

| Factor | Local | Cloud Run | Impact |
|--------|-------|-----------|--------|
| NLTK data | Cached on disk | Downloads each time | +100s per init |
| Langfuse init | Fast local network | Slow internet latency | +200s |
| Model init | Single process | Parallel thread contention | +300s |
| Filesystem | Persistent SSD | Ephemeral tmpfs | Slower I/O |
| Cold starts | N/A | 30-60s penalty | Variable |

## Optimization Plan

### Phase 1: Quick Fixes (Target: Same Day)

| # | Fix | Expected Savings | Effort |
|---|-----|------------------|--------|
| 1 | Preload NLTK cmudict at container startup | **158s → ~2s** | 1 hour |
| 2 | Preload Langfuse handler at container startup | **201s → ~2s** | 1 hour |
| 3 | Share single model instance across all gap threads | **300s → 0s** | 2 hours |

**Total Phase 1 savings: ~660 seconds (11 minutes)**

### Phase 2: Architecture Improvements (Target: This Week)

| # | Fix | Expected Savings | Effort |
|---|-----|------------------|--------|
| 4 | Parallelize anchor sequence search | **38s → ~10s** | 4 hours |
| 5 | Move lyrics processing to GCE VM | Eliminates cold starts | 1-2 days |

### Phase 3: Future Optimizations

| # | Approach | Impact | Effort |
|---|----------|--------|--------|
| 6 | Local Whisper transcription (GPU) | Eliminates AudioShake wait | 1 week |
| 7 | Faster audio separation models | Reduce Modal time | Research |
| 8 | Pre-warm AI model with keep-alive | Consistent fast response | 2 days |

## Implementation Details

### Fix 1: Preload NLTK at Startup

Add to `backend/services/spacy_preloader.py` (rename to `nlp_preloader.py`):

```python
import nltk
from nltk.corpus import cmudict

_preloaded_cmudict = None

def preload_nltk_resources():
    global _preloaded_cmudict
    # Ensure data is downloaded
    nltk.download('cmudict', quiet=True)
    # Load into memory
    _preloaded_cmudict = cmudict.dict()
    return _preloaded_cmudict

def get_preloaded_cmudict():
    return _preloaded_cmudict
```

### Fix 2: Preload Langfuse at Startup

Add to `backend/services/langfuse_preloader.py`:

```python
from langfuse.langchain import CallbackHandler

_preloaded_handler = None

def preload_langfuse_handler():
    global _preloaded_handler
    # Only initialize if credentials are present
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        _preloaded_handler = CallbackHandler()
    return _preloaded_handler

def get_preloaded_langfuse_handler():
    return _preloaded_handler
```

### Fix 3: Share Model Instance

Ensure `AgenticCorrector.from_model()` is called ONCE and the resulting instance is passed to all parallel gap processing threads, not created anew for each thread.

## Success Metrics

After implementing Phase 1 + Phase 2:

| Stage | Before | After | Target |
|-------|--------|-------|--------|
| Audio separation | 3 min | 3 min | - |
| Lyrics transcription | 16 min | **5 min** | < 5 min |
| Human review | Variable | Variable | - |
| Video encoding | 10 min | 10 min | - |
| **Total** | ~30 min | **~18 min** | 10 min |

Further optimization (Phase 3) needed to reach 10-minute target.

## Implementation Status

### Phase 1: Quick Fixes (Completed)

1. **NLTK Preloading** - `backend/services/nltk_preloader.py`
   - Preloads cmudict at container startup
   - SyllablesMatchHandler now uses preloaded data
   - Expected savings: **158s**

2. **Langfuse Preloading** - `backend/services/langfuse_preloader.py`
   - Preloads callback handler at container startup
   - ModelFactory now uses preloaded handler
   - Expected savings: **201s**

3. **Model Warmup** - `LangChainBridge.warmup()`
   - Added `warmup()` method for eager model initialization
   - `AgenticCorrector.from_model()` now calls warmup by default
   - Prevents 5+ parallel threads all hitting lazy init
   - Expected savings: **300s+**

### Phase 2: Architecture Improvements (Partial)

4. **Parallel Anchor Search** - `anchor_sequence.py`
   - N-gram lengths now processed in parallel using ThreadPoolExecutor
   - Added `_process_ngram_length_no_state()` for thread-safe processing
   - Configurable via `ANCHOR_SEARCH_WORKERS` env var (default: 4)
   - Can be disabled via `ANCHOR_SEARCH_SEQUENTIAL=1`
   - Expected savings: **~28s** (38s → ~10s)

5. **GCE Lyrics Processing** - Design Only (Future PR)
   - See design below

### Phase 2.2 Design: GCE Lyrics Worker

For even better performance, lyrics processing could be moved to a dedicated GCE VM
similar to the encoding worker. This eliminates Cloud Run's ephemeral filesystem
and cold start issues entirely.

#### Architecture

```text
Cloud Run (Backend)              GCE Lyrics Worker VM
┌────────────────────┐           ┌─────────────────────────┐
│ Lyrics Worker      │  HTTP     │ FastAPI Service         │
│                    │ ───────► │                         │
│ submit_lyrics_job()│           │ - NLTK pre-downloaded   │
│                    │           │ - SpaCy model cached    │
│ poll_for_result()  │ ◄─────── │ - Langfuse pre-init     │
│                    │           │ - Persistent filesystem │
└────────────────────┘           └─────────────────────────┘
```

#### Required Components

1. **Infrastructure** (Pulumi)
   - New GCE VM: `lyrics_worker_vm.py`
   - Service account with GCS access
   - Startup script for dependencies

2. **GCE Service** (`backend/services/gce_lyrics/main.py`)
   - FastAPI endpoints: `/transcribe`, `/status/{job_id}`, `/health`
   - Downloads audio from GCS, runs transcription, uploads results

3. **Client Service** (`backend/services/lyrics_service.py`)
   - Similar to `encoding_service.py`
   - Feature flag: `USE_GCE_LYRICS=1`

4. **Integration**
   - Update `lyrics_worker.py` to dispatch to GCE when enabled

#### Benefits

- **No cold starts**: VM is always running
- **Persistent filesystem**: NLTK/SpaCy models cached
- **Dedicated CPU**: No contention with other Cloud Run instances
- **Hot code updates**: Can pull latest wheel from GCS

#### Estimated Savings

With GCE lyrics worker, lyrics processing could drop from ~5 min to ~2-3 min
by eliminating all initialization overhead.

## References

- [LESSONS-LEARNED.md - Thread-Safe Lazy Initialization](../LESSONS-LEARNED.md#thread-safe-lazy-initialization-in-shared-components)
- [LESSONS-LEARNED.md - Preloading Heavy Resources](../LESSONS-LEARNED.md#preloading-heavy-resources-at-container-startup)
- [LESSONS-LEARNED.md - Reuse LLM Model Instances](../LESSONS-LEARNED.md#reuse-llm-model-instances-across-operations)
- PR #232: Thread-safe locking for LangChainBridge
- PR #233: SpaCy model preloading
