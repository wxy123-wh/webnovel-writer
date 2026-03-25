param(
    [string]$BackupFile,
    [switch]$UseLatest
)

$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script as Administrator.'
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupDir = Join-Path $scriptDir 'admin-acl-backups'

if ($UseLatest -or [string]::IsNullOrWhiteSpace($BackupFile)) {
    $latest = Get-ChildItem -Path $backupDir -Filter 'cmd-acl-*.txt' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) {
        throw "No backup file found in $backupDir"
    }
    $BackupFile = $latest.FullName
}

if (-not (Test-Path $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

icacls 'C:\' /restore $BackupFile | Out-Null
Write-Output "RESTORED ACLs from $BackupFile"
