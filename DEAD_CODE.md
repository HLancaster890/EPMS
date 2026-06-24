================================================================================
           EPMS ENTERPRISE — DEAD CODE REPORT
           Generated: 2026-06-23 21:45 UTC
================================================================================

1. OLD MICROSERVICE SOURCE FILES (deleted before this audit)
--------------------------------------------------------------------------------
The following source files had already been deleted during the
consolidation phase. Only __pycache__ bytecode remained:
  Resources/services/epms_api_service.py
  Resources/services/epms_analytics_service.py
  Resources/services/epms_event_processor_service.py
  Resources/services/epms_gateway_service.py
  Resources/services/epms_notifications_service.py
  Resources/services/epms_reporting_service.py

Their compiled .pyc files (found in __pycache__) have now been moved
to UNWANTED_FILES.

2. OLD MICROSERVICE TEST FILES (deleted before this audit)
--------------------------------------------------------------------------------
  tests/test_api_service.py
  tests/test_analytics_service.py
  tests/test_event_processor_service.py
  tests/test_gateway_service.py
  tests/test_notifications_service.py
  tests/test_reporting_service.py

Only __pycache__ bytecode remained. Moved to UNWANTED_FILES.

3. NATS CONNECTION MODULE
--------------------------------------------------------------------------------
  Resources/epms_common/nats_conn.py (deleted)
  Resources/epms_common/__pycache__/nats_conn.cpython-314.pyc (moved)

The NATS transport layer was removed during the REST-only migration.
Only a .pyc orphan remained.

4. MISSING COLUMN AND SCHEMA ISSUES (fixed in earlier sessions)
--------------------------------------------------------------------------------
- agent_heartbeats.agent_id FK to agents.id (broken JOIN, fixed)
- Missing browser_activity.is_productive column (added)
- Missing productivity_scores.hb_count column (added)
- Missing teams table (created)
- Missing productivity_rules table (created)

5. OLD MICROSERVICE BUILD OUTPUT (compiled exes)
--------------------------------------------------------------------------------
6 PyInstaller-built executables existed in Resources/:
  epms-agent-gateway.exe (10.1 MB)
  epms-analytics.exe (10.1 MB)
  epms-api.exe (10.1 MB)
  epms-event-processor.exe (8.8 MB)
  epms-notifications.exe (8.8 MB)
  epms-reporting.exe (8.7 MB)

Each was a frozen Python executable for the old architecture. All
replaced by the single epms_server_service.py → epms-server.exe.

6. STUB FILES MASQUERADING AS DEPENDENCIES
--------------------------------------------------------------------------------
9 files containing only the text "stub" (5 bytes each):
  nginx.exe, nssm.exe, redis-server.exe, redis-cli.exe,
  nats-server.exe, postgresql-16.4-1-windows-x64.exe,
  dotnet8_runtime, vcpp_2022_x64, license.rtf

These were placeholders for binaries that are either:
- Not needed (nginx, nssm, nats)
- Optional (redis)
- Need real binary before release (postgresql)

7. VARIABLES.WXI — STALE CONFIGURATION
--------------------------------------------------------------------------------
File: epms-server-installer/Variables.wxi (KEPT but needs update)
The WiX variables still define:
  - 6 separate services (EPMS-API, EPMS-Analytics, etc.)
  - Ports 8000-8005 for each microservice
  - Redis at port 6379
  - NATS at port 4222

This needs to be updated to match the consolidated single-service
architecture before building a release MSI.

8. OLD LAUNCH SCRIPTS
--------------------------------------------------------------------------------
  root/start-epms.bat                          Launches 3 separate services
  RELEASE/INSTALLERS/Server/Scripts/install-server-services.ps1  (6 services)

Both reference the old multi-service architecture.
start-epms.bat moved to UNWANTED_FILES.
install-server-services.ps1 moved as part of RELEASE/.

================================================================================
