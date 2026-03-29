> generated_by: nexus-mapper v2
> verified_at: 2026-03-27
> provenance: AST-backed for Python and JavaScript modules under webnovel-writer/; service dependency links are inferred from direct router and import inspection where query_graph import edges were sparse.

# Systems

## Scope
This map focuses on the active code under `webnovel-writer/` and excludes transient roots like `.worktrees/` and `__temp__/`.

## System Boundaries

| System | Responsibility | Code Path | Entrypoints |
| --- | --- | --- | --- |
| CLI Gateway | Unified command dispatch and runtime checks for novel workflows. | `webnovel-writer/scripts/data_modules/webnovel.py` | `python -X utf8 webnovel-writer/scripts/webnovel.py <tool> ...` |
| Dashboard App | FastAPI composition layer for read APIs and router mounting. | `webnovel-writer/dashboard/app.py` | `create_app(...)` and `/api/*` handlers |
| Runtime Management | Workspace and pointer profile plus migration execution. | `webnovel-writer/dashboard/services/runtime/service.py` | `/api/runtime/profile`, `/api/runtime/migrate` |
| Skills Management | Skill registry CRUD, enable or disable operations, audit log output. | `webnovel-writer/dashboard/services/skills/manager.py` | `/api/skills/*` |
| Settings Dictionary | Settings file read or write, dictionary extraction, conflict resolution. | `webnovel-writer/dashboard/services/dictionary/service.py` | `/api/settings/files/*`, `/api/settings/dictionary/*` |
| Outline Split | Outline split, resplit, rollback planning, order validation. | `webnovel-writer/dashboard/services/split/service.py`, `.../split/resplit.py` | `/api/outlines/*` |
| Edit Assist | Text rewrite preview or apply with selection-version guard rails. | `webnovel-writer/dashboard/services/edit_assist/service.py` | `/api/edit-assist/*` |
| Codex Bridge | Dashboard-driven local Codex dialog launch with prompt artifact files. | `webnovel-writer/dashboard/routers/codex_bridge.py` | `/api/codex/*` |
| RAG Adapter | Vector DB schema management, indexing, retrieval, and consistency metadata. | `webnovel-writer/scripts/data_modules/rag_adapter.py` | `webnovel rag ...`, consistency checks |

## Frontend Surface

Main pages under `webnovel-writer/dashboard/frontend/src/pages/`:
- `DashboardPage.jsx`, `EntitiesPage.jsx`, `GraphPage.jsx`, `ChaptersPage.jsx`, `ReadingPowerPage.jsx` (read-heavy)
- `SkillsPage.jsx`, `SettingsPage.jsx`, `OutlineWorkspacePage.jsx`, `FilesPage.jsx` (currently include write or Codex-trigger operations)

## Evidence Gaps

- `query_graph --hub-analysis` shows sparse internal import edges for this repo layout, so service-to-service links were validated by direct router imports and endpoint code, not only graph metrics.
- Git hotspots in the last 90 days are dominated by legacy `.claude/*` paths, so hotspot risk for current `webnovel-writer/*` modules is weakly evidenced from git stats alone.
