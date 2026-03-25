param(
    [ValidateSet("smoke", "full")]
    [string]$Mode = "smoke",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

Set-Location $ProjectRoot

$tmpRoot = Join-Path $ProjectRoot ".tmp\\pytest"
New-Item -ItemType Directory -Path $tmpRoot -Force | Out-Null

$ScriptsDir = (Resolve-Path $PSScriptRoot).Path
$TestsDir = Join-Path $ScriptsDir "data_modules\\tests"
$BootstrapDir = Join-Path $ScriptsDir "test_bootstrap"

$env:TMP = $tmpRoot
$env:TEMP = $tmpRoot
$env:WEBNOVEL_TMPDIR_FIX = "1"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
$env:PYTHONPATH = "$BootstrapDir;$ScriptsDir"

# 避免 Windows 下 basetemp 目录因权限/残留锁导致 rm_rf 失败（会让所有用例在 setup 阶段直接报错）。
$runId = Get-Date -Format "yyyyMMdd_HHmmssfff"
$baseTemp = Join-Path $tmpRoot ("run-" + $Mode + "-" + $runId)

Write-Host "ProjectRoot: $ProjectRoot"
Write-Host "ScriptsDir: $ScriptsDir"
Write-Host "TestsDir: $TestsDir"
Write-Host "BootstrapDir: $BootstrapDir"
Write-Host "TMP/TEMP: $tmpRoot"
Write-Host "Mode: $Mode"

# 预检：某些 Windows Python 发行版（尤其 WindowsApps shim）在 tempfile.mkdtemp 时会创建“不可访问目录”，
# 会导致 pytest 在创建/清理临时目录阶段直接 WinError 5。
@'
import tempfile
from pathlib import Path
import sys

try:
    d = Path(tempfile.mkdtemp(prefix="webnovel_writer_pytest_"))
    # 既要能列目录，也要能写文件；否则 pytest 必挂。
    list(d.iterdir())
    (d / "probe.txt").write_text("ok", encoding="utf-8")
except Exception as exc:
    print(f"PYTEST_TMPDIR_PRECHECK_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
    raise
'@ | python - 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "❌ Python 临时目录预检失败（常见原因：WindowsApps 的 python.exe shim / 权限异常）"
    Write-Host "建议：改用标准 Python（python.org 安装版）或用 uv/uvx 提供的 Python 运行测试。"
    exit 1
}

if ($Mode -eq "smoke") {
    python -m pytest -q `
        (Join-Path $TestsDir "test_extract_chapter_context.py") `
        (Join-Path $TestsDir "test_rag_adapter.py") `
        -p pytest_asyncio.plugin `
        -o addopts= `
        --basetemp $baseTemp `
        -p no:cacheprovider
    exit $LASTEXITCODE
}

python -m pytest -q `
    $TestsDir `
    -p pytest_asyncio.plugin `
    -o addopts= `
    --basetemp $baseTemp `
    -p no:cacheprovider
exit $LASTEXITCODE
