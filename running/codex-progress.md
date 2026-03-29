# Codex Progress (Long-Running Dev Harness)

## Session Rules

1. Restore context before any code changes:
- `git log --oneline -20`
- `running/codex-progress.md`
- `running/feature_list.json`
- latest root `log/*.md`

2. Re-run 1-2 completed (`status=done`) items before starting a new task.
3. Claim exactly one `passes=false` + `status=pending` task per session by default.
4. Update runtime fields in sequence: `claimed -> in_progress -> done|blocked`.
5. If interfaces/boundaries may change, run `query_graph.py --impact` first.
6. Frontend/UI tasks must pass `npm run build` and Playwright verification before marking done.
7. Update `running/feature_list.json`, `running/codex-progress.md`, and root `log/*.md` each session.
8. If checks pass, create one conventional commit mapped to one task ID.
9. Every session must be isolated context: run as a new `codex exec --ephemeral` process (no resume/fork).
10. Failed-but-actionable tasks must be summarized and requeued to tail (`defer_to_tail=true`) instead of being silently dropped.
11. In Sisyphus dispatcher mode, root process only dispatches; coding and evaluator must run as fresh worker processes (can be parallel across worktrees).

## Current Status

- Total items: 16
- Passed items: 0
- Done items: 0
- Blocked items: 0
- Active mode: Development Harness (Initializer + Coding + Evaluator)

## Session Journal

| Date | Session Goal | Claimed Item | Final Task Status | Regression Checks | Verification Evidence | Commit(s) | Result | Human Assist | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-27 | Rewrite harness as development workflow (Anthropic-aligned) | D001-D015 backlog reset | in_progress | N/A (baseline reset) | init + smoke rerun required next session | None | In Progress | No | Replaced writing-oriented framing with long-running dev harness topology |
| 2026-03-27 | Add stateless ralph loop execution path | N/A (process hardening) | in_progress | N/A | `ralph-loop.ps1 -MaxIterations 1 -DryRun` passed | None | In Progress | No | Added `codex exec --ephemeral` loop runner and enforced fresh-session rules across workflow/spec/prompts |
| 2026-03-27 | Add fail-summary and tail requeue policy | N/A (process hardening) | in_progress | N/A | `ralph-loop.ps1 -MaxIterations 1 -DryRun` passed; script parse passed | None | In Progress | No | Failed tasks now auto-summarize and requeue to tail (`defer_to_tail=true`) unless human help is required |
| 2026-03-27 | Runtime smoke test and loop stability fixes | N/A (process hardening) | in_progress | N/A | Parse + JSON + DryRun passed; non-DryRun control flow passed with graceful codex failure handling | None | In Progress | No | Fixed native stderr termination and prompt rendering; remaining blocker is external API stream disconnect |
| 2026-03-27 | Switch Codex API base URL to api.asxs.top | N/A (runtime config hardening) | in_progress | N/A | DryRun shows `API base URL: https://api.asxs.top/v1`; real run logs requests to `/v1/responses` on api.asxs.top | None | In Progress | No | Added `ApiBaseUrl` parameter to runner and applied env injection/restore around each codex exec |
| 2026-03-27 | Add loop runner API key parameter injection | N/A (runtime config hardening) | in_progress | N/A | DryRun with `-ApiKey` passed; env set/restore branches validated | None | In Progress | No | Added `-ApiKey` to `ralph-loop.ps1` so each isolated run can use explicit key without global environment dependency |
| 2026-03-27 | Split `docs/prd-refined.md` into harness tasks and run loop | T001-T016 | pending (auto-requeued) | N/A (no `done` items) | `ralph-loop.ps1` real runs completed but all items requeued; session logs show provider-policy read-only block in isolated mode and stream disconnect in inherited mode against `api.asxs.top` | None | Blocked by runtime environment | No | Rebuilt `running/feature_list.json` (v4, PRD-based), added sandbox + dirty-worktree guard to `ralph-loop.ps1`, and added inherited-provider base URL override support |
| 2026-03-28 | Generate TASKS.md and harness launch script; validate dry-run | N/A (harness tooling) | ready to launch | Dry-run: all 16 tasks T001-T016 in queue, correct priority order, codex-cli 1.3.0 resolved | `start-harness.ps1 -DryRun` passed; all 16 tasks visible | None | Ready | No | Created `running/TASKS.md` (full task list with steps+acceptance), `running/start-harness.ps1` (one-click launcher with interactive API key prompt). Awaiting API key to start real execution. |

