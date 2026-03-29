# 2026-03-27 codex api base url switched to api.asxs.top

## Trigger

User requested to use `https://api.asxs.top/v1` as the Codex API base URL.

## Changes

1. Updated loop runner default API base URL.
- File: `running/ralph-loop.ps1`
- Added parameter:
  - `ApiBaseUrl` (default: `https://api.asxs.top/v1`)
- Runner now injects `OPENAI_BASE_URL` for each `codex exec` call and restores prior environment afterward.

2. Updated workflow quick command examples.
- File: `running/workflow.md`
- Added `-ApiBaseUrl https://api.asxs.top/v1` usage example.

## Validation

1. Script parse check passed.
2. `ralph-loop.ps1 -MaxIterations 1 -DryRun` shows configured API base URL in runner output.
3. Real run (`-MaxIterations 1`) confirms Codex requests target:
- `https://api.asxs.top/v1/responses`

## Current status

- Base URL switch is effective.
- Runtime still fails due stream disconnect on provider side in this environment.