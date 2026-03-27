param(
    [string]$RepoRoot,
    [string]$ProjectRoot,
    [string]$WorkspaceRoot,
    [switch]$IncludeDev,
    [switch]$SkipInstall,
    [switch]$SkipFrontend,
    [switch]$RunSmoke,
    [switch]$StartDashboard,
    [string]$DashboardHost = "127.0.0.1",
    [int]$DashboardPort = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Command-Exists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-AbsolutePath {
    param([string]$PathValue)
    return (Resolve-Path -Path $PathValue).Path
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $scriptDir
}
$RepoRoot = Resolve-AbsolutePath $RepoRoot
Set-Location $RepoRoot
Write-Step "Repository root: $RepoRoot"

$appRoot = Join-Path $RepoRoot "webnovel-writer"
$cliPath = Join-Path $appRoot "scripts/webnovel.py"
if (-not (Test-Path $appRoot)) {
    throw "Missing app root: $appRoot"
}
if (-not (Test-Path $cliPath)) {
    throw "Missing CLI entrypoint: $cliPath"
}

$pythonLauncher = $null
$pythonPrefixArgs = @()
if (Command-Exists "python") {
    $pythonLauncher = "python"
} elseif (Command-Exists "py") {
    $pythonLauncher = "py"
    $pythonPrefixArgs = @("-3")
} else {
    throw "Python is not available in PATH (python or py)."
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & $pythonLauncher @pythonPrefixArgs @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $pythonLauncher $($pythonPrefixArgs + $Args -join ' ')"
    }
}

if (-not $SkipInstall) {
    Write-Step "Installing Python dependencies"
    $requirements = @(
        (Join-Path $appRoot "dashboard/requirements.txt"),
        (Join-Path $appRoot "scripts/requirements.txt")
    )
    if ($IncludeDev) {
        $requirements += (Join-Path $appRoot "dashboard/requirements-dev.txt")
        $requirements += (Join-Path $appRoot "scripts/requirements-dev.txt")
    }
    foreach ($req in $requirements) {
        if (-not (Test-Path $req)) {
            throw "Missing requirements file: $req"
        }
        Write-Step "pip install -r $req"
        Invoke-Python -m pip install -r $req
    }

    if (-not $SkipFrontend) {
        $frontendRoot = Join-Path $appRoot "dashboard/frontend"
        $frontendPkg = Join-Path $frontendRoot "package.json"
        if (Test-Path $frontendPkg) {
            Push-Location $frontendRoot
            try {
                Write-Step "Installing frontend dependencies in $frontendRoot"
                if ((Test-Path "pnpm-lock.yaml") -and (Command-Exists "pnpm")) {
                    pnpm install
                } elseif ((Test-Path "yarn.lock") -and (Command-Exists "yarn")) {
                    yarn install
                } elseif (Command-Exists "npm") {
                    npm install
                } else {
                    Write-Step "No frontend package manager found; skip frontend install."
                }
                if ($LASTEXITCODE -ne 0) {
                    throw "Frontend dependency install failed."
                }
            } finally {
                Pop-Location
            }
        } else {
            Write-Step "No frontend package.json found; skip frontend install."
        }
    } else {
        Write-Step "Skip frontend dependency installation (--SkipFrontend)."
    }
}

$resolvedProjectRoot = $null
if (-not [string]::IsNullOrWhiteSpace($ProjectRoot)) {
    if (-not (Test-Path $ProjectRoot)) {
        throw "ProjectRoot does not exist: $ProjectRoot"
    }
    $resolvedProjectRoot = Resolve-AbsolutePath $ProjectRoot
}

$resolvedWorkspaceRoot = $null
if (-not [string]::IsNullOrWhiteSpace($WorkspaceRoot)) {
    $resolvedWorkspaceRoot = Resolve-AbsolutePath $WorkspaceRoot
} elseif ($resolvedProjectRoot) {
    $resolvedWorkspaceRoot = $resolvedProjectRoot
} else {
    $resolvedWorkspaceRoot = $RepoRoot
}

if ($resolvedProjectRoot) {
    $workspaceCodexDir = Join-Path $resolvedWorkspaceRoot ".codex"
    if (-not (Test-Path $workspaceCodexDir)) {
        Write-Step "Creating workspace codex context dir: $workspaceCodexDir"
        New-Item -ItemType Directory -Path $workspaceCodexDir -Force | Out-Null
    }

    Write-Step "Binding workspace pointer to project"
    Invoke-Python -X utf8 $cliPath use $resolvedProjectRoot --workspace-root $resolvedWorkspaceRoot
}

if ($RunSmoke) {
    Write-Step "Running smoke checks"
    Invoke-Python -X utf8 $cliPath --help
    if ($resolvedProjectRoot) {
        Invoke-Python -X utf8 $cliPath --project-root $resolvedProjectRoot preflight --format json
    } else {
        Write-Step "ProjectRoot not set; skip project preflight smoke."
    }
}

Write-Step "Initialization complete"
Write-Host "Next steps:" -ForegroundColor Green
Write-Host '  1) Create project: python -X utf8 webnovel-writer/scripts/webnovel.py init ./webnovel-project "My Book" "Genre"' -ForegroundColor Green
Write-Host "  2) Bootstrap + smoke: powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot ./webnovel-project -RunSmoke" -ForegroundColor Green
Write-Host "  3) Follow workflow: running/workflow.md" -ForegroundColor Green
Write-Host "  4) Optional server: powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot ./webnovel-project -StartDashboard -NoBrowser" -ForegroundColor Green

if ($StartDashboard) {
    if (-not $resolvedProjectRoot) {
        throw "-StartDashboard requires -ProjectRoot"
    }
    Write-Step "Starting dashboard server"
    Write-Host (("Dashboard URL: http://{0}:{1}" -f $DashboardHost, $DashboardPort)) -ForegroundColor Green
    $dashboardArgs = @(
        "-m", "dashboard.server",
        "--project-root", $resolvedProjectRoot,
        "--host", $DashboardHost,
        "--port", $DashboardPort
    )
    if ($NoBrowser) {
        $dashboardArgs += "--no-browser"
    }

    Push-Location $appRoot
    try {
        Invoke-Python @dashboardArgs
    } finally {
        Pop-Location
    }
}
