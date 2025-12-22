# Backend Testing Gaps Analysis

**Created:** 2025-12-22  
**Updated:** 2025-12-22  
**Status:** Mostly Complete ✅  
**Priority:** High

## Background

During end-to-end testing of the remote karaoke-gen CLI, a bug was discovered:

```
Error: 'AudioSearchResult' object has no attribute 'extra_info'
```

This bug existed in production code but wasn't caught by automated tests because the remote download code path had no test coverage.

## Root Cause Analysis

1. **Missing remote code path tests**: The download routing logic for `provider in ["Redacted", "OPS"]` was never exercised
2. **State not set up for remote scenario**: Tests never configured `_remote_search_id` and `_remote_client` together  
3. **`FlacfetchClient` had zero tests**: The entire HTTP client was untested
4. **Tests mocked at wrong level**: Tests mocked `service._fetcher` completely, bypassing the routing logic

## Services Testing Status

### ✅ Fully Tested

| Service | Test File | Test Count | Notes |
|---------|-----------|------------|-------|
| `credential_manager.py` | `test_credential_manager.py` | 27 | Good coverage |
| `job_manager.py` | `test_job_manager.py` | 15 | Good coverage |
| `flacfetch_client.py` | `test_flacfetch_client.py` | 26 | **Added 2025-12-22** |
| `audio_search_service.py` | `test_audio_search.py` | 39 | **+7 tests 2025-12-22** |
| `storage_service.py` | `test_storage_service.py` | 17 | **Added 2025-12-22** |
| `audio_analysis_service.py` | `test_audio_analysis_service.py` | 9 | **Added 2025-12-22** |
| `audio_editing_service.py` | `test_audio_editing_service.py` | 13 | **Added 2025-12-22** |
| `youtube_service.py` | `test_youtube_service.py` | 12 | **Added 2025-12-22** |
| `dropbox_service.py` | `test_dropbox_service.py` | 14 | **Added 2025-12-22** |
| `gdrive_service.py` | `test_gdrive_service.py` | 13 | **Added 2025-12-22** |

### ❌ No Dedicated Test File (Lower Priority)

| Service | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| `rclone_service.py` | Low | Low | Wrapper around rclone CLI |
| `firestore_service.py` | Low | Medium | Firestore operations |
| `auth_service.py` | Low | Low | Auth utilities |
| `job_logging.py` | Low | Low | Logging utilities |
| `tracing.py` | Low | Low | OpenTelemetry setup |
| `worker_service.py` | Medium | High | Worker orchestration |

## Implementation Plan

### Phase 1: Core Audio Services (High Priority) ✅

- [x] `flacfetch_client.py` - Remote audio download client
- [x] `audio_search_service.py` - Remote download path tests

### Phase 2: Audio Processing Services (High Priority) ✅

- [x] `audio_analysis_service.py` - Waveform analysis, peak detection
- [x] `audio_editing_service.py` - Mute regions, audio manipulation

### Phase 3: Distribution Services (Medium Priority) ✅

- [x] `youtube_service.py` - YouTube credential management
- [x] `dropbox_service.py` - Dropbox upload API
- [x] `gdrive_service.py` - Google Drive upload API
- [x] `storage_service.py` - GCS operations

### Phase 4: Infrastructure Services (Low Priority)

- [ ] `worker_service.py` - Worker orchestration
- [ ] `firestore_service.py` - Firestore operations
- [ ] `rclone_service.py` - Rclone wrapper
- [ ] `auth_service.py` - Auth utilities
- [ ] `job_logging.py` - Logging
- [ ] `tracing.py` - Tracing

## Test Coverage Goals

- **Target:** 80%+ line coverage for high-priority services
- **Minimum:** Key code paths tested (happy path + error handling)
- **Integration:** Mock external APIs (YouTube, Dropbox, GCS, etc.)

## Testing Patterns to Follow

### 1. Mock External Services

```python
@patch("backend.services.youtube_service.build")
def test_upload_video(self, mock_build):
    mock_service = Mock()
    mock_build.return_value = mock_service
    # ...
```

### 2. Test Error Handling

```python
def test_upload_handles_network_error(self):
    with pytest.raises(ServiceError) as exc_info:
        service.upload(...)
    assert "network" in str(exc_info.value).lower()
```

### 3. Test State Transitions

```python
def test_download_routes_to_remote_for_torrent_providers(self):
    service._remote_client = Mock()
    service._remote_search_id = "search_123"
    service._cached_results = [result_with_provider_redacted]
    
    service.download(0, "/tmp")
    
    service._download_remote.assert_called_once()
```

### 4. Verify Request/Response Format

```python
def test_search_sends_correct_payload(self):
    # ...
    call_args = mock_client.post.call_args
    assert call_args.kwargs["json"] == {"artist": "ABBA", "title": "Waterloo"}
```

## Files Changed

**Bug Fix:**
- `backend/services/audio_search_service.py` - Removed `extra_info` attribute access

**Tests Added (2025-12-22):**
- `backend/tests/test_audio_search.py` - +7 tests for remote download path
- `backend/tests/test_flacfetch_client.py` - 26 new tests (new file)
- `backend/tests/test_storage_service.py` - 17 new tests (new file)
- `backend/tests/test_audio_analysis_service.py` - 9 new tests (new file)
- `backend/tests/test_audio_editing_service.py` - 13 new tests (new file)
- `backend/tests/test_youtube_service.py` - 12 new tests (new file)
- `backend/tests/test_dropbox_service.py` - 14 new tests (new file)
- `backend/tests/test_gdrive_service.py` - 13 new tests (new file)

**Total New Tests:** 111 tests added

**Version:** 0.74.2

## Running Tests

```bash
# All backend tests
cd backend && python -m pytest tests/ -v

# Specific service tests
python -m pytest tests/test_flacfetch_client.py -v
python -m pytest tests/test_audio_search.py -v

# With coverage
python -m pytest tests/ -v --cov=services --cov-report=term-missing
```

## Notes for Future Sessions

When continuing this work:

1. Start with `audio_analysis_service.py` and `audio_editing_service.py` - they're core to the pipeline
2. Distribution services need OAuth mocking - check existing patterns in `test_credential_manager.py`
3. Use `pytest.mark.asyncio` for async service methods
4. Follow existing test patterns in `test_flacfetch_client.py` for HTTP client mocking

