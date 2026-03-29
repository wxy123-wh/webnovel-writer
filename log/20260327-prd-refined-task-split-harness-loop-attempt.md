# 2026-03-27 PRD refined task split + harness loop run attempt

## Trigger

User requested to split `docs/prd-refined.md` into executable tasks and start the `running/` harness loop until acceptance.

## Context Restored Before Changes

1. Read latest root log: `log/20260327-codex-gateway-stream-bridge.md`.
2. Read `.nexus-map/INDEX.md` and required routing docs:
   - `.nexus-map/arch/systems.md`
   - `.nexus-map/arch/dependencies.md`
   - `.nexus-map/arch/test_coverage.md`
   - `.nexus-map/hotspots/git_forensics.md`
   - `.nexus-map/concepts/domains.md`
3. Ran structural queries with `query_graph.py` (`--summary` and `--impact` on key entry files).

## Key Changes

1. Rebuilt `running/feature_list.json` from PRD scope (version 4).
- Source anchored to `docs/prd-refined.md`.
- Replaced previous D001-D015 process-heavy list with PRD-oriented queue `T001..T016` across M1/M2/M3.
- Preserved harness runtime fields and requeue fields required by `running/workflow.md`.

2. Hardened `running/ralph-loop.ps1` for current repository reality.
- Added `CodexSandbox` parameter (default `workspace-write`).
- Injected sandbox argument into `codex exec` call.
- Updated session prompt with explicit rule that dirty worktree is expected (do not stop only because git status is dirty).
- Added inherited-provider base URL override for non-isolated mode:
  - appends `-c model_provider="codex"`
  - appends `-c model_providers.codex.base_url="<effectiveApiBaseUrl>"`

3. Updated `running/codex-progress.md` to reflect PRD queue reset and loop execution outcomes.

## Harness Execution Evidence

### Commands run

1. `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1` (no key)
- Result: failed (`OPENAI_API_KEY` missing in isolated provider mode).

2. `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 20 -ApiKey <masked>`
- Result: loop iterated; all tasks auto-requeued (`passes=false`, `status=pending`), no completion.
- Failure pattern in session logs:
  - isolated provider path forced read-only/policy-restricted execution in sub-sessions.

3. `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -DisableIsolatedCodexHome -ApiKey <masked>`
- Result: sub-session had workspace-write but transport still disconnected when reaching `https://api.asxs.top/v1/responses`.

4. `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -DisableIsolatedCodexHome -ApiKey <masked>` after adding provider override args
- Result: command entered launch path with override arguments; long-running sessions still unresolved within tool timeout window.

## Current Backlog Runtime State

- `running/feature_list.json` has 16 tasks (`T001..T016`).
- All tasks remain `status=pending`, `passes=false`.
- Auto-requeue counters incremented by loop attempts (notably `T001`).

## Main Blockers Identified

1. Isolated asxs provider sessions return policy-limited behavior for command execution in sub-agents.
2. Non-isolated provider mode can be workspace-write, but upstream transport to asxs is unstable unless base URL routing is fully stabilized.
3. Playwright MCP startup in sub-sessions is inconsistent and may block frontend gate evidence capture.

## Next Recommended Continuation Point

1. Stabilize one provider route for sub-sessions (writable + stable streaming).
2. Resume loop from `T001` and verify first successful `done/passes=true` transition.
3. Continue `T001 -> T016` with evidence-backed acceptance gates.