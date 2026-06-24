# COMMANDS.md — EPMS Enterprise

Quick reference for all commands used in this project.

## Build Commands

### Server Services
```powershell
# Full release build (at repo root)
.\build-release.ps1

# Build just server services
.\activitywatch_Source code\epms-server-installer\build-services.ps1

# Build individual service (example: epms-api)
cd activitywatch_Source code\epms-server-installer
python -m PyInstaller --clean --distpath "D:\activitywatch\RELEASE\SERVER" --workpath "D:\activitywatch\RELEASE\SERVER\epms-api\build" --specpath "D:\activitywatch\RELEASE\SERVER" --noconfirm --console --onefile --name epms-api --add-data "Resources\config;config" --hidden-import uvicorn.logging --hidden-import uvicorn.loops --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols --hidden-import uvicorn.protocols.http --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.websockets --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan --hidden-import uvicorn.lifespan.on epms_api_service.py
```

### Client Executables
```powershell
# Build agent and gateway
cd RELEASE
bin\build-exe.bat

# Or use PyInstaller directly
cd activitywatch_Source code\epms-agent-client
pyinstaller --onefile --name EPMS_Agent agent_main.py
pyinstaller --onefile --name EPMS_Gateway epms_gateway/server.py
```

### NSIS Installers
```powershell
# Build server installer
& "C:\Program Files (x86)\NSIS\makensis.exe" "D:\activitywatch\setup release\EPMS_Server_Setup.nsi"

# Build client installer
& "C:\Program Files (x86)\NSIS\makensis.exe" "D:\activitywatch\setup release\EPMS_Client_Setup.nsi"
```

## Test Commands

### Python Tests
```powershell
# Navigate to agent directory
cd activitywatch_Source code\epms-agent-client

# Install test dependencies
pip install -e ".[test]"

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_browser.py -v

# Run with coverage
python -m pytest tests/ --cov=epms_agent --cov-report=html
```

### Health Checks
```powershell
# Full health check (services + infrastructure)
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\health-check.ps1 -Mode Full

# Quick health check (API only)
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\health-check.ps1 -Mode Quick

# Health check with JSON output
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\health-check.ps1 -Mode Full -Format JSON
```

### Config Validation
```powershell
# Validate config at default location
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\validate-config.ps1

# Validate config at specific location
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\validate-config.ps1 -ConfigDir "C:\ProgramData\EPMS\Config"
```

## Deployment Commands

### Install
```powershell
# Install everything (server + client)
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install

# Install server only
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install -Component Server

# Install client only
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install -Component Client

# Silent install
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install -Silent
```

### Upgrade / Repair / Restart
```powershell
# Upgrade (with backup)
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action upgrade

# Repair (reinstall without backup)
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action repair

# Restart all services
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action restart
```

### Rollback / Uninstall
```powershell
# Rollback to last backup
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action rollback

# Uninstall everything
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action uninstall

# Uninstall server only
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action uninstall -Component Server
```

### Firewall Rules
```powershell
# Create firewall rules
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\firewall.ps1 -Action Create -Component Server

# Remove firewall rules
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\firewall.ps1 -Action Remove -Component All
```

## Service Management

```powershell
# Check service status
Get-Service EPMS-*, EPMS-Agent, EPMS-Client-Gateway

# Start a service
Start-Service EPMS-API

# Stop a service
Stop-Service EPMS-API

# Restart a service
Restart-Service EPMS-API

# View service details
sc.exe qc EPMS-API
sc.exe query EPMS-API
```

## Skills Management

```powershell
# List installed skills
npx skills list

# Search for skills
npx skills find [query]

# Install a skill
npx skills add <owner/repo@skill-name>

# Check for updates
npx skills check

# Update all skills
npx skills update
```

## Development

```powershell
# Run API service locally (for development)
cd activitywatch_Source code\epms-server-installer\Resources\services
python epms_api_service.py

# Run with custom port
$env:EPMS_API_PORT="9000"; python epms_api_service.py

# Install Python dependencies
pip install fastapi uvicorn asyncpg redis nats-py pyjwt
```

## SHA-256 Checksums

```powershell
# Generate checksum for a file
(Get-FileHash -Algorithm SHA256 "D:\activitywatch\setup release\EPMS_Server_Setup.exe").Hash

# Generate checksums for all installer
$serverHash = (Get-FileHash -Algorithm SHA256 "D:\activitywatch\setup release\EPMS_Server_Setup.exe").Hash
$clientHash = (Get-FileHash -Algorithm SHA256 "D:\activitywatch\setup release\EPMS_Client_Setup.exe").Hash
Write-Host "Server: $serverHash"
Write-Host "Client: $clientHash"
```
