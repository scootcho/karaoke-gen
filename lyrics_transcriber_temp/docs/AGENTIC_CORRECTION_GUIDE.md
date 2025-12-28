# Agentic AI Lyrics Correction - User Guide

**Last Updated:** 2025-12-26

This guide explains how to use the agentic AI correction system for lyrics transcription.

## Overview

The agentic correction system uses LLMs to classify and correct transcription errors in lyrics. Unlike the rule-based correction handlers, the agentic system:

1. **Classifies gaps first** - Determines the type of error before attempting correction
2. **Routes to specialized handlers** - Each error type has its own handler
3. **Provides detailed reasoning** - Every correction includes confidence and explanation
4. **Supports human review** - Uncertain corrections are flagged for human verification

## Enabling Agentic Correction

### Environment Variables

```bash
# Required: Enable agentic mode
export USE_AGENTIC_AI=1

# Required: Specify model (provider/model format)
export AGENTIC_AI_MODEL="openai/gpt-4"  # or "anthropic/claude-3-sonnet-20240229" or "ollama/llama3.2:latest"

# Optional: LLM Provider API keys (only needed for cloud providers)
export OPENAI_API_KEY="your-key"           # For OpenAI models
export ANTHROPIC_API_KEY="your-key"        # For Anthropic models

# Optional: Observability with Langfuse
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"

# Optional: Tuning parameters
export AGENTIC_TIMEOUT_SECONDS=30          # Request timeout
export AGENTIC_MAX_RETRIES=2               # Max retry attempts
export AGENTIC_CIRCUIT_THRESHOLD=3         # Failures before circuit opens
export AGENTIC_CIRCUIT_OPEN_SECONDS=60     # Circuit open duration
export DISABLE_LLM_CACHE=1                 # Disable response caching
```

### Supported LLM Providers

| Provider | Model Format | API Key Required |
|----------|-------------|------------------|
| **OpenAI** | `openai/gpt-4`, `openai/gpt-4-turbo` | `OPENAI_API_KEY` |
| **Anthropic** | `anthropic/claude-3-sonnet-20240229` | `ANTHROPIC_API_KEY` |
| **Ollama** (local) | `ollama/llama3.2:latest`, `ollama/mistral:latest` | None |

### Using with Ollama (Local, Free)

