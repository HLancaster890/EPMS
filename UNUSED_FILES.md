================================================================================
           EPMS ENTERPRISE — UNUSED FILES REPORT
           Generated: 2026-06-23 21:45 UTC
================================================================================

All files classified as Category B (Unused/Obsolute) — moved to
UNWANTED_FILES/. Total: 7,723 files, 2,537 MB.

1. ACTIVITYWATCH SOURCE CODE (13 directories, 972+ files)
--------------------------------------------------------------------------------
ALL ActivityWatch code was completely unused by EPMS. Zero imports,
zero shared dependencies, zero compatibility requirements.

Directory           Files     Purpose
aw-client/          33        AW Python client library
aw-core/            70        AW core data model + datastore
aw-notify/          15        AW Rust notification daemon
aw-qt/              32        AW PyQt5 systray/process manager
aw-server-rust/     275       AW Rust server rewrite + Vue.js web UI
aw-server/          202       AW Python Flask server + Vue.js web UI
aw-tauri/           184       AW Tauri desktop app + Vue.js web UI
aw-watcher-afk/     21        AW AFK watcher
aw-watcher-input/   18        AW keyboard/mouse watcher
aw-watcher-window/  25        AW foreground window watcher
awatcher/           42        Third-party Rust watcher (Linux)
dist/               21        AW distribution archives
scripts/            34        AW build/packaging scripts

