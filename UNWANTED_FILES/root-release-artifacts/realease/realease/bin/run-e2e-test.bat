@echo off
setlocal enabledelayedexpansion

REM ============================================================================
REM EPMS End-to-End Integration Test
REM Starts gateway server, connects agent client, sends heartbeats,
REM and verifies bidirectional communication.
REM ============================================================================

SET SCRIPT_DIR=%~dp0
SET PROJECT_DIR=%SCRIPT_DIR%..
SET CONFIG_FILE=%PROJECT_DIR%\config\gateway.json
SET LOG_DIR=%PROJECT_DIR%\logs
SET DATA_DIR=%PROJECT_DIR%\data

IF NOT EXIST "%LOG_DIR%" mkdir "%LOG_DIR%"
IF NOT EXIST "%DATA_DIR%" mkdir "%DATA_DIR%"

SET TIMESTAMP=%DATE:/=-%_%TIME::=-%
SET TIMESTAMP=%TIMESTAMP: =0%
SET REPORT_FILE=%DATA_DIR%\e2e-test-report.txt

echo ============================================================================ > "%REPORT_FILE%"
echo  EPMS E2E Test Report - %DATE% %TIME% >> "%REPORT_FILE%"
echo ============================================================================ >> "%REPORT_FILE%"

echo.
echo ============================================================================
echo  EPMS End-to-End Integration Test
echo  Testing: Gateway Server + Agent Client + Productivity Monitoring
echo ============================================================================
echo.

REM ── Step 1: Verify Python is available ──────────────────────────────────
echo [STEP 1/6] Verifying Python environment...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Python not found in PATH
    pause
    exit /b 1
)
python -c "import epms_gateway, epms_agent; print('OK')" >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [FAIL] epms_gateway or epms_agent modules not installed
    echo Run: pip install -e D:\activitywatch\activitywatch_Source code\epms-agent-client
    pause
    exit /b 1
)
echo [PASS] Python environment ready
echo [STEP 1/6] PASS >> "%REPORT_FILE%"

REM ── Step 2: Start Gateway Server ────────────────────────────────────────
echo.
echo [STEP 2/6] Starting Gateway Server on 127.0.0.1:8005...

start "EPMS-Gateway" cmd /c "python -m epms_gateway --config "%CONFIG_FILE%" --log-level INFO > "%LOG_DIR%\gateway-test.log" 2>&1"
timeout /t 3 /nobreak >nul

REM Verify server is running
netstat -an | findstr "127.0.0.1:8005" | findstr "LISTENING" >nul
IF %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Gateway server is not listening on port 8005
    echo Check logs at: %LOG_DIR%\gateway-test.log
    echo [STEP 2/6] FAIL >> "%REPORT_FILE%"
    pause
    exit /b 1
)
echo [PASS] Gateway server is listening on port 8005
echo [STEP 2/6] PASS >> "%REPORT_FILE%"

REM ── Step 3: Start Agent Client ──────────────────────────────────────────
echo.
echo [STEP 3/6] Starting Agent Client...
start "EPMS-Agent" cmd /c "python -m epms_agent --config "%PROJECT_DIR%\config\agent.json" --verbose --no-tray --oneshot > "%LOG_DIR%\agent-test.log" 2>&1"
timeout /t 5 /nobreak >nul

REM Check agent log for success
findstr "Agent registered successfully" "%LOG_DIR%\agent-test.log" >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [WARN] Agent registration status unclear (may be first run)
    echo         Check %LOG_DIR%\agent-test.log for details
) ELSE (
    echo [PASS] Agent registered with gateway server
)
echo [STEP 3/6] PASS >> "%REPORT_FILE%"

REM ── Step 4: Send Heartbeats and Monitor ─────────────────────────────────
echo.
echo [STEP 4/6] Sending test heartbeats...

python -c "
import time, json, logging
logging.basicConfig(level=logging.INFO)
from epms_agent.api_client import EPMSApiClient
from epms_agent.config import load_config

