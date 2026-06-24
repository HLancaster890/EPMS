# AGENTS.md — EPMS Enterprise

EPMS (Enterprise Productivity Management System) is a workforce productivity monitoring platform for Windows enterprise environments. Single FastAPI service, PostgreSQL backend, AD-integrated auth.

## Architecture

### Production target
| Directory | Role |
|-----------|------|
| `activitywatch_Source code/epms-agent-client/` | Python agent — process scanner, AFK detection, systray. PyInstaller → standalone exe |
| `activitywatch_Source code/epms-server-installer/` | WiX v5 Burn BA installer: 1 consolidated FastAPI service + embedded PostgreSQL 16 |

**1 Server service** (FastAPI/uvicorn, PyInstaller-built `.exe`):
- `epms-server` (port 8000) — consolidated: auth (JWT + AD/LDAP), agent API, analytics (including per-agent scores, trends, org summary), reports, notifications, alerts, aggregation worker, enterprise dashboard

**Only PostgreSQL required.** No Redis, no NATS. Redis is optional — rate limiting and token blacklist degrade gracefully.

**Agent features**: full process scanning via `psutil.process_iter()`, foreground window tracking, per-process CPU/RAM metrics, AFK detection, systray, SQLite offline buffer.

### Release layout
```
RELEASE/
├── SERVER/                       # 1 PyInstaller COLLECT dir (epms-server/)
├── CLIENT/                       # EPMS_Agent.exe, agent.json
├── INSTALLERS/                   # PowerShell deployment scripts
│   ├── deploy-epms.ps1           # Master orchestrator (install/upgrade/repair/rollback/restart/validate/uninstall)
│   ├── firewall.ps1              # Windows Firewall rule management
│   ├── health-check.ps1          # Service + API health verification
│   ├── validate-config.ps1       # Configuration validation
│   ├── Server/Scripts/           # install-server-service.ps1, uninstall-server-service.ps1
│   ├── Client/Scripts/           # install-agent-service.ps1, uninstall-agent-service.ps1
│   └── Config/                   # appsettings.json, validate-config.ps1
├── config/                       # appsettings.json (deployed to C:\ProgramData\EPMS\Config\)
├── DOCUMENTATION/
setup release/                    # NSIS installer sources + built .exe installers
```

## Build commands

```powershell
# Full release (at repo root)
.\build-release.ps1

# Build just server service
.\activitywatch_Source code\epms-server-installer\build-services.ps1

# Build just agent executable
.\realease\bin\build-exe.bat

# Build NSIS installers
& "C:\Program Files (x86)\NSIS\makensis.exe" "D:\activitywatch\setup release\EPMS_Server_Setup.nsi"
& "C:\Program Files (x86)\NSIS\makensis.exe" "D:\activitywatch\setup release\EPMS_Client_Setup.nsi"

# Build dashboard
cd dashboard
npx next build
Copy-Item -Path "out\*" -Destination "..\activitywatch_Source code\epms-server-installer\Resources\services\web-ui\" -Recurse -Force

# Run agent tests
cd activitywatch_Source code\epms-agent-client
pip install -e ".[test]"
python -m pytest tests/ -v

# Run server tests
cd activitywatch_Source code\epms-server-installer
python -m pytest tests/ -v
```

## Service file naming
The service `.py` file uses underscores (e.g. `epms_server_service.py`) — uvicorn imports the module name, and Python can't import hyphenated names. Uses FastAPI **lifespan context manager** (no `@app.on_event`).

## Deployment — known gotchas

### Single service only
There is 1 service (`epms-server` on port 8000). No NATS, no Redis, no WebSocket gateway. Agents POST heartbeats via REST (`Authorization: Bearer <key>`).

### Config path defaults
- `deploy-epms.ps1`: `$ConfigDir` defaults to empty; must set explicitly to `$env:ProgramData\EPMS\Config`
- `validate-config.ps1`: defaults to `$env:ProgramData\EPMS\Config`
- `install-server-service.ps1`: defaults to `$env:ProgramData\EPMS\Config`

### Service startup
Single service starts after PostgreSQL. No Redis/NATS dependency. Health endpoint always returns HTTP 200; check JSON body for `database` connection state.

### Infrastructure dependencies
Only PostgreSQL 16 is required. No Redis, no NATS, no NGINX.

## Key quirks

