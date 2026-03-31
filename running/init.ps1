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
    [switch]$NoBrowser,
    [switch]$NoBootstrapIndex,
    [string[]]$CorsOrigin,
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO",
    [switch]$LogJson,
    [string]$BasicAuth
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

function Assert-CommandExists {
    param(
        [string]$Name,
        [string]$InstallHint
    )
    if (-not (Command-Exists $Name)) {
        throw "$Name is required but was not found in PATH. $InstallHint"
    }
}

function Get-FrontendPackageManager {
    param([string]$FrontendRoot)

    if ((Test-Path (Join-Path $FrontendRoot "pnpm-lock.yaml")) -and (Command-Exists "pnpm")) {
        return "pnpm"
    }
    if ((Test-Path (Join-Path $FrontendRoot "yarn.lock")) -and (Command-Exists "yarn")) {
        return "yarn"
    }
    if (Command-Exists "npm") {
        return "npm"
    }
    if (Command-Exists "pnpm") {
        return "pnpm"
    }
    if (Command-Exists "yarn") {
        return "yarn"
    }
    return $null
}

function Invoke-FrontendPackageManager {
    param(
        [string]$FrontendRoot,
        [string]$PackageManager,
        [string[]]$Arguments
    )

    Push-Location $FrontendRoot
    try {
        & $PackageManager @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend command failed: $PackageManager $($Arguments -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

function Test-FrontendBuildReady {
    param([string]$FrontendRoot)
    $distIndex = Join-Path $FrontendRoot "dist/index.html"
    return (Test-Path $distIndex)
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
Assert-CommandExists -Name $pythonLauncher -InstallHint "Install Python 3.10+ and ensure `python` or `py` is available."

$frontendRoot = Join-Path $appRoot "dashboard/frontend"
$frontendPkg = Join-Path $frontendRoot "package.json"
$frontendPackageManager = $null
if (Test-Path $frontendPkg) {
    $frontendPackageManager = Get-FrontendPackageManager -FrontendRoot $frontendRoot
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
        if (Test-Path $frontendPkg) {
            if (-not $frontendPackageManager) {
                throw "Frontend package.json exists but no package manager was found in PATH. Install npm, pnpm, or yarn."
            }
            Write-Step "Installing frontend dependencies via $frontendPackageManager"
            Invoke-FrontendPackageManager -FrontendRoot $frontendRoot -PackageManager $frontendPackageManager -Arguments @("install")

            Write-Step "Building frontend via $frontendPackageManager"
            if ($frontendPackageManager -eq "yarn") {
                Invoke-FrontendPackageManager -FrontendRoot $frontendRoot -PackageManager $frontendPackageManager -Arguments @("build")
            } else {
                Invoke-FrontendPackageManager -FrontendRoot $frontendRoot -PackageManager $frontendPackageManager -Arguments @("run", "build")
            }
        } else {
            Write-Step "No frontend package.json found; skip frontend install/build."
        }
    } else {
        Write-Step "Skip frontend dependency installation/build (--SkipFrontend)."
    }
}

if ((-not $SkipFrontend) -and (Test-Path $frontendPkg) -and (-not (Test-FrontendBuildReady -FrontendRoot $frontendRoot))) {
    if (-not $frontendPackageManager) {
        throw "Frontend assets are missing and no package manager is available to build them."
    }
    Write-Step "Frontend assets missing; running build via $frontendPackageManager"
    if ($frontendPackageManager -eq "yarn") {
        Invoke-FrontendPackageManager -FrontendRoot $frontendRoot -PackageManager $frontendPackageManager -Arguments @("build")
    } else {
        Invoke-FrontendPackageManager -FrontendRoot $frontendRoot -PackageManager $frontendPackageManager -Arguments @("run", "build")
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
Write-Host "  4) Start app: powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot ./webnovel-project -StartDashboard -NoBrowser" -ForegroundColor Green

if ($StartDashboard) {
    if (-not $resolvedProjectRoot) {
        throw "-StartDashboard requires -ProjectRoot"
    }
    if (-not (Test-FrontendBuildReady -FrontendRoot $frontendRoot)) {
        throw "Frontend assets are still missing after bootstrap. Re-run without -SkipFrontend or build the dashboard frontend before starting."
    }
    Write-Step "Starting dashboard via unified CLI"
    Write-Host (("Dashboard URL: http://{0}:{1}" -f $DashboardHost, $DashboardPort)) -ForegroundColor Green
    $dashboardArgs = @(
        "-X", "utf8",
        $cliPath,
        "dashboard",
        "--project-root", $resolvedProjectRoot,
        "--host", $DashboardHost,
        "--port", $DashboardPort
    )
    if ($NoBrowser) {
        $dashboardArgs += "--no-browser"
    }
    if ($NoBootstrapIndex) {
        $dashboardArgs += "--no-bootstrap-index"
    }
    foreach ($origin in ($CorsOrigin | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
        $dashboardArgs += "--cors-origin"
        $dashboardArgs += $origin
    }
    if (-not [string]::IsNullOrWhiteSpace($LogLevel)) {
        $dashboardArgs += "--log-level"
        $dashboardArgs += $LogLevel
    }
    if ($LogJson) {
        $dashboardArgs += "--log-json"
    }
    if (-not [string]::IsNullOrWhiteSpace($BasicAuth)) {
        $dashboardArgs += "--basic-auth"
        $dashboardArgs += $BasicAuth
    }

    Invoke-Python @dashboardArgs
}