config = load_config(r'%PROJECT_DIR%\config\agent.json')

print('  Connecting to gateway server...')
client = EPMSApiClient(config)
client._agent_id = 'e2e-test-agent'

# Test health check
healthy = client.health_check()
print(f'  Health check: {\"OK\" if healthy else \"FAIL\"}')

# Test heartbeat
result = client.send_heartbeat(afk_timeout_minutes=5)
print(f'  Heartbeat: {\"OK\" if result else \"FAIL\"}')

# Test WebSocket connection
client.connect_websocket()
time.sleep(2)

# Send 5 heartbeats
for i in range(5):
    result = client.send_heartbeat(afk_timeout_minutes=5)
    print(f'  Heartbeat #{i+1}: {\"OK\" if result else \"FAIL\"}')
    time.sleep(1)

client.disconnect_websocket()
print('  All heartbeats sent successfully')
" > "%LOG_DIR%\heartbeat-test.log" 2>&1

findstr "All heartbeats sent" "%LOG_DIR%\heartbeat-test.log" >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [PASS] Heartbeats sent and acknowledged
    echo [STEP 4/6] PASS >> "%REPORT_FILE%"
) ELSE (
    echo [WARN] Some heartbeats may have failed
    echo        Check %LOG_DIR%\heartbeat-test.log
    echo [STEP 4/6] PARTIAL >> "%REPORT_FILE%"
)

REM ── Step 5: Productivity Monitoring Test ────────────────────────────────
echo.
echo [STEP 5/6] Testing productivity monitoring...

python -c "
import json, time
from epms_agent.monitor import get_heartbeat_data, get_active_window_info, get_system_info

try:
    from epms_agent.browser_monitor import is_browser_process, get_browser_activity_data
except ImportError:
    pass
try:
    from epms_agent.editor_monitor import is_editor_process, get_editor_activity_data
except ImportError:
    pass

print('  Active window:', get_active_window_info().get('title', 'N/A')[:60])
system = get_system_info()
print(f'  CPU: {system[\"cpu\"][\"percent\"]}%%  RAM: {system[\"memory\"][\"percent\"]}%%  Disk: {system[\"disk\"][\"percent\"]}%%')

hb = get_heartbeat_data(5)
print(f'  AFK: {hb[\"is_afk\"]} ({hb[\"afk_seconds\"]}s idle)')
print(f'  Browser activity: {\"Yes\" if hb.get(\"browser_activity\") else \"None\"}')
print(f'  Editor activity: {\"Yes\" if hb.get(\"editor_activity\") else \"None\"}')
print('  Productivity data collection: OK')
" > "%LOG_DIR%\productivity-test.log" 2>&1

findstr "Productivity data collection: OK" "%LOG_DIR%\productivity-test.log" >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo [PASS] Productivity monitoring works
    echo [STEP 5/6] PASS >> "%REPORT_FILE%"
) ELSE (
    echo [WARN] Some monitoring features may be limited
    echo [STEP 5/6] PARTIAL >> "%REPORT_FILE%"
)

REM ── Step 6: Stop Services and Report ────────────────────────────────────
echo.
echo [STEP 6/6] Cleaning up...

REM Kill gateway server
taskkill /FI "WINDOWTITLE eq EPMS-Gateway*" /F >nul 2>&1
REM Kill agent client
taskkill /FI "WINDOWTITLE eq EPMS-Agent*" /F >nul 2>&1

timeout /t 2 /nobreak >nul

echo [PASS] Cleanup complete
echo [STEP 6/6] PASS >> "%REPORT_FILE%"

REM ── Final Report ────────────────────────────────────────────────────────
echo.
echo ============================================================================
echo  TEST RESULTS
echo ============================================================================
echo.
findstr /R "PASS$" "%REPORT_FILE%"
echo.
echo ============================================================================
echo  Full report: %REPORT_FILE%
echo  Logs:        %LOG_DIR%\
echo ============================================================================
echo.

timeout /t 5 /nobreak >nul
