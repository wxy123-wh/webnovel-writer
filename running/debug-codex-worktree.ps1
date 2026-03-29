# debug-codex-worktree.ps1 — 直接在 worktree 里调用 codex，看 stderr
$codexBin     = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$worktreePath = 'd:\code\webnovel-writer\.worktrees\sisyphus\t009-20260328-222442-01-T009'
$lastMsgFile  = Join-Path $env:TEMP 'wt-test-last.txt'

$env:OPENAI_API_KEY  = 'sk-db4420e5de254a1467cc5cfb1a845e13'
$env:OPENAI_BASE_URL = 'https://api.asxs.top/v1'

$escapedArgs = "exec --ephemeral -s danger-full-access -C `"$worktreePath`" --output-last-message `"$lastMsgFile`" -"

Write-Host "Args: $escapedArgs" -ForegroundColor Gray
Write-Host ''

$psi = [System.Diagnostics.ProcessStartInfo]::new($codexBin, $escapedArgs)
$psi.UseShellExecute        = $false
$psi.RedirectStandardInput  = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true
$psi.CreateNoWindow         = $true
$psi.WorkingDirectory       = $worktreePath

$proc = [System.Diagnostics.Process]::new()
$proc.StartInfo = $psi
$null = $proc.Start()

$proc.StandardInput.Write('Reply with exactly one word: HELLO')
$proc.StandardInput.Close()

# 读取前 30 行输出
Write-Host '=== STDOUT ===' -ForegroundColor Cyan
$outLines = 0
while (-not $proc.StandardOutput.EndOfStream -and $outLines -lt 10) {
    Write-Host ('OUT: ' + $proc.StandardOutput.ReadLine())
    $outLines++
}
Write-Host '=== STDERR ===' -ForegroundColor Yellow
$errLines = 0
while (-not $proc.StandardError.EndOfStream -and $errLines -lt 30) {
    Write-Host ('ERR: ' + $proc.StandardError.ReadLine()) -ForegroundColor DarkYellow
    $errLines++
}

if (-not $proc.HasExited) {
    Write-Host '(still running - killing after reading initial output)' -ForegroundColor Gray
    $proc.Kill()
}
$proc.WaitForExit(5000)
Write-Host "Exit code: $($proc.ExitCode)" -ForegroundColor Yellow
