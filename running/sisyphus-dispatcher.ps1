param(
    [string]$RepoRoot,
    [int]$MaxDispatches = 20,
    [int]$MaxParallel = 2,
    [string]$WorktreeRoot = ".worktrees/sisyphus",
    [string]$BranchPrefix = "codex/sisyphus",
    [string]$CodexBin = "",
    [string]$CodexSandbox = "workspace-write",
    [string]$Model = "",
    [string]$ApiBaseUrl = "https://api.asxs.top/v1",
    [string]$ApiKey = "",
    [string]$CodexHome = "",
    [switch]$DisableIsolatedCodexHome,
    [switch]$DryRun,
    [switch]$ContinueWhenBlocked,
    [switch]$KeepWorktrees,
    [string]$SessionArtifactsDir = "running/sessions",
    [string]$DispatcherId = "sisyphus-dispatcher"
)

$ErrorActionPreference = "Stop"

if (-not $PSBoundParameters.ContainsKey("KeepWorktrees")) {
    $KeepWorktrees = $true
}
if ($MaxDispatches -lt 1) { throw "MaxDispatches must be >= 1." }
if ($MaxParallel -lt 1) { throw "MaxParallel must be >= 1." }

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-AbsPath {
    param([string]$PathValue, [string]$BaseDir)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDir $PathValue))
}

function Resolve-CodexExecutable {
    param([string]$Requested)
    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Requested)) { [void]$candidates.Add($Requested) }

    $userHome = [Environment]::GetFolderPath("UserProfile")
    if (-not [string]::IsNullOrWhiteSpace($userHome)) {
        [void]$candidates.Add((Join-Path $userHome ".local\bin\codex.exe"))
        [void]$candidates.Add((Join-Path $userHome ".local\bin\codex.cmd"))
    }
    [void]$candidates.Add("codexx.cmd")
    [void]$candidates.Add("codex.exe")
    [void]$candidates.Add("codex.cmd")
    [void]$candidates.Add("codex")

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $isPath = ($candidate.Contains("\") -or $candidate.Contains("/") -or $candidate.Contains(":"))
        if ($isPath) {
            if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
            continue
        }
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $cmd) { continue }
        if (-not [string]::IsNullOrWhiteSpace($cmd.Path)) { return $cmd.Path }
        if (-not [string]::IsNullOrWhiteSpace($cmd.Definition)) { return $cmd.Definition }
    }
    throw "Codex executable not found."
}

function Load-FeatureList {
    param([string]$Path)
    if (-not (Test-Path $Path)) { throw "Missing feature list: $Path" }
    return Get-Content -Raw $Path | ConvertFrom-Json
}

function Save-FeatureList {
    param([string]$Path, [object]$State)
    $State | ConvertTo-Json -Depth 100 | Set-Content -Path $Path -NoNewline
}

function Ensure-TaskRuntimeFields {
    param([object]$Task)
    $defaults = @{
        passes = $false
        status = "pending"
        claimed_by = ""
        claimed_at = ""
        started_at = ""
        completed_at = ""
        blocked_reason = ""
        human_help_requested = $false
        handoff_requested_at = ""
        defer_to_tail = $false
        failure_count = 0
        last_failure_summary = ""
        requeued_at = ""
        notes = ""
        last_verified_at = ""
    }
    foreach ($key in $defaults.Keys) {
        if ($null -eq $Task.PSObject.Properties[$key]) {
            $Task | Add-Member -NotePropertyName $key -NotePropertyValue $defaults[$key]
        }
    }
}

function Append-TaskNote {
    param([object]$Task, [string]$Note)
    if ([string]::IsNullOrWhiteSpace($Note)) { return }
    if ([string]::IsNullOrWhiteSpace([string]$Task.notes)) {
        $Task.notes = $Note
    } else {
        $Task.notes = ($Task.notes + "`n" + $Note)
    }
}

function Update-Task {
    param([string]$FeatureListPath, [string]$TaskId, [scriptblock]$Updater)
    $state = Load-FeatureList -Path $FeatureListPath
    $task = @($state.features | Where-Object { $_.id -eq $TaskId })[0]
    if ($null -eq $task) { throw "Task not found: $TaskId" }
    Ensure-TaskRuntimeFields -Task $task
    & $Updater $task
    Save-FeatureList -Path $FeatureListPath -State $state
    return $task
}

