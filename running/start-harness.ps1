# start-harness.ps1
# One-click launcher for the Sisyphus development harness.
# Usage:
#   powershell -ExecutionPolicy Bypass -File running/start-harness.ps1
#   powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -ApiKey sk-xxx
#   powershell -ExecutionPolicy Bypass -File running/start-harness.ps1 -Mode ralph -MaxIterations 8

param(
    [string]$ApiKey = "",
    [ValidateSet("sisyphus", "ralph")]
    [string]$Mode = "sisyphus",
    [int]$MaxDispatches = 16,
    [int]$MaxIterations = 16,
    [int]$MaxParallel = 2,
    [string]$Model = "",
    [switch]$DryRun,
    [switch]$KeepWorktrees
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir

Write-Step "webnovel-writer Codex Development Harness"
Write-Step "Repo root: $repoRoot"
Write-Step "Mode: $Mode"

# --- Resolve API key ---
if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    if (-not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        $ApiKey = $env:OPENAI_API_KEY
        Write-Step "API key: from OPENAI_API_KEY env var (len=$($ApiKey.Length))"
    } elseif ($DryRun) {
        $ApiKey = "dry-run-placeholder"
        Write-Step "API key: dry-run placeholder (no real calls)"
    } else {
        Write-Host ""
        Write-Host "No API key found. Please enter your OpenAI-compatible API key:" -ForegroundColor Yellow
        Write-Host "(This key is used only for this session and is not stored to disk)" -ForegroundColor DarkGray
        $secureKey = Read-Host -Prompt "API Key" -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        $ApiKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        if ([string]::IsNullOrWhiteSpace($ApiKey)) {
            throw "API key is required to run the harness."
        }
        Write-Step "API key: entered interactively (len=$($ApiKey.Length))"
    }
}

# --- Dry-run preview always shown first ---
Write-Step "Queue preview (dry-run):"
$dryArgs = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", (Join-Path $scriptDir "sisyphus-dispatcher.ps1"),
    "-RepoRoot", $repoRoot,
    "-DryRun",
    "-MaxDispatches", "16"
)
& powershell @dryArgs
Write-Host ""

if ($DryRun) {
    Write-Step "DryRun mode: exiting without launching real execution."
    exit 0
}

# --- Launch ---
if ($Mode -eq "sisyphus") {
    Write-Step ("Launching Sisyphus dispatcher (MaxDispatches={0}, MaxParallel={1})" -f $MaxDispatches, $MaxParallel)
    $launchArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $scriptDir "sisyphus-dispatcher.ps1"),
        "-RepoRoot", $repoRoot,
        "-MaxDispatches", $MaxDispatches,
        "-MaxParallel", $MaxParallel,
        "-ApiKey", $ApiKey,
        "-ApiBaseUrl", "https://api.asxs.top/v1"
    )
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $launchArgs += @("-Model", $Model)
    }
    if ($KeepWorktrees) {
        $launchArgs += "-KeepWorktrees"
    }
    & powershell @launchArgs
} else {
    Write-Step ("Launching Ralph single-thread loop (MaxIterations={0})" -f $MaxIterations)
    $launchArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", (Join-Path $scriptDir "ralph-loop.ps1"),
        "-MaxIterations", $MaxIterations,
        "-ApiKey", $ApiKey,
        "-ApiBaseUrl", "https://api.asxs.top/v1"
    )
    if (-not [string]::IsNullOrWhiteSpace($Model)) {
        $launchArgs += @("-Model", $Model)
    }
    & powershell @launchArgs
}

Write-Step "Harness finished."
