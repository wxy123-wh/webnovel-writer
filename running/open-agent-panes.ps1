# open-agent-panes.ps1
# 监听 sessions/ 目录，每当有新 Agent session 出现就自动用 wt split-pane
# 开一个原生终端窗格，在里面实时 tail 该 Agent 的 coding/evaluator 输出。
# 每个窗格标题 = task_id，颜色区分 coding(蓝) / evaluator(绿)。
#
# 用法（在已有 wt 窗口里的某个窗格中运行）:
#   powershell -ExecutionPolicy Bypass -File running\open-agent-panes.ps1
#
# 参数:
#   -PollInterval   检测新 session 的间隔（秒，默认 2）
#   -SessionsDir    sessions 目录（默认 running/sessions）
#   -MaxPanes       同时保持的最大 Agent 窗格数（默认 4）
#   -TailLines      启动时先回看多少行（默认 40）
#   -WtWindowId     目标 wt 窗口 ID（默认 0，即第一个窗口）

param(
    [int]$PollInterval  = 2,
    [string]$SessionsDir = "",
    [int]$MaxPanes      = 4,
    [int]$TailLines     = 40,
    [string]$WtWindowId = "0"
)

$ErrorActionPreference = "Continue"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($SessionsDir)) {
    $SessionsDir = Join-Path $scriptDir "sessions"
}
if (-not (Test-Path $SessionsDir)) {
    New-Item -ItemType Directory -Path $SessionsDir -Force | Out-Null
}

$ps = (Get-Command powershell -ErrorAction SilentlyContinue).Source
if (-not $ps) { $ps = "powershell" }

# 检查 wt 是否可用
$wtAvailable = $null -ne (Get-Command wt -ErrorAction SilentlyContinue)
if (-not $wtAvailable) {
    Write-Host "[WARN] wt.exe 不在 PATH，将回退到独立 PowerShell 窗口模式。" -ForegroundColor Yellow
}

# 已经为哪些 session 开过窗格
$opened = @{}
$paneCount = 0

function B64([string]$cmd) {
    [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($cmd))
}

# 修复：用 [hashtable] 返回，避免多返回值解构 bug
function Get-LogFile([string]$sessionPath) {
    foreach ($fn in @("coding-output.log", "evaluator-output.log", "codex-output.log")) {
        $fp = Join-Path $sessionPath $fn
        if (Test-Path $fp) {
            return @{ Path = $fp; Name = $fn }
        }
    }
    return $null
}

function Open-AgentPane([string]$sessionName, [string]$logFile, [string]$logFileName) {
    $taskId = ($sessionName -split "-")[-1]   # e.g. T003
    $stage  = if ($logFileName -like "eval*") { "EVAL" } else { "CODE" }
    $title  = "$stage $taskId"

    # 命令：先回看 TailLines 行，再持续 tail
    $tailCmd = @"
Write-Host '=== $title | $sessionName ===' -ForegroundColor Cyan
Write-Host '--- Log: $logFile ---' -ForegroundColor DarkGray
Get-Content '$logFile' -Tail $TailLines -Wait
"@
    $encoded = B64 $tailCmd

    if ($wtAvailable) {
        # 在指定 wt 窗口里水平分割新窗格
        # --window $WtWindowId 确保作用在正确的窗口上
        $wtArgs = @(
            "--window", $WtWindowId,
            "split-pane",
            "--title", $title,
            "-H",
            "--", $ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", $encoded
        )
        Start-Process "wt.exe" -ArgumentList $wtArgs -ErrorAction SilentlyContinue
    } else {
        # 回退：开独立 PowerShell 窗口
        Start-Process $ps -ArgumentList @(
            "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", $encoded
        ) -ErrorAction SilentlyContinue
    }

    Write-Host ("{0} Opened pane for {1} ({2})" -f (Get-Date -Format "[HH:mm:ss]"), $title, $logFile) -ForegroundColor Green
}

Write-Host "==> Agent Pane Monitor 启动" -ForegroundColor Cyan
Write-Host ("    sessions 目录: {0}" -f $SessionsDir) -ForegroundColor Gray
Write-Host ("    最大窗格数: {0}  |  轮询间隔: {1}s  |  wt 窗口: {2}" -f $MaxPanes, $PollInterval, $WtWindowId) -ForegroundColor Gray
Write-Host "    Ctrl+C 退出" -ForegroundColor Gray
Write-Host ""

while ($true) {
    if (-not (Test-Path $SessionsDir)) {
        Start-Sleep -Seconds $PollInterval
        continue
    }

    $sessions = Get-ChildItem -Path $SessionsDir -Directory |
        Sort-Object -Property LastWriteTime -Descending

    foreach ($s in $sessions) {
        if ($opened.ContainsKey($s.Name)) { continue }
        if ($paneCount -ge $MaxPanes) { break }

        # 修复：用 hashtable 接收返回值
        $logInfo = Get-LogFile -sessionPath $s.FullName
        if ($null -eq $logInfo) { continue }   # log 还没创建，等下一轮

        $opened[$s.Name] = $true
        $paneCount++
        Open-AgentPane -sessionName $s.Name -logFile $logInfo.Path -logFileName $logInfo.Name

        # 稍微错开，避免 wt 窗格同时创建冲突
        Start-Sleep -Milliseconds 400
    }

    Start-Sleep -Seconds $PollInterval
}
