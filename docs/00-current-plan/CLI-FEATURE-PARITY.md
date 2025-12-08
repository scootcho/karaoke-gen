# CLI Feature Parity: karaoke-gen vs karaoke-gen-remote

This document tracks the feature parity between the local `karaoke-gen` CLI and the cloud-hosted `karaoke-gen-remote` CLI.

**Last Updated:** 2025-12-08

## Summary

| Category | karaoke-gen (Local) | karaoke-gen-remote (Cloud) | Status |
|----------|---------------------|---------------------------|--------|
| **Core Workflow** | ✅ Full | 🔄 Partial | In Progress |
| **Input Sources** | ✅ Files, URLs, YouTube | ⚠️ Files only | Limited |
| **Human Interactions** | ✅ Full | ✅ Full | Complete |
| **Style Configuration** | ✅ Full | ✅ Implemented | Complete |
| **Output Formats** | ✅ Full (6 formats) | 🔄 Partial | In Progress |
| **Finalisation Options** | ✅ Full | 🔄 Partial | In Progress |
| **Distribution** | ✅ Full | 🔄 Partial (Discord) | In Progress |

---

## Feature Comparison

### ✅ Working in Both CLIs

| Feature | Description | Notes |
|---------|-------------|-------|
| File upload | Submit local audio files | Remote supports: mp3, wav, flac, m4a, ogg, aac |
| Audio separation | Two-stage GPU separation via Modal | Same Modal API used by both |
| Lyrics transcription | AudioShake API transcription | Same AudioShake API |
| Auto-correction | Automatic lyrics correction | Uses LyricsTranscriber library |
| Human review | Browser-based lyrics review UI | Remote uses separate React UI |
| Instrumental selection | Choose clean vs with-backing-vocals | Interactive prompt in both |
| Job monitoring | Track progress to completion | Remote has colored CLI output |
| Resume jobs | Continue interrupted jobs | `--resume <job_id>` in remote |

### ⚠️ Partial/Limited in karaoke-gen-remote

| Feature | Local Behavior | Remote Behavior | TODO |
|---------|----------------|-----------------|------|
| **YouTube URL input** | Downloads and processes | ❌ Not supported | Backend needs URL download worker |
| **YouTube search** | Searches by artist+title | ❌ Not supported | Requires YouTube API integration |
| **Folder batch processing** | Process entire folder | ❌ Not supported | Backend needs batch job support |
| **Playlist processing** | Process YouTube playlists | ❌ Not supported | Backend needs playlist parsing |
| **Output formats** | 6 video formats generated | 🔄 Partial | Backend generates limited formats |
| **Title/End screens** | Custom styles from JSON | ⚠️ Default styles only | Backend needs style parameter support |

### ✅ Newly Implemented in karaoke-gen-remote

| Feature | Local CLI Flag | Description | Notes |
|---------|---------------|-------------|-------|
| **Style customization** | `--style_params_json` | Custom fonts, colors, backgrounds | Uploads JSON + all referenced files |
| **CDG generation** | `--enable_cdg` | Generate CDG+MP3 ZIP | Backend support added |
| **TXT generation** | `--enable_txt` | Generate TXT+MP3 ZIP | Backend support added |
| **Brand code** | `--brand_prefix` | Sequential brand numbering | Stored in job, backend TODO |
| **Discord notification** | `--discord_webhook_url` | Send Discord notification | Stored in job, backend TODO |
| **YouTube description** | `--youtube_description_file` | YouTube video description | Uploaded as text |

### ❌ Not Yet Implemented in karaoke-gen-remote

| Feature | Local CLI Flag | Description | Priority |
|---------|---------------|-------------|----------|
| **--prep-only** | `--prep-only` | Run only preparation phase | Medium |
| **--finalise-only** | `--finalise-only` | Run only finalisation phase | Low |
| **--edit-lyrics** | `--edit-lyrics` | Re-edit lyrics of existing track | Low |
| **--skip-transcription** | `--skip-transcription` | Skip lyrics (manual sync later) | Low |
| **--skip-separation** | `--skip-separation` | Skip audio separation | Low |
| **--skip-lyrics** | `--skip-lyrics` | Skip lyrics entirely | Low |
| **--lyrics-only** | `--lyrics-only` | Only process lyrics | Low |
| **--existing_instrumental** | `--existing_instrumental` | Use pre-separated instrumental | Medium |
| **--lyrics_file** | `--lyrics_file` | Use local lyrics file | Medium |
| **--background_video** | `--background_video` | Video background instead of image | Low |
| **Folder organization** | `--organised_dir` | Move to organized location (local-only) | N/A |
| **YouTube upload** | `--youtube_client_secrets_file` | Upload to YouTube | High |
| **Email draft** | `--email_template_file` | Create Gmail draft | Low |
| **rclone sync** | `--rclone_destination` | Sync to cloud storage (local-only) | N/A |
| **Style overrides** | `--style_override` | Override individual style params | Low |

