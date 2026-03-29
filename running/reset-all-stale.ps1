# reset-all-stale.ps1 — 把所有 in_progress/blocked 任务重置为 pending
$flPath = 'd:\code\webnovel-writer\running\feature_list.json'
$fl = Get-Content $flPath -Raw | ConvertFrom-Json

foreach ($task in $fl.features) {
    if ($task.status -in @('in_progress', 'blocked')) {
        Write-Host "Resetting $($task.id): $($task.status) -> pending" -ForegroundColor Yellow
        $task.status = 'pending'
        $task.human_help_requested = $false
        $task.blocked_reason = ''
        $task.claimed_by = ''
        $task.claimed_at = ''
        $task.started_at = ''
        $task.defer_to_tail = $false
    }
}

$fl | ConvertTo-Json -Depth 100 | Set-Content $flPath -Encoding UTF8
Write-Host 'Done.' -ForegroundColor Green
