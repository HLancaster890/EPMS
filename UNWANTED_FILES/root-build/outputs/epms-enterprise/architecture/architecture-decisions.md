# EPMS Enterprise — Architecture Decision Records (ADRs)

## ADR-001: Python/FastAPI for server services

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Context** | The agent is already Python-based. Team is Python-skilled. Server needs async I/O for NATS/Redis/PostgreSQL. FastAPI is the de facto standard for async Python REST APIs. |
| **Decision** | Keep Python 3.10+ / FastAPI for all 6 server services. |
| **Consequences** | Cannot use `multiprocessing` or `uvicorn --workers >1` due to PyInstaller fork limitation. All services must be single-process. |
| **ADP-001.1** | If a service is CPU-bound (currently none are), extract that module to a standalone Go binary. |

## ADR-002: PyInstaller for packaging

| Field | Value |
|-------|-------|
| **Status** | Accepted (with caveats) |
| **Context** | Enterprise customers require a single `.exe` installer with no Python runtime dependency. PyInstaller is the most mature Python → .exe tool. |
| **Decision** | Use PyInstaller with COLLECT mode for all 6 server services. |
| **Consequences** | Must set `optimize=0`, `workers=1`, and maintain `hiddenimports` manually. Spec files must be updated every time a new dependency is added. |
| **ADP-002.1** | Set `upx=False` to avoid AV false positives. Add authenticode signing step to build pipeline. |

## ADR-003: NATS as message bus (not Kafka, not Redis Streams)

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Context** | Need a persistent message bus for the event pipeline: agent → gateway → processor → DB. Kafka is heavy (needs Zookeeper/KRaft, ~512MB+). Redis Streams lacks native pub/sub fanout. NATS is 10MB binary, has JetStream for persistence, and supports pub/sub. |
| **Decision** | Use NATS with JetStream enabled. |
| **Consequences** | NATS is less common than Kafka. Team must learn NATS concepts (subjects, streams, consumers). Limited UI tooling. |

## ADR-004: Embedded PostgreSQL (not external)

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Context** | Enterprise customers want single-server deployment. Requiring an external DBA to set up PostgreSQL is a dealbreaker for POC. |
| **Decision** | Bundle PostgreSQL 16 Windows installer within the WiX bundle and install as a Windows service. |
| **Consequences** | Adds ~200MB to installer size. PostgreSQL must be configured with appropriate `max_connections`, `shared_buffers` for the target scale. No managed backup (must be scripted). |
| **ADP-004.1** | Future: support external PostgreSQL as an alternative for high-scale deployments. |

## ADR-005: Organization isolation at query level (no RLS)

| Field | Value |
|-------|-------|
| **Status** | Accepted (interim) |
| **Context** | Multi-tenant data isolation is required. PostgreSQL Row-Level Security (RLS) is the ideal solution but requires careful implementation and adds complexity. The current system already has `organization_id` on all tables. |
| **Decision** | For MVP, enforce org isolation at the application layer: all dashboard/agent queries include `WHERE organization_id = $token.org_id`. Migrate to RLS in v2. |
| **Consequences** | Code review finds this is currently NOT implemented — all queries are cross-org. Must add application-layer scoping immediately. RLS migration in v2 will provide defense-in-depth. |

## ADR-006: API key in first WebSocket message (not query string)

| Field | Value |
|-------|-------|
| **Status** | Proposed |
| **Context** | Current gateway accepts API key as WS query parameter. This exposes the key to proxy logs, browser history, and Referer headers. |
| **Decision** | Move API key authentication to the first WebSocket message sent by the agent after connection. Gateway reads first message, validates key, then begins normal message processing. If validation fails, send error and close. |
| **Consequences** | Agent `ws_client.py` must send an auth message immediately after WS connect. Backward compatibility break — requires agent + gateway update in same release. |

## ADR-007: Agent writes REST fallback (no SQLite offline buffer)

| Field | Value |
|-------|-------|
| **Status** | Deferred |
| **Context** | During network outages, the agent currently drops events silently. An offline SQLite buffer would queue events and replay them on reconnection. |
| **Decision** | Defer offline buffer to v1.1. MVP ships with in-memory queue only. |
| **Consequences** | Events during network outage are lost. Acceptable for MVP; critical for production compliance. Revisit when customer requires 99.9% event delivery guarantee. |

## ADR-008: Config file (not env vars) for on-prem deployment

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Context** | Windows Service environment variables are awkward to manage (registry, reboot required for changes). A JSON config file is editable directly by the admin. |
| **Decision** | All service configuration is in `appsettings.json` at `C:\ProgramData\EPMS\Config\`. Services read via `APP_SETTINGS_PATH` env var pointing to this file. |
| **Consequences** | Plaintext secrets on disk (DB password, JWT secret, SMTP credentials). Mitigation: NTFS ACL to restrict to `SYSTEM` and `Administrators`. Future: add config encryption for secrets section. |

## ADR-009: Vanilla JS dashboard (no React in MVP)

| Field | Value |
|-------|-------|
| **Status** | Accepted (interim) |
| **Context** | Dashboard is currently a single `index.html` with Chart.js and fetch API. Adding React would add 2 weeks to build pipeline setup (Vite, TypeScript, component tree, routing). |
| **Decision** | Keep vanilla JS for MVP. Add Webpack + TypeScript for bundling and type safety. Re-evaluate React when >5 dashboard pages exist. |
| **Consequences** | No component reusability. JS will become harder to maintain as features grow. Acceptable for 9-page MVP dashboard. |

## ADR-010: TimescaleDB extension (deferred to v1.1)

| Field | Value |
|-------|-------|
| **Status** | Deferred |
| **Context** | Event tables will grow huge (>100M rows at 1K agents × 90 days). TimescaleDB hypertables provide automatic partitioning, compression, and built-in retention policies. |
| **Decision** | Defer to v1.1. For MVP, add plain PostgreSQL indexes and a custom purge function. |
| **Consequences** | At >5K agents, manual partition management will be needed. Migration to TimescaleDB is additive (install extension, convert tables to hypertables — no data loss). |
