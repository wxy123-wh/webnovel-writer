param(
    [string]$RepoRoot,
    [int]$MaxIterations = 20,
    [string]$CodexBin = "",
    [string]$CodexHome = "",
    [string]$CodexSandbox = "workspace-write",
    [switch]$DisableIsolatedCodexHome,
    [switch]$DisableGatewayBridge,
    [string]$GatewayBridgeScript = "running/codex-gateway-bridge.py",
    [string]$GatewayBridgeHost = "127.0.0.1",
    [int]$GatewayBridgePort = 18888,
    [ValidateSet("buffered", "stream")]
    [string]$GatewayBridgeResponseMode = "buffered",
    [string]$Model = "",
    [string]$ApiBaseUrl = "https://api.asxs.top/v1",
    [string]$ApiKey = "",
    [switch]$DryRun,
    [switch]$ContinueWhenBlocked,
    [string]$SessionArtifactsDir = "running/sessions",
    [switch]$DisableAutoRequeueOnFail
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Resolve-AbsolutePath {
    param([string]$PathValue)
    return (Resolve-Path -Path $PathValue).Path
}

function Resolve-CodexExecutable {
    param([string]$Requested)

    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        [void]$candidates.Add($Requested)
    }

    $homeDir = [Environment]::GetFolderPath("UserProfile")
    if (-not [string]::IsNullOrWhiteSpace($homeDir)) {
        [void]$candidates.Add((Join-Path $homeDir ".local\bin\codex.exe"))
        [void]$candidates.Add((Join-Path $homeDir ".local\bin\codex.cmd"))
    }

    [void]$candidates.Add("codexx.cmd")
    [void]$candidates.Add("codex.exe")
    [void]$candidates.Add("codex.cmd")
    [void]$candidates.Add("codex")

    $seen = @{}
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }

        $key = $candidate.ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            continue
        }
        $seen[$key] = $true

        $isExplicitPath = ($candidate.Contains("\") -or $candidate.Contains("/") -or $candidate.Contains(":"))
        if ($isExplicitPath) {
            if (Test-Path $candidate) {
                return (Resolve-Path $candidate).Path
            }
            continue
        }

        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $cmd) {
            continue
        }

        if ($cmd.CommandType -eq "Alias") {
            if (($null -ne $cmd.ResolvedCommand) -and (-not [string]::IsNullOrWhiteSpace($cmd.ResolvedCommand.Path))) {
                return $cmd.ResolvedCommand.Path
            }
            continue
        }

        if (-not [string]::IsNullOrWhiteSpace($cmd.Path)) {
            return $cmd.Path
        }
        if (-not [string]::IsNullOrWhiteSpace($cmd.Definition)) {
            return $cmd.Definition
        }
    }

    if ([string]::IsNullOrWhiteSpace($Requested)) {
        throw "Codex executable not found. Tried: ~/.local/bin/codex.exe, codexx.cmd, codex.exe, codex.cmd, codex."
    }
    throw "Codex executable not found: $Requested"
}

function Get-CodexCliVersion {
    param([string]$ExecutablePath)

    try {
        $raw = (& $ExecutablePath "--version" 2>&1 | Out-String).Trim()
    } catch {
        return ""
    }

    if ($raw -match "codex-cli\s+([0-9]+\.[0-9]+\.[0-9]+)") {
        return $Matches[1]
    }
    if ($raw -match "OpenAI Codex v([0-9]+\.[0-9]+\.[0-9]+)") {
        return $Matches[1]
    }
    return $raw
}

function Write-CodexHomeProviderConfig {
    param(
        [string]$HomeDir,
        [string]$ProviderId,
        [string]$BaseUrl
    )

    $configPath = Join-Path $HomeDir "config.toml"
    $content = @"
model_provider = "$ProviderId"

[model_providers.$ProviderId]
name = "Ralph Gateway"
base_url = "$BaseUrl"
env_key = "OPENAI_API_KEY"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
"@
    Set-Content -Path $configPath -Value $content -NoNewline
    return $configPath
}

