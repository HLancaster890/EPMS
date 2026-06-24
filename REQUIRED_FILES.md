================================================================================
           EPMS ENTERPRISE — REQUIRED FILES REPORT
           Generated: 2026-06-23 21:45 UTC
================================================================================

All files classified as Category A (Required) — actively used by
production, build, test, or deployment processes.

1. EPMS SERVER SOURCE (epms-server-installer)
--------------------------------------------------------------------------------
Main Application:
  Resources/services/epms_server_service.py     Consolidated FastAPI service
  Resources/services/live_demo.py               Demo data generator
  Resources/services/web-ui/                    Deployed dashboard (18 pages)
  services/epms-server.spec                     PyInstaller spec

Shared Library (epms_server/):
  Resources/epms_server/__init__.py
  Resources/epms_server/config.py               JWT, Redis, token config
  Resources/epms_server/rbac.py                 Role-based access control
  Resources/epms_server/ad_login.py             AD/LDAP integration
  Resources/epms_server/aggregation.py          Background aggregation worker

Common Library (epms_common/):
  Resources/epms_common/__init__.py
  Resources/epms_common/db.py                   asyncpg connection pool
  Resources/epms_common/middleware.py            CORS middleware
  Resources/epms_common/redis_cache.py           Optional Redis wrapper
  Resources/epms_common/settings.py             Shared settings

Configuration:
  Config/appsettings.json                       Default config
  Config/appsettings.json.template              Production template
  Config/epms.yaml.template                     YAML config template
  Config/logging.yaml.template                  Logging config template
  Config/sql/001_initial_schema.sql             DB schema
  Config/sql/002_indexes_and_retention.sql      Indexes + retention
  Config/sql/002_seed_data.sql                  Seed data
  Config/sql/003_indexes.sql                    Additional indexes
  Config/sql/003_process_events.sql             Process events schema

Custom Actions (C#/DTF):
  CustomActions/AdminActions.cs
  CustomActions/ConfigActions.cs
  CustomActions/DatabaseActions.cs
  CustomActions/ServiceActions.cs
  CustomActions/ValidationActions.cs
  CustomActions/EPMS.CustomActions.csproj

WiX Installer:
  Bundle.wxs, Product.wxs, Services.wxs
  UI.wxs, Firewall.wxs, Database.wxs, CustomActions.wxs
  Variables.wxi, epms-server.wixproj
  build.bat, build-services.ps1

Tests:
  tests/conftest.py
  tests/test_consolidated_server.py
  tests/requirements-test.txt

CI/CD:
  .github/workflows/build.yml

Other:
  scripts/generate_bmp_stubs.py
  Resources/logo.ico

2. EPMS AGENT SOURCE (epms-agent-client)
--------------------------------------------------------------------------------
Agent Package (epms_agent/):
  epms_agent/__init__.py
  epms_agent/__main__.py                        CLI entry point
  epms_agent/monitor.py                         Process scanner + AFK detection
  epms_agent/api_client.py                      Async HTTP client
  epms_agent/rest_client.py                     REST transport layer
  epms_agent/config.py                          Agent configuration
  epms_agent/browser_monitor.py                 Browser activity monitor
  epms_agent/editor_monitor.py                  Editor activity monitor
  epms_agent/event_buffer.py                    SQLite offline buffer
  epms_agent/systray.py                         Windows system tray

Build & Install:
  epms-agent.spec                               PyInstaller spec
  pyproject.toml                                Project config + dependencies
  Product.wxs, Bundle.wxs, Variables.wxi         WiX installer source
  epms-agent.wixproj                            WiX project file
  Resources/logo.ico

Tests:
  tests/__init__.py
  tests/conftest.py
  tests/test_api_client.py
  tests/test_event_buffer.py
  tests/test_rest_client.py

3. DASHBOARD (dashboard/)
--------------------------------------------------------------------------------
Source:
  app/ (18 page files + layout.tsx + globals.css + favicon.ico)
  components/layout/Sidebar.tsx, Header.tsx
  components/ui/Card.tsx, StatCard.tsx, Badge.tsx, LoadingSpinner.tsx,
    TimePeriodSelector.tsx
  components/charts/LineChart.tsx, BarChart.tsx, DoughnutChart.tsx,
    TimelineChart.tsx
  components/features/ActivityTable.tsx, DeviceTable.tsx,
    AlertsPanel.tsx, ProductivityScore.tsx
  lib/api.ts, lib/types.ts, lib/store.ts, lib/providers.tsx
  public/ (5 SVG files)

Config:
  package.json, next.config.ts, tsconfig.json
  postcss.config.mjs, eslint.config.mjs

Build Output:
  out/ (166 files — static export deployed to web-ui)

4. BUILD & DEPLOYMENT SCRIPTS (root)
--------------------------------------------------------------------------------
  build-release.ps1                             Full release build orchestrator
  start-epms-consolidated.bat                   Developer launcher
  AGENTS.md                                     Project documentation
  COMMANDS.md, DEPLOYMENT.md, STACK.md          Supporting docs
  TROUBLESHOOTING.md

5. SANDBOX (sandbox/)
--------------------------------------------------------------------------------
  seed_data.py, heartbeat_simulator.py          Test data + heartbeat sim
  test_all_endpoints.py                         API endpoint test suite
  start_server.ps1, start_server.cmd            Server starters
  run_sandbox.ps1                               Orchestrator
  check_hash.py                                 Utility
  server.log, server.err                        Runtime logs

6. CONFIGURATION
--------------------------------------------------------------------------------
  opencode.json, skills-lock.json               OpenCode AI config
  .agents/skills/                               Installed AI skills

Total Required Files: ~500
================================================================================
