# 2026-03-27 running harness rewritten for development workflow

## Trigger

User requested a full rewrite of `running/` from writing-oriented flow into a software development harness, aligned with:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

## What changed

1. Rewrote workflow contract to long-running development mode.
- File: `running/workflow.md`
- Added explicit topology: Initializer Agent + Coding Agent + Evaluator Agent.
- Added Session 0 vs Session N loops, deterministic gates, failure recovery, release gates.
- Added structural-query step with `query_graph.py --impact` before boundary-risk changes.

2. Rewrote app spec around development harness outcomes.
- File: `running/app_spec.md`
- Goal now: durable coding harness for multi-session implementation.
- Added measurable success metrics and strict Definition of Done.

3. Replaced feature backlog with development-harness + product backlog hybrid.
- File: `running/feature_list.json`
- Version bumped to 3.
- Added immutable/mutable field policy with `last_verified_at` as runtime field.
- Replaced old F001-F007 with D001-D015 covering:
  - harness bootstrap/process/commit discipline/regression gate,
  - product-facing refactor targets and verification paths.

4. Rewrote progress file for evaluator-driven long-run sessions.
- File: `running/codex-progress.md`
- Session journal now records item id, regression checks, verification, commits, result.
- Added open risks and next actionable plan.

5. Upgraded init script from bootstrap-only to harness launcher.
- File: `running/init.ps1`
- Preserved install/bind/smoke behavior.
- Added optional dashboard startup switches:
  - `-StartDashboard`
  - `-DashboardHost`
  - `-DashboardPort`
  - `-NoBrowser`
- Fixed PowerShell interpolation issue for host:port output.

6. Added prompt templates for role-separated long-running execution.
- Files:
  - `running/prompts/initializer_prompt.md`
  - `running/prompts/coding_prompt.md`
  - `running/prompts/evaluator_prompt.md`

## Validation performed

1. `query_graph.py --summary` (nexus-query) executed before rewrite to re-validate repository boundaries.
2. `python -m json.tool running/feature_list.json` passed.
3. `running/init.ps1 -SkipInstall -RunSmoke` passed after script fix.
4. `running/prompts/` file presence verified.

## Notes

- `running/log/` remained non-writable in this environment; per current harness contract, root `log/` is mandatory and has been updated.
- This rewrite does not change application runtime boundaries under `webnovel-writer/`; `.nexus-map` refresh is not required for this documentation/harness-only update.
