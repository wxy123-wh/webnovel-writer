# run-with-live-output.ps1
# 直接在前台运行 dispatcher（MaxDispatches=1 只跑第一个任务）
# 同时在新 wt 窗格里实时 tail codex 的输出

param(
    [string]$ApiKey = "sk-db4420e5de254a1467cc5cfb1a845e13",
    [string]$ApiBaseUrl = "https://api.asxs.top/v1"
)

$repoRoot  = 'd:\code\webnovel-writer'
$scriptDir = 'd:\code\webnovel-writer\running'
$sessDir   = "$scriptDir\sessions"
$ps5 = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"

function B64([string]$cmd) {
    [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($cmd))
}

# 窗格命令：等 session 出现后实时 tail coding-output.log
$tailCmd = @"
Set-Location '$repoRoot'
Write-Host '=== 等待 Agent 输出 ===' -ForegroundColor Cyan
Write-Host '监听 sessions 目录...' -ForegroundColor Gray
Write-Host ''
`$sd = '$sessDir'
while (`$true) {
    `$latest = Get-ChildItem `$sd -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (`$null -ne `$latest) {
        `$logFile = Join-Path `$latest.FullName 'coding-output.log'
        if (Test-Path `$logFile) {
            Write-Host ('=== ' + `$latest.Name + ' ===') -ForegroundColor Green
            Write-Host ('Log: ' + `$logFile) -ForegroundColor DarkGray
            Write-Host ''
            Get-Content `$logFile -Tail 0 -Wait
        }
    }
    Start-Sleep -Seconds 1
}
"@
$tailPane = B64 $tailCmd

# 先开 wt 分割窗格实时显示输出
Write-Host '==> 开启实时输出窗格...' -ForegroundColor Cyan
Start-Process 'wt.exe' -ArgumentList @(
    '--window', '0',
    'split-pane', '-V', '--size', '0.55',
    '--title', 'Agent-Live-Output',
    '--', $ps5, '-NoProfile', '-EncodedCommand', $tailPane
)
Start-Sleep -Seconds 2

# 前台直接运行 dispatcher，只跑 1 个任务
Write-Host '==> 启动 Dispatcher (MaxDispatches=1)...' -ForegroundColor Cyan
Write-Host ''

$dispArgs = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', "$scriptDir\sisyphus-dispatcher.ps1",
    '-RepoRoot', $repoRoot,
    '-MaxDispatches', '1',
    '-MaxParallel', '1',
    '-ApiKey', $ApiKey,
    '-ApiBaseUrl', $ApiBaseUrl,
    '-CodexBin', 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe',
    '-CodexSandbox', 'danger-full-access',
    '-DisableIsolatedCodexHome',
    '-ContinueWhenBlocked'
)

& $ps5 @dispArgs

Write-Host ''
Write-Host '==> Dispatcher 完成。' -ForegroundColor Green
Write-Host '右侧窗格显示的是 Agent 的实时输出。' -ForegroundColor Yellow
