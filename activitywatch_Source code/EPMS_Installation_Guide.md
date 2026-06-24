# EPMS Enterprise Server — Installation Guide

## Version 1.0.0

---

## Server Installation

### Prerequisites
- Windows 10/11 or Windows Server 2019/2022 (64-bit)
- Administrator privileges
- .NET 8 Runtime (auto-installed by bootstrapper)
- Visual C++ 2022 Redistributable (auto-installed)

### Installation Steps
1. Run `EPMS_Server_Setup.exe` **as Administrator** (right-click → Run as Administrator)
2. Click through the setup wizard:
   - **Welcome** → Read introduction
   - **License Agreement** → Accept terms
   - **Installation Type** → Select Express (Recommended)
   - **Server Configuration** → Accept defaults (port 443)
   - **Database Configuration** → Install embedded PostgreSQL
   - **Admin Account** → Enter email, password, organization name
3. Review and click **Install**
4. Wait for installation to complete (3-5 minutes)
5. Click **Finish** — dashboard opens automatically

### Silent (Unattended) Installation
```batch
EPMS_Server_Setup.exe /quiet /norestart ^
    EPMS_INSTALL_TYPE=express ^
    EPMS_PORT=443 ^
    EPMS_ADMIN_EMAIL=admin@company.com ^
    EPMS_ADMIN_PASSWORD="YourP@ssw0rd123!" ^
    EPMS_ORGANIZATION="Company Inc"
```

### Verifying Installation
1. Open `https://localhost` in a browser
2. Log in with admin credentials
3. Dashboard shows: connected devices, online status, activity metrics

---

## Client Agent Installation

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Network access to EPMS Server
- Server API key (from administrator)

### Installation Steps
1. Run `EPMS_Agent_Setup.exe` **as Administrator**
2. When prompted, enter:
   - **Server Address**: IP or domain (e.g., `192.168.1.100` or `epms.company.com`)
   - **Port**: `443` (default)
   - **API Key**: Provided by administrator
   - **Display Name**: Optional descriptive name
3. Agent installs, registers with server, and starts monitoring

### Silent Installation
```batch
EPMS_Agent_Setup.exe /quiet /norestart
```
Configure post-install: `%ProgramData%\EPMS\Agent\config\agent.json`

### Agent Features
- ✅ Automatic server registration with heartbeat
- ✅ Browser monitoring: Google Chrome, Microsoft Edge, Mozilla Firefox, Brave
- ✅ Editor monitoring: VS Code, Visual Studio, Cursor, Windsurf, PyCharm, IntelliJ, Eclipse, Notepad++, Sublime Text
- ✅ System metrics: CPU, memory, disk, network
- ✅ AFK / idle detection
- ✅ Offline data cache
- ✅ Auto-recovery and auto-start
- ✅ System tray status indicator
- ✅ Configuration dialog (right-click tray icon)

---

## Communication Flow

```
Client Agent                    EPMS Server
     │                              │
     │── HTTPS POST /api/v1/agent/register ──►│
     │                              │
     │── HTTPS POST /api/v1/agent/heartbeat ──►│  (every 30s)
     │                              │
     │── HTTPS POST /api/v1/agent/browser ────►│  (browser activity)
     │                              │
     │── HTTPS POST /api/v1/agent/editor ─────►│  (editor activity)
     │                              │
     │── HTTPS GET /api/v1/agent/policies ◄────│  (config pull)
     │                              │
     │── WebSocket /ws/ ◄──────────────────────►│  (real-time)
     │                              │
     ▼                              ▼
  Monitoring                  Dashboard
```

---

*For detailed deployment, see the Deployment Guide in DEPLOYMENT_GUIDES/*

---

## Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| Server setup fails | Run as Administrator; check Windows Event Viewer |
| Services not starting | `net start EPMS-API` from Admin terminal |
| Dashboard shows 502 | Check NGINX: `sc query EPMS-API` |
| Agent won't connect | Verify server address and API key |
| Database error | Check: `sc query epms-postgresql-16` |
| Certificate warning | Self-signed is normal; import cert for production |
