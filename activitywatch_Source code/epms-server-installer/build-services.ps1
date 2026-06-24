# EPMS Server Services Build Script
# Builds the consolidated epms-server executable using PyInstaller

param(
    [switch]$Clean
)

$ErrorActionPreference = "Continue"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$SPEC_DIR = Join-Path $SCRIPT_DIR "services"
$OUTPUT_DIR = Join-Path $SCRIPT_DIR "Resources"
$BUILD_DIR = Join-Path $SCRIPT_DIR "build"
$DIST_DIR = Join-Path $SCRIPT_DIR "dist"

$PYTHON = Get-Command python -ErrorAction SilentlyContinue
if (-not $PYTHON) { Write-Error "Python not found"; exit 1 }

$SPEC = "epms-server.spec"
$OUTPUT_NAME = "epms-server"
$specPath = Join-Path $SPEC_DIR $SPEC

if ($Clean) {
    Write-Output "Cleaning build artifacts..."
    Remove-Item -Recurse -Force $BUILD_DIR -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $DIST_DIR $OUTPUT_NAME) -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $OUTPUT_DIR $OUTPUT_NAME) -ErrorAction SilentlyContinue
}

if (-not (Test-Path $specPath)) { Write-Error "Spec not found: $specPath"; exit 1 }

Write-Output "Building epms-server..."
Write-Output "  Running: python -m PyInstaller --clean --noconfirm --distpath $OUTPUT_DIR `"$specPath`""
& $PYTHON -m PyInstaller --clean --noconfirm --distpath "$OUTPUT_DIR" "$specPath"

$builtExe = Join-Path $OUTPUT_DIR "$OUTPUT_NAME.exe"
if (Test-Path $builtExe) {
    Write-Output "  OK: $builtExe"
} else {
    $dirCheck = Join-Path $OUTPUT_DIR $OUTPUT_NAME
    if (Test-Path $dirCheck) {
        $actualExe = Get-ChildItem -Recurse -Filter "*.exe" -Path $dirCheck | Select-Object -First 1
        if ($actualExe) {
            Copy-Item $actualExe.FullName $builtExe -Force
            Write-Output "  OK: $builtExe (from COLLECT dir)"
        } else {
            Write-Error "  FAIL: No exe found"
        }
    } else {
        Write-Error "  FAIL: No output found"
    }
}

Write-Output "`nBuild complete. Output in: $OUTPUT_DIR\$OUTPUT_NAME"
