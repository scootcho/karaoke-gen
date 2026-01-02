# Karaoke-Gen AI Assistant Guidelines

## Project Overview

**Karaoke video generation platform** - CLI tool and web service that creates professional karaoke videos with synchronized lyrics.

- **Production**: <https://gen.nomadkaraoke.com> (frontend), <https://api.nomadkaraoke.com> (backend)
- **CLI**: `karaoke-gen` (local), `karaoke-gen-remote` (cloud)
- **Repo**: <https://github.com/nomadkaraoke/karaoke-gen>

## Quick Reference

| What | Where |
|------|-------|
| Product vision & goals | `docs/PRODUCT-VISION.md` |
| Current status | `docs/README.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Dev setup & testing | `docs/DEVELOPMENT.md` |
| API reference | `docs/API.md` |
| Past learnings | `docs/LESSONS-LEARNED.md` |

## Tech Stack

- **Backend**: FastAPI on Cloud Run, Firestore, GCS, Secret Manager
- **Frontend**: Next.js on Cloudflare Pages
- **Processing**: Modal (GPU audio separation), AudioShake/Whisper (transcription)
- **Infra**: Pulumi IaC, GitHub Actions CI/CD

## Essential Rules

### Git Workflow
- **Never commit directly to `main`** - use `/new-worktree <description>` to start
- **Follow global workflow** - see `~/.claude/CLAUDE.md` for command sequence
- Create PR with summary, changes, testing info
- Merge only after CI passes

### Testing (Required Before Commit)
```bash
# Backend (10 min timeout, limit output)
make test 2>&1 | tail -n 500

# Frontend
cd frontend && npm run test:all 2>&1 | tail -n 200
```

### Version Bumping
- Bump `tool.poetry.version` in `pyproject.toml` for code changes
- Skip for docs-only changes

### Infrastructure
- All GCP changes via Pulumi in `infrastructure/`
- `gcloud` CLI for reading/debugging only
- Stop and notify user on auth issues

## Documentation Maintenance

### Structure
```text
docs/
├── README.md          # Current status + navigation (UPDATE THIS)
├── ARCHITECTURE.md    # System design
├── DEVELOPMENT.md     # Dev setup, testing, deployment
├── API.md             # Backend API reference
├── LESSONS-LEARNED.md # Key insights for future agents
└── archive/           # Historical docs (YYYY-MM-DD-topic.md)
```

### Rules
1. **Before merging PRs**: Run `/docs-review` to check if docs need updating
2. **Periodically**: Run `/docs-maintain` to verify docs are organized
3. **For significant work**: Create `docs/archive/YYYY-MM-DD-topic.md`
4. **Add learnings**: Update `docs/LESSONS-LEARNED.md` with insights
5. **Keep status current**: Update `docs/README.md` when project state changes

### What Goes Where
- **README.md**: Current status, known issues, quick links
- **ARCHITECTURE.md**: System design, data flow, tech decisions
- **DEVELOPMENT.md**: Setup, testing, deployment, CI/CD
- **API.md**: Endpoints, request/response formats
- **LESSONS-LEARNED.md**: What worked, what didn't, gotchas
- **archive/**: Completed work, session summaries, old plans

## Related Projects

### flacfetch
Location: `/Users/andrew/Projects/flacfetch`

Workflow: Make changes on `main`, bump version, push, wait for CI, then `poetry update flacfetch` in karaoke-gen.

## Pre-PR Checklist

Follow global workflow (`~/.claude/CLAUDE.md`):

- [ ] Tests pass: `/test` (or `make test` / `npm run test:all`)
- [ ] Version bumped (if code changed)
- [ ] Docs checked: `/docs-review`
- [ ] Code reviewed: `/review` (CodeRabbit CLI)
- [ ] PR created: `/pr` (adds @coderabbitai ignore)
