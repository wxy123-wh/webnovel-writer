# App Spec (Development Harness for webnovel-writer)

## 1. Product Goal

Build a durable coding harness for long-running development sessions so this repository can be advanced safely across many independent agent runs.

## 2. Target Users

1. Maintainers implementing roadmap items over multiple sessions.
2. Contributors onboarding mid-stream who need reliable resume context.

## 3. Scope

In scope:
1. Session bootstrap and environment readiness.
2. Immutable backlog + mutable task lifecycle tracking.
3. One-item-per-session execution loop with fresh context isolation.
4. Evaluator gate for pass/fail decisions.
5. Root-level audit logs per modification session.

Out of scope:
1. Replacing CI as source of truth.
2. Replacing project product docs under `docs/`.
3. Auto-merging or auto-deploying code without review.

## 4. Constraints

1. Runtime: Python >= 3.10, Node.js >= 18, PowerShell.
2. Process: only one pending item is advanced per session by default.
3. Safety: failed checks block pass-state updates; actionable failures are deferred to queue tail, human-dependent failures move to blocked flow.
4. Mutability: `feature_list.json` body fields are immutable after Session 0.
5. Verification: frontend-impact items require `npm run build` and Playwright evidence.
6. Context isolation: each coding session must run in a new Codex execution (`codex exec --ephemeral`), never a resumed chat thread.
7. Queue discipline: failed tasks are summarized and deferred to queue tail for final-resolution passes unless human assistance is required.

## 5. Entrypoints

1. Harness bootstrap: `running/init.ps1`
2. Unified CLI: `webnovel-writer/scripts/webnovel.py`
3. Dashboard runtime: `python -X utf8 webnovel-writer/scripts/webnovel.py dashboard --project-root <PROJECT_ROOT>`
4. Stateless loop runner: `running/ralph-loop.ps1`

## 6. Success Metrics

1. Resume time <= 5 minutes from cold session to active coding.
2. Regression catch rate >= 90% for repeated completed-item checks.
3. Session completion quality: item marked pass only with verification evidence.
4. Mean time to recover from failed session <= 1 session.
5. Blocked sessions produce actionable human-assist requests in the same session.
6. Session contamination rate = 0 (no task run relies on prior chat memory).

## 7. Definition of Done

1. Every item in `running/feature_list.json` is `passes=true` and `status=done`.
2. Recent regression checks succeed.
3. Root `log/*.md` includes latest session summary.
4. Workflow docs match actual scripts and commands.
