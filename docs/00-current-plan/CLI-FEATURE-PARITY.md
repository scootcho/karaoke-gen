# CLI Feature Parity: karaoke-gen vs karaoke-gen-remote

This document tracks the feature parity between the local `karaoke-gen` CLI and the cloud-hosted `karaoke-gen-remote` CLI.

**Last Updated:** 2024-12-09

## Summary

| Category | karaoke-gen (Local) | karaoke-gen-remote (Cloud) | Status |
|----------|---------------------|---------------------------|--------|
| **Core Workflow** | ✅ Full | ✅ Full | Complete |
| **Input Sources** | ✅ Files, URLs, YouTube | ⚠️ Files only | Limited |
| **Human Interactions** | ✅ Full | ✅ Full | Complete |
| **Style Configuration** | ✅ Full | ✅ Full | Complete |
| **Output Formats** | ✅ Full (6 formats) | ✅ Full (6 formats) | Complete |
| **Finalisation Options** | ✅ Full | ✅ Most features | Complete |
| **Distribution** | ✅ Full | ✅ Discord | Partial |

---

## Daily Workflow Support

The remote CLI now supports the typical daily workflow:

```bash
karaoke-gen-remote \
  --style_params_json="/path/to/karaoke-prep-styles-nomad.json" \
  --enable_cdg --enable_txt \
  --brand_prefix=NOMAD \
  --discord_webhook_url='https://discord.com/api/webhooks/...' \
  --youtube_description_file='/path/to/youtube-video-description.txt' \
  file.flac "Artist" "Title"
```

### What This Does:
1. **Uploads audio** + style JSON + all referenced images/fonts
2. **Separates audio** via Modal GPU workers
3. **Transcribes lyrics** via AudioShake API
4. **Opens review UI** for human lyrics correction
5. **Prompts for instrumental** selection (clean vs backing vocals)
6. **Generates videos** in 4 formats using custom styles
7. **Generates CDG/TXT** packages with custom CDG styles
8. **Posts Discord notification** with YouTube URL
9. **Downloads all outputs** to local machine with brand code naming

---

## Feature Comparison

### ✅ Fully Working in Both CLIs

| Feature | Description | Implementation |
|---------|-------------|----------------|
| File upload | Submit local audio files | Remote: mp3, wav, flac, m4a, ogg, aac |
| Audio separation | Two-stage GPU separation | Same Modal API |
| Lyrics transcription | AudioShake API | Same implementation |
| Auto-correction | Automatic lyrics correction | LyricsTranscriber library |
| Human review | Browser-based UI | https://lyrics.nomadkaraoke.com |
| **Preview video with custom styles** | Preview uses custom backgrounds/fonts | ✅ Fixed 2024-12-09 |
| Instrumental selection | Clean vs with-backing-vocals | CLI prompt |
| **Style configuration** | Custom backgrounds, fonts, colors | Uploads style JSON + all asset files |
| **CDG generation** | CDG+MP3 ZIP packages | Uses CDGGenerator with custom styles |
| **TXT generation** | TXT+MP3 ZIP packages | Uses KaraokeFinalise |
| **Brand codes** | Sequential numbering (NOMAD-0001) | KaraokeFinalise server-side mode |
| **Discord notifications** | Webhook on completion | KaraokeFinalise.post_discord_notification() |
| **4 video formats** | Lossless/Lossy 4K/720p | KaraokeFinalise.process() |
| Job resume | Continue interrupted jobs | `--resume <job_id>` |
| File download | Download completed outputs | gsutil with proper naming |

### ⚠️ Limited in karaoke-gen-remote

| Feature | Local Behavior | Remote Status | Notes |
|---------|----------------|---------------|-------|
| **YouTube URL input** | Downloads and processes | ❌ Not supported | Requires URL download worker |
| **YouTube search** | Searches by artist+title | ❌ Not supported | Requires YouTube API |
| **Folder batch processing** | Process entire folder | ❌ Not supported | Requires batch job support |
| **YouTube upload** | Uploads to YouTube | ❌ Not supported | Requires server-side OAuth |

### ❌ Local-Only Features (Cannot Work in Cloud)

| Feature | Local CLI Flag | Reason |
|---------|---------------|--------|
| **Folder organization** | `--organised_dir` | Requires local filesystem |
| **Public share copy** | `--public_share_dir` | Requires local filesystem |
| **rclone sync** | `--rclone_destination` | Requires local rclone |
| **Email draft** | `--email_template_file` | Creates local Gmail draft |

### ❌ Not Yet Implemented

| Feature | Local CLI Flag | Priority |
|---------|---------------|----------|
| **--prep-only** | Run only preparation phase | Low |
| **--finalise-only** | Run only finalisation phase | Low |
| **--edit-lyrics** | Re-edit lyrics of existing track | Low |
| **--existing_instrumental** | Use pre-separated instrumental | Medium |
| **--lyrics_file** | Use local lyrics file | Medium |
| **--style_override** | Override individual style params | Low |

---

## Implementation Details

### Style Configuration Flow

Style loading is consolidated in a **unified module** (`karaoke_gen/style_loader.py`) used by both local CLI and cloud backend. See [STYLE-LOADER-REFACTOR.md](./STYLE-LOADER-REFACTOR.md) for architecture details.

1. **CLI parses** `--style_params_json` and extracts all file references:
   - `intro.background_image`, `intro.font`
   - `karaoke.background_image`, `karaoke.font_path`
   - `end.background_image`, `end.font`
   - `cdg.font_path`, `cdg.instrumental_background`, `cdg.title_screen_background`, `cdg.outro_background`

