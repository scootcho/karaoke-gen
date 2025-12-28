# API Reference

Base URL: `https://api.nomadkaraoke.com` (production) or `http://localhost:8000` (local)

## Authentication

All endpoints except `/health` and `/api/themes` require authentication.

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" ...
```

## Endpoints

### Health

```
GET /health
```

No auth required. Returns service status.

### Jobs

#### Create Job with Upload

```
POST /api/jobs/upload
Content-Type: multipart/form-data

file: <audio file>
artist: "Artist Name"
title: "Song Title"
```

Returns job ID. Triggers async processing.

#### Get Job Status

```
GET /api/jobs/{job_id}
```

Response includes:
- `status` - Current job state
- `file_urls` - Signed URLs for outputs (when ready)
- `state_data` - Worker progress details
- `timeline` - Processing history

#### List Jobs

```
GET /api/jobs
GET /api/jobs?status=complete
GET /api/jobs?limit=10&offset=0
```

#### Delete Job

```
DELETE /api/jobs/{job_id}
```

### Review

#### Get Correction Data

```
GET /api/review/{job_id}/correction-data
```

Returns lyrics correction data for the review UI.

#### Complete Review

```
POST /api/review/{job_id}/complete
Content-Type: application/json

{
  "corrections": [...],
  "corrected_segments": [...]
}
```

Saves corrections and triggers video rendering.

#### Generate Preview

```
POST /api/review/{job_id}/preview-video
```

Generates preview video during review.

#### Stream Audio

```
GET /api/review/{job_id}/audio/{stem_type}
```

Streams audio for review playback.

### Instrumental Selection

```
POST /api/jobs/{job_id}/select-instrumental
Content-Type: application/json

{
  "selection": "clean"  // or "with_backing"
}
```

### Audio Search

```
GET /api/audio-search?q=song+name
```

Search for songs (flacfetch integration).

### Themes

```
GET /api/themes
```

No auth required. Returns available video themes.

### Internal (Admin Only)

These endpoints are used by workers and require admin tokens.

```
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

## Rate Limits

No rate limits currently implemented.

## Webhooks

Not yet implemented. Jobs must be polled for status.
