# Karaoke-Gen Documentation

> **Status**: Production-ready. First full E2E flow completed 2025-12-28.

## What Works

- **Web App**: https://gen.nomadkaraoke.com
  - `/` - Landing page with pricing and beta enrollment
  - `/app` - Main app (upload audio, review lyrics, download videos)
- **Backend API**: https://api.nomadkaraoke.com - FastAPI on Cloud Run
- **CLI Tools**: `karaoke-gen` (local), `karaoke-gen-remote` (cloud)

## Current State

| Component | Status |
|-----------|--------|
| Audio upload & separation | Working |
| Lyrics transcription | Working |
| Agentic AI correction | Working (Gemini 3 Flash via Vertex AI) |
| Human lyrics review | Working |
| Preview video generation | Working |
| Instrumental selection | Working |
| Multi-format encoding | Working |
| Token-based auth | Working |
| Magic link auth | Working |
| Payment flow (Stripe) | Working |
| Beta tester program | Working |
| CI/CD self-hosted runner | Working (GCP) |

## Known Issues

- CDG format generation requires additional style configuration
- Long audio files (>10 min) may timeout on some workers

## Recent Changes

- **E2E Test Suite Consolidated** (2025-12-29): Tests reorganized into `production/` (real API) and `regression/` (mocked API, CI-safe). See [archive/2025-12-29-e2e-test-consolidation-plan.md](archive/2025-12-29-e2e-test-consolidation-plan.md)

## Quick Links

| Doc | Purpose |
|-----|---------|
| [PRODUCT-VISION.md](PRODUCT-VISION.md) | Product goals, audience, business model |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, integrations |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup, testing, deployment |
| [API.md](API.md) | Backend endpoint reference |
| [LESSONS-LEARNED.md](LESSONS-LEARNED.md) | Key insights for future agents |
| [STRIPE-SETUP.md](STRIPE-SETUP.md) | Payment integration setup |
| [MOBILE-UX-BEST-PRACTICES.md](MOBILE-UX-BEST-PRACTICES.md) | Mobile/responsive design guidelines |
| [archive/](archive/) | Historical documentation |

## Workflow Summary

```
Upload Audio → Parallel Processing → Human Review → Video Generation → Download
                   │                      │
           (Modal + AudioShake)    (LyricsTranscriber UI)
```

## For AI Agents

Start with `CLAUDE.md` in the repo root for essential rules, then reference these docs as needed. Keep this README current when project state changes.