- **Process scanner**: Uses `psutil.process_iter()` every 5s to collect ALL running processes (name, pid, cpu%, memory_mb, window_title if foreground). AFK via `GetLastInputInfo()`.
- **AD/LDAP integration**: Users authenticate via AD credentials. AD groups map to EPMS roles (Domain Admins → admin, EPMS-Managers → manager, all others → employee). Mail attribute auto-populates email for reports. First AD login auto-provisions user/org/team.
- **Role-Based Access Control**: 3 tiers — **Employee** (own data only: activity, productivity, apps), **Manager** (own + team: drill-down, reports, alerts, limited settings, users, rules), **Admin** (full access: org, teams, users, settings, all reports). Sidebar filters nav items by role.
- **REST-only transport**: No WebSocket, no NATS. Agent sends batch heartbeats via `POST /api/v1/agent/heartbeat` with `Authorization: Bearer <key>`. Offline data uses SQLite buffer. Agent uses `httpx.AsyncClient` (no `websocket-client`).
- **Redis optional**: Rate limiting and token blacklist fall back gracefully when Redis is unavailable. Set `redis_client=None` at startup to disable.
- **Shared config module**: `epms_server/config.py` centralizes JWT settings, token prefixes, and `redis_client` reference. `rbac.py` imports from config instead of the service module — no circular imports.
- **CORS**: Default `http://localhost:3000`. Set explicit `CORS_ORIGINS` env var for production.
- **Multi-tenant isolation**: All endpoints filter by `organization_id` from JWT claim. Token must include `org_id`.
- **JWT includes org_id**: `create_access_token()` requires `org_id` parameter. Tokens without `org_id` return empty results.
- **Dev mode**: Requires `EPMS_DEV_MODE=true` AND `EPMS_DEV_CREDENTIALS=<base64-json>`. Generate via: `[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('{"email":"admin@corp.local","password":"MyP@ss1"}'))`.
- **Dashboard login credentials** (dev mode): `admin@corp.local` / `MyP@ss1` (matches the login page defaults). The server MUST be started with `EPMS_DEV_MODE=true` and `EPMS_DEV_CREDENTIALS` set for the login to work without a pre-existing DB user.
- **API key pepper**: Must set `EPMS_API_KEY_PEPPER` env var. Warns on first use if unset, falls back to weak default.
- **Per-agent analytics**: 4 endpoints — `GET /api/v1/analytics/scores/{agent_id}`, `/trends/{agent_id}`, `/organization`, `/live/{agent_id}`. Protected by `require_role("manager")`.
- **Dashboard**: Next.js 16.2.9 static export (TypeScript + React 19 + Tailwind v4 + Chart.js + React Query + Zustand), served by API service via `StaticFiles` mount at `/dashboard`. Build source at `dashboard/` — run `npm run build` then copy `out/` to `services/web-ui/`.
- **PyInstaller workers=1 mandatory**: uvicorn multi-worker uses fork() which breaks PyInstaller frozen exe. Single `.spec` at `services/epms-server.spec`.
- **Server uses lifespan**: FastAPI `@asynccontextmanager` lifespan replaces deprecated `@app.on_event("startup")`/`"shutdown"`.

## Dashboard Pages (18 total)

| Page | Auth | Features |
|------|------|----------|
| `/` | Any | Stat cards, productivity trend, activity breakdown, AFK idle time, period selector |
| `/devices/` | Any | Device table with status |
| `/activity/` | Any | Timeline Gantt chart, category doughnut, events table, period selector |
| `/browsers/` | Any | Bar chart + table |
| `/editors/` | Any | Bar chart + table |
| `/productivity/` | Any | 30-day trend, 4-category breakdown (productive/neutral/distracting/idle), period selector |
| `/team/` | Manager+ | Team card grid |
| `/users/` | Manager+ | User table (name, role, status, last login) |
| `/rules/` | Manager+ | Productivity rules CRUD (glob/regex/exact patterns → productive/neutral/distracting) |
| `/alerts/` | Any | Alert list with acknowledge |
| `/reports/` | Any | Report generation + download |
| `/org/` | Admin | Organization overview + team/user counts |
| `/settings/` | Any | Profile, role, API config |

All data pages have a **TimePeriodSelector** (today/week/month/custom). Sidebar is role-aware (employee sees 8 items, manager sees 11, admin sees 12).

## Dashboard components

