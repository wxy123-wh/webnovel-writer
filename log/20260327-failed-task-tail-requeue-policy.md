# 2026-03-27 failed-task tail requeue policy

## Trigger

User requested that failed tasks should not be dropped or immediately block the whole run:
- summarize failure,
- put task back to the bottom of task list,
- solve these deferred failures at the end.

## Key changes

1. Enforced auto requeue-to-tail in loop runner.
- File: `running/ralph-loop.ps1`
- Added failure policy (default enabled):
  - if task is not passed and no human handoff is required,
  - auto write failure summary,
  - set `status=pending`, `defer_to_tail=true`, `passes=false`,
  - increment `failure_count`, update `last_failure_summary`, `requeued_at`,
  - append `[AUTO-REQUEUE ...]` note,
  - move task object to end of `features` array.
- Added switch: `-DisableAutoRequeueOnFail` to opt out.

2. Added runtime fields for deferred-failure tracking.
- File: `running/feature_list.json`
- Added mutable fields:
  - `defer_to_tail`
  - `failure_count`
  - `last_failure_summary`
  - `requeued_at`
- Backfilled default values for all tasks.

3. Synced workflow and prompts.
- Files:
  - `running/workflow.md`
  - `running/app_spec.md`
  - `running/codex-progress.md`
  - `running/prompts/coding_prompt.md`
  - `running/prompts/evaluator_prompt.md`
- Policy now distinguishes:
  - actionable test failure => summarize + requeue tail,
  - human-dependent blocker => `status=blocked` + human handoff.

## Validation

1. `python -m json.tool running/feature_list.json` passed.
2. PowerShell parse check for `running/ralph-loop.ps1` passed.
3. `powershell -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -DryRun` passed.
4. Verified all task entries contain new deferred-failure runtime fields.

## Notes

- Loop remains stateless (`codex exec --ephemeral`) per iteration.
- Human-assist blockers still stop loop by default.