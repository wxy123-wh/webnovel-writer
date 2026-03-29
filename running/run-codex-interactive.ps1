# run-codex-interactive.ps1
param(
    [string]$TaskId = 'T001'
)

$sessDir = 'D:\code\webnovel-writer\running\sessions'
$wtRoot  = 'D:\code\webnovel-writer\.worktrees\sisyphus'
$codex   = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'

$env:OPENAI_API_KEY  = 'sk-db4420e5de254a1467cc5cfb1a845e13'
$env:OPENAI_BASE_URL = 'https://api.asxs.top/v1'

# 找最新的 session
$sess = Get-ChildItem $sessDir -Directory |
    Where-Object { $_.Name -match $TaskId } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $sess) { Write-Host "No session for $TaskId" -ForegroundColor Red; exit 1 }

$prompt = Join-Path $sess.FullName 'coding-prompt.md'
if (-not (Test-Path $prompt)) { Write-Host "No prompt in $($sess.Name)" -ForegroundColor Red; exit 1 }

# 找对应的 worktree
$wt = Get-ChildItem $wtRoot -Directory |
    Where-Object { $_.Name -match ($TaskId.ToLower()) } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if ($null -eq $wt) { Write-Host "No worktree for $TaskId" -ForegroundColor Red; exit 1 }

Write-Host "Session:  $($sess.Name)" -ForegroundColor Cyan
Write-Host "Worktree: $($wt.Name)" -ForegroundColor Cyan
Write-Host ''
Write-Host '=== Codex starting ===' -ForegroundColor Green
Write-Host ''

# 用 cmd /c 通过 < 重定向而不是 pipe，这样 codex 能检测到 TTY，保留颜色和交互
$promptEsc = $prompt -replace '\\', '\\'
cmd /c "& `""$codex`"" exec --ephemeral -s danger-full-access -C `""$($wt.FullName)`"" - < `""$prompt`"""

Write-Host ''
Write-Host "=== Codex exited: $LASTEXITCODE ===" -ForegroundColor Yellow
Read-Host 'Press Enter to close'
