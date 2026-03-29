> generated_by: nexus-mapper v2
> verified_at: 2026-03-27
> provenance: Derived from docs + code scan of dashboard services and data_modules; uncertain relations are marked explicitly.

# Domains

## Domain: Workspace Routing

- Core objects: `workspace_id`, `project_root`, workspace pointer files.
- Main rules: requests must stay inside resolved project root; mismatch returns forbidden-style API errors.
- Implemented in: `dashboard/services/runtime/service.py`, shared checks in settings and edit-assist services.

## Domain: Settings Dictionary

- Core objects: setting entries, conflict candidates, resolution decisions.
- Main rules: extraction supports incremental mode; conflict resolution must be auditable and repeat-safe.
- Implemented in: `dashboard/services/dictionary/service.py` and `dashboard/routers/settings.py`.

## Domain: Outline Segmentation

- Core objects: total outline selection, split records, segment order, resplit rollback plan.
- Main rules: split and resplit are guarded by lock + idempotency key; order conflicts must block apply.
- Implemented in: `dashboard/services/split/service.py`, `dashboard/services/split/resplit.py`.

## Domain: Edit Assistance

- Core objects: proposal store, selection version, apply log entries.
- Main rules: apply requires proposal match and version match to prevent stale writes.
- Implemented in: `dashboard/services/edit_assist/service.py`.

## Domain: Skills Lifecycle

- Core objects: skill registry item, enabled status, audit line.
- Main rules: create, enable, disable, delete all produce auditable updates.
- Implemented in: `dashboard/services/skills/manager.py`.

## Domain: RAG Consistency

- Core objects: `vectors.db`, `index.db`, `rag_schema_meta`, max chapter watermark.
- Main rules: CLI consistency check reports drift between state/index/rag and provides remediation commands.
- Implemented in: `scripts/data_modules/rag_adapter.py`, `scripts/data_modules/webnovel.py`.

## Domain: Codex Session Bridge

- Core objects: split-dialog prompt payload, file-edit prompt payload, session launch parameters.
- Main rules: dashboard emits request payloads for local Codex session initiation.
- Implemented in: `dashboard/routers/codex_bridge.py` and frontend page actions.

## Evidence Gaps

- Unknown: strict session-only lifecycle guarantee for skills is not implemented yet; current code persists registry and audit under `.webnovel`.
- Evidence gap: clear single source of truth for chapter/outline fast-index artifacts is not yet defined in `docs/prd.md`.
