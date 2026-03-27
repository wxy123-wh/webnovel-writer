# 2026-03-28 GitHub Submit: Commercial Rollout Batch

## Trigger

User requested: commit and push all current workspace changes to GitHub.

## Context Restored

1. Read latest log: `log/20260328-tasks-and-harness-launch-ready.md`.
2. Read `.nexus-map/INDEX.md` and required routing files:
   - `arch/systems.md`
   - `arch/dependencies.md`
   - `arch/test_coverage.md`
   - `hotspots/git_forensics.md`
   - `concepts/domains.md`
3. Read commit skill requirements and recent commit history.
4. Inspected current git status, remote, and diff statistics.

## Batch Summary

This submission packages an already-existing rollout batch spanning repository migration, dashboard/API work, scripts, docs, and generated frontend assets.

### 1. Codex migration and repository cleanup

- Renamed plugin artifacts from `.claude-plugin` to `.codex-plugin`.
- Updated README, development docs, references, skills, agents, and shared guidance from Claude-oriented wording to Codex-oriented wording.
- Removed obsolete docs and temporary tracked fixture files under `docs/` and `__temp__/`.

### 2. Dashboard and frontend updates

- Added Codex bridge API surface and related model/test files.
- Updated settings, outlines, runtime, and dictionary-related router/service/frontend code.
- Refreshed frontend API tests and regenerated built assets under `dashboard/frontend/dist/`.

### 3. Scripts and workflow alignment

- Updated project locator, config, migration, CLI, RAG, and related data-module tests.
- Added/updated PRD and running workflow artifacts for the commercial rollout stream.
- Added `.nexus-map/` knowledge-base outputs to the repository state.

## Diff Snapshot

- Files changed: 134
- Insertions: 984
- Deletions: 7497
- Branch: `codex/commercial-rollout-delivery`
- Remote: `origin git@github.com:wxy123-wh/webnovel-writer.git`

## Commit Intent

Create one focused Conventional Commit covering the full rollout batch and push it to the tracked GitHub branch.
