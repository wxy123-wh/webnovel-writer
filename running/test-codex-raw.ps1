# test-codex-raw.ps1 — 直接调用 codex exec，不经过 run-codex-stage.ps1
$codexExe = 'D:\chromexiazai\codex-x86_64-pc-windows-msvc.exe'
$repoRoot  = 'd:\code\webnovel-writer'
$tmpDir    = $env:TEMP
$lastMsgFile = Join-Path $tmpDir 'test-raw-last.txt'

$env:OPENAI_API_KEY = 'sk-db4420e5de254a1467cc5cfb1a845e13'
$env:OPENAI_BASE_URL = 'https://api.asxs.top/v1'

Write-Host '==> 直接调用 codex exec...' -ForegroundColor Cyan
Write-Host ''

# 直接把 prompt 通过 stdin pipe 传给 codex
$prompt = 'Reply with exactly one word: HELLO'

$psi = [System.Diagnostics.ProcessStartInfo]::new($codexExe)
$psi.Arguments = "exec --ephemeral -s workspace-write -C `"$repoRoot`" --output-last-message `"$lastMsgFile`" -"
$psi.UseShellExecute = $false
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.WorkingDirectory = $repoRoot

$proc = [System.Diagnostics.Process]::new()
$proc.StartInfo = $psi
$null = $proc.Start()

$proc.StandardInput.Write($prompt)
$proc.StandardInput.Close()

# 读取输出
$stdout = $proc.StandardOutput.ReadToEnd()
$stderr = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()

Write-Host "Exit code: $($proc.ExitCode)" -ForegroundColor Yellow
Write-Host ''
Write-Host '=== STDOUT ===' -ForegroundColor Cyan
if ([string]::IsNullOrWhiteSpace($stdout)) { Write-Host '(empty)' -ForegroundColor Red } else { Write-Host $stdout }
Write-Host ''
Write-Host '=== STDERR ===' -ForegroundColor Cyan  
if ([string]::IsNullOrWhiteSpace($stderr)) { Write-Host '(empty)' -ForegroundColor Red } else { Write-Host $stderr }
Write-Host ''
Write-Host '=== Last Message ===' -ForegroundColor Cyan
if (Test-Path $lastMsgFile) { Get-Content $lastMsgFile } else { Write-Host '(not created)' -ForegroundColor Red }
