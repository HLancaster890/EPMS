# DEPLOYMENT.md — EPMS Enterprise

Deployment procedures and configuration.

## Prerequisites

### System Requirements
- Windows 10/11 or Windows Server 2016+
- 4 GB RAM minimum (8 GB recommended)
- 10 GB disk space
- PowerShell 5.1+

### Infrastructure Requirements
- PostgreSQL 16 (or use bundled installer)
- Redis 3.x+ (or use bundled installer)
- NATS 2.10+ (or use bundled installer)

## Installation

### Option 1: NSIS Installer (Recommended)
1. Run `EPMS_Server_Setup.exe` or `EPMS_Client_Setup.exe`
2. Follow the wizard:
   - Welcome → License → Directory → Components → Install → Finish
3. Services are automatically registered and started

### Option 2: PowerShell Deployment
```powershell
# Install everything
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install

# Install server only
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install -Component Server

# Install client only
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action install -Component Client
```

### Option 3: Manual Installation
1. Copy `RELEASE\SERVER\*` to `C:\Program Files\EPMS\Server\`
2. Copy `RELEASE\CLIENT\*` to `C:\Program Files\EPMS\Agent\`
3. Run `install-server-services.ps1` and `install-agent-service.ps1`
4. Configure firewall rules using `firewall.ps1`

## Configuration

### Server Configuration
Location: `C:\ProgramData\EPMS\Config\appsettings.json`

```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "epms",
    "user": "postgres",
    "password": "",
    "max_connections": 20
  },
  "redis": {
    "host": "localhost",
    "port": 6379
  },
  "nats": {
    "url": "nats://localhost:4222"
  }
}
```

### Client Configuration
Location: `C:\Program Files\EPMS\Agent\agent.json`

```json
{
  "server": {
    "url": "ws://localhost:8005"
  },
  "monitoring": {
    "heartbeat_interval": 30,
    "browser": true,
    "editor": true,
    "afk_timeout": 300
  }
}
```

## Service Management

### Service Names
| Service | Display Name | Port |
|---------|--------------|------|
| EPMS-API | EPMS API Service | 8000 |
| EPMS-Analytics | EPMS Analytics Service | 8001 |
| EPMS-Reporting | EPMS Reporting Service | 8002 |
| EPMS-Notifications | EPMS Notifications Service | 8003 |
| EPMS-EventProcessor | EPMS Event Processor | 8004 |
| EPMS-Gateway | EPMS Agent Gateway | 8005 |
| EPMS-Agent | EPMS Monitoring Agent | N/A |
| EPMS-Client-Gateway | EPMS Client Gateway | 8005 |

### Service Environment Variables
Services read environment variables from registry:
`HKLM:\SYSTEM\CurrentControlSet\Services\<ServiceName>\Environment`

| Variable | Purpose |
|----------|---------|
| `APP_SETTINGS_PATH` | Path to appsettings.json |
| `EPMS_API_PORT` | API service port |
| `EPMS_LOG_DIR` | Log directory |

### Start/Stop Services
```powershell
# Start all server services
Start-Service EPMS-API, EPMS-Analytics, EPMS-Reporting, EPMS-Notifications, EPMS-EventProcessor, EPMS-Gateway

# Stop all server services
Stop-Service EPMS-API, EPMS-Analytics, EPMS-Reporting, EPMS-Notifications, EPMS-EventProcessor, EPMS-Gateway

# Restart all services
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action restart
```

## Upgrade

```powershell
# Upgrade with automatic backup
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action upgrade
```

## Rollback

```powershell
# Rollback to last backup
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action rollback
```

## Uninstall

```powershell
# Uninstall everything
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action uninstall

# Uninstall server only
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\deploy-epms.ps1 -Action uninstall -Component Server
```

## Verification

### Health Check
```powershell
# Full health check
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\health-check.ps1 -Mode Full

# Quick health check
powershell -ExecutionPolicy Bypass -File RELEASE\INSTALLERS\health-check.ps1 -Mode Quick
```

### Manual Verification
```powershell
# Check API health
Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing

# Check service status
Get-Service EPMS-*
```

## Web Dashboard

Access at: `http://localhost:8000/dashboard`

The dashboard is served from the API service (port 8000) via `StaticFiles` mount.

## Firewall Rules

The following firewall rules are created:

### Server (Inbound)
- EPMS-API (TCP 8000)
- EPMS-Analytics (TCP 8001)
- EPMS-Reporting (TCP 8002)
- EPMS-Notifications (TCP 8003)
- EPMS-EventProcessor (TCP 8004)
- EPMS-Gateway (TCP 8005)
- EPMS-All (TCP 8000-8005)

### Client (Bidirectional)
- EPMS-Agent-Outbound
- EPMS-Client-Gateway-Inbound
- EPMS-Client-Gateway-Outbound
- EPMS-Agent-All
