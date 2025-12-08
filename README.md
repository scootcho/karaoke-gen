# Karaoke Generator 🎶 🎥 🚀

![PyPI - Version](https://img.shields.io/pypi/v/karaoke-gen)
![Python Version](https://img.shields.io/badge/python-3.10+-blue)
![Tests](https://github.com/nomadkaraoke/karaoke-gen/workflows/Test%20and%20Publish/badge.svg)
![Test Coverage](https://codecov.io/gh/nomadkaraoke/karaoke-gen/branch/main/graph/badge.svg)

Generate karaoke videos with instrumental audio and synchronized lyrics. Available as both a **CLI tool** and a **web application**.

## ✨ Two Ways to Use Karaoke Generator

### 1. Command Line Interface (CLI)
Traditional Python package for local karaoke generation - perfect for batch processing and automation.

### 2. Web Application
Modern web interface for easy karaoke creation - no installation required!
- **Frontend**: https://gen.nomadkaraoke.com
- **Technology**: React + TypeScript on Cloudflare Pages
- **Backend**: FastAPI on Google Cloud Run

[Learn more about the web version →](docs/NEW-ARCHITECTURE.md)

## Overview

Karaoke Generator is a comprehensive tool for creating high-quality karaoke videos. It automates the entire workflow:

1. **Download** audio and lyrics for a specified song
2. **Separate** audio stems (vocals, instrumental)
3. **Synchronize** lyrics with the audio
4. **Generate** title and end screens
5. **Combine** everything into a polished final video
6. **Organize** and **share** the output files

## Installation

```bash
pip install karaoke-gen
```

## Remote Audio Separation 🌐

Karaoke Generator now supports remote audio separation using the Audio Separator API. This allows you to offload the compute-intensive audio separation to a remote GPU server while keeping the rest of the workflow local.

### Benefits of Remote Processing
- **Save Local Resources**: No more laptop CPU/GPU consumption during separation
- **Faster Processing**: GPU-accelerated separation on dedicated hardware
- **Cost Effective**: ~$0.019 per separation job on Modal.com (with $30/month free credits)
- **Multiple Models**: Process with multiple separation models efficiently

### Setup Remote Processing

1. **Deploy Audio Separator API** (using Modal.com):
   ```bash
   pip install modal
   modal setup
   modal deploy audio_separator/remote/deploy_modal.py
   ```

2. **Set Environment Variable**:
   ```bash
   export AUDIO_SEPARATOR_API_URL="https://USERNAME--audio-separator-api.modal.run"
   ```

3. **Run Karaoke Generator Normally**:
   ```bash
   karaoke-gen "Rick Astley" "Never Gonna Give You Up"
   ```

The tool will automatically detect the `AUDIO_SEPARATOR_API_URL` environment variable and use remote processing instead of local separation. If the remote API is unavailable, it will gracefully fall back to local processing.

### Remote vs Local Processing

| Aspect | Remote Processing | Local Processing |
|--------|------------------|------------------|
| **Resource Usage** | Minimal local CPU/GPU | High local CPU/GPU |
| **Processing Time** | ~2-5 minutes | ~15-45 minutes |
| **Cost** | ~$0.019 per job | Free (but uses local resources) |
| **Requirements** | Internet connection | Local GPU recommended |
| **Setup** | One-time API deployment | Audio separator models download |

## Quick Start

### Local Processing

```bash
# Generate a karaoke video from a YouTube URL
karaoke-gen "https://www.youtube.com/watch?v=dQw4w9WgXcQ" "Rick Astley" "Never Gonna Give You Up"

# Or let it search YouTube for you
karaoke-gen "Rick Astley" "Never Gonna Give You Up"
```

### Cloud Processing (Remote Backend)

Use `karaoke-gen-remote` to offload all processing to a cloud-hosted backend. This is perfect for users who want to generate karaoke videos without needing local GPU resources.

```bash
# Set your cloud backend URL
export KARAOKE_GEN_URL="https://your-backend.run.app"

# Submit a job to the cloud backend
karaoke-gen-remote ./song.mp3 "ABBA" "Waterloo"

# Resume monitoring an existing job
karaoke-gen-remote --resume abc12345
```

The remote CLI:
1. Uploads your audio file to the cloud backend
2. Monitors job progress with live updates
3. Opens the lyrics review UI when human review is needed
4. Prompts for instrumental selection interactively
5. Downloads all output files when complete

**Environment Variables:**
- `KARAOKE_GEN_URL` - Backend service URL (required)
- `REVIEW_UI_URL` - Lyrics review UI URL (default: http://localhost:5173)
- `POLL_INTERVAL` - Seconds between status polls (default: 5)
- `KARAOKE_GEN_BUCKET` - GCS bucket name for downloads

**Requirements:**
- `gcloud` CLI for authentication (`gcloud auth login`)
- `gsutil` for downloading output files

## Workflow Options

Karaoke Gen supports different workflow options to fit your needs:

```bash
# Run only the preparation phase (download, separate stems, create title screens)
karaoke-gen --prep-only "Rick Astley" "Never Gonna Give You Up"

# Run only the finalisation phase (must be run in a directory prepared by the prep phase)
karaoke-gen --finalise-only

# Skip automatic lyrics transcription/synchronization (for manual syncing)
karaoke-gen --skip-transcription "Rick Astley" "Never Gonna Give You Up"

# Skip audio separation (if you already have instrumental)
karaoke-gen --skip-separation --existing-instrumental="path/to/instrumental.mp3" "Rick Astley" "Never Gonna Give You Up"
```

## Advanced Features

### Audio Processing

```bash
# Specify custom audio separation models
karaoke-gen --clean_instrumental_model="model_name.ckpt" "Rick Astley" "Never Gonna Give You Up"
```

### Lyrics Handling

```bash
# Use a local lyrics file instead of fetching from online
karaoke-gen --lyrics_file="path/to/lyrics.txt" "Rick Astley" "Never Gonna Give You Up"

# Adjust subtitle timing
karaoke-gen --subtitle_offset_ms=500 "Rick Astley" "Never Gonna Give You Up"
```

### Video Background

```bash
# Use a video as background instead of static image
karaoke-gen --background_video="path/to/video.mp4" "Rick Astley" "Never Gonna Give You Up"

# Use a video background with darkening overlay (0-100%)
karaoke-gen --background_video="path/to/video.mp4" --background_video_darkness=50 "Rick Astley" "Never Gonna Give You Up"
```

The video background feature automatically:
- Scales the video to 4K resolution (3840x2160) with intelligent cropping
- Loops the video if it's shorter than the audio
- Trims the video if it's longer than the audio
- Applies an optional darkening overlay to improve subtitle readability
- Renders synchronized ASS subtitles on top of the video

### Finalisation Options

```bash
# Enable CDG ZIP generation
karaoke-gen --enable_cdg --style_params_json="path/to/style.json" "Rick Astley" "Never Gonna Give You Up"

# Enable TXT ZIP generation
karaoke-gen --enable_txt "Rick Astley" "Never Gonna Give You Up"

# Upload to YouTube
karaoke-gen --youtube_client_secrets_file="path/to/client_secret.json" --youtube_description_file="path/to/description.txt" "Rick Astley" "Never Gonna Give You Up"

# Draft completion emails (requires youtube_client_secrets_file for Gmail OAuth)
karaoke-gen --email_template_file="path/to/template.txt" --youtube_client_secrets_file="path/to/client_secret.json" "Rick Astley" "Never Gonna Give You Up"

# Organize files with brand code
karaoke-gen --brand_prefix="BRAND" --organised_dir="path/to/Tracks-Organized" "Rick Astley" "Never Gonna Give You Up"
```

## Full Command Reference

For a complete list of options:

```bash
karaoke-gen --help
```

## Development

### Running Tests

The project uses pytest for testing with unit and integration tests:

```bash
# Run all tests (unit tests first, then integration tests)
pytest

# Run only unit tests (fast feedback during development)
pytest -m "not integration"

# Run only integration tests (comprehensive end-to-end testing)
pytest -m integration
```

Unit tests run quickly and provide fast feedback, while integration tests are slower but test the full workflow end-to-end.

## Web Application

Want to use karaoke generation without installing anything? Check out our web app!

**Features**:
- Submit jobs from YouTube URLs
- Upload your own audio files
- Real-time progress tracking
- Download generated karaoke videos
- Mobile-friendly interface

**Access**: https://gen.nomadkaraoke.com

**Documentation**:
- [Architecture Overview](docs/NEW-ARCHITECTURE.md)
- [Deployment Guide](docs/CLOUDFLARE-PAGES-DEPLOYMENT.md)
- [Backend API](backend/README.md)
- [Frontend Development](frontend-react/README.md)

## Project Structure

```
karaoke-gen/
├── karaoke_gen/           # Core CLI package (shared by CLI and web)
├── backend/               # Web application backend (FastAPI)
├── frontend-react/        # Web application frontend (React)
├── docs/                  # Documentation
├── tests/                 # Test suite
└── README.md             # This file
```

## Contributing

Contributions are welcome! Please see our contributing guidelines.

## License

MIT
