param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$WorktreePath,
    [Parameter(Mandatory = $true)][string]$CodexBin,
    [string]$CodexSandbox = "workspace-write",
    [Parameter(Mandatory = $true)][string]$PromptPath,
    [Parameter(Mandatory = $true)][string]$OutputLastMessagePath,
    [Parameter(Mandatory = $true)][string]$TranscriptPath,
    [string]$Model = "",
    [string]$ApiBaseUrl = "",
    [string]$ApiKey = "",
    [string]$CodexHome = "",
    [switch]$DisableIsolatedCodexHome
)

$ErrorActionPreference = "Stop"

function Resolve-Abs {
    param([string]$PathValue)
    return (Resolve-Path -Path $PathValue).Path
}

$RepoRoot = Resolve-Abs $RepoRoot
$WorktreePath = Resolve-Abs $WorktreePath
$PromptPath = Resolve-Abs $PromptPath
$CodexBin = Resolve-Abs $CodexBin

$outputDir = Split-Path -Parent $OutputLastMessagePath
if (-not [string]::IsNullOrWhiteSpace($outputDir) -and (-not (Test-Path $outputDir))) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}
$transcriptDir = Split-Path -Parent $TranscriptPath
if (-not [string]::IsNullOrWhiteSpace($transcriptDir) -and (-not (Test-Path $transcriptDir))) {
    New-Item -ItemType Directory -Path $transcriptDir -Force | Out-Null
}

$prompt = Get-Content -Path $PromptPath -Raw
$args = @(
    "exec",
    "--ephemeral",
    "-s", $CodexSandbox,
    "-C", $WorktreePath,
    "--output-last-message", $OutputLastMessagePath
)

if ($DisableIsolatedCodexHome -and (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl))) {
    $args += @("-c", "model_provider=`"codex`"")
    $args += @("-c", ("model_providers.codex.base_url=`"{0}`"" -f $ApiBaseUrl))
}
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $args += @("-m", $Model)
}
$args += "-"

$prevErrPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$hadNativePref = $null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)
if ($hadNativePref) {
    $prevNativePref = $PSNativeCommandUseErrorActionPreference
    $PSNativeCommandUseErrorActionPreference = $false
}

$prevApiBaseUrl = $env:OPENAI_BASE_URL
$setApiBaseUrl = -not [string]::IsNullOrWhiteSpace($ApiBaseUrl)
if ($setApiBaseUrl) {
    $env:OPENAI_BASE_URL = $ApiBaseUrl
}

$prevApiKey = $env:OPENAI_API_KEY
$setApiKey = -not [string]::IsNullOrWhiteSpace($ApiKey)
if ($setApiKey) {
    $env:OPENAI_API_KEY = $ApiKey
}

$prevCodexHome = $env:CODEX_HOME
$setCodexHome = (-not $DisableIsolatedCodexHome) -and (-not [string]::IsNullOrWhiteSpace($CodexHome))
if ($setCodexHome) {
    if (-not (Test-Path $CodexHome)) {
        New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null
    }
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

    if ($hadNativePref) {
        $PSNativeCommandUseErrorActionPreference = $prevNativePref
    }
    $ErrorActionPreference = $prevErrPref
}

($result | Out-String) | Set-Content -Path $TranscriptPath -NoNewline
exit $exitCode