---

## Detailed TODO List

### Phase 1: Core Feature Parity (High Priority)

These features are essential for basic usage parity.

#### 1.1 YouTube URL Support
**Status:** ❌ Not Started  
**Effort:** Medium (2-3 days)  
**Description:** Allow users to submit YouTube URLs instead of uploading files.

**Backend Changes:**
- [ ] Add URL input to job creation endpoint
- [ ] Create download worker that uses yt-dlp
- [ ] Handle rate limiting and geo-restrictions
- [ ] Store downloaded file in GCS

**CLI Changes:**
- [ ] Accept URL as first positional argument (already in parser)
- [ ] Submit URL to backend instead of uploading file

---

#### 1.2 Complete Output Formats
**Status:** 🔄 Partial  
**Effort:** Medium (2-3 days)  
**Description:** Generate all 6 output formats that local CLI produces.

**Required Formats:**
- [ ] Lossless 4K MP4 (PCM audio)
- [ ] Lossless 4K MKV (FLAC audio)
- [ ] Lossy 4K MP4 (AAC audio)
- [ ] Lossy 720p MP4 (AAC audio)
- [ ] CDG+MP3 ZIP
- [ ] TXT+MP3 ZIP

**Backend Changes:**
- [ ] Video worker to generate all 4 video formats
- [ ] Add CDG generation worker/step
- [ ] Add TXT generation worker/step
- [ ] Store all formats in GCS with proper naming

---

#### 1.3 YouTube Upload Integration
**Status:** ❌ Not Started  
**Effort:** High (3-5 days)  
**Description:** Automatically upload completed videos to YouTube.

**Backend Changes:**
- [ ] Secure credential storage in Secret Manager
- [ ] YouTube Data API v3 integration
- [ ] Upload worker with retry logic
- [ ] Thumbnail upload
- [ ] Store YouTube URL in job metadata

**CLI Changes:**
- [ ] Accept `--youtube_client_secrets_file` (already in parser)
- [ ] Display YouTube URL on completion

---

### Phase 2: Enhanced Features (Medium Priority)

#### 2.1 Custom Style Parameters
**Status:** ❌ Not Started  
**Effort:** Medium (2-3 days)  
**Description:** Support custom fonts, colors, and backgrounds.

**Backend Changes:**
- [ ] Accept style_params_json in job creation
- [ ] Upload style JSON to GCS
- [ ] Pass style params to title/end screen generator
- [ ] Pass style params to lyrics video generator

**CLI Changes:**
- [ ] Upload style JSON file with job submission

---

#### 2.2 Existing Instrumental Support
**Status:** ❌ Not Started  
**Effort:** Low (1 day)  
**Description:** Skip separation when user provides instrumental.

**Backend Changes:**
- [ ] Accept instrumental file upload
- [ ] Store instrumental in GCS
- [ ] Skip audio separation worker when instrumental provided
- [ ] Use provided instrumental in finalization

**CLI Changes:**
- [ ] Accept `--existing_instrumental` path
- [ ] Upload instrumental file alongside main audio

---

#### 2.3 Custom Lyrics File
**Status:** ❌ Not Started  
**Effort:** Low (1 day)  
**Description:** Use user-provided lyrics instead of fetching.

**Backend Changes:**
- [ ] Accept lyrics file upload
- [ ] Store lyrics in GCS
- [ ] Pass lyrics file to transcriber for alignment only

**CLI Changes:**
- [ ] Accept `--lyrics_file` path
- [ ] Upload lyrics file with job submission

---

#### 2.4 CDG/TXT Generation
**Status:** ❌ Not Started  
**Effort:** Medium (2-3 days)  
**Description:** Generate CDG and TXT karaoke formats.

**Backend Changes:**
- [ ] Integrate CDGGenerator from lyrics_transcriber
- [ ] Generate MP3 from instrumental FLAC
- [ ] Create ZIP packages
- [ ] Add job option flags: enable_cdg, enable_txt

**CLI Changes:**
- [ ] Accept `--enable_cdg` and `--enable_txt` flags
- [ ] Download CDG/TXT ZIPs on completion

---

### Phase 3: Distribution Features (Lower Priority)

#### 3.1 Discord Notification
**Status:** ❌ Not Started  
**Effort:** Low (1 day)

