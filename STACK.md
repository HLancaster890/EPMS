# STACK.md — EPMS Enterprise

Technology stack and version information.

## Core Stack

### Server Services (Python)
| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Runtime |
| FastAPI | 0.104+ | REST API framework |
| Uvicorn | 0.24+ | ASGI server |
| asyncpg | 0.29+ | PostgreSQL async driver |
| redis-py | 5.3.1 | Redis async client |
| nats-py | 2.10+ | NATS messaging client |
| PyJWT | 2.8+ | JWT token handling |
| PyInstaller | 6.3+ | Build standalone executables |

### Infrastructure
| Component | Version | Purpose |
|-----------|---------|---------|
| PostgreSQL | 16 | Primary database |
| Redis | 3.x / 6.x | Caching, sessions, rate limiting |
| NATS | 2.10+ | Event messaging |

### Client (Python)
| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Runtime |
| psutil | 5.9+ | System metrics |
| websockets | 12.0+ | WebSocket client |
| PyInstaller | 6.3+ | Build standalone executables |

### Installers
| Component | Version | Purpose |
|-----------|---------|---------|
| NSIS | 3.12 | Windows installer creation |
| PowerShell | 5.1 | Deployment scripts |

## Version History

### Current Version: 2.0.0
- 6 FastAPI microservices
- Dual-service client architecture
- NSIS installers
- Windows Service registration via registry
- Web dashboard at `/dashboard`

### Previous Versions
- **1.0.0**: Initial release with single-service architecture

## Update Procedures

### Updating Python Dependencies
```powershell
# Update server service dependencies
cd activitywatch_Source code\epms-server-installer
pip install --upgrade fastapi uvicorn asyncpg redis nats-py pyjwt

# Update client dependencies
cd activitywatch_Source code\epms-agent-client
pip install --upgrade psutil websockets

# Update PyInstaller
pip install --upgrade pyinstaller
```

### Updating redis-py (Windows Redis 3.x)
```powershell
# redis-py 8.0.0 uses HELLO command not supported by Redis 3.x Windows port
# Downgrade to redis-py 5.3.1 for compatibility
pip install "redis<6.0"

# Then rebuild PyInstaller executables
.\build-release.ps1
```

### Updating NSIS
```powershell
# Check NSIS version
& "C:\Program Files (x86)\NSIS\makensis.exe" /VERSION

# Download latest from: https://nsis.sourceforge.io/Download
```

### Updating Infrastructure
```powershell
# Redis (Windows port)
# Download from: https://github.com/tporadowski/redis/releases

# PostgreSQL
# Download from: https://www.postgresql.org/download/windows/

# NATS
# Download from: https://nats.io/download/
```

## Dependency Matrix

### Server Service Dependencies
| Service | Python Packages |
|---------|-----------------|
| epms-api | fastapi, uvicorn, asyncpg, redis, nats-py, pyjwt |
| epms-analytics | fastapi, uvicorn, redis, nats-py |
| epms-reporting | fastapi, uvicorn, asyncpg |
| epms-notifications | fastapi, uvicorn, redis, nats-py, aiosmtplib |
| epms-event-processor | fastapi, uvicorn, asyncpg, nats-py |
| epms-agent-gateway | fastapi, uvicorn, redis, nats-py, websockets |

### Client Dependencies
| Component | Python Packages |
|-----------|-----------------|
| EPMS_Agent | psutil, websockets, requests |
| EPMS_Gateway | websockets |

## Known Compatibility Issues

### redis-py 8.0.0 + Redis 3.x Windows
- **Issue**: redis-py 8.0.0 uses `HELLO` command not supported by Redis 3.x Windows port
- **Fix**: Use `pip install "redis<6.0"` or upgrade to Redis 6.x

### PowerShell 5.1 + Ternary Operator
- **Issue**: `?` operator is PowerShell 7+ only
- **Fix**: Use `if/else` statements

### PyInstaller + Uvicorn Workers
- **Issue**: Uvicorn multi-worker uses fork() which breaks PyInstaller frozen exe
- **Fix**: Always use `workers=1` in uvicorn.run()
