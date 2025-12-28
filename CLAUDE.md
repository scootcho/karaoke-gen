# Project Guidelines for AI Assistants

This document contains guidelines and rules for AI assistants working on this codebase.

## Core Principles

**Always be testing.** Proactively evaluate, read, run, fix, and improve tests whenever you touch any part of the system—frontend, backend, infrastructure. Every code change should be thoroughly tested. Leave everything better tested than you found it.

**Always be documenting.** Continuously read, write, improve, update, and organize markdown documentation. Reference existing docs and keep them accurate as the codebase evolves.

**Build for maintainability.** Keep code SOLID, modular, and clean. Favor simplicity and clarity. Future developers (and AI agents) will thank you.

## Branching Workflow

**Never commit directly to `main`.** Always work on a feature branch.

Create descriptive branch names like `feature/add-discord-notifications`, `fix/audio-sync-issue`, or `refactor/cleanup-api-routes`.

### Using Git Worktrees

**All changes require a git worktree.** Since all changes must go through a PR, always create a worktree in the parent folder before making any file changes:

```bash
git worktree add -b feature/xyz ../karaoke-gen-feat-xyz main
```

- This keeps the main directory clean on `main` and enables parallel work on multiple features
- Name the worktree folder descriptively, e.g., `../karaoke-gen-fix-audio-sync`

**Cleanup:** When done with a worktree, remove it with:
```bash
git worktree remove ../karaoke-gen-feat-xyz
```

### Creating a Pull Request

Once all changes are complete, tests pass, and commits are pushed, create a PR with:

1. **Summary** - Brief overview of the changes
2. **Changes Made** - List of specific modifications
3. **Testing** - How changes were tested (unit tests, manual testing)
4. **Related Issues** - Reference any GitHub issues (e.g., "Fixes #123")

Only merge after review and CI checks pass.

## Infrastructure Changes

All Google Cloud infrastructure (IAM, Cloud Storage, Cloud Run, Secret Manager, Artifact Registry, etc.) must be managed via **Pulumi IaC** in the `infrastructure/` folder.

### Rules

- **Reading/querying** with `gcloud` CLI is fine for investigation and debugging
- **Temporary changes** via `gcloud` CLI or Console are acceptable for urgent fixes or experimentation, but **must be cleaned up** and properly codified in the IaC afterward
- **Permanent changes** must go through Pulumi — never leave `gcloud` or Console changes as the final state

### Workflow

1. Make changes in `infrastructure/`
2. Run `pulumi preview` and verify the output
3. Run `pulumi up` to apply

### Authentication Issues

If you encounter any authentication issues with `gcloud` or `pulumi` (e.g., expired tokens, permission errors), **stop and notify the user** so they can run the appropriate auth commands in their external terminal:

```bash
gcloud auth login
gcloud auth application-default login
```

Do not attempt to work around auth issues or make assumptions about credentials.

## Version Management

When committing and pushing **code changes**, bump the patch version in `pyproject.toml`.

The version is located at `tool.poetry.version` in `pyproject.toml`. For example, if the current version is `0.70.3`, bump it to `0.70.4`.

**Skip version bumps** for documentation-only changes (e.g., updating `CLAUDE.md`, `README.md`, or other markdown files) that don't affect deployed code.

This ensures every code release has a unique version number for tracking and deployment purposes.

## Testing Requirements

**Before committing and pushing ANY changes, you MUST run the full test suite.**

### Backend Test Command

```bash
make test 2>&1 | tail -n 500
```

**Important for AI agents:**
- Set a **10 minute timeout** when running tests (they can take a while with emulators)
- Always pipe output through `tail -n 500` to limit output and preserve context window
- The tail output will show test results and any failures at the end

This runs all backend tests in order and fails fast if any test fails:
1. Unit tests (karaoke_gen package) with coverage check
2. Backend unit tests
3. E2E integration tests with emulators (auto-starts/stops emulators)

### Frontend Test Command

When working in the `frontend/` directory, run:

```bash
cd frontend && npm run test:all 2>&1 | tail -n 200
```

This runs:
1. **Unit tests** (Jest) - Component and utility tests
2. **E2E tests** (Playwright) - Browser-based integration tests

**Note:** E2E tests require `KARAOKE_ACCESS_TOKEN` environment variable to be set in `frontend/.env.local`.

Individual test commands:
- `npm run test:unit` - Run unit tests only
- `npm run test:e2e` - Run E2E tests only
- `npm run test:ci` - Run unit tests with coverage

### Pre-commit Checklist

- [ ] `make test` passes (for backend changes)
- [ ] `cd frontend && npm run test:all` passes (for frontend changes)
- [ ] Version in `pyproject.toml` has been bumped
- [ ] `coderabbit review --plain` has been run to get comprehensive analysis and suggestions for cleaner, more maintainable code. Apply the feedback to improve accessibility, structure, and best practices.

**Do not commit or push code that fails tests. Fix any test failures before proceeding.**

## Related Projects

### flacfetch

**Location:** `/Users/andrew/Projects/flacfetch`

The `flacfetch` package is a dependency of karaoke-gen that we also own. When working on features that interact with flacfetch, you can read and modify its code directly.

**Workflow for flacfetch changes:**

1. Navigate to `/Users/andrew/Projects/flacfetch`
2. Create a worktree and make changes (same branching rules apply)
3. Run tests and ensure they pass
4. Bump the version in flacfetch's `pyproject.toml`
5. Commit, push, and create a PR
6. Wait for CI workflow to complete and auto-release the new version
7. Return to karaoke-gen and update the poetry dependency:
   ```bash
   poetry update flacfetch
   ```
8. Commit the updated `poetry.lock` in karaoke-gen

