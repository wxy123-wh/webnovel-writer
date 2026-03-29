# test-codex-direct.ps1 — 直接运行 run-codex-stage.ps1 看原始错误
$repoRoot  = 'd:\code\webnovel-writer'
$scriptDir = 'd:\code\webnovel-writer\running'
$tmpDir    = $env:TEMP
$promptFile   = Join-Path $tmpDir 'test-codex-prompt.txt'
$lastMsgFile  = Join-Path $tmpDir 'test-codex-last.txt'
$transcriptFile = Join-Path $tmpDir 'test-codex-transcript.txt'

# 简单的测试 prompt
Set-Content -Path $promptFile -Value 'Reply with exactly one word: HELLO'

# 清空 transcript
Set-Content -Path $transcriptFile -Value ''

$codexBin = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$ps5 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

Write-Host '==> Running run-codex-stage.ps1 directly...' -ForegroundColor Cyan
Write-Host "CodexBin: $codexBin" -ForegroundColor Gray
Write-Host ''

$args = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', "$scriptDir\run-codex-stage.ps1",
    '-RepoRoot', $repoRoot,
    '-WorktreePath', $repoRoot,
    '-CodexBin', $codexBin,
    '-PromptPath', $promptFile,
    '-OutputLastMessagePath', $lastMsgFile,
    '-TranscriptPath', $transcriptFile,
    '-ApiBaseUrl', 'https://api.asxs.top/v1',
    '-ApiKey', 'sk-db4420e5de254a1467cc5cfb1a845e13',
    '-DisableIsolatedCodexHome'
)

$proc = Start-Process $ps5 -ArgumentList $args -PassThru -Wait -NoNewWindow
Write-Host "Exit code: $($proc.ExitCode)" -ForegroundColor Yellow
Write-Host ''
Write-Host '=== Transcript ===' -ForegroundColor Cyan
if (Test-Path $transcriptFile) {
    $content = Get-Content $transcriptFile -Raw
    if ([string]::IsNullOrWhiteSpace($content)) {
        Write-Host '(transcript is empty)' -ForegroundColor Red
    } else {
        Write-Host $content
    }
} else {
    Write-Host '(transcript file not created)' -ForegroundColor Red
}
Write-Host ''
Write-Host '=== Last Message ===' -ForegroundColor Cyan
if (Test-Path $lastMsgFile) {
    Get-Content $lastMsgFile
} else {
    Write-Host '(last message file not created)' -ForegroundColor Red
}
