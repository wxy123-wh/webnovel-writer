param(
    [Parameter(Mandatory = $true)][string]$RepoRoot,
    [Parameter(Mandatory = $true)][string]$WorktreePath,
    [Parameter(Mandatory = $true)][string]$CodexBin,
    [string]$CodexSandbox = "danger-full-access",
    [Parameter(Mandatory = $true)][string]$PromptPath,
    [Parameter(Mandatory = $true)][string]$OutputLastMessagePath,
    [Parameter(Mandatory = $true)][string]$TranscriptPath,
    [string]$Model = "",
    [string]$ApiBaseUrl = "",
    [string]$ApiKey = "",
    [string]$CodexHome = "",
    [switch]$DisableIsolatedCodexHome,
    [int]$TimeoutMinutes = 30
)

$ErrorActionPreference = "Stop"

function Resolve-Abs {
    param([string]$PathValue)
    return [System.IO.Path]::GetFullPath($PathValue)
}

# NOTE: $CodexBin must NOT be converted to an absolute path when it is a bare
# command name (e.g. "codex"), because GetFullPath would turn it into
# "<cwd>\codex" which does not exist.  Only resolve it when it looks like an
# explicit path (contains a path separator or drive letter).
function Resolve-CodexBin {
    param([string]$Bin)
    $isExplicitPath = ($Bin.Contains("\") -or $Bin.Contains("/") -or $Bin.Contains(":"))
    if ($isExplicitPath) {
        return [System.IO.Path]::GetFullPath($Bin)
    }
    # Bare command name: look it up on PATH so we get the real .exe/.cmd path
    $cmd = Get-Command $Bin -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $cmd) {
        if (-not [string]::IsNullOrWhiteSpace($cmd.Path))    { return $cmd.Path }
        if (-not [string]::IsNullOrWhiteSpace($cmd.Definition)) { return $cmd.Definition }
    }
    # Fall back to the bare name and let the OS resolve it at launch time
    return $Bin
}

$RepoRoot     = Resolve-Abs $RepoRoot
$WorktreePath = Resolve-Abs $WorktreePath
$PromptPath   = Resolve-Abs $PromptPath
$CodexBin     = Resolve-CodexBin $CodexBin

$outputDir = Split-Path -Parent $OutputLastMessagePath
if (-not [string]::IsNullOrWhiteSpace($outputDir) -and (-not (Test-Path $outputDir))) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}
$transcriptDir = Split-Path -Parent $TranscriptPath
if (-not [string]::IsNullOrWhiteSpace($transcriptDir) -and (-not (Test-Path $transcriptDir))) {
    New-Item -ItemType Directory -Path $transcriptDir -Force | Out-Null
}

$prompt = Get-Content -Path $PromptPath -Raw

# Build argument list
$argParts = [System.Collections.Generic.List[string]]::new()
$argParts.Add("exec")
$argParts.Add("--ephemeral")
$argParts.Add("-s"); $argParts.Add($CodexSandbox)
$argParts.Add("-C"); $argParts.Add($WorktreePath)
$argParts.Add("--output-last-message"); $argParts.Add($OutputLastMessagePath)

