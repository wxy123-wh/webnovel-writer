# check-agent-output.ps1
$sessDir = 'd:\code\webnovel-writer\running\sessions'
$sess = Get-ChildItem $sessDir -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($null -eq $sess) { Write-Host 'No sessions found'; exit 1 }
Write-Host "Latest session: $($sess.Name)" -ForegroundColor Cyan

$log = Join-Path $sess.FullName 'coding-output.log'
if (Test-Path $log) {
    $size = (Get-Item $log).Length
    Write-Host "Log size: $size bytes" -ForegroundColor Green
    Write-Host '--- First 80 lines ---' -ForegroundColor Gray
    Get-Content $log | Select-Object -First 80
} else {
    Write-Host 'No coding-output.log found' -ForegroundColor Red
    Write-Host 'Files in session:'
    Get-ChildItem $sess.FullName | ForEach-Object { Write-Host "  $_" }
}
