================================================================================
           EPMS ENTERPRISE — CLEANUP RECOMMENDATION REPORT
           Generated: 2026-06-23 21:45 UTC
================================================================================

Actions taken and remaining recommendations.

1. COMPLETED CLEANUP ACTIONS
--------------------------------------------------------------------------------
[✓] Moved all 13 ActivityWatch source directories to UNWANTED_FILES/
    (aw-client, aw-core, aw-notify, aw-qt, aw-server-rust, aw-server,
     aw-tauri, aw-watcher-afk, aw-watcher-input, aw-watcher-window,
     awatcher, dist, scripts)

[✓] Moved 17 AW root-level files to UNWANTED_FILES/
[✓] Moved AW .github/ CI workflows to UNWANTED_FILES/
[✓] Moved RELEASE/ (487 MB old build output) to UNWANTED_FILES/
[✓] Moved realease/ (74 MB misspelled build) to UNWANTED_FILES/
[✓] Moved setup release/ (256 MB NSIS installers) to UNWANTED_FILES/
[✓] Moved 12 root-level stale files (.spec, .sed, logs, etc.) to UNWANTED_FILES/
[✓] Moved 3 empty directories (-ConfigDir, -InstallDir, -Silent) to UNWANTED_FILES/
[✓] Moved root build/outputs/logs directories to UNWANTED_FILES/
[✓] Moved .pytest_cache and .wix to UNWANTED_FILES/
[✓] Moved 6 old microservice PyInstaller directories from Resources/
[✓] Moved 6 old microservice .exe files from Resources/
[✓] Moved 10 stub/placeholder files to UNWANTED_FILES/
[✓] Moved Config/nginx.conf.template to UNWANTED_FILES/
[✓] Moved 13 dead .pyc files from __pycache__ to UNWANTED_FILES/
[✓] Moved server-installer build/, dist/, reports/ to UNWANTED_FILES/
[✓] Moved agent build/, dist/, egg-info, Config, caches to UNWANTED_FILES/
[✓] Moved test-results.xml to UNWANTED_FILES/
[✓] Generated 6 audit reports as .md files

Total space reclaimed: 2,537 MB (7,723 files)

2. REMAINING RECOMMENDATIONS
--------------------------------------------------------------------------------

HIGH PRIORITY:
--------------
1. UPDATE Variables.wxi
   The WiX installer variables still reference the old 6-service
   architecture. Before building a release MSI, update:
   - Service names → single "EPMS-Server" service
   - Ports → port 8000 only
   - Remove Redis/NATS references
   - File: epms-server-installer/Variables.wxi

2. UPDATE .wxs SERVICE DEFINITIONS
   Services.wxs currently defines 6 Windows services. Update to 1:
   - epms-server on port 8000
   - File: epms-server-installer/Services.wxs

3. UPDATE build.bat FOR CONSOLIDATED ARCHITECTURE
   The batch build script references old service binaries.
   Update to build only the single consolidated server.
   - File: epms-server-installer/build.bat

4. UPDATE BUILD-RELEASE.PS1
   Remove fallback references to "realease/" directory.
   - File: root/build-release.ps1

MEDIUM PRIORITY:
----------------
5. UPDATE Database.wxs
   The database setup custom action may reference old service accounts.
   Verify it creates the correct PostgreSQL role for single-service auth.

6. REMOVE UNWANTED_FILES/ ONCE VALIDATED
   After verifying the cleaned repo builds and deploys correctly,
   the UNWANTED_FILES/ directory can be deleted.

7. ADD REAL POSTGRESQL INSTALLER
   The bundled PostgreSQL installer is a 5-byte stub. Before any
   production release, replace with actual EDB PostgreSQL 16.4
   Windows x64 installer.

LOW PRIORITY:
-------------
8. EVALUATE LICENSE FILE
   EPMS uses MPL-2.0 (per AGENTS.md) but no LICENSE file exists
   in the repo. Consider adding one.

9. ADD README.md
   The original AW README was removed. EPMS could benefit from
   a project-specific README.

10. EVALUATE dashboard/out/ RETENTION
    The out/ directory (166 files) is a build artifact. It can
    be regenerated with `npm run build`. Consider adding to
    .gitignore and deleting, or keeping for convenience.

11. EVALUATE .agents/skills/ RETENTION
    309 files for AI skills. These are for OpenCode tooling, not
    the EPMS application itself. Consider if they belong in the
    project repo or should be user-local.

3. FILES MOVED BUT POTENTIALLY NEEDED
--------------------------------------------------------------------------------
The following files were moved because they appeared to be build
artifacts. Verify before final deletion:

  agent/dist/EPMS_Agent_Setup_v1.0.0.0.exe   (33 MB) - Compiled installer
  agent/dist/EPMS_Agent_Core.msi              (5-10 MB) - Compiled MSI
  agent/dist/epms-agent.exe                    (10+ MB) - PyInstaller binary

These CAN be regenerated from source (pyinstaller + wix build),
so keeping only source is correct.

================================================================================
