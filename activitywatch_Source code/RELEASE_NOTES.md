# EPMS Enterprise Server — Release Notes

## Version 2.0.0 (Consolidated Architecture)

**Release Date:** June 2026

---

### Overview

EPMS v2.0.0 is a major architecture revision: 6 microservices consolidated into a single FastAPI service. Removed Redis, NATS, WebSocket gateway, and NGINX dependencies. Added full process scanning, AD/LDAP integrated auth with RBAC, and bucket abstraction layer.

### Breaking Changes

#### Removed Components
- **6 microservices → 1**: `epms-api`, `epms-analytics`, `epms-reporting`, `epms-notifications`, `epms-event-processor`, `epms-gateway` consolidated into a single `epms-server` service (port 8000)
- **Redis removed**: No longer required. Rate limiting uses in-memory counters. Caching is optional and file-based.
- **NATS removed**: No message bus needed — single service calls itself via direct function calls or DB.
- **WebSocket gateway removed**: Agents now POST heartbeats via REST to `POST /api/v1/heartbeat` with `Authorization: Bearer <key>`.
- **NGINX removed**: Single service listens directly on port 8000; no reverse proxy required for standard deployments.
- **`EPMS_INTERNAL_API_KEY` removed**: No service-to-service auth needed.

#### Configuration Changes
| Old Variable | Status | New Variable |
|-------------|--------|-------------|
| `EPMS_PORT` | Removed | — |
| `REDIS_HOST` / `REDIS_PORT` | Removed | — |
| `NATS_URL` / `NATS_USER` / `NATS_PASSWORD` | Removed | — |
| `EPMS_INTERNAL_API_KEY` | Removed | — |
| `ENROLLMENT_TOKEN` | Renamed | `EPMS_ENROLLMENT_TOKEN` |
| `API_KEY` (gateway) | Removed | Agents use server-issued API keys |
| `EPMS_API_KEY_PEPPER` | Kept | Same — hashes agent API keys |
| — | Added | `EPMS_LDAP_SERVER`, `EPMS_LDAP_DOMAIN`, `EPMS_LDAP_USE_SSL` |
| — | Added | `EPMS_DEV_MODE`, `EPMS_DEV_CREDENTIALS` |
| — | Added | `CORS_ORIGINS` (default `http://localhost:3000`) |

#### Data Flow Changes
- **Old**: Agent → WebSocket → Gateway → NATS → Event Processor → PostgreSQL
- **New**: Agent → REST → epms-server → PostgreSQL (direct)
- **Old**: Analytics consumed NATS stream → Redis cache → API → Dashboard
- **New**: Aggregation worker runs inline, writes directly to `app_sessions` table → Dashboard queries PostgreSQL

### New Features

#### Full Process Scanner
- Replaces window-title-only browser/editor monitors
- Collects ALL running processes every 5s via `psutil.process_iter()`: name, PID, CPU%, memory_mb, window_title (if foreground)
- Per-process metrics stored in `process_events` table
- AFK detection via `GetLastInputInfo()`

#### AD/LDAP Authentication
- Users authenticate via AD credentials (`POST /api/v1/auth/ad-login`)
- AD groups map to EPMS roles: Domain Admins → admin, EPMS-Managers → manager, all others → employee
- Mail attribute auto-populates email for reports
- First AD login auto-provisions user, org, and team

#### Role-Based Access Control
- **Employee**: Own data only (activity, productivity, apps)
- **Manager**: Own + team data (drill-down, reports, alerts, limited settings)
- **Admin**: Full access (org, users, settings, all reports)
- Enforced via `require_role()` middleware on every endpoint

#### Bucket Abstraction Layer
- Virtual view over relational tables
- `GET /api/v1/buckets/<id>/events?start=...&end=...` maps to parameterized SQL on `app_sessions` / `process_events`
- Bucket config stored in `bucketing_rules` table (no separate data store)

#### REST-Only Agent Transport
- Heartbeats: `POST /api/v1/heartbeat` (batch payload, every 30s)
- Auth: `Authorization: Bearer <server-issued-api-key>`
- Offline buffering: SQLite local buffer, replay on reconnect
- No WebSocket, no query-param API key exposure

### Security Improvements (v2.0.0)

