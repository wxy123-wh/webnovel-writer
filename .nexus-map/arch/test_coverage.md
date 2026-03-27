> generated_by: nexus-mapper v2
> verified_at: 2026-03-27
> provenance: Static test-surface scan from repository paths; tests were not executed in this mapping run.

# Test Coverage

## Dashboard Test Surface

Located in `webnovel-writer/dashboard/tests/`:
- `test_dashboard_readonly_api.py`
- `test_runtime_api.py`
- `test_skills_api.py`
- `test_settings_dictionary_api.py`
- `test_outlines_split_api.py`
- `test_outlines_resplit_api.py`
- `test_edit_assist_api.py`
- `test_codex_bridge_api.py`
- `test_phase2_coverage.py`

Coverage implication: API-level behavior for runtime, skills, settings, outlines, edit-assist, and codex bridge has dedicated test files.

## Data Modules Test Surface

Located in `webnovel-writer/scripts/data_modules/tests/`:
- Workflow and CLI orchestration: `test_webnovel_unified_cli.py`, `test_workflow_manager.py`, `test_update_state_add_review_cli.py`
- State and index: `test_state_validator.py`, `test_state_manager_extra.py`, `test_sql_state_manager.py`, `test_migrate_state_to_sqlite.py`
- Context and entity: `test_context_manager.py`, `test_context_ranker.py`, `test_entity_linker_cli.py`
- RAG and graph: `test_rag_adapter.py`, `test_relationship_graph.py`
- Core infra and utilities: `test_config.py`, `test_api_client.py`, `test_archive_manager.py`, `test_project_locator.py`

Coverage implication: RAG and consistency-critical modules already have unit tests that can be reused for PRD item "test rag availability".

## Evidence Gaps

- No runtime evidence in this run for pass rate, flakiness, or p95 metrics because test execution is intentionally out-of-scope for mapper baseline.
- Some temporary inaccessible directories under tests (`dashboard/tests/t06-split-*`) were observed in filesystem scan and excluded from assertions.
- Frontend-only behavior (button visibility, disabled state, pure-read interactions) currently lacks explicit E2E test evidence in this static snapshot.

## Suggested Verification Focus for Upcoming PRD Changes

1. Add regression tests asserting write endpoints are hidden or blocked from frontend paths intended to be display-only.
2. Add/extend CLI tests for Codex standard flow that indexes chapter, outline, and detail-outline artifacts.
3. Promote `test_rag_adapter.py` scenarios into a single health-check command contract (connectivity + retrieval + consistency watermark).
