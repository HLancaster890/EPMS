# EPMS Enterprise - Productivity Monitoring System

Enterprise-grade productivity monitoring system with WebSocket gateway, agent
clients, and continuous real-time monitoring.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Install the packages:

```bash
cd activitywatch_Source\ code\epms-agent-client
pip install -e .
pip install websocket-client psutil requests pyinstaller
```

### Start the Gateway Server

```bash
realease\bin\start-gateway.bat
```

Or manually:

```bash
python -m epms_gateway --port 8005 --api-keys "epms-dev-key-2024"
```

### Start an Agent Client

```bash
realease\bin\start-agent.bat
```

Or manually:

```bash
python -m epms_agent --config realease\config\agent.json --verbose --no-tray
```

### Continuous Productivity Monitor

```bash
python realease\bin\monitor-productivity.py
```

This starts the gateway, connects an agent, and continuously streams heartbeats
with live AFK status, active window tracking, and system health.

### Run E2E Test

```bash
realease\bin\run-e2e-test.bat
```

## 📁 Release Structure

```
realease/
├── README.md                     # This file
├── bin/
│   ├── start-gateway.bat         # Start the gateway server
│   ├── start-agent.bat           # Start an agent client
│   ├── monitor-productivity.py   # Continuous productivity monitoring
│   ├── run-e2e-test.bat          # End-to-end integration test
│   └── build-exe.bat             # Build standalone executables (PyInstaller)
├── config/
│   ├── gateway.json              # Gateway server configuration
│   └── agent.json                # Agent client configuration
├── logs/                         # Runtime logs (auto-created)
└── data/                         # Test reports (auto-created)
```

## ⚙️ Configuration

### Gateway (`config/gateway.json`)

| Field | Default | Description |
|-------|---------|-------------|
| `host` | `127.0.0.1` | Bind address |
| `port` | `8005` | WebSocket port |
| `api_keys` | `["dev-key"]` | Valid API keys for auth |
| `max_connections` | `100` | Max concurrent agents |
| `rate_limit_per_second` | `200` | Max msgs/sec per agent |
| `heartbeat_timeout_seconds` | `120` | Disconnect idle agents |

### Agent (`config/agent.json`)

| Field | Default | Description |
|-------|---------|-------------|
| `server.host` | `127.0.0.1` | Gateway host |
| `server.ws_port` | `8005` | WebSocket port |
| `server.api_key` | `dev-key` | API key for auth |
| `monitoring.heartbeat_interval_seconds` | `10` | Heartbeat frequency |
| `monitoring.afk_timeout_minutes` | `5` | AFK detection threshold |

## 🧪 Testing

```bash
# Run all tests
cd activitywatch_Source\ code\epms-agent-client
python -m pytest tests/ -v

# Run specific tests
python -m pytest tests/integration/test_gateway.py -v
python -m pytest tests/unit/test_ws_client.py -v
```

## 📦 Building Standalone Executables

```bash
realease\bin\build-exe.bat
```

This creates standalone `.exe` files in `realease\dist\` that run without Python:

- `epms-gateway-server.exe`
- `epms-agent-client.exe`

## 🔌 Architecture

```
┌──────────────────┐         WebSocket (WSS)        ┌──────────────────┐
│  Agent Client 1  │ ◄═══════════════════════════► │                  │
│  (Windows/Mac)   │                               │   EPMS Gateway   │
└──────────────────┘                               │   (epms_gateway) │
                                                    │                  │
┌──────────────────┐         WebSocket (WSS)        │  - Auth          │
│  Agent Client 2  │ ◄═══════════════════════════► │  - Rate Limit    │
│  (Linux)         │                               │  - Multi-Client  │
└──────────────────┘                               │  - TLS/SSL       │
                                                    │  - Health API    │
┌──────────────────┐                               └──────────────────┘
│  Agent Client N  │
│  (any OS)        │
└──────────────────┘
```

## 🔐 Security

- **API Key Authentication**: Every WebSocket connection requires a valid API key
- **Agent ID Validation**: Agent IDs restricted to `[a-zA-Z0-9_-]{1,64}`
- **Rate Limiting**: Per-agent message rate enforced
- **Heartbeat Timeout**: Idle agents automatically disconnected
- **SSL/TLS**: Optional WSS via `--ssl-cert` / `--ssl-key`
- **Safe Logging**: Agent IDs truncated in logs for privacy

## 🩺 Health Check

```bash
curl http://127.0.0.1:8005/ws/health
# {"status":"healthy","agents":3}
```

## 📄 License

Part of the ActivityWatch project. See `LICENSE.txt` for details.