2. **CLI uploads** style JSON + all referenced files to backend

3. **Backend stores** all files in GCS under `uploads/{job_id}/style/`

4. **Workers download** style assets from GCS using `load_styles_from_gcs()`:
   - `screens_worker.py` uses style config for title/end screens
   - `render_video_worker.py` uses style config for karaoke video with lyrics
   - `review.py` uses style config for preview video generation
   - `video_worker.py` passes CDG styles to `KaraokeFinalise`

### Video Worker Architecture

The video worker reuses `KaraokeFinalise.process()` with all parameters:

```python
finalise = KaraokeFinalise(
    # CDG/TXT generation
    enable_cdg=job.enable_cdg,
    enable_txt=job.enable_txt,
    cdg_styles=style_config.get_cdg_styles(),
    # Brand code
    brand_prefix=job.brand_prefix,
    # Notifications
    discord_webhook_url=job.discord_webhook_url,
    # Server-side mode
    non_interactive=True,
    server_side_mode=True,
)
result = finalise.process()
```

This **reuses 100% of existing code** - no duplicate implementations.

### File Download

On job completion, the CLI downloads all outputs with proper naming:

```
{Brand Code} - {Artist} - {Title}/
├── Artist - Title (Final Karaoke Lossless 4k).mp4
├── Artist - Title (Final Karaoke Lossless 4k).mkv
├── Artist - Title (Final Karaoke Lossy 4k).mp4
├── Artist - Title (Final Karaoke Lossy 720p).mp4
├── Artist - Title (Final Karaoke CDG).zip
├── Artist - Title (Final Karaoke TXT).zip
├── Artist - Title (Karaoke).lrc
├── Artist - Title (Karaoke).ass
└── stems/
    ├── instrumental_clean.flac
    └── instrumental_with_backing.flac
```

---

## Files Modified for Style Support

| File | Changes |
|------|---------|
| `karaoke_gen/style_loader.py` | **New** - Unified style loading module (defaults, asset mappings, GCS loading) |
| `karaoke_gen/config.py` | Delegates to style_loader for style operations |
| `backend/models/job.py` | Added `style_assets`, `brand_prefix`, `discord_webhook_url` fields |
| `backend/api/routes/file_upload.py` | Accepts style files (JSON, images, fonts) as multipart upload |
| `backend/api/routes/review.py` | Uses `load_styles_from_gcs()` for preview video custom styles |
| `backend/workers/style_helper.py` | `StyleConfig` class wraps unified style_loader |
| `backend/workers/render_video_worker.py` | Uses `load_styles_from_gcs()` for post-review video |
| `backend/workers/screens_worker.py` | Uses `StyleConfig` for title/end screens |
| `backend/workers/video_worker.py` | Reuses `KaraokeFinalise.process()` with all params |
| `karaoke_gen/utils/remote_cli.py` | Parses style JSON, uploads all files, improved downloads |
| `karaoke_gen/utils/cli_args.py` | Shared argument parser for both CLIs |

---

## Human Interaction Points

| Interaction | Local CLI | Remote CLI |
|-------------|-----------|------------|
| Lyrics review | https://lyrics.nomadkaraoke.com | https://lyrics.nomadkaraoke.com |
| Instrumental selection | CLI prompt | CLI prompt |
| Approval prompts | CLI prompt | N/A (async) |

**Note:** Both CLIs use the hosted review UI at `https://lyrics.nomadkaraoke.com`. Set `LYRICS_REVIEW_UI_URL=local` to use the bundled local frontend instead.

---

## Recent Fixes

### 2024-12-09: Preview Video Custom Styles
- **Bug**: Preview videos in remote mode showed black background instead of custom background images
- **Cause**: `review.py` was using minimal styles instead of downloading job's custom styles from GCS
- **Fix**: Updated to use unified `load_styles_from_gcs()` function
- **Result**: Preview videos now correctly display custom backgrounds/fonts during lyrics review

### 2024-12-09: Style Loader Consolidation
- **Problem**: Style loading code was duplicated in 5+ places with slight variations, causing bugs
- **Fix**: Created `karaoke_gen/style_loader.py` as single source of truth
- **Details**: See [STYLE-LOADER-REFACTOR.md](./STYLE-LOADER-REFACTOR.md)

---

## Future Work (Lower Priority)

### YouTube URL Support
- Backend needs URL download worker using yt-dlp
- Handle rate limiting and geo-restrictions

### YouTube Upload
- Server-side OAuth flow
- Credential storage in Secret Manager
- YouTube Data API v3 integration

### Batch Processing
- Batch job creation endpoint
- Queue management for multiple jobs

---

## Testing

Tests are in `backend/tests/`:
- `test_style_upload.py` - Style parsing and loading tests
  - `TestRemoteCLIStyleParsing` - Tests CLI style JSON parsing
  - `TestStyleHelper` - Tests backend style config loading
- `test_routes_review.py` - Review API tests
  - `TestPreviewStyleLoading` - Tests unified style loader for previews

Run with: `pytest backend/tests/test_style_upload.py backend/tests/test_routes_review.py -v`

---

## Related Documentation

- [KARAOKE-GEN-CLI-WORKFLOW.md](../01-reference/KARAOKE-GEN-CLI-WORKFLOW.md) - Full local CLI workflow
- [CURRENT-STATUS.md](./CURRENT-STATUS.md) - Backend implementation status
- [WORKER-IMPLEMENTATION-PLAN.md](./WORKER-IMPLEMENTATION-PLAN.md) - Worker architecture
- [STYLE-LOADER-REFACTOR.md](./STYLE-LOADER-REFACTOR.md) - Style loader consolidation details