## Human Assistance Queue

| Date | Task ID | Blocker | Decision Needed | Status |
| --- | --- | --- | --- | --- |
| N/A | N/A | N/A | N/A | Empty |

## Open Risks

1. Isolated asxs provider sessions are constrained to read-only/policy-blocked command execution, so coding tasks cannot complete in-loop.
2. Inherited provider mode avoids read-only but currently stream-disconnects when targeting `https://api.asxs.top/v1/responses`.
3. Frontend acceptance still requires stable Playwright MCP startup in loop sub-sessions.

## Next Session Plan

1. Set `OPENAI_API_KEY` or pass `-ApiKey` to the launcher.
2. Run `running/start-harness.ps1` (Sisyphus mode, 16 tasks, 2 parallel).
3. Keep PRD queue order T001 → T016; require evidence-backed completion before release gate.
4. Task list with full steps and acceptance criteria: `running/TASKS.md`.

## Launch Commands

```powershell
# Option A: Sisyphus parallel dispatcher (recommended)
$env:OPENAI_API_KEY = "<your-key>"
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1

# Option B: Ralph single-thread loop
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -Mode ralph

# Option C: Direct dispatcher call
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 `
  -RepoRoot d:\code\webnovel-writer `
  -MaxDispatches 16 -MaxParallel 2 `
  -ApiKey $env:OPENAI_API_KEY `
  -ApiBaseUrl https://api.asxs.top/v1

# Dry-run preview only
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -DryRun -ApiKey dummy
```
| 2026-03-28 | Sisyphus dispatcher run | T015 | pending | N/A | stage=evaluator; run=20260328-052204-02-T015 | codex/sisyphus/t015-20260328-052204-02-T015 | FAIL | N/A | gaps: Attempted to run `python -X utf8 webnovel-writer/scripts/webnovel.py codex rag verify --project-root . --report json`, but command execution failed before the script started with `windows sandbox: CreateProcessWithLogonW failed: 2`.; Could not verify that the JSON report includes all required metrics, that threshold violations return a non-zero exit code, or that the pass summary is machine-readable because no verification command produced output. |
| 2026-03-28 | Sisyphus dispatcher run | T010 | blocked | N/A | stage=coding; run=20260328-051625-01-T010 | codex/sisyphus/t010-20260328-051625-01-T010 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T002 | blocked | N/A | stage=coding; run=20260328-062139-02-T002 | codex/sisyphus/t002-20260328-062139-02-T002 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T003 | blocked | N/A | stage=coding; run=20260328-081905-01-T003 | codex/sisyphus/t003-20260328-081905-01-T003 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T016 | blocked | N/A | stage=coding; run=20260328-052705-01-T016 | codex/sisyphus/t016-20260328-052705-01-T016 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T004 | blocked | N/A | stage=coding; run=20260328-050954-01-T004 | codex/sisyphus/t004-20260328-050954-01-T004 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T005 | blocked | N/A | stage=coding; run=20260328-050955-02-T005 | codex/sisyphus/t005-20260328-050955-02-T005 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T003 | blocked | N/A | stage=coding; run=20260328-055118-01-T003 | codex/sisyphus/t003-20260328-055118-01-T003 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T004 | blocked | N/A | stage=coding; run=20260328-055119-02-T004 | codex/sisyphus/t004-20260328-055119-02-T004 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-054318-01-T001 | codex/sisyphus/t001-20260328-054318-01-T001 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T006 | blocked | N/A | stage=coding; run=20260328-051153-01-T006 | codex/sisyphus/t006-20260328-051153-01-T006 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T008 | blocked | N/A | stage=coding; run=20260328-051414-01-T008 | codex/sisyphus/t008-20260328-051414-01-T008 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T002 | blocked | N/A | stage=coding; run=20260328-053437-02-T002 | codex/sisyphus/t002-20260328-053437-02-T002 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-053101-01-T001 | codex/sisyphus/t001-20260328-053101-01-T001 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T007 | blocked | N/A | stage=coding; run=20260328-051154-02-T007 | codex/sisyphus/t007-20260328-051154-02-T007 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T009 | blocked | N/A | stage=coding; run=20260328-051415-02-T009 | codex/sisyphus/t009-20260328-051415-02-T009 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T002 | blocked | N/A | stage=coding; run=20260328-053102-02-T002 | codex/sisyphus/t002-20260328-053102-02-T002 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T011 | blocked | N/A | stage=coding; run=20260328-051625-02-T011 | codex/sisyphus/t011-20260328-051625-02-T011 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T012 | blocked | N/A | stage=coding; run=20260328-051855-01-T012 | codex/sisyphus/t012-20260328-051855-01-T012 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T013 | blocked | N/A | stage=coding; run=20260328-051856-02-T013 | codex/sisyphus/t013-20260328-051856-02-T013 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-062137-01-T001 | codex/sisyphus/t001-20260328-062137-01-T001 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-053748-01-T001 | codex/sisyphus/t001-20260328-053748-01-T001 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T002 | blocked | N/A | stage=coding; run=20260328-053749-02-T002 | codex/sisyphus/t002-20260328-053749-02-T002 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T014 | blocked | N/A | stage=coding; run=20260328-052203-01-T014 | codex/sisyphus/t014-20260328-052203-01-T014 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T003 | blocked | N/A | stage=coding; run=20260328-053831-03-T003 | codex/sisyphus/t003-20260328-053831-03-T003 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-053436-01-T001 | codex/sisyphus/t001-20260328-053436-01-T001 | FAIL | N/A | Coding worker exit code -1 |
| 2026-03-28 | Sisyphus dispatcher run | T007 | blocked | N/A | stage=coding; run=20260328-110657-01-T007 | codex/sisyphus/t007-20260328-110657-01-T007 | FAIL | N/A | Coding worker exit code 2 |
| 2026-03-28 | Sisyphus dispatcher run | T008 | blocked | N/A | stage=coding; run=20260328-110658-02-T008 | codex/sisyphus/t008-20260328-110658-02-T008 | FAIL | N/A | Coding worker exit code 2 |
| 2026-03-28 | Sisyphus dispatcher run | T009 | blocked | N/A | stage=coding; run=20260328-221615-01-T009 | codex/sisyphus/t009-20260328-221615-01-T009 | FAIL | N/A | Coding worker exit code 2 |
| 2026-03-28 | Sisyphus dispatcher run | T009 | blocked | N/A | stage=coding; run=20260328-222442-01-T009 | codex/sisyphus/t009-20260328-222442-01-T009 | FAIL | N/A | Coding worker exit code 2 |
| 2026-03-28 | Sisyphus dispatcher run | T009 | blocked | N/A | stage=coding; run=20260328-223238-01-T009 | codex/sisyphus/t009-20260328-223238-01-T009 | FAIL | N/A | Coding worker exit code 2 |
| 2026-03-28 | Sisyphus dispatcher run | T009 | blocked | N/A | stage=coding; run=20260328-223459-01-T009 | codex/sisyphus/t009-20260328-223459-01-T009 | FAIL | N/A | Coding worker exit code 2 |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-225024-01-T001 | codex/sisyphus/t001-20260328-225024-01-T001 | FAIL | N/A | Coding worker exit code  |
| 2026-03-28 | Sisyphus dispatcher run | T001 | blocked | N/A | stage=coding; run=20260328-225151-01-T001 | codex/sisyphus/t001-20260328-225151-01-T001 | FAIL | N/A | Coding worker exit code  |
| 2026-03-28 | Sisyphus dispatcher run | T002 | blocked | N/A | stage=coding; run=20260328-225441-01-T002 | codex/sisyphus/t002-20260328-225441-01-T002 | FAIL | N/A | Coding worker exit code  |
