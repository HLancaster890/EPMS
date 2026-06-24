================================================================================
           EPMS ENTERPRISE — DUPLICATE FILES REPORT
           Generated: 2026-06-23 21:45 UTC
================================================================================

1. PyInstaller .spec FILES
--------------------------------------------------------------------------------
File                                    Location
epms-agent.spec (KEPT)                  epms-agent-client/epms-agent.spec
EPMS_Agent.spec (REMOVED)               Root: EPMS_Agent.spec

Analysis: The agent directory has its own .spec. The root-level
EPMS_Agent.spec was an older copy/alias. Kept the canonical copy.

2. ActivityWatch Vue.js Dashboard (aw-webui)
--------------------------------------------------------------------------------
The same Vue.js web UI existed in 3 places:
  aw-server/aw-webui/                   Original
  aw-server-rust/aw-webui/              Rust server copy
  aw-tauri/aw-webui/                    Tauri desktop copy

All 3 removed as part of AW directory cleanup. EPMS has its own
Next.js dashboard (completely different tech stack).

3. WiX Installer Sources (.wxs, .wxi)
--------------------------------------------------------------------------------
Server WiX source (KEPT):
  epms-server-installer/Bundle.wxs
  epms-server-installer/Product.wxs
  (and all other .wxs/.wxi files)

Agent WiX source (KEPT):
  epms-agent-client/Bundle.wxs
  epms-agent-client/Product.wxs
  (and all other .wxs/.wxi files)

Future MSI references in RELEASE (REMOVED):
  RELEASE/INSTALLERS/Future_MSI/Server/*.wxs
  RELEASE/INSTALLERS/Future_MSI/Client/*.wxs

Analysis: The Future_MSI sources in the old RELEASE directory were
development experiments. The canonical WiX sources are kept in each
component's own directory.

4. Deployment Scripts
--------------------------------------------------------------------------------
  RELEASE/INSTALLERS/deploy-epms.ps1                    (REMOVED - old RELEASE)
  RELEASE/INSTALLERS/health-check.ps1                   (REMOVED - old RELEASE)
  RELEASE/INSTALLERS/firewall.ps1                       (REMOVED - old RELEASE)
  RELEASE/INSTALLERS/validate-config.ps1                (REMOVED - old RELEASE)

These were copies of deployment scripts packaged in the old release.
Their canonical sources were never in the repo - they were generated
during release builds. No EPMS source references them.

5. Configuration Files
--------------------------------------------------------------------------------
  activitywatch_Source code/gptme.toml                  (REMOVED - AW tool config)
  opencode.json (KEPT)                                  Root

Analysis: gptme.toml was an AW AI assistant config. The EPMS project
uses opencode.json + skills-lock.json.

6. Documentation
--------------------------------------------------------------------------------
  activitywatch_Source code/README.md                   (REMOVED - AW README)
  AGENTS.md (KEPT)                                      Root

  activitywatch_Source code/LICENSE.txt                 (REMOVED - AGPL-3.0, AW)
  No EPMS license file (uses MPL-2.0 per AGENTS.md)

  activitywatch_Source code/CODE_OF_CONDUCT.md          (REMOVED - AW)
  activitywatch_Source code/CONTRIBUTING.md             (REMOVED - AW)
  activitywatch_Source code/SECURITY.md                 (REMOVED - AW)

7. Build Output: Dashboard
--------------------------------------------------------------------------------
  dashboard/out/                                        (KEPT - canonical build)
  epms-server-installer/Resources/services/web-ui/      (KEPT - deployed copy)

Analysis: Both contain the same static export. The canonical build is
dashboard/out/. The deployed copy is web-ui/. Both kept because the
build pipeline copies from one to the other.

================================================================================
