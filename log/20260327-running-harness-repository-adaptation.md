# 2026-03-27 running harness repository adaptation

## Summary
- Converted `running/` harness from generic template to repository-ready workflow for `webnovel-writer`.
- Added direct bootstrap, smoke, and session execution paths aligned with current `README.md` and `docs/prd-refined.md`.

## Key Changes

1. Rebuilt `running/init.ps1` to support this repository layout.
   - Script now resolves repository root as parent of `running/`.
   - Python dependencies install from:
     - `webnovel-writer/dashboard/requirements*.txt`
     - `webnovel-writer/scripts/requirements*.txt`
   - Frontend dependencies install from `webnovel-writer/dashboard/frontend/`.
   - Added project binding and preflight smoke support:
     - `-ProjectRoot`
     - auto-create workspace `.codex` context directory
     - `webnovel.py --help` + `preflight --format json`

2. Replaced `running/feature_list.json` sample features with PRD-frozen project features.
   - F001-F007 now match read-only UI conversion, write API deletion, codex command group, incremental index, session skill profiles, RAG verification, and regression gate.

3. Rewrote `running/codex-progress.md` for this repository.
   - Session restore now includes root `log/*.md` and `running/log/*.md`.
   - Added dependency check rule with `query_graph.py`.
   - Updated current status and next session plan to start from F001.

4. Replaced `running/app_spec.md` template with repository-specific app spec.
   - Captures goals, scope, constraints, entrypoints, DoD, and E2E checklist for this repo.

5. Added `running/workflow.md`.
   - Provides executable Session 0 bootstrap, per-session loop, release gate, and quick command reference.

## Validation Evidence

- `query_graph.py --summary` executed using `.nexus-map/raw/ast_nodes.json` for structure sanity before adaptation.
- `running/init.ps1 -SkipInstall -RunSmoke` passed.
- `running/init.ps1 -SkipInstall -RunSmoke -ProjectRoot <temp_project>` passed with `preflight.ok=true`.
- `running/init.ps1 -SkipFrontend -ProjectRoot <temp_project> -RunSmoke` passed.
- `running/init.ps1 -ProjectRoot <temp_project> -RunSmoke` passed after fixing frontend package-manager condition.

## Measured Runtime (local)

- Smoke only (`-SkipInstall -RunSmoke`): ~0.216s
- Smoke with project bind (`-SkipInstall -RunSmoke -ProjectRoot`): ~0.408s
- Full init without frontend (`-SkipFrontend -ProjectRoot -RunSmoke`): ~29.782s
- Full init with frontend (`-ProjectRoot -RunSmoke`): ~33.294s

## Notes

- During pip install, non-blocking warnings appeared for temporary directory cleanup and pip latest-version check.
- Temporary smoke project created for validation was removed after tests.

## Post-adjustment
- Updated app spec checklist to require root log/ update as mandatory and treat unning/log/ as optional, due environment write constraints observed during this session.
- Clarification: root `log/` update is mandatory for each modification session; `running/log/` is optional.
