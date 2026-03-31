# Long-Running Development Harness Workflow

This workflow is aligned to Anthropic's long-running agent harness pattern and adapted for this repository.

## 1. Core Principles

1. Split planning from implementation to reduce compounding errors over long sessions.
2. Persist progress to durable artifacts so each session can resume with low context loss.
3. Use deterministic verification gates before marking work complete.
4. Change only one backlog item per session unless explicitly requested.
5. Run regression checks before new work to prevent silent drift.
6. Enforce task lifecycle states: `pending -> claimed -> in_progress -> done|blocked`.
7. Enforce stateless execution: each task run must start a fresh conversation context.

## 2. Agent Topology

1. Initializer Agent (Session 0 only): creates and freezes scope artifacts.
2. Coding Agent (Session N): claims exactly one pending item and implements it end-to-end.
3. Evaluator Agent (Session N): runs checks, scores risk, and decides pass/fail.

Notes:
- Agents can be separate processes or the same model with different prompts.
- Prompt templates are in `running/prompts/`.

## 3. Durable Artifacts

1. `running/app_spec.md`: immutable product and quality contract.
2. `running/feature_list.json`: immutable backlog body; only runtime fields are mutable.
3. `running/codex-progress.md`: session journal and aggregate status.
4. `running/prompts/initializer_prompt.md`: initializer role instructions.
5. `running/prompts/coding_prompt.md`: coding role instructions.
6. `running/prompts/evaluator_prompt.md`: evaluator role instructions.
7. `log/<YYYYMMDD-topic>.md`: root-level execution log per modification session.
8. `running/sisyphus-dispatcher.ps1`: dispatcher-only orchestrator that can run coding/evaluator workers in parallel worktrees.
9. `running/run-codex-stage.ps1`: stage launcher used by dispatcher worker processes.
10. `running/prompts/sisyphus_coding_worker_prompt.md` + `running/prompts/sisyphus_evaluator_worker_prompt.md`: worker role templates.

## 4. Task Runtime Fields (`running/feature_list.json`)

Each task must maintain these runtime fields:
1. `status`: `pending|claimed|in_progress|blocked|done`.
2. `passes`: verification result gate (`true` only when all checks pass).
3. `claimed_by`, `claimed_at`, `started_at`, `completed_at`.
4. `blocked_reason`, `human_help_requested`, `handoff_requested_at`.
5. Failure deferral fields: `defer_to_tail`, `failure_count`, `last_failure_summary`, `requeued_at`.
6. `notes`, `last_verified_at`.

State transition rules:
1. Claim task: `pending -> claimed`.
2. Begin coding: `claimed -> in_progress`.
3. Verification passed: `in_progress -> done`, and set `passes=true`.
4. Verification failed (no human dependency): summarize and requeue to tail (`status=pending`, `defer_to_tail=true`, `passes=false`).
5. Verification failed with human dependency: `in_progress -> blocked`, set `human_help_requested=true`.
6. Human resolves blocker: `blocked -> claimed` for next session.

## 5. Session 0 (Initializer)

1. Run bootstrap:

```powershell
powershell -ExecutionPolicy Bypass -File running/init.ps1 -IncludeDev
```

2. If no project root exists, create one:

```powershell
python -X utf8 webnovel-writer/scripts/webnovel.py init ./webnovel-project "My Book" "Genre"
```

3. Bind project and run baseline smoke:

```powershell
powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot ./webnovel-project -RunSmoke
```

4. Freeze `app_spec.md` and `feature_list.json` body fields.
5. Record baseline in `running/codex-progress.md` and root `log/*.md`.

## 6. Session N (Coding + Evaluator)

1. Restore context:
- `git log --oneline -20`
- `running/codex-progress.md`
- `running/feature_list.json`
- latest root `log/*.md`

2. Re-run regression checks for 1-2 completed (`status=done`) items.
3. Select one highest-priority task where `passes=false` and `status=pending`.
4. Claim task immediately:
- set `status=claimed`
- set `claimed_by=codex`, `claimed_at=<iso datetime>`
- write claim note to `notes`
5. Move to development state before edits:
- set `status=in_progress`, `started_at=<iso datetime>`
6. Run structural query first when boundaries may be affected:

```powershell
python C:/Users/wxy/.codex/skills/nexus-query/scripts/query_graph.py D:/code/webnovel-writer/.nexus-map/raw/ast_nodes.json --impact <target_path>
```

7. Implement only that single item.
8. Run the item's verification commands.
9. Frontend-specific hard gate (required for UI-affecting items):
- run `npm run build` in `webnovel-writer/dashboard/frontend`
- start app preview/dev server
- open with Playwright and execute the task checklist
- record Playwright evidence (checklist result + screenshots path) in `notes` and `codex-progress.md`
10. Evaluator decides `PASS`/`FAIL`:
- if `PASS`: set `passes=true`, `status=done`, `completed_at=<iso datetime>`
- if `FAIL`: keep `passes=false`, set `status=blocked` or `status=in_progress` with remediation note
11. Update journals:
- `running/feature_list.json` (runtime fields only)
- `running/codex-progress.md` session row
- root `log/<date-topic>.md`
12. If checks pass, create one conventional commit mapped to this task ID.

## 7. Sisyphus Dispatcher Mode (Dispatcher-only + Worker Agents)

Use this mode when you want:
1. Main orchestrator to only dispatch tasks.
2. Fresh coding worker agent per task.
3. Fresh evaluator worker agent per task.
4. Parallel task execution across isolated git worktrees.

