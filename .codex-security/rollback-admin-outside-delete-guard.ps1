param(
    [string]$BackupDir = 'D:\code\webnovel-writer\.codex-security\admin-acl-backups-outside-delete',
    [string]$Stamp,
    [switch]$UseLatest
)

$ErrorActionPreference = 'Stop'

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script as Administrator.'
}

if (-not (Test-Path $BackupDir)) {
    throw "Backup directory not found: $BackupDir"
}

if ($UseLatest -or [string]::IsNullOrWhiteSpace($Stamp)) {
    $latestManifest = Get-ChildItem $BackupDir -Filter 'targets-*.txt' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latestManifest) {
        throw "No manifest found in $BackupDir"
    }
    $Stamp = ($latestManifest.BaseName -replace '^targets-','')
}

$aclFiles = Get-ChildItem $BackupDir -Filter "acl-$Stamp-*.txt"
if (-not $aclFiles) {
    throw "No ACL backup files found for stamp $Stamp in $BackupDir"
}

foreach ($f in $aclFiles) {
    icacls 'C:\' /restore $f.FullName | Out-Null
    icacls 'D:\' /restore $f.FullName | Out-Null
}

Write-Output "RESTORED outside-delete ACLs for stamp: $Stamp"
