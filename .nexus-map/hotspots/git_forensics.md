> generated_by: nexus-mapper v2
> verified_at: 2026-03-27
> provenance: Computed from `.nexus-map/raw/git_stats.json` (90-day window). Interpretation notes include explicit uncertainty where hotspots point to legacy paths.

# Git Forensics

## Window Summary

- analysis_period_days: 90
- total_commits: 140
- total_authors: 4

## Top Hotspots (raw)

1. `README.md` (48, high)
2. `.claude/skills/webnovel-write/SKILL.md` (25, high)
3. `.claude/scripts/data_modules/state_manager.py` (20, high)
4. `.claude/agents/context-agent.md` (19, high)
5. `.claude/scripts/data_modules/index_manager.py` (19, high)

## Risk Interpretation

- High churn is concentrated in legacy `.claude/*` paths, while current active code now lives mostly in `webnovel-writer/*`.
- This implies migration or path reshaping occurred; historical co-change signals only partially map to present module layout.
- For upcoming PRD work, hotspot confidence is medium-low for current runtime files and should be combined with direct code boundaries.

## Practical Impact for Current PRD

- Frontend pure-display refactor risk is better estimated from endpoint fan-out (pages + API adapters) than from git hotspot rank.
- Codex-flow standardization should prioritize current CLI + dashboard bridge entrypoints, even if those files are not top git hotspots.
- RAG validation risk remains meaningful due existing dedicated tests and consistency-check code, despite weak hotspot position.

## Evidence Gap

unknown: a one-to-one mapping from historical `.claude/scripts/data_modules/*` to current `webnovel-writer/scripts/data_modules/*` is not encoded in git stats output alone.
