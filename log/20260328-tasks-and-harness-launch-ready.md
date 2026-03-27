# 2026-03-28 Tasks List Generated + Harness Launch Ready

## Trigger

User requested: generate a running task list from `docs/prd-refined.md` and start the Codex development harness.

## Context Restored

1. Read `docs/prd-refined.md` (PRD freeze, M1/M2/M3 milestones, 16 deliverables).
2. Read `running/feature_list.json` (v4, T001–T016, all `pending`).
3. Read `running/workflow.md`, `running/codex-progress.md`, `running/app_spec.md`.
4. Read dispatcher + runner scripts: `sisyphus-dispatcher.ps1`, `ralph-loop.ps1`, `run-codex-stage.ps1`.
5. Read worker prompt templates: `sisyphus_coding_worker_prompt.md`, `sisyphus_evaluator_worker_prompt.md`.
6. Read latest logs: `20260328-running-smoke-test.md`, `20260328-sisyphus-dispatcher-multi-agent-worktree.md`.

## State Assessment

- `codex-cli 1.3.0` at `C:\Users\wxy\.local\bin\codexx.cmd` — operational.
- All 16 tasks T001–T016 in `pending` state, correct priority order.
- `running/.codex-home/config.toml` points to `http://127.0.0.1:18888/v1` (gateway bridge).
- `ralph-loop.ps1` auto-starts bridge from `running/codex-gateway-bridge.py` when `-ApiBaseUrl` is `https://`.
- `OPENAI_API_KEY` not set in current shell — needs to be provided at launch.

## Actions Taken

### 1. Created `running/TASKS.md`

Full human-readable task list derived from `docs/prd-refined.md` and `running/feature_list.json`:
- Queue overview table (all 16 tasks with ID, milestone, priority, risk, status)
- Per-task sections with: 目标、步骤、验收命令、验收检查
- M1 (T001–T008): Frontend read-only conversion + backend write route deletion
- M2 (T009–T013): Unified CLI + incremental index + fast lookup
- M3 (T014–T016): Session skill profiles + RAG 13-tier verification + CI gate
- Launch commands section at bottom

### 2. Created `running/start-harness.ps1`

One-click harness launcher with:
- `-Mode sisyphus` (default) or `-Mode ralph`
- `-ApiKey` parameter; falls back to `$env:OPENAI_API_KEY`; interactive prompt in non-DryRun mode
- `-DryRun` flag skips prompt and real execution, shows queue preview only
- Auto-shows 16-task dry-run preview before any real execution
- Forwards all args to `sisyphus-dispatcher.ps1` or `ralph-loop.ps1`

### 3. Updated `running/codex-progress.md`

- Replaced stale "Next Session Plan" with current launch commands
- Added session journal row for 2026-03-28

## Verification

```
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -DryRun -ApiKey dummy
```

Output confirmed:
- `codex-cli 1.3.0` resolved at `C:\Users\wxy\.local\bin\codexx.cmd`
- All 16 tasks displayed in priority order (T001 p=1 → T016 p=16)
- `defer_to_tail` tasks correctly sorted to end within milestone
- DryRun exits cleanly without any real codex execution

## Task Queue Order (from dry-run)

| Order | ID | Priority | Title |
|-------|----|----------|-------|
| 1 | T001 | 1 | M1 read-only contract and shared indicator |
| 2 | T002 | 2 | M1 SkillsPage read-only conversion |
| 3 | T003 | 3 | M1 SettingsPage read-only conversion |
| 4 | T004 | 4 | M1 OutlineWorkspacePage read-only conversion |
| 5 | T005 | 5 | M1 FilesPage read-only conversion |
| 6 | T006 | 6 | M1 remove dashboard write routes (runtime/skills/settings) |
| 7 | T007 | 7 | M1 remove dashboard write routes (outlines/edit-assist/codex) |
| 8 | T008 | 8 | M1 acceptance gate and migration notes |
| 9 | T009 | 9 | M2 add unified webnovel codex command group |
| 10 | T010 | 10 | M2 implement codex session start/stop |
| 11 | T011 | 11 | M2 implement project-scoped index status artifacts |
| 12 | T012 | 12 | M2 file watcher and incremental auto-index |
| 13 | T013 | 13 | M2 fast lookup by chapter number and scene tag |
| 14 | T014 | 14 | M3 session-scoped skill profile loader |
| 15 | T015 | 15 | M3 implement codex rag verify metrics command |
| 16 | T016 | 16 | M3 CI gate and final acceptance package |

(Tasks with `defer_to_tail=true` are sorted after normal-priority tasks at the same priority level.)

## How to Launch

```powershell
# Set your API key first
$env:OPENAI_API_KEY = "<your-key>"

# Launch Sisyphus parallel dispatcher (recommended)
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1

# Or launch Ralph single-thread loop
powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -Mode ralph

# Or directly
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 `
  -RepoRoot d:\code\webnovel-writer `
  -MaxDispatches 16 -MaxParallel 2 `
  -ApiKey $env:OPENAI_API_KEY `
  -ApiBaseUrl https://api.asxs.top/v1
```

## Known Constraints

1. API key must be valid for `api.asxs.top` (asxs provider, OpenAI-compatible).
2. Gateway bridge (`codex-gateway-bridge.py`) is auto-started by `ralph-loop.ps1` when upstream is `https://`.
3. `sisyphus-dispatcher.ps1` does **not** auto-start the bridge — it passes `ApiBaseUrl` directly to `run-codex-stage.ps1` which sets `OPENAI_BASE_URL` env var.
4. Frontend tasks (T001–T005, T008) require `npm run build` and Playwright MCP — these run inside each worker's codex session.
5. Worktrees are created under `d:\code\webnovel-writer\.worktrees\sisyphus\` — ensure sufficient disk space.
