# TROUBLESHOOTING.md — EPMS Enterprise

Common issues and solutions.

## Service Issues

### Services Won't Start

**Symptom**: Services show "Stopped" or fail to start

**Causes & Fixes**:

1. **BAT wrapper issue (FIXED)**
   - Old scripts registered `.bat` files as `binPath`
   - Windows SCM cannot execute `.bat` files
   - **Fix**: Reinstall services with updated scripts that register `.exe` directly

2. **Missing binaries**
   ```powershell
   # Check if exe exists
   Test-Path "C:\Program Files\EPMS\Server\epms-api\epms-api.exe"
   ```
   - **Fix**: Reinstall or copy missing files

3. **Port conflict**
   ```powershell
   # Check what's using the port
   netstat -ano | findstr :8000
   ```
   - **Fix**: Stop conflicting process or change port in config

4. **Missing environment variables**
   ```powershell
   # Check registry for service env vars
   Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\EPMS-API\Environment"
   ```
   - **Fix**: Reinstall services to restore registry entries

### Services Start but Health Check Fails

**Symptom**: Services running but `/health` returns 503

**Causes & Fixes**:

1. **PostgreSQL not running**
   ```powershell
   # Check PostgreSQL
   Get-Service postgresql*
   ```
   - **Fix**: Start PostgreSQL or install it

2. **Redis not running**
   ```powershell
   # Check Redis
   Get-Service Redis*
   & "C:\Program Files\Redis\redis-cli.exe" PING
   ```
   - **Fix**: Start Redis or install it

3. **NATS not running**
   ```powershell
   # Check NATS
   Get-Process nats-server
   ```
   - **Fix**: Start NATS server

### Services in Degraded Mode

**Symptom**: Health shows `database=disconnected`, `redis=disconnected`, or `nats=disconnected`

This is normal when infrastructure isn't running. Services operate in degraded mode:
- API: Returns 503 on database-dependent endpoints
- Analytics: No real-time data
- EventProcessor: Cannot ingest events
- Gateway: Cannot cache agent data

**Fix**: Start required infrastructure (PostgreSQL, Redis, NATS)

## PowerShell Issues

### Execution Policy Error

**Error**: `running scripts is disabled on this system`

**Fix**:
```powershell
# Run with bypass
powershell -ExecutionPolicy Bypass -File script.ps1

# Or set policy (requires admin)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Ternary Operator Error

**Error**: `Unexpected token '?'`

**Cause**: PowerShell 5.1 doesn't support `?` ternary operator

**Fix**: Use `if/else` instead:
```powershell
# Bad (PS 7+)
$result = $condition ? "true" : "false"

# Good (PS 5.1)
if ($condition) { $result = "true" } else { $result = "false" }
```

## Configuration Issues

### Config Not Found

**Error**: `appsettings.json not found at C:\WINDOWS\system32`

**Cause**: `validate-config.ps1` defaulted to CWD

**Fix**: Pass explicit path:
```powershell
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\validate-config.ps1 -ConfigDir "C:\ProgramData\EPMS\Config"
```

### Wrong Config Path

**Error**: Config changes not taking effect

**Cause**: Service reading from wrong location

**Fix**: Check service environment variable:
```powershell
Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\EPMS-API\Environment" | Select-Object APP_SETTINGS_PATH
```

## Build Issues

### PyInstaller Build Fails

**Error**: Various import errors

**Fix**:
```powershell
# Install all dependencies
pip install fastapi uvicorn asyncpg redis nats-py pyjwt

# Clean build
pyinstaller --clean ...
```

### NSIS Build Fails

**Error**: `makensis.exe` not found

**Fix**: Install NSIS v3.12 from https://nsis.sourceforge.io/Download

### redis-py Version Mismatch

**Error**: Redis connection fails with `HELLO` command error

**Cause**: redis-py 8.0.0 uses HELLO command not supported by Redis 3.x Windows

**Fix**:
```powershell
pip install "redis<6.0"
# Then rebuild executables
```

## Network Issues

### Agent Cannot Connect to Gateway

**Check**:
```powershell
# Verify gateway is running
Get-Service EPMS-Gateway

# Test WebSocket connection
Test-NetConnection -ComputerName localhost -Port 8005
```

**Fix**:
- Ensure gateway service is running
- Check firewall rules
- Verify agent.json server URL

### API Cannot Connect to Database

**Check**:
```powershell
# Test PostgreSQL connection
Test-NetConnection -ComputerName localhost -Port 5432
```

**Fix**:
- Ensure PostgreSQL is running
- Check credentials in appsettings.json
- Verify database exists

## Logs

### Service Logs
Location: `C:\ProgramData\EPMS\Logs\`

### Windows Event Log
```powershell
# View service events
Get-WinEvent -LogName System -MaxEvents 50 | Where-Object {$_.ProviderName -like "*EPMS*"}
```

## Getting Help

### Health Check
```powershell
# Full diagnostic
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\health-check.ps1 -Mode Full -Format JSON
```

### Service Status
```powershell
# All EPMS services
Get-Service EPMS-*, EPMS-Agent, EPMS-Client-Gateway | Format-Table Name, Status, StartType
```

### Test Deployment
```powershell
# Run tests
cd activitywatch_Source code\epms-agent-client
pip install -e ".[test]"
python -m pytest tests/ -v
```
