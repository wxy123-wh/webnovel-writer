# debug-codex-args.ps1 — 模拟 run-codex-stage.ps1 的参数构建，打印实际命令行
$codexBin     = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$CodexSandbox = 'workspace-write'
$WorktreePath = 'd:\code\webnovel-writer'
$OutputLastMessagePath = 'C:\Users\wxy\AppData\Local\Temp\test-last.txt'
$ApiBaseUrl   = ''
$Model        = ''
$DisableIsolatedCodexHome = $true

$argParts = [System.Collections.Generic.List[string]]::new()
$argParts.Add('exec')
$argParts.Add('--ephemeral')
$argParts.Add('-s'); $argParts.Add($CodexSandbox)
$argParts.Add('-C'); $argParts.Add($WorktreePath)
$argParts.Add('--output-last-message'); $argParts.Add($OutputLastMessagePath)

if ($DisableIsolatedCodexHome -and (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl))) {
    $argParts.Add('-c'); $argParts.Add('model_provider="codex"')
    $argParts.Add('-c'); $argParts.Add(("model_providers.codex.base_url=`"{0}`"" -f $ApiBaseUrl))
}
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $argParts.Add('-m'); $argParts.Add($Model)
}
$argParts.Add('-')

function EscapeOneArg([string]$a) {
    if ($a -eq '') { return '""' }
    if ($a -notmatch '[\s"\\]') { return $a }
    $sb = [System.Text.StringBuilder]::new()
    $null = $sb.Append('"')
    $bs = 0
    foreach ($ch in $a.ToCharArray()) {
        if ($ch -eq '\') { $bs++ }
        elseif ($ch -eq '"') {
            $null = $sb.Append('\' * ($bs * 2 + 1))
            $null = $sb.Append('"')
            $bs = 0
        } else {
            if ($bs -gt 0) { $null = $sb.Append('\' * $bs); $bs = 0 }
            $null = $sb.Append($ch)
        }
    }
    if ($bs -gt 0) { $null = $sb.Append('\' * ($bs * 2)) }
    $null = $sb.Append('"')
    return $sb.ToString()
}

$escapedArgs = ($argParts | ForEach-Object { EscapeOneArg $_ }) -join ' '

Write-Host '=== 实际传给 Process.Arguments 的字符串 ===' -ForegroundColor Cyan
Write-Host $escapedArgs -ForegroundColor White
Write-Host ''
Write-Host '=== 逐个参数 ===' -ForegroundColor Cyan
$argParts | ForEach-Object { Write-Host "  [$_]" }
Write-Host ''

# 现在直接用这个参数运行，看 exit code 和 stderr
Write-Host '=== 测试运行（只看 exit code 和 stderr）===' -ForegroundColor Cyan
$env:OPENAI_API_KEY = 'sk-db4420e5de254a1467cc5cfb1a845e13'
$env:OPENAI_BASE_URL = 'https://api.asxs.top/v1'

$psi = [System.Diagnostics.ProcessStartInfo]::new($codexBin, $escapedArgs)
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.WorkingDirectory = $WorktreePath

$proc = [System.Diagnostics.Process]::new()
$proc.StartInfo = $psi
$null = $proc.Start()

$proc.StandardInput.Write('Reply with exactly: HELLO')
$proc.StandardInput.Close()

# 读取前 20 行 stdout/stderr（不等完成）
$lines = 0
while (-not $proc.StandardOutput.EndOfStream -and $lines -lt 20) {
    $line = $proc.StandardOutput.ReadLine()
    Write-Host "STDOUT: $line"
    $lines++
}
$errLines = 0
while (-not $proc.StandardError.EndOfStream -and $errLines -lt 20) {
    $line = $proc.StandardError.ReadLine()
    Write-Host "STDERR: $line" -ForegroundColor Red
    $errLines++
}

if (-not $proc.HasExited) {
    Write-Host '(Process still running after reading initial output - killing)' -ForegroundColor Yellow
    $proc.Kill()
}
$proc.WaitForExit(3000)
Write-Host "Exit code: $($proc.ExitCode)" -ForegroundColor Yellow