function Load-FeatureList {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Missing feature list: $Path"
    }
    return Get-Content -Raw $Path | ConvertFrom-Json
}

function Save-FeatureList {
    param([string]$Path, [object]$State)
    $State | ConvertTo-Json -Depth 100 | Set-Content -Path $Path -NoNewline
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
        }}, priority, id |
        Select-Object -First 1
}

function Get-TaskById {
    param([object[]]$Features, [string]$TaskId)
    return $Features | Where-Object { $_.id -eq $TaskId } | Select-Object -First 1
}

function Ensure-TaskField {
    param(
        [object]$Task,
        [string]$Name,
        [object]$DefaultValue
    )
    if ($null -eq $Task.PSObject.Properties[$Name]) {
        $Task | Add-Member -NotePropertyName $Name -NotePropertyValue $DefaultValue
    }
}

function Requeue-FailedTaskToTail {
    param(
        [string]$FeatureListPath,
        [string]$TaskId,
        [string]$FailureSummary
    )

    $state = Load-FeatureList -Path $FeatureListPath
    $features = @($state.features)
    $task = $features | Where-Object { $_.id -eq $TaskId } | Select-Object -First 1
    if ($null -eq $task) {
        return $null
    }

    Ensure-TaskField -Task $task -Name "defer_to_tail" -DefaultValue $false
    Ensure-TaskField -Task $task -Name "failure_count" -DefaultValue 0
    Ensure-TaskField -Task $task -Name "last_failure_summary" -DefaultValue ""
    Ensure-TaskField -Task $task -Name "requeued_at" -DefaultValue ""
    Ensure-TaskField -Task $task -Name "notes" -DefaultValue ""
    Ensure-TaskField -Task $task -Name "status" -DefaultValue "pending"
    Ensure-TaskField -Task $task -Name "passes" -DefaultValue $false

    $now = (Get-Date).ToString("s")
    if ([string]::IsNullOrWhiteSpace($FailureSummary)) {
        $FailureSummary = "Verification failed in isolated session; deferred for end-of-queue handling."
    }

    $task.passes = $false
    $task.status = "pending"
    $task.defer_to_tail = $true
    $task.failure_count = [int]$task.failure_count + 1
    $task.last_failure_summary = $FailureSummary
    $task.requeued_at = $now

    $requeueNote = "[AUTO-REQUEUE $now] $FailureSummary"
    if ([string]::IsNullOrWhiteSpace([string]$task.notes)) {
        $task.notes = $requeueNote
    } else {
        $task.notes = ($task.notes + "`n" + $requeueNote)
    }

    $others = @($features | Where-Object { $_.id -ne $TaskId })
    $state.features = @($others + $task)
    Save-FeatureList -Path $FeatureListPath -State $state
    return $task
}

