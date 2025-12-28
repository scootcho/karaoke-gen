# Agentic Correction System - Implementation Status

**Last Updated:** 2025-12-26
**Status:** Core Implementation Complete, Ready for User Testing

## Overview

The agentic AI correction system for lyrics transcription is now feature-complete for the core workflow. This document tracks implementation status and what's available for testing.

## ✅ Completed Features

### Phase 1: Classification-First Correction Workflow

#### Gap Classification System
- **8 classification categories**: PUNCTUATION_ONLY, SOUND_ALIKE, BACKGROUND_VOCALS, EXTRA_WORDS, REPEATED_SECTION, COMPLEX_MULTI_ERROR, AMBIGUOUS, NO_ERROR
- **Category-specific handlers** for each type with appropriate actions
- **Classification prompt** with few-shot examples
- **Handler registry pattern** for extensibility

#### LLM Provider Support
- **OpenAI** (GPT-4, GPT-4-turbo)
- **Anthropic** (Claude 3 Sonnet)
- **Ollama** (local, free - llama3.2, mistral)
- **LangChain integration** for unified API

#### Reliability Features
- **Circuit breaker** pattern for failure protection
- **Configurable retries** and timeouts
- **Graceful degradation** to FLAG for human review

### Phase 2: Human Feedback Collection

#### Backend API
- `POST /api/v1/annotations` - Save correction annotations
- `GET /api/v1/annotations/{audio_hash}` - Get annotations for song
- `GET /api/v1/annotations/stats` - Aggregated statistics

#### Storage
- JSONL format for easy parsing and export
- Automatic datetime serialization
- Training data export capability

### Phase 3: Frontend UI Enhancements

#### Agentic Correction Metrics Panel
- Shows correction counts by category
- Visual icons for each gap category
- Confidence distribution filtering

#### Correction Detail Cards
- Click any corrected word to see details
- Shows original vs corrected text
- Displays AI reasoning and confidence
- Action buttons: Revert, Edit, Accept

#### Duration Timeline View
- Toggle to see word timing proportions
- Warning indicators for abnormally long words (>2s)
- Color coding: Green (corrected), Orange (gaps), Blue (anchors)

### Phase 4: Observability

#### Langfuse Integration
- Automatic trace grouping by session
- Full prompt/response logging
- Token counts and latency metrics
- Cost estimation for paid APIs

### Phase 5: Testing Infrastructure

#### Unit Tests
- 15 tests covering agentic handlers and feedback store
- All tests passing

#### E2E Tests (Playwright)
- Test fixtures with mock agentic correction data
- UI component tests
- File upload flow tests
- 7 tests passing

## 🚧 Future Enhancements (Not Blocking)

### Frontend Annotation Modal
- `CorrectionAnnotationModal.tsx` - UI for collecting human feedback on corrections
- Would trigger after user edits for training data collection
- Low priority - can use raw API for now

### Analysis Scripts
- `scripts/analyze_annotations.py` - Generate reports from collected annotations
- `scripts/generate_few_shot_examples.py` - Auto-generate prompt examples from feedback

### A/B Testing Framework
- Compare different prompt versions
- Track model performance over time

## Quick Start

### Enable Agentic Correction

```bash
# Required
export USE_AGENTIC_AI=1
export AGENTIC_AI_MODEL="openai/gpt-4"  # or "anthropic/claude-3-sonnet-20240229" or "ollama/llama3.2:latest"

# For cloud providers
export OPENAI_API_KEY="your-key"        # For OpenAI
export ANTHROPIC_API_KEY="your-key"     # For Anthropic

# Optional: Observability
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
```

### Run with Agentic Correction

```bash
# With OpenAI
USE_AGENTIC_AI=1 AGENTIC_AI_MODEL="openai/gpt-4" \
  lyrics-transcriber /path/to/song.mp3 --artist "Artist" --title "Song"

# With local Ollama (free)
USE_AGENTIC_AI=1 AGENTIC_AI_MODEL="ollama/llama3.2:latest" \
  lyrics-transcriber /path/to/song.mp3 --artist "Artist" --title "Song"
```

### Run Frontend Tests

```bash
cd lyrics_transcriber_temp/lyrics_transcriber/frontend
yarn install
yarn playwright install --with-deps chromium
yarn test
```

## File Reference

| Component | Files |
|-----------|-------|
| Core Agent | `correction/agentic/agent.py` |
| Handlers | `correction/agentic/handlers/*.py` |
| Classification Prompt | `correction/agentic/prompts/classifier.py` |
| LLM Providers | `correction/agentic/providers/*.py` |
| Feedback Storage | `correction/feedback/store.py` |
| API Endpoints | `review/server.py` |
| Frontend Metrics | `frontend/src/components/AgenticCorrectionMetrics.tsx` |
| Frontend Detail Card | `frontend/src/components/CorrectionDetailCard.tsx` |
| E2E Tests | `frontend/e2e/agentic-corrections.spec.ts` |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agentic Correction Flow                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Gap Found in Transcription                              │
│     │                                                       │
│     ▼                                                       │
│  2. Classification Prompt → LLM                             │
│     │                                                       │
│     ▼                                                       │
│  3. GapClassification (category, confidence, reasoning)     │
│     │                                                       │
│     ▼                                                       │
│  4. Handler Registry → Specialized Handler                  │
│     │                                                       │
│     ├── SOUND_ALIKE → SoundAlikeHandler → Replace           │
│     ├── BACKGROUND_VOCALS → BackgroundVocalsHandler → Delete│
│     ├── EXTRA_WORDS → ExtraWordsHandler → Delete            │
│     ├── PUNCTUATION_ONLY → PunctuationHandler → No Action   │
│     ├── NO_ERROR → NoErrorHandler → No Action               │
│     └── AMBIGUOUS/COMPLEX/REPEATED → Flag for Human Review  │
│     │                                                       │
│     ▼                                                       │
│  5. CorrectionProposal(s) returned                          │
│     │                                                       │
│     ▼                                                       │
│  6. Adapter → WordCorrection(s) for frontend                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## See Also

- [AGENTIC_CORRECTION_GUIDE.md](./AGENTIC_CORRECTION_GUIDE.md) - User guide for the agentic system
- [AGENTIC_UI_IMPROVEMENTS_COMPLETE.md](./AGENTIC_UI_IMPROVEMENTS_COMPLETE.md) - Frontend feature details
- [LANGCHAIN_MIGRATION.md](./LANGCHAIN_MIGRATION.md) - LangChain architecture details
