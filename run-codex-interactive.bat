@echo off
SET OPENAI_API_KEY=sk-db4420e5de254a1467cc5cfb1a845e13
SET OPENAI_BASE_URL=https://api.asxs.top/v1
type "D:\code\webnovel-writer\running\sessions\20260328-225151-01-T001\coding-prompt.md" | "D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe" exec --ephemeral -s danger-full-access -C "D:\code\webnovel-writer\.worktrees\sisyphus\t001-20260328-225151-01-T001" -
pause
