# Cloud Run Concurrency Optimization Investigation

**Date:** February 11, 2026
**Status:** Investigation in progress
**Potential Savings:** $2,400-3,000/month (75% reduction in Cloud Run costs)

## Current Configuration

```yaml
Service: karaoke-backend
CPU: 8 cores
Memory: 16Gi
Concurrency: 1 request per instance
Min Instances: 4 (always running)
Max Instances: 50
Timeout: 1800s (30 min)
CPU Throttling: Disabled
CPU Boost: Enabled

Monthly Cost: ~$3,200
```

## Problem Statement

Current configuration is extremely wasteful:
- `concurrency=1` forces one request per instance → requires many instances
- `min-instances=4` keeps 4 idle instances running 24/7 → $2,300/month idle cost
- High CPU/RAM allocation may be unnecessary after GCE encoding worker was added

## Architecture Analysis

### Two-Stage Video Processing

**Stage 1: Render (Cloud Run - render_video_worker)**
```
render_video_worker:
  Input: Corrected lyrics + audio file
  Process: OutputGenerator → video.py → FFmpeg (libx264)
  Output: with_vocals.mkv (intermediate file)
  CPU: Medium-high (FFmpeg encoding)
  Duration: ~30-120 seconds
```

**Stage 2: Final Encoding (GCE - video_worker → encoding worker)**
```
video_worker (Cloud Run):
  Input: with_vocals.mkv
  Process: Delegates to GCE encoding worker
  Output: Final .mp4 files

encoding_worker (GCE c4d-highcpu-32):
  Input: with_vocals.mkv from GCS
  Process: FFmpeg final encoding (high-performance)
  Output: Multiple formats (.mp4, .mkv)
  CPU: Very high (32 cores, dedicated)
  Duration: ~60-300 seconds
```

### Key Insight

The **heaviest** encoding (final video) runs on GCE, not Cloud Run. However, Cloud Run still runs FFmpeg for the intermediate render step.

## Investigation Questions

### Q1: Why was `concurrency=1` set?

**Git History:**
- Added in commit `ea1c6598` (Dec 28, 2025)
- Commit message: "Replace Cloud Build with GitHub Actions"
- **No explanation for concurrency=1** in commit message
- Appears to have been cargo-culted from somewhere

**Hypothesis:** May have been set conservatively without testing, or copied from example config.

### Q2: What actually runs on Cloud Run?

**Worker Breakdown:**

| Worker | CPU Usage | Memory Usage | Can Run Concurrent? |
|--------|-----------|--------------|---------------------|
| `audio_worker` | Low (API calls to Modal/AudioShake) | Low (~512MB) | ✅ Yes |
| `lyrics_worker` | Low (API calls, Whisper on Modal) | Low (~1GB) | ✅ Yes |
| `screens_worker` | Low (text processing) | Low (~512MB) | ✅ Yes |
| `render_video_worker` | Medium-High (FFmpeg) | Medium (~4-6GB) | ⚠️ Test needed |
| `video_worker` | Low (delegates to GCE) | Low (~1GB) | ✅ Yes |

**Critical:** Only `render_video_worker` is CPU/memory intensive on Cloud Run.

### Q3: Can we increase concurrency safely?

**Test Plan:**

1. **Profile current usage:**
```bash
# Get actual CPU/memory usage from Cloud Monitoring
gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/container/memory/utilizations"
            AND resource.labels.service_name="karaoke-backend"' \
  --format="table(points[0].value.doubleValue)" \
  --aggregate-by-period=1h

gcloud monitoring time-series list \
  --filter='metric.type="run.googleapis.com/container/cpu/utilizations"
            AND resource.labels.service_name="karaoke-backend"' \
  --format="table(points[0].value.doubleValue)" \
  --aggregate-by-period=1h
```

2. **Check request patterns:**
```bash
# How many concurrent render jobs typically run?
gcloud logging read 'resource.type="cloud_run_revision"
  AND resource.labels.service_name="karaoke-backend"
  AND textPayload=~"render_video_worker"' \
  --limit=100 \
  --freshness=24h \
  --format=json | jq '.[] | .timestamp' | sort | uniq -c
```

3. **Identify peak memory usage:**
```bash
# Check for OOM errors
gcloud logging read 'resource.type="cloud_run_revision"
  AND resource.labels.service_name="karaoke-backend"
  AND (textPayload=~"memory" OR textPayload=~"OOM")' \
  --limit=50 \
  --freshness=7d
```

4. **Test incremental changes in staging:**
```yaml
# Proposed staging config
concurrency: 4           # Start with 4 (vs 1)
cpu: 4                   # Reduce from 8
memory: 8Gi              # Reduce from 16Gi
min-instances: 1         # Reduce from 4
```

### Q4: What's the actual render duration?

