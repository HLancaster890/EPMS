@echo off
title EPMS Consolidated Server
cd /d "%~dp0"

echo ============================================
echo   EPMS Enterprise — Consolidated Server
echo ============================================
echo.

:: Kill any existing epms python processes
taskkill /f /im python.exe /fi "WindowTitle eq epms*" 2>nul >nul

:: 1. Consolidated Server (port 8000) — API, Analytics, Reports, Notifications, Gateway
echo [1/2] Starting Consolidated Server...
start "epms-server" cmd /c "set EPMS_DEV_MODE=1 && set EPMS_SERVER_PORT=8000 && cd /d activitywatch_Source code\epms-server-installer && python Resources/services/epms_server_service.py"

timeout /t 5 /nobreak >nul

:: 2. EPMS Agent Client
echo [2/2] Starting Agent...
start "epms-agent" cmd /c "cd /d activitywatch_Source code\epms-agent-client && python -m epms_agent --no-tray --verbose"

echo.
echo ============================================
echo   Services started.
echo   Server:    http://localhost:8000
echo   Dashboard: http://localhost:8000/dashboard/
echo ============================================
echo.
echo   Press any key to open the dashboard...
pause >nul
start http://localhost:8000/dashboard/
