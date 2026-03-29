# 2026-03-27 ralph loop stateless session workflow

## Trigger

User requested:
1. complete the harness loop process,
2. ensure execution does not continue in one long chat,
3. guarantee each run clears context and starts from durable artifacts.

## Key changes

1. Added executable loop runner.
- File: `running/ralph-loop.ps1`
- Implements iterative task pickup from `running/feature_list.json`.
- Selects highest-priority pending item each iteration.
- Launches Codex with `codex exec --ephemeral` every iteration.
- Stops on blocked tasks requiring human help unless explicitly overridden.
- Stores per-iteration artifacts under `running/sessions/<run-id>/`.

2. Enforced stateless-session contract in workflow docs.
- File: `running/workflow.md`
- Added explicit rule: each run must start fresh context.
- Added dedicated "Ralph Loop (Stateless Runner)" section.
- Added quick command for loop execution.

3. Synced product/process contracts.
- Files: `running/app_spec.md`, `running/codex-progress.md`
- Added context isolation constraint: no resume/fork memory reuse.
- Added runner entrypoint and success metric for zero context contamination.

4. Synced agent prompts with stateless constraint.
- Files:
  - `running/prompts/coding_prompt.md`
  - `running/prompts/evaluator_prompt.md`
  - `running/prompts/initializer_prompt.md`
- Coding prompt now requires stateless behavior.
- Evaluator checks fresh-session evidence.
- Initializer verifies loop runner exists and uses `--ephemeral`.

5. Added ignore rule for runtime session artifacts.
- File: `.gitignore`
- Added: `/running/sessions/`

## Validation

1. `powershell -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -DryRun` passed.
2. Verified docs and prompts contain `stateless` / `codex exec --ephemeral` rules.
3. Verified loop runner writes per-iteration prompt artifacts and does not resume prior sessions.

## Notes

- This update changes harness/process files only.
- No application runtime module boundary changes were made.