Why moved: Legacy ActivityWatch open-source code. EPMS is a
completely independent codebase with its own:
- Data model (relational schema vs AW's bucket/event model)
- Transport (REST-only vs AW's WebSocket)
- Agent (psutil-based process scanner vs AW's per-window watcher)
- Dashboard (Next.js/React vs AW's Vue.js)
- Auth (AD/LDAP + JWT vs AW's API keys)

2. ACTIVITYWATCH ROOT-LEVEL FILES (17+ files)
--------------------------------------------------------------------------------
File                         Why moved
aw.spec                      PyInstaller spec for AW server
Makefile                     AW build targets
poetry.lock                  AW Python dependency lock
pyproject.toml               AW project config (name="activitywatch")
README.md                    AW project README
CITATION.cff                 AW citation metadata
CODE_OF_CONDUCT.md           AW code of conduct
CONTRIBUTING.md              AW contribution guide
LICENSE.txt                  AW license (AGPL-3.0, EPMS uses MPL-2.0)
SECURITY.md                  AW security policy
diagram.svg                  AW architecture diagram
dist.zip                     AW distribution archive
gptme.toml                   AW AI assistant config
.tool-versions               AW tool version spec
.gitattributes               AW git attributes
.gitmodules                  AW submodule pointers
.github/                     AW CI workflows (15 files)
MULTINODE_SETUP.md           AW multi-node deployment guide

3. EPMS BUILD ARTIFACTS — OUTDATED RELEASES
--------------------------------------------------------------------------------
Directory/File        Size     Why moved
RELEASE/              487 MB   Release build from old 6-service architecture
                               Contains 6 separate PyInstaller COLLECT dirs
                               (epms-api, epms-analytics, epms-gateway, etc.)
                               plus NSIS installers, deployment scripts, docs.
                               The consolidated single-service replaces this.

realease/              74 MB   Misspelled alternate build directory with
                               old PyInstaller outputs (epms-gateway-server,
                               epms-agent-client). Referenced by build-release.ps1
                               as fallback only.

setup release/        256 MB   NSIS installer source + compiled .exe files.
                               Server (188 MB) + Client (33 MB) installers.
                               WiX-based installers replace NSIS.

4. EPMS SERVER-INSTALLER BUILD ARTIFACTS
--------------------------------------------------------------------------------
Path                              Size    Why moved
Resources/epms-agent-gateway/     10.5 MB Old microservice PyInstaller
Resources/epms-analytics/         10.5 MB Old microservice PyInstaller
Resources/epms-api/               10.1 MB Old microservice PyInstaller
Resources/epms-event-processor/    8.8 MB Old microservice PyInstaller
Resources/epms-notifications/      8.8 MB Old microservice PyInstaller
Resources/epms-reporting/          8.7 MB Old microservice PyInstaller
Resources/epms-agent-gateway.exe  10.1 MB Old microservice binary
Resources/epms-analytics.exe      10.1 MB Old microservice binary
Resources/epms-api.exe            10.1 MB Old microservice binary
Resources/epms-event-processor.exe 8.8 MB Old microservice binary
Resources/epms-notifications.exe   8.8 MB Old microservice binary
Resources/epms-reporting.exe       8.7 MB Old microservice binary
build/                              ~60 MB PyInstaller work directory (6 services)
dist/                               ~10 MB Compiled MSI for old 6-service arch
reports/                            ~1 MB  22 runtime-generated CSV files
services/server_stderr.log                  Runtime log artifact
services/server_stdout.log                  Runtime log artifact

5. PLACEHOLDER/STUB FILES (not needed)
--------------------------------------------------------------------------------
File                            Content     Why moved
nginx.exe                       "stub"      NGINX not used (FastAPI serves directly)
nssm.exe                        "stub"      NSSM not used (WiX handles services)
redis-server.exe                "stub"      Redis optional, binary not shipped
redis-cli.exe                   "stub"      Not needed
redis.conf.template             config      Not needed (Redis optional)
nats-server.exe                 "stub"      NATS not used in consolidated arch
nats.conf.template              config      Not used
postgresql-16.4-1-windows-x64.exe "stub"    Placeholder for real PostgreSQL installer
dotnet8_runtime/                stub       .NET runtime stub
vcpp_2022_x64/                  stub       VC++ redist stub
license.rtf                     "stub"      Placeholder (5 bytes)
Config/nginx.conf.template      config      NGINX not used

6. DEAD BYTECODE (__pycache__ remnants)
--------------------------------------------------------------------------------
File
services/__pycache__/epms_analytics_service.cpython-314.pyc
services/__pycache__/epms_api_service.cpython-314.pyc
services/__pycache__/epms_event_processor_service.cpython-314.pyc
services/__pycache__/epms_gateway_service.cpython-314.pyc
services/__pycache__/epms_notifications_service.cpython-314.pyc
services/__pycache__/epms_reporting_service.cpython-314.pyc
epms_common/__pycache__/nats_conn.cpython-314.pyc
tests/__pycache__/test_analytics_service.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_api_service.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_event_processor_service.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_gateway_service.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_notifications_service.cpython-314-pytest-9.1.1.pyc
tests/__pycache__/test_reporting_service.cpython-314-pytest-9.1.1.pyc

7. AGENT BUILD ARTIFACTS
--------------------------------------------------------------------------------
File                        Why moved
build/                      PyInstaller work directory (14 files)
dist/                       Compiled .exe + .msi (outdated build)
epms_agent.egg-info/        pip install -e metadata
Config/                     Empty placeholder directory
.hypothesis/                Hypothesis test cache
.pytest_cache/              Pytest cache
test-results.xml            Old test results
Resources/WixStandardBootstrapperApplication  WiX BA binary (not needed standalone)

8. ROOT-LEVEL STALE FILES
--------------------------------------------------------------------------------
File                        Why moved
EPMS_Agent.spec             Duplicate (agent has its own in epms-agent.spec)
EPMS_Gateway.spec           Old gateway service, not used
EPMS_Client_Setup.sed       NSIS project file (NSIS replaced by WiX)
test_client.sed             NSIS test project file
dump.rdb                    Redis dump (164 bytes, empty)
api_stderr.log              Empty runtime log
api_stdout.log              Empty runtime log
epms-server-stderr.log      Empty runtime log
epms-server-stdout.log      Empty runtime log
start                       Text file "postgresql-x64-16"
stop                        Text file "postgresql-x64-16"
start-epms.bat              Old multi-service launcher (replaced by -consolidated)
build/                      59 MB PyInstaller work + NATS binary + logs
outputs/                    Architecture planning documents (tech-stack, etc.)
logs/gateway.log             Gateway runtime log
-ConfigDir/                 Empty deployment placeholder
-InstallDir/                Empty deployment placeholder
-Silent/                    Empty deployment placeholder
.pytest_cache/              Root-level test cache
.wix/                       Empty WiX cache

================================================================================