function Get-NextPendingTask {
    param([object[]]$Features)
    return $Features |
        Where-Object {
            ($_.passes -ne $true) -and
            (($_.status -eq "pending") -or [string]::IsNullOrWhiteSpace([string]$_.status))
        } |
        Sort-Object -Property @{ Expression = {
            if (($_.PSObject.Properties["defer_to_tail"]) -and ($_.defer_to_tail -eq $true)) { 1 } else { 0 }
        }}, @{ Expression = {
            $p = $_.priority
            if ($null -eq $p) { return 9999 }
            $n = 0
            if ([int]::TryParse([string]$p, [ref]$n)) { return $n } else { return 9999 }
        }}, id |
        Select-Object -First 1
}

function Claim-Task {
    param([string]$FeatureListPath, [string]$TaskId, [string]$ClaimedBy)
    $now = (Get-Date).ToString("s")
    return Update-Task -FeatureListPath $FeatureListPath -TaskId $TaskId -Updater {
        param($task)
        $task.status = "claimed"
        $task.claimed_by = $ClaimedBy
        $task.claimed_at = $now
        $task.status = "in_progress"
        $task.started_at = $now
        $task.human_help_requested = $false
        $task.blocked_reason = ""
        Append-TaskNote -Task $task -Note ("[DISPATCH {0}] Claimed by {1}" -f $now, $ClaimedBy)
    }
}

function Mark-TaskPass {
    param([string]$FeatureListPath, [string]$TaskId, [string]$RunId, [string]$BranchName, [string]$WorktreePath)
    $now = (Get-Date).ToString("s")
    return Update-Task -FeatureListPath $FeatureListPath -TaskId $TaskId -Updater {
        param($task)
        $task.passes = $true
        $task.status = "done"
        $task.completed_at = $now
        $task.last_verified_at = $now
        $task.human_help_requested = $false
        $task.blocked_reason = ""
        $task.defer_to_tail = $false
        Append-TaskNote -Task $task -Note ("[PASS {0}] run={1} branch={2} worktree={3}" -f $now, $RunId, $BranchName, $WorktreePath)
    }
}

function Mark-TaskFail {
    param([string]$FeatureListPath, [string]$TaskId, [string]$RunId, [string]$Summary, [bool]$HumanHelpRequested)
    $now = (Get-Date).ToString("s")
    return Update-Task -FeatureListPath $FeatureListPath -TaskId $TaskId -Updater {
        param($task)
        $task.passes = $false
        $task.last_verified_at = $now
        if ($HumanHelpRequested) {
            $task.status = "blocked"
            $task.human_help_requested = $true
            $task.blocked_reason = $Summary
            $task.handoff_requested_at = $now
            Append-TaskNote -Task $task -Note ("[BLOCKED {0}] run={1} {2}" -f $now, $RunId, $Summary)
        } else {
            $task.status = "pending"
            $task.human_help_requested = $false
            $task.blocked_reason = ""
            $task.defer_to_tail = $true
            $task.failure_count = [int]$task.failure_count + 1
            $task.last_failure_summary = $Summary
            $task.requeued_at = $now
            Append-TaskNote -Task $task -Note ("[REQUEUE {0}] run={1} {2}" -f $now, $RunId, $Summary)
        }
    }
}

function Parse-EvaluatorResult {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $null }
    $raw = (Get-Content -Raw $Path).Trim()
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    try {
        return $raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        return $null
    }
}

function Start-StageProcess {
    param(
        [string]$StageScriptPath,
        [string]$RepoRoot,
        [string]$WorktreePath,
        [string]$CodexBin,
        [string]$CodexSandbox,
        [string]$PromptPath,
        [string]$LastMessagePath,
        [string]$TranscriptPath,
        [string]$Model,
        [string]$ApiBaseUrl,
        [string]$ApiKey,
        [string]$CodexHome,
        [switch]$DisableIsolatedCodexHome
    )
    $argList = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $StageScriptPath,
        "-RepoRoot", $RepoRoot,
        "-WorktreePath", $WorktreePath,
        "-CodexBin", $CodexBin,
        "-CodexSandbox", $CodexSandbox,
        "-PromptPath", $PromptPath,
        "-OutputLastMessagePath", $LastMessagePath,
        "-TranscriptPath", $TranscriptPath,
        "-ApiBaseUrl", $ApiBaseUrl,
        "-ApiKey", $ApiKey
    )
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $argList += @("-Model", $Model)
    }
    if ($DisableIsolatedCodexHome) {
        $argList += "-DisableIsolatedCodexHome"
    } elseif (-not [string]::IsNullOrWhiteSpace($CodexHome)) {
        $argList += @("-CodexHome", $CodexHome)
    }
    return Start-Process -FilePath "powershell" -ArgumentList $argList -PassThru -WindowStyle Hidden
}

