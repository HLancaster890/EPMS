@echo off
title EPMS Launcher
cd /d "%~dp0"

echo ============================================
echo   EPMS Enterprise — Starting Services
echo ============================================
echo.

:: Kill any existing epms python processes
taskkill /f /im python.exe /fi "WindowTitle eq epms*" 2>nul >nul

:: 1. API Service (port 8000) — REST API + Dashboard
echo [1/3] Starting API Service...
start "epms-api" cmd /c "set EPMS_DEV_MODE=1 && cd /d activitywatch_Source code\epms-server-installer && python Resources/services/epms_api_service.py"

timeout /t 3 /nobreak >nul

:: 2. Analytics Service (port 8001) — Live scoring + analytics
echo [2/3] Starting Analytics Service...
start "epms-analytics" cmd /c "cd /d activitywatch_Source code\epms-server-installer && python Resources/services/epms_analytics_service.py"

timeout /t 3 /nobreak >nul

:: 3. EPMS Agent Client
echo [3/3] Starting Agent...
start "epms-agent" cmd /c "cd /d activitywatch_Source code\epms-agent-client && python -m epms_agent --no-tray --verbose"

echo.
echo ============================================
echo   All services started.
echo   API:       http://localhost:8000
echo   Dashboard: http://localhost:8000/dashboard/
echo   Analytics: http://localhost:8001
echo   Agent:     Running in console mode
echo ============================================
echo.
echo   Press any key to open the dashboard in your browser...
pause >nul
start http://localhost:8000/dashboard/
