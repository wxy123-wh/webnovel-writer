# debug-stage-full.ps1 — 完整模拟 run-codex-stage.ps1 在 worktree 里的调用
$codexBin     = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$worktreePath = 'd:\code\webnovel-writer\.worktrees\sisyphus\t009-20260328-222442-01-T009'
$repoRoot     = 'd:\code\webnovel-writer'
$tmpDir       = $env:TEMP
$promptFile   = Join-Path $tmpDir 'stage-test-prompt.txt'
$lastMsgFile  = Join-Path $tmpDir 'stage-test-last.txt'
$transcriptFile = Join-Path $tmpDir 'stage-test-transcript.txt'

Set-Content $promptFile 'Reply with exactly one word: HELLO'
Set-Content $transcriptFile ''

$env:OPENAI_API_KEY  = 'sk-db4420e5de254a1467cc5cfb1a845e13'
$env:OPENAI_BASE_URL = 'https://api.asxs.top/v1'

Write-Host "WorktreePath exists: $(Test-Path $worktreePath)" -ForegroundColor Cyan

$ps5 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$scriptDir = 'd:\code\webnovel-writer\running'

$args2 = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', "$scriptDir\run-codex-stage.ps1",
    '-RepoRoot', $repoRoot,
    '-WorktreePath', $worktreePath,
    '-CodexBin', $codexBin,
    '-PromptPath', $promptFile,
    '-OutputLastMessagePath', $lastMsgFile,
    '-TranscriptPath', $transcriptFile,
    '-ApiBaseUrl', 'https://api.asxs.top/v1',
    '-ApiKey', 'sk-db4420e5de254a1467cc5cfb1a845e13',
    '-DisableIsolatedCodexHome'
)

Write-Host '==> 运行 run-codex-stage.ps1 (在 worktree 里)...' -ForegroundColor Cyan
$proc = Start-Process $ps5 -ArgumentList $args2 -PassThru -Wait -NoNewWindow
Write-Host "Exit code: $($proc.ExitCode)" -ForegroundColor Yellow
Write-Host ''
Write-Host '=== Transcript (first 30 lines) ===' -ForegroundColor Cyan
if (Test-Path $transcriptFile) {
    $content = Get-Content $transcriptFile
    if ($content) { $content | Select-Object -First 30 }
    else { Write-Host '(empty)' -ForegroundColor Red }
} else {
    Write-Host '(not created)' -ForegroundColor Red
}
Write-Host ''
Write-Host '=== Last Message ===' -ForegroundColor Cyan
if (Test-Path $lastMsgFile) { Get-Content $lastMsgFile }
else { Write-Host '(not created)' -ForegroundColor Red }
