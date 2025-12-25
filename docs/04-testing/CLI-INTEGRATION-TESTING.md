# CLI + Backend Integration Testing

## The Problem

We had multiple bugs that unit tests didn't catch:
- Content-type mismatch in signed URL uploads (403 errors)
- Style file path handling issues

These bugs required:
1. Full CI/CD deploy (~12 min)
2. Full karaoke generation (~10 min)
3. Manual inspection of logs

**Total: 20+ minutes per iteration** 😱

## The Solution

New **CLI + Backend Integration Tests** that:
- Run the ACTUAL CLI code against a LOCAL backend
- Use GCP emulators (Firestore + GCS) 
- Test the full signed URL upload flow
- Run in **< 30 seconds**

## Test Architecture

```
┌─────────────────────────────────────┐
│   Unit Tests (Mocked)               │  ← Fast, isolated
│   tests/unit/                       │     ~0.5s, 100+ tests
├─────────────────────────────────────┤
│   Backend Emulator Tests            │  ← Backend-only integration
│   backend/tests/emulator/           │     ~2s, 11 tests
├─────────────────────────────────────┤
│   CLI + Backend Integration Tests   │  ← NEW! Full flow
│   tests/integration/                │     ~20s, catches real bugs
│   test_cli_backend_integration.py   │
├─────────────────────────────────────┤
│   Cloud Integration Tests           │  ← Against deployed backend
│   backend/tests/test_api_integration│     ~10min, pre-prod only
└─────────────────────────────────────┘
```

## Quick Start

### Run All Integration Tests

```bash
./scripts/run-cli-integration-tests.sh
```

This automatically:
1. Starts GCP emulators
2. Starts local backend
3. Runs tests
4. Cleans up

### Interactive Development Mode

```bash
# Terminal 1: Start environment
./scripts/start-local-test-env.sh

# Terminal 2: Run specific tests repeatedly
pytest tests/integration/test_cli_backend_integration.py -v -k "test_style_params"
```

## What These Tests Catch

### ✅ Content-Type Mismatches
```python
def test_style_params_json_upload(self, test_style_files, cli_config):
    """Test uploading style_params.json via signed URL."""
    # This would have caught the Path('.json').suffix bug!
    result = client.search_audio(
        artist="Test Artist",
        title="Test Song",
        style_params_path=test_style_files['style_params_path'],
    )
    # If we get 403, the test fails with a clear message
```

### ✅ Request/Response Format Mismatches
Tests verify CLI and backend agree on API contract.

### ✅ GCS Path Issues  
Uploads go to real (emulated) GCS, catches path/encoding bugs.

### ✅ Auth Token Handling
Tests run with actual token flow.

## When to Run

| Situation | Run This |
|-----------|----------|
| Quick check before commit | `./scripts/run-emulator-tests.sh` |
| Testing CLI changes | `./scripts/run-cli-integration-tests.sh` |
| Testing backend API changes | `./scripts/run-cli-integration-tests.sh` |
| Before creating PR | Both of the above |
| Pre-production | Cloud integration tests |

## Test Files

### `tests/integration/test_cli_backend_integration.py`

Key test classes:
- `TestSignedUrlUploadRoundTrip` - Full upload flow
- `TestContentTypeMatching` - Catches the specific bug
- `TestAudioSearchWithStyles` - API contract tests

### Test Fixtures

- `test_style_files` - Creates minimal valid PNG/TTF/JSON files
- `cli_config` - Points CLI at local backend

## Extending Tests

### Adding a New Integration Test

```python
class TestMyNewFeature:
    def test_my_feature(self, cli_config, tmp_path):
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient, RemoteConfig
        import logging
        
        config = RemoteConfig(
            service_url=cli_config['service_url'],
            auth_token=cli_config['auth_token'],
            environment='test'
        )
        client = RemoteKaraokeClient(config, logging.getLogger("test"))
        
        # Test your feature
        result = client.some_method(...)
        assert result['expected_field'] == expected_value
```

## Prerequisites

1. **Docker** (for fake-gcs-server)
2. **gcloud CLI** with Firestore emulator:
   ```bash
   gcloud components install cloud-firestore-emulator
   ```

## Troubleshooting

### "Emulators not running"
```bash
./scripts/start-emulators.sh
```

### "Backend failed to start"
Check if port 8000 is already in use:
```bash
lsof -i :8000
```

### Tests pass locally but fail in CI
The integration tests require Docker, which may not be available in all CI environments. Consider:
- Running in a CI job with Docker support
- Skipping in CI and running locally before merge

## Benefits

| Before | After |
|--------|-------|
| 20+ min per iteration | < 30 sec per iteration |
| Manual log inspection | Automated assertions |
| Bugs found in production | Bugs caught locally |
| Expensive cloud resources | Free local emulators |