if ($DisableIsolatedCodexHome -and (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl))) {
    $argParts.Add("-c"); $argParts.Add('model_provider="codex"')
    $argParts.Add("-c"); $argParts.Add(("model_providers.codex.base_url=`"{0}`"" -f $ApiBaseUrl))
}
if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $argParts.Add("-m"); $argParts.Add($Model)
}
$argParts.Add("-")

function EscapeOneArg([string]$a) {
    if ($a -eq '') { return '""' }
    if ($a -notmatch '[\s"\\]') { return $a }
    $sb = [System.Text.StringBuilder]::new()
    $null = $sb.Append('"')
    $bs = 0
    foreach ($ch in $a.ToCharArray()) {
        if ($ch -eq '\') { $bs++ }
        elseif ($ch -eq '"') {
            $null = $sb.Append('\' * ($bs * 2 + 1))
            $null = $sb.Append('"')
            $bs = 0
        } else {
            if ($bs -gt 0) { $null = $sb.Append('\' * $bs); $bs = 0 }
            $null = $sb.Append($ch)
        }
    }
    if ($bs -gt 0) { $null = $sb.Append('\' * ($bs * 2)) }
    $null = $sb.Append('"')
    return $sb.ToString()
}
$escapedArgs = ($argParts | ForEach-Object { EscapeOneArg $_ }) -join ' '

# Set environment variables
$envBackup = @{}
if (-not [string]::IsNullOrWhiteSpace($ApiBaseUrl)) {
    $envBackup['OPENAI_BASE_URL'] = [System.Environment]::GetEnvironmentVariable('OPENAI_BASE_URL')
    [System.Environment]::SetEnvironmentVariable('OPENAI_BASE_URL', $ApiBaseUrl)
}
if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $envBackup['OPENAI_API_KEY'] = [System.Environment]::GetEnvironmentVariable('OPENAI_API_KEY')
    [System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $ApiKey)
}
if ((-not $DisableIsolatedCodexHome) -and (-not [string]::IsNullOrWhiteSpace($CodexHome))) {
    if (-not (Test-Path $CodexHome)) { New-Item -ItemType Directory -Path $CodexHome -Force | Out-Null }
    $envBackup['CODEX_HOME'] = [System.Environment]::GetEnvironmentVariable('CODEX_HOME')
    [System.Environment]::SetEnvironmentVariable('CODEX_HOME', $CodexHome)
}

$exitCode = 1
try {
    $psi = [System.Diagnostics.ProcessStartInfo]::new($CodexBin, $escapedArgs)
    $psi.UseShellExecute        = $false
    $psi.RedirectStandardInput  = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.CreateNoWindow         = $true
    $psi.WorkingDirectory       = $WorktreePath

    $proc = [System.Diagnostics.Process]::new()
    $proc.StartInfo = $psi
    $null = $proc.Start()

    # Write prompt to stdin and close it
    $proc.StandardInput.Write($prompt)
    $proc.StandardInput.Close()

    # Stream stdout and stderr to transcript file concurrently
    $transcriptPathLocal = $TranscriptPath
    $stdoutDone = [System.Threading.ManualResetEventSlim]::new($false)
    $stderrDone = [System.Threading.ManualResetEventSlim]::new($false)

    $stdoutReader = $proc.StandardOutput
    $stdoutThread = [System.Threading.Thread]::new([System.Threading.ThreadStart]{
        try {
            $buf = [char[]]::new(4096)
            $writer = [System.IO.StreamWriter]::new(
                $transcriptPathLocal,
                $true,
                [System.Text.Encoding]::UTF8
            )
            $writer.AutoFlush = $true
            try {
                while ($true) {
                    $read = $stdoutReader.Read($buf, 0, $buf.Length)
                    if ($read -le 0) { break }
                    $writer.Write($buf, 0, $read)
                }
            } finally {
                $writer.Dispose()
            }
        } catch { }
        $stdoutDone.Set()
    })
    $stdoutThread.IsBackground = $true
    $stdoutThread.Start()

    $stderrReader = $proc.StandardError
    $stderrThread = [System.Threading.Thread]::new([System.Threading.ThreadStart]{
        try {
            $buf2 = [char[]]::new(4096)
            $writer2 = [System.IO.StreamWriter]::new(
                $transcriptPathLocal,
                $true,
                [System.Text.Encoding]::UTF8
            )
            $writer2.AutoFlush = $true
            try {
                while ($true) {
                    $read2 = $stderrReader.Read($buf2, 0, $buf2.Length)
                    if ($read2 -le 0) { break }
                    $writer2.Write($buf2, 0, $read2)
                }
            } finally {
                $writer2.Dispose()
            }
        } catch { }
        $stderrDone.Set()
    })
    $stderrThread.IsBackground = $true
    $stderrThread.Start()

    # Wait with timeout
    $timeoutMs = $TimeoutMinutes * 60 * 1000
    $finished = $proc.WaitForExit($timeoutMs)
    if (-not $finished) {
        Write-Host "[run-codex-stage] Timeout after $TimeoutMinutes min — killing process" -ForegroundColor Yellow
        try { $proc.Kill($true) } catch { try { $proc.Kill() } catch { } }
        $proc.WaitForExit(5000) | Out-Null
        $exitCode = 124   # POSIX timeout convention
    } else {
        $exitCode = $proc.ExitCode
    }

    $stdoutDone.Wait(5000) | Out-Null
    $stderrDone.Wait(5000) | Out-Null

} finally {
    foreach ($key in $envBackup.Keys) {
        $val = $envBackup[$key]
        [System.Environment]::SetEnvironmentVariable($key, $val)
    }
    if ($null -ne $proc) { $proc.Dispose() }
}

exit $exitCode
