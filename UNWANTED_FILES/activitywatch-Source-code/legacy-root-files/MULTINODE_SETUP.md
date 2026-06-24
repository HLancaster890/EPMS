# ActivityWatch Multi-Node Setup

Centralised productivity data collection from multiple machines to a single server, with per-device authentication and optional bucket isolation.

## Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Laptop   │    │ Desktop  │    │  Other   │
│ Watchers ├───►│ Watchers ├───►│ Watchers │
└────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │
     │  Auth: Bearer │  Auth: Bearer │  Auth: Bearer
     │  + Node-Id    │  + Node-Id    │  + Node-Id
     ▼               ▼               ▼
┌──────────────────────────────────────────┐
│           Central Server                 │
│  aw-server-rust (--host 0.0.0.0)         │
│  Port 5600                               │
│  Auth: Master key / per-node keys        │
│  Isolation: laptop/ desktop/ buckets     │
└──────────────────────────────────────────┘
```

## Server Setup

### Prerequisites

- Windows (the server was built for x86_64-pc-windows-msvc)
- Network reachable from all client machines

### Files needed

| File | Description |
|------|-------------|
| `aw-server-rust.exe` | Modified server binary (v0.14.0 with auth + multi-node) |
| `aw-server-rust.exe.bak` | Original v0.13.2 backup |

### Config file

Location: `%APPDATA%\activitywatch\aw-server-rust\config.toml`

```toml
[server]
host = "0.0.0.0"
port = 5600

[auth]
# Master key grants full access to all buckets
api_key = "paste-a-random-generated-secret-here"

# Optional per-node keys for scoped access
[node_keys]
# "node-name" = "node-specific-key"
# laptop  = "laptop-secret"
# desktop = "desktop-secret"

[node]
# When true, each node's buckets are prefixed with the node ID
# e.g. laptop/aw-watcher-window-windows
isolation = false

# Optional HTTPS
# [tls]
# cert = "C:\\path\\to\\cert.pem"
# key  = "C:\\path\\to\\key.pem"
```

### Steps

1. Copy `aw-server-rust.exe` to `C:\Program Files (x86)\ActivityWatch\aw-server-rust\` on the server machine
2. Create the config file at `%APPDATA%\activitywatch\aw-server-rust\config.toml` with a strong random `api_key`
3. Open firewall port 5600:
   ```
   netsh advfirewall firewall add rule name="ActivityWatch" dir=in action=allow protocol=TCP localport=5600
   ```

### Running the Server

**Manually (command line):**
```powershell
# Basic - only reachable from this machine
"C:\Program Files (x86)\ActivityWatch\aw-server-rust\aw-server-rust.exe"

# Reachable from other machines on the network
"C:\Program Files (x86)\ActivityWatch\aw-server-rust\aw-server-rust.exe" --host 0.0.0.0

# Custom port
"C:\Program Files (x86)\ActivityWatch\aw-server-rust\aw-server-rust.exe" --host 0.0.0.0 --port 5600

# With web UI (point at Python aw-server's pre-built static files)
"C:\Program Files (x86)\ActivityWatch\aw-server-rust\aw-server-rust.exe" --host 0.0.0.0 --webpath "C:\Program Files (x86)\ActivityWatch\aw-server\aw_server\static"
```

**Via the system tray (aw-qt.exe):**
The server starts automatically when you launch `aw-qt.exe` from the Start Menu or `C:\Program Files (x86)\ActivityWatch\aw-qt.exe`.

**On Windows startup (via installer script):**
```powershell
.\server\install-server.ps1 -ApiKey "your-key"
```

This creates a shortcut in the Startup folder, so the server launches automatically when Windows boots.

### Verify server

```powershell
# Health check (no auth required)
curl http://<SERVER_IP>:5600/api/0/info

# List buckets (requires auth header)
$headers = @{ Authorization = "Bearer <api_key>" }
curl -Headers $headers http://<SERVER_IP>:5600/api/0/buckets
```

Expected output:
```
GET /api/0/info       -> 200 + JSON with hostname, version, device_id
GET /api/0/buckets    -> 200 from localhost (bypasses auth), 401 from remote without key
                       -> 200 from anywhere with valid Bearer token
```

### Web UI

Open `http://<SERVER_IP>:5600/` in a browser. The web UI loads without authentication when accessed from the server machine itself (localhost bypasses auth). From remote machines, API authentication is still enforced.

The web UI is served via `--webpath` pointing at the pre-built static files from the Python aw-server package. To serve the web UI permanently, include `--webpath` in your startup command.

---

## Client Setup (each node)

Each machine that sends data needs only the modified Python `aw-client` package. The watchers themselves are unchanged.

### 1. Install modified aw-client

On each node, replace the existing `aw-client`:

```bash
pip install --upgrade aw-client
```

Or install from the local copy:

```bash
cd C:\AW\activitywatch\aw-client
pip install -e .
```

### 2. Configure aw-client.toml

Location: `%APPDATA%\activitywatch\aw-client.toml`

```toml
[server]
server_url = "http://<SERVER_IP>:5600"
api_key = "<the-server-api-key>"
```

### 3. Set node identity (optional)

For bucket isolation, set the `AW_NODE_ID` environment variable to a unique name for this machine:

```cmd
setx AW_NODE_ID "my-laptop-name"
```

The node ID is also configurable via the `ActivityWatchClient` constructor in custom scripts:

```python
from aw_client import ActivityWatchClient
client = ActivityWatchClient("my-watcher", node_id="my-laptop-name")
```

### 4. Restart watchers

Restart `aw-qt.exe` (or the individual watchers) on each node. They will now send data to the central server.

### Verify client

Check that data appears on the server:

```powershell
$headers = @{ Authorization = "Bearer <api_key>" }
curl -Headers $headers http://<SERVER_IP>:5600/api/0/buckets
```

With isolation enabled, buckets appear as `<node_id>/<bucket_name>`.

---

## Security Notes

- The `api_key` is sent as a Bearer token in the `Authorization` header (no hashing)
- For production use over untrusted networks, **enable TLS** in the config and use `https://` in `server_url`
- The `/api/0/info` endpoint is always public (no auth required) for health-check purposes
- All other `/api/0/*` endpoints require a valid API key
- Empty `api_key` disables authentication entirely (not recommended for multi-node setups)

---

## Files Modified

| File | What changed |
|------|-------------|
| `aw-server-rust/aw-server/src/config.rs` | Added `AWAuthConfig`, `AWTlsConfig`, `AWNodeConfig` structs; `[auth]`, `[tls]`, `[node]` config sections |
| `aw-server-rust/aw-server/src/endpoints/apikey.rs` | New file: Bearer token auth fairing with master key + per-node keys |
| `aw-server-rust/aw-server/src/endpoints/mod.rs` | Mounts `ApiKeyCheck` fairing, passes config to Rocket |
| `aw-client/aw_client/config.py` | `load_local_server_api_key()` reads keys for any host, not just localhost |
| `aw-client/aw_client/client.py` | `node_id` parameter, `AW_API_KEY` env var, `X-Node-Id` header, `_effective_bucket_id()` prefixing |

## Source Code Location

All modified source code is at `C:\AW\activitywatch\` on the build machine.