- **SQL injection fixed**: Report generation parameterized `organization_id` via `$3`
- **WebSocket removed entirely**: Eliminates query-param key leakage vector
- **Dev mode backdoor removed**: Hardcoded `admin@epms.local` / `Admin123!@#` replaced with `EPMS_DEV_CREDENTIALS` (base64 JSON env var)
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `X-XSS-Protection: 0`
- **CORS default**: `http://localhost:3000` (logs warning if unset)
- **AD login rate limiting**: 5-attempt/min throttle
- **LDAP default SSL**: Port 636, SSL enabled by default
- **Enrollment token exact match**: `=` instead of `LIKE`
- **Report download path traversal guard**: `report_dir` prefix check
- **Startup validation**: Logs CRITICAL if `JWT_SECRET`, `EPMS_API_KEY_PEPPER`, `EPMS_LDAP_SERVER` unset

### Supported Platforms

| Platform | Server | Agent |
|----------|--------|-------|
| Windows 10 | ✅ | ✅ |
| Windows 11 | ✅ | ✅ |
| Windows Server 2019 | ✅ | ❌ |
| Windows Server 2022 | ✅ | ❌ |
| Linux | ❌ | ❌ |

### Known Limitations

1. **Bucket abstraction is SQL-backed**: Not a separate query-language store. Complex queries use raw SQL via `bucketing_rules`. No ActivityWatch-compatible query language.
2. **No WebSocket**: Real-time dashboard updates require polling (SSE planned for v2.1).
3. **Single-threaded PyInstaller**: Production deployment uses `workers=1` — uvicorn multi-worker breaks frozen exe. Scale vertically.
4. **Dashboard CDN dependencies**: Chart.js and Font Awesome require internet access. Offline bundle planned.

### Upgrade Notes

- **v1.0.0 → v2.0.0 requires full reinstall**: Database schema changed (new tables, removed Redis/NATS tables). WiX installer handles migration via `--mode upgrade`.
- **Agents must update**: Old WebSocket agents will not connect. Deploy new `EPMS_Agent.exe` with REST-only configuration.
- **Configuration migration**: Remove Redis/NATS config from `appsettings.json`. Add AD/LDAP config if using AD auth.
- **Downgrade not supported**: Schema changes are non-reversible. Take full backup before upgrade.

### Required Configuration

| Variable | Purpose | Default | Required |
|----------|---------|---------|----------|
| `JWT_SECRET` | Signs JWT tokens | `""` (startup warning) | **Yes** |
| `EPMS_API_KEY_PEPPER` | API key hashing | `""` (startup warning) | **Yes** |
| `CORS_ORIGINS` | CORS allowed origins | `http://localhost:3000` | Recommended |
| `EPMS_ENROLLMENT_TOKEN` | Agent enrollment | auto-generated | No |
| `EPMS_DEV_MODE` | Enable dev bypass | off | Dev only |
| `EPMS_DEV_CREDENTIALS` | Dev admin creds (base64 JSON) | `""` | Dev only |
| `EPMS_LDAP_SERVER` | AD/LDAP server | `""` (disabled) | If using AD |
| `EPMS_LDAP_DOMAIN` | AD domain | `""` | If using AD |
| `EPMS_LDAP_USE_SSL` | LDAP SSL | `true` | Recommended |

### Package Contents

```
RELEASE/
├── SERVER/
│   ├── epms-server/              (single service COLLECT dir)
│   │   ├── epms_server_service.exe
│   │   ├── web-ui/               (dashboard static files)
│   │   └── alembic/              (migration scripts)
│   └── appsettings.json.template
├── CLIENT/
│   ├── EPMS_Agent.exe
│   └── agent.json
├── config/
│   └── appsettings.json
├── INSTALLERS/
│   ├── deploy-epms.ps1
│   ├── firewall.ps1
│   ├── health-check.ps1
│   └── validate-config.ps1
├── SUPPORT/
│   ├── ADMINISTRATOR_GUIDE.md
│   └── DEPLOYMENT_GUIDE.md
├── DOCUMENTATION/
└── RELEASE_NOTES/
```

---

## Version 1.0.0 (Original — Superseded)

**Release Date:** June 2025

The original v1.0.0 release with 6 microservices, Redis, NATS, and WebSocket gateway. Superseded by v2.0.0 consolidated architecture. See v2.0.0 for upgrade notes.

---

*For questions or support, contact IT or visit the EPMS documentation portal.*