function New-TaskWorktree {
    param([string]$RepoRoot, [string]$WorktreeRoot, [string]$BranchPrefix, [string]$TaskId, [string]$RunId)
    if (-not (Test-Path $WorktreeRoot)) {
        New-Item -ItemType Directory -Path $WorktreeRoot -Force | Out-Null
    }
    $branchName = ("{0}/{1}-{2}" -f $BranchPrefix.TrimEnd("/"), $TaskId.ToLowerInvariant(), $RunId)
    $worktreePath = Join-Path $WorktreeRoot ("{0}-{1}" -f $TaskId.ToLowerInvariant(), $RunId)
    $prevEA = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $hadNative = $null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)
    if ($hadNative) { $prevNative = $PSNativeCommandUseErrorActionPreference; $PSNativeCommandUseErrorActionPreference = $false }
    $result = & git -C $RepoRoot worktree add -b $branchName $worktreePath HEAD 2>&1
    $gitExit = $LASTEXITCODE
    if ($hadNative) { $PSNativeCommandUseErrorActionPreference = $prevNative }
    $ErrorActionPreference = $prevEA
    if ($gitExit -ne 0) {
        throw "git worktree add failed (exit $gitExit): $($result | Out-String)"
    }
    return [PSCustomObject]@{
        BranchName = $branchName
        WorktreePath = $worktreePath
    }
}

function Remove-TaskWorktree {
    param([string]$RepoRoot, [string]$WorktreePath)
    if (Test-Path $WorktreePath) {
        & git -C $RepoRoot worktree remove --force $WorktreePath | Out-Null
    }
}

function Append-ProgressNote {
    param(
        [string]$ProgressPath,
        [string]$TaskId,
        [string]$RunId,
        [string]$Stage,
        [string]$Result,
        [string]$Status,
        [string]$BranchName,
        [string]$Note
    )
    if (-not (Test-Path $ProgressPath)) { return }
    $date = Get-Date -Format "yyyy-MM-dd"
    $line = ("| {0} | Sisyphus dispatcher run | {1} | {2} | N/A | stage={3}; run={4} | {5} | {6} | N/A | {7} |" -f $date, $TaskId, $Status, $Stage, $RunId, $BranchName, $Result, $Note)
    Add-Content -Path $ProgressPath -Value $line
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $scriptDir
}
$RepoRoot = Get-AbsPath -PathValue $RepoRoot -BaseDir $PWD.Path
$featureListPath = Join-Path $RepoRoot "running/feature_list.json"
$progressPath = Join-Path $RepoRoot "running/codex-progress.md"
$stageScriptPath = Join-Path $RepoRoot "running/run-codex-stage.ps1"
$codingTemplatePath = Join-Path $RepoRoot "running/prompts/sisyphus_coding_worker_prompt.md"
$evaluatorTemplatePath = Join-Path $RepoRoot "running/prompts/sisyphus_evaluator_worker_prompt.md"
$sessionRoot = Get-AbsPath -PathValue $SessionArtifactsDir -BaseDir $RepoRoot
$worktreeRootAbs = Get-AbsPath -PathValue $WorktreeRoot -BaseDir $RepoRoot
$CodexBin = Resolve-CodexExecutable -Requested $CodexBin

if (-not (Test-Path $sessionRoot)) { New-Item -ItemType Directory -Path $sessionRoot -Force | Out-Null }
if (-not (Test-Path $stageScriptPath)) { throw "Missing stage script: $stageScriptPath" }
if (-not (Test-Path $codingTemplatePath)) { throw "Missing coding template: $codingTemplatePath" }
if (-not (Test-Path $evaluatorTemplatePath)) { throw "Missing evaluator template: $evaluatorTemplatePath" }

Write-Step ("Sisyphus dispatcher start max_dispatches={0} max_parallel={1}" -f $MaxDispatches, $MaxParallel)
Write-Step ("Codex executable: {0}" -f $CodexBin)
Write-Step ("Worktree root: {0}" -f $worktreeRootAbs)

if ($DryRun) {
    $state = Load-FeatureList -Path $featureListPath
    $preview = @($state.features | Where-Object {
        ($_.passes -ne $true) -and (($_.status -eq "pending") -or [string]::IsNullOrWhiteSpace([string]$_.status))
    } | Sort-Object priority, id | Select-Object -First $MaxDispatches)
    Write-Step ("DryRun: next tasks count={0}" -f $preview.Count)
    foreach ($t in $preview) {
        Write-Host (" - {0} p={1} {2}" -f $t.id, $t.priority, $t.title) -ForegroundColor Yellow
    }
    exit 0
}

$active = New-Object System.Collections.Generic.List[object]
$dispatched = 0
$completed = 0
$queueFinished = $false