```
dashboard/
├── app/                       # 18 App Router pages
├── components/
│   ├── layout/               # Sidebar (role-filtered), Header
│   ├── ui/                   # Card, StatCard, Badge, LoadingSpinner, TimePeriodSelector
│   ├── charts/               # LineChart, BarChart, DoughnutChart, TimelineChart (Gantt)
│   └── features/             # ActivityTable, DeviceTable, AlertsPanel, ProductivityScore
├── lib/
│   ├── types.ts              # All TypeScript interfaces (User, Team, Org, ProductivityRule, etc.)
│   ├── api.ts                # Typed API client with field normalization
│   ├── store.ts              # Zustand auth store
│   └── providers.tsx         # React Query provider + auth hydration
```

## API Endpoints (server)

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/api/v1/auth/me` | Any | Current user info |
| POST | `/api/v1/auth/login` | Public | Email/password login |
| POST | `/api/v1/auth/ad-login` | Public | AD/LDAP login |
| POST | `/api/v1/auth/refresh` | Public | Refresh token |
| POST | `/api/v1/auth/logout` | Any | Blacklist token |
| POST | `/api/v1/agent/register` | API key | Agent registration |
| POST | `/api/v1/agent/heartbeat` | API key | Process heartbeat + process list |
| POST | `/api/v1/agent/browser` | API key | Browser activity |
| POST | `/api/v1/agent/editor` | API key | Editor activity |
| POST | `/api/v1/agent/events/batch` | API key | Batch events |
| POST | `/api/v1/agent/metrics` | API key | System metrics |
| GET | `/api/v1/agent/config` | API key | Agent configuration |
| GET | `/api/v1/agent/policies` | API key | Agent policies |
| GET | `/api/v1/dashboard/summary?period=` | Any | Dashboard stats |
| GET | `/api/v1/dashboard/devices` | Any | Device list |
| GET | `/api/v1/dashboard/activity?period=` | Any | Activity feed |
| GET | `/api/v1/dashboard/browser-activity` | Any | Browser events |
| GET | `/api/v1/dashboard/editor-activity` | Any | Editor events |
| GET | `/api/v1/dashboard/alerts` | Any | Alert list |
| GET | `/api/v1/dashboard/reports` | Any | Report list |
| GET | `/api/v1/analytics/productivity?days=&period=` | Any | Productivity scores |
| GET | `/api/v1/analytics/scores/{agent_id}` | Manager | Single agent score |
| GET | `/api/v1/analytics/trends/{agent_id}` | Manager | Agent trend |
| GET | `/api/v1/analytics/organization` | Manager | Org summary |
| GET | `/api/v1/analytics/live/{agent_id}` | Manager | Live score |
| GET | `/api/v1/teams` | Any | Team list (org-scoped) |
| GET | `/api/v1/users` | Manager+ | User list (org-scoped) |
| GET | `/api/v1/organizations` | Admin | All orgs |
| GET/POST | `/api/v1/productivity-rules` | Manager+ | List/create rules |
| PUT/DELETE | `/api/v1/productivity-rules/{id}` | Manager+ | Update/delete rule |
| POST | `/api/v1/notifications/send` | Manager | Send notification |
| GET | `/api/v1/notifications` | Any | Get notifications |
| POST | `/api/v1/reports/generate` | Manager | Generate report |
| GET | `/api/v1/reports/{id}` | Any | Report status |
| GET | `/api/v1/reports/{id}/download` | Any | Download report |

## Test results (latest)

```powershell
# Server: 53 pass / 1 skip (pre-existing test_login_dev_mode case mismatch)
# Agent:  77 pass
# Total: 130 pass (end-to-end: 15/15 pass)
```

## FIXES APPLIED (2026-06-24) — Dashboard Route & Login Page Fix

### Dashboard `__next_error__` crash fixed
**Root cause**: `basePath: "/dashboard"` in `next.config.ts` puts dashboard page at `out/dashboard/index.html` but the error page (`out/index.html`) was at root. Server mounted at `/dashboard` serving `web-ui/` root would serve `web-ui/index.html` (error page) at `/dashboard/`, causing `__next_error__` crash.

**Fix**: Post-build reorganization moves all page directories (`login/`, `devices/`, etc.) and `_next/` static assets inside `out/dashboard/`. Then `out/dashboard/*` is copied to `web-ui/`. The server mount at `/dashboard` from `web-ui/` root now serves the correct dashboard page at `/dashboard/`.

### Login page text invisibility fixed
Login page wrapped in `ThemeProvider` and uses theme-aware CSS variables (`text-foreground`, `bg-card`, `bg-input-bg`, `text-muted`) instead of hardcoded light background colors.

### Server mount validation improved
Updated `epms_server_service.py` mount logic to check for `index.html` existence before mounting, with clearer warning messages.

### Auth fixed — dev mode credentials
Server must run with `EPMS_DEV_MODE=true` and `EPMS_DEV_CREDENTIALS=<base64>` for dashboard login to work without a pre-seeded DB user. Login page defaults match the dev credentials (`admin@corp.local` / `MyP@ss1`).

### Dashboard route `/dashboard/dashboard` 404 fixed
**Root cause**: `app/dashboard/page.tsx` defined a separate `/dashboard` route, and `app/page.tsx` called `redirect("/dashboard/")`. With `basePath: "/dashboard"`, Next.js auto-prepends basePath to redirects, turning `redirect("/dashboard/")` into `redirect("/dashboard/dashboard/")` → 404.

**Fix**: Deleted `app/dashboard/page.tsx` and moved its dashboard content to `app/page.tsx`. The `/dashboard` route no longer exists; the dashboard is served at the `/` route (URL: `/dashboard/` via basePath). No post-build reorganization is needed — build output is flat, copy directly to `web-ui/`.

### Build command simplified
Post-build reorganization step removed since `/dashboard` route no longer exists. Build output is flat: copy `out/*` directly to `web-ui/`.

## Data model

```
users (AD-synced) ───> orgs
users ───> teams (via user_team_memberships)
process_events (raw heartbeats, short retention)
app_sessions (aggregated foreground sessions, dashboard)
afk_periods (idle time chunks)
productivity_rules (org-defined categories: productive/neutral/distracting)
productivity_scores (daily scores per agent)
alert_rules (manager-defined thresholds)
```

## Installed Skills

OpenCode skills are loaded automatically when tasks match their descriptions.

| Skill | Purpose | Auto-triggers on |
|-------|---------|------------------|
| `systematic-debugging` | Root cause analysis before fixing | Bugs, test failures, unexpected behavior |
| `python-testing` | pytest patterns, fixtures, mocking | Writing/fixing Python tests |
| `code-review-analysis` | Code quality review checklist | Code review requests |
| `browser-qa` | Browser testing workflows | UI/browser testing |
| `improve-codebase-architecture` | Refactoring patterns | Code organization, refactoring |
| `fullstack-developer` | Web dev (React, Node, DB) | Web app development |

**Install more:** `npx skills add <owner/repo@skill-name>`
**Browse:** https://skills.sh/

## FIXES APPLIED (2026-06-23) — All Data Flow Blockers Resolved

### Schema changes (applied to running PostgreSQL)
All child-table `agent_id` columns changed from `UUID` → `VARCHAR(255)`. FKs to `agents(id)` dropped:
- `agent_heartbeats`, `process_events`, `app_sessions` — already VARCHAR
- `browser_activity`, `editor_activity`, `activity_events`, `system_metrics`
- `productivity_scores`, `alerts`, `audit_log`

### Code fixes in `epms_server_service.py`
- `verify_api_key`: Enrollment token lookup uses `c.value #>> '{}'` instead of `::text` (fixes JSONB quoting)
- `register_agent`: INSERT/UPDATE now includes `organization_id` from `agent_identity`
- 10 dashboard JOINs: Changed `child.agent_id = a.id` → `child.agent_id::text = a.agent_id` (UUID → VARCHAR cast)
- `receive_browser_event`, `receive_editor_event`: Use `_parse_ts(event.timestamp)` to handle empty defaults
- Error handling added to browser/editor endpoints (try/except with logger.exception)
- Reports INSERT: Changed `config` column reference to `filters`
- Admin enrollment endpoints: `POST /api/v1/admin/enrollment-token` (generate) and `POST /api/v1/admin/enrollment-token/revoke`

### Agent fixes
- `api_client.py`: Persists `api_key` and `agent_id` to config via `save_config()` after registration

### Running server (port 8000, PID varies)
```
Health: {"status":"healthy","database":"connected","redis":"connected"}
Dashboard: All 10 endpoints return 200 with live agent data
```

## PHASE 4.5 — Dashboard Enhancement, Node Discovery, System Inventory & Theme Engine (2026-06-24)

Complete dashboard frontend overhaul — 22 pages, 8 themes, visual redesign, 4 new feature pages, 6 new backend API endpoints.

### What was built

#### 1. Theme Engine (8 themes)
- `lib/theme.ts` — 8 professionally designed themes with full color palettes
- `components/layout/ThemeProvider.tsx` — React context for theme management
- `components/ui/ThemeSwitcher.tsx` — Dropdown selector in sidebar + settings page
- Themes: Midnight Indigo (dark), Emerald City (dark), Sunset Ember (dark), Ocean Depths (dark), Royal Purple (dark), Forest Canopy (dark), Arctic Frost (light), Graphite (light)
- Persisted via `localStorage` key `epms_theme`
- CSS variables for each theme, applied via `data-theme` attribute on `<html>`
- Tailwind v4 integration via `@theme inline` mapping CSS vars to utility classes

#### 2. New Dashboard Pages (4 pages)

| Page | Route | Features |
|------|-------|----------|
| **Node Discovery & Inventory** | `/inventory/` | OS distribution, resource summary, asset counts, discovered nodes table, avg CPU/RAM/disk |
| **Device Health Overview** | `/health/` | Health distribution, anomaly detection, real-time metrics (CPU/memory/disk per device), health gauges |
| **Node Details** | `/nodes/?agent_id=` | Full system info, health gauges, performance index, installed software, running services, network interfaces |
| **Executive Overview** | `/executive/` | Org-wide summary, weekly comparison, needs-attention list, top performers, department breakdown, trend indicator |

#### 3. New API Endpoints (6 server-side)

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/api/v1/agent/inventory` | Agent sends system inventory snapshot (stored in agents.metadata JSONB) |
| GET | `/api/v1/inventory/summary` | Org-wide inventory summary (manager+) |
| GET | `/api/v1/inventory/detail/{agent_id}` | Full system inventory for a node (manager+) |
| GET | `/api/v1/health/devices` | All devices health overview (manager+) |
| GET | `/api/v1/health/detail/{agent_id}` | Single device health metrics (manager+) |
| GET | `/api/v1/health/anomalies` | Detected anomalies across devices (manager+) |
| GET | `/api/v1/executive/summary` | Executive-level org-wide summary (manager+) |

#### 4. Visual Redesign (all 22 pages)
- Dark-first design with `bg-card` / `text-foreground` / `text-muted` color system
- Glassmorphism via `.glass` CSS class (`backdrop-filter: blur(12px)`)
- `GlassCard` component with optional gradient border
- `GaugeChart` SVG component with animated arc
- `StatCard` with 3 variants: `default`, `glass`, `gradient`
- `Card` component with optional `title`/`action` slots
- Custom scrollbar styling
- Animations: `fadeIn`, `slideIn`, `pulse-glow`
- Gradient text and gradient backgrounds via CSS utility classes
- Consistent `hover:bg-table-row-hover` on all table rows
- `Badge` with 14 color variants
- All SVG icons replaced with Unicode symbols (no external icon deps)

#### 5. New UI Components

| Component | File | Purpose |
|-----------|------|---------|
| `GlassCard` | `components/ui/GlassCard.tsx` | Glassmorphism card with optional gradient border/hover |
| `GaugeChart` | `components/ui/GaugeChart.tsx` | SVG arc gauge (0-100%) with color thresholds |
| `ThemeSwitcher` | `components/ui/ThemeSwitcher.tsx` | Full/minimal theme selector dropdown |
| `Card` (enhanced) | `components/ui/Card.tsx` | Added title/action props |
| `StatCard` (enhanced) | `components/ui/StatCard.tsx` | Added 3 visual variants |

#### 6. New TypeScript Types
- `SystemInventory` — CPU, RAM, disk, OS, software, services, network
- `DeviceHealth` — health score, CPU/memory/disk %, uptime, alerts
- `HealthAnomaly` — anomaly detection data
- `ExecutiveSummary` — org-wide KPI summary
- `InventorySummary` — aggregated inventory stats
- Extended `Team`, `Organization`, `DashboardSummary` with optional count fields

#### 7. New API Client Methods
- `api.inventory.summary()`, `api.inventory.detail(agentId)`
- `api.health.devices()`, `api.health.detail(agentId)`, `api.health.anomalies()`
- `api.executive.summary()`

### Build commands (updated)
```powershell
# Build dashboard (for Phase 4.5 changes)
cd dashboard
npx next build
Copy-Item -Path "out\*" -Destination "..\activitywatch_Source code\epms-server-installer\Resources\services\web-ui\" -Recurse -Force
```

## License

MPL-2.0
