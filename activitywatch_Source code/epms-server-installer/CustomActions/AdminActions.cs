// EPMS Enterprise Server — Admin & Security Custom Actions

using System;
using System.IO;
using WixToolset.Dtf.WindowsInstaller;

using Org.BouncyCastle.Asn1;
using Org.BouncyCastle.Asn1.X509;
using Org.BouncyCastle.Crypto;
using Org.BouncyCastle.Crypto.Generators;
using Org.BouncyCastle.Crypto.Prng;
using Org.BouncyCastle.Math;
using Org.BouncyCastle.Pkcs;
using Org.BouncyCastle.Security;
using Org.BouncyCastle.X509;

namespace EPMS.CustomActions
{
    public class AdminActions
    {
        /// <summary>
        /// Creates the initial administrator account in the database.
        /// Hashes the password using BCrypt and inserts into the users table.
        /// </summary>
        [CustomAction]
        public static ActionResult CreateAdminAccount(Session session)
        {
            session.Log("Creating administrator account...");

            try
            {
                string email = session.CustomActionData["EPMS_ADMIN_EMAIL"];
                string password = session.CustomActionData["EPMS_ADMIN_PASSWORD"];
                string organization = session.CustomActionData["EPMS_ORGANIZATION"] ?? "Default Organization";
                string host = session.CustomActionData["EPMS_DB_HOST"] ?? "localhost";
                string port = session.CustomActionData["EPMS_DB_PORT"] ?? "5432";
                string dbPassword = session.CustomActionData["EPMS_DB_PASSWORD"];

                string connectionString = $"Host={host};Port={port};Database=epms;Username=postgres;Password={dbPassword};Timeout=30";

                using (var conn = new Npgsql.NpgsqlConnection(connectionString))
                {
                    conn.Open();

                    // Create default organization
                    using (var cmd = new Npgsql.NpgsqlCommand(
                        @"INSERT INTO organizations (id, name, is_active, created_at) 
                          VALUES (gen_random_uuid(), @org, true, NOW())
                          ON CONFLICT (name) DO NOTHING", conn))
                    {
                        cmd.Parameters.AddWithValue("org", organization);
                        cmd.ExecuteNonQuery();
                    }

                    // Get organization ID
                    Guid orgId;
                    using (var cmd = new Npgsql.NpgsqlCommand("SELECT id FROM organizations WHERE name = @org", conn))
                    {
                        cmd.Parameters.AddWithValue("org", organization);
                        orgId = (Guid)cmd.ExecuteScalar();
                    }

                    // Hash password with BCrypt
                    string passwordHash = BCrypt.Net.BCrypt.HashPassword(password, workFactor: 12);

                    // Create admin user
                    using (var cmd = new Npgsql.NpgsqlCommand(
                        @"INSERT INTO users (id, organization_id, email, password_hash, display_name, 
                          role, is_active, mfa_enabled, created_at, last_login)
                          VALUES (gen_random_uuid(), @orgId, @email, @hash, 'Administrator', 
                          'super_admin', true, false, NOW(), NOW())
                          ON CONFLICT (email) DO UPDATE SET password_hash = @hash, role = 'super_admin'", conn))
                    {
                        cmd.Parameters.AddWithValue("orgId", orgId);
                        cmd.Parameters.AddWithValue("email", email);
                        cmd.Parameters.AddWithValue("hash", passwordHash);
                        cmd.ExecuteNonQuery();
                    }

                    // Generate enrollment token for agents
                    string token = $"EPMS-ENROLL-{Guid.NewGuid():N}";
                    using (var cmd = new Npgsql.NpgsqlCommand(
                        @"INSERT INTO configuration (organization_id, scope, key, value)
                          VALUES (@orgId, 'organization', 'enrollment_token', @token::jsonb)", conn))
                    {
                        cmd.Parameters.AddWithValue("orgId", orgId);
                        cmd.Parameters.AddWithValue("token", "\"" + token + "\"");
                        cmd.ExecuteNonQuery();
                    }

                    session.Log($"Administrator account created: {email}");
                    session.Log($"Enrollment token: {token}");
                }

                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Admin account creation error: {ex.Message}");
                return ActionResult.Failure;
            }
        }

        /// <summary>
        /// Generates a self-signed X.509 certificate for development/test environments.
        /// Uses BouncyCastle for cross-platform .NET Standard 2.0 compatibility.
        /// </summary>
        [CustomAction]
        public static ActionResult GenerateSelfSignedCert(Session session)
        {
            session.Log("Generating self-signed SSL certificate...");

            try
            {
                string certPath = Environment.ExpandEnvironmentVariables(@"%ProgramData%\EPMS\Certs");
                Directory.CreateDirectory(certPath);

                string domain = session.CustomActionData["EPMS_DOMAIN"] ?? "localhost";
                string certFile = Path.Combine(certPath, "epms-server.pfx");
                string password = Guid.NewGuid().ToString("N");

                // Generate RSA key pair (4096 bits)
                var randomGenerator = new CryptoApiRandomGenerator();
                var secureRandom = new SecureRandom(randomGenerator);
                var keyGenerationParameters = new KeyGenerationParameters(secureRandom, 4096);
                var keyPairGenerator = new RsaKeyPairGenerator();
                keyPairGenerator.Init(keyGenerationParameters);
                AsymmetricCipherKeyPair keyPair = keyPairGenerator.GenerateKeyPair();

                // Build certificate subject and issuer DN
                var subjectDN = new X509Name($"CN={domain}, O=EPMS Enterprise Server, OU=IT");
                var issuerDN = subjectDN; // Self-signed: issuer == subject

                // Certificate generator
                var certGenerator = new X509V3CertificateGenerator();
                certGenerator.SetSerialNumber(BigInteger.ProbablePrime(128, secureRandom));
                certGenerator.SetIssuerDN(issuerDN);
                certGenerator.SetSubjectDN(subjectDN);
                certGenerator.SetNotBefore(DateTime.UtcNow.AddDays(-1));
                certGenerator.SetNotAfter(DateTime.UtcNow.AddYears(5));
                certGenerator.SetPublicKey(keyPair.Public);

                // Add Subject Alternative Names (SAN)
                var sanList = new Asn1EncodableVector
                {
                    new GeneralName(GeneralName.DnsName, domain),
                    new GeneralName(GeneralName.DnsName, "localhost"),
                    new GeneralName(GeneralName.IPAddress, "127.0.0.1"),
                    new GeneralName(GeneralName.IPAddress, "0.0.0.0")
                };
                certGenerator.AddExtension(
                    X509Extensions.SubjectAlternativeName.Id,
                    false,
                    new DerSequence(sanList));

                // Add Key Usage
                certGenerator.AddExtension(
                    X509Extensions.KeyUsage.Id,
                    true,
                    new KeyUsage(KeyUsage.DigitalSignature | KeyUsage.KeyEncipherment));

                // Add Extended Key Usage (Server Authentication)
                // Construct EKU as a SEQUENCE of OIDs — avoids KeyPurposeId naming variance
                // across Portable.BouncyCastle builds
                certGenerator.AddExtension(
                    X509Extensions.ExtendedKeyUsage.Id,
                    false,
                    new DerSequence(new DerObjectIdentifier("1.3.6.1.5.5.7.3.1")));

                // Add Basic Constraints
                certGenerator.AddExtension(
                    X509Extensions.BasicConstraints.Id,
                    true,
                    new BasicConstraints(false));

                // Sign the certificate with the private key
                Org.BouncyCastle.X509.X509Certificate certificate = certGenerator.Generate(keyPair.Private, secureRandom);

                // Convert BouncyCastle certificate to .NET X509Certificate2
                var store = new Pkcs12Store();
                string friendlyName = "EPMS Server Self-Signed Certificate";
                store.SetKeyEntry(friendlyName, new AsymmetricKeyEntry(keyPair.Private), new[] {
                    new X509CertificateEntry(certificate)
                });

                using (var ms = new MemoryStream())
                {
                    store.Save(ms, password.ToCharArray(), secureRandom);
                    ms.Seek(0, SeekOrigin.Begin);

                    // Load the PFX into an X509Certificate2
                    var certificate2 = new System.Security.Cryptography.X509Certificates.X509Certificate2(
                        ms.ToArray(), password,
                        System.Security.Cryptography.X509Certificates.X509KeyStorageFlags.Exportable);

                    // Save as PFX
                    File.WriteAllBytes(certFile, certificate2.Export(
                        System.Security.Cryptography.X509Certificates.X509ContentType.Pfx, password));

                    // Save as PEM (DER-encoded public cert)
                    File.WriteAllBytes(
                        Path.Combine(certPath, "epms-server.crt"),
                        certificate2.Export(System.Security.Cryptography.X509Certificates.X509ContentType.Cert));

                    // Export private key as PEM
                    string privateKeyPem = ExportPrivateKeyToPem(keyPair);
                    File.WriteAllText(
                        Path.Combine(certPath, "epms-server.key"),
                        privateKeyPem);
                }

                session.Log($"Self-signed certificate generated: {certFile}");
                return ActionResult.Success;
            }
            catch (Exception ex)
            {
                session.Log($"Certificate generation error: {ex.Message}");
                // Non-fatal — can be generated later via admin panel
                return ActionResult.Success;
            }
        }

        /// <summary>
        /// Converts a BouncyCastle private key to PEM format.
        /// </summary>
        private static string ExportPrivateKeyToPem(AsymmetricCipherKeyPair keyPair)
        {
            var privateKeyInfo = PrivateKeyInfoFactory.CreatePrivateKeyInfo(keyPair.Private);
            var base64 = Convert.ToBase64String(privateKeyInfo.GetDerEncoded(), Base64FormattingOptions.InsertLineBreaks);
            return "-----BEGIN PRIVATE KEY-----\n" + base64 + "\n-----END PRIVATE KEY-----";
        }
    }
}