Command:

```powershell
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 -MaxDispatches 8 -MaxParallel 3
```

Execution model:
1. Dispatcher claims task in root queue state (`feature_list.json`).
2. Dispatcher creates a new `git worktree` + branch for that task.
3. Dispatcher launches coding worker (`run-codex-stage.ps1` + coding prompt template).
   - `run-codex-stage.ps1` uses two background .NET threads to stream stdout/stderr in real time to the transcript file — output appears immediately, not after process exit.
4. After coding exits, dispatcher launches a new evaluator worker for the same task/worktree.
5. Dispatcher reads evaluator JSON verdict and updates queue state:
- `PASS` => `status=done`, `passes=true`
- `FAIL` => `status=pending` + requeue or `status=blocked` when human help is requested

Notes:
1. This preserves the existing pipeline semantics (`派任务 -> 写代码 -> 测试`), but decouples roles by process.
2. Dispatcher never performs implementation or acceptance itself.
3. Keep/cleanup worktrees can be controlled by `-KeepWorktrees`.

### Monitoring — Native Windows Terminal Pane Split

The recommended way to watch agents is via **native wt pane splitting**, not a Python renderer:

```
┌─────────────────────────────┬──────────────────┐
│  Dispatcher                 │  Task Status     │
│  (front-end, Tee to log)    ├──────────────────┤
│                             │  Agent Monitor   │
│                             │  (auto-splits    │
│                             │   new panes)     │
└─────────────────────────────┴──────────────────┘
                                      │
                         New Agent session detected:
                         ┌────────────────────────┐
                         │  CODE T003             │
                         │  Get-Content -Wait     │
                         │  (raw codex output)    │
                         └────────────────────────┘
```

- **`open-dashboard.ps1`** — one command launches the full layout above.
- **`open-agent-panes.ps1`** — polls `sessions/` every 2 s; calls `wt split-pane` for each new agent, showing raw `Get-Content -Tail -Wait` output in its own terminal pane.
- Each pane title = `CODE T003` or `EVAL T003` so stage and task are visible at a glance.

```powershell
# Recommended: one-command full dashboard
powershell -ExecutionPolicy Bypass -File running/open-dashboard.ps1 -ApiKey "sk-xxx"

# Already have a wt window? Just start the agent pane monitor inside it:
powershell -ExecutionPolicy Bypass -File running/open-agent-panes.ps1
```

Alternative (Python rich TUI, no wt required):

```powershell
# Renders dispatcher + up to 3 agent logs in one terminal with color-coded lines
python running/watch-logs.py
```

## 8. Human Assistance Branch (Blocking Path)

Trigger this branch if any condition is met:
1. Requirement ambiguity blocks implementation decisions.
2. External dependency or environment issue cannot be resolved by one retry.
3. Verification repeatedly fails and requires a human decision, not just another coding retry.

When triggered:
1. Set task `status=blocked`, `passes=false`.
2. Fill `blocked_reason`, set `human_help_requested=true`, `handoff_requested_at=<iso datetime>`.
3. Write an explicit assist request in `running/codex-progress.md` including:
- current behavior
- expected behavior
- evidence (error output/screenshots)
- exact decision needed from human
4. Stop new coding on other tasks until blocker is resolved.

## 9. Failure Recovery

1. If blocked by flaky checks, retry once and record both outputs.
2. If verification fails but is still actionable by agent, write failure summary and requeue task to queue tail.
3. If blocked by unclear requirements, stop new coding and enter Human Assistance Branch.
4. If regression appears, revert affected item to `passes=false` and fix before new work.
5. Never silently skip failed checks.

## 10. Release Gate

All conditions must hold:
1. Every item in `running/feature_list.json` has `passes=true` and `status=done`.
2. Regression checks pass for at least 2 recently completed items.
3. `webnovel codex rag verify` (when implemented) passes thresholds.
4. Docs in `docs/` and `running/` reflect actual behavior.

## 11. Quick Commands

```powershell
# Baseline bootstrap
powershell -ExecutionPolicy Bypass -File running/init.ps1 -IncludeDev

# Bind project and smoke
powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot <PROJECT_ROOT> -RunSmoke

# Canonical app startup from repo root
powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot <PROJECT_ROOT> -StartDashboard

# Frontend gate: build + run for Playwright checks
cd webnovel-writer/dashboard/frontend
npm run build
npm run preview -- --host 127.0.0.1 --port 4173

# Sisyphus dispatcher mode (parallel worktree workers)
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 -MaxDispatches 8 -MaxParallel 3

# Sisyphus dry-run (preview dispatch order only)
powershell -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 -DryRun -MaxDispatches 5

# CLI preflight
python -X utf8 webnovel-writer/scripts/webnovel.py --project-root <PROJECT_ROOT> preflight --format json

# ★ 推荐：一键启动全套原生分屏监控（Dispatcher 前台可见 + 每个 Agent 独立窗格）
powershell -ExecutionPolicy Bypass -File running/open-dashboard.ps1 -ApiKey "sk-xxx"

# 已有 wt 窗口时，单独启动 Agent 窗格监听器
powershell -ExecutionPolicy Bypass -File running/open-agent-panes.ps1

# 备选：Python rich TUI（无需 wt，单窗口内渲染多 Agent 日志）
python running/watch-logs.py

# 任务状态单独查看
python running/watch-status.py
```
