# Lessons Learned

Key insights for future AI agents working on this codebase.

## Architecture Decisions

### LyricsTranscriber: Library, Not Server

**Problem**: LyricsTranscriber's `ReviewServer` blocks waiting for human input - incompatible with async cloud architecture.

**Solution**: Use LyricsTranscriber as a library:
- Call `transcribe()` and `correct()` for processing
- Save `corrections.json` to GCS
- Skip `ReviewServer` entirely
- Call `OutputGenerator` only after human review completes

**What to use**: `LyricsTranscriber`, `CorrectionResult`, `OutputGenerator`, `OutputConfig`, `CorrectionOperations`

**What NOT to use**: `ReviewServer`, `server.start()`, blocking waits

### Video Generation Timing

**Wrong**: Generate video during lyrics worker, then review
**Right**: Lyrics worker saves JSON → Human reviews → Render worker generates video

Video must include human-corrected lyrics, so generation happens AFTER review.

### Parallel Processing

Audio separation and lyrics transcription run in parallel:
- Both can fail independently
- Progress tracked separately in `state_data`
- Screens generation waits for both to complete

## Common Gotchas

### Pydantic Model Fields

**Problem**: Setting a field that doesn't exist in the Pydantic model silently does nothing.

```python
# BAD - fails silently if field doesn't exist
job.input_media_gcs_path = "path/to/file"

# GOOD - explicit field in model
class Job(BaseModel):
    input_media_gcs_path: Optional[str] = None
```

**Lesson**: Always verify Pydantic model has the field before setting it.

### Styles Configuration

ASS subtitle generator requires ALL style fields present and properly typed:

```python
required_fields = [
    "font", "font_path", "ass_name",  # ass_name often missed
    "primary_color", "secondary_color", "outline_color", "back_color",
    "bold", "italic", "underline", "strike_out",
    "scale_x", "scale_y", "spacing", "angle",
    "border_style", "outline", "shadow",
    "margin_l", "margin_r", "margin_v", "encoding"
]

# Critical: font_path must be string, not None
"font_path": ""  # Correct
"font_path": None  # Causes ASS writer to fail
```

### Frontend Data Format

The React review UI sends partial correction data:

```python
# Frontend sends:
{"corrections": [...], "corrected_segments": [...]}

# Backend must merge with original corrections.json
```

### Firestore Consistency

**Problem**: Update job, trigger worker immediately, worker reads stale data.

**Solution**: Verify updates propagated before triggering workers:
```python
# Update job
await job_manager.update_job(job_id, updates)

# Verify update visible
job = await job_manager.get_job(job_id)
if job.input_media_gcs_path:
    await trigger_worker()
```

## Testing Insights

### Emulator Tests Catch Real Bugs

Unit tests with mocks didn't catch the `input_media_gcs_path` bug. Emulator integration tests did because they use real Firestore behavior.

**Lesson**: Run `make test` which includes emulator tests before every commit.

### Test Isolation

Emulator tests need their own `conftest.py` that does NOT mock `google.cloud.*`. Mocks from unit tests can leak into integration tests.

### Playwright: Use Assertions, Not Timeouts

**Problem**: `waitForTimeout()` is flaky and slow:

```typescript
// BAD - arbitrary wait, still flaky
await page.waitForTimeout(2000);
const hasContent = await page.locator('.content').count();
```

**Solution**: Use Playwright's auto-retry assertions:

```typescript
// GOOD - waits only until condition met, retries automatically
await expect(page.getByText('Hello,')).toBeVisible({ timeout: 5000 });
```

**Why it matters**: Playwright assertions have built-in retry logic and fail fast when conditions aren't met. Arbitrary timeouts either waste time (waiting when condition is already met) or cause flaky tests (not waiting long enough on slow CI).

## Deployment Notes

### Cloud Run Timeouts

Default 5-minute timeout may not be enough for video encoding. Consider:
- Cloud Run Jobs for long-running tasks
- Breaking encoding into smaller chunks
- Increasing timeout for specific operations

### Secret Manager Access

Cloud Run service account needs `Secret Manager Secret Accessor` role. This is managed via Pulumi in `infrastructure/`.

### CI/CD: GitHub Actions

Migrated from Cloud Build to GitHub Actions for:
- Simpler configuration
- Better visibility
- Faster feedback

### Self-Hosted Runner on GCP

GitHub-hosted runners have ~14GB disk, which caused failures during Docker builds. Solution: self-hosted runner on GCP with 200GB SSD.

**Key learnings:**

1. **GPG in startup scripts**: Always use `gpg --batch` for non-interactive execution
2. **setup-python on self-hosted**: Needs Python in tool cache at `$RUNNER/_work/_tool/Python/<version>/x64/` with `x64.complete` marker
3. **Debian vs Ubuntu**: PPAs don't work on Debian; use upstream repos (Temurin, NodeSource)
4. **pyenv for Python**: More reliable than source builds or distro packages for specific versions

See `docs/archive/2025-12-28-self-hosted-github-runner.md` for full details.

## Performance Observations

| Operation | Duration |
|-----------|----------|
| Audio separation | 5-8 min |
| Lyrics transcription | 2-3 min |
| Auto-correction | 30 sec |
| Screens generation | 30 sec |
| Video rendering | 10-15 min |
| Final encoding | 5-10 min |
| **Total** | 30-50 min |

Human review time varies (5-15 min typical).

## What We'd Do Differently

1. **Add Pydantic model fields test first** - Would have caught the silent field issue immediately

2. **Use emulator tests from day one** - Faster feedback than deploying to test

3. **Design for async human review upfront** - Avoided rearchitecting after discovering ReviewServer blocks

4. **Keep docs minimal and current** - Less documentation, but always accurate
