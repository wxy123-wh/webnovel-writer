# 2026-03-27 harness workflow upgraded for task claim + Playwright gate

## Trigger

User requested the harness workflow to support:
- explicit task list claiming and completion marking,
- select task -> develop -> verify,
- frontend verification with build then Playwright,
- progress/task updates and commit discipline,
- blocked branch with human assistance request.

## Key changes

1. Added explicit task lifecycle and runtime field contract.
- File: `running/workflow.md`
- Added states: `pending -> claimed -> in_progress -> done|blocked`.
- Added required runtime fields and transition rules.
- Added claim/start/complete update sequence.

2. Added mandatory frontend verification gate.
- Files: `running/workflow.md`, `running/prompts/coding_prompt.md`, `running/prompts/evaluator_prompt.md`, `running/feature_list.json`
- Enforced `npm run build` + Playwright checklist evidence for UI-affecting tasks.
- Updated D007-D010 verification type to `build_and_playwright_manual_e2e`.

3. Added blocked/human-assistance branch.
- Files: `running/workflow.md`, `running/prompts/coding_prompt.md`, `running/prompts/evaluator_prompt.md`, `running/codex-progress.md`
- Defined trigger conditions for human help.
- Added required blocker fields and explicit handoff requirements.

4. Updated progress and spec contracts.
- Files: `running/codex-progress.md`, `running/app_spec.md`, `running/prompts/initializer_prompt.md`
- Progress table now includes final task status and human-assist visibility.
- App spec now includes status-based DoD and frontend gate requirement.

## Validation

1. `python -m json.tool running/feature_list.json` passed.
2. Verified all 15 tasks have lifecycle fields with `status=pending` by default.
3. Verified D007-D010 include build + Playwright verification contract.

## Notes

- This update changes harness/process artifacts only (`running/*`, root `log/*`), not runtime code boundaries.
- `.nexus-map` refresh not required for this documentation-only workflow upgrade.