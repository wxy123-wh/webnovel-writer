# Commercialization Rollout Implementation Plan

> **For agentic workers:** This file is retained as the executed rollout record for the commercialization stream.

**Goal:** Turn the current repository into a commercially defensible product by first reconciling product claims with reality, then adding the minimum trust, security, and packaging gates required before charging users.

**Architecture:** Keep the product surface intentionally narrow: a local or trusted-network Codex writing companion with CLI-driven authoring and a read-only dashboard. Commercialization is implemented as truthful, supportable self-hosted delivery rather than a hosted SaaS expansion.

**Tech Stack:** Python, FastAPI, React, SQLite, Docker, Markdown docs, CLI tooling

**Execution Status:** Completed for the selected commercialization path: GPL v3 self-hosted single-tenant deployment + paid support / implementation services.

---

## Scope and commercialization stance

This file is now retained as an execution record. The selected commercialization path is GPL v3 self-hosted single-tenant deployment + paid support / implementation services. The rollout closed these binary gates:

1. Public docs, CLI docs, and shipped code must describe the same supported product surface.
2. Core quality claims around RAG verification and incremental indexing must be based on executable evidence, not simulated constants.
3. A supported secure deployment model must exist for any non-local paid use.
4. The commercialization model must be explicitly compatible with the repository's licensing posture.

## File map

### Product truth and scope
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/CLI_REFERENCE.md`
- Modify: `docs/操作手册.md`
- Modify: `webnovel-writer/dashboard/app.py`

### Quality proof
- Modify: `webnovel-writer/scripts/data_modules/rag_verifier.py`
- Modify: `webnovel-writer/scripts/data_modules/incremental_indexer.py`
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Test: `webnovel-writer/scripts/data_modules/tests/`

### Secure deployment and paid boundary
- Modify: `README.md`
- Modify: `webnovel-writer/dashboard/server.py`
- Modify: deployment docs/configs under repo root as needed
- Test: dashboard startup and authenticated deployment path

### Commercial packaging
- Modify: `LICENSE`
- Modify: `README.md`
- Modify: packaging/distribution docs

---

## Chunk 1: Phase 0 — Commercial truth baseline

**Outcome:** The repository no longer over-claims capabilities. Supported behavior is explicit, narrow, and internally consistent.

### Task 1: Reconcile the shipped dashboard surface

**Files:**
- Modify: `webnovel-writer/dashboard/app.py`
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`

- [x] **Step 1: Write a consistency checklist**

Pass only if all are true:
- `app.py` imports only routers that are actually exported and mounted.
- Docs do not claim writable dashboard flows are part of the current mainline product.
- Docs do not claim current support for more routes than the runtime actually exposes.

- [x] **Step 2: Remove stale router imports from `webnovel-writer/dashboard/app.py`**

Target state:
- Import only `runtime_router` from `dashboard.routers`.
- Keep route mounting aligned with imports.

- [x] **Step 3: Update `README.md` to match current support**

Required changes:
- Replace any “M1/M2/M3 已全部完成” phrasing with explicit current-state wording.
- State that dashboard is read-only and current commercial scope is local/trusted-network usage only.
- State that authentication is not built in and commercial remote use is not yet supported.

- [x] **Step 4: Update `docs/ARCHITECTURE.md` to stop claiming validated watcher/RAG completion unless verified**

Required changes:
- Mark file watching and RAG quality verification according to real code state.
- Make clear that only the read-only dashboard runtime is mounted today.

- [x] **Step 5: Verify the Python module still imports cleanly**

Run: `python -c "import sys; sys.path.insert(0, r'D:\code\webnovel-writer\webnovel-writer'); import dashboard.app; print('ok')"`
Expected: prints `ok`

### Task 2: Reconcile operator docs with actual CLI/runtime

**Files:**
- Modify: `docs/操作手册.md`
- Modify: `docs/CLI_REFERENCE.md`
- Modify: `README.md`

- [x] **Step 1: Remove stale write-flow SOP from `docs/操作手册.md`**

Required changes:
- Delete or rewrite settings dictionary, split/resplit, and edit-assist POST flow instructions.
- Replace with read-only dashboard usage and CLI/runtime status workflow.

