---
description: Maintain git worktrees - identify merged PRs for cleanup and rename generic branches
allowed-tools: Read, Glob, Grep, Bash, mcp__github__list_pull_requests, mcp__github__pull_request_read, mcp__github__get_me, mcp__github__search_pull_requests, AskUserQuestion
---

# Git Worktree Maintenance

You are performing maintenance on the project's git worktrees.

## Process

### 1. List All Worktrees
Run `git worktree list` to see all current worktrees.

### 2. Get PR Status for Each Branch
For each worktree (excluding main), check the PR status:
- Use `gh pr list --state all --limit 50 --json number,title,headRefName,state,mergedAt` to get PR info
- Match each worktree branch to its PR
- Identify: MERGED (can cleanup), OPEN (keep), NO PR (investigate)

### 3. Categorize Worktrees

**Can be cleaned up (PRs merged):**
- List worktrees where the associated PR has been merged
- These are safe to remove with `git worktree remove <path>`

**Outstanding/WIP (keep):**
- List worktrees with open PRs
- Check if the worktree name is descriptive or generic (e.g., "work-20251230-151202", "session-YYYY-MM-DD-HHMM")
- For generic names, read the PR title/description to suggest a better name

**No PR found:**
- Flag these for user attention - may be abandoned work or local-only branches

### 4. Present Findings

Show a summary table:
```
## Can be cleaned up (merged):
| Worktree | Branch | PR # |
|----------|--------|------|

## Outstanding PRs (keep):
| Worktree | Branch | PR # | Suggested Rename |
|----------|--------|------|------------------|

## No PR found:
| Worktree | Branch | Notes |
|----------|--------|-------|
```

### 5. Ask User for Action

Use AskUserQuestion to ask what to do:
- Clean up all merged worktrees?
- Rename generic worktree names to descriptive ones?
- Investigate worktrees with no PR?

### 6. Execute Cleanup

If user approves:

**Removing merged worktrees:**
```bash
git worktree remove <path>
```
If there are uncommitted changes, check if they're already in main before force-removing.

**Renaming worktrees:**
```bash
mv <old-path> <new-path>
git worktree repair <new-path>
git worktree prune
```

### 7. Final Verification

Run `git worktree list` again to confirm the final state.

## Important Notes

- Never remove the main worktree
- Always check for uncommitted changes before removing
- If a worktree has changes not in main, offer to create a PR first
- Generic names to watch for: `work-YYYYMMDD-*`, `session-YYYY-MM-DD-*`, `feature/work-*`
- Good descriptive names should reflect the PR content (e.g., `log-timing-analyzer`, `e2e-completion`)
