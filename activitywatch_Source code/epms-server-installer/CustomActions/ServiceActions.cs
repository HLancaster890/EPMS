// EPMS Enterprise Server — NSSM Service Registration Custom Actions
// These actions run during WiX installation to register Windows Services via NSSM.

using System;
using System.Diagnostics;
using System.IO;
using Microsoft.Win32;
using WixToolset.Dtf.WindowsInstaller;

namespace EPMS.CustomActions
{
    public class ServiceActions
    {
        /// <summary>
        /// Registers all EPMS services using NSSM service wrapper.
        /// Called during install sequence (deferred, impersonate=no).
        /// </summary>
        [CustomAction]
        public static ActionResult InstallNSSMServices(Session session)
        {
            session.Log("Registering EPMS services via NSSM...");

            try
            {
                string installPath = session.CustomActionData["INSTALLFOLDER"];
                string logPath = session.CustomActionData["EPMSLOGFOLDER"];
                string nssmPath = Path.Combine(installPath, "nssm", "nssm.exe");

                if (!File.Exists(nssmPath))
                {
                    session.Log($"NSSM not found at: {nssmPath}");
                    return ActionResult.Failure;
                }

                // Service definitions: name, displayName, description, binary, port
                var services = new[]
                {
                    new {
                        Name = "EPMS-API",
                        Display = "EPMS REST API Service",
                        Desc = "FastAPI-based REST API gateway for the EPMS Enterprise Productivity Management System",
                        Binary = Path.Combine(installPath, @"bin\services\epms-api.exe"),
                        Port = "8000"
                    },
                    new {
                        Name = "EPMS-EventProcessor",
                        Display = "EPMS Event Processing Service",
                        Desc = "High-throughput event ingestion and processing pipeline with offline replay",
                        Binary = Path.Combine(installPath, @"bin\services\epms-event-processor.exe"),
                        Port = "8004"
                    },
                    new {
                        Name = "EPMS-Analytics",
                        Display = "EPMS Analytics Service",
                        Desc = "Productivity analytics, aggregation, and trend computation service",
                        Binary = Path.Combine(installPath, @"bin\services\epms-analytics.exe"),
                        Port = "8001"
                    },
                    new {
                        Name = "EPMS-Reporting",
                        Display = "EPMS Reporting Service",
                        Desc = "Enterprise report generation engine supporting PDF, Excel, and CSV output",
                        Binary = Path.Combine(installPath, @"bin\services\epms-reporting.exe"),
                        Port = "8002"
                    },
                    new {
                        Name = "EPMS-Notifications",
                        Display = "EPMS Notification Service",
                        Desc = "Multi-channel notification delivery service supporting email, in-app, and push",
                        Binary = Path.Combine(installPath, @"bin\services\epms-notifications.exe"),
                        Port = "8003"
                    },
                    new {
                        Name = "EPMS-AgentGateway",
                        Display = "EPMS Agent Gateway Service",
                        Desc = "mTLS-secured WebSocket gateway for real-time agent communication",
                        Binary = Path.Combine(installPath, @"bin\services\epms-agent-gateway.exe"),
                        Port = "8005"
                    }
                };

                foreach (var svc in services)
                {
                    if (!File.Exists(svc.Binary))
                    {
                        session.Log($"  ⚠ Binary not found, skipping: {svc.Binary}");
                        continue;
                    }

                    session.Log($"  Registering service: {svc.Name}");

                    // Remove existing service if present (for upgrades)
                    RunNSSM(nssmPath, $"stop {svc.Name} confirm", true);
                    RunNSSM(nssmPath, $"remove {svc.Name} confirm", true);

                    // Install service
                    RunNSSM(nssmPath, $"install {svc.Name} \"{svc.Binary}\"");

                    // Configure service
                    RunNSSM(nssmPath, $"set {svc.Name} DisplayName \"{svc.Display}\"");
                    RunNSSM(nssmPath, $"set {svc.Name} Description \"{svc.Desc}\"");
                    RunNSSM(nssmPath, $"set {svc.Name} AppDirectory \"{Path.GetDirectoryName(svc.Binary)}\"");
                    RunNSSM(nssmPath, $"set {svc.Name} AppStdout \"{logPath}\\{svc.Name.ToLower()}-stdout.log\"");
                    RunNSSM(nssmPath, $"set {svc.Name} AppStderr \"{logPath}\\{svc.Name.ToLower()}-stderr.log\"");
                    RunNSSM(nssmPath, $"set {svc.Name} AppRotateFiles 1");
                    RunNSSM(nssmPath, $"set {svc.Name} AppRotateSeconds 86400");
                    RunNSSM(nssmPath, $"set {svc.Name} AppRotateBytes 10485760");
                    RunNSSM(nssmPath, $"set {svc.Name} AppThrottle 5000");
                    RunNSSM(nssmPath, $"set {svc.Name} AppStopMethodSkip 6");
                    RunNSSM(nssmPath, $"set {svc.Name} AppRestartDelay 10000");
                    RunNSSM(nssmPath, $"set {svc.Name} Start SERVICE_AUTO_START");
                    RunNSSM(nssmPath, $"set {svc.Name} ObjectName \"NT AUTHORITY\\NETWORKSERVICE\"");

                    session.Log($"  ✓ {svc.Name} registered successfully");
                }

                // Start all services
                session.Log("Starting EPMS services...");
                foreach (var svc in services)
                {
                    if (File.Exists(svc.Binary))
                    {
                        RunNSSM(nssmPath, $"start {svc.Name}", true);
                        session.Log($"  → {svc.Name} started");
                    }
                }

                session.Log("All EPMS services registered and started.");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Service registration error: {ex.Message}");
                return ActionResult.Failure;
            }
        }

