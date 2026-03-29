> generated_by: nexus-mapper v2
> verified_at: 2026-03-27
> provenance: AST-backed scan for `webnovel-writer/` plus manual router/import validation for cross-system dependency lines where graph import edges were sparse.

# INDEX

## Project Snapshot

This repository centers on two active code roots:
- `webnovel-writer/scripts/data_modules/`: unified CLI and writing workflow engines (state/index/rag/context/etc.).
- `webnovel-writer/dashboard/`: FastAPI backend + React frontend pages for project visualization and operational tools.

Primary PRD direction currently under clarification (`docs/prd.md`):
1. Turn frontend into a pure display surface.
2. Standardize Codex workflow for quickly indexing chapter/outline/detail-outline context.
3. Build a skill-library strategy that is session-scoped.
4. Verify RAG availability and health.

## Key Entrypoints

- CLI entry: `webnovel-writer/scripts/data_modules/webnovel.py`
- Dashboard server entry: `webnovel-writer/dashboard/server.py`
- Dashboard app composition: `webnovel-writer/dashboard/app.py`
- Router package: `webnovel-writer/dashboard/routers/__init__.py`
- RAG core: `webnovel-writer/scripts/data_modules/rag_adapter.py`

## Current Architecture in One View

- `dashboard/app.py` mounts runtime/skills/settings/outlines/edit-assist/codex-bridge routers.
- Service modules under `dashboard/services/*` implement write-capable operations that the frontend currently triggers.
- CLI routes `rag`, `index`, `status`, `update-state`, and `consistency-check` through data modules.
- RAG consistency checks already exist in CLI (`state/index/rag` watermark comparison).

## Current Evidence Gaps

- `query_graph` reported sparse internal import graph for this repo layout; dependency boundaries were confirmed through direct code inspection of router imports and endpoint handlers.
- Git hotspot ranking mainly points to historical `.claude/*` files, so hotspot-based risk is only partially representative for current `webnovel-writer/*` paths.
- `docs/prd.md` is still high-level and does not yet define immutable acceptance criteria for read-only behavior, session-only skill loading, and RAG health contract.

## Immediate Task Routing

When work involves frontend read-only conversion or Codex workflow standardization, inspect these first:
- `.nexus-map/arch/systems.md`
- `.nexus-map/arch/dependencies.md`
- `.nexus-map/arch/test_coverage.md`
- `.nexus-map/concepts/domains.md`
- `.nexus-map/hotspots/git_forensics.md`

## [操作指南] 强制执行步骤

> 本节是对所有读取本文件的 AI 发出的硬性操作指令，不是建议。

### 步骤1 — 必须先读完以下所有文件（顺序不限）

读完本文件后，在执行任何任务之前，必须依次 read 以下文件完整内容：

- `.nexus-map/arch/systems.md` — 系统边界与代码位置
- `.nexus-map/arch/dependencies.md` — 系统间依赖关系与 Mermaid 图
- `.nexus-map/arch/test_coverage.md` — 测试面与证据缺口
- `.nexus-map/hotspots/git_forensics.md` — Git 热点与耦合风险
- `.nexus-map/concepts/domains.md` — 核心领域概念

> 这些文件均为高密度摘要，总量通常 < 5000 tokens，是必要的上下文成本。
> 不得以"任务简单"或"只改一个文件"为由跳过。

### 步骤2 — 按任务类型追加操作（步骤1 完成后执行）

- 若任务涉及**接口修改、新增跨模块调用、删除/重命名公共函数**：
  → 必须运行 `query_graph.py --impact <目标文件>` 确认影响半径后再写代码。
- 若任务需要**判断某文件被谁引用**：
  → 运行 `query_graph.py --who-imports <模块名>`。
- 若仓库结构已发生重大变化（新增系统、重构模块边界）：
  → 任务完成后评估是否需要重新运行 nexus-mapper 更新知识库。
