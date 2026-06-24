================================================================================
           EPMS ENTERPRISE — REPOSITORY AUDIT REPORT
           Generated: 2026-06-23 21:45 UTC
================================================================================

1. REPOSITORY OVERVIEW
--------------------------------------------------------------------------------
Root path:          D:\activitywatch
Total size before:  ~3.2 GB
Total size after:   ~600 MB
Files removed:      7,723
Dirs removed:       1,716
Space reclaimed:    2,537 MB

2. REMAINING STRUCTURE
--------------------------------------------------------------------------------
D:\activitywatch\
├── .agents/skills/                  OpenCode AI skills (309 files, 1.3 MB)
├── activitywatch_Source code/
│   ├── epms-agent-client/           EPMS Agent (source + tests + WiX)
│   └── epms-server-installer/       EPMS Server (source + tests + WiX + dashboard)
│   ├── EPMS_Installation_Guide.md   Documentation
│   └── RELEASE_NOTES.md             Documentation
├── dashboard/                       Next.js dashboard source + build
├── sandbox/                         Testing/simulation scripts
├── UNWANTED_FILES/                  Archived unused files (7,723 files)
├── AGENTS.md                        Project documentation
├── build-release.ps1               Build orchestrator
├── COMMANDS.md                      Command reference
├── DEPLOYMENT.md                    Deployment guide
├── opencode.json                    OpenCode config
├── skills-lock.json                 Skills manifest
├── STACK.md                         Technology stack
├── start-epms-consolidated.bat     Consolidated server launcher
└── TROUBLESHOOTING.md               Troubleshooting guide

3. MAJOR CLASSIFICATIONS
--------------------------------------------------------------------------------
Category A (Required):  ~500 files (source, tests, configs, build scripts)
Category B (Unused):    7,723 files (moved to UNWANTED_FILES/)
Category C (Review):    0 files (all conclusively classified)

4. KEY FINDINGS
--------------------------------------------------------------------------------
1. The EPMS codebase is entirely independent from ActivityWatch.
   Zero imports, zero shared dependencies, zero compatibility requirements.
   All 13 aw-* directories were completely unused.

2. The build-release.ps1 references "realease/" (misspelled) directory.
   This directory had old build artifacts. The build script falls back
   to PyInstaller directly when this directory is absent.

3. The WiX installer (Variables.wxi) still describes the old 6-service
   architecture. The MSI output in dist/ was outdated. Source .wxs files
   were kept but need updating to target the consolidated single service.

4. 6 old microservice PyInstaller builds (~60 MB) existed in Resources/
   alongside 6 __pycache__ .pyc files from deleted source files.

5. Stub/placeholder files for PostgreSQL, nginx, redis, nats, nssm
   (each containing just "stub") were taking up no meaningful space
   but were misleading about actual dependencies.
================================================================================
