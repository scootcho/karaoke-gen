# API Reference

Base URL: `https://api.nomadkaraoke.com` (production) or `http://localhost:8000` (local)

## Authentication

All endpoints except `/health` and `/api/themes` require authentication.

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" ...
```

## Endpoints

### Health

```http
GET /health
```

No auth required. Returns service status.

### Jobs

#### Create Job with Upload

```http
POST /api/jobs/upload
Content-Type: multipart/form-data

file: <audio file>
artist: "Artist Name"
title: "Song Title"
```

Returns job ID. Triggers async processing.

#### Get Job Status

```http
GET /api/jobs/{job_id}
```

Response includes:
- `status` - Current job state
- `file_urls` - Signed URLs for outputs (when ready)
- `state_data` - Worker progress details
- `timeline` - Processing history

#### List Jobs

```http
GET /api/jobs
GET /api/jobs?status=complete
GET /api/jobs?limit=10&offset=0
```

#### Delete Job

```http
DELETE /api/jobs/{job_id}
```

### Review

#### Get Correction Data

```http
GET /api/review/{job_id}/correction-data
```

Returns lyrics correction data for the review UI.

#### Complete Review

```http
POST /api/review/{job_id}/complete
Content-Type: application/json

{
  "corrections": [...],
  "corrected_segments": [...]
}
```

Saves corrections and triggers video rendering.

#### Generate Preview

```http
POST /api/review/{job_id}/preview-video
```

Generates preview video during review.

#### Stream Audio

```http
GET /api/review/{job_id}/audio/{stem_type}
```

Streams audio for review playback.

### Instrumental Selection

```http
POST /api/jobs/{job_id}/select-instrumental
Content-Type: application/json

{
  "selection": "clean"  // or "with_backing"
}
```

### Audio Search

```http
GET /api/audio-search?q=song+name
```

Search for songs (flacfetch integration).

### Themes

```http
GET /api/themes
```

No auth required. Returns available video themes.

### Internal (Admin Only)

These endpoints are used by workers and require admin tokens.

```http
POST /api/internal/jobs/{job_id}/trigger-audio
POST /api/internal/jobs/{job_id}/trigger-lyrics
POST /api/internal/jobs/{job_id}/trigger-screens
POST /api/internal/jobs/{job_id}/trigger-render-video
POST /api/internal/jobs/{job_id}/trigger-video
```

## Job States

| State | Description |
|-------|-------------|
| `pending` | Created, not started |
| `downloading` | Processing input |
| `separating_stage1` | Audio separation (1/2) |
| `separating_stage2` | Audio separation (2/2) |
| `transcribing` | Lyrics transcription |
| `generating_screens` | Title/end screens |
| `awaiting_review` | Waiting for human review |
| `in_review` | Human reviewing |
| `review_complete` | Review submitted |
| `rendering_video` | Generating karaoke video |
| `awaiting_instrumental_selection` | Waiting for selection |
| `instrumental_selected` | Selection made |
| `generating_video` | Final encoding |
| `complete` | Done |
| `failed` | Error |

## Error Responses

```json
{
  "detail": "Error message"
}
```

Common status codes:
- `400` - Bad request
- `401` - Unauthorized
- `404` - Job not found
- `500` - Server error

## User Authentication

### Send Magic Link

```http
POST /api/users/auth/magic-link
Content-Type: application/json

{"email": "user@example.com"}
```

### Verify Magic Link

```http
GET /api/users/auth/verify?token=TOKEN
```

Returns session token and user info.

### Get Current User

```http
GET /api/users/me
Authorization: Bearer SESSION_TOKEN
```

### Logout

```http
POST /api/users/auth/logout
Authorization: Bearer SESSION_TOKEN
```

## Credits & Payments (PR #90)

### List Credit Packages

```http
GET /api/users/credits/packages
```

No auth required. Returns available packages and prices.

### Create Checkout Session

```http
POST /api/users/credits/checkout
Content-Type: application/json

{"package_id": "5_credits", "email": "user@example.com"}
```

Returns Stripe checkout URL.

### Stripe Webhook

```http
POST /api/users/webhooks/stripe
```

Handles `checkout.session.completed` events.

## Beta Tester Program (PR #90)

### Enroll as Beta Tester

```http
POST /api/users/beta/enroll
Content-Type: application/json

{
  "email": "user@example.com",
  "promise_text": "I promise to provide feedback...",
  "accept_corrections_work": true
}
```

Returns 1 free credit and session token.

### Submit Feedback

```http
POST /api/users/beta/feedback
Authorization: Bearer SESSION_TOKEN
Content-Type: application/json

{
  "overall_rating": 4,
  "ease_of_use_rating": 5,
  "lyrics_accuracy_rating": 4,
  "correction_experience_rating": 3,
  "what_went_well": "...",
  "what_could_improve": "..."
}
```

Bonus credit for detailed feedback (50+ chars).

## Rate Limits

No rate limits currently implemented.

## Webhooks

Stripe webhooks implemented at `/api/users/webhooks/stripe`.
Job status webhooks not yet implemented.
