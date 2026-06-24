# EPMS Enterprise - Full Release Build Script
# Builds all components and generates RELEASE artifacts

param(
    [switch]$SkipServices,
    [switch]$SkipClient,
    [switch]$Help
)

if ($Help) {
    Write-Output @"
EPMS Enterprise - Full Release Build Script

Usage: .\build-release.ps1 [options]

Options:
  -SkipServices     Skip building server service executable
  -SkipClient       Skip building client executables
  -Help             Show this help

Output: D:\activitywatch\RELEASE\
"@
    exit 0
}

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$SRC = Join-Path $ROOT "activitywatch_Source code"
$RELEASE = Join-Path $ROOT "RELEASE"
$EPMS_CLIENT = Join-Path $SRC "epms-agent-client"
$EPMS_SERVER = Join-Path $SRC "epms-server-installer"
$PYTHON = Get-Command python -ErrorAction SilentlyContinue
if (-not $PYTHON) { Write-Error "Python not found"; exit 1 }

Write-Output "============================================================"
Write-Output " EPMS Enterprise - Full Release Build"
Write-Output "============================================================"

# --- 1. Install dependencies ---
Write-Output "`n[1/5] Installing dependencies..."
if (Test-Path (Join-Path $EPMS_CLIENT "pyproject.toml")) {
    Push-Location $EPMS_CLIENT
    & python -m pip install -e ".[test,dev]"
    Pop-Location
}

# --- 2. Build Client executable ---
if (-not $SkipClient) {
    Write-Output "`n[2/5] Building Client executable..."
    $buildExe = Join-Path $ROOT "realease\bin\build-exe.bat"
    if (Test-Path $buildExe) {
        & $buildExe
    } else {
        Write-Output "  Building agent via PyInstaller..."
        & python -m PyInstaller --onefile --name "epms-agent-client" --distpath "$RELEASE\CLIENT" --workpath "$SRC\build\agent" --specpath "$SRC\build" --add-data "$EPMS_CLIENT\epms_agent;epms_agent" --hidden-import epms_agent --hidden-import epms_agent.config --hidden-import epms_agent.api_client --hidden-import epms_agent.rest_client --hidden-import epms_agent.monitor --hidden-import epms_agent.event_buffer --hidden-import httpx --hidden-import psutil --hidden-import requests --hidden-import json --clean --noconfirm "$EPMS_CLIENT\epms_agent\__main__.py"
    }
}

# --- 3. Build Server service executable ---
if (-not $SkipServices) {
    Write-Output "`n[3/5] Building Server service executable..."
    $buildScript = Join-Path $EPMS_SERVER "build-services.ps1"
    & powershell -ExecutionPolicy Bypass -File $buildScript
}

# --- 4. Assemble RELEASE directory ---
Write-Output "`n[4/5] Assembling RELEASE directory..."
New-Item -ItemType Directory -Force -Path "$RELEASE\SERVER" | Out-Null
New-Item -ItemType Directory -Force -Path "$RELEASE\CLIENT" | Out-Null
New-Item -ItemType Directory -Force -Path "$RELEASE\TEST_REPORTS" | Out-Null
New-Item -ItemType Directory -Force -Path "$RELEASE\DOCUMENTATION" | Out-Null
New-Item -ItemType Directory -Force -Path "$RELEASE\INSTALLERS" | Out-Null

# Copy consolidated server executable
$svcExe = Join-Path $EPMS_SERVER "dist\epms-server\epms-server.exe"
if (Test-Path $svcExe) { Copy-Item $svcExe "$RELEASE\SERVER\epms-server.exe" -Force }

# Copy client executable
$clientExe = Join-Path $EPMS_SERVER "dist\epms-agent-client\epms-agent-client.exe"
if (-not (Test-Path $clientExe)) {
    $clientExe = Join-Path $ROOT "realease\dist\epms-agent-client\epms-agent-client.exe"
}
if (Test-Path $clientExe) { Copy-Item $clientExe "$RELEASE\CLIENT\EPMS_Agent.exe" -Force }

# Copy config files
Copy-Item (Join-Path $EPMS_SERVER "Config\appsettings.json.template") "$RELEASE\SERVER\appsettings.json.template" -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $EPMS_SERVER "Config\logging.yaml.template") "$RELEASE\SERVER\logging.yaml.template" -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $ROOT "realease\config\agent.json") "$RELEASE\CLIENT\agent.json" -Force -ErrorAction SilentlyContinue

# Copy installer scripts
$installerDir = Join-Path $SRC "epms-server-installer\RELEASE\INSTALLERS"
if (Test-Path $installerDir) {
    Copy-Item "$installerDir\*" "$RELEASE\INSTALLERS\" -Recurse -Force -ErrorAction SilentlyContinue
}

# Copy documentation
$docs = @("EPMS_Installation_Guide.md", "MULTINODE_SETUP.md", "AGENTS.md", "ADMINISTRATOR_GUIDE.md", "DEPLOYMENT_GUIDE.md", "RELEASE_NOTES.md")
foreach ($doc in $docs) {
    $srcDoc = Join-Path $SRC $doc
    if (Test-Path $srcDoc) { Copy-Item $srcDoc "$RELEASE\DOCUMENTATION\" -Force }
    else {
        $altDoc = Join-Path $ROOT $doc
        if (Test-Path $altDoc) { Copy-Item $altDoc "$RELEASE\DOCUMENTATION\" -Force }
    }
}

# Copy SQL migrations
$sqlDir = Join-Path $EPMS_SERVER "Config\sql"
if (Test-Path $sqlDir) {
    Copy-Item "$sqlDir\*" "$RELEASE\SERVER\sql\" -Force -ErrorAction SilentlyContinue
}

# --- 5. Run tests ---
Write-Output "`n[5/5] Running tests..."
$testReport = "$RELEASE\TEST_REPORTS\test_results.xml"
Push-Location $EPMS_CLIENT
try {
    & python -m pytest tests/test_rest_client.py tests/test_api_client.py tests/test_event_buffer.py -v --junitxml="$testReport"
} catch {
    Write-Output "  Tests encountered errors (see report)"
}
Pop-Location

Write-Output "`n============================================================"
Write-Output " Release build complete!"
Write-Output "============================================================"
Write-Output "`nRELEASE directory:"
Get-ChildItem -Recurse -Depth 2 $RELEASE | Where-Object { -not $_.PSIsContainer } | ForEach-Object { "  $($_.FullName.Replace($ROOT,''))" }
