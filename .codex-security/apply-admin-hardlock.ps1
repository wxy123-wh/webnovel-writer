param(
    [string]$SandboxGroup = 'WH\CodexSandboxUsers'
)

$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script as Administrator.'
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backupDir = Join-Path $scriptDir 'admin-acl-backups'
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

$target = 'C:\Windows\System32\cmd.exe'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupFile = Join-Path $backupDir "cmd-acl-$stamp.txt"

icacls $target /save $backupFile /q | Out-Null
icacls $target /deny "${SandboxGroup}:(RX)" | Out-Null

Write-Output "APPLIED: deny execute on $target for $SandboxGroup"
Write-Output "BACKUP: $backupFile"
