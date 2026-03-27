# 2026-03-27 Codex Harness Templates Generated

## What changed
- Added `app_spec.md` template for product scope, constraints, and DoD.
- Added `feature_list.json` with immutable/mutable field rules and 3 starter features.
- Added `init.ps1` for environment bootstrap with Node/Python detection.
- Added `codex-progress.md` with session rules and journal format.

## Notes
- `query_graph.py --summary` could not run because `query_graph.py` is missing in repo root.
- `.nexus-map/INDEX.md` is not present in this repository.

## Next actions
1. Replace sample features in `feature_list.json` with real project feature definitions.
2. Run `init.ps1` to validate environment startup.
3. Start session-based implementation and update `passes` + progress log after each validated feature.