while ($true) {
    while (($active.Count -lt $MaxParallel) -and ($dispatched -lt $MaxDispatches) -and (-not $queueFinished)) {
        $state = Load-FeatureList -Path $featureListPath
        $blocked = @($state.features | Where-Object { ($_.status -eq "blocked") -and ($_.human_help_requested -eq $true) })
        if (($blocked.Count -gt 0) -and (-not $ContinueWhenBlocked)) {
            Write-Step "Dispatch paused because blocked tasks exist."
            $queueFinished = $true
            break
        }

        $task = Get-NextPendingTask -Features @($state.features)
        if ($null -eq $task) {
            $queueFinished = $true
            break
        }

        $runId = "{0}-{1:D2}-{2}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), ($dispatched + 1), $task.id
        $runDir = Join-Path $sessionRoot $runId
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null

        $null = Claim-Task -FeatureListPath $featureListPath -TaskId $task.id -ClaimedBy $DispatcherId
        $worktree = New-TaskWorktree -RepoRoot $RepoRoot -WorktreeRoot $worktreeRootAbs -BranchPrefix $BranchPrefix -TaskId $task.id -RunId $runId

        $taskJson = $task | ConvertTo-Json -Depth 50
        $codingPromptPath = Join-Path $runDir "coding-prompt.md"
        $evalPromptPath = Join-Path $runDir "evaluator-prompt.md"
        $codingLastPath = Join-Path $runDir "coding-last-message.txt"
        $evalLastPath = Join-Path $runDir "evaluator-last-message.txt"
        $codingOutPath = Join-Path $runDir "coding-output.log"
        $evalOutPath = Join-Path $runDir "evaluator-output.log"

        $codingPromptLines = @(
            (Get-Content -Raw $codingTemplatePath).TrimEnd(),
            "",
            ("run_id: {0}" -f $runId),
            ("task_id: {0}" -f $task.id),
            ("worktree: {0}" -f $worktree.WorktreePath),
            "",
            "Task JSON:",
            '```json',
            $taskJson,
            '```'
        )
        $codingPromptLines -join "`n" | Set-Content -Path $codingPromptPath -NoNewline

        $evalPromptLines = @(
            (Get-Content -Raw $evaluatorTemplatePath).TrimEnd(),
            "",
            ("run_id: {0}" -f $runId),
            ("task_id: {0}" -f $task.id),
            ("worktree: {0}" -f $worktree.WorktreePath),
            "",
            "Task JSON:",
            '```json',
            $taskJson,
            '```'
        )
        $evalPromptLines -join "`n" | Set-Content -Path $evalPromptPath -NoNewline

        $codingProc = Start-StageProcess -StageScriptPath $stageScriptPath -RepoRoot $RepoRoot -WorktreePath $worktree.WorktreePath -CodexBin $CodexBin -CodexSandbox $CodexSandbox -PromptPath $codingPromptPath -LastMessagePath $codingLastPath -TranscriptPath $codingOutPath -Model $Model -ApiBaseUrl $ApiBaseUrl -ApiKey $ApiKey -CodexHome $CodexHome -DisableIsolatedCodexHome:$DisableIsolatedCodexHome

        [void]$active.Add([PSCustomObject]@{
            TaskId = $task.id
            RunId = $runId
            BranchName = $worktree.BranchName
            WorktreePath = $worktree.WorktreePath
            Stage = "coding"
            Process = $codingProc
            EvalPromptPath = $evalPromptPath
            EvalLastPath = $evalLastPath
            EvalOutPath = $evalOutPath
            CodingOutPath = $codingOutPath
        })
        $dispatched += 1
        Write-Step ("Dispatched {0} to branch {1}" -f $task.id, $worktree.BranchName)
    }

    if ($active.Count -eq 0) {
        if ($queueFinished -or ($dispatched -ge $MaxDispatches)) { break }
        Start-Sleep -Seconds 1
        continue
    }

    Start-Sleep -Seconds 2
    $remaining = New-Object System.Collections.Generic.List[object]

    foreach ($entry in $active) {
        if (-not $entry.Process.HasExited) {
            [void]$remaining.Add($entry)
            continue
        }

        if ($entry.Stage -eq "coding") {
            if ($entry.Process.ExitCode -ne 0) {
                $exitCode = $entry.Process.ExitCode
                $summary = "Coding worker exit code $exitCode"
                # Exit code 1 = task-level failure (requeue); any other code = environment/process crash (block for human)
                $isEnvCrash = ($exitCode -ne 1)
                $taskAfter = Mark-TaskFail -FeatureListPath $featureListPath -TaskId $entry.TaskId -RunId $entry.RunId -Summary $summary -HumanHelpRequested $isEnvCrash
                Append-ProgressNote -ProgressPath $progressPath -TaskId $entry.TaskId -RunId $entry.RunId -Stage "coding" -Result "FAIL" -Status $taskAfter.status -BranchName $entry.BranchName -Note $summary
                Write-Step ("Task {0} failed in coding stage." -f $entry.TaskId)
                if (-not $KeepWorktrees) { Remove-TaskWorktree -RepoRoot $RepoRoot -WorktreePath $entry.WorktreePath }
                $completed += 1
                continue
            }

            $evalProc = Start-StageProcess -StageScriptPath $stageScriptPath -RepoRoot $RepoRoot -WorktreePath $entry.WorktreePath -CodexBin $CodexBin -CodexSandbox $CodexSandbox -PromptPath $entry.EvalPromptPath -LastMessagePath $entry.EvalLastPath -TranscriptPath $entry.EvalOutPath -Model $Model -ApiBaseUrl $ApiBaseUrl -ApiKey $ApiKey -CodexHome $CodexHome -DisableIsolatedCodexHome:$DisableIsolatedCodexHome
            $entry.Stage = "evaluator"
            $entry.Process = $evalProc
            [void]$remaining.Add($entry)
            Write-Step ("Task {0} coding finished; evaluator started." -f $entry.TaskId)
            continue
        }

        if ($entry.Process.ExitCode -ne 0) {
            $exitCode = $entry.Process.ExitCode
            $summary = "Evaluator worker exit code $exitCode"
            # Exit code 1 = task-level failure (requeue); any other code = environment/process crash (block for human)
            $isEnvCrash = ($exitCode -ne 1)
            $taskAfter = Mark-TaskFail -FeatureListPath $featureListPath -TaskId $entry.TaskId -RunId $entry.RunId -Summary $summary -HumanHelpRequested $isEnvCrash
            Append-ProgressNote -ProgressPath $progressPath -TaskId $entry.TaskId -RunId $entry.RunId -Stage "evaluator" -Result "FAIL" -Status $taskAfter.status -BranchName $entry.BranchName -Note $summary
            Write-Step ("Task {0} failed in evaluator stage." -f $entry.TaskId)
            if (-not $KeepWorktrees) { Remove-TaskWorktree -RepoRoot $RepoRoot -WorktreePath $entry.WorktreePath }
            $completed += 1
            continue
        }

        $evalResult = Parse-EvaluatorResult -Path $entry.EvalLastPath
        if (($null -ne $evalResult) -and ([string]$evalResult.result -ieq "PASS")) {
            $taskAfter = Mark-TaskPass -FeatureListPath $featureListPath -TaskId $entry.TaskId -RunId $entry.RunId -BranchName $entry.BranchName -WorktreePath $entry.WorktreePath
            Append-ProgressNote -ProgressPath $progressPath -TaskId $entry.TaskId -RunId $entry.RunId -Stage "evaluator" -Result "PASS" -Status $taskAfter.status -BranchName $entry.BranchName -Note "Evaluator PASS"
            Write-Step ("Task {0} PASS." -f $entry.TaskId)
            if (-not $KeepWorktrees) { Remove-TaskWorktree -RepoRoot $RepoRoot -WorktreePath $entry.WorktreePath }
            $completed += 1
            continue
        }

        $summary = "Evaluator FAIL"
        $human = $false
        if ($null -eq $evalResult) {
            $summary = "Evaluator output unparsable"
            $human = $true
        } else {
            if ($null -ne $evalResult.gaps) {
                $summary = "gaps: " + (@($evalResult.gaps) -join "; ")
            }
            if ($null -ne $evalResult.PSObject.Properties["human_help_requested"]) {
                $human = [bool]$evalResult.human_help_requested
            }
        }
        $taskAfter = Mark-TaskFail -FeatureListPath $featureListPath -TaskId $entry.TaskId -RunId $entry.RunId -Summary $summary -HumanHelpRequested $human
        Append-ProgressNote -ProgressPath $progressPath -TaskId $entry.TaskId -RunId $entry.RunId -Stage "evaluator" -Result "FAIL" -Status $taskAfter.status -BranchName $entry.BranchName -Note $summary
        Write-Step ("Task {0} FAIL." -f $entry.TaskId)
        if ((-not $KeepWorktrees) -and (-not $human)) {
            Remove-TaskWorktree -RepoRoot $RepoRoot -WorktreePath $entry.WorktreePath
        }
        $completed += 1
    }

    $active = $remaining
}

Write-Step ("Dispatcher finished dispatched={0} completed={1}" -f $dispatched, $completed)
