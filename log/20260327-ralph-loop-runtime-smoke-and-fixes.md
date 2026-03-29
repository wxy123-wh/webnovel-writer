# 2026-03-27 ralph loop runtime smoke test and stability fix

## Trigger

User requested to test whether the new harness flow can run normally.

## What was tested

1. Structural validation
- `running/ralph-loop.ps1` PowerShell parse check.
- `running/feature_list.json` JSON validation.

2. Dry-run loop execution
- Command: `powershell -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1 -DryRun`
- Result: pass.
- Confirmed queue pickup (D001) and per-iteration session artifact generation.

3. Real loop execution (non-DryRun)
- Command: `powershell -ExecutionPolicy Bypass -File running/ralph-loop.ps1 -MaxIterations 1`
- Environment used isolated `CODEX_HOME` to avoid local broken global rules.
- Result: script runtime path works and exits gracefully when Codex invocation fails.

## Runtime issues found

1. External dependency failure
- `codex exec --ephemeral` repeatedly failed with stream disconnect to OpenAI responses endpoint.
- This is network/provider connectivity outside harness logic.

2. Script robustness issues found and fixed
- Native command stderr from `codex` could terminate script early as PowerShell error.
- Prompt template had backtick-escape side effects (`running/...` and `$TaskId` rendering).

## Fixes applied

1. Hardened external command execution in `running/ralph-loop.ps1`
- Wrapped `codex` invocation with temporary preference adjustments to avoid premature termination on native stderr.
- Script now captures output and handles non-zero exit code via controlled branch.

2. Fixed session prompt text rendering in `running/ralph-loop.ps1`
- Removed problematic backtick formatting in prompt body.
- Verified item id and paths render correctly in `codex-output.log`.

## Current conclusion

- Harness runner itself is executable and stable in both dry-run and real-run control flow.
- End-to-end task solving is currently blocked by upstream Codex API stream disconnections in this environment.