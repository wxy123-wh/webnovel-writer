# 2026-03-28 Sisyphus Dispatcher Multi-Agent Worktree Refactor

## Trigger

User requested replacing Ralph single-loop behavior with a dispatcher-only model:
1. Main process only dispatches.
2. Coding must run in fresh worker agents.
3. Acceptance/testing must run in another fresh worker agent.
4. Support parallel task handling on isolated git worktrees.

## Context Restored Before Changes

1. Read latest root log: `log/20260327-prd-refined-task-split-harness-loop-attempt.md`.
2. Read `.nexus-map/INDEX.md` and required route docs:
   - `.nexus-map/arch/systems.md`
   - `.nexus-map/arch/dependencies.md`
   - `.nexus-map/arch/test_coverage.md`
   - `.nexus-map/hotspots/git_forensics.md`
   - `.nexus-map/concepts/domains.md`
3. Ran structural summary query:
   - `python C:/Users/wxy/.codex/skills/nexus-query/scripts/query_graph.py D:/code/webnovel-writer/.nexus-map/raw/ast_nodes.json --summary`

## Key Changes

1. Added dispatcher worker prompt templates:
   - `running/prompts/sisyphus_coding_worker_prompt.md`
   - `running/prompts/sisyphus_evaluator_worker_prompt.md`

2. Added stage launcher:
   - `running/run-codex-stage.ps1`
   - Purpose: run one `codex exec --ephemeral` stage with prompt file, transcript file, last-message file, sandbox and provider args.

3. Added dispatcher orchestration script:
   - `running/sisyphus-dispatcher.ps1`
   - Implements:
     - pending-task pickup and claim (`claimed -> in_progress`)
     - per-task worktree + branch creation
     - coding worker launch (fresh process)
     - evaluator worker launch (fresh process)
     - evaluator-driven PASS/FAIL update to `running/feature_list.json`
     - queue requeue/blocked handling and progress journal append
     - parallel active pipelines (`-MaxParallel`)
     - dry-run preview (`-DryRun`)

4. Updated workflow documentation:
   - `running/workflow.md`
   - Added Sisyphus dispatcher mode section and commands.

5. Updated progress rule references:
   - `running/codex-progress.md`
   - Added dispatcher-mode rule: dispatcher only dispatches, workers execute coding/evaluation.

## Verification

1. PowerShell parse check:
   - `running/run-codex-stage.ps1` => `PARSE_OK`
   - `running/sisyphus-dispatcher.ps1` => `PARSE_OK`

2. Dispatcher dry-run:
   - Command: `powershell -NoProfile -ExecutionPolicy Bypass -File running/sisyphus-dispatcher.ps1 -DryRun -MaxDispatches 3`
   - Result: correctly previews top pending tasks (`T001`, `T002`, `T003`) and prints resolved worktree root.

## Notes

1. This refactor keeps the original flow semantics (`派任务 -> 写代码 -> 测试`) but separates each stage into fresh processes.
2. Dispatcher does not perform coding/acceptance logic; it only orchestrates and updates queue state based on worker outcomes.
