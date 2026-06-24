// EPMS Enterprise Server — Configuration Generation Custom Actions

using System;
using System.IO;
using System.Text.Json;
using WixToolset.Dtf.WindowsInstaller;

namespace EPMS.CustomActions
{
    public class ConfigActions
    {
        /// <summary>
        /// Generates appsettings.json from template with installation-time values.
        /// This is the primary configuration file for all EPMS services.
        /// </summary>
        [CustomAction]
        public static ActionResult GenerateConfiguration(Session session)
        {
            session.Log("Generating server configuration...");

            try
            {
                string installPath = session.CustomActionData["INSTALLFOLDER"];
                string configPath = Path.Combine(installPath, "config");
                string host = session.CustomActionData["EPMS_DB_HOST"] ?? "localhost";
                string port = session.CustomActionData["EPMS_DB_PORT"] ?? "5432";
                string dbPassword = session.CustomActionData["EPMS_DB_PASSWORD"];
                string serverPort = session.CustomActionData["EPMS_PORT"] ?? "443";
                string domain = session.CustomActionData["EPMS_DOMAIN"] ?? "localhost";
                string bindAddress = session.CustomActionData["EPMS_BIND_ADDRESS"] ?? "0.0.0.0";
                string sslMode = session.CustomActionData["EPMS_SSL_MODE"] ?? "self-signed";

                var config = new
                {
                    server = new
                    {
                        bind_address = bindAddress,
                        port = int.Parse(serverPort),
                        domain = domain,
                        ssl_mode = sslMode,
                        ssl_cert_path = @"%ProgramData%\EPMS\Certs\epms-server.pfx",
                        cors_origins = new[] { "*" },
                        log_level = "info",
                        log_retention_days = 30
                    },
                    database = new
                    {
                        host = host,
                        port = int.Parse(port),
                        name = "epms",
                        user = "postgres",
                        password = dbPassword,
                        max_connections = 100,
                        pool_size = 20,
                        command_timeout_seconds = 60,
                        enable_audit_log = true
                    },
                    redis = new
                    {
                        host = "localhost",
                        port = 6379,
                        password = "",
                        db = 0,
                        ssl = false,
                        connection_timeout_ms = 5000,
                        retry_count = 3
                    },
                    nats = new
                    {
                        url = "nats://localhost:4222",
                        user = "epms",
                        password = "",
                        max_reconnect = 10,
                        reconnect_wait_ms = 2000,
                        enable_jetstream = true
                    },
                    auth = new
                    {
                        jwt_secret = Guid.NewGuid().ToString("N") + Guid.NewGuid().ToString("N"),
                        jwt_access_token_expiry_minutes = 15,
                        jwt_refresh_token_expiry_days = 7,
                        mfa_enabled = false,
                        mfa_issuer = "EPMS Enterprise Server",
                        session_timeout_minutes = 480,
                        max_concurrent_sessions = 3,
                        lockout_threshold = 5,
                        lockout_duration_minutes = 15,
                        password_min_length = 12,
                        password_require_uppercase = true,
                        password_require_lowercase = true,
                        password_require_digit = true,
                        password_require_special = true
                    },
                    services = new
                    {
                        api = new { port = 8000, workers = 4 },
                        analytics = new { port = 8001, workers = 2, aggregation_interval_minutes = 5 },
                        reporting = new { port = 8002, workers = 2, output_dir = Path.Combine(installPath, "data", "reports") },
                        notifications = new { port = 8003, workers = 2 },
                        event_processor = new { port = 8004, workers = 4, batch_size = 1000, flush_interval_ms = 1000 },
                        agent_gateway = new { port = 8005, max_connections = 10000, heartbeat_timeout_seconds = 60 }
                    },
                    monitoring = new
                    {
                        metrics_enabled = true,
                        metrics_port = 9090,
                        health_check_interval_seconds = 30,
                        enable_prometheus = true
                    }
                };

                string json = JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(Path.Combine(configPath, "appsettings.json"), json);

                session.Log("Configuration file generated: appsettings.json");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Configuration generation error: {ex.Message}");
                return ActionResult.Failure;
            }
        }
    }
}
