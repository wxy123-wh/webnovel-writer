> generated_by: nexus-mapper v2
> verified_at: 2026-03-27
> provenance: Mixed. Router-to-service links are code-verified from imports and include_router wiring; some cross-system dependencies are inferred from endpoint contracts and docs.

# Dependencies

## System Graph

```mermaid
graph TD
  CLI["CLI Gateway\nwebnovel.py"] --> DM["Data Modules\nstate/index/rag/context"]
  DM --> RAG["RAG Adapter\nrag_adapter.py"]
  DM --> IDX["Index Manager\nindex_manager.py"]

  Server["dashboard/server.py"] --> App["dashboard/app.py"]
  App --> RuntimeRouter["runtime_router"]
  App --> SkillsRouter["skills_router"]
  App --> SettingsRouter["settings_files_router + settings_dictionary_router"]
  App --> OutlineRouter["outlines_router"]
  App --> EditRouter["edit_assist_router"]
  App --> CodexRouter["codex_bridge_router"]

  RuntimeRouter --> RuntimeSvc["runtime/service.py"]
  SkillsRouter --> SkillsSvc["skills/manager.py"]
  SettingsRouter --> DictSvc["dictionary/service.py"]
  OutlineRouter --> SplitSvc["split/service.py + split/resplit.py"]
  EditRouter --> EditSvc["edit_assist/service.py"]

  Frontend["React Frontend\npages/*.jsx"] --> App
  Frontend --> CodexRouter

  DictSvc --> ProjectFiles["Project files\n设定集 / 大纲 / .webnovel/*"]
  SplitSvc --> ProjectFiles
  EditSvc --> ProjectFiles
  RAG --> VectorDB[".webnovel/vectors.db"]
  IDX --> IndexDB[".webnovel/index.db"]
```

## Key Flow: Outline Split Apply

```mermaid
sequenceDiagram
  participant UI as OutlineWorkspacePage
  participant API as /api/outlines/split/apply
  participant SVC as SplitService
  participant FS as .webnovel/outlines/*

  UI->>API: POST split/apply (selection, project_root)
  API->>SVC: apply_split(request)
  SVC->>SVC: validate selection + idempotency
  SVC->>FS: write split-map.json and detailed-segments.jsonl
  SVC-->>API: split record + segment count
  API-->>UI: 200 OK payload
```

## Key Flow: RAG Consistency Check

```mermaid
sequenceDiagram
  participant CLI as webnovel consistency-check
  participant Cmd as webnovel.py
  participant IDX as index.db snapshot
  participant RAG as rag_adapter metadata

  CLI->>Cmd: consistency-check --project-root
  Cmd->>IDX: read max chapter + sync meta
  Cmd->>RAG: read schema/version + max chapter
  Cmd->>Cmd: compare state/index/rag watermarks
  Cmd-->>CLI: status ok or drift + suggestions
```

## Dependency Risks Relevant to PRD

- Frontend write capability is spread across `SettingsPage`, `OutlineWorkspacePage`, `SkillsPage`, and Codex-launch actions in `FilesPage`; converting to pure display will touch multiple API adapters and page actions.
- RAG verification touches both command dispatch (`webnovel.py`) and retrieval implementation (`rag_adapter.py`) plus tests in `scripts/data_modules/tests/test_rag_adapter.py`.
- Workspace safety enforcement appears in both dashboard service layer and CLI pointer resolution; standardizing Codex flow should define one authoritative resolution strategy.