- [x] **Step 2: Update `docs/CLI_REFERENCE.md` to reflect current code truthfully**

Required changes:
- Ensure command set matches `codex_cli.py` exactly.
- Mark `rag verify` output example as illustrative if metrics are not yet measured.

- [x] **Step 3: Manual QA doc sanity check**

Pass only if a reader can answer these without contradiction:
- What can I do from the dashboard?
- What can I do from the CLI?
- Which commercial-use restrictions still exist?

---

## Chunk 2: Phase 1 — Evidence-based quality gates

**Outcome:** The product's core anti-forgetting / anti-hallucination claim is backed by executable evidence.

### Task 3: Replace simulated RAG verification

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/rag_verifier.py`
- Test: `webnovel-writer/scripts/data_modules/tests/test_rag_verifier*.py`
- Modify: docs that currently claim validated metrics

- [x] **Step 1: Add failing tests for real correctness/performance sourcing**
- [x] **Step 2: Implement verifier logic that reads fixtures/benchmarks instead of constants**
- [x] **Step 3: Run tests and verify pass**
- [x] **Step 4: Run CLI manually and capture real output**

### Task 4: Align indexing claims with implementation

**Files:**
- Modify: `webnovel-writer/scripts/data_modules/incremental_indexer.py`
- Test: `webnovel-writer/scripts/data_modules/tests/`
- Modify: `README.md`, `docs/ARCHITECTURE.md`

- [x] **Step 1: Decide one truthful state**
Choose one and implement/document it consistently:
- true watcher-backed indexing, or
- scan-based indexing with no watcher claim.

- [x] **Step 2: Implement and verify the chosen state**
- [x] **Step 3: Run manual QA on a sample project and show index artifact changes**

---

## Chunk 3: Phase 2 — Minimum safe paid deployment

**Outcome:** A paid deployment path has a real security boundary and an operator playbook.

### Task 5: Define the only supported paid deployment mode

**Files:**
- Modify: `README.md`
- Modify: deployment docs/config

- [x] **Step 1: Freeze one supported mode**
Recommended first mode: single-tenant local or trusted-network deployment only.

- [x] **Step 2: Document unsupported modes explicitly**
Examples:
- public unauthenticated deployment
- multi-tenant hosted SaaS

### Task 6: Productize access control for non-local deployment (if pursued)

**Files:**
- Modify: `webnovel-writer/dashboard/server.py`
- Modify: deployment docs/config

- [x] **Step 1: Add failing tests for required auth boundary**
- [x] **Step 2: Implement the minimum supported auth path**
- [x] **Step 3: Manually verify unauthorized access is blocked**

---

## Chunk 4: Phase 3 — Commercial packaging decision

**Outcome:** The thing being sold is legally and operationally defined.

### Task 7: Resolve commercialization model

**Files:**
- Modify: `LICENSE`
- Modify: `README.md`
- Modify: packaging docs

- [x] **Step 1: Choose the commercial shape**
One of:
- paid support / services around GPL product
- hosted offering with clearly scoped source obligations
- license change before proprietary distribution

Current choice executed in repo docs: **paid support / services around GPL product**.

- [x] **Step 2: Document the chosen model in plain language**
- [x] **Step 3: Ensure sales claims match the actual supported product surface**

Completion note:
- The repo now documents a GPL v3 self-hosted single-tenant deployment model with paid support / implementation services.
- Public multi-tenant hosted SaaS is explicitly out of current scope.
- Commercial acceptance is tied to project-specific `rag verify` benchmark evidence, not only the repo CI fixture.

---

## Immediate execution recommendation

Start with **Chunk 1 / Task 1 + Task 2** as one implementation slice.

**Why this first:**
1. It is the highest-leverage trust fix.
2. It reduces support and sales ambiguity immediately.
3. It creates a clean baseline for the later hard work: real verifier evidence, secure deployment, and licensing decisions.

**Binary completion for the first slice:**
- `dashboard.app` imports cleanly.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/CLI_REFERENCE.md`, and `docs/操作手册.md` no longer claim deleted write flows or validated metrics that are still simulated.
- Manual QA confirms the docs describe one coherent supported product.
