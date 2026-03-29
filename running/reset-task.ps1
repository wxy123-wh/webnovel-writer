# reset-task.ps1 — 重置任务状态为 pending
param([string]$TaskId = 'T009')

$flPath = 'd:\code\webnovel-writer\running\feature_list.json'
$fl = Get-Content $flPath -Raw | ConvertFrom-Json
$task = @($fl.features | Where-Object { $_.id -eq $TaskId })[0]
if ($null -eq $task) { Write-Host "Task $TaskId not found"; exit 1 }

Write-Host "Before: id=$($task.id) status=$($task.status) passes=$($task.passes) blocked=$($task.human_help_requested)" -ForegroundColor Yellow

$task.status = 'pending'
$task.passes = $false
$task.human_help_requested = $false
$task.blocked_reason = ''
$task.defer_to_tail = $false

$fl | ConvertTo-Json -Depth 100 | Set-Content $flPath -NoNewline
Write-Host "After:  id=$($task.id) status=$($task.status) passes=$($task.passes)" -ForegroundColor Green