**Backend Changes:**
- [ ] Accept webhook URL in job creation
- [ ] Send notification on completion
- [ ] Include job details and YouTube URL

---

#### 3.2 Email Draft Creation
**Status:** ❌ Not Started  
**Effort:** Medium (2-3 days)

**Backend Changes:**
- [ ] Gmail API integration
- [ ] Template file handling
- [ ] Draft creation with placeholders

---

#### 3.3 Brand Code Organization
**Status:** ❌ Not Started  
**Effort:** Low (1-2 days)

**Backend Changes:**
- [ ] Sequential brand code tracking in Firestore
- [ ] Rename output files with brand code
- [ ] Support `--brand_prefix` option

---

### Phase 4: Advanced Workflows (Low Priority)

#### 4.1 Prep-Only Mode
**Status:** ❌ Not Started  
**Effort:** Low (1 day)

**Backend Changes:**
- [ ] Add job option to stop after screens generation
- [ ] Return job in "prep_complete" state

---

#### 4.2 Edit Lyrics Mode
**Status:** ❌ Not Started  
**Effort:** Medium (2-3 days)

**Backend Changes:**
- [ ] API to re-open review for existing job
- [ ] Backup existing outputs
- [ ] Re-run lyrics processing only
- [ ] Re-generate affected outputs

---

#### 4.3 Batch Processing
**Status:** ❌ Not Started  
**Effort:** High (3-5 days)

**Backend Changes:**
- [ ] Batch job creation endpoint
- [ ] Queue management for multiple jobs
- [ ] Aggregate progress reporting
- [ ] Batch completion notification

---

## Implementation Order Recommendation

Based on user value and effort, recommended implementation order:

### Sprint 1 (Week 1-2)
1. **Complete Output Formats** - Users need all video formats
2. **CDG/TXT Generation** - Core karaoke format support

### Sprint 2 (Week 2-3)
3. **YouTube URL Support** - Major convenience feature
4. **Custom Style Parameters** - Important for branding

### Sprint 3 (Week 3-4)
5. **YouTube Upload** - Automation for distribution
6. **Existing Instrumental** - Power user feature

### Sprint 4 (Week 4+)
7. **Custom Lyrics File** - Power user feature
8. **Discord/Email Notifications** - Nice to have
9. **Brand Code Organization** - Nice to have
10. **Advanced Workflows** - Edge cases

---

## Architecture Notes

### File Handling Differences

| Aspect | Local CLI | Remote CLI |
|--------|-----------|------------|
| Input location | Local filesystem | Uploaded to GCS |
| Working directory | Local temp dir | Cloud Run temp dir |
| Output storage | Local filesystem | GCS bucket |
| Output access | Direct file access | gsutil download / signed URLs |
| Cleanup | Manual | GCS lifecycle policies |

### Authentication Differences

| Aspect | Local CLI | Remote CLI |
|--------|-----------|------------|
| API auth | Environment variables | gcloud identity token |
| YouTube | Local OAuth flow | Server-side OAuth (TBD) |
| Gmail | Local OAuth flow | Server-side OAuth (TBD) |
| GCS | Not needed | Service account |

### Human Interaction Differences

| Interaction | Local CLI | Remote CLI |
|-------------|-----------|------------|
| Lyrics review | https://lyrics.nomadkaraoke.com (hosted UI, can override with `LYRICS_REVIEW_UI_URL=local`) | https://lyrics.nomadkaraoke.com (hosted UI) |
| Instrumental selection | CLI prompt | CLI prompt (same) |
| Approval prompts | CLI prompt | N/A (async) |

**Note:** Both CLIs now default to the hosted review UI at `https://lyrics.nomadkaraoke.com`. The local CLI starts a local API server on port 8000, and the hosted UI connects to it. Set `LYRICS_REVIEW_UI_URL=local` to use the bundled local frontend instead.

---

## Testing Checklist

When adding new features, ensure:

- [ ] Feature works with both small (<1 min) and large (>5 min) audio files
- [ ] Error handling for network failures
- [ ] Progress updates visible in CLI
- [ ] Output files downloadable via gsutil
- [ ] Job state persists across CLI interruptions
- [ ] Resume (`--resume`) works after feature is used

---

## Related Documentation

- [KARAOKE-GEN-CLI-WORKFLOW.md](../01-reference/KARAOKE-GEN-CLI-WORKFLOW.md) - Full local CLI workflow
- [CURRENT-STATUS.md](./CURRENT-STATUS.md) - Backend implementation status
- [WORKER-IMPLEMENTATION-PLAN.md](./WORKER-IMPLEMENTATION-PLAN.md) - Worker architecture
