# Development Guide

## Quick Start

### Prerequisites

- Python 3.12
- Node.js 20+
- Docker (for GCS emulator)
- Google Cloud SDK with Firestore emulator

```bash
# Install Firestore emulator
gcloud components install cloud-firestore-emulator
```

### Backend Setup

```bash
# Create and activate venv
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
poetry install

# Copy environment template
cp .env.example .env
# Edit .env with required API keys
```

### Frontend Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# Edit .env.local with KARAOKE_ACCESS_TOKEN
```

## Running Locally

### Backend with Emulators

```bash
# Start emulators and backend
./scripts/run-backend-local.sh --with-emulators

# Backend runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm run dev
# Runs at http://localhost:3000
```

## Testing

**See [TESTING.md](TESTING.md) for complete testing guidance.**

Quick reference (run before committing):

```bash
make test 2>&1 | tail -n 500
```

This runs ALL tests (backend + frontend) and installs dependencies automatically.

For faster iteration, run subsets:
- `make test-backend` - Backend only (~2 min)
- `make test-frontend` - Frontend only (~3 min)

TESTING.md covers: test types, CI requirements, Playwright usage, mocking guidelines, and coverage enforcement.

## Deployment

### Automatic (CI/CD)

Push to `main` triggers GitHub Actions:
1. Run tests
2. Build Docker image
3. Deploy to Cloud Run
4. Deploy frontend to Cloudflare Pages

### Infrastructure Changes (Pulumi)

**All infrastructure changes must go through PRs.** The CI pipeline automatically deploys Pulumi changes when PRs merge to main.

```bash
# Preview changes locally (requires GCP auth)
cd infrastructure
pulumi preview --stack nomadkaraoke/karaoke-gen-infrastructure/prod

# DO NOT run `pulumi up` locally - let CI handle deployment
# CI uses --skip-preview due to limited service account permissions
```

**What's managed by Pulumi:**
- Firestore database and indexes
- GCS buckets
- Cloud Run service configuration
- Cloud Tasks queues
- Secret Manager secrets
- Service accounts and IAM bindings
- Workload Identity Federation
- GCE instances (GitHub runners, encoding worker)

**Workflow:**
1. Make changes in the appropriate module under `infrastructure/`
   - `modules/` - Core GCP resources (database, storage, secrets, IAM, etc.)
   - `compute/` - VM definitions and startup scripts
   - `config.py` - Shared configuration constants
   - `__main__.py` - Entry point that wires modules together
2. Run `pulumi preview` locally to verify
3. Create PR and merge
4. CI deploys automatically

See `docs/LESSONS-LEARNED.md` for Pulumi CI gotchas.

### Manual Frontend Deploy

```bash
cd frontend
npm run build
npx wrangler pages deploy out
```

## Environment Variables

### Backend (.env)

```bash
# Required
AUDIOSHAKE_API_TOKEN=...
GENIUS_ACCESS_TOKEN=...
AUDIO_SEPARATOR_API_URL=...  # Modal API endpoint

# GCP (auto-configured in Cloud Run)
GOOGLE_CLOUD_PROJECT=...
GCS_BUCKET_NAME=...

# Auth
ADMIN_TOKENS=token1,token2
```

### Frontend (.env.local)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000

# For E2E tests (see frontend/.env.local.example)
KARAOKE_ACCESS_TOKEN=...     # Skip email enrollment
TESTMAIL_API_KEY=...         # testmail.app API key
TESTMAIL_NAMESPACE=...       # testmail.app namespace
```

## Key Scripts

| Script | Purpose |
|--------|---------|
| `make test` | Run all backend tests |
| `./scripts/run-backend-local.sh` | Start backend with emulators |
| `./scripts/start-emulators.sh` | Start emulators only |
| `./scripts/stop-emulators.sh` | Stop emulators |
| `./scripts/debug-job.sh <job_id>` | Debug a cloud job (status, logs, files) |
| `./scripts/get_job.py <job_id>` | Fetch job data from Firestore |
| `./scripts/fetch_job_logs.py <job_id>` | Fetch cloud job logs to local file |
| `./scripts/analyze_log_timing.py <log>` | Profile karaoke-gen performance from logs |
| `./scripts/benchmark_ffmpeg.py` | Isolated FFmpeg encoding benchmark |
| `./scripts/compare_local_vs_remote.py` | Compare local vs cloud karaoke-gen performance |

## Project Structure

```
karaoke-gen/
├── backend/
│   ├── api/routes/       # FastAPI endpoints
│   ├── models/           # Pydantic models
│   ├── services/         # Business logic
│   ├── workers/          # Background workers
│   └── tests/            # Backend tests
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── components/   # React components
│   │   └── lib/          # Utilities
│   └── tests/            # Frontend tests
├── infrastructure/       # Pulumi IaC
├── karaoke_gen/          # CLI package
└── scripts/              # Dev scripts
```

## Troubleshooting

### Emulators Won't Start

```bash
# Check if already running
lsof -i :8080  # Firestore
lsof -i :4443  # GCS

# Stop them
./scripts/stop-emulators.sh
```

### Docker Issues

```bash
# Ensure Docker is running
docker info

# For GCS emulator
docker pull fsouza/fake-gcs-server
```

### Test Failures

See [TESTING.md](TESTING.md#debugging-failed-tests) for debugging test failures, coverage issues, and CI troubleshooting.