1. Install Ollama: [https://ollama.ai](https://ollama.ai)
2. Pull a model: `ollama pull llama3.2:latest`
3. Set environment:
   ```bash
   export USE_AGENTIC_AI=1
   export AGENTIC_AI_MODEL="ollama/llama3.2:latest"
   ```

## Gap Classification Categories

The agentic system classifies gaps into 8 categories:

| Category | Description | Handler Action |
|----------|-------------|----------------|
| `PUNCTUATION_ONLY` | Style differences (quotes, punctuation) | No action |
| `SOUND_ALIKE` | Homophones ("out" → "now") | Replace word |
| `BACKGROUND_VOCALS` | Parenthesized backing vocals | Delete |
| `EXTRA_WORDS` | Filler words ("And", "But", "Well") | Delete |
| `REPEATED_SECTION` | Chorus/verse repetitions | Flag for human review |
| `COMPLEX_MULTI_ERROR` | Multiple error types | Flag for human review |
| `AMBIGUOUS` | Unclear without audio | Flag for human review |
| `NO_ERROR` | Matches reference lyrics | No action |

## Running with Agentic Correction

### CLI Usage

```bash
# Basic usage with agentic correction
USE_AGENTIC_AI=1 AGENTIC_AI_MODEL="openai/gpt-4" \
  lyrics-transcriber /path/to/song.mp3 --artist "Artist" --title "Song"

# With Ollama (free, local)
USE_AGENTIC_AI=1 AGENTIC_AI_MODEL="ollama/llama3.2:latest" \
  lyrics-transcriber /path/to/song.mp3 --artist "Artist" --title "Song"

# With debugging output
USE_AGENTIC_AI=1 AGENTIC_AI_MODEL="openai/gpt-4" \
  lyrics-transcriber /path/to/song.mp3 --artist "Artist" --title "Song" --log_level debug
```

### As a Library

```python
from lyrics_transcriber import LyricsTranscriber
from lyrics_transcriber.core.controller import TranscriberConfig, LyricsConfig, OutputConfig
import os

# Enable agentic mode
os.environ["USE_AGENTIC_AI"] = "1"
os.environ["AGENTIC_AI_MODEL"] = "openai/gpt-4"
os.environ["OPENAI_API_KEY"] = "your-key"

transcriber = LyricsTranscriber(
    audio_filepath="/path/to/song.mp3",
    artist="Artist",
    title="Title",
    transcriber_config=TranscriberConfig(
        audioshake_api_token="...",
    ),
    lyrics_config=LyricsConfig(
        genius_api_token="...",
    ),
    output_config=OutputConfig(
        output_dir="./out",
    ),
)

result = transcriber.process()

# Check agentic corrections
for correction in result.corrections:
    if correction.handler == "AgenticCorrector":
        print(f"Agentic correction: {correction.original_word} → {correction.corrected_word}")
        print(f"  Category: {correction.reason}")  # Contains [CATEGORY] tag
        print(f"  Confidence: {correction.confidence}")
```

## Frontend Review UI

When agentic corrections are made, the review UI shows:

1. **Agentic Correction Metrics Panel** - Summary of corrections by category
2. **Category Icons** - Visual indicators for correction types
3. **Confidence Filters** - Filter by low (<60%) or high (≥80%) confidence
4. **Correction Detail Cards** - Click any corrected word to see:
   - Original vs corrected text
   - Category classification
   - Confidence score
   - AI reasoning
   - Action buttons (Revert, Edit, Accept)

### Duration Timeline View

Toggle to duration view to see:
- Word timing bars proportional to duration
- Red warning indicators for abnormally long words (>2s)
- Color coding: Green (corrected), Orange (uncorrected gaps), Blue (anchors)

## Observability with Langfuse

When Langfuse is configured, you get:

- **Trace grouping** by session ID
- **Full prompts and responses**
- **Token counts and latency**
- **Cost estimates** for paid APIs
- **Model performance metrics**

Set up at [https://langfuse.com](https://langfuse.com)

## Human Feedback Collection

The system supports collecting feedback on corrections:

### API Endpoints

```bash
# Submit annotation
POST /api/v1/annotations
{
  "audio_hash": "abc123",
  "annotation_type": "SOUND_ALIKE",
  "action_taken": "REPLACE",
  "original_text": "out",
  "corrected_text": "now",
  "confidence": 5,
  "reasoning": "Reference lyrics clearly show 'now'"
}

# Get annotations for song
GET /api/v1/annotations/{audio_hash}

# Get statistics
GET /api/v1/annotations/stats
```

### Annotation Storage

Annotations are stored in `{cache_dir}/correction_annotations.jsonl` in JSONL format for easy processing and training data export.

## Troubleshooting

### "Failed to import agentic modules"

Ensure required packages are installed:
```bash
pip install langchain langchain-openai langchain-anthropic langchain-ollama langfuse
```

### "Langfuse keys are set but initialization failed"

Check your Langfuse credentials:
```bash
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY
```

### "Circuit breaker is open"

The system has detected too many failures. Wait 60 seconds or check:
- LLM API is accessible
- API keys are valid
- Model name is correct

### "Timeout waiting for LLM response"

Increase timeout:
```bash
export AGENTIC_TIMEOUT_SECONDS=60
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agentic Correction Flow                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Gap Found                                               │
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

## Files Reference

| File | Purpose |
|------|---------|
| `correction/agentic/agent.py` | Main AgenticCorrector class |
| `correction/agentic/adapter.py` | Converts proposals to WordCorrection |
| `correction/agentic/router.py` | Model selection logic |
| `correction/agentic/handlers/` | Category-specific handlers |
| `correction/agentic/models/schemas.py` | Pydantic models |
| `correction/agentic/prompts/classifier.py` | Classification prompt |
| `correction/agentic/providers/` | LLM provider implementations |
| `correction/feedback/` | Human feedback collection |

## Contributing

When adding new gap categories or handlers:

1. Add category to `GapCategory` enum in `models/schemas.py`
2. Create handler in `handlers/` extending `BaseHandler`
3. Register handler in `handlers/registry.py`
4. Add few-shot examples to `prompts/classifier.py`
5. Add tests in `tests/unit/correction/agentic/`

## See Also

- [AGENTIC_IMPLEMENTATION_STATUS.md](./AGENTIC_IMPLEMENTATION_STATUS.md) - Implementation progress
- [AGENTIC_UI_IMPROVEMENTS_COMPLETE.md](./AGENTIC_UI_IMPROVEMENTS_COMPLETE.md) - Frontend features
- [LANGCHAIN_MIGRATION.md](./LANGCHAIN_MIGRATION.md) - LangChain architecture details
