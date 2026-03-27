# 2026-03-27 loop runner api key injection support

## Trigger

User asked whether direct terminal execution should work and whether this can be fixed from script side.

## Changes

1. Added explicit API key injection parameter to loop runner.
- File: `running/ralph-loop.ps1`
- New parameter: `ApiKey`.
- Behavior:
  - if provided, runner sets `OPENAI_API_KEY` for each `codex exec` call,
  - restores previous environment value after each call,
  - logs only masked source message (never prints key value).

2. Updated workflow command examples.
- File: `running/workflow.md`
- Added example with `-ApiKey <YOUR_API_KEY>`.

## Validation

1. PowerShell parse check for `ralph-loop.ps1` passed.
2. Dry-run with `-ApiKey` passed and printed masked source message.
3. Verified script contains key set/restore branches for `OPENAI_API_KEY`.

## Notes

- This change removes dependence on globally preconfigured API key state.
- It does not override provider-side streaming compatibility issues.