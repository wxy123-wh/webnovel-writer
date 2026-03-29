# debug-stage-v2.ps1 — 完整模拟 dispatcher 调用 run-codex-stage.ps1，捕获 stderr
$codexBin     = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$worktreePath = 'D:\code\webnovel-writer\.worktrees\sisyphus\t009-20260328-223459-01-T009'
$repoRoot     = 'D:\code\webnovel-writer'
$sessionDir   = 'D:\code\webnovel-writer\running\sessions\20260328-223459-01-T009'
$promptFile   = Join-Path $sessionDir 'coding-prompt.md'
$lastMsgFile  = Join-Path $sessionDir 'coding-last-message.txt'
$transcriptFile = Join-Path $sessionDir 'coding-output.log'
$scriptDir    = 'D:\code\webnovel-writer\running'

Write-Host "PromptFile exists:    $(Test-Path $promptFile)" -ForegroundColor Cyan
Write-Host "WorktreePath exists:  $(Test-Path $worktreePath)" -ForegroundColor Cyan
Write-Host "SessionDir exists:    $(Test-Path $sessionDir)" -ForegroundColor Cyan
Write-Host ''

$ps5 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

$stageArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', "$scriptDir\run-codex-stage.ps1",
    '-RepoRoot', $repoRoot,
    '-WorktreePath', $worktreePath,
    '-CodexBin', $codexBin,
    '-CodexSandbox', 'danger-full-access',
    '-PromptPath', $promptFile,
    '-OutputLastMessagePath', $lastMsgFile,
    '-TranscriptPath', $transcriptFile,
    '-ApiBaseUrl', 'https://api.asxs.top/v1',
    '-ApiKey', 'sk-db4420e5de254a1467cc5cfb1a845e13',
    '-DisableIsolatedCodexHome'
)

Write-Host '==> 运行 run-codex-stage.ps1 并捕获 stderr...' -ForegroundColor Cyan

# 用 Start-Process 捕获 stderr
$errFile = Join-Path $env:TEMP 'stage-stderr.txt'
$outFile = Join-Path $env:TEMP 'stage-stdout.txt'

$proc = Start-Process $ps5 -ArgumentList $stageArgs -PassThru -Wait `
    -RedirectStandardOutput $outFile `
    -RedirectStandardError $errFile

Write-Host "Exit code: $($proc.ExitCode)" -ForegroundColor Yellow
Write-Host ''
Write-Host '=== STDOUT ===' -ForegroundColor Cyan
if (Test-Path $outFile) { Get-Content $outFile } else { Write-Host '(none)' }
Write-Host ''
Write-Host '=== STDERR ===' -ForegroundColor Red
if (Test-Path $errFile) { Get-Content $errFile } else { Write-Host '(none)' }
Write-Host ''
Write-Host '=== Transcript ===' -ForegroundColor Cyan
if (Test-Path $transcriptFile) {
    $c = Get-Content $transcriptFile -Raw
    if ([string]::IsNullOrWhiteSpace($c)) { Write-Host '(empty)' -ForegroundColor Red }
    else { Write-Host $c }
} else {
    Write-Host '(not created)' -ForegroundColor Red
}
