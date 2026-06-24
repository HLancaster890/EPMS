@echo off
setlocal enabledelayedexpansion

SET SCRIPT_DIR=%~dp0
SET CONFIG_FILE=%SCRIPT_DIR%..\config\agent.json
SET LOG_DIR=%SCRIPT_DIR%..\logs

IF NOT EXIST "%LOG_DIR%" mkdir "%LOG_DIR%"

echo ============================================================================
echo  EPMS Agent Client v1.0.0
echo  Connecting to gateway at 127.0.0.1:8005
echo  Monitor mode: continuous heartbeats + productivity tracking
echo ============================================================================

python -m epms_agent --config "%CONFIG_FILE%" --verbose --no-tray

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Agent client exited with code %ERRORLEVEL%
    pause
)
