@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: EPMS Enterprise Server — Installer Build Script
:: Builds:  EPMS_Server_Core.msi
::
:: Prerequisites:
::   - .NET 8 SDK:       https://dotnet.microsoft.com/download/dotnet/8.0
::   - WiX Toolset v7:   dotnet tool install --global wix
::   - Extensions:       wix extension add -g WixToolset.Firewall.wixext
::                       wix extension add -g WixToolset.Util.wixext
::                       wix extension add -g WixToolset.UI.wixext
:: ============================================================

set VERSION=1.0.0.0
set CONFIGURATION=Release
set SOLUTION_DIR=%~dp0
set OUTPUT_DIR=%SOLUTION_DIR%dist

echo ============================================================
echo  EPMS Server Installer Build Script v%VERSION%
echo ============================================================
echo.

:: ── Prerequisites ──────────────────────────────────────────

where dotnet >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: .NET SDK not found. Install .NET 8 SDK from:
    echo   https://dotnet.microsoft.com/download/dotnet/8.0
    exit /b 1
)

where wix >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: WiX Toolset v7 not found. Install with:
    echo   dotnet tool install --global wix
    exit /b 1
)

:: ── Ensure output directory ────────────────────────────────

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

:: ── Step 1: Build custom actions (C# DTF) ─────────────────

echo.
echo [1/3] Building custom actions (C# DTF)...

dotnet build "%SOLUTION_DIR%CustomActions\EPMS.CustomActions.csproj" ^
    --configuration %CONFIGURATION% ^
    --output "%OUTPUT_DIR%\CustomActions"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Custom actions build failed.
    exit /b 1
)
echo   ✓ Custom actions built: EPMS.CustomActions.CA.dll

:: ── Step 2: Build MSI package ──────────────────────────────

echo.
echo [2/3] Building MSI package...

wix build ^
    -arch x64 ^
    -bindpath "%SOLUTION_DIR%Resources" ^
    -bindpath "%OUTPUT_DIR%\CustomActions" ^
    -loc "%SOLUTION_DIR%Resources\Strings.en-us.wxl" ^
    -ext WixToolset.Firewall.wixext ^
    -ext WixToolset.Util.wixext ^
    -ext WixToolset.UI.wixext ^
    -define "Configuration=%CONFIGURATION%" ^
    -define "ProductVersion=%VERSION%" ^
    -define "ResourcesDir=Resources" ^
    -define "ConfigDir=Config" ^
    -define "CustomActions.TargetDir=dist\CustomActions" ^
    -out "%OUTPUT_DIR%\EPMS_Server_Core.msi" ^
    Product.wxs Services.wxs Firewall.wxs Database.wxs CustomActions.wxs UI.wxs
if %ERRORLEVEL% neq 0 (
    echo ERROR: MSI build failed.
    exit /b 1
)
echo   ✓ MSI package built: EPMS_Server_Core.msi

:: ── Step 3: Sign binaries (if certificate configured) ──────

echo.
echo [3/3] Signing binaries...

if defined EPMS_SIGNING_CERT_PATH (
    signtool sign /fd SHA256 /a ^
        /f "%EPMS_SIGNING_CERT_PATH%" ^
        /p "%EPMS_SIGNING_PASSWORD%" ^
        /tr http://timestamp.digicert.com ^
        /td SHA256 ^
        "%OUTPUT_DIR%\EPMS_Server_Core.msi"
    echo   ✓ MSI signed
) else (
    echo   - Skipping (EPMS_SIGNING_CERT_PATH not set)
)

:: ── Summary ────────────────────────────────────────────────

echo.
echo ============================================================
echo  Build Complete!
echo ============================================================
echo.
echo  Output:
echo    %OUTPUT_DIR%\EPMS_Server_Core.msi
echo.
echo  Install:
echo    msiexec /i "%OUTPUT_DIR%\EPMS_Server_Core.msi"
echo.
echo  Silent install:
echo    msiexec /i "%OUTPUT_DIR%\EPMS_Server_Core.msi" /quiet
echo.
echo ============================================================

endlocal