        /// <summary>
        /// Removes all EPMS services during uninstall.
        /// Falls back to reading INSTALLFOLDER from registry if CustomActionData
        /// is not populated (which happens on uninstall since SaveInstallProperties
        /// only fires during install/reinstall).
        /// </summary>
        [CustomAction]
        public static ActionResult RemoveNSSMServices(Session session)
        {
            session.Log("Removing EPMS services...");
            try
            {
                // Try CustomActionData first (populated by SaveInstallProperties on install)
                string installPath = session.CustomActionData["INSTALLFOLDER"];

                // Fall back to registry if CustomActionData is empty (uninstall path)
                if (string.IsNullOrEmpty(installPath))
                {
                    session.Log("CustomActionData INSTALLFOLDER not found, reading from registry...");
                    try
                    {
                        using (var key = Registry.LocalMachine.OpenSubKey(@"SOFTWARE\EPMS\Server"))
                        {
                            if (key != null)
                            {
                                installPath = key.GetValue("InstallPath") as string;
                                session.Log($"  Read from registry: {installPath}");
                            }
                        }
                    }
                    catch (Exception regEx)
                    {
                        session.Log($"  Registry read failed: {regEx.Message}");
                    }
                }

                // If still empty, try default install location
                if (string.IsNullOrEmpty(installPath))
                {
                    installPath = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                        "EPMS Inc", "EPMS Server");
                    session.Log($"  Using default path: {installPath}");
                }

                // Locate NSSM — try the install path first, then PATH
                string nssmPath = Path.Combine(installPath, "nssm", "nssm.exe");
                if (!File.Exists(nssmPath))
                {
                    session.Log($"NSSM not found at {nssmPath}, checking PATH...");
                    // Try finding nssm in PATH
                    try
                    {
                        var whichProc = Process.Start(new ProcessStartInfo
                        {
                            FileName = "where",
                            Arguments = "nssm.exe",
                            UseShellExecute = false,
                            RedirectStandardOutput = true,
                            CreateNoWindow = true
                        });
                        string pathResult = whichProc.StandardOutput.ReadLine();
                        whichProc.WaitForExit(5000);
                        if (!string.IsNullOrEmpty(pathResult) && File.Exists(pathResult))
                        {
                            nssmPath = pathResult;
                            session.Log($"  Found NSSM in PATH: {nssmPath}");
                        }
                    }
                    catch
                    {
                        // Ignore — will try sc.exe fallback below
                    }
                }

                string[] serviceNames = {
                    "EPMS-API", "EPMS-EventProcessor", "EPMS-Analytics",
                    "EPMS-Reporting", "EPMS-Notifications", "EPMS-AgentGateway"
                };

                if (File.Exists(nssmPath))
                {
                    session.Log($"Using NSSM at: {nssmPath}");
                    foreach (var name in serviceNames)
                    {
                        RunNSSM(nssmPath, $"stop {name} confirm", true);
                        RunNSSM(nssmPath, $"remove {name} confirm", true);
                        session.Log($"  ✓ {name} removed via NSSM");
                    }
                }
                else
                {
                    // Fallback: use sc.exe to stop and delete services directly
                    session.Log("NSSM not available, using sc.exe fallback for service removal...");
                    foreach (var name in serviceNames)
                    {
                        try
                        {
                            // Stop service
                            Process.Start(new ProcessStartInfo
                            {
                                FileName = "sc",
                                Arguments = $"stop \"{name}\"",
                                UseShellExecute = false,
                                CreateNoWindow = true
                            })?.WaitForExit(10000);

                            // Delete service
                            var deleteProc = Process.Start(new ProcessStartInfo
                            {
                                FileName = "sc",
                                Arguments = $"delete \"{name}\"",
                                UseShellExecute = false,
                                RedirectStandardOutput = true,
                                CreateNoWindow = true
                            });
                            string output = deleteProc?.StandardOutput.ReadToEnd();
                            deleteProc?.WaitForExit(10000);

                            if (output?.Contains("SUCCESS") == true)
                                session.Log($"  ✓ {name} removed via sc.exe");
                            else
                                session.Log($"  ⚠ {name} may not have been removed: {output?.Trim()}");
                        }
                        catch (Exception scEx)
                        {
                            session.Log($"  ⚠ Failed to remove {name}: {scEx.Message}");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                session.Log($"Service removal error: {ex.Message}");
            }
            return ActionResult.Success;
        }

        /// <summary>
        /// Saves installation properties into CustomActionData for deferred actions.
        /// This immediate action runs before any deferred actions that need install-time values.
        /// </summary>
        [CustomAction]
        public static ActionResult SaveInstallProperties(Session session)
        {
            session.Log("Saving installation properties for deferred actions...");

            try
            {
                // Read all properties from the session and write to CustomActionData
                string[] props = {
                    "INSTALLFOLDER", "EPMS_BIND_ADDRESS", "EPMS_PORT", "EPMS_DOMAIN",
                    "EPMS_SSL_MODE", "EPMS_DB_HOST", "EPMS_DB_PORT", "EPMS_DB_PASSWORD",
                    "EPMS_ADMIN_EMAIL", "EPMS_ADMIN_PASSWORD", "EPMS_ORGANIZATION",
                    "EPMS_INSTALL_TYPE", "EPMS_INSTALL_POSTGRESQL"
                };

                foreach (var prop in props)
                {
                    string val = session[prop];
                    if (!string.IsNullOrEmpty(val))
                    {
                        session.CustomActionData[prop] = val;
                        session.Log($"  {prop} = {val}");
                    }
                }

                // Derive derived paths
                string installPath = session["INSTALLFOLDER"];
                session.CustomActionData["INSTALLFOLDER"] = installPath;
                session.CustomActionData["EPMSLOGFOLDER"] = 
                    Environment.ExpandEnvironmentVariables(@"%ProgramData%\EPMS\Logs");

                session.Log("Installation properties saved successfully.");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Error saving properties: {ex.Message}");
                return ActionResult.Failure;
            }
        }

        private static void RunNSSM(string nssmPath, string arguments, bool ignoreErrors = false)
        {
            var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = nssmPath,
                    Arguments = arguments,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                }
            };

            process.Start();
            process.WaitForExit(30000);

            if (!ignoreErrors && process.ExitCode != 0)
            {
                string error = process.StandardError.ReadToEnd();
                throw new Exception($"NSSM command failed (exit {process.ExitCode}): {arguments}\nError: {error}");
            }
        }
    }
}
