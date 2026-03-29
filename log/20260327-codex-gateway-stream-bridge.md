# 2026-03-27 codex gateway stream compatibility bridge

## Trigger

User reported that Codex CLI streaming path to custom gateway in harness was incompatible and asked for a fix in `running/`.

## Root Cause Summary

1. `codex exec` to `https://api.asxs.top/v1/responses` repeatedly failed with `stream disconnected before completion: error sending request for url (...)`.
2. Direct Python `requests` to the same gateway succeeded (returned normal HTTP 401 for invalid key), so the issue was on Codex CLI transport compatibility for direct upstream connection, not general network reachability.
3. Existing runner also depended on non-deterministic Codex binary resolution and global Codex home/rules side effects.

## Changes

1. Added gateway compatibility bridge script.
- File: `running/codex-gateway-bridge.py`
- Behavior:
  - listens on local HTTP (`127.0.0.1:18888` by default),
  - forwards requests to configured HTTPS upstream,
  - streams upstream response bytes back to Codex caller,
  - preserves status code and key response headers.

2. Hardened runner executable and config pathing.
- File: `running/ralph-loop.ps1`
- Added/kept:
  - robust Codex executable auto-resolution (prefers modern CLI binaries),
  - CLI version diagnostics,
  - isolated `CODEX_HOME` by default.

3. Integrated bridge into runner lifecycle.
- File: `running/ralph-loop.ps1`
- New parameters:
  - `-DisableGatewayBridge`
  - `-GatewayBridgeScript`
  - `-GatewayBridgeHost`
  - `-GatewayBridgePort`
- Runtime behavior:
  - for HTTPS `ApiBaseUrl`, runner auto-starts local bridge,
  - in `-DryRun`, bridge launch is skipped and target bridge base URL is printed only,
  - rewrites effective `OPENAI_BASE_URL` to local bridge (`http://127.0.0.1:18888/v1` for default),
  - writes isolated Codex provider config to use `asxs` provider with `wire_api="responses"` and `supports_websockets=false`,
  - stops bridge process on exit via `finally` cleanup.

4. Updated workflow docs.
- File: `running/workflow.md`
- Added bridge script to durable artifacts and documented bridge default behavior plus disable command.

## Validation

1. Dry run passes with bridge enabled.
- Command: `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -DryRun`
- Result: script completed; bridge start/stop messages present.

2. Real run with bridge enabled returns explicit gateway status instead of stream transport failure.
- Command: `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -ApiKey sk-test`
- Result in session log: `unexpected status 401 Unauthorized ... url: http://127.0.0.1:18888/v1/responses`.

3. Real run with bridge disabled reproduces original incompatibility.
- Command: `powershell -NoProfile -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -ApiKey sk-test -DisableGatewayBridge`
- Result in session log: `stream disconnected before completion ... https://api.asxs.top/v1/responses`.

## Notes

- The bridge fixes harness compatibility path by avoiding direct Codex CLI -> gateway transport mismatch while preserving Responses API behavior.
- If gateway behavior changes, bridge can be disabled with `-DisableGatewayBridge` for A/B comparison.
