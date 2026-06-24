@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM EPMS Enterprise Build Script — Agent Client only (consolidated server built via build-services.ps1)
REM Creates standalone executable for the Agent Client using httpx REST transport.
REM
REM Usage:
REM   build-exe.bat              - Build agent executable
REM   build-exe.bat agent        - Build agent executable
REM ============================================================================

SET SCRIPT_DIR=%~dp0
SET PROJECT_DIR=%SCRIPT_DIR%..
SET SOURCE_DIR=D:\activitywatch\activitywatch_Source code\epms-agent-client
SET BUILD_DIR=%PROJECT_DIR%\build
SET DIST_DIR=%PROJECT_DIR%\dist

echo ============================================================================
echo  EPMS Enterprise Build — Agent Client executable
echo ============================================================================
echo.
for %%I in ("%SOURCE_DIR%") do set SHORT_SOURCE_DIR=%%~sI
echo  Source:  %SOURCE_DIR%
echo  Short:   %SHORT_SOURCE_DIR%
echo  Build:   %BUILD_DIR%
echo  Output:  %DIST_DIR%
echo.

REM ── Ensure source is installed ────────────────────────────────────────
python -m pip install -e "%SOURCE_DIR%" >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install epms packages
    pause
    exit /b 1
)

REM ── Build Agent Client ───────────────────────────────────────────────
echo [1/1] Building Agent Client executable...

IF NOT EXIST "%BUILD_DIR%" mkdir "%BUILD_DIR%"

python -m PyInstaller ^
    --onefile ^
    --name "epms-agent-client" ^
    --path "%SOURCE_DIR%" ^
    --distpath "%DIST_DIR%" ^
    --workpath "%BUILD_DIR%\agent" ^
    --specpath "%BUILD_DIR%" ^
    --add-data "%SHORT_SOURCE_DIR%\epms_agent;epms_agent" ^
    --hidden-import epms_agent ^
    --hidden-import epms_agent.config ^
    --hidden-import epms_agent.api_client ^
    --hidden-import epms_agent.rest_client ^
    --hidden-import epms_agent.monitor ^
    --hidden-import epms_agent.event_buffer ^
    --hidden-import httpx ^
    --hidden-import psutil ^
    --hidden-import requests ^
    --hidden-import json ^
    --clean ^
    --noconfirm ^
    "%SHORT_SOURCE_DIR%\epms_agent\__main__.py"

IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Agent build failed
    pause
    exit /b 1
)
echo [DONE] Agent Client executable created

:END
echo.
echo ============================================================================
echo  Build Complete
echo ============================================================================
echo.
echo  Standalone executable:
echo    %DIST_DIR%\epms-agent-client.exe
echo.
echo  Run without Python installed:
echo    %DIST_DIR%\epms-agent-client.exe --config config\agent.json
echo.
echo  Requires: config\agent.json
echo.

pause
