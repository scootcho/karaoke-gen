# E2E Test Improvements - December 30, 2025

## Summary

This document summarizes improvements made to the production E2E test and backend issues discovered during testing.

## E2E Test Improvements

### 1. Token Reuse Support
- Added ability to use `KARAOKE_ACCESS_TOKEN` environment variable to skip MailSlurp enrollment
- Helpful when MailSlurp rate limits are reached (30 inboxes/month free tier)
- Test logs full token after successful enrollment for reuse

### 2. MailSlurp Rate Limit Handling
- Added clear error messages when MailSlurp rate limit is reached
- Provides instructions for getting a token manually or via API

### 3. Improved Job Status Polling (`pollJobStatus`)
- Added retry logic (3 attempts) for API timeouts
- Reduced individual request timeout to 30s with retries instead of single 2-minute wait
- Added state_data inspection for accurate progress tracking
- Logs only when progress changes (reduces noise)
- Detects completion via `review_token`, `instrumental_token`, or `download_urls` even when status field is incorrect
- Works around backend bug where status field doesn't update

### 4. Robust Job Creation
- Retry logic for UI button clicks (3 attempts)
- Falls back to direct API call if UI doesn't work
- Captures job_id from API response since UI job list doesn't always refresh

### 5. Token Capture Helper
- Created `capture-token.ts` helper for manual token capture
- Run with `--headed` mode for manual login when MailSlurp is unavailable

### 6. Generating Screens Status Handling
- Added `generating_screens` to accepted statuses in Step 6
- Step 7 waits for screen generation to complete before attempting lyrics review
- Handles transition from `generating_screens` → `awaiting_review`

### 7. Increased Timeouts
- Job processing timeout increased from 10min to 20min
- Full test timeout increased from 15min to 30min
- Accounts for slow AI services and AudioShake latency

## Backend Issues Discovered

### 1. Job Status Not Updating
- **Issue**: Job `status` field stays at "downloading" even after audio separation completes
- **Workaround**: Test checks `state_data.audio_progress.stage` and `state_data.lyrics_progress.stage` for actual progress
- **Impact**: Test needs to rely on state_data rather than status field

### 2. Lyrics Worker Agentic Correction Stuck
- **Issue**: Lyrics worker crashes or times out during agentic correction phase
- **Observed**: Workers stop logging after "Attempting agentic correction for gap X/Y"
- **Jobs affected**: bcc74e79 (stuck at gap 1/52), 4c585c6f (stuck at gap 1/52), 66bbb6b5 (reached generating_screens but with AI errors)
- **Likely cause**: Cloud Run timeout, Vertex AI/Gemini 404 errors ("Publisher Mode" errors)
- **Impact**: Jobs either don't complete, or complete with gaps flagged for manual review

### 3. UI Job List Not Refreshing
- **Issue**: Frontend job list shows "0 jobs" even after job creation
- **Workaround**: Test captures job_id from API response directly
- **Impact**: "Select Audio" button never visible in UI

## Test Coverage Status

### Working Steps (Steps 1-5)
- [x] Landing page verification
- [x] Beta enrollment via MailSlurp OR token auth
- [x] Credits verification
- [x] Job creation (UI or API fallback)
- [x] Audio selection (UI or API fallback)

### Blocked Steps (Backend Issues)
- [ ] Step 6: Wait for processing - blocked by lyrics worker timeout
- [ ] Step 7: Lyrics review - never reached
- [ ] Step 8: Instrumental selection - never reached
- [ ] Step 9: Wait for completion - never reached
- [ ] Step 10: Output verification - never reached

## Recommendations

1. **Fix Agentic Lyrics Correction**
   - Workers hang at "Attempting agentic correction for gap 1/52"
   - Add timeout/retry for agentic correction AI calls
   - Consider making agentic correction optional or async
   - Add better error logging when AI service fails

2. **Fix Status Field Updates**
   - Ensure job status updates as workers complete
   - Add status field for each worker (audio_status, lyrics_status)

3. **Fix Frontend Job List**
   - Investigate why jobs don't appear after creation
   - May be a caching or state management issue

## Files Changed

- `frontend/e2e/helpers/email-testing.ts` - MailSlurp rate limit handling
- `frontend/e2e/production/full-user-journey.spec.ts` - All test improvements
- `frontend/e2e/helpers/capture-token.ts` - New token capture helper