function New-SessionPrompt {
    param(
        [string]$TaskId,
        [int]$Iteration,
        [string]$RunId,
        [string]$RepoRoot
    )

    return @"
# Ralph Loop Session

Session run id: $RunId
Iteration: $Iteration
Assigned backlog item: $TaskId
Repository root: $RepoRoot

Hard constraints:
1. This run is stateless and must be treated as a brand-new conversation.
2. Do not assume any memory from previous sessions.
3. Do not use resume/fork semantics.
4. Follow running/workflow.md and running/prompts/coding_prompt.md.
5. Implement and evaluate exactly one item: $TaskId.
6. Update running/feature_list.json, running/codex-progress.md, and root log/*.md.
7. For frontend-impact tasks, run build and Playwright checks before completion.
8. If blocked, set status=blocked, human_help_requested=true, and write explicit human handoff.
9. If checks pass, create one conventional commit mapped to $TaskId.
10. If verification fails but no human handoff is required, summarize failure and keep data ready for auto-requeue-to-tail policy.
11. Existing unrelated local changes in this repository are expected. Do not stop only because git status is dirty.
12. Never revert unrelated files; only edit paths required by the assigned item.
"@
}

if ($MaxIterations -lt 1) {
    throw "MaxIterations must be >= 1."
}

$CodexBin = Resolve-CodexExecutable -Requested $CodexBin
$CodexCliVersion = Get-CodexCliVersion -ExecutablePath $CodexBin

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $scriptDir
}
$RepoRoot = Resolve-AbsolutePath $RepoRoot
Set-Location $RepoRoot

$featureListPath = Join-Path $RepoRoot "running/feature_list.json"
$sessionRoot = Join-Path $RepoRoot $SessionArtifactsDir
if (-not (Test-Path $sessionRoot)) {
    New-Item -ItemType Directory -Path $sessionRoot -Force | Out-Null
}

$effectiveApiBaseUrl = $ApiBaseUrl
$bridgeProcess = $null
$bridgeEligible = (
    (-not $DisableGatewayBridge) -and
    (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl)) -and
    ($ApiBaseUrl -match "^https://")
)
if ($bridgeEligible) {
    $bridgeScriptPath = Join-Path $RepoRoot $GatewayBridgeScript
    if (-not (Test-Path $bridgeScriptPath)) {
        throw "Gateway bridge script not found: $bridgeScriptPath"
    }

    $apiUri = [Uri]$ApiBaseUrl
    $apiPath = $apiUri.AbsolutePath
    if (($apiPath -eq "/") -or [string]::IsNullOrWhiteSpace($apiPath)) {
        $apiPath = ""
    } else {
        $apiPath = $apiPath.TrimEnd("/")
    }

    $effectiveApiBaseUrl = "http://$GatewayBridgeHost`:$GatewayBridgePort$apiPath"

    if (-not $DryRun) {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $pythonCmd) {
            throw "Python executable not found; cannot start gateway bridge."
        }

        $bridgeArgs = @(
            $bridgeScriptPath,
            "--listen-host", $GatewayBridgeHost,
            "--listen-port", [string]$GatewayBridgePort,
            "--upstream-base", $ApiBaseUrl,
            "--response-mode", $GatewayBridgeResponseMode
        )

        $bridgeProcess = Start-Process -FilePath $pythonCmd.Path `
            -ArgumentList $bridgeArgs `
            -PassThru `
            -WindowStyle Hidden
        Start-Sleep -Milliseconds 700
        if ($bridgeProcess.HasExited) {
            throw "Gateway bridge exited unexpectedly."
        }
    }
}

Write-Step "Ralph loop start (max iterations: $MaxIterations)"
Write-Step "Context policy: fresh session per iteration via codex exec --ephemeral"
Write-Step ("Codex sandbox mode: {0}" -f $CodexSandbox)
if (-not $DisableAutoRequeueOnFail) {
    Write-Step "Failure policy: auto-requeue failed tasks to queue tail (with summary)."
}
if (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    Write-Step ("API base URL: {0}" -f $ApiBaseUrl)
}
if ($null -ne $bridgeProcess) {
    Write-Step ("Gateway bridge: enabled ({0} -> {1}, mode={2})" -f $effectiveApiBaseUrl, $ApiBaseUrl, $GatewayBridgeResponseMode)
} elseif ($bridgeEligible -and $DryRun) {
    Write-Step ("Gateway bridge: dry-run launch skipped ({0} -> {1}, mode={2})" -f $effectiveApiBaseUrl, $ApiBaseUrl, $GatewayBridgeResponseMode)
} elseif ($DisableGatewayBridge) {
    Write-Step "Gateway bridge: disabled by parameter."
} elseif ($ApiBaseUrl -match "^http://") {
    Write-Step "Gateway bridge: skipped (upstream already plain HTTP)."
}
if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    Write-Step "API key source: script parameter (masked)."
}
if ([string]::IsNullOrWhiteSpace($CodexCliVersion)) {
    Write-Step ("Codex executable: {0}" -f $CodexBin)
} else {
    Write-Step ("Codex executable: {0} (codex-cli {1})" -f $CodexBin, $CodexCliVersion)
}
if (
    (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl)) -and
    (-not [string]::IsNullOrWhiteSpace($CodexCliVersion)) -and
    ($CodexCliVersion -match "^0\.")
) {
    Write-Step ("Compatibility warning: codex-cli {0} may be unstable with custom gateway streaming; prefer >= 1.x." -f $CodexCliVersion)
}
if (-not $DisableIsolatedCodexHome) {
    if ([string]::IsNullOrWhiteSpace($CodexHome)) {
        $CodexHome = Join-Path $RepoRoot "running/.codex-home"
    }
    if (-not (Test-Path $CodexHome)) {
        New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null
    }
    $codexHomeConfigPath = Write-CodexHomeProviderConfig -HomeDir $CodexHome -ProviderId "asxs" -BaseUrl $effectiveApiBaseUrl
    Write-Step ("Codex home mode: isolated ({0})" -f $CodexHome)
    Write-Step ("Codex home provider config: {0}" -f $codexHomeConfigPath)
} else {
    Write-Step "Codex home mode: inherited from current environment."
    if (-not [string]::IsNullOrWhiteSpace($effectiveApiBaseUrl)) {
        Write-Step ("Inherited provider override: model_providers.codex.base_url={0}" -f $effectiveApiBaseUrl)
    }
}
Write-Step "Repo root: $RepoRoot"

$completedIterations = 0

try {
for ($i = 1; $i -le $MaxIterations; $i++) {
    $state = Load-FeatureList -Path $featureListPath

    $blocked = @(
        $state.features | Where-Object {
            ($_.status -eq "blocked") -and ($_.human_help_requested -eq $true)
        }
    )
    if (($blocked.Count -gt 0) -and (-not $ContinueWhenBlocked)) {
        Write-Step "Stop: detected blocked tasks requiring human assistance."
        foreach ($b in $blocked) {
            Write-Host ("   - {0}: {1}" -f $b.id, $b.blocked_reason) -ForegroundColor Yellow
        }
        break
    }

    $task = Get-NextPendingTask -Features $state.features
    if ($null -eq $task) {
        Write-Step "No pending tasks remaining."
        break
    }

    $runId = "{0}-{1:D2}-{2}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $i, $task.id
    $runDir = Join-Path $sessionRoot $runId
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null

    $promptPath = Join-Path $runDir "prompt.md"
    $outputPath = Join-Path $runDir "codex-output.log"
    $lastMessagePath = Join-Path $runDir "last-message.txt"

    $prompt = New-SessionPrompt -TaskId $task.id -Iteration $i -RunId $runId -RepoRoot $RepoRoot
    Set-Content -Path $promptPath -Value $prompt -NoNewline

    Write-Step ("Iteration {0}: run task {1} (priority={2})" -f $i, $task.id, $task.priority)
    Write-Step ("Session artifact dir: {0}" -f $runDir)

    if ($DryRun) {
        Write-Step "DryRun enabled: skip codex execution."
        continue
    }

    $args = @(
        "exec",
        "--ephemeral",
        "-s", $CodexSandbox,
        "-C", $RepoRoot,
        "--output-last-message", $lastMessagePath
    )
    if ($DisableIsolatedCodexHome -and (-not [string]::IsNullOrWhiteSpace($effectiveApiBaseUrl))) {
        $args += @("-c", ("model_provider=`"codex`""))
        $args += @("-c", ("model_providers.codex.base_url=`"{0}`"" -f $effectiveApiBaseUrl))
    }
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $args += @("-m", $Model)
    }
    $args += "-"

    Write-Step ("Launch command: {0} {1}" -f $CodexBin, ($args -join " "))

    $hadNativePref = $null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)
    if ($hadNativePref) {
        $prevNativePref = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    $prevErrPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $prevApiBaseUrl = $env:OPENAI_BASE_URL
    $setApiBaseUrl = -not [string]::IsNullOrWhiteSpace($effectiveApiBaseUrl)
    if ($setApiBaseUrl) {
        $env:OPENAI_BASE_URL = $effectiveApiBaseUrl
    }
    $prevApiKey = $env:OPENAI_API_KEY
    $setApiKey = -not [string]::IsNullOrWhiteSpace($ApiKey)
    if ($setApiKey) {
        $env:OPENAI_API_KEY = $ApiKey
    }
    $prevCodexHome = $env:CODEX_HOME
    $setCodexHome = -not $DisableIsolatedCodexHome
    if ($setCodexHome) {
        $env:CODEX_HOME = $CodexHome
    }

    try {
        $result = $prompt | & $CodexBin @args 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        if ($setCodexHome) {
            if ([string]::IsNullOrWhiteSpace($prevCodexHome)) {
                Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
            } else {
                $env:CODEX_HOME = $prevCodexHome
            }
        }
        if ($setApiKey) {
            if ([string]::IsNullOrWhiteSpace($prevApiKey)) {
                Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
            } else {
                $env:OPENAI_API_KEY = $prevApiKey
            }
        }
        if ($setApiBaseUrl) {
            if ([string]::IsNullOrWhiteSpace($prevApiBaseUrl)) {
                Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue
            } else {
                $env:OPENAI_BASE_URL = $prevApiBaseUrl
            }
        }
        $ErrorActionPreference = $prevErrPref
        if ($hadNativePref) {
            $PSNativeCommandUseErrorActionPreference = $prevNativePref
        }
    }

    ($result | Out-String) | Set-Content -Path $outputPath -NoNewline

    if ($exitCode -ne 0) {
        # Exit code 1 = task-level failure (requeue to tail); any other code = environment/process crash (stop loop)
        if ($exitCode -eq 1) {
            Write-Step ("Codex run exited with code 1 (task failure); requeueing task {0}." -f $task.id)
            if (-not $DisableAutoRequeueOnFail) {
                $requeued = Requeue-FailedTaskToTail -FeatureListPath $featureListPath -TaskId $task.id -FailureSummary ("codex exit code 1 in isolated session.")
                if ($null -ne $requeued) {
                    Write-Step ("Task {0} requeued to tail (failure_count={1})." -f $requeued.id, $requeued.failure_count)
                }
            }
            continue
        }
        Write-Step ("Stop: codex run failed with environment/process error (exit code {0})." -f $exitCode)
        break
    }

    $stateAfter = Load-FeatureList -Path $featureListPath
    $taskAfter = Get-TaskById -Features $stateAfter.features -TaskId $task.id
    if ($null -eq $taskAfter) {
        Write-Step ("Stop: task disappeared from feature_list: {0}" -f $task.id)
        break
    }

    Write-Step ("Task {0} => status={1}, passes={2}, human_help_requested={3}" -f $task.id, $taskAfter.status, $taskAfter.passes, $taskAfter.human_help_requested)

    if (($taskAfter.status -eq "done") -and ($taskAfter.passes -eq $true)) {
        $completedIterations += 1
        continue
    }

    if ($taskAfter.human_help_requested -eq $true) {
        Write-Step "Stop: task blocked and requires human assistance."
        break
    }

    if (($taskAfter.passes -ne $true) -and (-not $DisableAutoRequeueOnFail)) {
        $failureSummary = ""
        if (-not [string]::IsNullOrWhiteSpace([string]$taskAfter.blocked_reason)) {
            $failureSummary = [string]$taskAfter.blocked_reason
        } elseif (-not [string]::IsNullOrWhiteSpace([string]$taskAfter.last_failure_summary)) {
            $failureSummary = [string]$taskAfter.last_failure_summary
        } else {
            $failureSummary = "Verification failed in isolated session; deferred for end-of-queue handling."
        }

        $requeued = Requeue-FailedTaskToTail -FeatureListPath $featureListPath -TaskId $task.id -FailureSummary $failureSummary
        if ($null -ne $requeued) {
            Write-Step ("Task {0} requeued to tail (failure_count={1})." -f $requeued.id, $requeued.failure_count)
            continue
        }
    }

    Write-Step "Stop: task not completed in this isolated session."
    break
}
} finally {
    if ($null -ne $bridgeProcess) {
        if (-not $bridgeProcess.HasExited) {
            Stop-Process -Id $bridgeProcess.Id -Force -ErrorAction SilentlyContinue
        }
        Write-Step "Gateway bridge stopped."
    }
}

Write-Step ("Ralph loop finished. Completed iterations: {0}" -f $completedIterations)
