# Project Guidelines for AI Assistants

This document contains guidelines and rules for AI assistants working on this codebase.

## Branching Workflow

**Never commit directly to `main`.** Always work on a feature branch.

Create descriptive branch names like `feature/add-discord-notifications`, `fix/audio-sync-issue`, or `refactor/cleanup-api-routes`.

### Using Git Worktrees

**For non-trivial changes** (new features, multi-file edits, refactors):
- Create a git worktree in the parent folder before making any file changes:
  ```bash
  git worktree add ../karaoke-gen-feat-xyz feature/xyz
  ```
- This keeps the main directory clean on `main` and enables parallel work on multiple features
- Name the worktree folder descriptively, e.g., `../karaoke-gen-fix-audio-sync`

**For trivial changes** (typos, single-line fixes):
- Creating a branch in the current directory is acceptable
- Use `git checkout -b fix/typo-xyz` before making changes

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

When committing and pushing changes, always bump the patch version in `pyproject.toml`.

The version is located at `tool.poetry.version` in `pyproject.toml`. For example, if the current version is `0.70.3`, bump it to `0.70.4`.

This ensures every commit pushed to the repository has a unique version number for tracking and deployment purposes.

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

