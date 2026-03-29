# open-dashboard.ps1  —  Windows Terminal 原生分屏监控面板
#
# 布局:
#   ┌─────────────────────┬───────────────┐
#   │                     │  Task Status  │
#   │    Dispatcher       │  (watch-status│
#   │    (前台直接输出)    ├───────────────┤
#   │                     │  Agent Panes  │
#   │                     │  (自动分屏)   │
#   └─────────────────────┴───────────────┘
#
# Agent 窗格监听器（open-agent-panes.ps1）检测到新 session 后，
# 自动用 wt split-pane 在右侧再开新窗格，直接 tail Agent 的原始输出。
#
# 用法:
#   powershell -ExecutionPolicy Bypass -File running\open-dashboard.ps1 -ApiKey "sk-xxx"
#   powershell -ExecutionPolicy Bypass -File running\open-dashboard.ps1 -NoDispatcher

param(
    [string]$ApiKey       = "",
    [switch]$NoDispatcher,
    [int]$MaxParallel     = 2,
    [int]$MaxDispatches   = 16,
    [string]$ApiBaseUrl   = "https://api.asxs.top/v1",
    [switch]$ContinueWhenBlocked
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir

# 优先用 PowerShell 5（与 codex 兼容性最好）
$ps5 = [System.IO.Path]::Combine($env:SystemRoot, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
if (-not (Test-Path $ps5)) { $ps5 = 'powershell' }

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = 'python' }

# 从环境变量补充 ApiKey
if ([string]::IsNullOrWhiteSpace($ApiKey) -and -not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $ApiKey = $env:OPENAI_API_KEY
}

# 确保 log 目录存在，清空旧 dispatcher 日志
$logDir  = Join-Path $scriptDir 'log'
$dispOut = Join-Path $logDir 'dispatcher-out.txt'
$dispErr = Join-Path $logDir 'dispatcher-err.txt'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
if (-not $NoDispatcher) {
    try { [System.IO.File]::WriteAllText($dispOut, "=== Dispatcher log $(Get-Date) ===`n") } catch { }
    try { [System.IO.File]::WriteAllText($dispErr, "") } catch { }
}

# sessions 目录：确保存在
$sessionsDir = Join-Path $scriptDir 'sessions'
if (-not (Test-Path $sessionsDir)) { New-Item -ItemType Directory -Path $sessionsDir -Force | Out-Null }

function B64([string]$cmd) {
    [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($cmd))
}

# ---------- 窗格 1: Dispatcher（前台直接运行，输出完全可见） ----------
# Dispatcher 在这个窗格中直接跑，stdout/stderr 同时写入 log 文件以供其他工具读取
if ($NoDispatcher -or [string]::IsNullOrWhiteSpace($ApiKey)) {
    $dispPane = B64 (
        "Set-Location '" + $repoRoot + "'; " +
        "Write-Host '=== Shell ready. Start dispatcher manually: ===' -ForegroundColor Yellow; " +
        "Write-Host 'powershell -File running\sisyphus-dispatcher.ps1 -ApiKey <key>' -ForegroundColor White"
    )
} else {
    # 直接前台运行 dispatcher，同时用 Tee-Object 复制输出到日志文件
    $dispBody  = "Set-Location '" + $repoRoot + "'; "
    $dispBody += "Write-Host '=== Sisyphus Dispatcher ===' -ForegroundColor Cyan; "
    $dispBody += "Write-Host 'MaxParallel=$MaxParallel  MaxDispatches=$MaxDispatches' -ForegroundColor Gray; "
    $dispBody += "Write-Host ''; "
    $dispBody += "& '$ps5' -NoProfile -ExecutionPolicy Bypass "
    $dispBody += " -File '" + $scriptDir + "\sisyphus-dispatcher.ps1'"
    $dispBody += " -RepoRoot '" + $repoRoot + "'"
    $dispBody += " -ApiKey '" + $ApiKey + "'"
    $dispBody += " -ApiBaseUrl '" + $ApiBaseUrl + "'"
    $dispBody += " -MaxDispatches $MaxDispatches -MaxParallel $MaxParallel"
    if ($ContinueWhenBlocked) { $dispBody += " -ContinueWhenBlocked" }
    # Tee 同时写日志
    $dispBody += " 2>&1 | Tee-Object -FilePath '" + $dispOut + "' -Append"
    $dispBody += "; Write-Host '' ; Write-Host 'Dispatcher finished.' -ForegroundColor Green"
    $dispBody += "; Read-Host 'Press Enter to close'"
    $dispPane = B64 $dispBody
}

# ---------- 窗格 2: Task Status（watch-status.py） ----------
$statusPane = B64 (
    "Set-Location '" + $repoRoot + "'; " +
    "Write-Host '=== Task Queue Status ===' -ForegroundColor Blue; " +
    "& '" + $python + "' '" + $scriptDir + "\watch-status.py' 2"
)

# ---------- 窗格 3: Agent Pane Monitor（open-agent-panes.ps1） ----------
# 这个脚本持续监听 sessions/，发现新 Agent 就用 wt split-pane 开新窗格
$agentMonPane = B64 (
    "Set-Location '" + $repoRoot + "'; " +
    "Write-Host '=== Agent Pane Monitor ===' -ForegroundColor Magenta; " +
    "Write-Host '新 Agent 启动时会自动在右侧开新窗格' -ForegroundColor Gray; " +
    "Write-Host ''; " +
    "& '" + $ps5 + "' -NoProfile -ExecutionPolicy Bypass " +
    "-File '" + $scriptDir + "\open-agent-panes.ps1' " +
    "-SessionsDir '" + $sessionsDir + "' " +
    "-PollInterval 2 -MaxPanes 6 -TailLines 50"
)

# ---------- 构建 wt 参数 ----------
#
# 布局目标:
#   Tab 1:
#     左(60%)  = Dispatcher
#     右上(40%) = Task Status
#     右下(40%) = Agent Pane Monitor
#
# wt 分屏顺序: new-tab(dispatcher) -> split-pane -V(右列) -> 聚焦右列 split-pane -H

$wtArgs = @(
    # 强制创建新独立窗口（避免命令作用在当前 wt 窗口上）
    '--window', 'new',
    # 新 tab，左侧跑 Dispatcher（占 60%）
    'new-tab',
    '--title', 'Dispatcher',
    '--', $ps5, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $dispPane,

    # 右侧纵向分割，上方跑 Task Status（占 40% 宽）
    ';', 'split-pane', '-V', '--size', '0.40', '--title', 'Task Status',
    '--', $ps5, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $statusPane,

    # 右列内再横向分割，下方跑 Agent Monitor
    ';', 'split-pane', '-H', '--size', '0.50', '--title', 'Agent Monitor',
    '--', $ps5, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $agentMonPane
)

# ---------- 启动 ----------
$keyInfo = if ($ApiKey) { "set (len=$($ApiKey.Length))" } else { 'NOT SET — dispatcher will not start' }
Write-Host '' -ForegroundColor Cyan
Write-Host '==> Launching Windows Terminal dashboard' -ForegroundColor Cyan
Write-Host ('    Layout : Dispatcher(L 60%) | Status(R-top) | AgentMonitor(R-bot)') -ForegroundColor Gray
Write-Host ('    ApiKey : ' + $keyInfo) -ForegroundColor Gray
Write-Host ('    MaxParallel=' + $MaxParallel + '  MaxDispatches=' + $MaxDispatches) -ForegroundColor Gray
Write-Host ('    Agent panes auto-split when sessions appear in: ' + $sessionsDir) -ForegroundColor Gray
Write-Host ''

if ($null -eq (Get-Command wt -ErrorAction SilentlyContinue)) {
    Write-Host '[ERROR] wt.exe not found. Install Windows Terminal from the Microsoft Store.' -ForegroundColor Red
    exit 1
}

Start-Process 'wt.exe' -ArgumentList $wtArgs
Write-Host 'Done. Windows Terminal launching...' -ForegroundColor Green
