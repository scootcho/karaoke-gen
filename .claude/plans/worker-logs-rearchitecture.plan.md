# Plan: Worker Logs Rearchitecture

**Created:** 2026-01-04
**Branch:** TBD (use `/new-worktree worker-logs-subcollection`)
**Status:** Draft

## Overview

Move `worker_logs` from embedded array in job documents to a Firestore subcollection to avoid the 1MB document size limit. The current approach caused job 501258e1 to fail when logs reached 1.26 MB (98.6% of document size).

## Problem Statement

- Firestore documents have a 1 MB size limit
- `worker_logs` is stored as an array field within job documents
- Long-running jobs (especially video encoding) can generate thousands of log entries
- When the limit is exceeded, job updates fail with: `Document cannot be written because its size exceeds the maximum allowed size`

## Requirements

- [ ] Logs must remain associated with their job
- [ ] Logs should be queryable by job_id, worker type, timestamp
- [ ] Old logs should auto-cleanup (TTL: 30 days)
- [ ] Existing API endpoint (`GET /api/jobs/{id}/logs`) must continue to work
- [ ] Frontend must continue to display logs without changes
- [ ] Migration path for existing jobs (optional - can just start fresh)

## Technical Approach

### Option A: Subcollection (Recommended)
Store logs in `jobs/{job_id}/logs/{log_id}` subcollection.

**Pros:**
- Natural association with job (delete job = delete logs with cascading)
- Each log entry is its own document (no size limit concerns)
- Can add TTL via Firestore TTL policies
- Efficient queries with composite indexes

**Cons:**
- More Firestore read operations for paginated log fetching
- Slightly more complex write logic

### Option B: Separate Collection
Store logs in `job_logs` collection with `job_id` field.

**Pros:**
- Can query across all jobs
- Simpler TTL management

**Cons:**
- Orphaned logs if job deleted (need cleanup logic)
- Extra index needed for job_id queries

### Decision: Option A (Subcollection)

## Implementation Steps

### Phase 1: Backend Changes

1. [ ] **Create log entry model** - `backend/models/log.py`
   - `LogEntry` dataclass with: id, job_id, timestamp, level, worker, message, metadata
   - Keep backward compatible with existing log format

2. [ ] **Update FirestoreService** - `backend/services/firestore_service.py`
   - Add `append_log_to_subcollection(job_id, log_entry)` method
   - Add `get_logs_from_subcollection(job_id, limit, since_timestamp, worker)` method
   - Keep old `append_worker_log` temporarily for migration period

3. [ ] **Update JobManager** - `backend/services/job_manager.py`
   - Modify `add_worker_log()` to write to subcollection instead of array
   - Modify `get_worker_logs()` to read from subcollection
   - Add migration flag/env var to switch between old and new

4. [ ] **Update jobs API** - `backend/api/routes/jobs.py`
   - `GET /api/jobs/{id}/logs` - Update to read from subcollection
   - Response format stays the same (backward compatible)

5. [ ] **Add TTL configuration** - `infrastructure/__main__.py`
   - Configure Firestore TTL policy for logs subcollection (30 days)

### Phase 2: Testing

6. [ ] **Unit tests** - `backend/tests/unit/test_log_subcollection.py`
   - Test write to subcollection
   - Test read with pagination
   - Test filtering by worker type
   - Test TTL field is set correctly

7. [ ] **Integration tests** - `backend/tests/emulator/test_worker_logs_subcollection.py`
   - Test concurrent log writes from multiple workers
   - Test large log volumes (1000+ entries)
   - Test log retrieval performance

### Phase 3: Deployment & Migration

8. [ ] **Deploy with feature flag**
   - Add `USE_LOG_SUBCOLLECTION=true` env var
   - Deploy to production with flag OFF initially

9. [ ] **Enable for new jobs**
   - Turn on flag for new jobs
   - Monitor for issues

10. [ ] **Optional: Migrate existing jobs**
    - Script to move existing `worker_logs` arrays to subcollections
    - Can skip this - old jobs will use old format, new jobs use new

### Phase 4: Cleanup

11. [ ] **Remove old code path**
    - Remove `worker_logs` field from job model
    - Remove old `append_worker_log` method
    - Remove feature flag

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `backend/models/log.py` | Create | LogEntry dataclass |
| `backend/services/firestore_service.py` | Modify | Add subcollection methods |
| `backend/services/job_manager.py` | Modify | Switch to subcollection |
| `backend/api/routes/jobs.py` | Modify | Update logs endpoint |
| `backend/models/job.py` | Modify | Make worker_logs optional/deprecated |
| `backend/tests/unit/test_log_subcollection.py` | Create | Unit tests |
| `backend/tests/emulator/test_worker_logs_subcollection.py` | Create | Integration tests |
| `infrastructure/__main__.py` | Modify | Add TTL policy (if supported) |

## Log Entry Schema

```python
@dataclass
class LogEntry:
    id: str  # Auto-generated UUID
    job_id: str
    timestamp: datetime
    level: str  # "info", "warning", "error", "debug"
    worker: str  # "audio", "lyrics", "video", "render", "screens"
    message: str
    metadata: Optional[Dict[str, Any]] = None
    ttl_expiry: datetime  # For Firestore TTL (timestamp + 30 days)
```

## Firestore Structure

```
jobs/
  {job_id}/
    ... (job fields, no more worker_logs array)
    logs/  # subcollection
      {log_id}/
        timestamp: datetime
        level: string
        worker: string
        message: string
        metadata: map (optional)
        ttl_expiry: datetime
```

## API Response (Unchanged)

```json
{
  "logs": [
    {
      "timestamp": "2026-01-04T12:00:00Z",
      "level": "info",
      "worker": "video",
      "message": "Starting video generation"
    }
  ],
  "total": 150,
  "has_more": true
}
```

## Testing Strategy

- **Unit tests**: Mock Firestore, test business logic
- **Emulator tests**: Use Firestore emulator for integration tests
- **Load test**: Generate 5000+ logs for a single job, verify no size issues
- **Manual test**: Run a full job through the pipeline, verify logs appear

## Rollback Plan

1. Set `USE_LOG_SUBCOLLECTION=false` env var
2. Redeploy backend
3. New logs will go back to embedded array
4. Subcollection logs will remain but won't be read

## Open Questions

- [ ] Should we paginate logs in the API? (Currently returns all)
- [ ] What's the optimal TTL period? (30 days proposed)
- [ ] Should we index by timestamp for efficient range queries?

## Performance Considerations

- Reading logs: One query vs reading embedded array (slightly slower)
- Writing logs: Similar cost (one document write either way)
- Storage: Similar (array elements vs subcollection documents)
- Deletion: Subcollection deletes require batch delete or callable

## References

- [Firestore TTL](https://cloud.google.com/firestore/docs/ttl)
- [Firestore Subcollections](https://firebase.google.com/docs/firestore/data-model#subcollections)
- [Firestore Limits](https://firebase.google.com/docs/firestore/quotas#limits)
