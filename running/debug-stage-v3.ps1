# debug-stage-v3.ps1 — 用 & 操作符直接在当前进程运行，看到所有输出
$codexBin     = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$worktreePath = 'D:\code\webnovel-writer\.worktrees\sisyphus\t009-20260328-223459-01-T009'
$repoRoot     = 'D:\code\webnovel-writer'
$sessionDir   = 'D:\code\webnovel-writer\running\sessions\20260328-223459-01-T009'
$promptFile   = Join-Path $sessionDir 'coding-prompt.md'
$lastMsgFile  = Join-Path $sessionDir 'coding-last-message.txt'
$transcriptFile = Join-Path $sessionDir 'coding-output.log'
$scriptDir    = 'D:\code\webnovel-writer\running'

$env:OPENAI_API_KEY  = 'sk-db4420e5de254a1467cc5cfb1a845e13'
$env:OPENAI_BASE_URL = 'https://api.asxs.top/v1'

Write-Host "PromptFile: $promptFile  exists=$(Test-Path $promptFile)" -ForegroundColor Cyan
Write-Host "Worktree:   $worktreePath  exists=$(Test-Path $worktreePath)" -ForegroundColor Cyan
Write-Host ''

# 直接在当前 PowerShell 进程中 dot-source 运行，所有错误直接可见
# 用 try/catch 捕获异常
try {
    & 'd:\code\webnovel-writer\running\run-codex-stage.ps1' `
        -RepoRoot $repoRoot `
        -WorktreePath $worktreePath `
        -CodexBin $codexBin `
        -CodexSandbox 'danger-full-access' `
        -PromptPath $promptFile `
        -OutputLastMessagePath $lastMsgFile `
        -TranscriptPath $transcriptFile `
        -ApiBaseUrl 'https://api.asxs.top/v1' `
        -ApiKey 'sk-db4420e5de254a1467cc5cfb1a845e13' `
        -DisableIsolatedCodexHome
    Write-Host "run-codex-stage exit: $LASTEXITCODE" -ForegroundColor Green
} catch {
    Write-Host "EXCEPTION: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "At: $($_.InvocationInfo.PositionMessage)" -ForegroundColor Red
}

Write-Host ''
Write-Host '=== Transcript ===' -ForegroundColor Cyan
if (Test-Path $transcriptFile) {
    $c = Get-Content $transcriptFile -Raw
    if ([string]::IsNullOrWhiteSpace($c)) { Write-Host '(empty)' -ForegroundColor Yellow }
    else { $c | Select-Object -First 30 }
} else {
    Write-Host '(not created)' -ForegroundColor Red
}
