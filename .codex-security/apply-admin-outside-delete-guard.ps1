param(
    [string]$WorkspaceRoot = 'D:\code\webnovel-writer',
    [string]$SandboxGroup = 'WH\CodexSandboxUsers'
)

$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script as Administrator.'
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupDir = Join-Path $scriptDir 'admin-acl-backups-outside-delete'
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

$targets = @()
$targets += Get-ChildItem 'D:\code' -Directory -Force | Where-Object { $_.FullName -ne $WorkspaceRoot } | Select-Object -ExpandProperty FullName
$homeCandidates = @('Desktop','Documents','Downloads','Pictures','Music','Videos','OneDrive','source') | ForEach-Object { Join-Path 'C:\Users\wxy' $_ }
$targets += $homeCandidates | Where-Object { Test-Path $_ }
$targets = $targets | Sort-Object -Unique

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$manifest = Join-Path $backupDir "targets-$stamp.txt"
$targets | Set-Content -Path $manifest -Encoding UTF8

foreach ($t in $targets) {
    $safe = ($t -replace '[:\\ ]','_')
    $aclFile = Join-Path $backupDir "acl-$stamp-$safe.txt"
    icacls $t /save $aclFile /t /c /q | Out-Null
    icacls $t /deny "${SandboxGroup}:(OI)(CI)(D,DC)" /t /c /q | Out-Null
}

Write-Output "APPLIED outside-delete guard for $SandboxGroup"
Write-Output "TARGET_COUNT: $($targets.Count)"
Write-Output "MANIFEST: $manifest"
Write-Output "BACKUP_DIR: $backupDir"
