// EPMS Enterprise Server — Validation Custom Actions

using System;
using System.Diagnostics;
using System.Net.Http;
using System.Net.Sockets;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using WixToolset.Dtf.WindowsInstaller;
using Npgsql;

namespace EPMS.CustomActions
{
    public class ValidationActions
    {
        /// <summary>
        /// Validates the complete installation health after all components are installed.
        /// Checks: service status, database connectivity, port availability, API responsiveness.
        /// </summary>
        [CustomAction]
        public static ActionResult ValidateHealth(Session session)
        {
            session.Log("Validating installation health...");

            try
            {
                string host = session.CustomActionData["EPMS_DB_HOST"] ?? "localhost";
                string port = session.CustomActionData["EPMS_DB_PORT"] ?? "5432";
                string password = session.CustomActionData["EPMS_DB_PASSWORD"];
                string serverPort = session.CustomActionData["EPMS_PORT"] ?? "443";

                // 1. Check database connectivity
                session.Log("Checking database connectivity...");
                string connectionString = $"Host={host};Port={port};Database=epms;Username=postgres;Password={password};Timeout=10";
                using (var conn = new NpgsqlConnection(connectionString))
                {
                    conn.Open();
                    using (var cmd = new NpgsqlCommand("SELECT 1", conn))
                    {
                        cmd.ExecuteScalar();
                    }
                    session.Log("  ✓ Database connection successful");
                }

                // 2. Check that required services are running
                session.Log("Checking Windows services...");
                string[] services = {
                    "EPMS-API", "EPMS-EventProcessor", "EPMS-Analytics",
                    "EPMS-Reporting", "EPMS-Notifications", "EPMS-AgentGateway"
                };

                foreach (var service in services)
                {
                    var process = Process.Start(new ProcessStartInfo
                    {
                        FileName = "sc",
                        Arguments = $"query {service}",
                        UseShellExecute = false,
                        RedirectStandardOutput = true
                    });
                    string output = process.StandardOutput.ReadToEnd();
                    process.WaitForExit(5000);

                    if (output.Contains("RUNNING"))
                    {
                        session.Log($"  ✓ {service}: Running");
                    }
                    else if (output.Contains("STOPPED"))
                    {
                        session.Log($"  ⚠ {service}: Stopped (will be started automatically)");
                        // Attempt to start
                        Process.Start("net", $"start {service}").WaitForExit(10000);
                    }
                    else
                    {
                        session.Log($"  ⚠ {service}: Not found (may be disabled in feature selection)");
                    }
                }

                // 3. Check API endpoint
                session.Log("Checking API availability...");
                try
                {
                    using (var client = new HttpClient { Timeout = TimeSpan.FromSeconds(5) })
                    {
                        var response = client.GetAsync($"https://localhost:{serverPort}/health").Result;
                        if (response.IsSuccessStatusCode)
                        {
                            session.Log("  ✓ API endpoint responding");
                        }
                    }
                }
                catch (Exception)
                {
                    session.Log("  ⚠ API endpoint not yet available (services may still be starting)");
                }

                // 4. Verify port availability
                session.Log("Checking port configuration...");
                string[] portsToCheck = { "5432", "6379", "4222", "8000", "8001", "8002", "8003", "8004", "8005" };
                foreach (var checkPort in portsToCheck)
                {
                    try
                    {
                        using (var tcpClient = new TcpClient())
                        {
                            tcpClient.Connect("127.0.0.1", int.Parse(checkPort));
                            session.Log($"  ✓ Port {checkPort}: Open");
                        }
                    }
                    catch
                    {
                        session.Log($"  ⚠ Port {checkPort}: Not accessible (may be disabled)");
                    }
                }

                session.Log("Health validation completed.");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Health validation error: {ex.Message}");
                session.Log("Installation may still be functional. Check logs for details.");
                return ActionResult.Success; // Non-fatal: don't rollback on validation failure
            }
        }

        /// <summary>
        /// Validates user-provided configuration before proceeding with installation.
        /// Runs immediately (not deferred) to provide instant UI feedback.
        /// </summary>
        [CustomAction]
        public static ActionResult ValidateConfig(Session session)
        {
            session.Log("Validating installation configuration...");

            try
            {
                // Validate admin password
                string password = session["EPMS_ADMIN_PASSWORD"];
                if (password.Length < 12)
                {
                    session.Log("Password too short (minimum 12 characters)");
                    return ActionResult.Failure;
                }
                if (!System.Text.RegularExpressions.Regex.IsMatch(password, @"[A-Z]"))
                {
                    session.Log("Password must contain uppercase letter");
                    return ActionResult.Failure;
                }
                if (!System.Text.RegularExpressions.Regex.IsMatch(password, @"[a-z]"))
                {
                    session.Log("Password must contain lowercase letter");
                    return ActionResult.Failure;
                }
                if (!System.Text.RegularExpressions.Regex.IsMatch(password, @"[0-9]"))
                {
                    session.Log("Password must contain digit");
                    return ActionResult.Failure;
                }
                if (!System.Text.RegularExpressions.Regex.IsMatch(password, @"[!@#$%^&*(),.?:{}|<>]"))
                {
                    session.Log("Password must contain special character");
                    return ActionResult.Failure;
                }

                // Validate email
                string email = session["EPMS_ADMIN_EMAIL"];
                if (!email.Contains("@") || !email.Contains("."))
                {
                    session.Log("Invalid email address");
                    return ActionResult.Failure;
                }

                // Validate port
                string port = session["EPMS_PORT"];
                if (int.TryParse(port, out int portNum))
                {
                    if (portNum < 1 || portNum > 65535)
                    {
                        session.Log("Port must be between 1 and 65535");
                        return ActionResult.Failure;
                    }
                }
                else
                {
                    session.Log("Invalid port number");
                    return ActionResult.Failure;
                }

                session.Log("Configuration validation passed.");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Validation error: {ex.Message}");
                return ActionResult.Failure;
            }
        }
    }
}