**Check logs:**
```bash
gcloud logging read 'resource.type="cloud_run_revision"
  AND textPayload=~"WORKER_END.*render_video_worker"' \
  --limit=20 \
  --freshness=24h \
  --format="value(textPayload)" | grep -oP "duration=\K[0-9.]+"
```

Expected: 30-120 seconds for typical song.

## Proposed Optimization Strategy

### Phase 1: Data Collection (1-2 days)

**Actions:**
1. ✅ Review git history for concurrency rationale → **DONE: No rationale found**
2. ⬜ Profile actual CPU/memory usage patterns
3. ⬜ Analyze concurrent request patterns
4. ⬜ Check for any OOM errors in logs
5. ⬜ Document render_video_worker duration distribution

**Deliverable:** Metrics report showing actual resource usage vs allocated.

### Phase 2: Staging Test (3-5 days)

**Test Configuration:**
```yaml
# Staging environment test
concurrency: 4              # 4x improvement
cpu: 4                      # 50% reduction
memory: 8Gi                 # 50% reduction
min-instances: 1            # 75% reduction
max-instances: 20           # Reduce from 50
timeout: 1800               # Keep same
cpu-boost: true             # Keep enabled
no-cpu-throttling: true     # Keep disabled
```

**Test Cases:**
1. Single render job → verify completes successfully
2. 4 concurrent render jobs → check for OOM or timeouts
3. 10 concurrent jobs → stress test
4. Monitor staging logs for errors

**Success Criteria:**
- ✅ No OOM errors
- ✅ No timeouts
- ✅ Render duration within 20% of baseline
- ✅ No quality degradation

**Rollback Plan:**
If tests fail, revert to current config and document root cause.

### Phase 3: Production Gradual Rollout (1 week)

**Week 1: Conservative Start**
```yaml
concurrency: 2              # 2x improvement (conservative)
min-instances: 2            # 50% reduction
# Keep CPU/memory same initially
```

**Monitor for 48 hours:**
- Error rates
- Request latency
- Instance count
- OOM events

**Week 2: Increase if successful**
```yaml
concurrency: 4              # 4x improvement
min-instances: 1            # 75% reduction
cpu: 6                      # 25% reduction
memory: 12Gi                # 25% reduction
```

**Week 3: Final optimization**
```yaml
concurrency: 4-8            # Based on data
min-instances: 0-1          # Based on traffic patterns
cpu: 4-6                    # Based on profiling
memory: 8-12Gi              # Based on profiling
```

## Cost Impact Analysis

### Scenario A: Conservative (concurrency=2, min=2, same CPU/RAM)
- **Reduction:** ~30% instance hours
- **Savings:** ~$960/month
- **Risk:** Very low

### Scenario B: Moderate (concurrency=4, min=1, CPU=6, RAM=12Gi)
- **Reduction:** ~60% cost
- **Savings:** ~$1,920/month
- **Risk:** Low (if tests pass)

### Scenario C: Aggressive (concurrency=8, min=0, CPU=4, RAM=8Gi)
- **Reduction:** ~75% cost
- **Savings:** ~$2,400/month
- **Risk:** Medium (needs thorough testing)

## Open Questions

1. **Why was concurrency=1 originally set?**
   - ⬜ Check Slack/Discord history
   - ⬜ Ask team members who worked on it
   - ⬜ Review any production incidents around that time

2. **Are there any workers that truly can't run concurrently?**
   - ⬜ Code review for global state, file locks, etc.
   - ⬜ Check for any database transaction issues

3. **What's the p95/p99 memory usage?**
   - ⬜ Query Cloud Monitoring for percentiles
   - ⬜ Identify if 16Gi is truly needed or over-provisioned

4. **Can render_video_worker be offloaded to GCE too?**
   - Alternative: Move ALL FFmpeg to GCE (both render + final encode)
   - Would allow Cloud Run to be much smaller
   - Tradeoff: More complexity, longer cold starts

## Next Steps

**Immediate (Today):**
1. Run data collection queries above
2. Document actual usage patterns
3. Create metrics dashboard

**This Week:**
1. Set up staging environment with test config
2. Run concurrent job tests
3. Review results with team

**Next Week:**
1. If tests pass: Create PR with gradual rollout plan
2. Deploy Phase 1 (conservative) to production
3. Monitor for 48 hours

**Decision Point:**
After data collection, decide between:
- **Option A:** Optimize existing Cloud Run config (this doc)
- **Option B:** Move render to GCE too (bigger change, more savings)

## References

- Current config: `.github/workflows/ci.yml` lines 1229-1246
- Render worker: `backend/workers/render_video_worker.py`
- Video worker: `backend/workers/video_worker.py`
- GCE encoding: `backend/services/gce_encoding/main.py`
- Cost doc: `docs/GCP-COST-OPTIMIZATION.md`

## Owner

**Assigned to:** Claude Code Agent
**Reviewer:** @beveradb
**Timeline:** 1-2 weeks

---

*Last updated: February 11, 2026*
